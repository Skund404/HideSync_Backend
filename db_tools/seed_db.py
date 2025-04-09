#!/usr/bin/env python
"""
db_tools/seed_db.py

Database Seeding Script for HideSync
Loads data from seed_data.json and populates the database.
"""

import os
import sys
import json
import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Type
from datetime import datetime
from enum import Enum

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

# Define the order in which entities should be created to respect FK constraints
ENTITIES_ORDER = [
    "permissions",
    "roles",
    "users",
    "documentation_categories",
    "suppliers",
    "customers",
    "storage_locations",
    "patterns",
    "documentation_resources",
    "storage_cells",
    "materials",
    "tools",
    "components",
    "products",
    "project_templates",
    "projects",
    "project_components",
    "timeline_tasks",
    "sales",
    "sale_items",
    "purchases",
    "purchase_items",
    "picking_lists",
    "picking_list_items",
    "storage_assignments",
    "tool_maintenance",
    "tool_checkouts",
]

# Field overrides for specific entities
OVERRIDES_BY_ENTITY = {
    "permissions": {
        # Empty but keep the key for consistency
    },
    "roles": {
        # Keep is_system_role as is since the database expects it
    },
    "users": {
        "plain_password": "password",
    },
    "suppliers": {
        "material_categories": "categories",
        "lead_time": "shipping_time",
    },
    "materials": {
        "animal_source": "source",
        "supplies_material_type": "type",
    },
    "storage_locations": {
        "section": "area",
    },
    "storage_cells": {
        "storage_location_id": "storage_id",
    },
}


def camel_to_snake(name: str) -> str:
    """Convert a camelCase string to snake_case."""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def decamelize_keys(data: Any) -> Any:
    """Recursively convert all keys in dictionaries (and lists) from camelCase to snake_case."""
    if isinstance(data, dict):
        return {
            camel_to_snake(key): decamelize_keys(value) for key, value in data.items()
        }
    elif isinstance(data, list):
        return [decamelize_keys(item) for item in data]
    else:
        return data


def apply_overrides(data: dict, overrides: dict) -> dict:
    """
    Apply custom key overrides on the given dictionary.
    For each key in the overrides, if the key exists in data,
    rename it to the corresponding override.
    """
    data_copy = data.copy()
    for old_key, new_key in overrides.items():
        if old_key in data_copy:
            data_copy[new_key] = data_copy.pop(old_key)
    return data_copy


def map_material_attributes(data: Dict[str, Any], material_type: str) -> Dict[str, Any]:
    """Map custom material attributes based on type."""
    result = data.copy()
    # Ensure material_type is uppercase for comparison
    material_type_upper = material_type.upper()

    logger.debug(
        f"Mapping attributes for material_type '{material_type_upper}'. Keys before mapping: {list(result.keys())}"
    )

    if material_type_upper == "HARDWARE":
        if "color" in result:
            result["hardware_color"] = result.pop("color")
            logger.debug(f"  Mapped 'color' to 'hardware_color'")
        if "finish" in result:
            result["hardware_finish"] = result.pop("finish")
            logger.debug(f"  Mapped 'finish' to 'hardware_finish'")
    elif material_type_upper == "SUPPLIES":
        if "color" in result:
            result["supplies_color"] = result.pop("color")
            logger.debug(f"  Mapped 'color' to 'supplies_color'")
        if "finish" in result:
            result["supplies_finish"] = result.pop("finish")
            logger.debug(f"  Mapped 'finish' to 'supplies_finish'")
    # Leather doesn't need specific renaming here as 'color' and 'finish' are standard

    logger.debug(f"Keys after mapping: {list(result.keys())}")
    return result


def load_seed_data(seed_file_path: str) -> Dict[str, List[Dict[str, Any]]]:
    """Load seed data from the given JSON file."""
    try:
        # If it's an absolute path, use it directly
        if os.path.isabs(seed_file_path):
            if os.path.exists(seed_file_path):
                file_path = seed_file_path
            else:
                logger.error(f"Seed file not found at absolute path: {seed_file_path}")
                return {}
        else:
            # Try relative to project root
            file_path = os.path.join(project_root, seed_file_path)
            if not os.path.exists(file_path):
                # Check common locations
                common_locations = [
                    os.path.join(project_root, "app", "db", "seed_data.json"),
                    os.path.join(project_root, "data", "seed_data.json"),
                    os.path.join(project_root, "seed_data.json"),
                ]
                for loc in common_locations:
                    if os.path.exists(loc):
                        file_path = loc
                        break
                else:
                    logger.error(f"Seed file not found: {seed_file_path}")
                    return {}

        logger.info(f"Loading seed data from: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        logger.info(f"Successfully loaded seed data with {len(data)} entity types")
        return data

    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON from {seed_file_path}: {e}")
        return {}
    except Exception as e:
        logger.error(f"Error loading seed data: {e}")
        return {}


def seed_database(seed_data: Dict[str, List[Dict[str, Any]]], db_path: str) -> bool:
    """Seed the database with the provided data."""
    try:
        # Get encryption key
        key = KeyManager.get_database_encryption_key()
        if not key:
            logger.error("Failed to get database encryption key")
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
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        if result and result[0] == 1:
            logger.info("Database connection verified")
        else:
            logger.error("Failed to verify database connection")
            return False

        # Dictionary to track created entity IDs (for handling FK relationships)
        entity_ids = {}

        # Seed database with entities in the correct order
        for entity_type in ENTITIES_ORDER:
            if entity_type not in seed_data:
                logger.debug(f"No seed data found for entity type: {entity_type}")
                continue

            logger.info(f"Seeding {entity_type}...")
            entity_count = 0

            # Get schema information for this table
            try:
                cursor.execute(f"PRAGMA table_info({entity_type})")
                columns_info = cursor.fetchall()
                valid_columns = [col[1] for col in columns_info]
                logger.debug(f"Table schema for {entity_type}: {valid_columns}")

                if not valid_columns:
                    logger.warning(
                        f"Table {entity_type} not found in database or has no columns"
                    )
                    continue
            except Exception as e:
                logger.warning(f"Error getting schema for {entity_type}: {e}")
                logger.warning(f"Skipping entity type: {entity_type}")
                continue

            # Process each entity
            for idx, item_data in enumerate(seed_data[entity_type], 1):
                try:
                    # 1. Convert camelCase to snake_case
                    data = decamelize_keys(item_data)

                    # 2. Apply entity-specific overrides
                    if entity_type in OVERRIDES_BY_ENTITY:
                        data = apply_overrides(data, OVERRIDES_BY_ENTITY[entity_type])

                    # 3. Handle special entity types for materials
                    if entity_type == "materials" and "material_type" in data:
                        material_type = data.get("material_type", "").lower()
                        data = map_material_attributes(data, material_type)

                    # 4. Prepare data for insertion
                    filtered_data = {}
                    for key, value in data.items():
                        # Only include fields that exist in the table schema
                        if key in valid_columns:
                            # Handle complex types (dict, list)
                            if isinstance(value, (dict, list)):
                                filtered_data[key] = json.dumps(value)
                            # Handle date/time strings
                            elif isinstance(value, str) and (
                                key.endswith("_date")
                                or key.endswith("_at")
                                or key == "date"
                            ):
                                try:
                                    if value.endswith("Z"):
                                        value = value[:-1] + "+00:00"
                                    filtered_data[key] = datetime.fromisoformat(
                                        value
                                    ).isoformat()
                                except ValueError:
                                    filtered_data[key] = (
                                        value  # Keep original if parsing fails
                                    )
                            # Special handling for password hashing
                            elif entity_type == "users" and key == "password":
                                try:
                                    from app.core.security import get_password_hash

                                    filtered_data["hashed_password"] = (
                                        get_password_hash(value)
                                    )
                                except ImportError:
                                    # If security module not available, use the hashed_password directly
                                    filtered_data["hashed_password"] = data.get(
                                        "hashed_password", ""
                                    )
                            else:
                                filtered_data[key] = value

                    # 5. Handle foreign key references using entity_ids
                    for key in list(filtered_data.keys()):
                        if key.endswith("_id") and isinstance(filtered_data[key], int):
                            original_id = filtered_data[key]
                            fk_entity_type = None

                            # Map field name to referenced entity type
                            if key == "supplier_id":
                                fk_entity_type = "suppliers"
                            elif key == "customer_id":
                                fk_entity_type = "customers"
                            elif key == "project_id":
                                fk_entity_type = "projects"
                            elif key == "product_id":
                                fk_entity_type = "products"
                            elif key == "tool_id":
                                fk_entity_type = "tools"
                            elif key == "material_id":
                                fk_entity_type = "materials"
                            elif key == "storage_location_id":
                                fk_entity_type = "storage_locations"
                            elif key == "pattern_id":
                                fk_entity_type = "patterns"
                            elif key == "sale_id":
                                fk_entity_type = "sales"
                            elif key == "purchase_id":
                                fk_entity_type = "purchases"
                            elif key == "picking_list_id":
                                fk_entity_type = "picking_lists"
                            elif key == "component_id":
                                fk_entity_type = "components"
                            elif key == "project_template_id":
                                fk_entity_type = "project_templates"

                            # If we know the referenced entity type and have an ID mapping
                            if (
                                fk_entity_type
                                and fk_entity_type in entity_ids
                                and original_id in entity_ids[fk_entity_type]
                            ):
                                filtered_data[key] = entity_ids[fk_entity_type][
                                    original_id
                                ]
                                logger.debug(
                                    f"Mapped FK {key}: {original_id} -> {filtered_data[key]}"
                                )

                    # 6. Check if we have any data to insert after filtering
                    if not filtered_data:
                        logger.warning(
                            f"No valid data for {entity_type} at index {idx} after filtering"
                        )
                        continue

                    # 7. Generate and execute INSERT statement
                    columns = list(filtered_data.keys())
                    placeholders = ", ".join(["?"] * len(columns))
                    values = list(filtered_data.values())

                    sql = f"INSERT INTO {entity_type} ({', '.join(columns)}) VALUES ({placeholders})"

                    try:
                        cursor.execute(sql, values)
                    except Exception as e:
                        logger.error(f"Error inserting into {entity_type}: {e}")
                        logger.error(f"SQL: {sql}")
                        logger.error(f"Values: {values}")
                        raise

                    # 8. Get the ID of the inserted entity
                    cursor.execute("SELECT last_insert_rowid()")
                    new_id = cursor.fetchone()[0]

                    # Store the ID for future FK references
                    if entity_type not in entity_ids:
                        entity_ids[entity_type] = {}
                    entity_ids[entity_type][idx] = new_id

                    entity_count += 1
                    logger.debug(f"Inserted {entity_type} with ID {new_id}")

                except Exception as e:
                    logger.error(f"Error processing {entity_type} at index {idx}: {e}")
                    conn.rollback()
                    raise

            logger.info(f"Seeded {entity_count} {entity_type} records")

        # Commit changes and close connection
        conn.commit()
        conn.close()

        logger.info("Database seeding completed successfully")
        return True

    except Exception as e:
        logger.error(f"Error seeding database: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return False


def main():
    """Main function to seed the database."""
    import argparse

    parser = argparse.ArgumentParser(description="Seed HideSync database")
    parser.add_argument(
        "--seed-file",
        type=str,
        default="app/db/seed_data.json",
        help="Path to the seed data JSON file (relative to project root or absolute)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging for more detailed output",
    )

    args = parser.parse_args()

    # Enable debug logging if requested
    if args.debug:
        logging.getLogger(__name__).setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    # Check if database exists
    db_path = os.path.abspath(settings.DATABASE_PATH)
    if not os.path.exists(db_path):
        logger.error(f"Database does not exist at {db_path}")
        logger.error("Please create the database first using create_db.py")
        return False

    # Load seed data
    seed_data = load_seed_data(args.seed_file)
    if not seed_data:
        logger.error("Failed to load seed data")
        return False

    # Seed the database
    if not seed_database(seed_data, db_path):
        logger.error("Failed to seed database")
        return False

    logger.info("Database seeded successfully")
    return True


if __name__ == "__main__":
    if main():
        sys.exit(0)
    else:
        sys.exit(1)
