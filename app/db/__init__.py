# File: app/db/init_db.py
"""
Database initialization functions for HideSync.

This module provides functions for initializing the database schema and
creating any essential initial data.
"""

import logging
import os
import sys
from pathlib import Path

from app.db.session import init_db
from app.core.config import settings

logger = logging.getLogger(__name__)


def create_database_directory():
    """Create the database directory if it doesn't exist."""
    try:
        db_dir = Path(settings.DATABASE_PATH).parent
        if not db_dir.exists():
            logger.info(f"Creating database directory: {db_dir}")
            os.makedirs(db_dir, exist_ok=True)
    except Exception as e:
        logger.error(f"Error creating database directory: {str(e)}")
        raise


def main(reset=False):
    """
    Initialize the database.

    Args:
        reset: Whether to reset the database by dropping all tables first
    """
    # Create the database directory if needed
    create_database_directory()

    # Initialize the database (create tables)
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Call the main function
    main()
