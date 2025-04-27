#!/usr/bin/env python
"""
db_tools/create_db.py

Database Creation Script for HideSync
Creates an encrypted SQLCipher database with all models defined in the application.
"""

import os
import sys
import logging
from pathlib import Path
import traceback
import importlib

# Add project root to Python path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

try:
    import pysqlcipher3.dbapi2 as sqlcipher
    from sqlalchemy import create_engine, inspect
    from sqlalchemy.orm import sessionmaker, scoped_session
    from app.core.config import settings
    from app.core.key_manager import KeyManager
    from app.db.models.base import Base
except ImportError as e:
    logger.error(f"Error importing required modules: {e}")
    logger.error("Please ensure all dependencies are installed.")
    sys.exit(1)

# List of all model modules to import - derived from actual model files
MODEL_MODULES = [
    "app.db.models.annotation",
    "app.db.models.association_media",
    "app.db.models.associations",
    "app.db.models.base",
    "app.db.models.communication",
    "app.db.models.component",
    "app.db.models.customer",
    "app.db.models.documentation",
    "app.db.models.dynamic_enum",  # Add this
    "app.db.models.dynamic_material",  # Add this
    "app.db.models.entity_media",
    "app.db.models.enums",
    "app.db.models.file_metadata",
    "app.db.models.inventory",
    "app.db.models.material",
    "app.db.models.media_asset",
    "app.db.models.password_reset",
    "app.db.models.pattern",
    "app.db.models.picking_list",
    "app.db.models.platform_integration",
    "app.db.models.product",
    "app.db.models.project",
    "app.db.models.purchase",
    "app.db.models.recurring_project",
    "app.db.models.refund",
    "app.db.models.role",
    "app.db.models.sales",
    "app.db.models.settings",  # Add this
    "app.db.models.shipment",
    "app.db.models.storage",
    "app.db.models.supplier",
    "app.db.models.supplier_history",
    "app.db.models.supplier_rating",
    "app.db.models.tag",
    "app.db.models.timeline_task",
    "app.db.models.tool",
    "app.db.models.user",
]


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


def get_sqlalchemy_url(db_path, encryption_key):
    """Create SQLAlchemy URL for SQLCipher database."""
    # Format the connection string for SQLCipher with SQLAlchemy
    return f"sqlite:///{db_path}?cipher=sqlcipher&key={encryption_key}"


def import_all_models():
    """Import all model modules to register them with SQLAlchemy."""
    imported_modules = 0
    for module_name in MODEL_MODULES:
        try:
            importlib.import_module(module_name)
            imported_modules += 1
            logger.info(f"Imported model module: {module_name}")
        except ImportError as e:
            logger.warning(f"Failed to import model module {module_name}: {e}")
            logger.debug(traceback.format_exc())

    logger.info(
        f"Successfully imported {imported_modules} of {len(MODEL_MODULES)} model modules"
    )
    return imported_modules > 0


def create_database_with_sqlalchemy(db_path, encryption_key):
    """Create database and tables using SQLAlchemy."""
    try:
        # Import all models to ensure they're registered with Base.metadata
        import_all_models()

        # Create SQLAlchemy engine with SQLCipher connection
        engine = create_engine(
            get_sqlalchemy_url(db_path, encryption_key),
            connect_args={
                "check_same_thread": False,
                "cipher_page_size": 4096,
                "kdf_iter": 256000,
                "cipher_hmac_algorithm": "HMAC_SHA512",
                "cipher_kdf_algorithm": "PBKDF2_HMAC_SHA512",
            },
        )

        # Test connection
        with engine.connect() as conn:
            result = conn.execute("SELECT 1").scalar()
            if result != 1:
                raise Exception("Database connection test failed")

        # Create all tables
        Base.metadata.create_all(engine)

        # Log created tables
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        logger.info(f"Created {len(table_names)} tables")
        for table in sorted(table_names):
            logger.info(f"  - {table}")

        return True
    except Exception as e:
        logger.error(f"Error creating database with SQLAlchemy: {e}")
        logger.error(traceback.format_exc())
        return False


def create_database_with_raw_sql(db_path, encryption_key):
    """
    Create database using raw SQL commands with SQLCipher.
    Used as a fallback if SQLAlchemy approach fails.
    """
    try:
        # Connect to the database
        conn = sqlcipher.connect(db_path)
        cursor = conn.cursor()

        # Configure encryption
        cursor.execute(f"PRAGMA key = \"x'{encryption_key}'\";")
        cursor.execute("PRAGMA cipher_page_size = 4096;")
        cursor.execute("PRAGMA kdf_iter = 256000;")
        cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
        cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Verify connection
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        if result[0] != 1:
            raise Exception("Database connection test failed")

        # Import all models
        import_all_models()

        # Get all table definitions from SQLAlchemy models
        from sqlalchemy import schema

        # Create tables based on SQLAlchemy models
        tables_created = 0
        failed_tables = []
        tables_dict = dict(Base.metadata.tables)

        # First create tables with no foreign keys
        for table_name, table in sorted(tables_dict.items()):
            if not table.foreign_keys:
                try:
                    create_stmt = schema.CreateTable(table).compile()
                    sql = str(create_stmt).replace("\n", " ")
                    cursor.execute(sql)
                    tables_created += 1
                    logger.info(f"Created table: {table_name}")
                except Exception as e:
                    failed_tables.append((table_name, str(e)))
                    logger.warning(f"Error creating table {table_name}: {e}")

        # Then create tables with foreign keys (multiple passes)
        remaining_tables = {
            name: table for name, table in tables_dict.items() if table.foreign_keys
        }
        max_passes = 5  # Avoid infinite loops with circular dependencies

        for i in range(max_passes):
            if not remaining_tables:
                break

            tables_in_this_pass = list(remaining_tables.items())
            tables_created_in_pass = 0

            for table_name, table in tables_in_this_pass:
                try:
                    create_stmt = schema.CreateTable(table).compile()
                    sql = str(create_stmt).replace("\n", " ")
                    cursor.execute(sql)
                    tables_created += 1
                    tables_created_in_pass += 1
                    del remaining_tables[table_name]
                    logger.info(f"Created table: {table_name}")
                except Exception as e:
                    # Keep it in remaining_tables for the next pass
                    if i == max_passes - 1:  # Last pass
                        failed_tables.append((table_name, str(e)))
                        logger.warning(f"Error creating table {table_name}: {e}")

            if tables_created_in_pass == 0:
                logger.warning(
                    f"No tables created in pass {i + 1}, aborting dependency resolution"
                )
                break

        # Log failed tables
        if failed_tables:
            logger.warning(f"Failed to create {len(failed_tables)} tables:")
            for table_name, error in failed_tables:
                logger.warning(f"  - {table_name}: {error}")

        # Commit and close
        conn.commit()
        conn.close()

        logger.info(f"Created {tables_created} tables using raw SQL")
        return tables_created > 0
    except Exception as e:
        logger.error(f"Error creating database with raw SQL: {e}")
        logger.error(traceback.format_exc())
        return False


def main():
    """Main function to create the database."""
    import argparse

    parser = argparse.ArgumentParser(description="Create HideSync database")
    parser.add_argument(
        "--force", action="store_true", help="Force creation even if database exists"
    )
    parser.add_argument(
        "--method",
        choices=["sqlalchemy", "raw", "auto"],
        default="auto",
        help="Method to create database (sqlalchemy, raw SQL, or auto-detect)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Get database path and ensure directory exists
    db_path = os.path.abspath(settings.DATABASE_PATH)
    db_dir = os.path.dirname(db_path)

    if not create_directory_if_not_exists(db_dir):
        logger.error(f"Could not create database directory: {db_dir}")
        return False

    # Check if database already exists
    if os.path.exists(db_path):
        if args.force:
            try:
                os.remove(db_path)
                logger.info(f"Deleted existing database file: {db_path}")
            except Exception as e:
                logger.error(f"Error deleting existing database file: {e}")
                return False
        else:
            logger.warning(f"Database already exists at {db_path}")
            logger.warning("Use --force to overwrite the existing database")
            return False

    # Get encryption key
    encryption_key = KeyManager.get_database_encryption_key()
    if not encryption_key:
        logger.error("Failed to get database encryption key")
        return False

    # Create the database using the specified method
    if args.method == "sqlalchemy" or args.method == "auto":
        logger.info("Creating database using SQLAlchemy...")
        if create_database_with_sqlalchemy(db_path, encryption_key):
            logger.info(f"Database created successfully with SQLAlchemy at {db_path}")
            return True

        if args.method == "auto":
            logger.warning("SQLAlchemy method failed, falling back to raw SQL...")
        else:
            logger.error("SQLAlchemy method failed")
            return False

    if args.method == "raw" or args.method == "auto":
        logger.info("Creating database using raw SQL...")
        if create_database_with_raw_sql(db_path, encryption_key):
            logger.info(f"Database created successfully with raw SQL at {db_path}")
            return True
        else:
            logger.error("Raw SQL method failed")
            return False

    return False


if __name__ == "__main__":
    if main():
        sys.exit(0)
    else:
        sys.exit(1)
