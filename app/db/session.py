#!/usr/bin/env python
"""
Database session management with SQLCipher encryption for HideSync.

This module provides robust, production-ready database session management with:
1. Transparent SQLCipher encryption support
2. Connection pooling with health checks
3. Session management with SQLAlchemy
4. Comprehensive error handling and recovery
5. Performance optimizations for both encrypted and non-encrypted modes

Usage:
    from app.db.session import get_db

    # In FastAPI dependency
    def some_endpoint(db: Session = Depends(get_db)):
        # Use db for database operations
        ...
"""

import os
import logging
import threading
import datetime
import gc
from typing import Generator, Any, Optional, Dict, List, TypeVar

from contextlib import contextmanager
import functools
from app.sqlcipher_dialect import SQLCipherDialect
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.inspection import inspect
import sqlite3
import sqlalchemy

from app.core.key_manager import KeyManager
from app.core.exceptions import SecurityException, EncryptionKeyMissingException
from app.core.config import settings
from app.db.models.base import Base

# Configure module logger
logger = logging.getLogger(__name__)

# Define a generic model type for type hints
ModelT = TypeVar("ModelT", bound=Any)

# Constants
CONNECTION_RETRY_DELAY = 0.5  # seconds
CONNECTION_HEALTH_CHECK_INTERVAL = 60  # seconds
CONNECTION_MAX_AGE = 1800  # 30 minutes
CONNECTION_MAX_IDLE_TIME = 300  # 5 minutes
CONNECTION_POOL_RECYCLE = 900  # 15 minutes
CONNECTION_POOL_SIZE = getattr(settings, "DB_POOL_SIZE", 5)
CONNECTION_MAX_OVERFLOW = getattr(settings, "DB_MAX_OVERFLOW", 10)
CONNECTION_POOL_TIMEOUT = getattr(settings, "DB_POOL_TIMEOUT", 30)
CONNECTION_POOL_PRE_PING = True


# -----------------------------------------------------------------------------
# Encryption Management
# -----------------------------------------------------------------------------


class EncryptionManager:
    """
    Manages database encryption with SQLCipher.

    This class handles encryption key management, connection configuration,
    and provides a consistent interface for encrypted database operations.
    """

    _encryption_key: Optional[str] = None
    _sqlcipher_available: bool = False
    _sqlcipher_module = None
    _pragma_statements: Dict[str, str] = {
        "key": None,  # Will be set during initialization
        "cipher_page_size": "4096",
        "kdf_iter": "256000",
        "cipher_hmac_algorithm": "HMAC_SHA512",
        "cipher_kdf_algorithm": "PBKDF2_HMAC_SHA512",
        "foreign_keys": "ON",
    }
    _initialization_lock = threading.RLock()
    _initialized = False

    @classmethod
    def initialize(cls) -> None:
        """Initialize encryption manager, loading keys and checking availability."""
        with cls._initialization_lock:
            if cls._initialized:
                return

            try:
                cls._load_encryption_key()
                cls._check_sqlcipher_availability()

                # Set key PRAGMA once we have the key
                if cls._encryption_key:
                    cls._pragma_statements["key"] = f"\"x'{cls._encryption_key}'\""

                cls._initialized = True
                logger.info("Encryption manager initialized successfully")
            except Exception as e:
                logger.error(
                    f"Failed to initialize encryption manager: {e}", exc_info=True
                )
                raise

    @classmethod
    def get_encrypted_connection(cls, db_path: str) -> sqlite3.Connection:
        """
        Creates and returns a SQLCipher connection object with proper encryption configuration.

        Args:
            db_path: Path to the SQLite database file

        Returns:
            An initialized and configured SQLCipher connection

        Raises:
            RuntimeError: If SQLCipher is not available
            ValueError: If encryption key is missing
            Exception: If connection fails
        """
        if not cls.is_sqlcipher_available():
            raise RuntimeError(
                "SQLCipher is not available but an encrypted connection was requested"
            )

        encryption_key = cls.get_key()
        if not encryption_key:
            raise ValueError("Failed to retrieve database encryption key")

        try:
            sqlcipher = cls.get_sqlcipher_module()

            # Create the connection
            conn = sqlcipher.connect(db_path)

            # CRITICAL: Apply encryption key IMMEDIATELY after opening connection
            # Don't do anything else before setting the key
            cursor = conn.cursor()

            # Format the key properly
            key_pragma = f"\"x'{encryption_key}'\""
            cursor.execute(f"PRAGMA key = {key_pragma};")

            # Test the connection with a simple query to verify the key works
            try:
                cursor.execute("SELECT 1;").fetchone()
            except Exception as e:
                # Key verification failed - this is likely a key mismatch
                cursor.close()
                conn.close()
                logger.error(f"Database key verification failed: {str(e)}")
                raise ValueError(
                    f"Database encryption key appears to be incorrect: {str(e)}"
                )

            # Now apply other PRAGMA settings
            for pragma, value in cls._pragma_statements.items():
                if pragma != "key":  # We already set the key
                    cursor.execute(f"PRAGMA {pragma}={value};")

            cursor.close()
            return conn

        except ValueError:
            # Re-raise key verification errors
            raise
        except Exception as e:
            logger.error(f"Failed to create encrypted connection: {str(e)}")
            raise

    @classmethod
    def verify_encryption_key(cls, db_path: str, encryption_key: str = None) -> bool:
        """
        Verify that an encryption key can successfully open a database.

        Args:
            db_path: Path to the database file
            encryption_key: Optional specific key to test (uses default if None)

        Returns:
            True if key works, False otherwise
        """
        if not os.path.exists(db_path):
            logger.error(f"Cannot verify key: Database file {db_path} does not exist")
            return False

        if not cls.is_sqlcipher_available():
            logger.error("Cannot verify key: SQLCipher not available")
            return False

        # Use provided key or get stored key
        key = encryption_key or cls.get_key()
        if not key:
            logger.error("Cannot verify key: No encryption key available")
            return False

        conn = None
        cursor = None
        try:
            sqlcipher = cls.get_sqlcipher_module()
            conn = sqlcipher.connect(db_path)
            cursor = conn.cursor()

            # Try to decrypt with the key
            key_pragma = f"\"x'{key}'\""
            cursor.execute(f"PRAGMA key = {key_pragma};")

            # If key is incorrect, this will fail
            cursor.execute("SELECT count(*) FROM sqlite_master;")
            result = cursor.fetchone()

            logger.info(
                f"Key verification successful: database contains {result[0]} tables"
            )
            return True

        except Exception as e:
            if "file is not a database" in str(e):
                logger.error(
                    f"Key verification failed: incorrect encryption key for {db_path}"
                )
            else:
                logger.error(f"Key verification failed: {str(e)}")
            return False

        finally:
            if cursor:
                try:
                    cursor.close()
                except:
                    pass
            if conn:
                try:
                    conn.close()
                except:
                    pass

    @classmethod
    def _load_encryption_key(cls) -> None:
        """
        Load the encryption key from the key manager.

        Raises:
            RuntimeError: If the key fails to load and encryption is enabled
        """
        try:
            cls._encryption_key = KeyManager.get_database_encryption_key()
            if cls._encryption_key:
                logger.debug("Encryption key loaded successfully")
            elif settings.USE_SQLCIPHER:
                logger.error("KeyManager returned no key, but SQLCipher is enabled")
                raise EncryptionKeyMissingException(
                    "Mandatory encryption key failed to load"
                )
            else:
                logger.info("No encryption key loaded (SQLCipher disabled)")
        except SecurityException as e:
            logger.error(f"Failed to load encryption key via KeyManager: {e}")
            if settings.USE_SQLCIPHER:
                raise EncryptionKeyMissingException(
                    f"Mandatory encryption key failed to load: {e}"
                ) from e
            else:
                logger.warning(
                    "KeyManager failed, but SQLCipher is disabled. Proceeding without encryption"
                )
                cls._encryption_key = None
        except Exception as e:
            logger.exception(f"Unexpected error during encryption key loading: {e}")
            if settings.USE_SQLCIPHER:
                raise RuntimeError(
                    f"Mandatory encryption key failed to load: {e}"
                ) from e
            else:
                logger.warning(
                    "Key loading failed, but SQLCipher is disabled. Proceeding without encryption"
                )
                cls._encryption_key = None

    @classmethod
    def _check_sqlcipher_availability(cls) -> None:
        """
        Check if SQLCipher is available and configure accordingly.

        Raises:
            ImportError: If SQLCipher is requested but libraries are not installed
        """
        if settings.USE_SQLCIPHER:
            try:
                import pysqlcipher3.dbapi2 as sqlcipher

                cls._sqlcipher_available = True
                cls._sqlcipher_module = sqlcipher
                logger.info(
                    "SQLCipher libraries detected and will be used for database encryption"
                )
            except ImportError:
                cls._sqlcipher_available = False
                cls._sqlcipher_module = None
                logger.error(
                    "SQLCipher requested (USE_SQLCIPHER=true) but libraries (pysqlcipher3) not found"
                )
                raise ImportError(
                    "pysqlcipher3 library not found, but USE_SQLCIPHER is true"
                )
        else:
            cls._sqlcipher_available = False
            cls._sqlcipher_module = None
            logger.info(
                "SQLCipher encryption disabled in settings (USE_SQLCIPHER=false)"
            )

    @classmethod
    def get_key(cls) -> Optional[str]:
        """Get the current encryption key."""
        return cls._encryption_key

    @classmethod
    def is_sqlcipher_available(cls) -> bool:
        """Check if SQLCipher is available for use."""
        return cls._sqlcipher_available

    @classmethod
    def get_sqlcipher_module(cls):
        """Get the SQLCipher module for direct usage."""
        return cls._sqlcipher_module

    @classmethod
    def format_key_for_pragma(cls) -> str:
        """Format the encryption key for use in PRAGMA statements."""
        key = cls.get_key()
        if not key:
            raise ValueError("No encryption key available")
        return f"\"x'{key}'\""

    @classmethod
    def create_new_encrypted_database(cls, path: str) -> bool:
        """
        Create a new encrypted database.

        Args:
            path: Path where the database should be created

        Returns:
            True if creation succeeded, False otherwise
        """
        if not cls.is_sqlcipher_available():
            logger.error("Cannot create: SQLCipher not available")
            return False
        if not cls.get_key():
            logger.error("Cannot create: Encryption key not loaded")
            return False

        conn = None
        cursor = None
        try:
            if os.path.exists(path):
                logger.info(f"Removing existing database at {path}")
                os.remove(path)

            sqlcipher = cls.get_sqlcipher_module()
            conn = sqlcipher.connect(path)
            cursor = conn.cursor()

            # Apply all PRAGMA statements
            for pragma, value in cls._pragma_statements.items():
                if pragma == "key":
                    cursor.execute(f"PRAGMA key = {value};")
                else:
                    cursor.execute(f"PRAGMA {pragma}={value};")

            # Create a test table to verify encryption works
            cursor.execute("CREATE TABLE _encryption_test (id INTEGER PRIMARY KEY);")
            cursor.execute("DROP TABLE _encryption_test;")

            conn.commit()
            logger.info(f"New encrypted database created successfully at {path}")
            return True

        except Exception as e:
            logger.error(f"Failed to create encrypted database: {e}")
            # Cleanup attempt
            if os.path.exists(path):
                try:
                    if cursor:
                        cursor.close()
                    if conn:
                        conn.close()
                    conn = None
                    logger.debug(
                        f"Attempting to remove potentially corrupted DB file: {path}"
                    )
                    os.remove(path)
                except Exception as remove_e:
                    logger.error(f"Failed to remove DB file during cleanup: {remove_e}")
            return False
        finally:
            # Final cleanup of resources
            if cursor:
                try:
                    cursor.close()
                except Exception as cursor_e:
                    logger.error(f"Error closing cursor in finally: {cursor_e}")
            if conn:
                try:
                    conn.close()
                except Exception as conn_e:
                    logger.error(f"Error closing connection in finally: {conn_e}")

    @classmethod
    def create_tables_direct(cls, path: str, metadata) -> bool:
        """
        Create database tables using SQLCipher directly, bypassing SQLAlchemy.

        Args:
            path: Path to the database
            metadata: SQLAlchemy metadata containing table definitions

        Returns:
            True if tables were created successfully, False otherwise
        """
        if not cls.is_sqlcipher_available():
            logger.error("Cannot create tables directly: SQLCipher not available")
            return False

        if not cls.get_key():
            logger.error("Cannot create tables directly: Encryption key not loaded")
            return False

        # Generate table schemas from SQLAlchemy metadata
        from sqlalchemy.schema import CreateTable

        create_statements = []
        for table in metadata.sorted_tables:
            create_statements.append(
                str(
                    CreateTable(table).compile(
                        dialect=sqlalchemy.dialects.sqlite.dialect()
                    )
                )
            )

        conn = None
        cursor = None
        try:
            sqlcipher = cls.get_sqlcipher_module()
            conn = sqlcipher.connect(path)
            cursor = conn.cursor()

            # Apply all PRAGMA statements
            for pragma, value in cls._pragma_statements.items():
                if pragma == "key":
                    cursor.execute(f"PRAGMA key = {value};")
                else:
                    cursor.execute(f"PRAGMA {pragma}={value};")

            # Execute each CREATE TABLE statement
            for statement in create_statements:
                logger.debug(
                    f"Executing: {statement[:60]}..."
                )  # Log just the beginning
                cursor.execute(statement)

            conn.commit()

            # Verify table creation
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            table_names = [t[0] for t in tables]
            logger.info(f"Created {len(table_names)} tables directly with SQLCipher")

            if logger.isEnabledFor(logging.DEBUG):
                table_list = ", ".join(table_names[:5])
                if len(table_names) > 5:
                    table_list += "..."
                logger.debug(f"Tables created: {table_list}")

            return True

        except Exception as e:
            logger.error(f"Failed to create tables directly: {e}")
            return False
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception as e:
                    logger.error(f"Error closing cursor: {e}")
            if conn:
                try:
                    conn.close()
                except Exception as e:
                    logger.error(f"Error closing connection: {e}")

    @classmethod
    def test_encrypted_database(cls, path: str) -> bool:
        """
        Test if an encrypted database can be opened with the current key.

        Args:
            path: Path to the database

        Returns:
            True if database can be opened, False otherwise
        """
        if not cls.is_sqlcipher_available() or not os.path.exists(path):
            return False

        if not cls.get_key():
            logger.warning("Cannot test: Encryption key not loaded")
            return False

        conn = None
        cursor = None
        try:
            sqlcipher = cls.get_sqlcipher_module()
            conn = sqlcipher.connect(path)
            cursor = conn.cursor()

            # Apply all PRAGMA statements
            for pragma, value in cls._pragma_statements.items():
                if pragma == "key":
                    cursor.execute(f"PRAGMA key = {value};")
                else:
                    cursor.execute(f"PRAGMA {pragma}={value};")

            cursor.execute("SELECT count(*) FROM sqlite_master;")
            result = cursor.fetchone()  # Get result before closing

            if result is None:
                logger.error(f"Test query returned no result for {path}")
                return False  # Should get at least 0

            logger.info(
                f"Successfully tested encrypted database at {path} ({result[0]} tables found)"
            )
            return True

        except Exception as e:
            if "file is not a database" in str(e):
                logger.error(f"Failed test: Incorrect key or corrupted file at {path}")
            else:
                logger.error(f"Failed test at {path}: {e}")
            return False
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception as cursor_e:
                    logger.error(f"Error closing cursor in finally: {cursor_e}")
            if conn:
                try:
                    conn.close()
                except Exception as conn_e:
                    logger.error(f"Error closing connection in finally: {conn_e}")


# Initialize encryption configuration ONCE
EncryptionManager.initialize()


# -----------------------------------------------------------------------------
# Database Connection Setup
# -----------------------------------------------------------------------------
def get_database_path() -> str:
    """
    Get the database path from settings.

    Returns:
        Absolute path to the database file

    Raises:
        ValueError: If no database path is configured
    """
    if settings.DATABASE_PATH:
        db_path = os.path.abspath(settings.DATABASE_PATH)
        logger.info(f"Using database path: {db_path}")
        return db_path
    elif settings.DATABASE_URL:
        if settings.DATABASE_URL.startswith("sqlite"):
            # Extract path from sqlite URL
            # Ensure correct handling for different path formats (e.g., relative vs. absolute)
            db_url_path = settings.DATABASE_URL.split(":///", 1)[1]
            if not os.path.isabs(db_url_path):
                # Handle relative paths potentially specified in the URL
                # Assuming relative to project root or a specific base dir might be needed
                # For simplicity here, we make it absolute from CWD, adjust if needed
                db_path = os.path.abspath(db_url_path)
                logger.warning(
                    f"DATABASE_URL uses relative path '{db_url_path}'. Resolving to absolute path: {db_path}"
                )
            else:
                db_path = db_url_path

            logger.info(f"Extracted database path from URL: {db_path}")
            return db_path
        else:
            logger.error(
                f"Non-SQLite URL not supported with SQLCipher/standard SQLite mode: {settings.DATABASE_URL}"
            )
            raise ValueError(
                "Only SQLite URLs (sqlite:///...) are supported by this configuration"
            )
    else:
        # Consider providing a default path if none is specified, e.g., in user data directory
        raise ValueError(
            "No database path specified in settings (DATABASE_PATH or DATABASE_URL)"
        )


# Get database path
db_path = get_database_path()

# Determine if we should use SQLCipher based on settings and availability
use_sqlcipher = settings.USE_SQLCIPHER and EncryptionManager.is_sqlcipher_available()

# Create the engine based on encryption settings
if use_sqlcipher:
    logger.info(f"Creating SQLAlchemy engine with SQLCipher support for {db_path}")
    engine = create_engine(
        f"sqlcipher:///{db_path}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=CONNECTION_POOL_SIZE,
        max_overflow=CONNECTION_MAX_OVERFLOW,
        pool_timeout=CONNECTION_POOL_TIMEOUT,
        pool_pre_ping=CONNECTION_POOL_PRE_PING,
        pool_recycle=CONNECTION_POOL_RECYCLE,
    )

    # Add additional event listeners if needed
    @event.listens_for(engine, "connect")
    def _sqlcipher_on_connect(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    # Verify the engine works
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            logger.info(
                f"SQLAlchemy SQLCipher engine connection test successful: {result}"
            )
    except Exception as e:
        logger.critical(f"Failed to initialize SQLCipher engine: {e}", exc_info=True)
        raise RuntimeError(
            f"Could not initialize SQLCipher database connection: {e}"
        ) from e

else:
    # Standard SQLite Mode (No encryption)
    logger.info(
        f"Creating standard SQLAlchemy engine for non-encrypted database: {db_path}"
    )
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=CONNECTION_POOL_SIZE,
        max_overflow=CONNECTION_MAX_OVERFLOW,
        pool_timeout=CONNECTION_POOL_TIMEOUT,
        pool_pre_ping=CONNECTION_POOL_PRE_PING,
        pool_recycle=CONNECTION_POOL_RECYCLE,
        echo=settings.DEBUG,
    )

    # Add event listener for standard SQLite connections
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    # Verify the engine
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            logger.info(
                f"Standard SQLAlchemy engine connection test successful: {result}"
            )
    except Exception as e:
        logger.critical(
            f"Failed to initialize standard SQLite engine: {e}", exc_info=True
        )
        raise RuntimeError(
            f"Could not initialize standard SQLite database connection: {e}"
        ) from e

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# -----------------------------------------------------------------------------
# FastAPI Dependency
# -----------------------------------------------------------------------------


def get_db() -> Generator[Session, None, None]:
    """
    Get a database session with proper resource management.

    Returns:
        SQLAlchemy Session for database operations
    """
    thread_id = threading.get_ident()
    logger.debug(f"Creating DB session for thread {thread_id}")

    # Force garbage collection to reduce memory pressure
    gc.collect()

    # Create a new session
    db = SessionLocal()

    try:
        yield db
    except Exception as e:
        logger.error(f"Error in get_db for thread {thread_id}: {e}")
        raise
    finally:
        db.close()
        logger.debug(f"Closed DB session for thread {thread_id}")


# -----------------------------------------------------------------------------
# Transaction Support
# -----------------------------------------------------------------------------


@contextmanager
def transaction(session=None):
    """
    Context manager for database transactions.

    Args:
        session: Optional session to use (if None, creates a new one)

    Yields:
        Database session for use within the transaction
    """
    close_session = False

    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        if close_session and session:
            session.close()


def with_transaction(func):
    """
    Decorator to wrap a function in a transaction.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Check if session is already provided
        session_in_args = any(isinstance(arg, Session) for arg in args)
        session_in_kwargs = "session" in kwargs and isinstance(
            kwargs["session"], Session
        )

        if session_in_args or session_in_kwargs:
            # Session already provided, just call the function
            return func(*args, **kwargs)
        else:
            # Create a new session and wrap in transaction
            with transaction() as session:
                return func(*args, session=session, **kwargs)

    return wrapper


# -----------------------------------------------------------------------------
# Database Verification and Initialization
# -----------------------------------------------------------------------------


def verify_db_connection() -> bool:
    """
    Verify that we can connect to the database.

    Returns:
        True if connection succeeds, False otherwise
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar()
            logger.info(f"Database connection verified: {result}")
            return True
    except Exception as e:
        logger.error(f"Database connection verification failed: {e}")
        return False


def init_db(reset: bool = False) -> bool:
    """
    Initialize the database schema.

    Args:
        reset: Whether to reset (drop and recreate) the database

    Returns:
        True if initialization succeeds, False otherwise
    """
    logger.info("Initializing database schema...")

    try:
        if use_sqlcipher:
            if reset or not os.path.exists(db_path):
                action = "Resetting" if reset else "Creating new"
                logger.info(f"{action} encrypted database at {db_path}")
                if not EncryptionManager.create_new_encrypted_database(db_path):
                    logger.error("Failed to create new encrypted database")
                    return False
                logger.info("New encrypted database created")
            elif not EncryptionManager.test_encrypted_database(db_path):
                logger.error(
                    f"Existing encrypted database test failed. Recreating database..."
                )
                if not EncryptionManager.create_new_encrypted_database(db_path):
                    logger.error("Failed to recreate encrypted database")
                    return False
                logger.info("Encrypted database recreated successfully")

        # Verify connection
        if not verify_db_connection():
            logger.error("Engine connection test failed before create_all")
            return False

        # Drop all tables first if resetting
        if reset:
            logger.info("Dropping all tables for reset...")
            Base.metadata.drop_all(bind=engine)
            logger.info("Tables dropped successfully")

        # Create tables
        logger.info("Creating tables via SQLAlchemy...")
        Base.metadata.create_all(bind=engine)

        # Verify table creation
        with engine.connect() as conn:
            table_count = conn.execute(
                text("SELECT count(*) FROM sqlite_master WHERE type='table';")
            ).scalar()
            logger.info(f"Database schema initialized with {table_count} tables")

        return True
    except Exception as e:
        logger.error(f"Database schema initialization failed: {str(e)}")
        logger.exception("Database initialization error details:")
        return False


# -----------------------------------------------------------------------------
# Database Utility Functions
# -----------------------------------------------------------------------------


def get_table_info() -> List[Dict[str, Any]]:
    """
    Get detailed information about all tables in the database.

    Returns:
        List of dictionaries with table information
    """
    try:
        from sqlalchemy import inspect

        inspector = inspect(engine)

        result = []
        for table_name in inspector.get_table_names():
            if table_name.startswith("sqlite_"):
                continue

            # Get columns
            columns = []
            for column in inspector.get_columns(table_name):
                columns.append(
                    {
                        "name": column["name"],
                        "type": str(column["type"]),
                        "nullable": column["nullable"],
                        "primary_key": column.get("primary_key", False),
                    }
                )

            # Get indices
            indices = []
            for index in inspector.get_indexes(table_name):
                indices.append(index["name"])

            # Get row count
            with engine.connect() as conn:
                row_count = conn.execute(
                    text(f"SELECT COUNT(*) FROM {table_name}")
                ).scalar()

            result.append(
                {
                    "name": table_name,
                    "columns": columns,
                    "row_count": row_count,
                    "indices": indices,
                }
            )

        return result
    except Exception as e:
        logger.error(f"Error getting table info: {e}")
        return []


def get_db_stats() -> Dict[str, Any]:
    """
    Get database statistics and health metrics.

    Returns:
        Dictionary with database statistics
    """
    stats = {
        "status": "healthy",
        "db_path": db_path,
        "encryption_enabled": use_sqlcipher,
        "tables": [],
        "size_bytes": 0,
        "connection_pool": {},
    }

    try:
        # Get file size
        if os.path.exists(db_path):
            stats["size_bytes"] = os.path.getsize(db_path)
            stats["size_mb"] = stats["size_bytes"] / (1024 * 1024)

        # Get table info
        table_info = get_table_info()
        total_rows = 0

        tables = []
        for table in table_info:
            tables.append(
                {
                    "name": table["name"],
                    "rows": table["row_count"],
                    "column_count": len(table["columns"]),
                    "has_indices": len(table["indices"]) > 0,
                }
            )
            total_rows += table["row_count"]

        stats["tables"] = tables
        stats["total_tables"] = len(tables)
        stats["total_rows"] = total_rows

        # Get connection pool stats from SQLAlchemy
        pool = engine.pool
        stats["connection_pool"] = {
            "pool_size": getattr(pool, "size", None),
            "checkedin": getattr(pool, "checkedin", None),
            "checkedout": getattr(pool, "checkedout", None),
            "overflow": getattr(pool, "overflow", None),
        }

        return stats
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return {"status": "error", "error": str(e)}


def vacuum_db() -> bool:
    """
    Vacuum the database to optimize storage and performance.

    Returns:
        True if successful, False otherwise
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("VACUUM"))
            logger.info("Database vacuumed successfully")
        return True
    except Exception as e:
        logger.error(f"Error vacuuming database: {e}")
        return False


def analyze_db() -> bool:
    """
    Run ANALYZE on the database to update statistics used by the query planner.

    Returns:
        True if successful, False otherwise
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("ANALYZE"))
            logger.info("Database analyzed successfully")
        return True
    except Exception as e:
        logger.error(f"Error analyzing database: {e}")
        return False


def export_schema(output_file: str = None) -> str:
    """
    Export the database schema as SQL.

    Args:
        output_file: Optional path to save the schema to

    Returns:
        Schema SQL or file path where schema was saved
    """
    try:
        from sqlalchemy.schema import CreateTable, CreateIndex

        schema_sql = "-- HideSync Database Schema\n"
        schema_sql += f"-- Generated: {datetime.datetime.now().isoformat()}\n\n"

        schema_sql += "-- Tables\n"
        for table in Base.metadata.sorted_tables:
            schema_sql += f"{CreateTable(table).compile(dialect=engine.dialect)};\n\n"

        schema_sql += "-- Indices\n"
        inspector = inspect(engine)
        for table in Base.metadata.sorted_tables:
            indices = inspector.get_indexes(table.name)
            for index in indices:
                schema_sql += f"CREATE {'UNIQUE ' if index['unique'] else ''}INDEX {index['name']} ON {table.name} ({', '.join(index['column_names'])});\n\n"

        if output_file:
            with open(output_file, "w") as f:
                f.write(schema_sql)
            logger.info(f"Schema exported to {output_file}")
            return output_file
        else:
            return schema_sql

    except Exception as e:
        logger.error(f"Error exporting schema: {e}")
        return f"Error: {str(e)}"


def backup_db(backup_path: str, vacuum: bool = True) -> bool:
    """
    Create a backup of the database.

    Args:
        backup_path: Path to save the backup
        vacuum: Whether to vacuum the database before backup

    Returns:
        True if backup succeeded, False otherwise
    """
    try:
        # Ensure backup directory exists
        backup_dir = os.path.dirname(os.path.abspath(backup_path))
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        # Dispose of any existing connections
        engine.dispose()

        # Vacuum if requested
        if vacuum:
            if use_sqlcipher:
                conn = EncryptionManager.get_encrypted_connection(db_path)
                cursor = conn.cursor()
                cursor.execute("VACUUM")
                cursor.close()
                conn.close()
            else:
                with sqlite3.connect(db_path) as conn:
                    conn.execute("VACUUM")

        # For SQLCipher, we need to use SQLCipher-aware backup
        if use_sqlcipher:
            # Create source connection
            src_conn = EncryptionManager.get_encrypted_connection(db_path)

            # Create destination connection
            dst_conn = EncryptionManager.get_sqlcipher_module().connect(backup_path)
            dst_cursor = dst_conn.cursor()

            # Configure encryption on destination
            key = EncryptionManager.get_key()
            dst_cursor.execute(f"PRAGMA key = \"x'{key}'\";")
            dst_cursor.execute("PRAGMA cipher_page_size = 4096;")
            dst_cursor.execute("PRAGMA kdf_iter = 256000;")
            dst_cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
            dst_cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")

            # Perform backup
            src_conn.backup(dst_conn)

            # Close connections
            dst_cursor.close()
            dst_conn.close()
            src_conn.close()
        else:
            # For standard SQLite, use simpler backup
            import shutil

            shutil.copy2(db_path, backup_path)

        logger.info(f"Database backed up to {backup_path}")
        return True
    except Exception as e:
        logger.error(f"Error backing up database: {e}")
        return False


# -----------------------------------------------------------------------------
# Encryption Status
# -----------------------------------------------------------------------------


def get_encryption_status() -> dict:
    """
    Get current encryption status information.

    Returns:
        Dictionary with encryption status details
    """
    key_loaded = EncryptionManager.get_key() is not None
    return {
        "encryption_enabled_setting": settings.USE_SQLCIPHER,
        "sqlcipher_available": EncryptionManager.is_sqlcipher_available(),
        "encryption_active": use_sqlcipher and key_loaded,
        "database_path": db_path,
        "uses_sqlalchemy_dialect": True,
        "has_encryption_key_loaded": key_loaded,
    }


# -----------------------------------------------------------------------------
# Database Migrations Support
# -----------------------------------------------------------------------------


class Migration:
    """Base class for database migrations."""

    def __init__(self, version, description):
        self.version = version
        self.description = description

    def up(self, session):
        """
        Apply the migration.

        Args:
            session: Database session

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("Migration.up must be implemented")

    def down(self, session):
        """
        Revert the migration.

        Args:
            session: Database session

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("Migration.down must be implemented")


def _create_migrations_table():
    """Create the migrations tracking table if it doesn't exist."""
    with engine.connect() as conn:
        conn.execute(
            text(
                """
        CREATE TABLE IF NOT EXISTS migrations (
            id INTEGER PRIMARY KEY,
            version TEXT NOT NULL,
            description TEXT,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
            )
        )
        conn.commit()


def get_applied_migrations() -> List[str]:
    """
    Get list of already applied migrations.

    Returns:
        List of applied migration versions
    """
    _create_migrations_table()

    with engine.connect() as conn:
        result = conn.execute(text("SELECT version FROM migrations ORDER BY id"))
        return [row[0] for row in result]


def record_migration(version, description):
    """
    Record that a migration has been applied.

    Args:
        version: Migration version
        description: Migration description
    """
    with engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO migrations (version, description) VALUES (:version, :description)"
            ),
            {"version": version, "description": description},
        )
        conn.commit()


def remove_migration(version):
    """
    Remove a migration from the applied list.

    Args:
        version: Migration version to remove
    """
    with engine.connect() as conn:
        conn.execute(
            text("DELETE FROM migrations WHERE version = :version"),
            {"version": version},
        )
        conn.commit()


def apply_migrations(migrations: List[Migration], target_version: str = None) -> bool:
    """
    Apply database migrations.

    Args:
        migrations: List of Migration objects to apply
        target_version: Optional specific version to migrate to

    Returns:
        True if migrations were successful, False otherwise
    """
    logger.info(f"Applying migrations (target: {target_version or 'latest'})")

    try:
        # Ensure migrations table exists
        _create_migrations_table()

        # Get already applied migrations
        applied = get_applied_migrations()
        logger.info(f"Found {len(applied)} already applied migrations")

        # Sort migrations by version
        migrations.sort(key=lambda m: m.version)

        # Filter to only the migrations we need to apply
        to_apply = [m for m in migrations if m.version not in applied]

        # If target_version specified, only go up to that version
        if target_version:
            to_apply = [m for m in to_apply if m.version <= target_version]

        if not to_apply:
            logger.info("No migrations to apply")
            return True

        logger.info(f"About to apply {len(to_apply)} migrations")

        # Apply each migration
        db = SessionLocal()
        try:
            for migration in to_apply:
                logger.info(
                    f"Applying migration {migration.version}: {migration.description}"
                )
                migration.up(db)
                record_migration(migration.version, migration.description)
                logger.info(f"Successfully applied migration {migration.version}")

            db.commit()
            logger.info("All migrations applied successfully")
            return True

        except Exception as e:
            db.rollback()
            logger.error(f"Migration failed: {e}")
            return False
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error during migration process: {e}")
        return False


def revert_migrations(migrations: List[Migration], target_version: str = None) -> bool:
    """
    Revert database migrations.

    Args:
        migrations: List of Migration objects
        target_version: Version to revert to (defaults to reverting all)

    Returns:
        True if reverting was successful, False otherwise
    """
    logger.info(f"Reverting migrations to target: {target_version or 'initial state'}")

    try:
        # Ensure migrations table exists
        _create_migrations_table()

        # Get already applied migrations
        applied = get_applied_migrations()

        if not applied:
            logger.info("No migrations to revert")
            return True

        # Sort migrations by version in reverse (to revert newest first)
        migrations.sort(key=lambda m: m.version, reverse=True)

        # Filter to only the migrations we need to revert
        to_revert = [m for m in migrations if m.version in applied]

        # If target_version specified, only revert migrations newer than target
        if target_version:
            to_revert = [m for m in to_revert if m.version > target_version]

        if not to_revert:
            logger.info("No migrations to revert")
            return True

        logger.info(f"About to revert {len(to_revert)} migrations")

        # Revert each migration
        db = SessionLocal()
        try:
            for migration in to_revert:
                logger.info(
                    f"Reverting migration {migration.version}: {migration.description}"
                )
                migration.down(db)
                remove_migration(migration.version)
                logger.info(f"Successfully reverted migration {migration.version}")

            db.commit()
            logger.info("All migrations reverted successfully")
            return True

        except Exception as e:
            db.rollback()
            logger.error(f"Migration revert failed: {e}")
            return False
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error during migration revert process: {e}")
        return False


def get_db_health():
    """
    Comprehensive database health check with memory analysis.
    """
    try:
        import psutil
        import gc

        health = {
            "status": "healthy",
            "memory": {},
            "connections": {},
            "query_stats": {},
            "recommendations": [],
        }

        # Memory analysis
        try:
            process = psutil.Process()
            memory_info = process.memory_info()

            health["memory"] = {
                "rss_mb": memory_info.rss / (1024 * 1024),
                "vms_mb": memory_info.vms / (1024 * 1024),
                "percent": process.memory_percent(),
                "gc_counts": gc.get_count(),
            }

            # Add recommendations based on memory usage
            if health["memory"]["rss_mb"] > 1000:
                health["recommendations"].append(
                    "High memory usage detected - consider reducing query batch sizes"
                )
        except Exception as e:
            health["memory"]["error"] = str(e)

        # Connection analysis
        pool = engine.pool
        health["connections"] = {
            "pool_size": pool.size(),
            "checkedin": pool.checkedin(),
            "checkedout": pool.checkedout(),
            "overflow": pool.overflow(),
        }

        # Add connection-related recommendations
        if health["connections"]["checkedout"] > pool.size() * 0.8:
            health["recommendations"].append(
                "Connection pool nearly full - check for leaks"
            )

        # Add overall status
        if (
            health["memory"].get("rss_mb", 0) > 1500
            or len(health["recommendations"]) > 2
        ):
            health["status"] = "warning"

        return health
    except ImportError:
        # If psutil not available
        return {
            "status": "limited",
            "note": "psutil not available for memory analysis",
            "connections": {
                "pool_size": (
                    engine.pool.size() if hasattr(engine.pool, "size") else "unknown"
                ),
                "overflow": (
                    engine.pool.overflow()
                    if hasattr(engine.pool, "overflow")
                    else "unknown"
                ),
            },
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
