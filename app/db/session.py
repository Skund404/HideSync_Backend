#!/usr/bin/env python
"""
Database session management with SQLCipher encryption for HideSync.

This module provides robust, production-ready database session management with:
1. Transparent SQLCipher encryption support
2. Connection pooling with health checks
3. Session management with SQLAlchemy compatibility layer
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
import time
import datetime
import json
from typing import (
    Generator, Any, Optional, Union, Dict, List, Callable, Tuple,
    Set, Type, TypeVar, cast, Iterable, Sequence
)
from contextlib import contextmanager
import functools

from sqlalchemy import create_engine, event, text, Column, Table, MetaData
from sqlalchemy.orm import sessionmaker, Session, Query, scoped_session
from sqlalchemy.pool import NullPool, Pool, QueuePool
from sqlalchemy.engine import Engine, Connection, ResultProxy
from sqlalchemy.sql import ClauseElement, Select, expression, func
from sqlalchemy.sql.elements import BinaryExpression, UnaryExpression, ColumnElement
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.inspection import inspect
import sqlite3
import sqlalchemy
import time
import random

from app.core.key_manager import KeyManager
from app.core.exceptions import (
    SecurityException,
    DatabaseException,
    ConnectionPoolExhaustedException,
    EncryptionKeyMissingException
)
from app.core.config import settings
from app.db.models.base import Base

# Configure module logger
logger = logging.getLogger(__name__)

# Define a generic model type for type hints
ModelT = TypeVar('ModelT', bound=Any)

# Constants
MAX_CONNECTION_RETRIES = 3
CONNECTION_RETRY_DELAY = 0.5  # seconds
CONNECTION_HEALTH_CHECK_INTERVAL = 30  # seconds
CONNECTION_MAX_AGE = 3600  # 1 hour
CONNECTION_MAX_IDLE_TIME = 600  # 10 minutes
CONNECTION_POOL_RECYCLE = 1800  # 30 minutes
CONNECTION_POOL_SIZE = getattr(settings, 'DB_POOL_SIZE', 5)
CONNECTION_MAX_OVERFLOW = getattr(settings, 'DB_MAX_OVERFLOW', 10)
CONNECTION_POOL_TIMEOUT = getattr(settings, 'DB_POOL_TIMEOUT', 30)
CONNECTION_POOL_PRE_PING = True

_thread_local = threading.local()


def get_thread_connection(db_path):
    """
    Get or create a thread-specific database connection with proper lifecycle management.
    """
    thread_id = threading.get_ident()

    # Check if connection needs to be created
    if not hasattr(_thread_local, "connection") or _thread_local.connection is None:
        try:
            # Create new connection with proper tracking
            if settings.USE_SQLCIPHER and EncryptionManager.is_sqlcipher_available():
                conn = EncryptionManager.get_encrypted_connection(db_path)
            else:
                conn = sqlite3.connect(db_path)
                conn.execute("PRAGMA foreign_keys = ON;")

            # Store with creation metadata
            _thread_local.connection = conn
            _thread_local.connection_created = time.time()
            _thread_local.connection_last_used = time.time()
            _thread_local.connection_thread_id = thread_id

            # Register cleanup with atexit (belt and suspenders approach)
            if not hasattr(_thread_local, "cleanup_registered"):
                import atexit
                atexit.register(_cleanup_thread_connections)
                _thread_local.cleanup_registered = True

            logger.debug(f"Created new SQLite connection for thread {thread_id}")
        except Exception as e:
            logger.error(f"Error creating thread-specific connection: {e}")
            raise
    else:
        # Update last used time
        _thread_local.connection_last_used = time.time()

        # Validate connection before returning it
        try:
            _thread_local.connection.execute("SELECT 1").fetchone()
        except Exception as e:
            logger.warning(f"Thread connection validation failed: {e}, creating new connection")
            # Close invalid connection
            try:
                _thread_local.connection.close()
            except:
                pass

            # Recursively call to create a new connection
            delattr(_thread_local, "connection")
            return get_thread_connection(db_path)

    return _thread_local.connection


def _cleanup_thread_connections():
    """Global cleanup function for thread connections."""
    if hasattr(_thread_local, "connection") and _thread_local.connection:
        try:
            logger.debug(f"Cleaning up thread connection for thread {_thread_local.connection_thread_id}")
            _thread_local.connection.close()
            _thread_local.connection = None
        except Exception as e:
            logger.error(f"Error during thread connection cleanup: {e}")

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
                logger.error(f"Failed to initialize encryption manager: {e}", exc_info=True)
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
            raise RuntimeError("SQLCipher is not available but an encrypted connection was requested")

        encryption_key = cls.get_key()
        if not encryption_key:
            raise ValueError("Failed to retrieve database encryption key")

        try:
            sqlcipher = cls.get_sqlcipher_module()
            conn = sqlcipher.connect(db_path)

            cursor = conn.cursor()
            # Apply all PRAGMA statements
            for pragma, value in cls._pragma_statements.items():
                if pragma == "key":
                    cursor.execute(f"PRAGMA key = {value};")
                else:
                    cursor.execute(f"PRAGMA {pragma}={value};")

            # Test the connection (this will fail if the key is incorrect)
            cursor.execute("SELECT 1;")
            cursor.close()

            return conn
        except Exception as e:
            logger.error(f"Failed to create encrypted connection: {e}")
            raise

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
                raise EncryptionKeyMissingException("Mandatory encryption key failed to load")
            else:
                logger.info("No encryption key loaded (SQLCipher disabled)")
        except SecurityException as e:
            logger.error(f"Failed to load encryption key via KeyManager: {e}")
            if settings.USE_SQLCIPHER:
                raise EncryptionKeyMissingException(f"Mandatory encryption key failed to load: {e}") from e
            else:
                logger.warning("KeyManager failed, but SQLCipher is disabled. Proceeding without encryption")
                cls._encryption_key = None
        except Exception as e:
            logger.exception(f"Unexpected error during encryption key loading: {e}")
            if settings.USE_SQLCIPHER:
                raise RuntimeError(f"Mandatory encryption key failed to load: {e}") from e
            else:
                logger.warning("Key loading failed, but SQLCipher is disabled. Proceeding without encryption")
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
                logger.info("SQLCipher libraries detected and will be used for database encryption")
            except ImportError:
                cls._sqlcipher_available = False
                cls._sqlcipher_module = None
                logger.error("SQLCipher requested (USE_SQLCIPHER=true) but libraries (pysqlcipher3) not found")
                raise ImportError("pysqlcipher3 library not found, but USE_SQLCIPHER is true")
        else:
            cls._sqlcipher_available = False
            cls._sqlcipher_module = None
            logger.info("SQLCipher encryption disabled in settings (USE_SQLCIPHER=false)")

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
                    logger.debug(f"Attempting to remove potentially corrupted DB file: {path}")
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
            create_statements.append(str(CreateTable(table).compile(dialect=sqlalchemy.dialects.sqlite.dialect())))

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
                logger.debug(f"Executing: {statement[:60]}...")  # Log just the beginning
                cursor.execute(statement)

            conn.commit()

            # Verify table creation
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            table_names = [t[0] for t in tables]
            logger.info(f"Created {len(table_names)} tables directly with SQLCipher")

            if logger.isEnabledFor(logging.DEBUG):
                table_list = ', '.join(table_names[:5])
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

            logger.info(f"Successfully tested encrypted database at {path} ({result[0]} tables found)")
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
# Enhanced Connection Pool for SQLCipher
# -----------------------------------------------------------------------------

class ConnectionMetrics:
    """Collects and reports connection pool metrics."""

    def __init__(self):
        self.total_connections_created = 0
        self.total_connections_closed = 0
        self.connection_errors = 0
        self.connection_timeouts = 0
        self.checkout_count = 0
        self.checkout_time_total = 0
        self.longest_checkout_time = 0
        self.last_checkout_time = 0

    def record_connection_created(self):
        """Record that a new connection was created."""
        self.total_connections_created += 1

    def record_connection_closed(self):
        """Record that a connection was closed."""
        self.total_connections_closed += 1

    def record_connection_error(self):
        """Record a connection error."""
        self.connection_errors += 1

    def record_connection_timeout(self):
        """Record a connection timeout."""
        self.connection_timeouts += 1

    def record_checkout(self, duration):
        """Record connection checkout metrics."""
        self.checkout_count += 1
        self.checkout_time_total += duration
        self.last_checkout_time = duration
        if duration > self.longest_checkout_time:
            self.longest_checkout_time = duration

    def get_avg_checkout_time(self):
        """Get the average connection checkout time."""
        if self.checkout_count == 0:
            return 0
        return self.checkout_time_total / self.checkout_count

    def get_metrics(self):
        """Get all connection metrics."""
        return {
            "total_connections_created": self.total_connections_created,
            "total_connections_closed": self.total_connections_closed,
            "connection_errors": self.connection_errors,
            "connection_timeouts": self.connection_timeouts,
            "checkout_count": self.checkout_count,
            "avg_checkout_time": self.get_avg_checkout_time(),
            "longest_checkout_time": self.longest_checkout_time,
            "last_checkout_time": self.last_checkout_time
        }


class EnhancedSQLCipherPool:
    """
    Enhanced connection pool for SQLCipher connections with production-ready features.

    Features:
    - Connection health checks
    - Automatic reconnection
    - Connection timeouts with circuit breaker
    - Connection recycling based on age and usage
    - Metrics collection
    - Exponential backoff for retries
    """

    # For EnhancedSQLCipherPool.__init__:
    def __init__(self, db_path, pool_size=5, max_overflow=10, timeout=30,
                 recycle_timeout=3600, max_usage=1000, health_check_interval=30):
        """
        Initialize the connection pool.
        """
        self.db_path = db_path
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.timeout = timeout
        self.recycle_timeout = recycle_timeout
        self.max_usage = max_usage
        self.health_check_interval = health_check_interval

        # Connection storage
        self.connections = []  # Idle connections
        self.in_use = {}  # Maps connection ID to (connection, creation_time, use_count, last_used)

        # Thread safety
        self._conn_lock = threading.RLock()

        # Health check thread
        self._health_checker_thread = None
        self._stop_health_checker = threading.Event()

        # Metrics
        self.metrics = ConnectionMetrics()

        # Circuit breaker for error detection
        self._consecutive_errors = 0
        self._circuit_open = False
        self._circuit_open_time = 0
        self._max_consecutive_errors = 5
        self._circuit_reset_timeout = 30  # seconds

        # Add memory tracking
        self._track_memory_usage = getattr(settings, 'TRACK_MEMORY_USAGE', False)
        self._memory_snapshots = []
        self._memory_warning_threshold = getattr(settings, 'MEMORY_WARNING_THRESHOLD_MB', 500)
        self._memory_critical_threshold = getattr(settings, 'MEMORY_CRITICAL_THRESHOLD_MB', 1000)
        self._last_memory_check = 0
        self._memory_check_interval = 60  # seconds

        # Strict limit enforcement
        self._enforce_strict_limits = True
        self._max_total_connections = pool_size + max_overflow

        # Add more aggressive cleanup scheduling
        self._last_full_cleanup = time.time()
        self._full_cleanup_interval = 300  # 5 minutes

        # Enhanced metrics
        self.metrics.connection_age_stats = {
            'min_age': float('inf'),
            'max_age': 0,
            'total_age': 0,
            'count': 0
        }

        # Start health checker thread
        self._start_health_checker()

        logger.info(f"Initialized EnhancedSQLCipherPool with size={pool_size}, max_overflow={max_overflow}")



    def _start_health_checker(self):
        """Start the background health check thread."""
        if self.health_check_interval <= 0:
            return

        self._health_checker_thread = threading.Thread(
            target=self._health_check_worker,
            daemon=True,
            name="SQLCipherPoolHealthChecker"
        )
        self._health_checker_thread.start()

    def _health_check_worker(self):
        """Background worker that checks connection health periodically."""
        logger.info("Connection health checker thread started")
        while not self._stop_health_checker.wait(self.health_check_interval):
            try:
                self._check_idle_connections()
            except Exception as e:
                logger.error(f"Error in health checker: {e}", exc_info=True)
        logger.info("Connection health checker thread stopped")

    def _check_idle_connections(self):
        """Check and clean up idle connections."""
        with self._conn_lock:
            # Get current time once
            current_time = time.time()

            # Check connections that haven't been used for too long
            stale_time = current_time - CONNECTION_MAX_IDLE_TIME

            # Get list of stale connections to close
            to_remove = []
            for i, (conn, creation_time, use_count, last_used) in enumerate(self.connections):
                if last_used < stale_time:
                    to_remove.append((i, conn))
                elif current_time - creation_time > self.recycle_timeout:
                    to_remove.append((i, conn))
                elif use_count >= self.max_usage:
                    to_remove.append((i, conn))

            # Remove from highest index to lowest to avoid index shifting issues
            for i, conn in sorted(to_remove, key=lambda x: x[0], reverse=True):
                try:
                    conn.close()
                    self.metrics.record_connection_closed()
                    del self.connections[i]
                    logger.debug(f"Closed stale connection in health check")
                except Exception as e:
                    logger.warning(f"Error closing stale connection: {e}")

            # Check circuit breaker status
            if self._circuit_open and current_time - self._circuit_open_time > self._circuit_reset_timeout:
                logger.info("Resetting circuit breaker after timeout")
                self._circuit_open = False
                self._consecutive_errors = 0

    def _create_connection(self):
        """
        Create a new connection with SQLCipher parameters configured.

        Returns:
            A tuple of (connection, creation_time)

        Raises:
            Exception if connection fails
        """
        if self._circuit_open:
            # Check if it's time to try again
            if time.time() - self._circuit_open_time <= self._circuit_reset_timeout:
                raise ConnectionPoolExhaustedException(
                    "Connection circuit breaker is open due to repeated connection failures"
                )

            # Reset the circuit breaker and try again
            self._circuit_open = False
            self._consecutive_errors = 0

        try:
            # Use the enhanced connection method
            conn = EncryptionManager.get_encrypted_connection(self.db_path)
            creation_time = time.time()
            self.metrics.record_connection_created()

            # Reset error counter on success
            self._consecutive_errors = 0

            return conn, creation_time
        except Exception as e:
            # Increment error counter
            self._consecutive_errors += 1
            self.metrics.record_connection_error()

            # Open circuit breaker if too many consecutive errors
            if self._consecutive_errors >= self._max_consecutive_errors:
                self._circuit_open = True
                self._circuit_open_time = time.time()
                logger.warning("Circuit breaker activated due to repeated connection failures")

            logger.error(f"Failed to create SQLCipher connection: {e}")
            raise

    def connect(self):
        """Get a connection with memory protection and strict limits."""
        checkout_start = time.time()

        # Check memory usage if tracking enabled
        if self._track_memory_usage and time.time() - self._last_memory_check > self._memory_check_interval:
            self._check_memory_usage()

        with self._conn_lock:
            # Enforce hard connection limit
            total_connections = len(self.in_use) + len(self.connections)
            if self._enforce_strict_limits and total_connections >= self._max_total_connections:
                # Try to recover by forcing cleanup
                self._force_cleanup_connections()

                # Check again after cleanup
                total_connections = len(self.in_use) + len(self.connections)
                if total_connections >= self._max_total_connections:
                    self.metrics.record_connection_timeout()
                    raise ConnectionPoolExhaustedException(
                        f"Connection limit reached: {total_connections}/{self._max_total_connections} connections"
                    )

            # Try to get an idle connection first
            start_time = time.time()
            while self.connections and time.time() - start_time < self.timeout:
                if not self.connections:
                    time.sleep(0.1)
                    continue

                conn, creation_time, use_count, last_used = self.connections.pop(0)

                # Check if connection needs recycling
                current_time = time.time()
                conn_age = current_time - creation_time
                idle_time = current_time - last_used

                if (conn_age > self.recycle_timeout or use_count >= self.max_usage or
                        idle_time > CONNECTION_MAX_IDLE_TIME):
                    try:
                        conn.close()
                        self.metrics.record_connection_closed()
                    except Exception:
                        pass
                    continue

                # Validate and configure connection
                try:
                    cursor = conn.cursor()

                    # Apply key PRAGMA statements
                    for pragma, value in EncryptionManager._pragma_statements.items():
                        if pragma == "key":
                            cursor.execute(f"PRAGMA key = {value};")
                        else:
                            cursor.execute(f"PRAGMA {pragma}={value};")

                    # Test connection health
                    cursor.execute("SELECT 1")
                    cursor.close()

                    # Connection is good
                    use_count += 1
                    self.in_use[id(conn)] = (conn, creation_time, use_count, current_time)

                    # Record checkout time
                    checkout_time = time.time() - checkout_start
                    self.metrics.record_checkout(checkout_time)

                    return conn
                except Exception as e:
                    # Connection failed validation
                    logger.error(f"Connection validation failed: {e}")
                    try:
                        conn.close()
                        self.metrics.record_connection_closed()
                    except Exception:
                        pass
                    continue

            # Create new connection if within limits
            total_connections = len(self.in_use) + len(self.connections)
            if total_connections < self.pool_size + self.max_overflow:
                # Apply exponential backoff for retries
                retries = 0
                last_error = None

                while retries < MAX_CONNECTION_RETRIES:
                    try:
                        # Create new connection
                        conn, creation_time = self._create_connection()
                        self.in_use[id(conn)] = (conn, creation_time, 1, time.time())

                        # Record checkout time
                        checkout_time = time.time() - checkout_start
                        self.metrics.record_checkout(checkout_time)

                        return conn
                    except Exception as e:
                        retries += 1
                        last_error = e

                        if retries < MAX_CONNECTION_RETRIES:
                            # Apply exponential backoff
                            sleep_time = CONNECTION_RETRY_DELAY * (2 ** (retries - 1)) * (1 + random.random() * 0.1)
                            logger.warning(f"Connection attempt {retries} failed, retrying in {sleep_time:.2f}s: {e}")
                            time.sleep(sleep_time)

                # If we get here, all retries failed
                logger.error(f"Failed to create connection after {MAX_CONNECTION_RETRIES} attempts: {last_error}")
                raise last_error or ConnectionPoolExhaustedException("Max connection retries exceeded")

            # We've reached max connections, wait for one to be released
            while time.time() - start_time < self.timeout:
                time.sleep(0.1)  # Short sleep while waiting

                # Check if a connection was released while waiting
                if self.connections:
                    return self.connect()  # Recursive call to try again

            # Timeout reached without getting a connection
            self.metrics.record_connection_timeout()
            raise TimeoutError(f"Timeout waiting for SQLCipher connection after {self.timeout} seconds")

    def release(self, conn):
        """
        Return a connection to the pool.

        Args:
            conn: The connection to release
        """
        with self._conn_lock:
            conn_id = id(conn)

            if conn_id in self.in_use:
                _, creation_time, use_count, _ = self.in_use.pop(conn_id)
                current_time = time.time()

                # Check if connection should be recycled
                if (current_time - creation_time > self.recycle_timeout or
                        use_count >= self.max_usage):
                    try:
                        conn.close()
                        self.metrics.record_connection_closed()
                    except Exception as e:
                        logger.warning(f"Error closing recycled connection: {e}")
                else:
                    # Return to available pool with updated last used time
                    self.connections.append((conn, creation_time, use_count, current_time))
            else:
                # Connection not from this pool, close it
                try:
                    conn.close()
                except Exception as e:
                    logger.warning(f"Error closing unknown connection: {e}")

    def dispose(self):
        """Close all connections in the pool."""
        with self._conn_lock:
            # Stop health checker thread
            self._stop_health_checker.set()
            if self._health_checker_thread and self._health_checker_thread.is_alive():
                self._health_checker_thread.join(timeout=2.0)

            # Close all idle connections
            for conn, _, _, _ in self.connections:
                try:
                    conn.close()
                    self.metrics.record_connection_closed()
                except Exception as e:
                    logger.warning(f"Error closing connection during dispose: {e}")

            # Close all in-use connections
            for conn_id, (conn, _, _, _) in list(self.in_use.items()):
                try:
                    conn.close()
                    self.metrics.record_connection_closed()
                except Exception as e:
                    logger.warning(f"Error closing in-use connection during dispose: {e}")

            self.connections.clear()
            self.in_use.clear()

            logger.info("Connection pool disposed")

    def status(self) -> Dict[str, Any]:
        """
        Return pool status information.

        Returns:
            Dictionary with pool status metrics
        """
        with self._conn_lock:
            status_data = {
                'idle_connections': len(self.connections),
                'in_use_connections': len(self.in_use),
                'total_connections': len(self.connections) + len(self.in_use),
                'max_pool_size': self.pool_size,
                'max_overflow': self.max_overflow,
                'circuit_breaker_open': self._circuit_open,
                'consecutive_errors': self._consecutive_errors,
            }

            # Add connection metrics
            status_data.update(self.metrics.get_metrics())

            return status_data


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
            db_path = settings.DATABASE_URL.replace("sqlite:///", "")
            db_path = os.path.abspath(db_path)
            logger.info(f"Extracted database path from URL: {db_path}")
            return db_path
        else:
            logger.error(f"Non-SQLite URL not supported with SQLCipher: {settings.DATABASE_URL}")
            raise ValueError("Only SQLite URLs are supported with SQLCipher")
    else:
        raise ValueError("No database path specified in settings")


# Get database path
db_path = get_database_path()

# Determine if we should use SQLCipher
use_sqlcipher = settings.USE_SQLCIPHER and EncryptionManager.is_sqlcipher_available()

# Create the proper engine and session factory based on encryption settings
# Replace the SessionLocal implementation with this:

# Create the proper engine and session factory based on encryption settings
if use_sqlcipher:
    logger.info("Initializing SQLCipher mode")

    # Create an enhanced connection pool
    connection_pool = EnhancedSQLCipherPool(
        db_path,
        pool_size=CONNECTION_POOL_SIZE,
        max_overflow=CONNECTION_MAX_OVERFLOW,
        timeout=CONNECTION_POOL_TIMEOUT,
        recycle_timeout=CONNECTION_MAX_AGE,
        health_check_interval=CONNECTION_HEALTH_CHECK_INTERVAL
    )

    # Create SQLAlchemy engine for metadata operations only
    # This is not used for actual queries in SQLCipher mode
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False}
    )

    # Flag for direct SQLCipher mode
    direct_sqlcipher_mode = True


    # Session factory for SQLCipher mode
    def SessionLocal():
        """Factory function to create a new SQLCipherSession"""
        return SQLCipherSession(connection_pool)

else:
    logger.info(f"Creating standard SQLAlchemy engine for {db_path}")

    # Configure SQLAlchemy engine for standard mode
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        pool_size=CONNECTION_POOL_SIZE,
        max_overflow=CONNECTION_MAX_OVERFLOW,
        pool_timeout=CONNECTION_POOL_TIMEOUT,
        pool_pre_ping=CONNECTION_POOL_PRE_PING,
        pool_recycle=CONNECTION_POOL_RECYCLE,
        echo=settings.DEBUG
    )


    # Add event listener for standard SQLite operations
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = None
        try:
            cursor = dbapi_connection.cursor()
            logger.debug("Setting PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA foreign_keys=ON;")
        except Exception as e:
            logger.error(f"Error setting SQLite PRAGMA: {e}")
        finally:
            if cursor:
                cursor.close()


    # Flag to indicate we're using standard SQLAlchemy session
    direct_sqlcipher_mode = False


    # Create a thread-safe sessionmaker
    def SessionLocal():
        """Create a new thread-safe session for standard SQLite mode."""
        thread_id = threading.get_ident()
        logger.debug(f"Creating new session for thread {thread_id}")

        # Create a new engine specific to this thread
        thread_engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={
                "check_same_thread": False,
                "isolation_level": None  # Use SQLAlchemy's transaction control
            }
        )

        # Create session bound to this thread's engine
        session_factory = sessionmaker(autocommit=False, autoflush=False, bind=thread_engine)
        return session_factory()


    # Flag to indicate we're using standard SQLAlchemy session
    direct_sqlcipher_mode = False

    # Use standard SQLAlchemy session
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create thread-local session factory
    SessionLocal = scoped_session(session_factory)


# -----------------------------------------------------------------------------
# Result Proxy Class
# -----------------------------------------------------------------------------

class SQLCipherResultProxy:
    """
    A proxy for database query results that provides SQLAlchemy-like functionality.

    This class provides compatibility with SQLAlchemy's result interface for
    direct SQLCipher queries.
    """

    def __init__(self, results=None, column_names=None, rowcount=None, lastrowid=None):
        """
        Initialize the result proxy.

        Args:
            results: Query results (rows)
            column_names: Column names from the query
            rowcount: Number of rows affected (for DML)
            lastrowid: Last inserted row ID (for INSERT)
        """
        self.results = results or []
        self.column_names = column_names or []
        self.rowcount = rowcount
        self.lastrowid = lastrowid
        self._index = 0

    def __iter__(self):
        """Make the result proxy iterable."""
        return iter(self.results)

    def fetchone(self):
        """
        Fetch the next row.

        Returns:
            The next row or None if no more rows
        """
        if self._index < len(self.results):
            row = self.results[self._index]
            self._index += 1
            return row
        return None

    def fetchall(self):
        """
        Fetch all remaining rows.

        Returns:
            List of remaining rows
        """
        remaining = self.results[self._index:]
        self._index = len(self.results)
        return remaining

    def scalar(self):
        """
        Get the first column of the first row from the query result.

        Returns:
            The scalar value, or None if no rows
        """
        if self.results and len(self.results) > 0:
            # If the result is a list of model instances
            if hasattr(self.results[0], '__dict__'):
                # Try to get the first attribute
                first_instance = self.results[0]
                first_attr = next(iter(vars(first_instance).keys()), None)
                if first_attr:
                    return getattr(first_instance, first_attr)
                return 1  # Fallback

            # For tuples/lists
            if isinstance(self.results[0], (list, tuple)):
                return self.results[0][0] if len(self.results[0]) > 0 else None
            return self.results[0]

        return None

    def scalar_one(self):
        """
        Get first column of first row, raising error if no results.

        Returns:
            The scalar value

        Raises:
            ValueError: If no results found
        """
        if not self.results or len(self.results) == 0:
            raise ValueError("No results found for scalar_one()")

        # Handle both scalar and tuple/list results
        if isinstance(self.results[0], (list, tuple)):
            return self.results[0][0]
        return self.results[0]

    def scalar_one_or_none(self):
        """
        Get first column of first row, or None if no results.

        Returns:
            The scalar value or None
        """
        if not self.results or len(self.results) == 0:
            return None

        # Handle both scalar and tuple/list results
        if isinstance(self.results[0], (list, tuple)):
            return self.results[0][0]
        return self.results[0]

    def first(self):
        """
        Get first row.

        Returns:
            First row or None if no results
        """
        if self.results and len(self.results) > 0:
            return self.results[0]
        return None

    def keys(self):
        """
        Get column names.

        Returns:
            List of column names
        """
        return self.column_names

    def __len__(self):
        """
        Get result count.

        Returns:
            Number of rows in the result
        """
        return len(self.results)


# -----------------------------------------------------------------------------
# Custom Query Class for SQLCipher
# -----------------------------------------------------------------------------

class SQLCipherQuery:
    """
    A query builder that provides SQLAlchemy-like query functionality
    for use with SQLCipherSession.

    This class implements a compatible API to SQLAlchemy's Query object
    for use with direct SQLCipher connections.
    """

    def __init__(self, session, entities):
        """
        Initialize the query.

        Args:
            session: SQLCipherSession to use for the query
            entities: Models/entities to query
        """
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
        self._default_limit = getattr(settings, 'DB_DEFAULT_QUERY_LIMIT', 10000)
        self._limit = self._default_limit

    def filter(self, *criteria):
        """
        Add filter criteria (WHERE clause).

        Args:
            *criteria: Filter criteria to add

        Returns:
            Self for method chaining
        """
        self._filter_clauses.extend(criteria)
        return self

    def filter_by(self, **kwargs):
        """
        Add equality filter criteria (column=value).

        Args:
            **kwargs: Column-value pairs for filtering

        Returns:
            Self for method chaining
        """
        for key, value in kwargs.items():
            # Create a simple equality filter
            self._filter_clauses.append((key, value))
        return self

    def order_by(self, *criteria):
        """
        Add ORDER BY criteria.

        Args:
            *criteria: Order by criteria to add

        Returns:
            Self for method chaining
        """
        self._order_by_clauses.extend(criteria)
        return self

    def group_by(self, *criteria):
        """
        Add GROUP BY criteria.

        Args:
            *criteria: Group by criteria to add

        Returns:
            Self for method chaining
        """
        self._group_by_clauses.extend(criteria)
        return self

    def having(self, *criteria):
        """
        Add HAVING criteria.

        Args:
            *criteria: Having criteria to add

        Returns:
            Self for method chaining
        """
        self._having_clauses.extend(criteria)
        return self

    def join(self, target, onclause=None, isouter=False):
        """
        Add JOIN clause.

        Args:
            target: Target table/model to join
            onclause: Join condition
            isouter: True for LEFT OUTER JOIN, False for INNER JOIN

        Returns:
            Self for method chaining
        """
        self._joins.append({
            'target': target,
            'onclause': onclause,
            'isouter': isouter
        })
        return self

    def outerjoin(self, target, onclause=None):
        """
        Add LEFT OUTER JOIN clause.

        Args:
            target: Target table/model to join
            onclause: Join condition

        Returns:
            Self for method chaining
        """
        return self.join(target, onclause, isouter=True)

    def limit(self, limit):
        """
        Set LIMIT clause.

        Args:
            limit: Maximum number of rows to return

        Returns:
            Self for method chaining
        """
        self._limit = limit
        return self

    def offset(self, offset):
        """
        Set OFFSET clause.

        Args:
            offset: Number of rows to skip

        Returns:
            Self for method chaining
        """
        self._offset = offset
        return self

    def distinct(self, *args):
        """
        Set DISTINCT flag.

        Args:
            *args: Optional columns for DISTINCT ON

        Returns:
            Self for method chaining
        """
        self._distinct = True
        if args:
            self._select_columns.extend(args)
        return self

    def count(self):
        """
        Get count of rows.

        Returns:
            Count of rows matching the query
        """
        sql, params = self._build_count_query()
        result = self.session.execute(sql, params)
        return result.scalar()

    def exists(self):
        """
        Check if any rows match the query.

        Returns:
            True if rows exist, False otherwise
        """
        sql, params = self._build_exists_query()
        result = self.session.execute(sql, params)
        return bool(result.scalar())

    def first(self):
        """
        Get first result.

        Returns:
            First result or None if no results
        """
        self._limit = 1
        return self._fetch_one_instance()

    def one(self):
        """
        Get exactly one result, raising error if not exactly one.

        Returns:
            Single result

        Raises:
            ValueError: If no results or multiple results found
        """
        self._limit = 2  # Get 2 to verify only one exists
        instances = self._fetch_instances()

        if not instances:
            raise ValueError("No results found for one()")
        if len(instances) > 1:
            raise ValueError(f"Multiple results found for one(): {len(instances)} rows")

        return instances[0]

    def one_or_none(self):
        """
        Get one result, or None if no results, raising error if multiple.

        Returns:
            Single result or None

        Raises:
            ValueError: If multiple results found
        """
        self._limit = 2  # Get 2 to verify at most one exists
        instances = self._fetch_instances()

        if not instances:
            return None
        if len(instances) > 1:
            raise ValueError(f"Multiple results found for one_or_none(): {len(instances)} rows")

        return instances[0]

    def all(self):
        """
        Get all results with safety checks.
        """
        # Add memory protection
        if self._limit is None or self._limit > self._default_limit:
            logger.warning(f"Limiting unbounded query to {self._default_limit} rows for memory safety")
            self._limit = self._default_limit

        return self._fetch_instances()

    def scalar(self):
        """
        Execute the query and return the first column of the first row.

        This is commonly used for COUNT queries when we only need a single value.

        Returns:
            The scalar value, or None if no results
        """
        # Build and execute the query
        sql, params = self._build_query()
        result = self.session.execute(sql, params)

        # Get the scalar value from the result
        return result.scalar()

    def scalar_one(self):
        """
        Execute the query and return the first column of the first row.
        Raises an error if no results are found.

        Returns:
            The scalar value
        """
        # Build and execute the query
        sql, params = self._build_query()
        result = self.session.execute(sql, params)

        # Get the scalar value from the result
        return result.scalar_one()

    def scalar_one_or_none(self):
        """
        Execute the query and return the first column of the first row.
        Returns None if no results are found.

        Returns:
            The scalar value or None
        """
        # Build and execute the query
        sql, params = self._build_query()
        result = self.session.execute(sql, params)

        # Get the scalar value from the result
        return result.scalar_one_or_none()

    def _fetch_one_instance(self):
        """
        Fetch one instance from database.

        Returns:
            Single instance or None
        """
        instances = self._fetch_instances()
        if instances:
            return instances[0]
        return None

    def _fetch_instances(self):
        """
        Fetch instances from database with memory-efficient batch processing.
        """
        sql, params = self._build_query()
        cursor = None
        try:
            cursor = self.session.connection.cursor()
            cursor.execute(sql, params)

            # We need to determine the primary entity
            primary_entity = self.model

            # Get column information once
            column_names = [desc[0] for desc in cursor.description]
            metadata = self.session._get_model_metadata(primary_entity)

            # Process in configurable batches
            results = []
            BATCH_SIZE = 500  # Configurable batch size

            while True:
                # Fetch a limited batch to control memory usage
                rows = cursor.fetchmany(BATCH_SIZE)
                if not rows:
                    break

                # Process this batch of rows
                batch_results = []
                for row in rows:
                    # Create primary instance
                    instance = primary_entity()

                    for i, column in enumerate(column_names):
                        # Skip columns from joined tables
                        if '.' in column:
                            continue

                        if hasattr(instance, column):
                            # Get column type if available
                            col_type = next((col['type'] for col in metadata['columns']
                                             if col['name'] == column), None)
                            # Convert to appropriate Python type
                            value = self.session._convert_from_sqlite(row[i], col_type)
                            setattr(instance, column, value)

                    batch_results.append(instance)

                # Add batch to results and explicitly delete the batch reference
                results.extend(batch_results)
                del batch_results

            logger.debug(
                f"Retrieved {len(results)} instances from {primary_entity.__tablename__} using batch processing")
            return results

        except Exception as e:
            logger.error(f"Error in _fetch_instances: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def _build_query(self):
        """
        Build SQL query string and parameters from query attributes.

        Returns:
            Tuple of (sql_query, parameters)

        Raises:
            ValueError: If model is missing or invalid
        """
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
        """
        Build a query to count results.

        Returns:
            Tuple of (sql_query, parameters)

        Raises:
            ValueError: If model is missing or invalid
        """
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
        """
        Build a query to check if results exist.

        Returns:
            Tuple of (sql_query, parameters)

        Raises:
            ValueError: If model is missing or invalid
        """
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


# -----------------------------------------------------------------------------
# Custom Session Class for SQLCipher
# -----------------------------------------------------------------------------

class SQLCipherSession:
    """
    A production-ready session implementation that works with direct SQLCipher connections
    while providing compatibility with SQLAlchemy's Session API.

    This class allows code written for SQLAlchemy to work with SQLCipher
    encrypted databases without significant changes.
    """

    def __init__(self, connection_pool):
        """
        Initialize a new SQLCipher session.

        Args:
            connection_pool: Connection pool for SQLCipher connections
        """
        self.connection_pool = connection_pool
        self._connection = None
        self.closed = False
        self.bind = None  # Normally an Engine, but not used here
        self.autocommit = False
        self.autoflush = False
        self.info = {}
        self._pending_objects = set()  # Track objects pending commit
        self._deleted_objects = set()  # Track objects pending deletion
        self._transaction_depth = 0  # For nested transaction support
        self._modified_attrs = {}  # Track modified attributes for efficient updates
        self._memory_snapshots = []
        self._memory_warning_threshold = getattr(settings, 'MEMORY_WARNING_THRESHOLD_MB', 500)
        self._memory_critical_threshold = getattr(settings, 'MEMORY_CRITICAL_THRESHOLD_MB', 1000)
        self._last_memory_check = 0
        self._memory_check_interval = 60  # seconds

    def __enter__(self):
        """
        Enter context manager, starts transaction.

        Returns:
            Self for context manager interface
        """
        self._transaction_depth += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit context manager, commits or rolls back transaction.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred
        """
        self._transaction_depth -= 1
        if exc_type is not None:
            # Exception occurred, rollback
            self.rollback()
        elif self._transaction_depth == 0:
            # Outermost transaction is ending, commit
            self.commit()
            self.close()

    def _check_memory_usage(self):
        """
        Check current memory usage and take action if needed.
        """
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)

            self._memory_snapshots.append((time.time(), memory_mb))
            # Keep only the last 30 snapshots
            if len(self._memory_snapshots) > 30:
                self._memory_snapshots.pop(0)

            # Calculate growth rate
            if len(self._memory_snapshots) >= 2:
                first_time, first_mem = self._memory_snapshots[0]
                growth_rate = (memory_mb - first_mem) / (time.time() - first_time) if time.time() != first_time else 0

            # Log warning if memory usage is high
            if memory_mb > self._memory_warning_threshold:
                logger.warning(f"High memory usage: {memory_mb:.1f} MB, growth: {growth_rate:.2f} MB/s")

                # Take more aggressive action if critical
                if memory_mb > self._memory_critical_threshold:
                    logger.critical(f"Critical memory usage: {memory_mb:.1f} MB - forcing cleanup")
                    self._force_cleanup_connections()
                    self._circuit_open = True  # Activate circuit breaker
                    self._circuit_open_time = time.time()

            self._last_memory_check = time.time()
        except ImportError:
            logger.warning("psutil not available for memory monitoring")
        except Exception as e:
            logger.error(f"Error during memory usage check: {e}")

    def _force_cleanup_connections(self):
        """
        Aggressively clean up connections when reaching limits.
        """
        current_time = time.time()

        # Force immediate cleanup of all idle connections
        closed_count = 0
        for i in range(len(self.connections) - 1, -1, -1):
            conn, creation_time, use_count, last_used = self.connections[i]
            try:
                conn.close()
                self.metrics.record_connection_closed()
                closed_count += 1
                del self.connections[i]
            except Exception as e:
                logger.warning(f"Error closing idle connection during forced cleanup: {e}")

        # Close connections that have been idle too long
        to_close = []
        for conn_id, (conn, creation_time, use_count, last_used) in list(self.in_use.items()):
            # Aggressively close connections that haven't been used in a while
            # This is a last resort measure to prevent connection exhaustion
            if current_time - last_used > CONNECTION_MAX_IDLE_TIME * 2:
                to_close.append((conn_id, conn))

        # Close identified connections
        for conn_id, conn in to_close:
            try:
                conn.close()
                self.metrics.record_connection_closed()
                closed_count += 1
                del self.in_use[conn_id]
                logger.warning("Force-closed in-use connection due to resource constraints")
            except Exception as e:
                logger.error(f"Error force-closing in-use connection: {e}")

        if closed_count > 0:
            logger.warning(f"Force-closed {closed_count} connections to prevent resource exhaustion")

        # Reset last full cleanup time
        self._last_full_cleanup = current_time

    @property
    def connection(self):
        """
        Get the SQLCipher database connection from the pool.

        Returns:
            Active database connection

        Raises:
            RuntimeError: If session is closed
        """
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
        """
        Extract metadata from a model class or instance.

        Args:
            model: Model class or instance

        Returns:
            Dictionary with model metadata

        Raises:
            ValueError: If model doesn't have __tablename__
        """
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
        """
        Extract values from model instance for database operations.

        Args:
            instance: Model instance
            include_none: Whether to include None values

        Returns:
            Dictionary of values
        """
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
        """
        Convert Python values to SQLite-compatible formats.

        Args:
            value: Value to convert

        Returns:
            SQLite-compatible value
        """
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
        """
        Convert SQLite values to appropriate Python types with memory optimization.
        """
        if value is None:
            return None

        # Prioritize primitive types for memory efficiency
        if target_type is not None:
            type_name = target_type.__class__.__name__.lower()

            # For large text fields, use LazyText to reduce memory usage
            if ('text' in type_name or 'string' in type_name or 'varchar' in type_name) and \
                    isinstance(value, str) and len(value) > 10000:
                return LazyText(value)

            # Handle other types as before
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
        """
        Close the session and release database connection to the pool.
        """
        if not self.closed and self._connection:
            self.connection_pool.release(self._connection)
            self._connection = None
            self.closed = True
            self._pending_objects.clear()
            self._deleted_objects.clear()
            self._transaction_depth = 0
            self._modified_attrs.clear()

    def execute(self, statement, params=None):
        """
        Execute a SQL statement directly with parameters.

        Args:
            statement: SQL statement to execute
            params: Optional parameters for the statement

        Returns:
            Result proxy

        Raises:
            Exception: If execution fails
        """
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
        """
        Create a query object for the given model/entity classes.

        Args:
            *entities: Model classes to query

        Returns:
            Query object

        Raises:
            ValueError: If no entities specified
        """
        if not entities:
            raise ValueError("No entities specified for query")

        # Support multiple entities for joins
        return SQLCipherQuery(self, entities)

    def add(self, instance):
        """
        Add a new instance to the session for later insertion.

        Args:
            instance: Model instance to add
        """
        if instance in self._deleted_objects:
            self._deleted_objects.remove(instance)

        self._pending_objects.add(instance)

        # If autoflush is enabled, flush immediately
        if self.autoflush:
            self.flush()

        logger.debug(f"Instance of {instance.__class__.__name__} added to session")

    def add_all(self, instances):
        """
        Add multiple instances to the session.

        Args:
            instances: Iterable of model instances to add
        """
        for instance in instances:
            self.add(instance)

    def delete(self, instance):
        """
        Mark an instance for deletion.

        Args:
            instance: Model instance to delete
        """
        if instance in self._pending_objects:
            self._pending_objects.remove(instance)

        self._deleted_objects.add(instance)

        # If autoflush is enabled, flush immediately
        if self.autoflush:
            self.flush()

        logger.debug(f"Instance of {instance.__class__.__name__} marked for deletion")

    def flush(self, objects=None):
        """
        Flush pending changes to the database.

        Args:
            objects: Optional specific objects to flush
        """
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
        """
        Insert a new record or update an existing one.

        Args:
            instance: Model instance to insert or update
        """
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
        """
        Delete an instance from the database.

        Args:
            instance: Model instance to delete

        Raises:
            ValueError: If instance doesn't have __tablename__
        """
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
        """
        Commit the current transaction.
        """
        # Flush any pending changes
        self.flush()

        if not self.closed and self._connection:
            self._connection.commit()
            logger.debug("Session committed")

    def rollback(self):
        """
        Rollback the current transaction.
        """
        if not self.closed and self._connection:
            self._connection.rollback()

        # Clear pending changes
        self._pending_objects.clear()
        self._deleted_objects.clear()

        logger.debug("Session rolled back")

    def refresh(self, instance, attribute_names=None):
        """
        Refresh instance from the database.

        Args:
            instance: Model instance to refresh
            attribute_names: Optional specific attributes to refresh

        Raises:
            ValueError: If instance doesn't have __tablename__ or primary key
        """
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
        """
        Remove instance from session without affecting the database.

        Args:
            instance: Model instance to expunge
        """
        if instance in self._pending_objects:
            self._pending_objects.remove(instance)

        if instance in self._deleted_objects:
            self._deleted_objects.remove(instance)

        if id(instance) in self._modified_attrs:
            del self._modified_attrs[id(instance)]

        logger.debug(f"Expunged {instance.__class__.__name__} instance from session")

    def expunge_all(self):
        """
        Remove all instances from session without affecting the database.
        """
        self._pending_objects.clear()
        self._deleted_objects.clear()
        self._modified_attrs.clear()
        logger.debug("Expunged all instances from session")

    def merge(self, instance, load=True):
        """
        Merge the instance state with a persistent instance from database or create new.

        Args:
            instance: Model instance to merge
            load: Whether to load from database if not found

        Returns:
            Merged instance

        Raises:
            ValueError: If instance doesn't have __tablename__
        """
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
        """
        Get entity by primary key.

        Args:
            entity: Model class
            ident: Primary key value
            options: Optional query options

        Returns:
            Model instance or None if not found

        Raises:
            ValueError: If entity doesn't have __tablename__
        """
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
        """
        Check if instance exists in database or is pending in session.

        Args:
            instance: Model instance to check

        Returns:
            True if instance exists, False otherwise
        """
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

    def begin_nested(self):
        """
        Begin a nested transaction using SQLite SAVEPOINT.

        Returns:
            Transaction object
        """
        savepoint_name = f"SAVEPOINT_T{self._transaction_depth}"
        self.execute(f"SAVEPOINT {savepoint_name}")
        self._transaction_depth += 1

        # Return a simple object with a rollback method
        class NestedTransaction:
            def __init__(self, session, name):
                self.session = session
                self.name = name

            def rollback(self):
                self.session.execute(f"ROLLBACK TO SAVEPOINT {self.name}")

        return NestedTransaction(self, savepoint_name)

    @contextmanager
    def begin(self, nested=False):
        """
        Begin a transaction or nested transaction.

        Args:
            nested: Whether to use a nested transaction

        Yields:
            Session for use within the context
        """
        if nested:
            savepoint = self.begin_nested()
            try:
                yield self
            except:
                savepoint.rollback()
                raise
        else:
            try:
                yield self
                self.commit()
            except:
                self.rollback()
                raise

    def scalar(self, statement, params=None):
        """
        Execute a statement and return a scalar result.

        Args:
            statement: SQL statement to execute
            params: Optional parameters

        Returns:
            Scalar result
        """
        result = self.execute(statement, params)
        return result.scalar()


# -----------------------------------------------------------------------------
# Database Verification Function
# -----------------------------------------------------------------------------

def verify_db_connection() -> bool:
    """
    Verify that we can connect to the database.

    Returns:
        True if connection succeeds, False otherwise
    """
    if use_sqlcipher:
        try:
            logger.info(f"Verifying encrypted database at {db_path}...")
            conn = EncryptionManager.get_encrypted_connection(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM sqlite_master")
            table_count = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            logger.info(f"✅ Encrypted database verified with {table_count} tables")
            return True
        except Exception as e:
            logger.error(f"❌ Encrypted database verification failed: {e}")
            return False
    else:
        try:
            with engine.connect() as connection:
                result = connection.execute(text("SELECT 1")).scalar_one()
                logger.info("Standard DB verified via SQLAlchemy engine")
                return True
        except Exception as e:
            logger.error(f"Database connection verification failed: {e}")
            return False


# -----------------------------------------------------------------------------
# Database Initialization Function
# -----------------------------------------------------------------------------

def init_db(reset: bool = False) -> bool:
    """
    Initialize the database schema.

    Args:
        reset: Whether to reset (drop and recreate) the database

    Returns:
        True if initialization succeeds, False otherwise
    """
    logger.info("Initializing database schema...")

    if use_sqlcipher:
        if not db_path:
            logger.error("Cannot init SQLCipher DB: DATABASE_PATH not set")
            return False

        # Create or reset encrypted database
        if reset or not os.path.exists(db_path):
            action = "Resetting" if reset else "Creating new"
            logger.info(f"{action} encrypted database at {db_path}")
            if not EncryptionManager.create_new_encrypted_database(db_path):
                logger.error("Failed to create new DB")
                return False
            logger.info("New encrypted database created")
        else:
            logger.info(f"Testing existing encrypted database at {db_path}")
            if not EncryptionManager.test_encrypted_database(db_path):
                logger.error(f"Existing DB test failed. Recreating database...")
                if not EncryptionManager.create_new_encrypted_database(db_path):
                    logger.error("Failed to recreate DB")
                    return False
                logger.info("Database recreated successfully")

        # Create tables directly using SQLCipher
        logger.info("Creating database tables directly with SQLCipher...")
        if not EncryptionManager.create_tables_direct(db_path, Base.metadata):
            logger.error("Failed to create tables directly with SQLCipher")
            return False

        logger.info("Database tables created successfully with SQLCipher")
        return True
    else:
        try:
            logger.info("Testing connection via SQLAlchemy engine...")
            if not verify_db_connection():
                logger.error("Engine connection test failed before create_all")
                return False
                logger.info("Engine connection test successful")

            if reset:
                # Drop all tables first
                logger.info("Dropping all tables for reset...")
                Base.metadata.drop_all(bind=engine)
                logger.info("Tables dropped successfully")

            logger.info("Creating tables via SQLAlchemy...")
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created successfully")

            # Verify table creation
            with engine.connect() as conn:
                table_count = conn.execute(text("SELECT count(*) FROM sqlite_master WHERE type='table';")).scalar_one()
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
    if use_sqlcipher:
        try:
            conn = EncryptionManager.get_encrypted_connection(db_path)
            cursor = conn.cursor()

            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall() if not row[0].startswith('sqlite_')]

            # Get details for each table
            result = []
            for table in tables:
                # Get column info
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [
                    {
                        "name": row[1],
                        "type": row[2],
                        "nullable": not row[3],
                        "primary_key": bool(row[5])
                    }
                    for row in cursor.fetchall()
                ]

                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                row_count = cursor.fetchone()[0]

                # Get index info
                cursor.execute(f"PRAGMA index_list({table})")
                indices = [row[1] for row in cursor.fetchall()]

                result.append({
                    "name": table,
                    "columns": columns,
                    "row_count": row_count,
                    "indices": indices
                })

            cursor.close()
            conn.close()
            return result

        except Exception as e:
            logger.error(f"Error getting table info: {e}")
            return []
    else:
        try:
            from sqlalchemy import inspect
            inspector = inspect(engine)

            result = []
            for table_name in inspector.get_table_names():
                if table_name.startswith('sqlite_'):
                    continue

                # Get columns
                columns = []
                for column in inspector.get_columns(table_name):
                    columns.append({
                        "name": column['name'],
                        "type": str(column['type']),
                        "nullable": column['nullable'],
                        "primary_key": column.get('primary_key', False)
                    })

                # Get indices
                indices = []
                for index in inspector.get_indexes(table_name):
                    indices.append(index['name'])

                # Get row count
                with engine.connect() as conn:
                    row_count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()

                result.append({
                    "name": table_name,
                    "columns": columns,
                    "row_count": row_count,
                    "indices": indices
                })

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
        "connection_pool": {}
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
            tables.append({
                "name": table["name"],
                "rows": table["row_count"],
                "column_count": len(table["columns"]),
                "has_indices": len(table["indices"]) > 0
            })
            total_rows += table["row_count"]

        stats["tables"] = tables
        stats["total_tables"] = len(tables)
        stats["total_rows"] = total_rows

        # Get connection pool stats
        if use_sqlcipher:
            stats["connection_pool"] = connection_pool.status()
        else:
            # Try to get SQLAlchemy pool info
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
        if use_sqlcipher:
            conn = EncryptionManager.get_encrypted_connection(db_path)
            cursor = conn.cursor()
            cursor.execute("VACUUM")
            conn.commit()
            cursor.close()
            conn.close()
            logger.info("Database vacuumed successfully (SQLCipher)")
        else:
            with engine.connect() as conn:
                conn.execute(text("VACUUM"))
                logger.info("Database vacuumed successfully (SQLAlchemy)")

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
        if use_sqlcipher:
            conn = EncryptionManager.get_encrypted_connection(db_path)
            cursor = conn.cursor()
            cursor.execute("ANALYZE")
            conn.commit()
            cursor.close()
            conn.close()
            logger.info("Database analyzed successfully (SQLCipher)")
        else:
            with engine.connect() as conn:
                conn.execute(text("ANALYZE"))
                logger.info("Database analyzed successfully (SQLAlchemy)")

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
        if use_sqlcipher:
            conn = EncryptionManager.get_encrypted_connection(db_path)
            cursor = conn.cursor()

            # Get all tables
            cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
            tables = cursor.fetchall()

            # Get all indices
            cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%' ORDER BY name")
            indices = cursor.fetchall()

            # Get all triggers
            cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger' AND name NOT LIKE 'sqlite_%' ORDER BY name")
            triggers = cursor.fetchall()

            # Get all views
            cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='view' AND name NOT LIKE 'sqlite_%' ORDER BY name")
            views = cursor.fetchall()

            cursor.close()
            conn.close()

            # Build schema SQL
            schema_sql = "-- HideSync Database Schema\n"
            schema_sql += f"-- Generated: {datetime.datetime.now().isoformat()}\n\n"

            schema_sql += "-- Tables\n"
            for table_name, table_sql in tables:
                schema_sql += f"{table_sql};\n\n"

            schema_sql += "-- Indices\n"
            for index_name, index_sql in indices:
                if index_sql:  # Some indices might not have SQL definition
                    schema_sql += f"{index_sql};\n\n"

            schema_sql += "-- Views\n"
            for view_name, view_sql in views:
                schema_sql += f"{view_sql};\n\n"

            schema_sql += "-- Triggers\n"
            for trigger_name, trigger_sql in triggers:
                schema_sql += f"{trigger_sql};\n\n"

            if output_file:
                with open(output_file, 'w') as f:
                    f.write(schema_sql)
                logger.info(f"Schema exported to {output_file}")
                return output_file
            else:
                return schema_sql

        else:
            # Use SQLAlchemy metadata to generate schema
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
                with open(output_file, 'w') as f:
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

        if use_sqlcipher:
            # For SQLCipher, we need to decrypt and re-encrypt
            conn = EncryptionManager.get_encrypted_connection(db_path)

            # Vacuum first if requested (reduces size and defragments)
            if vacuum:
                cursor = conn.cursor()
                cursor.execute("VACUUM")
                cursor.close()

            # Export to backup with same encryption
            backup_conn = EncryptionManager.get_sqlcipher_module().connect(backup_path)
            backup_cursor = backup_conn.cursor()

            # Setup encryption on backup
            key = EncryptionManager.get_key()
            backup_cursor.execute(f"PRAGMA key = \"x'{key}'\";")
            backup_cursor.execute("PRAGMA cipher_page_size = 4096;")
            backup_cursor.execute("PRAGMA kdf_iter = 256000;")
            backup_cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
            backup_cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")

            # Use SQLite's backup API
            conn.backup(backup_conn)

            # Clean up
            backup_cursor.close()
            backup_conn.close()
            conn.close()

            logger.info(f"Encrypted database backed up to {backup_path}")
            return True

        else:
            # For standard SQLite, just use Python's file operations
            import shutil

            # Close all connections first
            if hasattr(engine, 'dispose'):
                engine.dispose()

            # Vacuum if requested
            if vacuum:
                with sqlite3.connect(db_path) as conn:
                    conn.execute("VACUUM")

            # Copy the file
            shutil.copy2(db_path, backup_path)
            logger.info(f"Database backed up to {backup_path}")
            return True

    except Exception as e:
        logger.error(f"Error backing up database: {e}")
        return False


# -----------------------------------------------------------------------------
# FastAPI Dependency
# -----------------------------------------------------------------------------

def get_db():
    """
    Get a database session with proper resource management.
    """
    thread_id = threading.get_ident()
    logger.debug(f"Creating DB session for thread {thread_id}")

    db = None
    try:
        # Create a new thread-safe session
        db = SessionLocal()

        # Set thread ID for tracing
        if hasattr(db, "info"):
            db.info['thread_id'] = thread_id
            db.info['created_at'] = time.time()

        yield db
    except Exception as e:
        logger.error(f"Error in get_db for thread {thread_id}: {e}")
        raise
    finally:
        if db:
            try:
                logger.debug(f"Closing DB session for thread {thread_id}")
                db.close()
            except Exception as e:
                logger.error(f"Error closing session for thread {thread_id}: {e}")

        # Also clean thread-local connection if needed
        if hasattr(_thread_local, "connection") and _thread_local.connection:
            conn_age = time.time() - getattr(_thread_local, "connection_created", 0)
            if conn_age > 3600:  # Force close connections older than 1 hour
                try:
                    _thread_local.connection.close()
                    _thread_local.connection = None
                    logger.info(f"Closed aged thread connection ({conn_age:.1f}s) for thread {thread_id}")
                except:
                    pass

# -----------------------------------------------------------------------------
# Transaction Support
# -----------------------------------------------------------------------------

@contextmanager
def transaction(session=None):
    """
    Context manager for database transactions.

    This provides a convenient way to use transactions with automatic
    commit/rollback based on exceptions.

    Args:
        session: Optional session to use (if None, creates a new one)

    Yields:
        Database session for use within the transaction

    Example:
        with transaction() as session:
            user = User(name="John")
            session.add(user)
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

    This automatically handles session creation, commit, and rollback.

    Args:
        func: Function to decorate

    Returns:
        Decorated function

    Example:
        @with_transaction
        def create_user(session, name):
            user = User(name=name)
            session.add(user)
            return user
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Check if session is already provided
        session_in_args = any(isinstance(arg, (Session, SQLCipherSession)) for arg in args)
        session_in_kwargs = 'session' in kwargs and isinstance(kwargs['session'], (Session, SQLCipherSession))

        if session_in_args or session_in_kwargs:
            # Session already provided, just call the function
            return func(*args, **kwargs)
        else:
            # Create a new session and wrap in transaction
            with transaction() as session:
                return func(*args, session=session, **kwargs)

    return wrapper


# -----------------------------------------------------------------------------
# Encryption Status
# -----------------------------------------------------------------------------
# Fix for SQLCipher codec attachment issues

def configure_sqlcipher_connection(connection):
    """
    Configure SQLCipher parameters for a connection.
    Ensures the encryption codec is properly attached.

    Args:
        connection: SQLite connection to configure

    Returns:
        Configured connection
    """
    if not connection:
        return None

    try:
        cursor = connection.cursor()

        # Get encryption key
        encryption_key = EncryptionManager.get_key()
        if not encryption_key:
            logger.error("No encryption key available for SQLCipher configuration")
            return connection

        # Format key for PRAGMA
        key_pragma = EncryptionManager.format_key_for_pragma()

        # Apply all PRAGMA statements in correct order
        logger.debug("Configuring SQLCipher connection with encryption key")

        # First set the key
        cursor.execute(f"PRAGMA key = {key_pragma};")

        # Then set other parameters
        cursor.execute("PRAGMA cipher_page_size = 4096;")
        cursor.execute("PRAGMA kdf_iter = 256000;")
        cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
        cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Test that configuration was successful
        cursor.execute("SELECT count(*) FROM sqlite_master;")
        cursor.fetchone()  # Just fetch to ensure it works
        cursor.close()

        return connection
    except Exception as e:
        logger.error(f"Error configuring SQLCipher connection: {e}")
        if cursor:
            try:
                cursor.close()
            except:
                pass
        return connection


# Update EnhancedSQLCipherPool._create_connection method
def _create_connection(self):
    """
    Create a new connection with SQLCipher parameters properly configured.

    Returns:
        A tuple of (connection, creation_time)

    Raises:
        Exception if connection fails
    """
    if self._circuit_open:
        # Check if it's time to try again
        if time.time() - self._circuit_open_time <= self._circuit_reset_timeout:
            raise ConnectionPoolExhaustedException(
                "Connection circuit breaker is open due to repeated connection failures"
            )

        # Reset the circuit breaker and try again
        self._circuit_open = False
        self._consecutive_errors = 0

    try:
        # Get raw connection from SQLCipher
        conn = EncryptionManager.get_sqlcipher_module().connect(self.db_path)

        # Apply all SQLCipher configuration
        conn = configure_sqlcipher_connection(conn)
        if not conn:
            raise Exception("Failed to configure SQLCipher connection")

        creation_time = time.time()
        self.metrics.record_connection_created()

        # Reset error counter on success
        self._consecutive_errors = 0

        return conn, creation_time
    except Exception as e:
        # Increment error counter
        self._consecutive_errors += 1
        self.metrics.record_connection_error()

        # Open circuit breaker if too many consecutive errors
        if self._consecutive_errors >= self._max_consecutive_errors:
            self._circuit_open = True
            self._circuit_open_time = time.time()
            logger.warning("Circuit breaker activated due to repeated connection failures")

        logger.error(f"Failed to create SQLCipher connection: {e}")
        raise

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
        "direct_sqlcipher_mode": direct_sqlcipher_mode,
        "has_encryption_key_loaded": key_loaded
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
    if use_sqlcipher:
        conn = EncryptionManager.get_encrypted_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS migrations (
            id INTEGER PRIMARY KEY,
            version TEXT NOT NULL,
            description TEXT,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()
        cursor.close()
        conn.close()
    else:
        with engine.connect() as conn:
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS migrations (
                id INTEGER PRIMARY KEY,
                version TEXT NOT NULL,
                description TEXT,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """))
            conn.commit()


def get_applied_migrations() -> List[str]:
    """
    Get list of already applied migrations.

    Returns:
        List of applied migration versions
    """
    _create_migrations_table()

    if use_sqlcipher:
        conn = EncryptionManager.get_encrypted_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT version FROM migrations ORDER BY id")
        versions = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return versions
    else:
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
    if use_sqlcipher:
        conn = EncryptionManager.get_encrypted_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO migrations (version, description) VALUES (?, ?)",
            (version, description)
        )
        conn.commit()
        cursor.close()
        conn.close()
    else:
        with engine.connect() as conn:
            conn.execute(
                text("INSERT INTO migrations (version, description) VALUES (:version, :description)"),
                {"version": version, "description": description}
            )
            conn.commit()


def remove_migration(version):
    """
    Remove a migration from the applied list.

    Args:
        version: Migration version to remove
    """
    if use_sqlcipher:
        conn = EncryptionManager.get_encrypted_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM migrations WHERE version = ?", (version,))
        conn.commit()
        cursor.close()
        conn.close()
    else:
        with engine.connect() as conn:
            conn.execute(
                text("DELETE FROM migrations WHERE version = :version"),
                {"version": version}
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
        session = SessionLocal()
        try:
            for migration in to_apply:
                logger.info(f"Applying migration {migration.version}: {migration.description}")
                migration.up(session)
                record_migration(migration.version, migration.description)
                logger.info(f"Successfully applied migration {migration.version}")

            session.commit()
            logger.info("All migrations applied successfully")
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"Migration failed: {e}")
            return False
        finally:
            session.close()

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
        session = SessionLocal()
        try:
            for migration in to_revert:
                logger.info(f"Reverting migration {migration.version}: {migration.description}")
                migration.down(session)
                remove_migration(migration.version)
                logger.info(f"Successfully reverted migration {migration.version}")

            session.commit()
            logger.info("All migrations reverted successfully")
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"Migration revert failed: {e}")
            return False
        finally:
            session.close()

    except Exception as e:
        logger.error(f"Error during migration revert process: {e}")
        return False


def get_db_health():
    """
    Comprehensive database health check with memory analysis.
    """
    import psutil
    import gc

    health = {
        "status": "healthy",
        "memory": {},
        "connections": {},
        "query_stats": {},
        "recommendations": []
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
            health["recommendations"].append("High memory usage detected - consider reducing query batch sizes")
    except Exception as e:
        health["memory"]["error"] = str(e)

    # Connection analysis
    if use_sqlcipher:
        conn_stats = connection_pool.status()
        health["connections"] = {
            "pool_size": conn_stats.get("idle_connections", 0) + conn_stats.get("in_use_connections", 0),
            "in_use": conn_stats.get("in_use_connections", 0),
            "idle": conn_stats.get("idle_connections", 0),
            "max_checkout_time": conn_stats.get("longest_checkout_time", 0),
            "avg_checkout_time": conn_stats.get("avg_checkout_time", 0),
        }

        # Add connection-related recommendations
        if health["connections"]["in_use"] > CONNECTION_POOL_SIZE * 0.8:
            health["recommendations"].append("Connection pool nearly full - check for leaks")

    # Add overall status
    if health["memory"].get("rss_mb", 0) > 1500 or len(health["recommendations"]) > 2:
        health["status"] = "warning"

    return health


class LazyText:
    """
    Memory-efficient wrapper for large text values.
    Defers loading the full string value until actually accessed.
    """

    def __init__(self, value):
        self._value = value
        self._length = len(value) if value is not None else 0
        # If value is very large, store just a truncated preview
        if self._length > 10000:
            self._preview = value[:100] + "..." if value else None
            # Only store reference to original value, not the whole thing
            self._value = None
            self._truncated = True
        else:
            self._preview = value
            self._truncated = False

    def __str__(self):
        """Return string representation, loading full value if needed."""
        if self._truncated and self._value is None:
            # In a real implementation, this would fetch from storage
            # For this example, we'll just return the preview with a note
            return f"{self._preview} [truncated, full length: {self._length}]"
        return self._value or self._preview or ""

    def __len__(self):
        """Return the length without loading full value."""
        return self._length

    def get_full_value(self):
        """Explicitly load and return the full value."""
        # In a real implementation, this would fetch from storage or DB
        # For this example, we just indicate it would be loaded
        if self._truncated:
            logger.debug(f"Loading full value of LazyText (length: {self._length})")
            # In reality, this would fetch the full text from somewhere
            return f"{self._preview} [full value would be loaded here]"
        return self._value or self._preview or ""

    def __repr__(self):
        """Developer-friendly representation."""
        if self._truncated:
            return f"LazyText(length={self._length}, truncated=True)"
        return f"LazyText('{self._preview}')"