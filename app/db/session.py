#!/usr/bin/env python
"""
Database session and connection management with SQLCipher encryption support.
Using direct SQLCipher connection for initial database creation and setup.
"""

import os
import logging
from typing import Generator, Any, Optional, Union, Dict, List, Callable
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool, Pool
from sqlalchemy.engine import Engine
import sqlite3
import sqlalchemy
from sqlalchemy.sql import ClauseElement

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
        Creates and returns a SQLCipher connection object.
        This ensures the connection can access the encrypted database.

        Args:
            db_path: Path to the SQLCipher database

        Returns:
            A SQLCipher connection with parameters configured
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
            # Configure encryption
            cursor.execute(f"PRAGMA key='{encryption_key}';")
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
    Simple connection pool for SQLCipher connections that manages connections directly,
    bypassing SQLAlchemy's dialect handling to avoid compatibility issues.
    """

    def __init__(self, db_path, pool_size=5, max_overflow=10):
        self.db_path = db_path
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.connections = []
        self.in_use = set()

    def _create_connection(self):
        """Create a new connection with all SQLCipher parameters configured"""
        return EncryptionManager.get_encrypted_connection(self.db_path)

    def connect(self):
        """Get a connection from the pool or create a new one"""
        if not self.connections:
            conn = self._create_connection()
            self.in_use.add(id(conn))
            return conn

        conn = self.connections.pop()
        self.in_use.add(id(conn))
        return conn

    def release(self, conn):
        """Return a connection to the pool"""
        if id(conn) in self.in_use:
            self.in_use.remove(id(conn))
            if len(self.connections) < self.pool_size:
                self.connections.append(conn)
            else:
                conn.close()

    def dispose(self):
        """Close all connections in the pool"""
        while self.connections:
            conn = self.connections.pop()
            conn.close()

        # Force closure of any unreturned connections
        self.in_use.clear()


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
if use_sqlcipher:
    logger.info(f"Creating engine with direct SQLCipher connections for {db_path}")

    # Create a direct connection pool for SQLCipher
    connection_pool = DirectSQLCipherPool(db_path)

    # Create a standard SQLite engine for metadata operations only
    # This engine is NOT used for actual database operations
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False}
    )

    # This is a flag to let dependency injection know we're using custom connections
    direct_sqlcipher_mode = True


    # Create a SessionLocal factory for compatibility with imports
    # This will return our custom SQLCipherSession instead
    def SessionLocal():
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
    A custom session that works with direct SQLCipher connections,
    implementing just enough of the SQLAlchemy Session API for compatibility.
    """

    def __init__(self, connection_pool):
        self.connection_pool = connection_pool
        self._connection = None
        self.closed = False
        # Add more attributes expected by SQLAlchemy Session API
        self.bind = None  # Normally an Engine
        self.autocommit = False
        self.autoflush = False
        self.info = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_user_by_id(self, user_id):
        """
        Direct implementation for user lookup by ID that reads the key
        directly from the file to ensure it matches what was used during login.
        """
        import os
        from app.core.config import settings
        from app.db.models.user import User

        # Print debug information to logs
        logger.info(f"Looking up user with ID: {user_id}")

        # Read key directly from file, matching the approach used during database creation
        key_file_path = os.path.abspath(settings.KEY_FILE_PATH)
        logger.debug(f"Reading encryption key directly from file: {key_file_path}")

        try:
            with open(key_file_path, "r", encoding="utf-8") as f:
                key = f.read().strip()

            logger.debug(f"Key read from file, length: {len(key)}")

            # Now use this key to access the database
            sqlcipher = EncryptionManager.get_sqlcipher_module()
            conn = sqlcipher.connect(db_path)
            cursor = conn.cursor()

            # Use the Hex key format which was successful in login
            cursor.execute(f"PRAGMA key=\"x'{key}'\";")
            cursor.execute("PRAGMA foreign_keys=ON;")

            # Test connection
            try:
                cursor.execute("SELECT count(*) FROM sqlite_master;")
                table_count = cursor.fetchone()[0]
                logger.debug(f"Successfully connected to the database with {table_count} tables")
            except Exception as e:
                logger.error(f"Connection test failed: {e}")
                cursor.close()
                conn.close()
                return None

            # Query for the user by ID
            query = """
            SELECT id, email, username, hashed_password, full_name, 
                   is_active, is_superuser, last_login, change_history, 
                   created_at, updated_at
            FROM users 
            WHERE id = ?
            LIMIT 1
            """
            cursor.execute(query, (user_id,))
            result = cursor.fetchone()

            if not result:
                logger.error(f"No user found with ID: {user_id}")
                cursor.close()
                conn.close()
                return None

            # Create a user object with the retrieved data
            user = User()

            # Map database columns to user object attributes
            user.id = result[0]
            user.email = result[1]
            user.username = result[2]
            user.hashed_password = result[3]
            user.full_name = result[4]
            user.is_active = bool(result[5])
            user.is_superuser = bool(result[6])
            user.last_login = result[7]
            user.change_history = result[8]
            user.created_at = result[9]
            user.updated_at = result[10]

            logger.info(f"Successfully retrieved user ID: {user.id}, email: {user.email}")

            cursor.close()
            conn.close()
            return user

        except Exception as e:
            logger.error(f"Error in get_user_by_id: {e}")
            return None

    def get_user_by_email(self, email):
        """
        Direct implementation for user lookup by email that reads the key
        directly from the file to ensure it matches what was used to create the database.
        """
        import os
        from app.core.config import settings

        # Read key directly from file, matching the approach used during database creation
        key_file_path = os.path.abspath(settings.KEY_FILE_PATH)
        logger.info(f"Reading encryption key directly from file: {key_file_path}")

        try:
            with open(key_file_path, "r", encoding="utf-8") as f:
                key = f.read().strip()

            logger.info(f"Key read from file, length: {len(key)}")

            # Now use this key to access the database
            sqlcipher = EncryptionManager.get_sqlcipher_module()
            conn = sqlcipher.connect(db_path)
            cursor = conn.cursor()

            # Apply encryption parameters
            cursor.execute(f"PRAGMA key='{key}';")
            cursor.execute("PRAGMA cipher_page_size=4096;")
            cursor.execute("PRAGMA kdf_iter=256000;")
            cursor.execute("PRAGMA cipher_hmac_algorithm=HMAC_SHA512;")
            cursor.execute("PRAGMA cipher_kdf_algorithm=PBKDF2_HMAC_SHA512;")
            cursor.execute("PRAGMA foreign_keys=ON;")

            # Test connection
            try:
                cursor.execute("SELECT count(*) FROM sqlite_master;")
                table_count = cursor.fetchone()[0]
                logger.info(f"Successfully connected to the database with {table_count} tables")
            except Exception as e:
                logger.error(f"Connection test failed: {e}")
                cursor.close()
                conn.close()
                return None

            # Query for the user
            query = """
            SELECT id, email, username, hashed_password, full_name, 
                   is_active, is_superuser, last_login, change_history, 
                   created_at, updated_at
            FROM users 
            WHERE email = ?
            LIMIT 1
            """
            cursor.execute(query, (email,))
            result = cursor.fetchone()

            if not result:
                logger.debug(f"No user found with email: {email}")
                cursor.close()
                conn.close()
                return None

            # Create a user object with the retrieved data
            from app.db.models.user import User
            user = User()

            # Map database columns to user object attributes
            user.id = result[0]
            user.email = result[1]
            user.username = result[2]
            user.hashed_password = result[3]
            user.full_name = result[4]
            user.is_active = bool(result[5])
            user.is_superuser = bool(result[6])
            user.last_login = result[7]
            user.change_history = result[8]
            user.created_at = result[9]
            user.updated_at = result[10]

            logger.info(f"Successfully retrieved user: {user.email}")

            cursor.close()
            conn.close()
            return user

        except Exception as e:
            logger.error(f"Error in get_user_by_email: {e}")
            return None

    # Add this method to the SQLCipherQuery class
    def filter_by_email(self, email):
        """Special case handling for email filtering"""
        if hasattr(self.model, '__tablename__') and self.model.__tablename__ == 'users':
            # Create a special subclass with the user lookup method
            class UserFilterQuery(SQLCipherQuery):
                def first(self_subclass):
                    return self.session.get_user_by_email(email)

            return UserFilterQuery(self.session, self.model)
        return self

    # Modify the SQLCipherQuery.filter method
    def filter(self, *criteria):
        """Add filter criteria - translates to WHERE clause"""
        self._filter_clauses.extend(criteria)

        # Handle the special case for user email filtering
        for criterion in criteria:
            # This is a very basic detection of a user email filter clause
            if hasattr(criterion, 'left') and hasattr(criterion.left, 'name') and criterion.left.name == 'email':
                if hasattr(criterion, 'right') and isinstance(criterion.right, str):
                    return self.filter_by_email(criterion.right)

        return self

    def close(self):
        if not self.closed and self._connection:
            self.connection_pool.release(self._connection)
            self._connection = None
            self.closed = True

    @property
    def connection(self):
        if self.closed:
            raise RuntimeError("Session is closed")
        if not self._connection:
            self._connection = self.connection_pool.connect()
        return self._connection

    def execute(self, statement, params=None):
        """Execute a SQL statement directly"""
        cursor = None
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(statement, params)
            else:
                cursor.execute(statement)

            if statement.upper().startswith(("SELECT", "PRAGMA")):
                result = cursor.fetchall()
                return result
            else:
                self.connection.commit()
                return cursor.rowcount
        finally:
            if cursor:
                cursor.close()

    def query(self, model):
        """Support basic ORM-style query"""
        return SQLCipherQuery(self, model)

    def commit(self):
        """Commit the current transaction"""
        if not self.closed and self._connection:
            self._connection.commit()

    def rollback(self):
        """Rollback the current transaction"""
        if not self.closed and self._connection:
            self._connection.rollback()

    def add(self, instance):
        """Add an instance - stub for compatibility"""
        logger.warning(f"SQLCipherSession.add() is not fully implemented")
        logger.debug(f"Would add instance: {instance}")
        # Implementation would convert to INSERT

    def delete(self, instance):
        """Delete an instance - stub for compatibility"""
        logger.warning(f"SQLCipherSession.delete() is not fully implemented")
        logger.debug(f"Would delete instance: {instance}")
        # Implementation would convert to DELETE

    # Add methods expected by SQLAlchemy Session API
    def flush(self, objects=None):
        """Flush changes - stub for compatibility"""
        pass

    def refresh(self, instance, attribute_names=None):
        """Refresh instance - stub for compatibility"""
        logger.warning(f"SQLCipherSession.refresh() is not fully implemented")

    def expunge(self, instance):
        """Remove instance from session - stub for compatibility"""
        pass

    def expunge_all(self):
        """Remove all instances from session - stub for compatibility"""
        pass

    def merge(self, instance, load=True):
        """Merge instance - stub for compatibility"""
        logger.warning(f"SQLCipherSession.merge() is not fully implemented")
        return instance

    def get(self, entity, ident, options=None):
        """Get by primary key - stub for compatibility"""
        logger.warning(f"SQLCipherSession.get() is not fully implemented")
        return None

    def __contains__(self, instance):
        """Check if instance is in session - stub for compatibility"""
        return False


class SQLCipherQuery:
    """
    A simplified query API that mimics SQLAlchemy's Query class
    enough to work with basic ORM operations.
    """

    def __init__(self, session, model):
        self.session = session
        self.model = model
        self._filter_clauses = []
        self._limit = None
        self._offset = None

    def filter(self, *criteria):
        """Add filter criteria - translates to WHERE clause"""
        self._filter_clauses.extend(criteria)
        return self

    def first(self):
        """Get first result - stub for compatibility"""
        # In real implementation, this would generate SQL and execute
        # For now, we'll just show debug info
        self._limit = 1
        logger.debug(f"Would query {self.model.__tablename__} with filters and limit 1")
        return None  # Would return first result

    def all(self):
        """Get all results - stub for compatibility"""
        logger.debug(f"Would query all {self.model.__tablename__} with filters")
        return []  # Would return all matching results

    def limit(self, limit):
        """Set LIMIT clause"""
        self._limit = limit
        return self

    def offset(self, offset):
        """Set OFFSET clause"""
        self._offset = offset
        return self


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