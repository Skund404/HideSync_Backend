#!/usr/bin/env python
"""
Patched database setup script for HideSync.

This script handles everything related to database setup:
1. Creating/resetting the database
2. Creating tables by running SQLAlchemy model creation code
3. Optionally seeding the database with initial data

Usage (from project root directory):
  python -m scripts.setup_database [--reset] [--seed] [--seed-file PATH]
"""

import os
import sys
import json
import re
import logging
import argparse
import importlib.util
from pathlib import Path
from typing import Dict, Any, List, Optional, Type
from datetime import datetime
from enum import Enum

# --- Path Setup ---
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent if script_dir.name == "scripts" else script_dir
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# --- PATCH ENUMS MODULE BEFORE OTHER IMPORTS ---
try:
    # Import the enums module directly
    enums_spec = importlib.util.find_spec("app.db.models.enums")
    enums_module = importlib.util.module_from_spec(enums_spec)
    enums_spec.loader.exec_module(enums_module)

    # Add the alias for HardwareMaterial to point to HardwareMaterialEnum
    if hasattr(enums_module, "HardwareMaterialEnum"):
        logger.info(
            "Patching enums module: Adding alias HardwareMaterial -> HardwareMaterialEnum"
        )
        enums_module.HardwareMaterial = enums_module.HardwareMaterialEnum
        # Make sure HardwareMaterial is also available as a global
        sys.modules["HardwareMaterial"] = enums_module.HardwareMaterialEnum

        # Also add this to the global namespace to avoid confusion
        HardwareMaterialEnum = enums_module.HardwareMaterialEnum

    # Register our patched module
    sys.modules["app.db.models.enums"] = enums_module

    logger.info("Enums module patched successfully")
except Exception as e:
    logger.error(f"Failed to patch enums module: {e}")
    sys.exit(1)

# --- Imports (after path setup and patching) ---
try:
    from app.db.session import (
        SessionLocal,
        engine,
        EncryptionManager,
        use_sqlcipher,
        init_db,
    )
    from app.core.config import settings
    from app.db.models.base import Base
    from app.db import models
    from app.db.models import (
        Customer,
        Supplier,
        Material,
        LeatherMaterial,
        HardwareMaterial,
        SuppliesMaterial,
        Tool,
        StorageLocation,
        StorageCell,
        StorageAssignment,
        ProjectTemplate,
        DocumentationCategory,
        DocumentationResource,
        PickingList,
        PickingListItem,
        ToolMaintenance,
        ToolCheckout,
        User,
        Project,
        ProjectComponent,
        Sale,
        SaleItem,
        PurchaseItem,
        Purchase,
        Pattern,
        TimelineTask,
        Component,
        Role,
        Product,
        Permission,
    )

    # Import the enums module (already patched above)
    from app.db.models import enums
    from app.core.security import get_password_hash

    # Import specific enum types to avoid confusion with model classes
    from app.db.models.enums import (
        MaterialType,
        LeatherType,
        HardwareType,
        HardwareMaterialEnum,
        HardwareFinish,
        LeatherFinish,
        InventoryStatus,
        MeasurementUnit,
        ProjectType,
        SaleStatus,
        FileType,
        SkillLevel,
        StorageLocationType,
        StorageLocationStatus,
        CustomerStatus,
        CustomerTier,
        CustomerSource,
        SupplierStatus,
        PaymentStatus,
        FulfillmentStatus,
    )
except ImportError as e:
    logger.error(f"Error importing application modules: {e}", file=sys.stderr)
    logger.error(
        "Please ensure you are running this script from the project root directory"
    )
    logger.error("and that all dependencies are installed in your virtual environment.")
    logger.error("Example command: python -m scripts.setup_database --reset --seed")
    sys.exit(1)


# --- Helper Functions ---


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


# --- Command Line Argument Parsing ---


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Set up the HideSync database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:\n  python -m scripts.setup_database --reset --seed",
    )
    parser.add_argument(
        "--seed", action="store_true", help="Seed the database with initial data"
    )
    parser.add_argument(
        "--seed-file",
        type=str,
        default="app/db/seed_data.json",
        help="Path to the seed data JSON file (relative to project root or absolute)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset the database (delete and recreate the encrypted file)",
    )
    return parser.parse_args()


# --- Database Operations ---


def reset_database():
    """Reset the database by deleting the existing database file."""
    db_path = os.path.abspath(settings.DATABASE_PATH)

    if use_sqlcipher:
        logger.info(f"Using SQLCipher encrypted database: {db_path}")
    else:
        logger.info(f"Using standard SQLite database: {db_path}")

    logger.info(f"Resetting database at {db_path}")

    # Delete existing database file if it exists
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
            logger.info(f"Deleted existing database file: {db_path}")
        except Exception as e:
            logger.error(f"Error deleting database file: {str(e)}")
            return False

    # For SQLCipher databases, create an empty encrypted database
    if use_sqlcipher:
        if not EncryptionManager.create_new_encrypted_database(db_path):
            logger.error("Failed to create empty encrypted database file")
            return False
        logger.info("Empty encrypted database file created successfully")

    logger.info("Database reset completed.")
    return True


def initialize_database_schema():
    """Initialize database schema using the appropriate method based on encryption settings."""
    logger.info("Creating database tables...")

    # Log registered models
    logger.info(f"Engine details: {engine}")
    logger.info("Registered models (from Base.metadata):")
    table_names = sorted(Base.metadata.tables.keys())
    if not table_names:
        logger.warning(
            "No tables found in Base.metadata. Ensure models are imported correctly."
        )

    for table_name in table_names:
        logger.info(f"- {table_name}")

    # Using the improved approach from our updated session.py
    if use_sqlcipher:
        logger.info("Using SQLCipher mode - calling specialized init_db function")
        success = init_db()
        if not success:
            logger.error("Database schema initialization failed.")
            return False
        logger.info("Database schema successfully initialized with SQLCipher")
        return True
    else:
        # For non-encrypted databases, use the standard SQLAlchemy approach
        try:
            logger.info("Using standard SQLite mode - calling create_all")
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created successfully")
            return True
        except Exception as e:
            logger.error(f"Error creating database tables: {str(e)}")
            logger.error(f"Detailed create_all error: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return False


# --- Database Seeding (Keep all your existing seeding functionality) ---


def get_enum_class_for_field(entity_type: str, field_name: str) -> Optional[Type[Enum]]:
    """
    Determines the correct Enum class based on the entity type and field name.
    This function centralizes the logic for resolving which enum to use.
    """
    # General mappings
    if field_name == "unit":
        return enums.MeasurementUnit
    if field_name == "skill_level":
        return enums.SkillLevel
    if field_name == "project_type":
        return enums.ProjectType
    if field_name == "file_type":
        return enums.FileType
    if field_name == "item_type":
        return enums.InventoryItemType
    if field_name == "transaction_type":
        return enums.InventoryTransactionType
    if field_name == "component_type":
        return enums.ComponentType
    if field_name == "category" and entity_type == "tools":
        return enums.ToolCategory
    if field_name == "type" and entity_type == "storage_locations":
        return enums.StorageLocationType

    # Status fields (context-dependent)
    if field_name == "status":
        if entity_type == "suppliers":
            return enums.SupplierStatus
        if entity_type == "customers":
            return enums.CustomerStatus
        if entity_type == "materials":
            return enums.InventoryStatus
        if entity_type == "tools":
            return enums.ToolStatus
        if entity_type == "projects":
            return enums.ProjectStatus
        if entity_type == "sales":
            return enums.SaleStatus
        if entity_type == "purchases":
            return enums.PurchaseStatus
        if entity_type == "picking_lists":
            return enums.PickingListStatus
        if entity_type == "picking_list_items":
            return enums.PickingListStatus  # Use PickingList status for items too
        if entity_type == "tool_checkouts":
            return enums.ToolStatus
        if entity_type == "tool_maintenance":
            return (
                enums.ToolMaintenanceStatus
                if hasattr(enums, "ToolMaintenanceStatus")
                else None
            )
        if entity_type == "storage_locations":
            return enums.StorageLocationStatus
        if entity_type == "timeline_tasks":
            return enums.ProjectStatus  # Use ProjectStatus for timeline tasks

        logger.warning(
            f"Generic 'status' field found for entity '{entity_type}'. Attempting InventoryStatus as fallback."
        )
        return enums.InventoryStatus  # Fallback

    # Payment/Fulfillment Status
    if field_name == "payment_status":
        return enums.PaymentStatus
    if field_name == "fulfillment_status":
        return enums.FulfillmentStatus

    # Material specific fields
    if entity_type == "materials":
        if field_name == "material_type":
            return enums.MaterialType
        if field_name == "leather_type":
            return enums.LeatherType
        if field_name == "finish":
            return enums.LeatherFinish
        if field_name == "quality":
            return enums.MaterialQualityGrade
        if field_name == "animal_source":
            return enums.LeatherType
        if field_name == "hardware_type":
            return enums.HardwareType
        # Now this should work better since we patched the module
        if field_name == "hardware_material":
            return enums.HardwareMaterialEnum  # Use HardwareMaterialEnum directly
        if field_name == "hardware_finish":
            return enums.HardwareFinish

    # Customer specific
    if entity_type == "customers":
        if field_name == "tier":
            return enums.CustomerTier
        if field_name == "source":
            return enums.CustomerSource

    return None


# Add a helper function to properly look up enum members by value
def get_enum_member_by_value(enum_class, value_str):
    """
    Find an enum member with a matching value, properly handling string comparisons.

    Args:
        enum_class: The enum class to search
        value_str: The string value to match against enum values

    Returns:
        The enum member if found, None otherwise
    """
    if not enum_class or not value_str:
        return None

    # If value_str is already an Enum object, just return it
    if isinstance(value_str, Enum):
        return value_str

    # Handle special cases for known enum mismatches
    if enum_class.__name__ == "LeatherFinish" and value_str.upper() == "PULL_UP":
        # Look for WAX_PULL_UP or OIL_PULL_UP as alternatives
        try:
            return enum_class["WAX_PULL_UP"]  # Try wax pull-up first
        except (KeyError, AttributeError):
            try:
                return enum_class["OIL_PULL_UP"]  # Then try oil pull-up
            except (KeyError, AttributeError):
                pass

    # For PickingListItemStatus and TimelineTasks, handle common case differences
    if value_str.lower() == "complete" and "COMPLETED" in enum_class.__members__:
        return enum_class["COMPLETED"]
    if value_str.lower() == "pending" and "PENDING" in enum_class.__members__:
        return enum_class["PENDING"]
    if value_str.lower() == "in_progress" and "IN_PROGRESS" in enum_class.__members__:
        return enum_class["IN_PROGRESS"]
    if value_str.lower() == "planning" and "PLANNING" in enum_class.__members__:
        return enum_class["PLANNING"]

    # First try direct lookup by uppercase name (common in JSON data)
    try:
        return enum_class[value_str.upper()]
    except (KeyError, AttributeError):
        pass

    # Then try direct lookup by exact name (for case-sensitive enums)
    try:
        return enum_class[value_str]
    except (KeyError, AttributeError):
        pass

    # Then try to match by value (case-insensitive)
    value_lower = value_str.lower()
    for member in enum_class:
        member_value = member.value
        # Handle string values with case-insensitive comparison
        if isinstance(member_value, str) and member_value.lower() == value_lower:
            return member

    # Try to match by similar name (useful for suffixed/prefixed enum values)
    for member_name in enum_class.__members__:
        if value_str.upper() in member_name or member_name in value_str.upper():
            return enum_class[member_name]

    # No match found
    logger.warning(f"Could not find enum value '{value_str}' in {enum_class.__name__}")
    return None


def seed_database(seed_file: str) -> bool:
    """
    Seed the database using a JSON file.
    Handles key conversion, overrides, and relationship linking.
    For SQLCipher databases, uses direct SQL operations instead of SQLAlchemy.
    """
    logger.info(f"Attempting to load seed data from: {seed_file}")
    try:
        with open(seed_file, "r", encoding="utf-8") as f:
            seed_data: Dict[str, List[Dict[str, Any]]] = json.load(f)
        logger.info(
            f"Successfully loaded seed data. Top-level keys: {list(seed_data.keys())}"
        )
    except FileNotFoundError:
        logger.error(f"Seed data file not found: {seed_file}")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {seed_file}: {e}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred while reading {seed_file}: {e}")
        return False

    # Define the order in which entities should be created to respect FK constraints
    entities_order = [
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

    # For SQLCipher databases, use direct SQL operations
    if use_sqlcipher:
        logger.info("Using direct SQLCipher seeding approach for encrypted database")
        return seed_with_direct_sqlcipher(seed_data, entities_order)
    else:
        # For non-encrypted databases, use SQLAlchemy (original approach)
        logger.info("Using SQLAlchemy seeding approach for standard database")
        return seed_with_sqlalchemy(seed_data, entities_order)


def seed_with_direct_sqlcipher(seed_data, entities_order):
    """Seed database using direct SQLCipher connection, bypassing SQLAlchemy."""
    db_path = os.path.abspath(settings.DATABASE_PATH)
    conn = None
    cursor = None

    try:
        # Get SQLCipher module
        sqlcipher = EncryptionManager.get_sqlcipher_module()
        if not sqlcipher:
            logger.error("SQLCipher module not available")
            return False

        # Establish direct connection
        conn = sqlcipher.connect(db_path)
        cursor = conn.cursor()

        # Configure SQLCipher parameters
        key = EncryptionManager.get_key()
        if not key:
            logger.error("No encryption key available")
            return False

        # Set pragmas
        key_pragma_value = EncryptionManager.format_key_for_pragma()
        cursor.execute(f"PRAGMA key = {key_pragma_value};")
        cursor.execute("PRAGMA cipher_page_size = 4096;")
        cursor.execute("PRAGMA kdf_iter = 256000;")
        cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
        cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Dictionary to track created entity IDs (for handling FK relationships)
        entity_ids = {}

        # Process entities in the correct order
        for entity_type in entities_order:
            if entity_type not in seed_data:
                continue

            logger.info(f"--- Seeding {entity_type} ---")
            entity_count = 0

            for idx, item_data in enumerate(seed_data[entity_type], 1):
                try:
                    # 1. Convert camelCase to snake_case
                    data = decamelize_keys(item_data)

                    # 2. Apply entity-specific overrides
                    if entity_type in overrides_by_entity:
                        data = apply_overrides(data, overrides_by_entity[entity_type])

                    # 3. Convert date strings to datetime objects
                    for key, value in list(data.items()):
                        if isinstance(value, str) and (
                            key.endswith("_date")
                            or key.endswith("_at")
                            or key == "date"
                        ):
                            try:
                                if value.endswith("Z"):
                                    value = value[:-1] + "+00:00"
                                data[key] = datetime.fromisoformat(value).isoformat()
                            except ValueError:
                                logger.warning(
                                    f"Invalid date format for {key}: {value}"
                                )
                                data[key] = None

                    # 4. Handle enum values
                    for key, value in list(data.items()):
                        if isinstance(value, str):
                            enum_class = get_enum_class_for_field(entity_type, key)
                            if enum_class:
                                enum_value = get_enum_member_by_value(enum_class, value)
                                if enum_value:
                                    # For direct SQL, store the string value of the enum
                                    data[key] = enum_value.value

                    # 5. Resolve foreign key references using entity_ids
                    for key in list(data.keys()):
                        if key.endswith("_id") and isinstance(data[key], int):
                            original_id = data[key]
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
                                data[key] = entity_ids[fk_entity_type][original_id]
                                logger.debug(
                                    f"Mapped FK {key}: {original_id} -> {data[key]}"
                                )

                    # 6. Generate and execute INSERT statement
                    if data:
                        # Remove any keys that aren't actual columns
                        # First get the schema for this table
                        cursor.execute(f"PRAGMA table_info({entity_type})")
                        columns_info = cursor.fetchall()
                        valid_columns = [col[1] for col in columns_info]

                        # Filter data to only include valid columns
                        filtered_data = {}
                        for key, value in data.items():
                            if key in valid_columns:
                                filtered_data[key] = value
                            else:
                                logger.debug(
                                    f"Removed field '{key}' not in {entity_type} table schema"
                                )

                        if filtered_data:
                            columns = list(filtered_data.keys())
                            values = list(filtered_data.values())

                            # Build and execute INSERT statement
                            placeholders = ", ".join(["?"] * len(columns))
                            sql = f"INSERT INTO {entity_type} ({', '.join(columns)}) VALUES ({placeholders})"

                            cursor.execute(sql, values)

                            # Get the ID of the inserted entity
                            cursor.execute("SELECT last_insert_rowid()")
                            new_id = cursor.fetchone()[0]

                            # Store the ID for future FK references
                            if entity_type not in entity_ids:
                                entity_ids[entity_type] = {}
                            entity_ids[entity_type][idx] = new_id

                            entity_count += 1
                            logger.debug(
                                f"Inserted {entity_type} at index {idx} with ID {new_id}"
                            )
                        else:
                            logger.warning(
                                f"Skipping {entity_type} at index {idx}: no valid columns found"
                            )

                except Exception as e:
                    logger.error(f"Error creating {entity_type} at index {idx}: {e}")
                    logger.error(f"Data: {item_data}")
                    logger.exception("Details:")
                    conn.rollback()
                    raise

            logger.info(f"Created {entity_count} {entity_type} records")

        # Commit all changes
        conn.commit()
        logger.info("Database seeding completed successfully")
        return True

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Fatal error during seeding: {e}")
        logger.exception("Details:")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def seed_with_sqlalchemy(seed_data, entities_order):
    """Original SQLAlchemy-based seeding implementation (for non-encrypted databases)."""

    # This section should contain your original SQLAlchemy-based seeding code
    # Here's a simplified example:

    db = SessionLocal()
    try:
        # Cache: { "entity_type": { json_index: db_id } }
        entity_ids: Dict[str, Dict[int, Any]] = {}

        for entity_type in entities_order:
            if entity_type in seed_data:
                logger.info(f"--- Seeding {entity_type} ---")
                entities_data = seed_data[entity_type]

                if not isinstance(entities_data, list):
                    logger.warning(
                        f"Seed data for '{entity_type}' is not a list. Skipping."
                    )
                    continue

                # Process each entity one at a time
                for idx, item_data in enumerate(entities_data, 1):
                    if not isinstance(item_data, dict):
                        logger.warning(
                            f"Item at index {idx} for '{entity_type}' is not a dictionary. Skipping."
                        )
                        continue

                    try:
                        # 1. Get the model class
                        model = model_map.get(entity_type)
                        if not model:
                            logger.warning(
                                f"Unknown entity type '{entity_type}'. Skipping."
                            )
                            continue

                        # 2. Decamelize keys and apply overrides
                        data = decamelize_keys(item_data)
                        if entity_type in overrides_by_entity:
                            data = apply_overrides(
                                data, overrides_by_entity[entity_type]
                            )

                        # 3. Create and add the entity
                        entity = model(**data)
                        db.add(entity)
                        db.flush()

                        # 4. Store the new ID in our cache
                        if entity_type not in entity_ids:
                            entity_ids[entity_type] = {}
                        entity_ids[entity_type][idx] = entity.id

                        logger.debug(f"Created {entity_type} with ID {entity.id}")

                    except Exception as e:
                        logger.error(
                            f"Error creating {entity_type} at index {idx}: {e}"
                        )
                        logger.error(f"Data: {item_data}")
                        logger.exception("Details:")
                        db.rollback()
                        raise

        # Commit all changes
        db.commit()
        logger.info("Database seeding completed successfully")
        return True

    except Exception as e:
        db.rollback()
        logger.error(f"Fatal error during seeding: {e}")
        logger.exception("Details:")
        return False
    finally:
        db.close()


def seed_with_direct_sqlcipher(seed_data):
    """Seed database using direct SQLCipher connection, bypassing SQLAlchemy."""
    db_path = os.path.abspath(settings.DATABASE_PATH)
    conn = None
    cursor = None

    try:
        # Get SQLCipher module
        sqlcipher = EncryptionManager.get_sqlcipher_module()
        if not sqlcipher:
            logger.error("SQLCipher module not available")
            return False

        # Establish direct connection
        conn = sqlcipher.connect(db_path)
        cursor = conn.cursor()

        # Configure SQLCipher parameters
        key_pragma_value = EncryptionManager.format_key_for_pragma()
        cursor.execute(f"PRAGMA key = {key_pragma_value};")
        cursor.execute("PRAGMA cipher_page_size = 4096;")
        cursor.execute("PRAGMA kdf_iter = 256000;")
        cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
        cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Dictionary to track created entity IDs (for handling FK relationships)
        entity_ids = {}

        # Process entities in the correct order
        for entity_type in entities_order:
            if entity_type not in seed_data:
                continue

            logger.info(f"--- Seeding {entity_type} ---")
            for idx, item_data in enumerate(seed_data[entity_type], 1):
                try:
                    # 1. Process the data (convert camelCase, apply mappings)
                    data = process_entity_data(entity_type, item_data, entity_ids)

                    # 2. Generate INSERT statement
                    if data:
                        columns = list(data.keys())
                        values = list(data.values())

                        # Convert Python types to SQLite compatible types
                        converted_values = []
                        for value in values:
                            if isinstance(value, datetime):
                                converted_values.append(value.isoformat())
                            elif isinstance(value, Enum):
                                converted_values.append(value.value)
                            elif value is None:
                                converted_values.append(None)
                            else:
                                converted_values.append(str(value))

                        # Build and execute INSERT statement
                        placeholders = ", ".join(["?"] * len(columns))
                        sql = f"INSERT INTO {entity_type} ({', '.join(columns)}) VALUES ({placeholders})"

                        cursor.execute(sql, converted_values)

                        # Get the ID of the inserted entity
                        cursor.execute("SELECT last_insert_rowid()")
                        new_id = cursor.fetchone()[0]

                        # Store the ID for future FK references
                        if entity_type not in entity_ids:
                            entity_ids[entity_type] = {}
                        entity_ids[entity_type][idx] = new_id

                        logger.debug(
                            f"Inserted {entity_type} at index {idx} with ID {new_id}"
                        )
                    else:
                        logger.warning(
                            f"Skipping {entity_type} at index {idx}: data processing resulted in empty data"
                        )

                except Exception as e:
                    logger.error(f"Error creating {entity_type} at index {idx}: {e}")
                    logger.error(f"Data: {item_data}")
                    logger.exception("Details:")
                    raise

        # Commit all changes
        conn.commit()
        logger.info("Database seeding completed successfully")
        return True

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Fatal error during seeding: {e}")
        logger.exception("Details:")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def process_entity_data(entity_type, item_data, entity_ids):
    """Process entity data for direct SQL insertion."""
    # 1. Convert camelCase to snake_case
    data = decamelize_keys(item_data)

    # 2. Apply entity-specific overrides
    if entity_type in overrides_by_entity:
        data = apply_overrides(data, overrides_by_entity[entity_type])

    # 3. Handle special entity types
    if entity_type == "materials":
        material_type = data.get("material_type", "").lower()
        data = map_material_attributes(data, material_type)

    # 4. Convert date strings to datetime objects
    for key, value in list(data.items()):
        if isinstance(value, str) and (
            key.endswith("_date") or key.endswith("_at") or key == "date"
        ):
            try:
                if value.endswith("Z"):
                    value = value[:-1] + "+00:00"
                data[key] = datetime.fromisoformat(value)
            except ValueError:
                logger.warning(f"Invalid date format for {key}: {value}")
                data[key] = None

    # 5. Resolve foreign key references using entity_ids
    for key in list(data.keys()):
        if key.endswith("_id") and isinstance(data[key], int):
            original_id = data[key]
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
                data[key] = entity_ids[fk_entity_type][original_id]
                logger.debug(f"Mapped FK {key}: {original_id} -> {data[key]}")

    # 6. Handle enum values
    for key, value in list(data.items()):
        if isinstance(value, str):
            enum_class = get_enum_class_for_field(entity_type, key)
            if enum_class:
                enum_value = get_enum_member_by_value(enum_class, value)
                if enum_value:
                    # For direct SQL, store the string value of the enum
                    data[key] = enum_value.value

    return data


def seed_with_sqlalchemy(seed_data):
    """Original seeding implementation using SQLAlchemy ORM."""
    db = SessionLocal()
    try:
        # Original SQLAlchemy seeding code...
        # Cache: { "entity_type": { json_index: db_id } }
        entity_ids: Dict[str, Dict[int, Any]] = {}

        for entity_type in entities_order:
            if entity_type in seed_data:
                logger.info(f"--- Seeding {entity_type} ---")
                entities_data = seed_data[entity_type]

                if not isinstance(entities_data, list):
                    logger.warning(
                        f"Seed data for '{entity_type}' is not a list. Skipping."
                    )
                    continue

                # ... rest of your original seeding code ...

        # Commit all changes
        db.commit()
        logger.info("Database seeding completed successfully")
        return True

    except Exception as e:
        db.rollback()
        logger.error(f"Fatal error during seeding: {e}")
        logger.exception("Details:")
        return False
    finally:
        db.close()


# --- Main Execution ---
def main():
    """Main function to orchestrate database setup."""
    args = parse_arguments()

    # Step 1: Reset database if requested
    if args.reset:
        if not reset_database():
            logger.error("Database reset failed, exiting.")
            sys.exit(1)
        else:
            logger.info("Database reset completed.")

    # Step 2: Initialize database schema
    if not initialize_database_schema():
        logger.error("Database schema initialization failed, exiting.")
        sys.exit(1)
    else:
        logger.info("Database schema initialization completed.")

    # Step 3: Seed database if requested
    if args.seed:
        seed_file_path_arg = args.seed_file
        if not os.path.isabs(seed_file_path_arg):
            resolved_path = project_root / seed_file_path_arg
            if resolved_path.exists():
                seed_file_path = str(resolved_path)
                logger.info(
                    f"Resolved seed file path relative to project root: {seed_file_path}"
                )
            else:
                logger.warning(
                    f"Seed file '{seed_file_path_arg}' not found relative to project root. Trying relative to CWD."
                )
                seed_file_path = seed_file_path_arg
        else:
            seed_file_path = seed_file_path_arg

        if not os.path.exists(seed_file_path):
            logger.error(f"Seed file not found at specified path: {seed_file_path}")
            sys.exit(1)

        logger.info(f"Starting database seeding using file: {seed_file_path}")
        if not seed_database(seed_file_path):
            logger.error("Database seeding failed, exiting.")
            sys.exit(1)
        else:
            logger.info("Database seeding completed.")

    logger.info("--- Database setup process finished successfully ---")


if __name__ == "__main__":
    main()
