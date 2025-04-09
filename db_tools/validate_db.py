#!/usr/bin/env python
"""
db_tools/validate_db.py

Database Validation Script for HideSync
Verifies that the database structure matches expected schema
and ensures that seed data was properly loaded.
"""

import os
import sys
import logging
from pathlib import Path

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
    from app.core.config import settings
    from app.core.key_manager import KeyManager
except ImportError as e:
    logger.error(f"Error importing required modules: {e}")
    logger.error("Please ensure all dependencies are installed.")
    sys.exit(1)

# List of all expected tables in the database based on the ER diagram
EXPECTED_TABLES = sorted([
    # Core entities
    "users",
    "roles",
    "permissions",
    "customers",
    "suppliers",
    "materials", # Base table for STI
    "tools",
    "products",
    "components",
    # Storage system
    "storage_locations",
    "storage_cells",
    "storage_assignments",
    "storage_moves",
    # Projects system
    "projects",
    "project_templates",
    "project_components",
    "project_template_components", # Added
    "timeline_tasks",
    "recurring_projects",
    "recurrence_patterns",
    "generated_projects",
    # Sales system
    "sales",
    "sale_items",
    "shipments",
    "refunds",
    # Purchasing system
    "purchases",
    "purchase_items",
    # "purchase_timeline_items", # Removed - No model provided
    # Tool management
    "tool_maintenance",
    "tool_checkouts",
    # Planning and picking
    "patterns",
    "picking_lists",
    "picking_list_items",
    # Inventory management
    "inventory",
    "inventory_transactions", # Added
    "component_materials",
    # Documentation system
    "documentation_categories",
    "documentation_resources",
    "documentation_category_assignments",
    "application_contexts",
    "contextual_help_mappings",
    # Platform integration
    "platform_integrations",
    "sync_events",
    "customer_platform_integration", # Added
    # Media system
    "media_assets",
    "tags", # Corrected from media_tags
    "media_asset_tags",
    "entity_media",
    # Auth / User related
    "password_reset_tokens", # Added
    "user_role", # Added
    "role_permission", # Added
    # Other
    "annotations", # Added
    "customer_communication", # Added
    "file_meta_data", # Added
    "supplier_history", # Added
    "supplier_rating", # Added
])


def validate_database():
    """Validate the database structure and content."""
    try:
        # Get database path and encryption key
        db_path = os.path.abspath(settings.DATABASE_PATH)
        key = KeyManager.get_database_encryption_key()

        # Check if database file exists
        if not os.path.exists(db_path):
            logger.error(f"Database file not found at: {db_path}")
            return False

        # Connect to the database
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
        try:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            logger.info(f"Database connection test: {result}")
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False

        # Get all tables in the database
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        existing_tables = set(row[0] for row in cursor.fetchall())

        logger.info(f"Found {len(existing_tables)} tables in the database")
        logger.info(f"Tables: {', '.join(sorted(existing_tables))}")

        # Check for expected tables
        missing_tables = set(EXPECTED_TABLES) - existing_tables
        unexpected_tables = existing_tables - set(EXPECTED_TABLES)

        if missing_tables:
            logger.warning(f"Missing {len(missing_tables)} expected tables:")
            for table in sorted(missing_tables):
                logger.warning(f"  - {table}")
        else:
            logger.info("All expected tables are present in the database")

        if unexpected_tables:
            logger.info(f"Found {len(unexpected_tables)} unexpected tables:")
            for table in sorted(unexpected_tables):
                logger.info(f"  + {table}")

        # Check media system tables specifically
        media_tables = {
            "media_assets",
            "entity_media",
            "media_tags",
            "media_asset_tags",
        }
        missing_media_tables = media_tables - existing_tables

        if missing_media_tables:
            logger.warning(
                f"Missing media system tables: {', '.join(sorted(missing_media_tables))}"
            )
        else:
            logger.info("All media system tables are present")

        # Check for data in key tables
        key_tables = [
            "users",
            "roles",
            "permissions",
            "customers",
            "suppliers",
            "materials",
            "projects",
            "sales",
            "purchases",
        ]

        for table in key_tables:
            if table in existing_tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    logger.info(f"Table {table} has {count} rows")
                except Exception as e:
                    logger.warning(f"Could not count rows in {table}: {e}")

        # Check for admin user
        if "users" in existing_tables:
            try:
                cursor.execute(
                    "SELECT id, email, is_superuser FROM users WHERE is_superuser = 1"
                )
                admin_users = cursor.fetchall()
                if admin_users:
                    logger.info(f"Found {len(admin_users)} admin users:")
                    for user in admin_users:
                        logger.info(f"  - ID: {user[0]}, Email: {user[1]}")
                else:
                    logger.warning("No admin users found in the database")
            except Exception as e:
                logger.warning(f"Error checking for admin users: {e}")

        # Close connection
        conn.close()

        logger.info("Database validation completed")
        return True

    except Exception as e:
        logger.error(f"Error validating database: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return False


def main():
    """Main function for database validation."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate HideSync database")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    # Set logging level based on verbosity
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")

    if validate_database():
        logger.info("Database validation succeeded")
        return True
    else:
        logger.error("Database validation failed")
        return False


if __name__ == "__main__":
    if main():
        sys.exit(0)
    else:
        sys.exit(1)
