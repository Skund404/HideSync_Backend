#!/usr/bin/env python
"""
Robust HideSync Database Setup Script

This script handles database initialization without using direct SQL commands,
avoiding encryption parameter mismatches that cause HMAC errors.
"""

import os
import sys
import logging
import argparse
from pathlib import Path

# Add project root to Python path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent if script_dir.name == "scripts" else script_dir
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Set up the HideSync database.")
    parser.add_argument("--reset", action="store_true", help="Reset the database")
    parser.add_argument("--seed", action="store_true", help="Seed the database with initial data")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    return parser.parse_args()


def verify_database_schema():
    """Verify database schema has all required tables."""
    from app.db.session import SessionLocal
    from sqlalchemy import inspect, text

    db = SessionLocal()
    try:
        # Get database inspector
        inspector = inspect(db.bind)

        # Get all tables
        tables = inspector.get_table_names()
        logger.info(f"Found {len(tables)} tables in database")

        # Check for critical tables
        critical_tables = [
            'entity_media', 'media_assets', 'media_asset_tags', 'suppliers'
        ]

        missing_tables = [table for table in critical_tables if table not in tables]

        if missing_tables:
            logger.warning(f"Missing critical tables: {', '.join(missing_tables)}")
            return False
        else:
            logger.info("All critical tables are present")

            # Check for entity_media specifically
            if 'entity_media' in tables:
                # Get column info
                columns = inspector.get_columns('entity_media')
                logger.info(f"entity_media table has {len(columns)} columns")

                # Verify through a query
                try:
                    result = db.execute(text("SELECT COUNT(*) FROM entity_media")).scalar()
                    logger.info(f"entity_media table query successful, contains {result} records")
                except Exception as e:
                    logger.error(f"Error querying entity_media table: {e}")
                    return False

            return True
    except Exception as e:
        logger.error(f"Error verifying database schema: {e}")
        return False
    finally:
        db.close()


def initialize_database():
    """Initialize the database schema using SQLAlchemy models."""
    from app.db.session import init_db

    logger.info("Initializing database schema...")
    success = init_db()

    if success:
        logger.info("Database schema initialized successfully")
    else:
        logger.error("Failed to initialize database schema")

    return success


def reset_database():
    """Reset the database by recreating it."""
    from app.core.config import settings
    from app.db.session import EncryptionManager

    db_path = os.path.abspath(settings.DATABASE_PATH)
    logger.info(f"Resetting database at {db_path}")

    # Delete existing database if it exists
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
            logger.info(f"Deleted existing database file: {db_path}")
        except Exception as e:
            logger.error(f"Error deleting database file: {e}")
            return False

    # Create empty encrypted database
    success = EncryptionManager.create_new_encrypted_database(db_path)
    if not success:
        logger.error("Failed to create empty encrypted database")
        return False

    logger.info("Empty database created successfully")
    return True


def seed_database():
    """Seed the database with initial data."""
    try:
        logger.info("Seeding database with initial data...")

        # Try to import seed module
        try:
            from app.db.seed import create_initial_roles, create_admin_user, seed_master_data

            # Create roles
            logger.info("Creating initial roles...")
            create_initial_roles()

            # Create admin user
            logger.info("Creating admin user...")
            admin_user = create_admin_user(
                email="admin@example.com",
                password="AdminPassword123!"
            )
            logger.info(f"Admin user created with ID: {admin_user.id}")

            # Seed master data
            logger.info("Seeding master data...")
            seed_master_data()

        except ImportError as e:
            logger.warning(f"Could not import seed module: {e}")
            logger.warning("Skipping database seeding")
            return False

        logger.info("Database seeding completed successfully")
        return True
    except Exception as e:
        logger.error(f"Error seeding database: {e}")
        return False


def main():
    """Main function to orchestrate database setup."""
    args = parse_arguments()

    # Set logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")

    if args.reset:
        if not reset_database():
            logger.error("Database reset failed, exiting.")
            sys.exit(1)

    # Always initialize the database schema
    if not initialize_database():
        logger.error("Database schema initialization failed, exiting.")
        sys.exit(1)

    # Always verify the schema
    if not verify_database_schema():
        logger.warning("Database schema verification found issues.")
        # Continue anyway, this is just for diagnostics

    # Seed the database if requested
    if args.seed:
        if not seed_database():
            logger.error("Database seeding failed, exiting.")
            sys.exit(1)

    logger.info("Database setup completed successfully")


if __name__ == "__main__":
    main()