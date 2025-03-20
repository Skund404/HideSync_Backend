# File: app/db/session.py
"""
Database session and connection management.

This module handles SQLAlchemy session creation and provides
support for SQLCipher encrypted databases when configured.
"""

import os
import logging
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

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
        logger.info("SQLCipher libraries detected and will be used for database encryption")
    except ImportError:
        logger.warning("SQLCipher requested but libraries not found. Falling back to standard SQLite.")
        SQLCIPHER_AVAILABLE = False
else:
    SQLCIPHER_AVAILABLE = False
    logger.info("SQLCipher encryption disabled in settings")

# Create the SQLAlchemy engine
if SQLCIPHER_AVAILABLE and settings.USE_SQLCIPHER:
    # Define a connection factory for SQLCipher
    def _get_sqlcipher_connection():
        """Create a SQLCipher connection with encryption key."""
        conn = sqlcipher.connect(settings.DATABASE_PATH)
        cursor = conn.cursor()
        # Set the encryption key
        cursor.execute(f"PRAGMA key = '{ENCRYPTION_KEY}'")
        # Configure additional SQLCipher settings for performance/security
        cursor.execute("PRAGMA cipher_page_size = 4096")  # Optimize for performance
        cursor.execute("PRAGMA kdf_iter = 64000")  # Key derivation iterations
        cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512")  # More secure HMAC
        cursor.close()
        return conn


    # Create SQLAlchemy engine with SQLCipher support
    engine = create_engine(
        f"sqlite:///{settings.DATABASE_PATH}",
        module=sqlcipher,
        creator=_get_sqlcipher_connection,
        connect_args={"check_same_thread": False}  # Only for SQLite
    )
    logger.info(f"Using SQLCipher encrypted database: {settings.DATABASE_PATH}")
else:
    # Standard SQLAlchemy engine
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False} if "sqlite" in str(settings.DATABASE_URL) else {}
    )
    logger.info(f"Using standard database connection: {settings.DATABASE_URL}")

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
    # Create database tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")

    # Check if database is encrypted (SQLCipher only)
    if SQLCIPHER_AVAILABLE and settings.USE_SQLCIPHER:
        try:
            conn = _get_sqlcipher_connection()
            cursor = conn.cursor()
            # Test query to verify encryption
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            logger.info(f"Verified database encryption is working (found {len(tables)} tables)")
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error verifying database encryption: {str(e)}")
            raise