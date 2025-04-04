#!/usr/bin/env python
"""
db_tools/create_db.py

Database Creation Script for HideSync
Creates an encrypted SQLCipher database with the necessary schema.
"""

import os
import sys
import logging
from pathlib import Path
import json

# Add project root to Python path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

try:
    import pysqlcipher3.dbapi2 as sqlcipher
    from app.core.config import settings
    from app.core.key_manager import KeyManager
except ImportError as e:
    logger.error(f"Error importing required modules: {e}")
    logger.error("Please ensure all dependencies are installed.")
    sys.exit(1)

# SQL statements for media system tables and other core tables that might not be in SQLAlchemy models
MEDIA_SYSTEM_TABLE_STATEMENTS = {
    'media_assets': """
    CREATE TABLE IF NOT EXISTS media_assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        file_path TEXT NOT NULL,
        file_size INTEGER,
        file_type TEXT,
        mime_type TEXT,
        width INTEGER,
        height INTEGER,
        duration INTEGER,
        title TEXT,
        description TEXT,
        alt_text TEXT,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP,
        uuid TEXT,
        is_public BOOLEAN DEFAULT FALSE,
        status TEXT DEFAULT 'active',
        metadata TEXT
    );
    """,
    'entity_media': """
    CREATE TABLE IF NOT EXISTS entity_media (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        media_asset_id INTEGER NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id INTEGER NOT NULL,
        media_type TEXT,
        display_order INTEGER DEFAULT 0,
        caption TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        uuid TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        updated_at TIMESTAMP,
        FOREIGN KEY (media_asset_id) REFERENCES media_assets(id) ON DELETE CASCADE
    );
    """,
    'media_tags': """
    CREATE TABLE IF NOT EXISTS media_tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        slug TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP
    );
    """,
    'media_asset_tags': """
    CREATE TABLE IF NOT EXISTS media_asset_tags (
        media_asset_id INTEGER NOT NULL,
        tag_id INTEGER NOT NULL,
        PRIMARY KEY (media_asset_id, tag_id),
        FOREIGN KEY (media_asset_id) REFERENCES media_assets(id) ON DELETE CASCADE,
        FOREIGN KEY (tag_id) REFERENCES media_tags(id) ON DELETE CASCADE
    );
    """
}

# Core tables definitions - these are the minimal tables needed for the application to function
CORE_TABLE_STATEMENTS = {
    'users': """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        username TEXT,
        hashed_password TEXT NOT NULL,
        full_name TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        is_superuser BOOLEAN DEFAULT FALSE,
        last_login TIMESTAMP,
        change_history TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP
    );
    """,
    'roles': """
    CREATE TABLE IF NOT EXISTS roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT,
        is_system_role BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP
    );
    """,
    'permissions': """
    CREATE TABLE IF NOT EXISTS permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        description TEXT,
        resource TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP
    );
    """,
    'user_roles': """
    CREATE TABLE IF NOT EXISTS user_roles (
        user_id INTEGER NOT NULL,
        role_id INTEGER NOT NULL,
        PRIMARY KEY (user_id, role_id),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
    );
    """,
    'role_permissions': """
    CREATE TABLE IF NOT EXISTS role_permissions (
        role_id INTEGER NOT NULL,
        permission_id INTEGER NOT NULL,
        PRIMARY KEY (role_id, permission_id),
        FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
        FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
    );
    """
}


def create_directory_if_not_exists(directory_path):
    """Create a directory if it doesn't exist."""
    try:
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)
            logger.info(f"Created directory: {directory_path}")
        return True
    except Exception as e:
        logger.error(f"Error creating directory {directory_path}: {e}")
        return False


def create_database():
    """Create a new SQLCipher database with encryption."""
    try:
        # Get database path from settings
        db_path = os.path.abspath(settings.DATABASE_PATH)
        db_dir = os.path.dirname(db_path)

        # Ensure the database directory exists
        if not create_directory_if_not_exists(db_dir):
            return False

        # Delete existing database if it exists
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
                logger.info(f"Deleted existing database file: {db_path}")
            except Exception as e:
                logger.error(f"Error deleting existing database file: {e}")
                return False

        # Get encryption key
        key = KeyManager.get_database_encryption_key()
        if not key:
            logger.error("Failed to get database encryption key")
            return False

        # Create a new encrypted database
        conn = sqlcipher.connect(db_path)
        cursor = conn.cursor()

        # Configure encryption with hex key approach
        cursor.execute(f"PRAGMA key = \"x'{key}'\";")
        cursor.execute("PRAGMA cipher_page_size = 4096;")
        cursor.execute("PRAGMA kdf_iter = 256000;")
        cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
        cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Verify connection
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        if result and result[0] == 1:
            logger.info("Database connection verified")
        else:
            logger.error("Failed to verify database connection")
            return False

        # Create core tables
        for table_name, sql in CORE_TABLE_STATEMENTS.items():
            try:
                cursor.execute(sql)
                logger.info(f"Created table: {table_name}")
            except Exception as e:
                logger.error(f"Error creating table {table_name}: {e}")
                conn.rollback()
                conn.close()
                return False

        # Create media system tables
        for table_name, sql in MEDIA_SYSTEM_TABLE_STATEMENTS.items():
            try:
                cursor.execute(sql)
                logger.info(f"Created table: {table_name}")
            except Exception as e:
                logger.error(f"Error creating table {table_name}: {e}")
                conn.rollback()
                conn.close()
                return False

        # Commit changes and close connection
        conn.commit()
        conn.close()

        logger.info(f"Database created successfully at {db_path}")
        return True

    except Exception as e:
        logger.error(f"Error creating database: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def import_sqlalchemy_models():
    """
    Import SQLAlchemy models and create tables.
    Uses direct connection to SQLCipher database.
    """
    try:
        # Get database path and encryption key
        db_path = os.path.abspath(settings.DATABASE_PATH)
        key = KeyManager.get_database_encryption_key()

        # Connect to the database
        conn = sqlcipher.connect(db_path)
        cursor = conn.cursor()

        # Configure encryption
        cursor.execute(f"PRAGMA key = \"x'{key}'\";")
        cursor.execute("PRAGMA cipher_page_size = 4096;")
        cursor.execute("PRAGMA kdf_iter = 256000;")
        cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
        cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Import SQLAlchemy models (without creating tables yet)
        try:
            from app.db.models.base import Base
            from app.db import models
        except ImportError as e:
            logger.error(f"Error importing models: {e}")
            return False

        # Get all table definitions from SQLAlchemy models
        from sqlalchemy import schema

        # Create tables based on SQLAlchemy models
        tables_created = 0
        for table_name, table in Base.metadata.tables.items():
            try:
                # Convert SQLAlchemy table definition to SQL statement
                create_stmt = schema.CreateTable(table).compile()
                sql = str(create_stmt).replace("\n", " ")

                # Execute the create table statement
                cursor.execute(f"CREATE TABLE IF NOT EXISTS {sql};")
                tables_created += 1
                logger.info(f"Created table from SQLAlchemy model: {table_name}")
            except Exception as e:
                logger.warning(f"Could not create table {table_name}: {e}")
                # Continue with other tables, don't fail

        # Commit changes and close connection
        conn.commit()
        conn.close()

        logger.info(f"Created {tables_created} tables from SQLAlchemy models")
        return True

    except Exception as e:
        logger.error(f"Error importing SQLAlchemy models: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def create_minimal_database():
    """Create a minimal database for testing purposes."""
    try:
        # Attempt to use SQLAlchemy models
        try:
            # Try importing the app.db.session to use the built-in initialization
            from app.db.session import init_db

            # If successful, use the application's init_db function
            logger.info("Using application's init_db function for schema creation")
            success = init_db()

            if success:
                logger.info("Database schema initialized successfully using init_db")
                return True
            else:
                logger.warning("init_db failed, falling back to direct table creation")
        except ImportError:
            logger.warning("Could not import init_db, falling back to direct table creation")

        # Create the database file with encryption
        if not create_database():
            logger.error("Failed to create database")
            return False

        # Attempt to import and create SQLAlchemy models
        try:
            import_sqlalchemy_models()
        except Exception as e:
            logger.warning(f"Error importing SQLAlchemy models: {e}")
            logger.info("Continuing with minimal database tables")

        logger.info("Minimal database created successfully")
        return True

    except Exception as e:
        logger.error(f"Error creating minimal database: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    """Main function to create the database."""
    import argparse

    parser = argparse.ArgumentParser(description="Create HideSync database")
    parser.add_argument("--minimal", action="store_true", help="Create minimal database with core tables only")
    parser.add_argument("--force", action="store_true", help="Force creation even if database exists")

    args = parser.parse_args()

    # Check if database already exists
    db_path = os.path.abspath(settings.DATABASE_PATH)
    if os.path.exists(db_path) and not args.force:
        logger.warning(f"Database already exists at {db_path}")
        logger.warning("Use --force to overwrite the existing database")
        return False

    if args.minimal:
        logger.info("Creating minimal database...")
        if create_minimal_database():
            logger.info("Minimal database created successfully")
            return True
        else:
            logger.error("Failed to create minimal database")
            return False
    else:
        logger.info("Creating full database...")
        # Create empty encrypted database
        if not create_database():
            logger.error("Failed to create the encrypted database")
            return False

        # Create SQLAlchemy model tables
        try:
            # Try to use the app's built-in initialization
            from app.db.session import init_db

            logger.info("Creating tables from SQLAlchemy models")
            if not init_db():
                logger.error("Failed to initialize database schema")
                return False

            logger.info("Database schema initialized successfully")
            return True
        except ImportError:
            logger.warning("Could not import init_db, trying direct SQLAlchemy model import")

            # Fall back to direct import of SQLAlchemy models
            if not import_sqlalchemy_models():
                logger.error("Failed to create tables from SQLAlchemy models")
                return False

            logger.info("Database created successfully")
            return True


if __name__ == "__main__":
    if main():
        sys.exit(0)
    else:
        sys.exit(1)