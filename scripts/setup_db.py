# File: scripts/setup_db.py
"""
Command-line script to set up the database.

This script initializes the database, creates all tables, and optionally
seeds the database with initial data. It should be run once before starting the application.
"""

import sys
import os
import logging
import json
import argparse
from pathlib import Path

# Add the parent directory to Python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Import with environment variable safety
os.environ.setdefault("ENVIRONMENT", "development")

from app.db.init_db import init_db
from app.core.config import settings
from app.db.session import engine, ENCRYPTION_KEY
from app.db.models.base import Base

# Import the seed function separately to avoid circular imports
from app.db.seed_db import seed_database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Set up the database with tables and optional seed data."""
    # Create argument parser
    parser = argparse.ArgumentParser(description="Set up the HideSync database.")
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Seed the database with initial data"
    )
    parser.add_argument(
        "--seed-file",
        type=str,
        default="./app/db/seed_data.json",
        help="Path to the seed data JSON file"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset the database before initialization (will drop all tables)"
    )

    args = parser.parse_args()

    # Display encryption status
    if settings.USE_SQLCIPHER:
        logger.info("Using SQLCipher encrypted database")
    else:
        logger.info("Using standard SQLite database")

    # Reset database if requested
    if args.reset:
        logger.info("Dropping all database tables...")
        try:
            Base.metadata.drop_all(bind=engine)
            logger.info("All tables dropped successfully")
        except Exception as e:
            logger.error(f"Error dropping tables: {str(e)}")
            sys.exit(1)

    # Initialize database
    logger.info("Setting up the database...")
    try:
        init_db()
        logger.info("Database setup completed successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        sys.exit(1)

    # Seed database if requested
    if args.seed:
        seed_file = args.seed_file
        if not os.path.exists(seed_file):
            logger.error(f"Seed file not found: {seed_file}")
            sys.exit(1)

        try:
            with open(seed_file, 'r') as f:
                seed_data = json.load(f)

            logger.info(f"Seeding database with data from {seed_file}")
            seed_database(seed_data)
            logger.info("Database seeding completed successfully")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in seed file: {seed_file}")
            logger.error(f"Error details: {str(e)}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error seeding database: {str(e)}")
            sys.exit(1)


if __name__ == "__main__":
    main()