#!/usr/bin/env python
"""
Script to find products missing inventory records and insert default entries.
Uses SQLCipher for encrypted databases.
"""

import os
import sys
import uuid
from pathlib import Path
import logging
from typing import List, Set, Optional
from datetime import datetime, timezone

# --- Setup Project Path ---
# Ensures 'app' can be imported
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent if script_dir.name == "scripts" else script_dir
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
# --- End Setup ---

# --- Imports ---
try:
    import pysqlcipher3.dbapi2 as sqlcipher
    from app.core.config import settings
    from app.core.key_manager import KeyManager
    # Import Enums needed for defaults
    from app.db.models.enums import InventoryStatus
except ImportError as e:
    print(f"Error importing necessary modules: {e}")
    print("Please ensure you are in the project root directory, the virtual environment is activated,")
    print("and all requirements from requirements.txt are installed.")
    sys.exit(1)
# --- End Imports ---

# --- Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DB_PATH = os.path.abspath(settings.DATABASE_PATH)

# Default values for new inventory records
DEFAULT_QUANTITY = 0.0
DEFAULT_STATUS = InventoryStatus.OUT_OF_STOCK.value # Use the enum's value
DEFAULT_LOCATION = "Unassigned"
DEFAULT_IS_ACTIVE = 1
# --- End Configuration ---

def connect_db(db_path: str, key: str) -> Optional[sqlcipher.Connection]:
    """Establishes a connection to the SQLCipher database."""
    try:
        logger.info(f"Attempting to connect to database: {db_path}")
        conn = sqlcipher.connect(db_path)
        cursor = conn.cursor()
        # Configure encryption with hex key approach
        cursor.execute(f"PRAGMA key = \"x'{key}'\";")
        cursor.execute("PRAGMA cipher_page_size = 4096;")
        cursor.execute("PRAGMA kdf_iter = 256000;")
        cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
        cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
        # Test connection with a simple query
        cursor.execute("SELECT count(*) FROM sqlite_master;")
        logger.info("Database connection and key successful.")
        return conn
    except Exception as e:
        logger.error(f"Failed to connect or unlock database: {e}", exc_info=True)
        return None

def get_all_product_ids(conn: sqlcipher.Connection) -> Set[int]:
    """Retrieves all product IDs from the products table."""
    ids = set()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM products;")
        rows = cursor.fetchall()
        ids = {row[0] for row in rows}
        logger.info(f"Found {len(ids)} product IDs in 'products' table.")
    except Exception as e:
        logger.error(f"Error fetching product IDs: {e}", exc_info=True)
    return ids

def get_existing_inventory_product_ids(conn: sqlcipher.Connection) -> Set[int]:
    """Retrieves item_ids for existing 'product' type inventory records."""
    ids = set()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT item_id FROM inventory WHERE item_type = 'product';")
        rows = cursor.fetchall()
        ids = {row[0] for row in rows}
        logger.info(f"Found {len(ids)} existing 'product' inventory records.")
    except Exception as e:
        logger.error(f"Error fetching existing inventory product IDs: {e}", exc_info=True)
    return ids

def insert_missing_inventory(conn: sqlcipher.Connection, product_id: int) -> bool:
    """Inserts a default inventory record for a given product ID."""
    try:
        cursor = conn.cursor()
        # now_iso = datetime.now(timezone.utc).isoformat() # No longer needed
        new_uuid = uuid.uuid4().hex # Generate hex UUID

        # --- CORRECTED SQL: Removed createdAt and updatedAt ---
        sql = """
        INSERT INTO inventory
        (item_type, item_id, quantity, status, storage_location, uuid, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            'product',
            product_id,
            DEFAULT_QUANTITY,
            DEFAULT_STATUS,
            DEFAULT_LOCATION,
            # now_iso, # REMOVED
            # now_iso, # REMOVED
            new_uuid,
            DEFAULT_IS_ACTIVE
        )
        # --- END CORRECTION ---

        cursor.execute(sql, params)
        logger.info(f"Successfully inserted default inventory record for product ID: {product_id}")
        return True
    except Exception as e:
        logger.error(f"Error inserting inventory record for product ID {product_id}: {e}", exc_info=True)
        return False

def main():
    """Finds missing inventory records and inserts defaults."""
    logger.info(f"Starting inventory check for database: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        logger.error(f"Database file not found at: {DB_PATH}")
        sys.exit(1)

    db_key = KeyManager.get_database_encryption_key()
    if not db_key:
        logger.error("Failed to retrieve database encryption key.")
        sys.exit(1)

    connection = connect_db(DB_PATH, db_key)
    if not connection:
        sys.exit(1)

    inserted_count = 0
    failed_count = 0
    try:
        all_product_ids = get_all_product_ids(connection)
        existing_inventory_ids = get_existing_inventory_product_ids(connection)

        if not all_product_ids:
            logger.warning("No products found in the database. Exiting.")
            return

        missing_ids = all_product_ids - existing_inventory_ids

        if not missing_ids:
            logger.info("All products have corresponding inventory records. No action needed.")
        else:
            logger.warning(f"Found {len(missing_ids)} products missing inventory records: {sorted(list(missing_ids))}")
            logger.info("Attempting to insert default inventory records...")

            for prod_id in sorted(list(missing_ids)):
                if insert_missing_inventory(connection, prod_id):
                    inserted_count += 1
                else:
                    failed_count += 1

            if failed_count == 0 and inserted_count > 0:
                logger.info("Committing changes...")
                connection.commit()
                logger.info(f"Successfully inserted {inserted_count} missing inventory records.")
            elif inserted_count > 0:
                logger.warning(f"Inserted {inserted_count} records, but {failed_count} insertions failed. Committing successful inserts.")
                connection.commit()
            else:
                logger.error("All insertions failed. Rolling back any potential changes (though none should have occurred).")
                connection.rollback() # Explicit rollback on complete failure

    except Exception as e:
        logger.error(f"An unexpected error occurred during the process: {e}", exc_info=True)
        if connection:
            connection.rollback()
    finally:
        if connection:
            connection.close()
            logger.info("Database connection closed.")

if __name__ == "__main__":
    main()