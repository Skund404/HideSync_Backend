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
import traceback

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
    # Use try-except for optional imports or ones that might fail
    import pysqlcipher3.dbapi2 as sqlcipher
    from app.core.config import settings
    from app.core.key_manager import KeyManager
except ImportError as e:
    logger.error(f"Error importing required modules: {e}")
    logger.error("Please ensure all dependencies are installed and configured.")
    sys.exit(1)

# =============================================================================
# EXPECTED_TABLES List - Generated from the provided model files
# =============================================================================
# This list should contain the __tablename__ value for every model inheriting
# from Base, plus any association tables defined using Table().
EXPECTED_TABLES = sorted([
    # Core entities
    "users",
    "roles",
    "permissions",
    "customers",
    "suppliers",
    "materials",                  # Base table for Material STI
    "tools",
    "products",
    "components",
    "patterns",

    # Storage system
    "storage_locations",
    "storage_cells",
    "storage_assignments",
    "storage_moves",

    # Projects system
    "projects",
    "project_templates",
    "project_components",
    "project_template_components",
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

    # Tool management
    "tool_maintenance",
    "tool_checkouts",

    # Planning and picking
    "picking_lists",
    "picking_list_items",

    # Inventory management
    "inventory",
    "inventory_transactions",
    "component_materials",

    # Documentation system
    "documentation_categories",
    "documentation_resources",
    "documentation_category_assignments", # Association Table
    "application_contexts",
    "contextual_help_mappings",

    # Platform integration
    "platform_integrations",
    "sync_events",
    "customer_platform_integration",    # Association Table

    # Media system
    "media_assets",
    "tags",                         # Corrected from media_tags
    "media_asset_tags",             # Association Model/Table
    "entity_media",

    # Auth / User related
    "password_reset_tokens",
    "user_role",                    # Association Table
    "role_permission",              # Association Table

    # Other / System
    "annotations",
    "customer_communication",
    "file_meta_data",
    "supplier_history",
    "supplier_rating",
    "enum_types",                   # Added dynamic enum table
    "enum_translations",            # Added dynamic enum table
])
# =============================================================================


def validate_database():
    """Validate the database structure and content."""
    db_path = None # Initialize to prevent UnboundLocalError
    conn = None    # Initialize to prevent UnboundLocalError
    try:
        # Get database path and encryption key
        db_path = os.path.abspath(settings.DATABASE_PATH)
        key = KeyManager.get_database_encryption_key()
        if not key:
            logger.error("Failed to retrieve database encryption key.")
            return False

        # Check if database file exists
        if not os.path.exists(db_path):
            logger.error(f"Database file not found at: {db_path}")
            return False

        logger.info(f"Connecting to database: {db_path}")
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

        # Verify connection by trying to read schema version or just select 1
        try:
            cursor.execute("SELECT 1") # Basic check
            # cursor.execute("PRAGMA user_version;") # Alternative check
            result = cursor.fetchone()
            logger.info(f"Database connection test successful. Result: {result}")
        except Exception as conn_test_e:
            logger.error(f"Database connection or decryption failed: {conn_test_e}")
            logger.error("Check if the database file exists, is valid, and the key is correct.")
            return False

        # --- Schema Validation ---
        # Get all tables in the database
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        existing_tables = set(row[0] for row in cursor.fetchall())

        logger.info(f"Found {len(existing_tables)} tables in the database.")
        if logger.isEnabledFor(logging.DEBUG): # Only log if verbose
             logger.debug(f"Tables found: {', '.join(sorted(existing_tables))}")

        # Compare existing tables with the expected list
        expected_set = set(EXPECTED_TABLES)
        missing_tables = expected_set - existing_tables
        unexpected_tables = existing_tables - expected_set

        schema_ok = True
        if missing_tables:
            logger.warning(f"MISSING {len(missing_tables)} expected tables:")
            for table in sorted(missing_tables):
                logger.warning(f"  - {table}")
            schema_ok = False
        else:
            logger.info("All expected tables are present.")

        if unexpected_tables:
            # Note: alembic_version is expected if using Alembic migrations
            unexpected_filtered = {t for t in unexpected_tables if t != 'alembic_version'}
            if unexpected_filtered:
                logger.info(f"Found {len(unexpected_filtered)} unexpected tables (excluding alembic_version):")
                for table in sorted(unexpected_filtered):
                    logger.info(f"  + {table}")
            if 'alembic_version' in unexpected_tables:
                logger.info("Found 'alembic_version' table (expected if using Alembic).")
            # Depending on strictness, you might set schema_ok = False here
            # schema_ok = False # Uncomment if unexpected tables are strictly an error

        if schema_ok:
            logger.info("Schema Validation: PASSED - All expected tables found.")
        else:
            logger.warning("Schema Validation: FAILED - Missing expected tables.")

        # --- Basic Data Validation ---
        logger.info("--- Basic Data Checks ---")
        key_tables_for_count = [
            "users", "roles", "permissions", "customers", "suppliers",
            "materials", "projects", "sales", "purchases", "products", "tools",
            "enum_types", "enum_translations" # Check dynamic enums too
        ]

        data_check_passed = True
        for table in key_tables_for_count:
            if table in existing_tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    logger.info(f"Data Check: Table '{table}' has {count} rows.")
                    # Add specific checks, e.g., if count should be > 0 for seed data
                    if table in ["users", "roles"] and count == 0:
                         logger.warning(f"Data Check Warning: Table '{table}' is empty. Seed data might be missing.")
                         # data_check_passed = False # Optionally fail validation if seed data missing
                except Exception as count_e:
                    logger.warning(f"Data Check Warning: Could not count rows in '{table}': {count_e}")
                    # data_check_passed = False # Optionally fail validation if count fails

        # Check for admin user specifically
        if "users" in existing_tables:
            try:
                cursor.execute(
                    # Ensure correct roles table name if different
                    "SELECT u.id, u.email FROM users u JOIN user_role ur ON u.id = ur.user_id JOIN roles r ON ur.role_id = r.id WHERE u.is_superuser = 1 OR lower(r.name) = 'admin'"
                )
                admin_users = cursor.fetchall()
                if admin_users:
                    logger.info(f"Data Check: Found {len(admin_users)} admin user(s):")
                    for user in admin_users:
                        logger.info(f"  - ID: {user[0]}, Email: {user[1]}")
                else:
                    logger.warning("Data Check Warning: No admin users found in the database.")
                    # data_check_passed = False # Optionally fail if no admin found
            except Exception as admin_check_e:
                logger.warning(f"Data Check Warning: Error checking for admin users: {admin_check_e}")
                # data_check_passed = False # Optionally fail

        logger.info("--- Data Checks Completed ---")

        # Final result combines schema and basic data checks (optional)
        overall_success = schema_ok # and data_check_passed # Decide if data checks should fail validation

        return overall_success

    except Exception as e:
        logger.error(f"An unexpected error occurred during database validation: {e}")
        logger.error(traceback.format_exc())
        return False
    finally:
        if conn:
            try:
                conn.close()
                logger.debug("Database connection closed.")
            except Exception as close_e:
                 logger.error(f"Error closing database connection: {close_e}")


def main():
    """Main function for database validation."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate HideSync database schema and basic data.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose (DEBUG) logging output.")

    args = parser.parse_args()

    # Set logging level based on verbosity
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled.")
    else:
        # Ensure INFO level is used if not verbose
         logging.getLogger().setLevel(logging.INFO)


    logger.info("Starting HideSync Database Validation...")
    if validate_database():
        logger.info("Database validation finished successfully.")
        sys.exit(0)
    else:
        logger.error("Database validation finished with errors.")
        sys.exit(1)


if __name__ == "__main__":
    main()