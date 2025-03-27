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
    if hasattr(enums_module, 'HardwareMaterialEnum'):
        logger.info("Patching enums module: Adding alias HardwareMaterial -> HardwareMaterialEnum")
        enums_module.HardwareMaterial = enums_module.HardwareMaterialEnum
        # Make sure HardwareMaterial is also available as a global
        sys.modules['HardwareMaterial'] = enums_module.HardwareMaterialEnum

        # Also add this to the global namespace to avoid confusion
        HardwareMaterialEnum = enums_module.HardwareMaterialEnum

    # Register our patched module
    sys.modules['app.db.models.enums'] = enums_module

    logger.info("Enums module patched successfully")
except Exception as e:
    logger.error(f"Failed to patch enums module: {e}")
    sys.exit(1)

# --- Imports (after path setup and patching) ---
try:
    from app.db.session import SessionLocal, engine
    from app.core.config import settings
    from app.db.models.base import Base
    from app.db import models
    from app.db.models import (
        Customer, Supplier, Material, LeatherMaterial, HardwareMaterial,
        SuppliesMaterial, Tool, StorageLocation, StorageCell, StorageAssignment,
        ProjectTemplate, DocumentationCategory, DocumentationResource,
        PickingList, PickingListItem, ToolMaintenance, ToolCheckout, User,
        Project, ProjectComponent, Sale, SaleItem, PurchaseItem, Purchase,
        Pattern, TimelineTask, Component, Role, Product, Permission
    )
    # Import the enums module (already patched above)
    from app.db.models import enums
    from app.core.security import get_password_hash

    # Import specific enum types to avoid confusion with model classes
    from app.db.models.enums import (
        MaterialType, LeatherType, HardwareType, HardwareMaterialEnum,
        HardwareFinish, LeatherFinish, InventoryStatus, MeasurementUnit,
        ProjectType, SaleStatus, FileType, SkillLevel, StorageLocationType,
        StorageLocationStatus, CustomerStatus, CustomerTier, CustomerSource,
        SupplierStatus, PaymentStatus, FulfillmentStatus
    )
except ImportError as e:
    logger.error(f"Error importing application modules: {e}", file=sys.stderr)
    logger.error("Please ensure you are running this script from the project root directory")
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
        f"Mapping attributes for material_type '{material_type_upper}'. Keys before mapping: {list(result.keys())}")

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
        epilog="Example:\n  python -m scripts.setup_database --reset --seed"
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

def create_db_directory(db_path: str):
    """Create the database directory if it doesn't exist."""
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        logger.info(f"Creating database directory: {db_dir}")
        os.makedirs(db_dir, exist_ok=True)


def reset_database(db_path: str, encryption_key: Optional[str]) -> bool:
    """Reset the database by deleting and recreating the file."""
    logger.info(f"Resetting database at {db_path}")
    if os.path.exists(db_path):
        try:
            os.unlink(db_path)
            logger.info(f"Deleted existing database file: {db_path}")
        except Exception as e:
            logger.error(f"Error deleting database file: {str(e)}")
            return False

    if settings.USE_SQLCIPHER:
        if not encryption_key:
            logger.error("SQLCipher is enabled but no encryption key found. Cannot reset.")
            return False
        try:
            try:
                import pysqlcipher3.dbapi2 as sqlcipher
            except ImportError:
                logger.error("SQLCipher libraries not found. Please install pysqlcipher3.")
                return False

            conn = sqlcipher.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA key = '{encryption_key}'")
            cursor.execute("PRAGMA cipher_page_size = 4096")
            cursor.execute("PRAGMA kdf_iter = 64000")
            cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512")
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute("CREATE TABLE _test_table (id INTEGER PRIMARY KEY)")
            cursor.execute("DROP TABLE _test_table")
            conn.commit()
            cursor.close()
            conn.close()
            logger.info("Empty encrypted database file created successfully")
            return True
        except Exception as e:
            logger.error(f"Error creating new encrypted database file: {str(e)}")
            if os.path.exists(db_path):
                try:
                    os.unlink(db_path)
                except:
                    pass
            return False
    else:
        create_db_directory(db_path)
        logger.info("Standard SQLite database file will be created by SQLAlchemy if it doesn't exist.")
        return True


def initialize_database_schema() -> bool:
    """Initialize database schema using SQLAlchemy models."""
    logger.info("Creating database tables...")
    try:
        logger.info(f"Engine details: {engine}")
        logger.info("Registered models (from Base.metadata):")
        table_names = sorted(Base.metadata.tables.keys())
        if not table_names:
            logger.warning("No tables found in Base.metadata. Ensure models are imported correctly.")

        for table_name in table_names:
            logger.info(f"- {table_name}")

        try:
            Base.metadata.create_all(bind=engine)
        except Exception as create_error:
            logger.error(f"Detailed create_all error: {create_error}")
            raise

        logger.info("Database tables created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


# --- Database Seeding ---

def get_enum_class_for_field(entity_type: str, field_name: str) -> Optional[Type[Enum]]:
    """
    Determines the correct Enum class based on the entity type and field name.
    This function centralizes the logic for resolving which enum to use.
    """
    # General mappings
    if field_name == "unit": return enums.MeasurementUnit
    if field_name == "skill_level": return enums.SkillLevel
    if field_name == "project_type": return enums.ProjectType
    if field_name == "file_type": return enums.FileType
    if field_name == "item_type": return enums.InventoryItemType
    if field_name == "transaction_type": return enums.InventoryTransactionType
    if field_name == "component_type": return enums.ComponentType
    if field_name == "category" and entity_type == "tools": return enums.ToolCategory
    if field_name == "type" and entity_type == "storage_locations": return enums.StorageLocationType

    # Status fields (context-dependent)
    if field_name == "status":
        if entity_type == "suppliers": return enums.SupplierStatus
        if entity_type == "customers": return enums.CustomerStatus
        if entity_type == "materials": return enums.InventoryStatus
        if entity_type == "tools": return enums.ToolStatus
        if entity_type == "projects": return enums.ProjectStatus
        if entity_type == "sales": return enums.SaleStatus
        if entity_type == "purchases": return enums.PurchaseStatus
        if entity_type == "picking_lists": return enums.PickingListStatus
        if entity_type == "picking_list_items": return enums.PickingListStatus  # Use PickingList status for items too
        if entity_type == "tool_checkouts": return enums.ToolStatus
        if entity_type == "tool_maintenance": return enums.ToolMaintenanceStatus if hasattr(enums,
                                                                                            'ToolMaintenanceStatus') else None
        if entity_type == "storage_locations": return enums.StorageLocationStatus
        if entity_type == "timeline_tasks": return enums.ProjectStatus  # Use ProjectStatus for timeline tasks

        logger.warning(
            f"Generic 'status' field found for entity '{entity_type}'. Attempting InventoryStatus as fallback.")
        return enums.InventoryStatus  # Fallback

    # Payment/Fulfillment Status
    if field_name == "payment_status": return enums.PaymentStatus
    if field_name == "fulfillment_status": return enums.FulfillmentStatus

    # Material specific fields
    if entity_type == "materials":
        if field_name == "material_type": return enums.MaterialType
        if field_name == "leather_type": return enums.LeatherType
        if field_name == "finish": return enums.LeatherFinish
        if field_name == "quality": return enums.MaterialQualityGrade
        if field_name == "animal_source": return enums.LeatherType
        if field_name == "hardware_type": return enums.HardwareType
        # Now this should work better since we patched the module
        if field_name == "hardware_material": return enums.HardwareMaterialEnum  # Use HardwareMaterialEnum directly
        if field_name == "hardware_finish": return enums.HardwareFinish

    # Customer specific
    if entity_type == "customers":
        if field_name == "tier": return enums.CustomerTier
        if field_name == "source": return enums.CustomerSource

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
        logger.error(
            f"An unexpected error occurred while reading {seed_file}: {e}"
        )
        return False

    # Define custom key overrides per entity type (JSON key -> Model attribute name)
    overrides_by_entity = {
        "materials": {
            "cost": "cost_price",
            "price": "price",
            "materialType": "material_type",
            "animalSource": "animal_source",
            "storageLocation": "storage_location_id",
            "hardwareType": "hardware_type",
            "hardwareMaterial": "hardware_material",
            "suppliesMaterialType": "supplies_material_type",
            "threadThickness": "thread_thickness",
            "materialComposition": "material_composition",
            "applicationMethod": "application_method",
        },
        "sales": {
            "createdat": "created_at",
            "paymentstatus": "payment_status",
            "fulfillmentstatus": "fulfillment_status",
            "depositamount": "deposit_amount",
            "customerid": "customer_id",
        },
        "purchases": {
            "supplierid": "supplier_id",
            "deliveryDate": "delivery_date",
        },
        "tools": {
            "supplierid": "supplier_id",
            "purchasePrice": "purchase_price",
            "purchaseDate": "purchase_date",
            "serialNumber": "serial_number",
            "maintenanceInterval": "maintenance_interval",
        },
        "tool_maintenance": {
            "toolId": "tool_id",
            "toolName": "tool_name",
            "maintenanceType": "maintenance_type",
            "performedBy": "performed_by",
            "conditionBefore": "condition_before",
            "conditionAfter": "condition_after",
            "nextDate": "next_date",
        },
        "tool_checkouts": {
            "toolId": "tool_id",
            "toolName": "tool_name",
            "checkedOutBy": "checked_out_by",
            "checkedOutDate": "checked_out_date",
            "dueDate": "due_date",
            "projectId": "project_id",
            "projectName": "project_name",
            "conditionBefore": "condition_before",
            "conditionAfter": "condition_after",
        },
        "storage_assignments": {
            "materialId": "material_id",
            "materialType": "material_type",
            "storageId": "storage_location_id",
            "assignedBy": "assigned_by",
        },
        "storage_cells": {
            "storageId": "storage_location_id",
        },
        "picking_list_items": {
            "picking_list_id": "picking_list_id",
            "material_id": "material_id",
            "quantity_ordered": "quantity_ordered",
            "quantity_picked": "quantity_picked",
        },
        "picking_lists": {
            "project_id": "project_id",
            "assignedTo": "assigned_to",
        },
        "purchase_items": {
            "purchase_id": "purchase_id",
            "itemType": "item_type",
            "materialType": "material_type",
        },
        "sale_items": {
            "sale_id": "sale_id",
        },
        "timeline_tasks": {
            "project_id": "project_id",
            "startDate": "start_date",
            "endDate": "end_date",
            "isCriticalPath": "is_critical_path",
        },
        "project_components": {
            "project_id": "project_id",
            "componentType": "component_type",
        },
        "projects": {
            "startDate": "start_date",
            "dueDate": "due_date",
            "completionPercentage": "completion_percentage",
            "projectTemplateId": "project_template_id",
        },
        "project_templates": {
            "projectType": "project_type",
            "estimatedDuration": "estimated_duration",
            "estimatedCost": "estimated_cost",
            "isPublic": "is_public",
        },
        "patterns": {
            "skill_level": "skill_level",
            "projectType": "project_type",
            "fileType": "file_type",
            "filePath": "file_path",
            "isFavorite": "is_favorite",
            "estimatedTime": "estimated_time",
            "estimatedDifficulty": "estimated_difficulty",
            "authorName": "author_name",
            "isPublic": "is_public",
        },
        "documentation_resources": {
            "skill_level": "skill_level",
            "category": "category_slug",
        },
        "users": {
            "plain_password": "plain_password",
            "full_name": "full_name",
            "is_active": "is_active",
            "is_superuser": "is_superuser",
        },
        "roles": {
            "is_system_role": "is_system_role",
        },
        "suppliers": {
            "contact_name": "contact_name",
            "materialCategories": "material_categories",
            "leadTime": "lead_time",
        },
        "customers": {
            "company_name": "company_name",
        },
    }

    # Map entity type names (from JSON keys) to SQLAlchemy Model classes
    model_map = {
        "permissions": models.Permission,
        "roles": models.Role,
        "users": models.User,
        "documentation_categories": models.DocumentationCategory,
        "documentation_resources": models.DocumentationResource,
        "suppliers": models.Supplier,
        "customers": models.Customer,
        "storage_locations": models.StorageLocation,
        "storage_cells": models.StorageCell,
        "materials": models.Material,
        "tools": models.Tool,
        "tool_maintenance": models.ToolMaintenance,
        "tool_checkouts": models.ToolCheckout,
        "patterns": models.Pattern,
        "components": models.Component,
        "project_templates": models.ProjectTemplate,
        "projects": models.Project,
        "project_components": models.ProjectComponent,
        "timeline_tasks": models.TimelineTask,
        "sales": models.Sale,
        "sale_items": models.SaleItem,
        "purchases": models.Purchase,
        "purchase_items": models.PurchaseItem,
        "picking_lists": models.PickingList,
        "picking_list_items": models.PickingListItem,
        "storage_assignments": models.StorageAssignment,
        "products": models.Product,
    }

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

    # --- Nested create_entity function ---
    def create_entity(
            entity_type: str,
            item_data: Dict[str, Any],
            session,
            entity_ids: Dict[str, Dict[int, Any]],
            idx: int,
    ) -> Optional[Any]:
        """Creates a single entity instance, handling relationships."""

        model = model_map.get(entity_type)
        if not model:
            logger.warning(f"Unknown entity type '{entity_type}' in model_map. Skipping index {idx}.")
            return None

        entity = None
        data = {}
        data_for_init = {}

        try:
            # 1. Decamelize keys first
            data = decamelize_keys(item_data)

            # 2. Apply overrides defined in overrides_by_entity
            if entity_type in overrides_by_entity:
                data = apply_overrides(data, overrides_by_entity[entity_type])

            # 8. Pre-process specific field mappings for various entity types
            if entity_type == "projects":
                # Map or remove fields that don't exist in the Project model
                if "completion_percentage" in data:
                    # This field doesn't exist in the model - may be duplicating 'progress'
                    logger.info(f"Removing 'completion_percentage' field from project data (using 'progress' instead)")
                    data.pop("completion_percentage")

            if entity_type == "documentation_resources" and "category_slug" in data:
                category_identifier = data.pop("category_slug")
                if category_identifier:
                    related_category_slug = str(category_identifier).lower().replace("_", "-")
                    logger.debug(f"  Extracted category slug '{related_category_slug}' for resource index {idx}")

            if entity_type == "project_components":
                if "component_id" not in data or data["component_id"] is None:
                    comp_data = {}
                    for key in ["name", "description", "component_type", "pattern_id"]:
                        if key in data:
                            comp_data[key] = data.pop(key)
                    if "pattern_id" in comp_data and isinstance(comp_data["pattern_id"], int):
                        original_fk_index = comp_data["pattern_id"]
                        fk_entity_type = "patterns"
                        if fk_entity_type in entity_ids and original_fk_index in entity_ids[fk_entity_type]:
                            comp_data["pattern_id"] = entity_ids[fk_entity_type][original_fk_index]
                        else:
                            logger.warning(
                                f"    Could not map FK pattern_id index {original_fk_index} for dynamic Component (project_component index {idx}). Setting to None.")
                            comp_data["pattern_id"] = None

                    # Fix for component_type handling
                    if 'component_type' in comp_data and comp_data['component_type'] is not None:
                        # First check if it's a string that needs conversion to an enum
                        if isinstance(comp_data['component_type'], str):
                            try:
                                from app.db.models.enums import ComponentType
                                # Try to match by name
                                comp_type_str = comp_data['component_type'].upper()
                                # Use string name not enum auto value
                                if hasattr(ComponentType, comp_type_str):
                                    logger.info(f"Setting component_type from string '{comp_type_str}' to enum value")
                                    comp_data['component_type'] = comp_type_str.lower()
                                else:
                                    logger.warning(
                                        f"Invalid component_type name '{comp_type_str}'. Using 'PANEL' as default.")
                                    comp_data['component_type'] = 'panel'
                            except Exception as e:
                                logger.error(f"Error processing component_type: {e}")
                                comp_data['component_type'] = 'panel'  # Default fallback
                        # If it's an integer (auto value), convert to string name
                        elif isinstance(comp_data['component_type'], int):
                            try:
                                from app.db.models.enums import ComponentType
                                # Find the name corresponding to this value
                                for name, member in ComponentType.__members__.items():
                                    if member.value == comp_data['component_type']:
                                        logger.info(
                                            f"Converted component_type int {comp_data['component_type']} to name '{name}'")
                                        comp_data['component_type'] = name.lower()
                                        break
                                else:
                                    logger.warning(
                                        f"Could not find enum name for value {comp_data['component_type']}. Using 'panel' as default.")
                                    comp_data['component_type'] = 'panel'
                            except Exception as e:
                                logger.error(f"Error converting component_type int to name: {e}")
                                comp_data['component_type'] = 'panel'  # Default fallback

                    if comp_data.get("name"):
                        logger.info(f"  Dynamically creating Component for project_component index {idx}")
                        try:
                            new_comp = models.Component(**comp_data)
                            session.add(new_comp)
                            session.flush()
                            # Get the newly created component ID
                            component_id = new_comp.id
                            data["component_id"] = component_id
                            logger.info(f"    Created Component with ID: {component_id}")

                            # Store the created component in our entity_ids cache for future reference
                            if "components" not in entity_ids:
                                entity_ids["components"] = {}
                            # Map both the original index and the newly created ID to the same ID value
                            # This ensures it can be looked up by either
                            entity_ids["components"][idx] = component_id
                            entity_ids["components"][component_id] = component_id

                            logger.info(f"    Added Component ID {component_id} to entity_ids cache")
                        except Exception as comp_e:
                            logger.error(f"    Error creating associated Component: {comp_e}")
                            raise
                    else:
                        logger.warning(
                            f"  Missing component_id and insufficient data (name) for project_component index {idx}. Skipping.")
                        return None

            # 4. Convert date strings to datetime objects
            for key, value in data.items():
                # Check fields that end with _date or _at, plus the standalone "date" field
                if isinstance(value, str) and (key.endswith("_date") or key.endswith("_at") or key == "date"):
                    if value:
                        try:
                            # Handle 'Z' for UTC timezone indication
                            if value.endswith("Z"): value = value[:-1] + "+00:00"
                            data[key] = datetime.fromisoformat(value)
                            logger.debug(f"  Converted date string '{value}' to datetime for key '{key}'")
                        except ValueError:
                            logger.warning(
                                f"  Could not parse date string '{value}' for key '{key}' in {entity_type} index {idx}. Setting to None.")
                            data[key] = None
                    else:
                        data[key] = None  # Handle empty strings as None

            # 5. Map Foreign Keys using the entity_ids cache
            for key in list(data.keys()):  # Iterate over a copy of keys
                # Use original JSON index (idx) for lookup
                original_fk_index_or_value = data[key]
                # Only map if the value looks like an index (integer)
                # AND the key name suggests it's a foreign key ID
                if key.endswith("_id") and isinstance(original_fk_index_or_value, int):
                    original_fk_index = original_fk_index_or_value  # Keep name for clarity
                    fk_entity_type = None
                    # Define FK relationships (expand this mapping as needed)
                    # Map field name to the entity type it references
                    fk_map = {
                        "category_id": "documentation_categories",
                        "supplier_id": "suppliers",
                        "customer_id": "customers",
                        "project_id": "projects",
                        "project_template_id": "project_templates",
                        "component_id": "components",
                        "material_id": "materials",
                        "tool_id": "tools",
                        "pattern_id": "patterns",
                        "sale_id": "sales",
                        "purchase_id": "purchases",
                        "product_id": "products",
                        "storage_location_id": "storage_locations",
                        "picking_list_id": "picking_lists",
                        "user_id": "users",
                        "role_id": "roles",
                        "permission_id": "permissions",
                        "assigned_to": "users",
                        "checked_out_by": "users",
                        "performed_by": "users",
                    }
                    fk_entity_type = fk_map.get(key)

                    if fk_entity_type:
                        if fk_entity_type in entity_ids and original_fk_index in entity_ids[fk_entity_type]:
                            new_db_id = entity_ids[fk_entity_type][original_fk_index]
                            data[key] = new_db_id  # Update the data dict with the actual DB ID
                            logger.debug(f"  Mapped FK {key}: index {original_fk_index} -> DB ID {new_db_id}")
                        else:
                            logger.warning(
                                f"  Could not map FK {key}: index {original_fk_index} for {entity_type} index {idx}. Related entity '{fk_entity_type}' index not found in cache. Setting FK to None.")
                            data[key] = None

            # 6. Separate relationship data (for M2M linking after creation)
            relationship_keys_to_remove = []
            if entity_type == "users": relationship_keys_to_remove.append("roles")
            if entity_type == "roles": relationship_keys_to_remove.append("permissions")

            temp_relationship_data = {}
            for key in relationship_keys_to_remove:
                if key in data:
                    logger.debug(f"  Temporarily removing relationship key '{key}' before {entity_type} init.")
                    temp_relationship_data[key] = data.pop(key)

            # 7. Convert string values to Enum objects (temporary step)
            enum_objects = {}  # Store the actual enum objects temporarily
            for key, value in data.items():
                if isinstance(value, str):
                    enum_class = get_enum_class_for_field(entity_type, key)
                    if enum_class:
                        try:
                            # Extra logging for debugging hardware-related enums
                            if key in ['hardware_material', 'hardware_finish', 'hardware_type']:
                                logger.info(f"Resolving enum for {key} = '{value}' using {enum_class.__name__}")

                            # Attempt lookup by uppercase key name first (common in JSON)
                            try:
                                enum_member = enum_class[value.upper()]
                                enum_objects[key] = enum_member  # Store the object
                                logger.debug(
                                    f"  Resolved string '{value}' to Enum member {enum_member} for key '{key}'")
                            except KeyError:
                                # Use our helper function to find enum member by value
                                enum_member = get_enum_member_by_value(enum_class, value)
                                if enum_member:
                                    enum_objects[key] = enum_member  # Store the object
                                    logger.debug(
                                        f"  Resolved string '{value}' to Enum member {enum_member} for key '{key}' (value lookup)")
                                else:
                                    # Log a warning and skip setting this field if we can't resolve
                                    logger.warning(
                                        f"  Could not find Enum member for string '{value}' in {enum_class.__name__} for key '{key}' (entity: {entity_type}). Will skip this field.")
                                    data[key] = None  # Mark for skipping
                        except Exception as enum_e:
                            logger.error(f"  Error resolving string '{value}' to Enum for key '{key}': {enum_e}")
                            logger.error(f"  Class being used: {enum_class.__name__}")
                            data[key] = None  # Fallback to None on other errors

            # 8. Explicitly remove fields present in JSON but NOT in the model
            if entity_type == "documentation_resources":
                data.pop("author", None)  # Example: remove 'author' if not a model field

            # --- Prepare data for model initialization (Using actual enum objects) ---
            data_for_init = {}
            for key, value in data.items():
                if key in enum_objects:
                    # Use the actual enum object, not just its value
                    data_for_init[key] = enum_objects[key]
                    logger.debug(f"  Using Enum object '{data_for_init[key]}' for key '{key}' in model init")
                else:
                    # Skip fields that were marked for skipping (None after failed enum resolution)
                    if key in data and value is None and get_enum_class_for_field(entity_type, key) is not None:
                        logger.debug(f"  Skipping enum field '{key}' that couldn't be resolved")
                        continue
                    # Keep other values (like strings, numbers, mapped FKs, dates) as they are
                    data_for_init[key] = value

            # Final conversion to ensure ALL enum values and complex types are converted to strings
            # This ensures SQLCipher can handle all the data types
            final_clean_data = {}
            for key, value in data_for_init.items():
                if isinstance(value, Enum):
                    # If we still have an Enum object, convert it to its string value
                    logger.info(f"Converting enum object {value} to string '{value.value}' for {key}")
                    final_clean_data[key] = value.value
                elif isinstance(value, tuple):
                    # Handle tuple values (like those for fulfillment_status)
                    logger.info(f"Converting tuple {value} to string '{value[0] if value else None}' for {key}")
                    final_clean_data[key] = value[0] if value else None
                elif isinstance(value, (list, set)):
                    # Handle other collection types
                    logger.info(f"Converting {type(value).__name__} {value} to string for {key}")
                    final_clean_data[key] = next(iter(value)) if value else None
                else:
                    final_clean_data[key] = value

            # Replace data_for_init with final_clean_data
            data_for_init = final_clean_data

            # 9. Create the entity instance using data_for_init
            if entity_type == "users":
                plain_password = data_for_init.pop("plain_password", None)
                if plain_password:
                    data_for_init["hashed_password"] = get_password_hash(plain_password)
                else:
                    logger.warning(f"  Missing plain_password for user index {idx}. Hashed password will not be set.")
                data_for_init.setdefault("is_active", True)
                data_for_init.setdefault("is_superuser", False)
                entity = model(**data_for_init)

            elif entity_type == "materials":
                # Polymorphic identity should already be a lowercase string in data_for_init
                material_type_value = data_for_init.get("material_type")

                # Extract actual string value if it's an enum object (should be already handled above)
                material_type_identity = material_type_value

                # Ensure it's a string
                if not isinstance(material_type_identity, str):
                    material_type_identity = "material"  # Default fallback

                # Make it lowercase for consistency
                material_type_identity = material_type_identity.lower()

                logger.info(f"Creating material with material_type_identity: {material_type_identity}")

                # Apply type-specific attribute mapping
                data_for_init = map_material_attributes(data_for_init, material_type_identity)

                # Set defaults
                data_for_init.setdefault("reorder_point", 0.0)
                data_for_init.setdefault("cost_price", 0.0)
                data_for_init.setdefault("price", 0.0)
                data_for_init.setdefault("quantity", 0.0)

                # Ensure we're using the correct model class names - this is the key fix!
                # Direct, explicit references to avoid any confusion
                from app.db.models.material import Material, LeatherMaterial, HardwareMaterial, SuppliesMaterial

                if material_type_identity.lower() == 'hardware':
                    model_to_use = HardwareMaterial
                    logger.info(f"DIRECTLY USING HardwareMaterial class from app.db.models.material")
                elif material_type_identity.lower() == 'leather':
                    model_to_use = LeatherMaterial
                    logger.info(f"DIRECTLY USING LeatherMaterial class from app.db.models.material")
                elif material_type_identity.lower() == 'supplies':
                    model_to_use = SuppliesMaterial
                    logger.info(f"DIRECTLY USING SuppliesMaterial class from app.db.models.material")
                else:
                    model_to_use = Material
                    logger.info(f"DIRECTLY USING base Material class from app.db.models.material")

                # Double check we have a valid model class
                logger.info(f"Using model class: {model_to_use.__name__} (module: {model_to_use.__module__})")
                if hasattr(model_to_use, '__module__') and 'enums' in model_to_use.__module__:
                    logger.error(f"CRITICAL ERROR: Still using enum class: {model_to_use.__name__}")
                    from app.db.models.material import Material
                    model_to_use = Material

                if model_to_use == Material and material_type_identity not in model_class_map:
                    logger.warning(
                        f"  Unknown material_type '{material_type_identity}' for material index {idx}. Using base Material class.")
                    data_for_init["material_type"] = "material"  # Ensure base identity if falling back

                # Check required fields
                if data_for_init.get("unit") is None:
                    logger.error(f"  Missing or invalid required field 'unit' for material index {idx}. Cannot create.")
                    return None

                # Map hardware-specific finish to hardware_finish if needed
                if material_type_identity.lower() == 'hardware' and 'finish' in data_for_init:
                    logger.info(f"Moving finish to hardware_finish: {data_for_init['finish']}")
                    data_for_init['hardware_finish'] = data_for_init.pop('finish')

                # One more final check for enums
                final_data = {}
                for key, value in data_for_init.items():
                    if isinstance(value, Enum):
                        logger.info(f"Converting material field {key} from enum {value} to '{value.value}'")
                        final_data[key] = value.value
                    else:
                        final_data[key] = value

                # When we have to fallback to Material class, we need to remove
                # subclass-specific fields that aren't in the base Material model
                if hasattr(model_to_use, '__name__') and model_to_use.__name__ == 'Material':
                    # Remove subclass-specific fields
                    base_fields = [
                        'id', 'name', 'material_type', 'status', 'quantity', 'unit',
                        'quality', 'supplier_id', 'supplier', 'sku', 'description',
                        'reorder_point', 'supplier_sku', 'cost_price', 'price',
                        'last_purchased', 'storage_location', 'notes', 'thumbnail'
                    ]

                    # Create a clean dict with only fields in the base model
                    filtered_data = {}
                    for key, value in final_data.items():
                        if key in base_fields:
                            filtered_data[key] = value
                        else:
                            logger.info(f"Removing field '{key}' not in base Material model")

                    entity = model_to_use(**filtered_data)
                else:
                    try:
                        entity = model_to_use(**final_data)
                    except TypeError as e:
                        if 'EnumMeta.__call__()' in str(e):
                            logger.error(f"ERROR: Attempted to use enum class as model: {model_to_use}")
                            # Last resort fix - use the base Material class
                            logger.info("Falling back to Material model class")
                            from app.db.models.material import Material
                            model_to_use = Material

                            # Filter fields to only those in base Material
                            base_fields = [
                                'id', 'name', 'material_type', 'status', 'quantity', 'unit',
                                'quality', 'supplier_id', 'supplier', 'sku', 'description',
                                'reorder_point', 'supplier_sku', 'cost_price', 'price',
                                'last_purchased', 'storage_location', 'notes', 'thumbnail'
                            ]

                            filtered_data = {}
                            for key, value in final_data.items():
                                if key in base_fields:
                                    filtered_data[key] = value
                                else:
                                    logger.info(f"Removing field '{key}' not in base Material model")

                            entity = model_to_use(**filtered_data)
                        else:
                            raise

            elif entity_type == "sales":
                # Handle tuple value for fulfillment_status explicitly
                if "fulfillment_status" in data_for_init and isinstance(data_for_init["fulfillment_status"], tuple):
                    logger.info(
                        f"Converting sales fulfillment_status from tuple {data_for_init['fulfillment_status']} to string")
                    data_for_init["fulfillment_status"] = data_for_init["fulfillment_status"][0] if data_for_init[
                        "fulfillment_status"] else None

                # Set default values for required fields
                data_for_init.setdefault("subtotal", 0.0)
                data_for_init.setdefault("taxes", 0.0)
                data_for_init.setdefault("shipping", 0.0)
                data_for_init.setdefault("platform_fees", 0.0)
                data_for_init.setdefault("net_revenue", 0.0)

                # Create the sales entity
                entity = model(**data_for_init)

            elif entity_type == "purchases":
                # Double-check date field is a datetime object
                if "date" in data_for_init and isinstance(data_for_init["date"], str):
                    try:
                        logger.info(f"Converting purchase date string '{data_for_init['date']}' to datetime")
                        # Handle ISO format string with 'T'
                        if 'T' in data_for_init["date"]:
                            data_for_init["date"] = datetime.fromisoformat(data_for_init["date"].replace('Z', '+00:00'))
                        else:
                            data_for_init["date"] = datetime.fromisoformat(data_for_init["date"])
                    except ValueError:
                        logger.warning(
                            f"  Could not parse date string '{data_for_init['date']}'. Setting to current time.")
                        data_for_init["date"] = datetime.now()

                # Set default values for required fields
                data_for_init.setdefault("total", 0.0)

                # Create the purchases entity
                entity = model(**data_for_init)

            else:  # Default case for non-special entities
                entity = model(**data_for_init)

            # --- Post-creation processing (only if entity was successfully instantiated) ---
            if entity:
                # Final safety check for any remaining unsupported types
                for column in entity.__table__.columns:
                    attr_name = column.key
                    if hasattr(entity, attr_name):
                        attr_value = getattr(entity, attr_name)
                        if isinstance(attr_value, (tuple, list, set)) and attr_value:
                            logger.warning(
                                f"Converting collection type in entity attribute {attr_name} from {attr_value} to single value")
                            if isinstance(attr_value, (tuple, list)):
                                setattr(entity, attr_name, attr_value[0])
                            else:  # set
                                setattr(entity, attr_name, next(iter(attr_value)))
                        elif isinstance(attr_value, Enum):
                            logger.warning(
                                f"Converting enum in entity attribute {attr_name} from {attr_value} to '{attr_value.value}'")
                            setattr(entity, attr_name, attr_value.value)

                session.add(entity)
                try:
                    session.flush()  # Flush to get the ID
                    logger.debug(f"  Created {entity_type} instance (ID: {entity.id}) for index {idx}")
                except Exception as flush_error:
                    logger.error(f"Error during session.flush(): {flush_error}")
                    # Print all attributes to help debug
                    for attr_name in dir(entity):
                        if not attr_name.startswith('_') and attr_name not in ('metadata', 'registry'):
                            try:
                                attr_value = getattr(entity, attr_name)
                                logger.error(f"  {attr_name} = {attr_value} (type: {type(attr_value)})")
                            except:
                                pass
                    raise

                # 10. Store the new DB ID in the cache using the original JSON index
                if entity_type not in entity_ids: entity_ids[entity_type] = {}
                entity_ids[entity_type][idx] = entity.id  # Use idx (JSON index) as the key

                # 11. Handle relationships (M2M linking, etc.)
                if entity_type == "documentation_resources" and related_category_slug:
                    # Find category by slug
                    category_obj = session.query(DocumentationCategory).filter(
                        DocumentationCategory.slug == related_category_slug
                    ).first()
                    if category_obj:
                        # Check if the model uses a relationship list or a direct FK
                        if hasattr(entity, 'categories') and isinstance(getattr(entity, 'categories', None), list):
                            # Check if already linked (e.g., if category_id was also mapped)
                            if category_obj not in entity.categories:
                                entity.categories.append(category_obj)
                                logger.debug(
                                    f"    Appended category '{category_obj.name}' (Slug: {related_category_slug}) to resource '{entity.title}'")
                        elif hasattr(entity, 'category_id'):
                            if entity.category_id != category_obj.id:
                                logger.warning(
                                    f"    Mismatch or late linking for category_id on resource '{entity.title}'. Setting to {category_obj.id}.")
                                entity.category_id = category_obj.id  # Set direct FK if relationship list isn't used
                        else:
                            logger.warning(
                                f"    Could not determine how to link category '{category_obj.name}' to resource '{entity.title}'. Model lacks 'categories' list and 'category_id'.")
                    else:
                        logger.warning(
                            f"    Category slug '{related_category_slug}' not found for resource '{entity.title}'. Cannot link category.")

                if entity_type == "users" and "roles" in temp_relationship_data:
                    role_names = temp_relationship_data.get("roles", [])
                    if isinstance(role_names, list):
                        for role_name in role_names:
                            role_obj = session.query(Role).filter(Role.name == role_name).first()
                            if role_obj:
                                if hasattr(entity, 'roles') and isinstance(getattr(entity, 'roles', None), list):
                                    if role_obj not in entity.roles:  # Avoid duplicates
                                        entity.roles.append(role_obj)
                                        logger.debug(f"    Assigned role '{role_name}' to user '{entity.email}'")
                                else:
                                    logger.warning(f"    User model missing or invalid 'roles' relationship attribute.")
                            else:
                                logger.warning(f"    Role '{role_name}' not found for user '{entity.email}'.")
                    else:
                        logger.warning(f"   'roles' field for user index {idx} is not a list.")

                if entity_type == "roles" and "permissions" in temp_relationship_data:
                    permission_codes = temp_relationship_data.get("permissions", [])
                    if isinstance(permission_codes, list):
                        for perm_code in permission_codes:
                            perm_obj = session.query(Permission).filter(Permission.code == perm_code).first()
                            if perm_obj:
                                if hasattr(entity, 'permissions') and isinstance(getattr(entity, 'permissions', None),
                                                                                 list):
                                    if perm_obj not in entity.permissions:  # Avoid duplicates
                                        entity.permissions.append(perm_obj)
                                        logger.debug(f"    Assigned permission '{perm_code}' to role '{entity.name}'")
                                else:
                                    logger.warning(
                                        f"    Role model missing or invalid 'permissions' relationship attribute.")
                            else:
                                logger.warning(f"    Permission '{perm_code}' not found for role '{entity.name}'.")
                    else:
                        logger.warning(f"   'permissions' field for role index {idx} is not a list.")

            return entity  # Return created entity or None

        except TypeError as e:
            logger.error(f"  TypeError creating {entity_type} index {idx}: {e}")
            # Log the data that was actually passed to the constructor
            logger.error(f"    Data passed to model init: {data_for_init}")
            logger.error(f"    Original item data from JSON: {item_data}")
            raise  # Re-raise to stop the process and trigger rollback
        except Exception as e:
            logger.error(f"  Unexpected error during instance creation/processing for {entity_type} index {idx}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise  # Re-raise other exceptions too to stop and rollback

    # --- End of nested create_entity function ---

    # --- Main Seeding Loop ---
    session = None
    try:
        session = SessionLocal()
        # Cache: { "entity_type": { json_index: db_id } }
        entity_ids: Dict[str, Dict[int, Any]] = {}

        for entity_type in entities_order:
            if entity_type in seed_data:
                logger.info(f"--- Seeding {entity_type} ---")
                entities_data = seed_data[entity_type]

                if not isinstance(entities_data, list):
                    logger.warning(f"Seed data for '{entity_type}' is not a list. Skipping.")
                    continue

                # Use enumerate starting from 1 for JSON index
                for idx, item_data in enumerate(entities_data, 1):
                    if not isinstance(item_data, dict):
                        logger.warning(f"Item at index {idx} for '{entity_type}' is not a dictionary. Skipping.")
                        continue

                    try:
                        created_entity = create_entity(
                            entity_type, item_data, session, entity_ids, idx
                        )
                        if created_entity is None:
                            logger.warning(f"Entity processing skipped or failed for {entity_type} (JSON index {idx}).")

                    except Exception as e:
                        session.rollback()
                        logger.error(f"CRITICAL error processing {entity_type} entity (JSON index {idx}): {str(e)}")
                        logger.error("Aborting seeding process due to critical error.")
                        return False  # Stop entire seeding process

        session.commit()
        logger.info("--- Database seeding completed successfully ---")
        return True

    except Exception as e:
        if session: session.rollback()
        logger.error(f"FATAL error during seeding process: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    finally:
        if session: session.close()
        logger.info("Seeding session closed.")


# --- Main Execution ---
def main():
    """Main function to orchestrate database setup."""
    args = parse_arguments()

    db_path = os.path.abspath(settings.DATABASE_PATH)
    encryption_key = settings.DATABASE_ENCRYPTION_KEY

    if settings.USE_SQLCIPHER:
        logger.info(f"Using SQLCipher encrypted database: {db_path}")
        if not encryption_key:
            logger.warning("SQLCipher is enabled in settings, but DATABASE_ENCRYPTION_KEY seems empty or missing.")
    else:
        logger.info(f"Using standard SQLite database: {db_path}")

    create_db_directory(db_path)

    if args.reset:
        if not reset_database(db_path, encryption_key):
            logger.error("Database reset failed, exiting.")
            sys.exit(1)
        else:
            logger.info("Database reset completed.")

    if not initialize_database_schema():
        logger.error("Database schema initialization failed, exiting.")
        sys.exit(1)
    else:
        logger.info("Database schema initialization completed.")

    if args.seed:
        seed_file_path_arg = args.seed_file
        if not os.path.isabs(seed_file_path_arg):
            resolved_path = project_root / seed_file_path_arg
            if resolved_path.exists():
                seed_file_path = str(resolved_path)
                logger.info(f"Resolved seed file path relative to project root: {seed_file_path}")
            else:
                logger.warning(
                    f"Seed file '{seed_file_path_arg}' not found relative to project root. Trying relative to CWD.")
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