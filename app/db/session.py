#!/usr/bin/env python
"""
Database session and connection management with SQLCipher encryption support.
Using direct SQLCipher connection for initial database creation and setup.
"""

import os
import logging
from typing import Generator, Any, Optional, Union
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from sqlalchemy.engine import Engine
import sqlite3
import sqlalchemy

from app.core.key_manager import KeyManager
from app.core.exceptions import SecurityException
from app.core.config import settings
from app.db.models.base import Base

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Encryption Configuration
# -----------------------------------------------------------------------------

class EncryptionManager:
    """Manages database encryption configuration and key handling."""
    _encryption_key: Optional[str] = None
    _sqlcipher_available: bool = False
    _sqlcipher_module = None

    @classmethod
    def initialize(cls) -> None:
        cls._load_encryption_key()
        cls._check_sqlcipher_availability()

    @classmethod
    def get_encrypted_connection(cls, db_path):
        """
        Creates and returns a SQLAlchemy Engine connection with SQLCipher parameters.
        This ensures the connection can access the encrypted database.

        Args:
            db_path: Path to the SQLCipher database

        Returns:
            A SQLAlchemy connection with SQLCipher parameters configured
        """
        import sqlalchemy
        from sqlalchemy import create_engine, event

        # Create a raw SQLite engine without SQLAlchemy's connection pooling
        engine = create_engine(f"sqlite:///{db_path}",
                               connect_args={"check_same_thread": False})

        # Key for pragmas
        encryption_key = cls.get_key()  # <-- Changed from get_database_key() to get_key()
        if not encryption_key:
            raise ValueError("Failed to retrieve database encryption key")

        # Set up event listener to configure SQLCipher parameters on connection
        @event.listens_for(engine, "connect")
        def configure_connection(dbapi_connection, connection_record):
            # Apply SQLCipher pragmas
            dbapi_connection.execute(f"PRAGMA key='{encryption_key}'")
            # Other common SQLCipher pragmas
            dbapi_connection.execute("PRAGMA cipher_compatibility = 3")
            dbapi_connection.execute("PRAGMA kdf_iter = 64000")
            dbapi_connection.execute("PRAGMA cipher_page_size = 4096")
            # Verify the key works by reading something
            result = dbapi_connection.execute("SELECT count(*) FROM sqlite_master")
            # If we get here, the key worked

        # Return a connection
        return engine.connect()

    @classmethod
    def _load_encryption_key(cls) -> None:
        try:
            cls._encryption_key = KeyManager.get_database_encryption_key()
            if cls._encryption_key:
                logger.debug("Encryption key loaded successfully via KeyManager.")
            elif settings.USE_SQLCIPHER:
                logger.error("KeyManager returned no key, but SQLCipher is enabled.")
                raise RuntimeError("Mandatory encryption key failed to load.")
            else:
                logger.info("No encryption key loaded (SQLCipher disabled).")
        except SecurityException as e:
            logger.error(f"Failed to load encryption key via KeyManager: {e}")
            if settings.USE_SQLCIPHER:
                raise RuntimeError(f"Mandatory encryption key failed to load: {e}") from e
            else:
                logger.warning("KeyManager failed, but SQLCipher is disabled. Proceeding without encryption.")
                cls._encryption_key = None
        except Exception as e:
            logger.exception(f"Unexpected error during encryption key loading: {e}")
            if settings.USE_SQLCIPHER:
                raise RuntimeError(f"Mandatory encryption key failed to load: {e}") from e
            else:
                logger.warning("Key loading failed, but SQLCipher is disabled. Proceeding without encryption.")
                cls._encryption_key = None

    @classmethod
    def _check_sqlcipher_availability(cls) -> None:
        if settings.USE_SQLCIPHER:
            try:
                import pysqlcipher3.dbapi2 as sqlcipher
                import sqlcipher3
                cls._sqlcipher_available = True
                cls._sqlcipher_module = sqlcipher
                logger.info("SQLCipher libraries detected and will be used for database encryption")
            except ImportError:
                cls._sqlcipher_available = False
                cls._sqlcipher_module = None
                logger.error("SQLCipher requested (USE_SQLCIPHER=true) but libraries (pysqlcipher3) not found.")
                raise ImportError("pysqlcipher3 library not found, but USE_SQLCIPHER is true.")
        else:
            cls._sqlcipher_available = False
            cls._sqlcipher_module = None
            logger.info("SQLCipher encryption disabled in settings (USE_SQLCIPHER=false)")

    @classmethod
    def get_key(cls) -> Optional[str]:
        return cls._encryption_key

    @classmethod
    def is_sqlcipher_available(cls) -> bool:
        return cls._sqlcipher_available

    @classmethod
    def get_sqlcipher_module(cls):
        return cls._sqlcipher_module

    @classmethod
    def format_key_for_pragma(cls) -> str:
        key = cls.get_key()
        if not key:
            raise ValueError("No encryption key available for PRAGMA formatting.")
        # Simplified formatting logic slightly
        if all(c in "0123456789ABCDEFabcdef" for c in key) and len(key) == 64:
            # Format raw hex as "x'key'"
            return f"\"x'{key}'\""
        elif key.startswith("x'") and key.endswith("'"):
            # Already formatted like x'...', ensure outer quotes for PRAGMA
            return f"\"{key}\""
        else:
            # Assume passphrase, wrap in single quotes
            return f"'{key}'"

    # --- Radically Simplified create_new_encrypted_database ---
    @classmethod
    def create_new_encrypted_database(cls, path: str) -> bool:
        if not cls.is_sqlcipher_available():
            logger.error("Cannot create: SQLCipher not available")
            return False
        if not cls.get_key():
            logger.error("Cannot create: Encryption key not loaded.")
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

            key_pragma_value = cls.format_key_for_pragma()
            key_pragma = f"PRAGMA key = {key_pragma_value};"
            logger.debug(f"Executing PRAGMA for new DB: {key_pragma}")
            cursor.execute(key_pragma)

            cursor.execute("PRAGMA cipher_page_size = 4096;")
            cursor.execute("PRAGMA kdf_iter = 256000;")
            cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
            cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
            cursor.execute("PRAGMA foreign_keys = ON;")
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
                    # Ensure resources are closed before delete attempt
                    if cursor:
                        try:
                            cursor.close()
                        except Exception:
                            pass  # Ignore errors closing cursor during error handling
                    if conn:
                        try:
                            conn.close()
                        except Exception:
                            pass  # Ignore errors closing connection during error handling
                    conn = None  # Prevent finally block from trying again
                    logger.debug(f"Attempting to remove potentially corrupted DB file: {path}")
                    os.remove(path)
                except Exception as remove_e:
                    logger.error(f"Failed to remove DB file during cleanup: {remove_e}")
            return False  # Return False indicating creation failure
        finally:
            # Final cleanup of resources
            if cursor:
                try:
                    cursor.close()
                except Exception as final_cursor_e:
                    logger.error(f"Error closing cursor in finally: {final_cursor_e}")
            if conn:
                try:
                    conn.close()
                except Exception as final_conn_e:
                    logger.error(f"Error closing connection in finally: {final_conn_e}")

    # --- Added a create_tables_direct method to use for encrypted databases ---
    @classmethod
    def create_tables_direct(cls, path: str, metadata) -> bool:
        """
        Create database tables directly using SQLCipher, bypassing SQLAlchemy's create_all.
        This ensures encrypted databases are created properly.
        """
        if not cls.is_sqlcipher_available():
            logger.error("Cannot create tables directly: SQLCipher not available")
            return False
        if not cls.get_key():
            logger.error("Cannot create tables directly: Encryption key not loaded.")
            return False

        # Generate table schemas from SQLAlchemy metadata
        from sqlalchemy.schema import CreateTable

        create_statements = []
        for table in metadata.sorted_tables:
            create_statements.append(str(CreateTable(table).compile(dialect=sqlalchemy.dialects.sqlite.dialect())))

        conn = None
        cursor = None
        try:
            sqlcipher = cls.get_sqlcipher_module()
            conn = sqlcipher.connect(path)
            cursor = conn.cursor()

            # Configure encryption
            key_pragma_value = cls.format_key_for_pragma()
            key_pragma = f"PRAGMA key = {key_pragma_value};"
            logger.debug(f"Executing PRAGMA for table creation: {key_pragma}")
            cursor.execute(key_pragma)
            cursor.execute("PRAGMA cipher_page_size = 4096;")
            cursor.execute("PRAGMA kdf_iter = 256000;")
            cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
            cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
            cursor.execute("PRAGMA foreign_keys = ON;")

            # Execute each CREATE TABLE statement
            for statement in create_statements:
                logger.debug(f"Executing: {statement[:60]}...")  # Log just the beginning
                cursor.execute(statement)

            conn.commit()

            # Verify table creation
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            table_names = [t[0] for t in tables]
            logger.info(f"Created {len(table_names)} tables directly with SQLCipher")
            logger.debug(
                f"Tables created: {', '.join(table_names[:5])}..." if len(table_names) > 5 else ', '.join(table_names))

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

    # --- Radically Simplified test_encrypted_database ---
    @classmethod
    def test_encrypted_database(cls, path: str) -> bool:
        if not cls.is_sqlcipher_available() or not os.path.exists(path):
            return False
        if not cls.get_key():
            logger.warning("Cannot test: Encryption key not loaded.")
            return False

        conn = None
        cursor = None
        try:
            sqlcipher = cls.get_sqlcipher_module()
            conn = sqlcipher.connect(path)
            cursor = conn.cursor()

            key_pragma_value = cls.format_key_for_pragma()
            key_pragma = f"PRAGMA key = {key_pragma_value};"
            logger.debug(f"Executing PRAGMA for testing DB: {key_pragma}")
            cursor.execute(key_pragma)

            cursor.execute("PRAGMA cipher_page_size = 4096;")
            cursor.execute("PRAGMA kdf_iter = 256000;")
            cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
            cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
            cursor.execute("PRAGMA foreign_keys = ON;")
            cursor.execute("SELECT count(*) FROM sqlite_master;")
            result = cursor.fetchone()  # Get result before closing

            if result is None:
                logger.error(f"Test query returned no result for {path}.")
                return False  # Should get at least 0

            logger.info(f"Successfully tested encrypted database at {path} ({result[0]} tables found)")
            return True

        except Exception as e:
            if "file is not a database" in str(e):
                logger.error(f"Failed test: Incorrect key or corrupted file at {path}.")
            else:
                logger.error(f"Failed test at {path}: {e}")
            return False
        finally:
            # Final cleanup of resources
            if cursor:
                try:
                    cursor.close()
                except Exception as final_cursor_e:
                    logger.error(f"Error closing cursor in finally: {final_cursor_e}")
            if conn:
                try:
                    conn.close()
                except Exception as final_conn_e:
                    logger.error(f"Error closing connection in finally: {final_conn_e}")


# Initialize encryption configuration ONCE
EncryptionManager.initialize()

# -----------------------------------------------------------------------------
# Database Engine Configuration (for non-encrypted operations)
# -----------------------------------------------------------------------------

db_uri_base = None
if settings.DATABASE_PATH:
    db_path_abs = os.path.abspath(settings.DATABASE_PATH)
    db_uri_base = f"sqlite:///{db_path_abs}"
    logger.info(f"Using database path for engine: {db_path_abs}")
elif settings.DATABASE_URL:
    db_uri_base = settings.DATABASE_URL
    logger.info(f"Using database URL from settings for engine: {db_uri_base}")

if not db_uri_base:
    raise ValueError("No database URL or path specified in settings")

use_sqlcipher = settings.USE_SQLCIPHER and EncryptionManager.is_sqlcipher_available()

# Only include standard connect_args
engine_connect_args = {}
if db_uri_base.startswith("sqlite"):
    engine_connect_args["check_same_thread"] = False

# Store SQLCipher parameters for later use
sqlcipher_params = {}
if use_sqlcipher:
    logger.info("SQLCipher enabled, parameters will be used for direct operations...")
    encryption_key = EncryptionManager.get_key()
    if not encryption_key:
        raise ValueError("SQLCipher is enabled, but no encryption key is available.")

    # Store these for direct connections
    sqlcipher_params = {
        'key': encryption_key,
        'cipher_page_size': 4096,
        'kdf_iter': 256000,
        'cipher_hmac_algorithm': 'HMAC_SHA512',
        'cipher_kdf_algorithm': 'PBKDF2_HMAC_SHA512',
    }
    logger.info("SQLCipher parameters prepared for direct operations.")
else:
    logger.info("SQLCipher disabled or unavailable. Using standard SQLite operations.")

try:
    logger.info(f"Creating SQLAlchemy engine with URL: {db_uri_base}")
    logger.info(f"Using connect_args: {engine_connect_args}")

    engine = create_engine(
        db_uri_base,
        connect_args=engine_connect_args,  # Only standard connect_args here
        poolclass=NullPool,
        echo=settings.DEBUG,
    )

    # Add an event listener for standard SQLite operations only if not using SQLCipher
    if not use_sqlcipher:
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = None
            try:
                cursor = dbapi_connection.cursor()
                logger.debug("Listener: Applying PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA foreign_keys=ON;")
            except Exception as e:
                logger.error(f"Error setting SQLite PRAGMA: {e}")
            finally:
                if cursor:
                    cursor.close()

    logger.info("SQLAlchemy engine created for non-encrypted operations.")

except Exception as e:
    logger.error(f"Failed to create database engine: {str(e)}")
    raise RuntimeError(f"Database engine creation failed: {str(e)}") from e

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# -----------------------------------------------------------------------------
# Database Interface Functions
# -----------------------------------------------------------------------------

def get_db() -> Generator[Session, None, None]:
    db: Optional[Session] = None
    try:
        db = SessionLocal()
        yield db
    except Exception as e:
        logger.error(f"Error creating database session: {e}")
        raise
    finally:
        if db is not None:
            try:
                db.close()
            except Exception as e:
                logger.error(f"Error closing database session: {e}")


def verify_db_connection() -> bool:
    # For SQLCipher databases, use direct test method
    if use_sqlcipher and settings.DATABASE_PATH:
        return EncryptionManager.test_encrypted_database(os.path.abspath(settings.DATABASE_PATH))

    # For non-encrypted databases, use SQLAlchemy engine
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar_one()
            logger.info("Standard DB verified via SQLAlchemy engine.")
            return True
    except Exception as e:
        logger.error(f"Database connection verification failed: {e}")
        return False


def init_db() -> bool:
    logger.info("Initializing database schema...")
    db_path = os.path.abspath(settings.DATABASE_PATH) if settings.DATABASE_PATH else None

    # Handle SQLCipher encrypted database
    if use_sqlcipher:
        if not db_path:
            logger.error("Cannot init SQLCipher DB: DATABASE_PATH not set.")
            return False

        # Create or reset encrypted database
        if not os.path.exists(db_path):
            logger.info(f"DB file not found. Creating new encrypted database at {db_path}")
            if not EncryptionManager.create_new_encrypted_database(db_path):
                logger.error("Failed to create new DB.")
                return False
            logger.info("New encrypted database created.")
        else:
            logger.info(f"Testing existing encrypted database at {db_path}")
            if not EncryptionManager.test_encrypted_database(db_path):
                logger.error(f"Existing DB test failed. Recreating database...")
                if not EncryptionManager.create_new_encrypted_database(db_path):
                    logger.error("Failed to recreate DB.")
                    return False
                logger.info("Database recreated successfully.")

        # Create tables directly using SQLCipher
        logger.info("Creating database tables directly with SQLCipher...")
        if not EncryptionManager.create_tables_direct(db_path, Base.metadata):
            logger.error("Failed to create tables directly with SQLCipher.")
            return False

        logger.info("Database tables created successfully with SQLCipher")
        return True

    # Handle standard (non-encrypted) database
    else:
        try:
            logger.info("Testing connection via SQLAlchemy engine...")
            if not verify_db_connection():
                logger.error("Engine connection test failed before create_all.")
                return False

            logger.info("Engine connection test successful.")
            logger.info("Creating tables via SQLAlchemy...")
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created successfully")

            with SessionLocal() as session:
                table_count = session.execute(
                    text("SELECT count(*) FROM sqlite_master WHERE type='table';")).scalar_one()
                logger.info(f"Database schema initialized with {table_count} tables.")
            return True
        except Exception as e:
            logger.error(f"Database schema initialization failed: {str(e)}")
            logger.exception("Database initialization error details:")
            return False


def get_encryption_status() -> dict:
    key_loaded = EncryptionManager.get_key() is not None
    db_url_to_log = db_uri_base
    return {
        "encryption_enabled_setting": settings.USE_SQLCIPHER,
        "sqlcipher_available": EncryptionManager.is_sqlcipher_available(),
        "encryption_active": use_sqlcipher and key_loaded,
        "database_path": settings.DATABASE_PATH,
        "database_url_base": db_url_to_log if 'db_url_to_log' in locals() else 'Not Constructed',
        "has_encryption_key_loaded": key_loaded
    }




