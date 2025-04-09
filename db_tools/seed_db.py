#!/usr/bin/env python
"""
db_tools/seed_db.py

Database Seeding Script for HideSync
Loads data from seed_data.json and populates the database using raw SQLCipher.
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
    # Use only the raw pysqlcipher3 driver for this script
    import pysqlcipher3.dbapi2 as sqlcipher
    from app.core.config import settings # Still needed for DB path
    from app.core.key_manager import KeyManager
    # Import security function if available and needed for hashing passwords not already hashed
    try:
        from app.core.security import get_password_hash
        PASSWORD_HASHER_AVAILABLE = True
    except ImportError:
        PASSWORD_HASHER_AVAILABLE = False
        logger.warning("Password hasher (app.core.security.get_password_hash) not found. "
                       "Ensure 'hashedPassword' is provided in seed data for users.")

except ImportError as e:
    logger.error(f"Error importing required modules: {e}")
    logger.error("Please ensure all dependencies are installed.")
    sys.exit(1)

# Define the order in which entities should be created to respect FK constraints
# (Using the previously corrected order)
ENTITIES_ORDER = [
    # Group 1: Mostly independent or only depend on each other
    "permissions", "roles", "users", "documentation_categories", "suppliers", "customers", "storage_locations", "patterns", "project_templates", "media_assets", "tags", "recurrence_patterns", "platform_integrations", "application_contexts",
    # Group 2: Depend on Group 1
    "documentation_resources", "storage_cells", "materials", "tools", "components", "sales", "purchases", "password_reset_tokens", "annotations", "file_meta_data", "supplier_history", "supplier_rating",
    # Group 3: Depend on Group 1 & 2
    "projects", "purchase_items", "component_materials", "storage_assignments", "storage_moves", "tool_maintenance", "refunds", "shipments", "sync_events", "customer_communication", "entity_media", "contextual_help_mappings", "recurring_projects",
    # Group 4: Depend on Group 3+
    "products", "project_components", "timeline_tasks", "tool_checkouts", "picking_lists", "inventory_transactions", "generated_projects", "sale_items",
    # Group 5: Depends on specific items being present
    "inventory", "picking_list_items",
]

# Field overrides for specific entities (Keep this updated based on seed_data.json)
OVERRIDES_BY_ENTITY = {
     "roles": {"isSystemRole": "is_system_role"},
     "projects": {"salesId": "sales_id", "templateId": "template_id"},
     "sale_items": {"saleId": "sale_id", "productId": "product_id", "projectId": "project_id", "patternId": "pattern_id"},
     "purchase_items": {"purchaseId": "purchase_id"},
     "picking_lists": {"projectId": "project_id", "saleId": "sale_id", "assignedTo": "assigned_to"},
     "picking_list_items": {"pickingListId": "picking_list_id", "materialId": "material_id", "componentId": "component_id"},
     "storage_cells": {"storageId": "storage_id"},
     "storage_assignments": {"materialId": "material_id", "storageId": "storage_id", "assignedBy": "assigned_by"},
     "tool_maintenance": {"toolId": "tool_id", "performedBy": "performed_by"},
     "tool_checkouts": {"toolId": "tool_id", "checkedOutBy": "checked_out_by", "projectId": "project_id"},
     "components": {"patternId": "pattern_id", "authorName": "author_name"},
     "timeline_tasks": {"projectId": "project_id"},
     # Add other necessary overrides here based on JSON keys vs snake_case DB columns
}


def camel_to_snake(name: str) -> str:
    """Convert a camelCase string to snake_case."""
    if not name or "_" in name or not any(c.isupper() for c in name): # Avoid double processing or non-camel case
        return name
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def decamelize_keys(data: Any) -> Any:
    """Recursively convert all keys in dictionaries (and lists) from camelCase to snake_case."""
    if isinstance(data, dict):
        new_dict = {}
        for key, value in data.items():
            new_key = camel_to_snake(key)
            new_dict[new_key] = decamelize_keys(value)
        return new_dict
    elif isinstance(data, list):
        return [decamelize_keys(item) for item in data]
    else:
        return data


def apply_overrides(data: dict, overrides: dict) -> dict:
    """Apply custom key overrides."""
    if not overrides:
        return data
    data_copy = data.copy()
    for old_key, new_key in overrides.items():
        # Apply override only if old_key exists and new_key is different
        if old_key in data_copy and old_key != new_key:
            data_copy[new_key] = data_copy.pop(old_key)
            logger.debug(f"Applied override: Renamed '{old_key}' to '{new_key}'")
    return data_copy


def map_material_attributes(data: Dict[str, Any], material_type: str) -> Dict[str, Any]:
    """Map specific material attributes based on type."""
    result = data.copy()
    material_type_upper = material_type.upper() if material_type else ""
    logger.debug(f"Mapping material attrs for type '{material_type_upper}'. Input keys: {list(result.keys())}")
    if 'color' in result:
        if material_type_upper == "HARDWARE": result["hardware_color"] = result.pop("color")
        elif material_type_upper == "SUPPLIES": result["supplies_color"] = result.pop("color")
    if 'finish' in result:
        if material_type_upper == "HARDWARE": result["hardware_finish"] = result.pop("finish")
        elif material_type_upper == "SUPPLIES": result["supplies_finish"] = result.pop("finish")
    if material_type_upper == "HARDWARE" and 'material' in result:
        result["hardware_material"] = result.pop("material")
    logger.debug(f"Keys after material mapping: {list(result.keys())}")
    return result


def load_seed_data(seed_file_path: str) -> Dict[str, List[Dict[str, Any]]]:
    """Load seed data from the given JSON file."""
    file_path = None
    try:
        if os.path.isabs(seed_file_path):
            if os.path.exists(seed_file_path): file_path = seed_file_path
            else: raise FileNotFoundError(f"Seed file not found at absolute path: {seed_file_path}")
        else:
            paths_to_check = [
                os.path.join(project_root, seed_file_path),
                os.path.join(project_root, "app", "db", "seed_data.json"),
                os.path.join(project_root, "seed_data.json"),
                os.path.join(script_dir, "seed_data.json"),
                os.path.join(script_dir, "..", "app", "db", "seed_data.json"),
            ]
            for loc in paths_to_check:
                abs_loc = os.path.abspath(loc)
                if os.path.exists(abs_loc):
                    file_path = abs_loc
                    break
            if not file_path: raise FileNotFoundError(f"Seed file not found: Tried '{seed_file_path}' and common locations.")

        logger.info(f"Loading seed data from: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f: data = json.load(f)
        logger.info(f"Successfully loaded seed data with {len(data)} entity types")
        return data
    except FileNotFoundError as e:
        logger.error(e)
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON from {file_path or seed_file_path}: {e}")
        return {}
    except Exception as e:
        logger.error(f"Error loading seed data: {e}")
        return {}


def seed_database(seed_data: Dict[str, List[Dict[str, Any]]], db_path: str) -> bool:
    """Seed the database with the provided data using raw SQLCipher."""
    conn = None
    cursor = None
    entity_ids: Dict[str, Dict[Any, Any]] = {} # Stores original_id -> new_db_id

    try:
        key = KeyManager.get_database_encryption_key()
        if not key: raise ValueError("Failed to get database encryption key")

        logger.info(f"Connecting to database: {db_path}")
        conn = sqlcipher.connect(db_path)
        cursor = conn.cursor()

        # --- Execute PRAGMAs EXACTLY as in create_db's raw function ---
        logger.info("Setting database key and PRAGMAs...")
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
            logger.debug(f"Executed: {pragma_sql}")

        # --- Verify connection AFTER setting key ---
        logger.info("Verifying connection...")
        cursor.execute("SELECT 1;")
        result = cursor.fetchone()
        if result and result[0] == 1:
            logger.info("Database connection verified successfully.")
        else:
            raise ConnectionError("Failed to verify database connection after setting key.")

        # --- Begin transaction ---
        cursor.execute("BEGIN TRANSACTION;")
        logger.info("Started transaction.")

        # --- Seeding Loop ---
        for entity_type in ENTITIES_ORDER:
            if entity_type not in seed_data or not seed_data[entity_type]:
                logger.debug(f"No seed data for entity type: {entity_type}")
                continue

            logger.info(f"Seeding {entity_type}...")
            entity_count = 0

            # Get schema info ONCE per entity type
            try:
                cursor.execute(f"PRAGMA table_info({entity_type});")
                columns_info = cursor.fetchall()
                valid_columns = {col[1] for col in columns_info}
                column_types = {col[1]: col[2].upper() for col in columns_info}
                logger.debug(f"Schema for {entity_type}: {valid_columns}")
                if not valid_columns: raise ValueError(f"Table '{entity_type}' not found or has no columns.")
            except Exception as e:
                logger.error(f"Fatal: Error getting schema for {entity_type}: {e}. Aborting seed.")
                raise # Stop seeding if schema can't be read

            # Process each item for the current entity type
            for item_data in seed_data[entity_type]:
                original_item_id = item_data.get('id') # Store original ID from JSON
                new_db_id = None
                data_mapped = {}
                filtered_data = {}

                try:
                    # 1. Transformations (camelCase, overrides, material specific)
                    data_snake = decamelize_keys(item_data)
                    data_overridden = apply_overrides(data_snake, OVERRIDES_BY_ENTITY.get(entity_type, {}))
                    if entity_type == "materials" and "material_type" in data_overridden:
                        material_type_val = data_overridden.get("material_type", "").lower()
                        data_mapped = map_material_attributes(data_overridden, material_type_val)
                    else:
                        data_mapped = data_overridden

                    # 2. Filter data for DB columns & handle types
                    filtered_data = {}
                    for key, value in data_mapped.items():
                        if key == "id" and entity_type != "permissions": continue # Skip provided ID except for permissions

                        if key in valid_columns:
                            # Password Hashing
                            if entity_type == "users" and key == "hashed_password":
                                if value and isinstance(value, str) and value.startswith("$2b$"):
                                    filtered_data["hashed_password"] = value
                                else: # Handle cases where it might be plain or missing
                                    logger.error(f"Invalid or missing 'hashedPassword' for user {original_item_id}.")
                                    filtered_data["hashed_password"] = "INVALID_HASH_PLACEHOLDER"
                                continue

                            # JSON conversion
                            if isinstance(value, (dict, list)):
                                try: filtered_data[key] = json.dumps(value)
                                except TypeError as json_err: logger.warning(f"JSON Error {key} for {entity_type} (ID: {original_item_id}): {json_err}. Setting NULL.", exc_info=False); filtered_data[key] = None
                            # Boolean conversion
                            elif isinstance(value, bool) and column_types.get(key) in ("INTEGER", "BOOLEAN"):
                                filtered_data[key] = 1 if value else 0
                            # Date/Time conversion
                            elif isinstance(value, str) and value and column_types.get(key) in ("DATETIME", "TIMESTAMP", "DATE"):
                                try:
                                    clean_value = value[:-1] + "+00:00" if value.endswith("Z") else value
                                    dt_obj = datetime.fromisoformat(clean_value)
                                    # Use ISO 8601 format which SQLite handles well in TEXT columns
                                    filtered_data[key] = dt_obj.isoformat()
                                except (ValueError, TypeError):
                                    logger.warning(f"Date parse error '{value}' for {entity_type}.{key}. Storing as TEXT.", exc_info=False)
                                    filtered_data[key] = value
                            # Enum conversion
                            elif isinstance(value, Enum): filtered_data[key] = value.value
                            # Default
                            else: filtered_data[key] = value

                        elif logger.level <= logging.DEBUG and key != 'id':
                            logger.debug(f"Skipping key '{key}' for {entity_type} (not in schema: {valid_columns})")

                    # 3. Map Foreign Keys
                    for key in list(filtered_data.keys()):
                        if key.endswith("_id") and filtered_data[key] is not None:
                            if key == 'id' and entity_type != 'permissions': continue # Skip self-referencing PK

                            fk_original_id_str = str(filtered_data[key]) # Value from JSON/Overrides
                            fk_entity_type = None
                            # --- Simplified FK Mapping (Add more as needed) ---
                            type_map = {
                                "supplier_id": "suppliers", "customer_id": "customers", "project_id": "projects",
                                "product_id": "products", "tool_id": "tools", "material_id": "materials",
                                "storage_id": "storage_locations", "storage_location_id": "storage_locations",
                                "pattern_id": "patterns", "sale_id": "sales", "purchase_id": "purchases",
                                "picking_list_id": "picking_lists", "component_id": "components",
                                "template_id": "project_templates", "user_id": "users", "role_id": "roles",
                                "permission_id": "permissions", "parent_category_id": "documentation_categories",
                                "author_id": "users", "platform_integration_id": "platform_integrations",
                                "media_asset_id": "media_assets", "tag_id": "tags",
                                "recurrence_pattern_id": "recurrence_patterns", "recurring_project_id": "recurring_projects",
                                "processed_by": "users", "assigned_by": "users", "checked_out_by": "users"
                            }
                            fk_entity_type = type_map.get(key)
                            # --------------------------------------------

                            if fk_entity_type:
                                try:
                                    fk_original_lookup_id = int(fk_original_id_str)
                                    if fk_entity_type in entity_ids and fk_original_lookup_id in entity_ids[fk_entity_type]:
                                        mapped_fk_id = entity_ids[fk_entity_type][fk_original_lookup_id]
                                        filtered_data[key] = mapped_fk_id
                                        logger.debug(f"Mapped FK {entity_type}.{key}: JSON ID {fk_original_lookup_id} -> DB ID {mapped_fk_id}")
                                    else:
                                        logger.warning(f"FK Mapping MISS for {entity_type}.{key}: Original JSON ID {fk_original_lookup_id} not in mapped IDs for {fk_entity_type}.")
                                        # Decide: fail, set NULL if allowed, or keep original (will likely fail)
                                        # For now, let the constraint failure happen if needed
                                except (ValueError, TypeError):
                                     logger.warning(f"Invalid FK value '{fk_original_id_str}' for {entity_type}.{key}. Keeping original.")
                                     filtered_data[key] = fk_original_id_str # Keep potentially invalid value

                    # 4. Insert Data
                    if not filtered_data:
                        logger.warning(f"No valid data to insert for {entity_type} (Original ID: {original_item_id}).")
                        continue

                    columns = list(filtered_data.keys())
                    placeholders = ", ".join(["?"] * len(columns))
                    values = list(filtered_data.values())
                    sql = f"INSERT INTO {entity_type} ({', '.join(columns)}) VALUES ({placeholders});"

                    logger.debug(f"Executing SQL: {sql}")
                    logger.debug(f"With values: {values}")
                    cursor.execute(sql, values)

                    # 5. Get and Store New DB ID for Mapping
                    new_db_id = None
                    if entity_type == 'permissions':
                        new_db_id = filtered_data.get('id') # Use the ID we inserted
                    else:
                        cursor.execute("SELECT last_insert_rowid();")
                        result_id = cursor.fetchone()
                        if result_id: new_db_id = result_id[0]

                    if original_item_id is not None and new_db_id is not None:
                        if entity_type not in entity_ids: entity_ids[entity_type] = {}
                        entity_ids[entity_type][original_item_id] = new_db_id
                        logger.debug(f"Stored ID map {entity_type}: JSON ID '{original_item_id}' -> DB ID {new_db_id}")
                    elif new_db_id is not None:
                         logger.warning(f"No 'id' in JSON for {entity_type} item, cannot map FKs TO this record. DB ID: {new_db_id}")
                    else:
                         logger.error(f"Failed to get DB ID for inserted {entity_type} (Original JSON ID: {original_item_id})")


                    entity_count += 1

                except Exception as e:
                    logger.error(f"Error processing {entity_type} record (Original JSON ID: {original_item_id}): {e}")
                    logger.error(f"Mapped data before filtering: {data_mapped}")
                    logger.error(f"Filtered data for insert attempt: {filtered_data}")
                    raise # Re-raise to trigger rollback and stop

            logger.info(f"Seeded {entity_count} {entity_type} records")

        # --- Commit transaction ---
        conn.commit()
        logger.info("Transaction committed.")

        logger.info("Database seeding completed successfully")
        return True

    except Exception as e:
        logger.error(f"Fatal error during database seeding: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if conn:
            logger.info("Rolling back transaction...")
            try: conn.rollback()
            except Exception as rb_err: logger.error(f"Error during rollback: {rb_err}")
        return False
    finally:
        if cursor:
            try: cursor.close()
            except Exception as cur_err: logger.error(f"Error closing cursor: {cur_err}")
        if conn:
            try: conn.close(); logger.info("Database connection closed.")
            except Exception as conn_err: logger.error(f"Error closing connection: {conn_err}")


def main():
    """Main function to seed the database."""
    import argparse

    parser = argparse.ArgumentParser(description="Seed HideSync database")
    parser.add_argument(
        "--seed-file",
        type=str,
        default="app/db/seed_data.json", # Default relative to project root
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
        # Set level for the script's logger
        logger.setLevel(logging.DEBUG)
        # Set level for the root logger to catch dependency logs if needed
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    # Check if database exists
    db_path = os.path.abspath(settings.DATABASE_PATH)
    if not os.path.exists(db_path):
        logger.error(f"Database file not found at {db_path}")
        logger.error("Please create the database first using create_db.py")
        return False

    # Load seed data
    seed_data = load_seed_data(args.seed_file)
    if not seed_data:
        logger.error("Failed to load seed data.")
        return False

    # Seed the database
    if not seed_database(seed_data, db_path):
        logger.error("Database seeding failed.")
        return False

    logger.info("Database seeded successfully.")
    return True


if __name__ == "__main__":
    if main():
        sys.exit(0)
    else:
        sys.exit(1)