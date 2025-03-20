# File: scripts/setup_db.py
"""
Command-line script to set up the database.

This script initializes the database, creates all tables, and sets up
the initial admin user. It should be run once before starting the application.
"""

import sys
import os
import logging
from pathlib import Path

# Add the parent directory to Python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.db.init_db import main as init_db_main

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Set up the database with tables and initial data."""
    logger.info("Setting up the database...")
    # Initialize SQLCipher database and create tables
    init_db_main()
    logger.info("Database setup completed successfully")


if __name__ == "__main__":
    main()
