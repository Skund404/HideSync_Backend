#!/usr/bin/env python
"""
db_tools/extract_db.py

Database Seed Data Extraction Script
Extracts data from all user tables in the SQLCipher database
and saves it to a JSON file in a format similar to seed_data.json.
"""

import os
import sys
import json
import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Type
from datetime import datetime

# Add project root to Python path
script_dir = Path(__file__).resolve().parent
# Adjust project_root detection based on script location
project_root = script_dir.parent if script_dir.name in ["db_tools", "scripts"] else script_dir
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

# System tables to exclude from extraction
SYSTEM_TABLES = {"sqlite_sequence", "sqlite_stat1", "sqlite_master"}

# --- Helper Functions ---

def snake_to_camel(snake_str: str) -> str:
    """Convert snake_case string to camelCase."""
    if not snake_str or "_" not in snake_str:
        return snake_str
    components = snake_str.split("_")
    # Join first component lower, subsequent components titled
    return components[0] + "".join(x.title() for x in components[1:])

def get_all_user_tables(cursor: sqlcipher.Cursor) -> List[str]:
    """Get a list of all non-system tables from the database."""
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall() if row[0] not in SYSTEM_TABLES]
        logger.info(f"Found {len(tables)} user tables: {sorted(tables)}")
        return sorted(tables)
    except Exception as e:
        logger.error(f"Error fetching table list: {e}")
        return []

def convert_db_value(value: Any, column_type: str, column_name: str) -> Any:
    """
    Convert a value retrieved from the database to a JSON-serializable format,
    attempting type-specific conversions (JSON, Bool, DateTime).
    """
    if value is None:
        return None

    # Attempt JSON parsing for TEXT columns likely containing JSON
    json_like_columns = {"tags", "attributes", "dimensions", "position", "change_history",
                         "material_categories", "dependencies", "cost_breakdown",
                         "marketplace_data", "media_attachments", "related_resource_ids"}
    if column_type == "TEXT" and (column_name in json_like_columns or column_name.endswith("_data") or column_name.endswith("_ids")):
        try:
            # Only parse if it looks like a JSON object or array start/end
            if isinstance(value, str) and value.strip().startswith(('[', '{')) and value.strip().endswith((']', '}')):
                 return json.loads(value)
            # Otherwise, return the string as is (might not be JSON)
            return value
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Could not decode JSON for column '{column_name}'. Returning raw string: {value[:50]}...", exc_info=False)
            return value # Return original string if parsing fails

    # Convert INTEGER 0/1 back to Boolean for relevant columns
    boolean_like_columns = {"is_active", "is_superuser", "is_system_role", "is_optional",
                            "is_favorite", "is_public", "occupied", "internal_service",
                            "is_critical_path", "is_full_hide"}
    if column_type == "INTEGER" and (column_name in boolean_like_columns or column_name.startswith("is_")):
        try:
            # Ensure it's actually 0 or 1 before converting
            int_val = int(value)
            if int_val in (0, 1):
                return bool(int_val)
            else:
                 logger.warning(f"Unexpected integer value '{value}' in boolean-like column '{column_name}'. Returning int.")
                 return int_val # Return original int if not 0 or 1
        except (ValueError, TypeError):
             logger.warning(f"Could not convert value '{value}' to boolean for column '{column_name}'. Returning original.")
             return value # Return original if conversion fails

    # Convert TEXT date/time strings back to ISO format strings (assuming they were stored that way)
    if column_type == "TEXT" and column_name.endswith(("_at", "_date")):
        try:
            # Attempt parsing to validate, then return standard ISO format
            # SQLite stores TEXT, so direct return is often okay if stored in ISO
            datetime.fromisoformat(str(value).replace(' ', 'T')) # Validate format
            return str(value).replace(' ', 'T') # Return standard ISO format string
        except (ValueError, TypeError):
            logger.warning(f"Could not parse value '{value}' as ISO date/time for column '{column_name}'. Returning raw string.")
            return str(value) # Return original string if parsing fails

    # Handle potential bytes
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors='replace') # Decode bytes to string
        except Exception:
             logger.warning(f"Could not decode bytes for column '{column_name}'. Returning representation.")
             return repr(value)

    # Default: return value as is (covers numbers, basic strings)
    return value

# --- Main Extraction Logic ---

def extract_seed_data():
    """Extract seed data from all user tables in the SQLCipher database."""
    db_path = os.path.abspath(settings.DATABASE_PATH)
    logger.info(f"Starting data extraction from database: {db_path}")
    key = KeyManager.get_database_encryption_key()
    if not key:
        logger.error("Failed to get database encryption key.")
        return {}

    conn = None
    cursor = None
    seed_data = {}

    try:
        # Establish connection
        conn = sqlcipher.connect(db_path)
        cursor = conn.cursor()

        # Configure encryption with hex key approach
        pragmas = [
            f"PRAGMA key = \"x'{key}'\";",
            "PRAGMA cipher_page_size = 4096;",
            "PRAGMA kdf_iter = 256000;",
            "PRAGMA cipher_hmac_algorithm = HMAC_SHA512;",
            "PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;",
            "PRAGMA foreign_keys = ON;"
        ]
        for pragma_sql in pragmas:
            cursor.execute(pragma_sql)

        # Verify connection *after* setting key
        cursor.execute("SELECT 1;")
        if not cursor.fetchone():
            raise ConnectionError("Failed to verify connection after setting key.")
        logger.info("Database connection and decryption verified.")

        # Get all user table names
        all_tables = get_all_user_tables(cursor)
        if not all_tables:
             logger.warning("No user tables found in the database.")
             return {}

        # Extract data table by table
        for table_name in all_tables:
            try:
                logger.info(f"Extracting data from table: {table_name}")
                # Get column names and types
                cursor.execute(f"PRAGMA table_info({table_name});")
                columns_info = cursor.fetchall()
                if not columns_info:
                    logger.warning(f"Could not get column info for table {table_name}, skipping.")
                    continue

                # Store column names (snake_case) and types
                db_columns = [col[1] for col in columns_info]
                column_types = {col[1]: col[2].upper() for col in columns_info}
                # Convert DB column names to desired output keys (camelCase)
                output_columns = [snake_to_camel(col) for col in db_columns]

                # Fetch all data from the table
                cursor.execute(f"SELECT {', '.join(db_columns)} FROM {table_name};")
                rows = cursor.fetchall()

                # Convert rows to dictionaries with type conversions
                table_data = []
                for row_index, row in enumerate(rows):
                    row_dict = {}
                    try:
                        for db_col, output_col, val in zip(db_columns, output_columns, row):
                            col_type = column_types.get(db_col, "UNKNOWN")
                            converted_val = convert_db_value(val, col_type, db_col)
                            row_dict[output_col] = converted_val
                        table_data.append(row_dict)
                    except Exception as row_err:
                         logger.error(f"Error processing row {row_index} in table {table_name}: {row_err}")
                         logger.error(f"Row data: {row}")
                         # Optionally skip row or add placeholder

                # Only add table to seed data if it has entries
                if table_data:
                    seed_data[table_name] = table_data
                    logger.info(f"  Extracted {len(table_data)} records.")
                else:
                    logger.info(f"  Table {table_name} is empty.")

            except Exception as table_err:
                logger.error(f"Error extracting data from table '{table_name}': {table_err}", exc_info=True)
                # Continue to the next table

    except sqlcipher.Error as db_err:
         logger.error(f"Database error during extraction: {db_err}", exc_info=True)
         # Specific check for decryption errors
         if "hmac check failed" in str(db_err) or "decrypting page" in str(db_err):
              logger.error("HMAC check failed - Decryption error. Ensure the correct key and PRAGMA settings are used.")
         return {} # Return empty on major DB error
    except Exception as e:
        logger.error(f"An unexpected error occurred during extraction: {e}", exc_info=True)
        return {}
    finally:
        if cursor:
            try: cursor.close()
            except Exception: pass
        if conn:
            try: conn.close(); logger.info("Database connection closed.")
            except Exception: pass

    logger.info(f"Finished extraction. Found data for {len(seed_data)} tables.")
    return seed_data

# --- Main Execution ---

def main():
    """Main function to extract and save seed data"""
    import argparse

    parser = argparse.ArgumentParser(description="Extract seed data from HideSync database")
    parser.add_argument(
        "--output", "-o",
        default="app/db/extracted_seed_data.json", # Default output file name
        help="Path to save the extracted seed data JSON file (relative or absolute)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging for more detailed output",
    )

    args = parser.parse_args()

    # Set logging level
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled.")

    # Extract seed data
    seed_data = extract_seed_data()

    if not seed_data:
         logger.error("Extraction failed or no data found.")
         sys.exit(1)

    # Ensure output directory exists
    output_path = os.path.abspath(args.output)
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
    except OSError as e:
        logger.error(f"Could not create output directory '{os.path.dirname(output_path)}': {e}")
        sys.exit(1)

    # Save to JSON file
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(seed_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Seed data extracted and saved successfully to: {output_path}")
        print(f"\nExtracted data for tables: {list(seed_data.keys())}")
    except IOError as e:
         logger.error(f"Could not write seed data to '{output_path}': {e}")
         sys.exit(1)
    except TypeError as e:
         logger.error(f"Data serialization error: {e}. Some data might not be JSON serializable.")
         # Consider logging the problematic data snippet if possible
         sys.exit(1)


if __name__ == "__main__":
    main()