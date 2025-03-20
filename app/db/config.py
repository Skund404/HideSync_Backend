# File: app/db/config.py
"""
Database configuration for the Leathercraft ERP system.

This module provides database connection configuration, including
support for encrypted databases with SQLCipher and database session
management for dependency injection.
"""

import os
import logging
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.db.models import Base

logger = logging.getLogger(__name__)


def get_db_url() -> str:
    """
    Get the database URL from settings.

    For SQLite databases, ensures proper URI handling.

    Returns:
        Database URL string
    """
    if settings.USE_SQLCIPHER:
        # SQLCipher is handled separately
        return None

    db_url = settings.DATABASE_URL

    # Ensure SQLite URLs use proper URI format
    if db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite:///")

    return db_url


def create_secure_engine():
    """
    Create an encrypted database engine using SQLCipher.

    Returns:
        SQLAlchemy engine configured with SQLCipher
    """
    try:
        import sqlcipher3.dbapi2 as sqlcipher
    except ImportError:
        logger.error("SQLCipher support requires sqlcipher3 and pysqlcipher3 packages.")
        raise

    # Function to create connections with encryption key
    def _connect_with_key():
        conn = sqlcipher.connect(settings.DATABASE_PATH)
        cursor = conn.cursor()

        # Apply encryption key and settings
        cursor.execute(f"PRAGMA key = '{settings.DATABASE_ENCRYPTION_KEY}'")
        cursor.execute("PRAGMA cipher_page_size = 4096")
        cursor.execute("PRAGMA kdf_iter = 64000")
        cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512")
        cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512")

        cursor.close()
        return conn

    # Create the engine with our custom connection function
    engine = create_engine(
        "sqlite://",  # In-memory is replaced by connection function
        creator=_connect_with_key,
        connect_args={"check_same_thread": False},
        poolclass=NullPool,  # Disable connection pooling for SQLCipher
    )

    return engine


def get_engine():
    """
    Get the appropriate database engine based on configuration.

    Returns:
        SQLAlchemy engine
    """
    if settings.USE_SQLCIPHER:
        logger.info("Using SQLCipher encrypted database.")
        return create_secure_engine()
    else:
        logger.info(f"Using standard database: {get_db_url()}")
        return create_engine(
            get_db_url(),
            pool_pre_ping=True,
            connect_args=(
                {"check_same_thread": False}
                if get_db_url().startswith("sqlite")
                else {}
            ),
        )


# Create engine and session factory
engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables():
    """
    Create database tables if they don't exist.

    This is typically used for initial database setup or testing.
    For production, use Alembic migrations instead.
    """
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Get a database session.

    This function is used as a dependency in FastAPI endpoints.

    Yields:
        SQLAlchemy session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.

    This can be used in scripts or background tasks.

    Yields:
        SQLAlchemy session
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def initialize_db(drop_all: bool = False):
    """
    Initialize the database, optionally dropping all tables first.

    Args:
        drop_all: Whether to drop all tables before creating them
    """
    if drop_all:
        logger.warning("Dropping all database tables!")
        Base.metadata.drop_all(bind=engine)

    logger.info("Creating database tables...")
    create_tables()
    logger.info("Database tables created successfully.")


def get_connection_info() -> dict:
    """
    Get database connection information for diagnostics.

    Returns:
        Dictionary with connection information
    """
    return {
        "engine": str(engine.url),
        "using_sqlcipher": settings.USE_SQLCIPHER,
        "driver": engine.driver,
        "dialect": engine.dialect.name,
    }
