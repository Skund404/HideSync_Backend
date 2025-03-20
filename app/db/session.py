"""
Database session and connection management.

This module handles SQLAlchemy session creation and provides
support for SQLCipher encrypted databases when configured.
"""

import os
import logging
from typing import Generator, Any, Optional
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from sqlalchemy.engine import Engine
import sqlite3

from app.core.config import settings
from app.db.models.base import Base

# Configure logging
logger = logging.getLogger(__name__)

# For production environments, use the KeyManager
if settings.ENVIRONMENT == "production" or settings.PRODUCTION:
    from app.core.key_manager import KeyManager

    try:
        ENCRYPTION_KEY = KeyManager.get_database_encryption_key()
        logger.info("Successfully loaded database encryption key using KeyManager")
    except Exception as e:
        logger.error(f"Failed to load encryption key: {str(e)}")
        raise
else:
    # For development, use the key from settings
    ENCRYPTION_KEY = settings.DATABASE_ENCRYPTION_KEY
    logger.warning("Using development encryption key - NOT SECURE FOR PRODUCTION")

# Check if we should use SQLCipher for encrypted database
if settings.USE_SQLCIPHER:
    try:
        import sqlcipher3
        import pysqlcipher3.dbapi2 as sqlcipher

        SQLCIPHER_AVAILABLE = True
        logger.info(
            "SQLCipher libraries detected and will be used for database encryption"
        )
    except ImportError:
        logger.warning(
            "SQLCipher requested but libraries not found. Falling back to standard SQLite."
        )
        SQLCIPHER_AVAILABLE = False
        sqlcipher = None
else:
    SQLCIPHER_AVAILABLE = False
    sqlcipher = None
    logger.info("SQLCipher encryption disabled in settings")


def _get_sqlcipher_connection() -> Any:
    """
    Create a SQLCipher connection with encryption key.

    Returns:
        A SQLCipher database connection with encryption configured
    """
    if not (SQLCIPHER_AVAILABLE and settings.USE_SQLCIPHER):
        raise RuntimeError("SQLCipher is not available or not enabled")

    conn = sqlcipher.connect(settings.DATABASE_PATH, check_same_thread=False)
    cursor = conn.cursor()

    try:
        # Set the encryption key with advanced security settings
        cursor.execute(f"PRAGMA key = '{ENCRYPTION_KEY}'")
        cursor.execute("PRAGMA cipher_page_size = 4096")  # Optimize for performance
        cursor.execute("PRAGMA kdf_iter = 64000")  # Key derivation iterations
        cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512")  # More secure HMAC
        cursor.execute("PRAGMA foreign_keys = ON")  # Enable foreign key support
    except Exception as e:
        logger.error(f"Error configuring SQLCipher connection: {str(e)}")
        raise
    finally:
        cursor.close()

    return conn


# Monkey patch SQLAlchemy's sqlite dialect to prevent regexp function registration
# This needs to happen before engine creation
import sqlalchemy.dialects.sqlite.pysqlite as sa_sqlite

# Store the original on_connect function
original_on_connect = sa_sqlite.SQLiteDialect_pysqlite.on_connect


# Create a new on_connect function that does nothing (empty function)
def empty_on_connect(self):
    return None


# Replace SQLAlchemy's on_connect with our empty version
sa_sqlite.SQLiteDialect_pysqlite.on_connect = empty_on_connect


# Create the SQLAlchemy engine with robust error handling
if SQLCIPHER_AVAILABLE and settings.USE_SQLCIPHER:
    engine = create_engine(
        f"sqlite:///{settings.DATABASE_PATH}",
        module=sqlcipher,
        creator=_get_sqlcipher_connection,
        connect_args={"check_same_thread": False},
        poolclass=NullPool,  # Disable connection pooling
    )
    logger.info(f"Using SQLCipher encrypted database: {settings.DATABASE_PATH}")
else:
    # Standard SQLAlchemy engine for non-encrypted or fallback scenarios
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    logger.info(f"Using standard database connection: {settings.DATABASE_URL}")


# Set up foreign keys for SQLite connections
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign keys for SQLite connections."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# Create sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Database session dependency.

    Creates a new SQLAlchemy session for each request and closes it afterwards.

    Yields:
        Session: A SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize the database by creating all tables."""
    try:
        # Create database tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")

        # Additional verification for encrypted databases
        if SQLCIPHER_AVAILABLE and settings.USE_SQLCIPHER:
            try:
                conn = _get_sqlcipher_connection()
                cursor = conn.cursor()
                # Test query to verify encryption
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                logger.info(
                    f"Verified database encryption is working (found {len(tables)} tables)"
                )
                cursor.close()
                conn.close()
            except Exception as e:
                logger.error(f"Error verifying database encryption: {str(e)}")
                raise
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        raise
