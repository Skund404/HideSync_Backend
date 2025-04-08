#!/usr/bin/env python
"""
Database Seed Data Extraction Script with Hex Key Approach
"""

import os
import sys
import json
from pathlib import Path
import logging

# Add project root to Python path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent if script_dir.name == "scripts" else script_dir
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pysqlcipher3.dbapi2 as sqlcipher
from app.core.config import settings
from app.core.key_manager import KeyManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Define tables to extract in order
TABLES_TO_EXTRACT = [
    'permissions',
    'roles',
    'users',
    'documentation_categories',
    'suppliers',
    'customers',
    'storage_locations',
    'patterns',
    'documentation_resources',
    'storage_cells',
    'materials',
    'tools',
    'components',
    'project_templates',
    'projects',
    'project_components',
    'timeline_tasks',
    'sales',
    'sale_items',
    'purchases',
    'purchase_items',
    'picking_lists',
    'picking_list_items',
    'storage_assignments',
    'tool_maintenance',
    'tool_checkouts'
]


def snake_to_camel(snake_str):
    """Convert snake_case to camelCase"""
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def convert_value(value):
    """Convert various value types to JSON-serializable format"""
    if value is None:
        return None
    if isinstance(value, bytes):
        try:
            return value.decode('utf-8')
        except:
            return str(value)
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return value


def extract_seed_data():
    """Extract seed data from SQLCipher database"""
    db_path = os.path.abspath(settings.DATABASE_PATH)
    logger.info(f"SCRIPT USING DB PATH: {db_path}")
    key = KeyManager.get_database_encryption_key()

    # Establish connection
    conn = sqlcipher.connect(db_path)
    cursor = conn.cursor()

    # Configure encryption with hex key approach
    cursor.execute(f"PRAGMA key = \"x'{key}'\";")
    cursor.execute("PRAGMA cipher_page_size = 4096;")
    cursor.execute("PRAGMA kdf_iter = 256000;")
    cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
    cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
    cursor.execute("PRAGMA foreign_keys = ON;")

    seed_data = {}

    for table_name in TABLES_TO_EXTRACT:
        try:
            # Get column names
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = [col[1] for col in cursor.fetchall()]
            camel_columns = [snake_to_camel(col) for col in columns]

            # Fetch data
            cursor.execute(f"SELECT * FROM {table_name};")
            rows = cursor.fetchall()

            # Convert rows to dictionaries
            table_data = []
            for row in rows:
                row_dict = {}
                for col, val in zip(camel_columns, row):
                    row_dict[col] = convert_value(val)
                table_data.append(row_dict)

            # Only add table to seed data if it has entries
            if table_data:
                seed_data[table_name] = table_data
                logger.info(f"Extracted {len(table_data)} records from {table_name}")

        except Exception as e:
            logger.error(f"Error extracting data from {table_name}: {e}")

    conn.close()
    return seed_data


def main():
    """Main function to extract and save seed data"""
    import argparse

    parser = argparse.ArgumentParser(description="Extract seed data from database")
    parser.add_argument(
        "--output",
        default="app/db/seed_data_comparison.json",
        help="Path to save the extracted seed data JSON"
    )

    args = parser.parse_args()

    # Extract seed data
    seed_data = extract_seed_data()

    # Ensure output directory exists
    output_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Save to JSON file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(seed_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Seed data extracted and saved to {output_path}")
    print(f"Seed data tables: {list(seed_data.keys())}")


if __name__ == "__main__":
    main()