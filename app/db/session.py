#!/usr/bin/env python
"""
Database session and connection management with SQLCipher encryption support.
Using direct SQLCipher connection for initial database creation and setup.
"""

#!/usr/bin/env python
"""
Database session and connection management with SQLCipher encryption support.
Using direct SQLCipher connection for initial database creation and setup.
"""

import os
import logging
import threading
import time
import datetime
import json
from typing import (
    Generator, Any, Optional, Union, Dict, List, Callable, Tuple,
    Set, Type, TypeVar, cast, Iterable, Sequence
)
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text, Column, Table, MetaData
from sqlalchemy.orm import sessionmaker, Session, Query
from sqlalchemy.pool import NullPool, Pool
from sqlalchemy.engine import Engine, Connection, ResultProxy
from sqlalchemy.sql import ClauseElement, Select, expression, func
from sqlalchemy.sql.elements import BinaryExpression, UnaryExpression, ColumnElement
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.inspection import inspect
import sqlite3
import sqlalchemy

from app.core.key_manager import KeyManager
from app.core.exceptions import SecurityException
from app.core.config import settings
from app.db.models.base import Base

# Define a generic model type for type hints
ModelT = TypeVar('ModelT', bound=Any)

logger = logging.getLogger(__name__)


def verify_db_connection() -> bool:
    """Verify that we can connect to the database"""
    if use_sqlcipher:
        try:
            logger.info(f"Verifying encrypted database at {db_path}...")
            conn = EncryptionManager.get_encrypted_connection(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM sqlite_master")
            table_count = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            logger.info(f"✅ Encrypted database verified with {table_count} tables.")
            return True
        except Exception as e:
            logger.error(f"❌ Encrypted database verification failed: {e}")
            return False
    else:
        try:
            with engine.connect() as connection:
                result = connection.execute(text("SELECT 1")).scalar_one()
                logger.info("Standard DB verified via SQLAlchemy engine.")
                return True
        except Exception as e:
            logger.error(f"Database connection verification failed: {e}")
            return False

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
        Creates and returns a SQLCipher connection object.
        This ensures the connection can access the encrypted database.
        """
        if not cls.is_sqlcipher_available():
            raise RuntimeError("SQLCipher is not available but an encrypted connection was requested")

        encryption_key = cls.get_key()
        if not encryption_key:
            raise ValueError("Failed to retrieve database encryption key")

        try:
            sqlcipher = cls.get_sqlcipher_module()
            conn = sqlcipher.connect(db_path)

            cursor = conn.cursor()
            # CRITICAL FIX: Use exact format from working diagnostic script
            cursor.execute(f"PRAGMA key = \"x'{encryption_key}'\";")
            cursor.execute("PRAGMA cipher_page_size=4096;")
            cursor.execute("PRAGMA kdf_iter=256000;")
            cursor.execute("PRAGMA cipher_hmac_algorithm=HMAC_SHA512;")
            cursor.execute("PRAGMA cipher_kdf_algorithm=PBKDF2_HMAC_SHA512;")
            cursor.execute("PRAGMA foreign_keys=ON;")

            # Test the connection
            cursor.execute("SELECT 1;")
            cursor.close()

            return conn
        except Exception as e:
            logger.error(f"Failed to create encrypted connection: {e}")
            raise

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
        """
        Format the encryption key for use in PRAGMA statements.
        CRITICAL: This must match the exact format used in diagnostic scripts.
        """
        key = cls.get_key()
        if not key:
            raise ValueError("No encryption key available for PRAGMA formatting.")

        # Use the exact format that works in diagnostic script
        # This is the critical fix - we don't try to be clever about formatting
        return f"\"x'{key}'\""

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

            # Configure encryption using EXACT format from diagnostic script
            key = cls.get_key()
            cursor.execute(f"PRAGMA key = \"x'{key}'\";")
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
# Custom Connection Pool for SQLCipher
# -----------------------------------------------------------------------------

class DirectSQLCipherPool:
    """
    Enhanced production-ready connection pool for SQLCipher connections.
    Features:
    - Connection health checks
    - Automatic reconnection
    - Connection timeouts
    - Connection recycling based on age and usage
    """

    def __init__(self, db_path, pool_size=5, max_overflow=10, timeout=30,
                 recycle_timeout=3600, max_usage=1000):
        self.db_path = db_path
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.timeout = timeout  # Seconds to wait for a connection
        self.recycle_timeout = recycle_timeout  # Max age in seconds before recycling
        self.max_usage = max_usage  # Max uses before recycling

        self.connections = []
        self.in_use = {}  # Maps connection ID to (connection, creation_time, use_count)
        self._conn_lock = threading.RLock()  # Thread safety for pool operations

    def _create_connection(self):
        """Create a new connection with SQLCipher parameters configured"""
        try:
            # Use the exact method that works in diagnostic script
            conn = EncryptionManager.get_encrypted_connection(self.db_path)
            creation_time = time.time()
            return conn, creation_time
        except Exception as e:
            logger.error(f"Failed to create SQLCipher connection: {e}")
            raise

    def connect(self):
        """Get a connection from the pool or create a new one"""
        with self._conn_lock:
            start_time = time.time()

            # First try to get an idle connection
            while self.connections and time.time() - start_time < self.timeout:
                if not self.connections:
                    time.sleep(0.1)  # Short sleep while waiting
                    continue

                conn, creation_time, use_count = self.connections.pop(0)

                # Check if connection needs recycling
                if (time.time() - creation_time > self.recycle_timeout or
                        use_count >= self.max_usage):
                    try:
                        conn.close()
                    except Exception:
                        pass  # Ignore errors when closing old connection
                    continue  # Skip this connection and try next

                # IMPORTANT: Always reconfigure the connection before use
                # This is crucial - SQLCipher connections may lose their configuration
                try:
                    key = EncryptionManager.get_key()
                    cursor = conn.cursor()
                    # Match EXACTLY the diagnostic script format
                    cursor.execute(f"PRAGMA key = \"x'{key}'\";")
                    cursor.execute("PRAGMA cipher_page_size = 4096;")
                    cursor.execute("PRAGMA kdf_iter = 256000;")
                    cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
                    cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
                    cursor.execute("PRAGMA foreign_keys = ON;")

                    # Test connection health
                    cursor.execute("SELECT 1")
                    cursor.close()

                    # Connection is good, increment use count and return it
                    use_count += 1
                    self.in_use[id(conn)] = (conn, creation_time, use_count)
                    return conn
                except Exception as e:
                    # Connection is bad, try to close it and continue
                    logger.error(f"Error reconfiguring connection: {e}")
                    try:
                        conn.close()
                    except Exception:
                        pass
                    continue  # Try next connection

            # No idle connections available, create a new one if under limits
            total_connections = len(self.in_use) + len(self.connections)

            if total_connections < self.pool_size + self.max_overflow:
                # Create new connection
                conn, creation_time = self._create_connection()
                self.in_use[id(conn)] = (conn, creation_time, 1)  # First use
                return conn

            # We've reached max connections, wait for one to be released
            while time.time() - start_time < self.timeout:
                time.sleep(0.1)  # Short sleep while waiting

                # Check if a connection was released while waiting
                if self.connections:
                    return self.connect()  # Recursive call to try again

            # Timeout reached without getting a connection
            raise TimeoutError(f"Timeout waiting for SQLCipher connection after {self.timeout} seconds")

    def release(self, conn):
        """Return a connection to the pool"""
        with self._conn_lock:
            conn_id = id(conn)

            if conn_id in self.in_use:
                _, creation_time, use_count = self.in_use.pop(conn_id)

                # Check if connection should be recycled
                if (time.time() - creation_time > self.recycle_timeout or
                        use_count >= self.max_usage):
                    try:
                        conn.close()
                    except Exception as e:
                        logger.warning(f"Error closing recycled connection: {e}")
                else:
                    # Return to available pool
                    self.connections.append((conn, creation_time, use_count))
            else:
                # Connection not from this pool, close it
                try:
                    conn.close()
                except Exception as e:
                    logger.warning(f"Error closing unknown connection: {e}")

    def dispose(self):
        """Close all connections in the pool"""
        with self._conn_lock:
            # Close all idle connections
            while self.connections:
                conn, _, _ = self.connections.pop()
                try:
                    conn.close()
                except Exception as e:
                    logger.warning(f"Error closing connection during dispose: {e}")

            # Close all in-use connections
            for conn_id, (conn, _, _) in list(self.in_use.items()):
                try:
                    conn.close()
                except Exception as e:
                    logger.warning(f"Error closing in-use connection during dispose: {e}")

            self.in_use.clear()

    def status(self):
        """Return pool status information"""
        with self._conn_lock:
            return {
                'idle_connections': len(self.connections),
                'in_use_connections': len(self.in_use),
                'total_connections': len(self.connections) + len(self.in_use),
                'max_pool_size': self.pool_size,
                'max_overflow': self.max_overflow
            }


# -----------------------------------------------------------------------------
# Database Connection Setup
# -----------------------------------------------------------------------------

db_path = None
if settings.DATABASE_PATH:
    db_path = os.path.abspath(settings.DATABASE_PATH)
    logger.info(f"Using database path: {db_path}")
elif settings.DATABASE_URL:
    if settings.DATABASE_URL.startswith("sqlite"):
        # Extract path from sqlite URL
        db_path = settings.DATABASE_URL.replace("sqlite:///", "")
        db_path = os.path.abspath(db_path)
        logger.info(f"Extracted database path from URL: {db_path}")
    else:
        logger.error(f"Non-SQLite URL not supported with SQLCipher: {settings.DATABASE_URL}")
        raise ValueError("Only SQLite URLs are supported with SQLCipher")

if not db_path:
    raise ValueError("No database path specified in settings")

use_sqlcipher = settings.USE_SQLCIPHER and EncryptionManager.is_sqlcipher_available()

# Create the proper engine based on encryption settings
# When using SQLCipher mode, initialize the enhanced session factory
if use_sqlcipher:
    # Create an enhanced connection pool
    connection_pool = DirectSQLCipherPool(
        db_path,
        pool_size=settings.DB_POOL_SIZE if hasattr(settings, 'DB_POOL_SIZE') else 5,
        max_overflow=settings.DB_MAX_OVERFLOW if hasattr(settings, 'DB_MAX_OVERFLOW') else 10,
        timeout=settings.DB_POOL_TIMEOUT if hasattr(settings, 'DB_POOL_TIMEOUT') else 30,
        recycle_timeout=settings.DB_RECYCLE_TIMEOUT if hasattr(settings, 'DB_RECYCLE_TIMEOUT') else 3600
    )

    # Create SQLAlchemy engine for metadata operations only
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False}
    )

    # Flag for direct SQLCipher mode
    direct_sqlcipher_mode = True

    def SessionLocal():
        """Factory function to create a new SQLCipherSession"""
        return SQLCipherSession(connection_pool)


else:
    logger.info(f"Creating standard SQLAlchemy engine for {db_path}")
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=settings.DEBUG
    )


    # Add event listener for standard SQLite operations
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


    # Flag to indicate we're using standard SQLAlchemy session
    direct_sqlcipher_mode = False

    # Use standard SQLAlchemy session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# -----------------------------------------------------------------------------
# Custom Session with SQLCipher Support
# -----------------------------------------------------------------------------

class SQLCipherSession:
    """
    A production-ready session implementation that works with direct SQLCipher connections
    while providing compatibility with SQLAlchemy's Session API.
    """

    def __init__(self, connection_pool):
        self.connection_pool = connection_pool
        self._connection = None
        self.closed = False
        self.bind = None  # Normally an Engine
        self.autocommit = False
        self.autoflush = False
        self.info = {}
        self._pending_objects = set()  # Track objects pending commit
        self._deleted_objects = set()  # Track objects pending deletion
        self._transaction_depth = 0  # For nested transaction support
        self._modified_attrs = {}  # Track modified attributes for efficient updates

    def __enter__(self):
        self._transaction_depth += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._transaction_depth -= 1
        if exc_type is not None:
            # Exception occurred, rollback
            self.rollback()
        elif self._transaction_depth == 0:
            # Outermost transaction is ending, commit
            self.commit()
            self.close()

    @property
    def connection(self):
        """Get the SQLCipher database connection from the pool"""
        if self.closed:
            raise RuntimeError("Session is closed")
        if not self._connection:
            self._connection = self.connection_pool.connect()

        # Always validate the connection before returning it
        try:
            cursor = self._connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
        except Exception as e:
            logger.error(f"Connection validation failed: {e}")
            # Close the bad connection
            try:
                self._connection.close()
            except:
                pass

            # Get a new connection
            self._connection = self.connection_pool.connect()

        return self._connection

    def _get_model_metadata(self, model):
        """Extract metadata from a model class or instance"""
        if not hasattr(model, '__tablename__'):
            raise ValueError(f"Model {model} must have __tablename__ attribute")

        result = {
            'tablename': model.__tablename__,
            'columns': [],
            'pk_column': 'id'  # Default, can be overridden
        }

        # Check for primary key column (SQLAlchemy models)
        if hasattr(model, '__mapper__') and hasattr(model.__mapper__, 'primary_key'):
            for pk in model.__mapper__.primary_key:
                result['pk_column'] = pk.name
                break

        # Get column info - use SQLAlchemy __table__ if available
        if hasattr(model, '__table__'):
            for column in model.__table__.columns:
                result['columns'].append({
                    'name': column.name,
                    'type': column.type,
                    'nullable': column.nullable,
                    'primary_key': column.primary_key,
                    'default': column.default,
                })
        else:
            # Fallback to examining the instance attributes
            # Exclude SQLAlchemy internal attributes and methods
            attrs = [attr for attr in dir(model)
                     if not attr.startswith('_') and
                     not callable(getattr(model, attr)) and
                     attr not in ('metadata', 'registry')]
            for attr in attrs:
                result['columns'].append({
                    'name': attr,
                    'type': None,  # Type info not available
                    'nullable': True,
                    'primary_key': (attr == result['pk_column']),
                    'default': None,
                })

        return result

    def _extract_instance_values(self, instance, include_none=False):
        """Extract values from model instance for database operations"""
        # Skip SQLAlchemy internal attributes
        skip_attrs = {'_sa_class_manager', '_sa_instance_state', 'metadata', 'registry'}

        values = {}
        for key, value in instance.__dict__.items():
            # Skip SQLAlchemy internal attributes and methods
            if key.startswith('_sa_') or key in skip_attrs or callable(value):
                continue

            # Include None values only if explicitly requested
            if value is None and not include_none:
                continue

            # Convert values to appropriate SQLite format
            values[key] = self._convert_value_for_sqlite(value)

        return values

    def _convert_value_for_sqlite(self, value):
        """Convert Python values to SQLite-compatible formats"""
        if value is None:
            return None
        elif isinstance(value, bool):
            return 1 if value else 0
        elif isinstance(value, (int, float, str)):
            return value
        elif isinstance(value, bytes):
            return value
        elif isinstance(value, datetime.datetime):
            # Store as ISO format string
            return value.isoformat()
        elif isinstance(value, datetime.date):
            return value.isoformat()
        elif isinstance(value, list) or isinstance(value, dict):
            # Store complex objects as JSON
            return json.dumps(value)
        elif hasattr(value, '__tablename__'):
            # For related objects, store the primary key
            if hasattr(value, 'id'):
                return value.id
            return None
        else:
            # For unknown types, convert to string
            logger.warning(f"Converting unknown type {type(value)} to string: {value}")
            return str(value)

    def _convert_from_sqlite(self, value, target_type=None):
        """Convert SQLite values to appropriate Python types"""
        if value is None:
            return None

        if target_type is not None:
            # If we have type information from SQLAlchemy, use it
            type_name = target_type.__class__.__name__.lower()

            if 'boolean' in type_name:
                return bool(value)
            elif 'integer' in type_name:
                return int(value)
            elif 'float' in type_name or 'numeric' in type_name:
                return float(value)
            elif 'datetime' in type_name:
                if isinstance(value, str):
                    return datetime.datetime.fromisoformat(value)
                return value
            elif 'date' in type_name:
                if isinstance(value, str):
                    return datetime.date.fromisoformat(value)
                return value
            elif 'json' in type_name:
                if isinstance(value, str):
                    return json.loads(value)
                return value
            else:
                # For string types and others, just return the value
                return value
        else:
            # Without type information, make best guess
            if isinstance(value, (int, float, str, bytes)):
                return value
            elif isinstance(value, str):
                # Try to detect JSON
                if (value.startswith('{') and value.endswith('}')) or \
                        (value.startswith('[') and value.endswith(']')):
                    try:
                        return json.loads(value)
                    except:
                        return value

                # Try to detect ISO datetime format
                try:
                    return datetime.datetime.fromisoformat(value)
                except:
                    return value
            else:
                return value

    def close(self):
        """Close the session and release database connection to the pool"""
        if not self.closed and self._connection:
            self.connection_pool.release(self._connection)
            self._connection = None
            self.closed = True
            self._pending_objects.clear()
            self._deleted_objects.clear()
            self._transaction_depth = 0
            self._modified_attrs.clear()

    def execute(self, statement, params=None):
        """Execute a SQL statement directly with parameters"""
        cursor = None
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(statement, params)
            else:
                cursor.execute(statement)

            if statement.upper().startswith(("SELECT", "PRAGMA")):
                result = cursor.fetchall()
                column_names = [desc[0] for desc in cursor.description] if cursor.description else []
                return SQLCipherResultProxy(result, column_names)
            else:
                self.connection.commit()
                return SQLCipherResultProxy(rowcount=cursor.rowcount, lastrowid=cursor.lastrowid)
        except Exception as e:
            logger.error(f"Error executing SQL: {e}\nStatement: {statement}\nParams: {params}")
            raise
        finally:
            if cursor:
                cursor.close()

    def query(self, *entities):
        """Create a query object for the given model/entity classes"""
        if not entities:
            raise ValueError("No entities specified for query")

        # Support multiple entities for joins
        return SQLCipherQuery(self, entities)

    def add(self, instance):
        """Add a new instance to the session for later insertion"""
        if instance in self._deleted_objects:
            self._deleted_objects.remove(instance)

        self._pending_objects.add(instance)

        # If autoflush is enabled, flush immediately
        if self.autoflush:
            self.flush()

        logger.debug(f"Instance of {instance.__class__.__name__} added to session")

    def add_all(self, instances):
        """Add multiple instances to the session"""
        for instance in instances:
            self.add(instance)

    def delete(self, instance):
        """Mark an instance for deletion"""
        if instance in self._pending_objects:
            self._pending_objects.remove(instance)

        self._deleted_objects.add(instance)

        # If autoflush is enabled, flush immediately
        if self.autoflush:
            self.flush()

        logger.debug(f"Instance of {instance.__class__.__name__} marked for deletion")

    def flush(self, objects=None):
        """Flush pending changes to the database"""
        # Process any pending objects first
        objects_to_process = objects or self._pending_objects
        for instance in objects_to_process:
            self._insert_or_update_instance(instance)

        # Process any pending deletions
        for instance in self._deleted_objects:
            self._delete_instance(instance)

        # Clear tracking sets
        if objects is None:  # Only clear all if not a targeted flush
            self._pending_objects.clear()
            self._deleted_objects.clear()

        logger.debug("Session flushed")

    def _insert_or_update_instance(self, instance):
        """Insert a new record or update an existing one"""
        metadata = self._get_model_metadata(instance.__class__)
        values = self._extract_instance_values(instance)

        # Skip if no values to insert/update
        if not values:
            return

        pk_column = metadata['pk_column']
        pk_value = getattr(instance, pk_column, None)

        cursor = None
        try:
            cursor = self.connection.cursor()

            if pk_value is not None:
                # Check if record exists
                check_sql = f"SELECT 1 FROM {metadata['tablename']} WHERE {pk_column} = ? LIMIT 1"
                cursor.execute(check_sql, (pk_value,))
                exists = cursor.fetchone() is not None

                if exists:
                    # Update existing record
                    set_clause = ', '.join([f"{col} = ?" for col in values.keys()])
                    update_values = list(values.values())
                    update_values.append(pk_value)

                    update_sql = f"UPDATE {metadata['tablename']} SET {set_clause} WHERE {pk_column} = ?"
                    cursor.execute(update_sql, update_values)

                    logger.debug(f"Updated {metadata['tablename']} record with {pk_column}={pk_value}")
                else:
                    # Insert with specific primary key
                    columns = list(values.keys())
                    if pk_column not in columns:
                        columns.append(pk_column)
                        values[pk_column] = pk_value

                    placeholders = ', '.join(['?'] * len(columns))
                    insert_sql = f"INSERT INTO {metadata['tablename']} ({', '.join(columns)}) VALUES ({placeholders})"
                    cursor.execute(insert_sql, [values[col] for col in columns])

                    logger.debug(f"Inserted {metadata['tablename']} record with specified {pk_column}={pk_value}")
            else:
                # Insert new record, let SQLite assign primary key
                columns = list(values.keys())
                placeholders = ', '.join(['?'] * len(columns))

                insert_sql = f"INSERT INTO {metadata['tablename']} ({', '.join(columns)}) VALUES ({placeholders})"
                cursor.execute(insert_sql, list(values.values()))

                # Get the new ID and update the instance
                new_id = cursor.lastrowid
                setattr(instance, pk_column, new_id)

                logger.debug(f"Inserted new {metadata['tablename']} record, {pk_column}={new_id}")
        except Exception as e:
            logger.error(f"Error in _insert_or_update_instance: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def _delete_instance(self, instance):
        """Delete an instance from the database"""
        if not hasattr(instance, '__tablename__'):
            raise ValueError("Instance must have __tablename__ attribute")

        metadata = self._get_model_metadata(instance.__class__)
        pk_column = metadata['pk_column']
        pk_value = getattr(instance, pk_column, None)

        if pk_value is None:
            # Nothing to delete if no primary key
            return

        cursor = None
        try:
            cursor = self.connection.cursor()
            delete_sql = f"DELETE FROM {metadata['tablename']} WHERE {pk_column} = ?"
            cursor.execute(delete_sql, (pk_value,))

            if cursor.rowcount > 0:
                logger.debug(f"Deleted {metadata['tablename']} record with {pk_column}={pk_value}")
            else:
                logger.debug(f"No {metadata['tablename']} record found with {pk_column}={pk_value} for deletion")
        except Exception as e:
            logger.error(f"Error in _delete_instance: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def commit(self):
        """Commit the current transaction"""
        # Flush any pending changes
        self.flush()

        if not self.closed and self._connection:
            self._connection.commit()
            logger.debug("Session committed")

    def rollback(self):
        """Rollback the current transaction"""
        if not self.closed and self._connection:
            self._connection.rollback()

        # Clear pending changes
        self._pending_objects.clear()
        self._deleted_objects.clear()

        logger.debug("Session rolled back")

    def refresh(self, instance, attribute_names=None):
        """Refresh instance from the database"""
        if not hasattr(instance, '__tablename__'):
            raise ValueError("Instance must have __tablename__ attribute")

        metadata = self._get_model_metadata(instance.__class__)
        pk_column = metadata['pk_column']
        pk_value = getattr(instance, pk_column, None)

        if pk_value is None:
            raise ValueError(f"Cannot refresh instance without {pk_column} value")

        # Determine which columns to fetch
        if attribute_names:
            columns = ', '.join([pk_column] + [name for name in attribute_names if name != pk_column])
        else:
            columns = '*'

        cursor = None
        try:
            cursor = self.connection.cursor()
            select_sql = f"SELECT {columns} FROM {metadata['tablename']} WHERE {pk_column} = ?"
            cursor.execute(select_sql, (pk_value,))

            row = cursor.fetchone()
            if not row:
                raise ValueError(f"No {metadata['tablename']} record found with {pk_column}={pk_value}")

            # Update instance with fresh data
            column_names = [desc[0] for desc in cursor.description]
            for i, name in enumerate(column_names):
                if hasattr(instance, name) and (attribute_names is None or name in attribute_names):
                    # Get column type info if available
                    col_type = next((col['type'] for col in metadata['columns']
                                     if col['name'] == name), None)
                    # Convert the value to the appropriate Python type
                    value = self._convert_from_sqlite(row[i], col_type)
                    setattr(instance, name, value)

            logger.debug(f"Refreshed {metadata['tablename']} instance with {pk_column}={pk_value}")
        except Exception as e:
            logger.error(f"Error in refresh: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def expunge(self, instance):
        """Remove instance from session without affecting the database"""
        if instance in self._pending_objects:
            self._pending_objects.remove(instance)

        if instance in self._deleted_objects:
            self._deleted_objects.remove(instance)

        if id(instance) in self._modified_attrs:
            del self._modified_attrs[id(instance)]

        logger.debug(f"Expunged {instance.__class__.__name__} instance from session")

    def expunge_all(self):
        """Remove all instances from session without affecting the database"""
        self._pending_objects.clear()
        self._deleted_objects.clear()
        self._modified_attrs.clear()
        logger.debug("Expunged all instances from session")

    def merge(self, instance, load=True):
        """Merge the instance state with a persistent instance from database or create new"""
        if not hasattr(instance, '__tablename__'):
            raise ValueError(f"Instance {instance} must have __tablename__ attribute")

        metadata = self._get_model_metadata(instance.__class__)
        pk_column = metadata['pk_column']
        pk_value = getattr(instance, pk_column, None)

        # If no primary key, treat as a new instance
        if pk_value is None:
            # Add to pending objects and return the instance
            self.add(instance)
            return instance

        # Check if instance exists in database
        cursor = None
        try:
            cursor = self.connection.cursor()
            select_sql = f"SELECT * FROM {metadata['tablename']} WHERE {pk_column} = ?"
            cursor.execute(select_sql, (pk_value,))

            row = cursor.fetchone()
            if not row and not load:
                # Instance doesn't exist and load=False, just return
                self.add(instance)
                return instance

            if not row and load:
                # Instance doesn't exist but we want to create it
                self.add(instance)
                self.flush([instance])  # Insert immediately
                return instance

            # Instance exists, create a new instance with database values
            merged = instance.__class__()

            # First populate with database values
            column_names = [desc[0] for desc in cursor.description]
            for i, name in enumerate(column_names):
                if hasattr(merged, name):
                    # Get column type if available
                    col_type = next((col['type'] for col in metadata['columns']
                                     if col['name'] == name), None)
                    # Convert to appropriate Python type
                    value = self._convert_from_sqlite(row[i], col_type)
                    setattr(merged, name, value)

            # Then override with non-None values from the input instance
            for name, value in self._extract_instance_values(instance, include_none=False).items():
                if hasattr(merged, name):
                    setattr(merged, name, value)

            # Add to session and return the merged instance
            self.add(merged)

            logger.debug(f"Merged {metadata['tablename']} instance with {pk_column}={pk_value}")
            return merged

        except Exception as e:
            logger.error(f"Error in merge: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def get(self, entity, ident, options=None):
        """Get entity by primary key"""
        if not hasattr(entity, '__tablename__'):
            raise ValueError(f"Entity {entity} must have __tablename__ attribute")

        metadata = self._get_model_metadata(entity)
        pk_column = metadata['pk_column']

        cursor = None
        try:
            cursor = self.connection.cursor()
            select_sql = f"SELECT * FROM {metadata['tablename']} WHERE {pk_column} = ?"
            cursor.execute(select_sql, (ident,))

            row = cursor.fetchone()
            if not row:
                return None

            # Create and populate instance
            instance = entity()
            column_names = [desc[0] for desc in cursor.description]

            for i, name in enumerate(column_names):
                if hasattr(instance, name):
                    # Get column type if available
                    col_type = next((col['type'] for col in metadata['columns']
                                     if col['name'] == name), None)
                    # Convert to appropriate Python type
                    value = self._convert_from_sqlite(row[i], col_type)
                    setattr(instance, name, value)

            logger.debug(f"Retrieved {metadata['tablename']} instance with {pk_column}={ident}")
            return instance

        except Exception as e:
            logger.error(f"Error in get: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def __contains__(self, instance):
        """Check if instance exists in database or is pending in session"""
        # Check if in pending objects or deleted objects
        if instance in self._pending_objects or instance in self._deleted_objects:
            return True

        # Check if exists in database
        if not hasattr(instance, '__tablename__'):
            return False

        metadata = self._get_model_metadata(instance.__class__)
        pk_column = metadata['pk_column']
        pk_value = getattr(instance, pk_column, None)

        if pk_value is None:
            return False

        cursor = None
        try:
            cursor = self.connection.cursor()
            check_sql = f"SELECT 1 FROM {metadata['tablename']} WHERE {pk_column} = ? LIMIT 1"
            cursor.execute(check_sql, (pk_value,))
            exists = cursor.fetchone() is not None
            return exists
        except Exception as e:
            logger.error(f"Error in __contains__: {e}")
            return False
        finally:
            if cursor:
                cursor.close()


class SQLCipherResultProxy:
    """A proxy for database query results that provides SQLAlchemy-like functionality"""

    def __init__(self, results=None, column_names=None, rowcount=None, lastrowid=None):
        self.results = results or []
        self.column_names = column_names or []
        self.rowcount = rowcount
        self.lastrowid = lastrowid
        self._index = 0

    def __iter__(self):
        return iter(self.results)

    def fetchone(self):
        """Fetch the next row"""
        if self._index < len(self.results):
            row = self.results[self._index]
            self._index += 1
            return row
        return None

    def fetchall(self):
        """Fetch all remaining rows"""
        remaining = self.results[self._index:]
        self._index = len(self.results)
        return remaining

    def scalar(self):
        """Get first column of first row"""
        if self.results and len(self.results) > 0 and len(self.results[0]) > 0:
            return self.results[0][0]
        return None

    def scalar_one(self):
        """Get first column of first row, raising error if no results"""
        if not self.results or len(self.results) == 0:
            raise ValueError("No results found for scalar_one()")
        return self.results[0][0]

    def scalar_one_or_none(self):
        """Get first column of first row, or None if no results"""
        if not self.results or len(self.results) == 0:
            return None
        return self.results[0][0]

    def first(self):
        """Get first row"""
        if self.results and len(self.results) > 0:
            return self.results[0]
        return None

    def keys(self):
        """Get column names"""
        return self.column_names

    def __len__(self):
        """Get result count"""
        return len(self.results)


class SQLCipherQuery:
    """
    A query builder that provides SQLAlchemy-like query functionality
    for use with SQLCipherSession.
    """

    def __init__(self, session, entities):
        self.session = session
        self.entities = entities
        self.model = entities[0] if entities else None
        self._filter_clauses = []
        self._order_by_clauses = []
        self._group_by_clauses = []
        self._joins = []
        self._limit = None
        self._offset = None
        self._distinct = False
        self._having_clauses = []
        self._select_columns = []

    def filter(self, *criteria):
        """Add filter criteria (WHERE clause)"""
        self._filter_clauses.extend(criteria)
        return self

    def filter_by(self, **kwargs):
        """Add equality filter criteria (column=value)"""
        for key, value in kwargs.items():
            # Create a simple equality filter
            self._filter_clauses.append((key, value))
        return self

    def order_by(self, *criteria):
        """Add ORDER BY criteria"""
        self._order_by_clauses.extend(criteria)
        return self

    def group_by(self, *criteria):
        """Add GROUP BY criteria"""
        self._group_by_clauses.extend(criteria)
        return self

    def having(self, *criteria):
        """Add HAVING criteria"""
        self._having_clauses.extend(criteria)
        return self

    def join(self, target, onclause=None, isouter=False):
        """Add JOIN clause"""
        self._joins.append({
            'target': target,
            'onclause': onclause,
            'isouter': isouter
        })
        return self

    def outerjoin(self, target, onclause=None):
        """Add LEFT OUTER JOIN clause"""
        return self.join(target, onclause, isouter=True)

    def limit(self, limit):
        """Set LIMIT clause"""
        self._limit = limit
        return self

    def offset(self, offset):
        """Set OFFSET clause"""
        self._offset = offset
        return self

    def distinct(self, *args):
        """Set DISTINCT flag"""
        self._distinct = True
        if args:
            self._select_columns.extend(args)
        return self

    def count(self):
        """Get count of rows"""
        sql, params = self._build_count_query()
        result = self.session.execute(sql, params)
        return result.scalar()

    def exists(self):
        """Check if any rows match the query"""
        sql, params = self._build_exists_query()
        result = self.session.execute(sql, params)
        return bool(result.scalar())

    def first(self):
        """Get first result"""
        self._limit = 1
        return self._fetch_one_instance()

    def one(self):
        """Get exactly one result, raising error if not exactly one"""
        self._limit = 2  # Get 2 to verify only one exists
        instances = self._fetch_instances()

        if not instances:
            raise ValueError("No results found for one()")
        if len(instances) > 1:
            raise ValueError(f"Multiple results found for one(): {len(instances)} rows")

        return instances[0]

    def one_or_none(self):
        """Get one result, or None if no results, raising error if multiple"""
        self._limit = 2  # Get 2 to verify at most one exists
        instances = self._fetch_instances()

        if not instances:
            return None
        if len(instances) > 1:
            raise ValueError(f"Multiple results found for one_or_none(): {len(instances)} rows")

        return instances[0]

    def all(self):
        """Get all results"""
        return self._fetch_instances()

    def _fetch_one_instance(self):
        """Fetch one instance from database"""
        instances = self._fetch_instances()
        if instances:
            return instances[0]
        return None

    def _fetch_instances(self):
        """Fetch instances from database based on the query"""
        sql, params = self._build_query()

        cursor = None
        try:
            cursor = self.session.connection.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()

            if not rows:
                return []

            # We need to determine the primary entity
            primary_entity = self.model

            # Create and populate model instances
            results = []
            column_names = [desc[0] for desc in cursor.description]

            for row in rows:
                # Create primary instance
                instance = primary_entity()

                # Get metadata for type conversion
                metadata = self.session._get_model_metadata(primary_entity)

                for i, column in enumerate(column_names):
                    # Skip columns from joined tables for now
                    # In a full implementation, this would handle dot notation (table.column)
                    if '.' in column:
                        continue

                    if hasattr(instance, column):
                        # Get column type if available
                        col_type = next((col['type'] for col in metadata['columns']
                                         if col['name'] == column), None)
                        # Convert to appropriate Python type
                        value = self.session._convert_from_sqlite(row[i], col_type)
                        setattr(instance, column, value)

                results.append(instance)

            logger.debug(f"Retrieved {len(results)} instances from {primary_entity.__tablename__}")
            return results

        except Exception as e:
            logger.error(f"Error in _fetch_instances: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def _build_query(self):
        """Build SQL query string and parameters from query attributes"""
        if not self.model or not hasattr(self.model, '__tablename__'):
            raise ValueError("Query requires a model with __tablename__")

        model_metadata = self.session._get_model_metadata(self.model)
        table_name = model_metadata['tablename']

        # Build SELECT clause
        select_clause = "SELECT "
        if self._distinct:
            select_clause += "DISTINCT "

        if self._select_columns:
            select_clause += ", ".join(self._select_columns)
        else:
            select_clause += f"{table_name}.*"

        # Add FROM clause
        from_clause = f" FROM {table_name}"

        # Build JOIN clauses (simplified)
        join_clause = ""
        for join in self._joins:
            target = join['target']
            if not hasattr(target, '__tablename__'):
                continue

            join_type = "LEFT JOIN" if join['isouter'] else "JOIN"
            target_table = target.__tablename__

            # Basic join implementation - in a real system, this would parse onclause
            # For now, assume joining on id = foreign_key
            join_clause += f" {join_type} {target_table} ON {table_name}.id = {target_table}.{table_name}_id"

        # Build WHERE clause from filters
        where_clause = ""
        params = []

        if self._filter_clauses:
            where_conditions = []

            for filter_item in self._filter_clauses:
                if isinstance(filter_item, tuple) and len(filter_item) == 2:
                    # Simple equality filter (column, value)
                    where_conditions.append(f"{filter_item[0]} = ?")
                    params.append(self.session._convert_value_for_sqlite(filter_item[1]))
                elif hasattr(filter_item, 'left') and hasattr(filter_item, 'right'):
                    # Try to handle SQLAlchemy BinaryExpression
                    # This is a simplified implementation
                    column_name = filter_item.left.name if hasattr(filter_item.left, 'name') else str(filter_item.left)

                    # Determine operator from the expression
                    op = '='  # Default operator
                    if hasattr(filter_item, 'operator'):
                        op_str = str(filter_item.operator)
                        if 'eq' in op_str:
                            op = '='
                        elif 'ne' in op_str:
                            op = '!='
                        elif 'lt' in op_str:
                            op = '<'
                        elif 'le' in op_str:
                            op = '<='
                        elif 'gt' in op_str:
                            op = '>'
                        elif 'ge' in op_str:
                            op = '>='
                        elif 'like' in op_str.lower():
                            op = 'LIKE'

                    # Get value from right side
                    if hasattr(filter_item.right, 'value'):
                        value = filter_item.right.value
                    else:
                        value = filter_item.right

                    where_conditions.append(f"{column_name} {op} ?")
                    params.append(self.session._convert_value_for_sqlite(value))
                else:
                    # For unknown filter types, add a placeholder condition
                    logger.warning(f"Unsupported filter type: {type(filter_item)}")
                    where_conditions.append("1=1")

            if where_conditions:
                where_clause = " WHERE " + " AND ".join(where_conditions)

        # Build GROUP BY clause
        group_by_clause = ""
        if self._group_by_clauses:
            group_columns = []
            for group_item in self._group_by_clauses:
                if hasattr(group_item, 'name'):
                    group_columns.append(group_item.name)
                else:
                    group_columns.append(str(group_item))

            if group_columns:
                group_by_clause = " GROUP BY " + ", ".join(group_columns)

        # Build HAVING clause
        having_clause = ""
        if self._having_clauses and group_by_clause:
            # Similar implementation to WHERE clause
            having_conditions = []

            for having_item in self._having_clauses:
                # Simplified handling
                having_conditions.append("1=1")

            if having_conditions:
                having_clause = " HAVING " + " AND ".join(having_conditions)

        # Build ORDER BY clause
        order_by_clause = ""
        if self._order_by_clauses:
            order_columns = []
            for order_item in self._order_by_clauses:
                if hasattr(order_item, 'name'):
                    # Check for desc() modifier
                    direction = "DESC" if hasattr(order_item, 'modifier') and 'desc' in str(
                        order_item.modifier) else "ASC"
                    order_columns.append(f"{order_item.name} {direction}")
                else:
                    order_columns.append(str(order_item))

            if order_columns:
                order_by_clause = " ORDER BY " + ", ".join(order_columns)

        # Add LIMIT and OFFSET
        limit_clause = f" LIMIT {self._limit}" if self._limit is not None else ""
        offset_clause = f" OFFSET {self._offset}" if self._offset is not None else ""

        # Combine all clauses
        sql = select_clause + from_clause + join_clause + where_clause + \
              group_by_clause + having_clause + order_by_clause + \
              limit_clause + offset_clause

        logger.debug(f"Built SQL: {sql}")
        logger.debug(f"Parameters: {params}")

        return sql, params

    def _build_count_query(self):
        """Build a query to count results"""
        if not self.model or not hasattr(self.model, '__tablename__'):
            raise ValueError("Query requires a model with __tablename__")

        table_name = self.model.__tablename__

        # Base SELECT COUNT(*) query
        select_clause = "SELECT COUNT(*)"
        if self._distinct and self._select_columns:
            # For DISTINCT with specific columns
            columns = ", ".join(self._select_columns)
            select_clause = f"SELECT COUNT(DISTINCT {columns})"

        # Add FROM clause
        from_clause = f" FROM {table_name}"

        # Build JOIN clauses (reusing same logic)
        join_clause = ""
        for join in self._joins:
            target = join['target']
            if not hasattr(target, '__tablename__'):
                continue

            join_type = "LEFT JOIN" if join['isouter'] else "JOIN"
            target_table = target.__tablename__

            # Basic join implementation
            join_clause += f" {join_type} {target_table} ON {table_name}.id = {target_table}.{table_name}_id"

        # Build WHERE clause (reusing same logic)
        where_clause = ""
        params = []

        if self._filter_clauses:
            where_conditions = []

            for filter_item in self._filter_clauses:
                if isinstance(filter_item, tuple) and len(filter_item) == 2:
                    # Simple equality filter
                    where_conditions.append(f"{filter_item[0]} = ?")
                    params.append(self.session._convert_value_for_sqlite(filter_item[1]))
                elif hasattr(filter_item, 'left') and hasattr(filter_item, 'right'):
                    # Try to handle SQLAlchemy BinaryExpression
                    column_name = filter_item.left.name if hasattr(filter_item.left, 'name') else str(filter_item.left)

                    # Determine operator
                    op = '='  # Default operator
                    if hasattr(filter_item, 'operator'):
                        op_str = str(filter_item.operator)
                        if 'eq' in op_str:
                            op = '='
                        elif 'ne' in op_str:
                            op = '!='
                        elif 'lt' in op_str:
                            op = '<'
                        elif 'le' in op_str:
                            op = '<='
                        elif 'gt' in op_str:
                            op = '>'
                        elif 'ge' in op_str:
                            op = '>='
                        elif 'like' in op_str.lower():
                            op = 'LIKE'

                    # Get value
                    if hasattr(filter_item.right, 'value'):
                        value = filter_item.right.value
                    else:
                        value = filter_item.right

                    where_conditions.append(f"{column_name} {op} ?")
                    params.append(self.session._convert_value_for_sqlite(value))
                else:
                    # For unknown filter types, add a placeholder
                    logger.warning(f"Unsupported filter type in count query: {type(filter_item)}")
                    where_conditions.append("1=1")

            if where_conditions:
                where_clause = " WHERE " + " AND ".join(where_conditions)

        # Combine clauses for count query
        # Note: COUNT queries don't need ORDER BY, LIMIT, or OFFSET
        sql = select_clause + from_clause + join_clause + where_clause

        logger.debug(f"Built COUNT SQL: {sql}")
        logger.debug(f"Parameters: {params}")

        return sql, params

    def _build_exists_query(self):
        """Build a query to check if results exist"""
        if not self.model or not hasattr(self.model, '__tablename__'):
            raise ValueError("Query requires a model with __tablename__")

        table_name = self.model.__tablename__

        # Base EXISTS query
        select_clause = "SELECT EXISTS(SELECT 1"

        # Add FROM clause
        from_clause = f" FROM {table_name}"

        # Build JOIN clauses (same logic)
        join_clause = ""
        for join in self._joins:
            target = join['target']
            if not hasattr(target, '__tablename__'):
                continue

            join_type = "LEFT JOIN" if join['isouter'] else "JOIN"
            target_table = target.__tablename__

            # Basic join implementation
            join_clause += f" {join_type} {target_table} ON {table_name}.id = {target_table}.{table_name}_id"

        # Build WHERE clause (same logic)
        where_clause = ""
        params = []

        if self._filter_clauses:
            where_conditions = []

            for filter_item in self._filter_clauses:
                if isinstance(filter_item, tuple) and len(filter_item) == 2:
                    # Simple equality filter
                    where_conditions.append(f"{filter_item[0]} = ?")
                    params.append(self.session._convert_value_for_sqlite(filter_item[1]))
                elif hasattr(filter_item, 'left') and hasattr(filter_item, 'right'):
                    # Try to handle SQLAlchemy BinaryExpression
                    column_name = filter_item.left.name if hasattr(filter_item.left, 'name') else str(filter_item.left)

                    # Determine operator
                    op = '='  # Default operator
                    if hasattr(filter_item, 'operator'):
                        op_str = str(filter_item.operator)
                        if 'eq' in op_str:
                            op = '='
                        elif 'ne' in op_str:
                            op = '!='
                        elif 'lt' in op_str:
                            op = '<'
                        elif 'le' in op_str:
                            op = '<='
                        elif 'gt' in op_str:
                            op = '>'
                        elif 'ge' in op_str:
                            op = '>='
                        elif 'like' in op_str.lower():
                            op = 'LIKE'

                    # Get value
                    if hasattr(filter_item.right, 'value'):
                        value = filter_item.right.value
                    else:
                        value = filter_item.right

                    where_conditions.append(f"{column_name} {op} ?")
                    params.append(self.session._convert_value_for_sqlite(value))
                else:
                    # For unknown filter types, add a placeholder
                    logger.warning(f"Unsupported filter type in exists query: {type(filter_item)}")
                    where_conditions.append("1=1")

            if where_conditions:
                where_clause = " WHERE " + " AND ".join(where_conditions)

        # Combine clauses for EXISTS query - close the subquery
        sql = select_clause + from_clause + join_clause + where_clause + ")"

        logger.debug(f"Built EXISTS SQL: {sql}")
        logger.debug(f"Parameters: {params}")

        return sql, params


# Helper function for dependency injection
def get_db() -> Generator[Union[Session, SQLCipherSession], None, None]:
    """Dependency for FastAPI to inject a database session"""
    db = None
    try:
        # Always use SessionLocal() which now handles both modes
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


# -----------------------------------------------------------------------------
# Database Management Functions
# -----------------------------------------------------------------------------

def verify_db_connection() -> bool:
    """Verify that we can connect to the database"""
    if use_sqlcipher:
        return EncryptionManager.test_encrypted_database(db_path)
    else:
        try:
            with engine.connect() as connection:
                result = connection.execute(text("SELECT 1")).scalar_one()
                logger.info("Standard DB verified via SQLAlchemy engine.")
                return True
        except Exception as e:
            logger.error(f"Database connection verification failed: {e}")
            return False


def init_db() -> bool:
    """Initialize the database schema"""
    logger.info("Initializing database schema...")

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

            conn = engine.connect()
            table_count = conn.execute(text("SELECT count(*) FROM sqlite_master WHERE type='table';")).scalar_one()
            conn.close()
            logger.info(f"Database schema initialized with {table_count} tables.")
            return True
        except Exception as e:
            logger.error(f"Database schema initialization failed: {str(e)}")
            logger.exception("Database initialization error details:")
            return False


def get_encryption_status() -> dict:
    """Get current encryption status information"""
    key_loaded = EncryptionManager.get_key() is not None
    return {
        "encryption_enabled_setting": settings.USE_SQLCIPHER,
        "sqlcipher_available": EncryptionManager.is_sqlcipher_available(),
        "encryption_active": use_sqlcipher and key_loaded,
        "database_path": db_path,
        "direct_sqlcipher_mode": direct_sqlcipher_mode if 'direct_sqlcipher_mode' in locals() else False,
        "has_encryption_key_loaded": key_loaded
    }