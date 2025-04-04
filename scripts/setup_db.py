#!/usr/bin/env python
"""
Enhanced database setup script for HideSync.

This script handles:
1. Creating/resetting the database (with SQLCipher support)
2. Creating tables by running SQLAlchemy model creation code
3. Seeding the database from JSON data
4. Diagnosing database tables and ensuring media system tables exist

Usage (from project root directory):
  python -m scripts.setup_db --reset --seed
  python -m scripts.setup_db --reset --seed --seed-file PATH_TO_SEED_FILE
  python -m scripts.setup_db --diagnose
  python -m scripts.setup_db --ensure-media-tables
"""

import os
import sys
import json
import re
import logging
import argparse
import importlib.util
from pathlib import Path
from typing import Dict, Any, List, Optional, Type, Set, Tuple
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
    from app.db.session import SessionLocal, engine, EncryptionManager, use_sqlcipher, init_db
    from app.core.config import settings
    from app.core.key_manager import KeyManager
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
    logger.error("Example command: python -m scripts.setup_db --reset --seed")
    sys.exit(1)

# --- Define Model Mapping ---
# This is needed for SQLAlchemy seeding to map entity types to model classes
model_map = {
    "users": User,
    "roles": Role,
    "permissions": Permission,
    "customers": Customer,
    "suppliers": Supplier,
    "materials": Material,
    "tools": Tool,
    "storage_locations": StorageLocation,
    "projects": Project,
    "project_templates": ProjectTemplate,
    "patterns": Pattern,
    "sales": Sale,
    "sale_items": SaleItem,
    "purchases": Purchase,
    "purchase_items": PurchaseItem,
    "picking_lists": PickingList,
    "picking_list_items": PickingListItem,
    "documentation_categories": DocumentationCategory,
    "documentation_resources": DocumentationResource,
    "storage_cells": StorageCell,
    "storage_assignments": StorageAssignment,
    "tool_maintenance": ToolMaintenance,
    "tool_checkouts": ToolCheckout,
    "project_components": ProjectComponent,
    "timeline_tasks": TimelineTask,
    "products": Product,
    "components": Component,
    # Media system tables might not have SQLAlchemy models yet, we'll handle them separately
    "media_assets": None,
    "media_tags": None,
    "media_asset_tags": None,
    "entity_media": None,
}

# --- SQL statements for media system tables ---
MEDIA_SYSTEM_TABLE_STATEMENTS = {
    'media_assets': """
    CREATE TABLE IF NOT EXISTS media_assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        file_path TEXT NOT NULL,
        file_size INTEGER,
        file_type TEXT,
        mime_type TEXT,
        width INTEGER,
        height INTEGER,
        duration INTEGER,
        title TEXT,
        description TEXT,
        alt_text TEXT,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP,
        uuid TEXT,
        is_public BOOLEAN DEFAULT FALSE,
        status TEXT DEFAULT 'active',
        metadata TEXT
    );
    """,
    'entity_media': """
    CREATE TABLE IF NOT EXISTS entity_media (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        media_asset_id INTEGER NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id INTEGER NOT NULL,
        media_type TEXT,
        display_order INTEGER DEFAULT 0,
        caption TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        uuid TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        updated_at TIMESTAMP,
        FOREIGN KEY (media_asset_id) REFERENCES media_assets(id) ON DELETE CASCADE
    );
    """,
    'media_tags': """
    CREATE TABLE IF NOT EXISTS media_tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        slug TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP
    );
    """,
    'media_asset_tags': """
    CREATE TABLE IF NOT EXISTS media_asset_tags (
        media_asset_id INTEGER NOT NULL,
        tag_id INTEGER NOT NULL,
        PRIMARY KEY (media_asset_id, tag_id),
        FOREIGN KEY (media_asset_id) REFERENCES media_assets(id) ON DELETE CASCADE,
        FOREIGN KEY (tag_id) REFERENCES media_tags(id) ON DELETE CASCADE
    );
    """
}

# List of all expected tables in the database based on the ER diagram
EXPECTED_TABLES = [
    # Core entities
    "users", "roles", "permissions",
    "customers", "suppliers",
    "materials", "leather_materials", "hardware_materials", "supplies_materials",
    "tools", "products", "components",

    # Storage system
    "storage_locations", "storage_cells", "storage_assignments", "storage_moves",

    # Projects system
    "projects", "project_templates", "project_components", "timeline_tasks",
    "recurring_projects", "recurrence_patterns", "generated_projects",

    # Sales system
    "sales", "sale_items", "shipments", "refunds",

    # Purchasing system
    "purchases", "purchase_items", "purchase_timeline_items",

    # Tool management
    "tool_maintenance", "tool_checkouts",

    # Planning and picking
    "patterns", "picking_lists", "picking_list_items",

    # Inventory management
    "inventory", "component_materials",

    # Documentation system
    "documentation_categories", "documentation_resources",
    "documentation_category_assignments", "application_contexts",
    "contextual_help_mappings",

    # Platform integration
    "platform_integrations", "sync_events",

    # Media system
    "media_assets", "media_tags", "media_asset_tags", "entity_media"
]

# --- Define Field Overrides ---
# These mappings handle differences between JSON field names and model field names
overrides_by_entity = {
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
        epilog="""
Examples:
  python -m scripts.setup_db --reset --seed
  python -m scripts.setup_db --diagnose
  python -m scripts.setup_db --ensure-media-tables
        """,
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
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Seed the database with demonstration data (using app.db.seed)",
    )
    parser.add_argument(
        "--admin-email",
        help="Email for admin user when seeding the database",
        default="admin@example.com",
    )
    parser.add_argument(
        "--admin-password",
        help="Password for admin user when seeding the database",
        default="AdminPassword123!",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging for more detailed output",
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Run database diagnostics to check table structure",
    )
    parser.add_argument(
        "--ensure-media-tables",
        action="store_true",
        help="Ensure that all media system tables exist in the database",
    )
    parser.add_argument(
        "--verbose-diagnostics",
        action="store_true",
        help="Show detailed information in diagnostics output",
    )
    parser.add_argument(
        "--fix-missing-tables",
        action="store_true",
        help="Automatically fix missing tables detected by diagnostics",
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
        logger.warning("No tables found in Base.metadata. Ensure models are imported correctly.")

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

        # Also ensure media tables exist (they might not be in SQLAlchemy models)
        success = ensure_media_tables_exist()
        if not success:
            logger.error("Media tables creation failed.")
            return False

        return True
    else:
        # For non-encrypted databases, use the standard SQLAlchemy approach
        try:
            logger.info("Using standard SQLite mode - calling create_all")
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created successfully")

            # Also ensure media tables exist (they might not be in SQLAlchemy models)
            success = ensure_media_tables_exist()
            if not success:
                logger.error("Media tables creation failed.")
                return False

            return True
        except Exception as e:
            logger.error(f"Error creating database tables: {str(e)}")
            logger.error(f"Detailed create_all error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False


def ensure_media_tables_exist():
    """Create media system tables if they don't exist."""
    logger.info("Ensuring media system tables exist...")

    if use_sqlcipher:
        # For SQLCipher databases, use direct SQL
        return create_media_tables_direct_sql()
    else:
        # For non-encrypted databases, we could use SQLAlchemy
        # but for consistency, use the same direct SQL approach
        return create_media_tables_direct_sql()


def create_media_tables_direct_sql():
    """Create media system tables using direct SQL commands."""
    db_path = os.path.abspath(settings.DATABASE_PATH)

    # Establish connection
    try:
        # Get SQLCipher module
        sqlcipher = EncryptionManager.get_sqlcipher_module()
        if not sqlcipher:
            logger.error("SQLCipher module not available")
            return False

        # Connect to the database
        conn = sqlcipher.connect(db_path)
        cursor = conn.cursor()

        # Configure encryption with hex key approach
        key = KeyManager.get_database_encryption_key()
        cursor.execute(f"PRAGMA key = \"x'{key}'\";")
        cursor.execute("PRAGMA cipher_page_size = 4096;")
        cursor.execute("PRAGMA kdf_iter = 256000;")
        cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
        cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Check which tables already exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        existing_tables = [row[0] for row in cursor.fetchall()]

        # Create tables in the right order to respect foreign key constraints
        tables_to_create = []
        for table_name in ['media_assets', 'entity_media', 'media_tags', 'media_asset_tags']:
            if table_name not in existing_tables:
                tables_to_create.append(table_name)

        if not tables_to_create:
            logger.info("All media system tables already exist")
            return True

        logger.info(f"Creating missing media tables: {', '.join(tables_to_create)}")

        # Create tables (in the right order for foreign key constraints)
        created_tables = []
        for table_name in ['media_assets', 'media_tags', 'media_asset_tags', 'entity_media']:
            if table_name in tables_to_create:
                try:
                    cursor.execute(MEDIA_SYSTEM_TABLE_STATEMENTS[table_name])
                    created_tables.append(table_name)
                    logger.info(f"Created table: {table_name}")
                except Exception as e:
                    logger.error(f"Error creating table {table_name}: {e}")
                    conn.rollback()
                    conn.close()
                    return False

        # Commit changes
        conn.commit()
        logger.info(f"Successfully created media tables: {', '.join(created_tables)}")

        # Verify the tables were created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        updated_tables = [row[0] for row in cursor.fetchall()]

        all_created = True
        for table_name in tables_to_create:
            if table_name not in updated_tables:
                logger.error(f"Table {table_name} was not created")
                all_created = False

        conn.close()
        return all_created

    except Exception as e:
        logger.error(f"Error ensuring media tables exist: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


# --- Database Diagnostics ---

def run_database_diagnostics(verbose=False, fix_missing=False):
    """Run a comprehensive database diagnostic check."""
    logger.info("Running database diagnostics...")

    db_path = os.path.abspath(settings.DATABASE_PATH)
    if not os.path.exists(db_path):
        logger.error(f"Database file not found at: {db_path}")
        return False

    try:
        # Get SQLCipher module
        sqlcipher = EncryptionManager.get_sqlcipher_module()
        if not sqlcipher:
            logger.error("SQLCipher module not available")
            return False

        # Connect to the database
        conn = sqlcipher.connect(db_path)
        cursor = conn.cursor()

        # Configure encryption with hex key approach
        key = KeyManager.get_database_encryption_key()
        cursor.execute(f"PRAGMA key = \"x'{key}'\";")
        cursor.execute("PRAGMA cipher_page_size = 4096;")
        cursor.execute("PRAGMA kdf_iter = 256000;")
        cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
        cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Verify connection and basic functionality
        try:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            logger.info(f"Database connection test: {result}")
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False

        # Get database version info
        cursor.execute("SELECT sqlite_version()")
        sqlite_version = cursor.fetchone()[0]
        logger.info(f"SQLite version: {sqlite_version}")

        try:
            cursor.execute("PRAGMA cipher_version")
            cipher_version = cursor.fetchone()[0]
            logger.info(f"SQLCipher version: {cipher_version}")
        except:
            logger.info("SQLCipher version not available (using standard SQLite)")

        # Get database file info
        db_size = os.path.getsize(db_path)
        logger.info(f"Database file size: {db_size} bytes ({db_size / 1024 / 1024:.2f} MB)")

        # Get all tables in the database
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        existing_tables = set(row[0] for row in cursor.fetchall())

        logger.info(f"Found {len(existing_tables)} tables in the database")
        if verbose:
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
        media_tables = {'media_assets', 'entity_media', 'media_tags', 'media_asset_tags'}
        missing_media_tables = media_tables - existing_tables

        if missing_media_tables:
            logger.warning(f"Missing media system tables: {', '.join(sorted(missing_media_tables))}")

            if fix_missing:
                logger.info("Attempting to create missing media tables...")
                if create_media_tables_direct_sql():
                    logger.info("Successfully created missing media tables")
                else:
                    logger.error("Failed to create missing media tables")
        else:
            logger.info("All media system tables are present")

        # Check table structures if verbose
        if verbose:
            logger.info("\nTable structure details:")
            for table_name in sorted(existing_tables):
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()

                logger.info(f"\nTable: {table_name} ({len(columns)} columns)")
                for col in columns:
                    pk_str = "PK" if col[5] else "  "
                    nn_str = "NN" if col[3] else "  "
                    logger.info(f"  - {col[1]:<20} {col[2]:<10} {pk_str} {nn_str} {col[4] or ''}")

                # Check row count
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = cursor.fetchone()[0]
                    logger.info(f"  Rows: {count}")
                except:
                    logger.warning(f"  Could not count rows in {table_name}")

        conn.close()

        # Summary
        if missing_tables:
            if fix_missing:
                logger.info("\nDiagnostics Summary: Issues found and repair attempted")
            else:
                logger.info("\nDiagnostics Summary: Issues found")
                logger.info("Run with --fix-missing-tables to attempt repair")
            return False
        else:
            logger.info("\nDiagnostics Summary: Database appears healthy")
            return True

    except Exception as e:
        logger.error(f"Error running diagnostics: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


# --- Database Seeding ---

def get_enum_class_for_field(entity_type: str, field_name: str) -> Optional[Type[Enum]]:
    """
    Determines the correct Enum class based on the entity type and field name.
    This function centralizes the logic for resolving which enum to use.
    """
    # Sales-specific mappings
    if entity_type == "sales":
        if field_name == "payment_status":
            return enums.PaymentStatus
        if field_name == "fulfillment_status":
            return enums.FulfillmentStatus
        if field_name == "status":
            return enums.SaleStatus
        if field_name == "channel":
            return enums.SaleChannel if hasattr(enums, "SaleChannel") else None

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


# Seeding function that supports both app.db.seed and direct JSON seeding
def seed_database(args) -> bool:
    """
    Seed the database using either app.db.seed or directly with a JSON file.
    Handles key conversion, overrides, and relationship linking.
    """
    # Try to use app.db.seed if requested with --demo or if seed_file not specified
    if args.demo:
        try:
            logger.info("Using app.db.seed module for seeding...")
            from app.db.seed import (
                create_admin_user,
                create_initial_roles,
                seed_demo_data,
                seed_master_data,
            )

            # Always create roles
            logger.info("Creating initial roles...")
            create_initial_roles()
            logger.info("Initial roles created successfully")

            # Create admin user
            logger.info(f"Creating admin user with email: {args.admin_email}")
            admin_user = create_admin_user(
                email=args.admin_email,
                password=args.admin_password,
            )
            logger.info(f"Admin user created with ID: {admin_user.id}")

            # Always seed master data
            logger.info("Seeding master data...")
            seed_master_data()
            logger.info("Master data seeded successfully")

            # Seed demo data if requested
            logger.info("Seeding demonstration data...")
            seed_demo_data()
            logger.info("Demonstration data seeded successfully")

            logger.info("Database seeding completed successfully")
            return True
        except ImportError as e:
            logger.warning(f"Could not import app.db.seed module: {e}")
            logger.warning("Falling back to JSON seeding...")

    # Use JSON seeding
    seed_file = resolve_seed_file_path(args.seed_file)
    if not seed_file:
        logger.error("Could not find seed data file")
        return False

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


def resolve_seed_file_path(seed_file_path_arg):
    """Resolve and validate the seed file path."""
    # If it's an absolute path, use it directly
    if os.path.isabs(seed_file_path_arg):
        if os.path.exists(seed_file_path_arg):
            return seed_file_path_arg
        else:
            logger.error(f"Seed file not found at absolute path: {seed_file_path_arg}")
            return None

    # Try relative to project root
    resolved_path = project_root / seed_file_path_arg
    if resolved_path.exists():
        return str(resolved_path)

    # Try common locations
    common_locations = [
        project_root / "app" / "db" / "seed_data.json",
        project_root / "data" / "seed_data.json",
        project_root / "seed_data.json",
    ]

    for location in common_locations:
        if location.exists():
            logger.info(f"Found seed file at: {location}")
            return str(location)

    logger.error(f"Could not find seed file '{seed_file_path_arg}' in any standard location")
    return None


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
        key = KeyManager.get_database_encryption_key()
        cursor.execute(f"PRAGMA key = \"x'{key}'\";")
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

            # Print schema for debugging
            cursor.execute(f"PRAGMA table_info({entity_type})")
            columns_info = cursor.fetchall()
            valid_columns = [col[1] for col in columns_info]
            logger.debug(f"Table schema for {entity_type}: {valid_columns}")

            for idx, item_data in enumerate(seed_data[entity_type], 1):
                try:
                    # 1. Convert camelCase to snake_case
                    data = decamelize_keys(item_data)

                    # Debug data after decamelizing
                    logger.debug(f"Data after decamelizing: {data.keys()}")

                    # 2. Apply entity-specific overrides
                    if entity_type in overrides_by_entity:
                        data = apply_overrides(data, overrides_by_entity[entity_type])

                    # 3. Handle special entity types for materials
                    if entity_type == "materials" and "material_type" in data:
                        material_type = data.get("material_type", "").lower()
                        data = map_material_attributes(data, material_type)

                    # 4. Handle complex fields that need special processing
                    for key, value in list(data.items()):
                        # Serialize dictionary or list fields to JSON strings
                        if isinstance(value, (dict, list)):
                            data[key] = json.dumps(value)

                        # Special handling for dimensions field in storage_locations
                        if entity_type == "storage_locations" and key == "dimensions" and isinstance(value, dict):
                            # Some SQLite schemas might store these as separate columns
                            for dim_key, dim_value in value.items():
                                # Add individual dimension fields
                                dim_field = f"dimension_{dim_key}"
                                if dim_field in valid_columns:
                                    data[dim_field] = dim_value

                    # 5. Convert date strings to datetime objects
                    for key, value in list(data.items()):
                        if isinstance(value, str) and (key.endswith("_date") or key.endswith("_at") or key == "date"):
                            try:
                                if value.endswith("Z"):
                                    value = value[:-1] + "+00:00"
                                data[key] = datetime.fromisoformat(value).isoformat()
                            except ValueError:
                                logger.warning(f"Invalid date format for {key}: {value}")
                                data[key] = None

                    # 6. Enhanced enum handling - debug version
                    for key, value in list(data.items()):
                        # Log original value for diagnosis
                        if key in ['status', 'payment_status', 'fulfillment_status', 'channel']:
                            logger.debug(f"Processing enum field: {key}={value} (type: {type(value)})")

                        if isinstance(value, str):
                            enum_class = get_enum_class_for_field(entity_type, key)
                            if enum_class:
                                # Log enum class for diagnosis
                                logger.debug(f"Found enum class {enum_class.__name__} for field {key}")

                                enum_value = get_enum_member_by_value(enum_class, value)
                                if enum_value:
                                    # For direct SQL, store the string value of the enum
                                    logger.debug(f"Converting enum {key} from {value} to {enum_value.value}")
                                    data[key] = enum_value.value
                                else:
                                    # If we can't find the enum value, use the original string
                                    # This is safer than failing
                                    logger.warning(
                                        f"Could not find enum value '{value}' in {enum_class.__name__}, using as-is")
                                    # Ensure it's a string
                                    data[key] = str(value)

                    # Special handling for payment status fields
                    if entity_type == 'sales':
                        # Handle payment_status and other enums specifically for sales
                        # Make sure all values are strings or integers
                        for key in ['status', 'payment_status', 'fulfillment_status', 'channel']:
                            if key in data and not isinstance(data[key], (str, int)):
                                # Convert to string representation if it's an enum or other object
                                data[key] = str(data[key])

                    # 7. Resolve foreign key references using entity_ids
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
                            if fk_entity_type and fk_entity_type in entity_ids and original_id in entity_ids[
                                fk_entity_type]:
                                data[key] = entity_ids[fk_entity_type][original_id]
                                logger.debug(f"Mapped FK {key}: {original_id} -> {data[key]}")

                    # 8. Handle special fields for certain entity types
                    if entity_type == "users" and "password" in data:
                        # Handle password hashing
                        from app.core.security import get_password_hash
                        data["hashed_password"] = get_password_hash(data.pop("password"))

                    # 9. Handle lists and array fields
                    for key, value in list(data.items()):
                        if isinstance(value, list):
                            # For now, we'll just join list values with commas
                            # This is a simplification - in a real app, you'd use a proper m2m relationship
                            data[key] = ','.join(str(item) for item in value)

                    # 10. Generate and execute INSERT statement
                    # Remove any keys that aren't actual columns
                    filtered_data = {}
                    for key, value in data.items():
                        if key in valid_columns:
                            filtered_data[key] = value
                        else:
                            logger.debug(f"Removed field '{key}' not in {entity_type} table schema")

                    if filtered_data:
                        # Make sure we have all required columns
                        missing_required = []
                        for col_info in columns_info:
                            col_name = col_info[1]
                            is_not_null = col_info[3] == 1  # "notnull" flag
                            has_default = col_info[4] is not None  # "dflt_value"
                            is_pk = col_info[5] == 1  # "pk" flag

                            # Column is required if it's NOT NULL, has no default, and is not an autoincrement PK
                            if is_not_null and not has_default and not is_pk and col_name not in filtered_data:
                                missing_required.append(col_name)

                        if missing_required:
                            logger.warning(f"Missing required columns for {entity_type}: {missing_required}")
                            logger.warning(f"Available data keys: {data.keys()}")
                            logger.warning(f"Skipping {entity_type} record due to missing required fields")
                            continue

                        columns = list(filtered_data.keys())
                        values = []

                        # Convert Python types to SQLite compatible types
                        for key, value in filtered_data.items():
                            logger.debug(f"Converting value for {key}: {value} (type: {type(value).__name__})")

                            if isinstance(value, bool):
                                # SQLite doesn't have a boolean type, so convert to 0/1
                                logger.debug(f"  Converting boolean {value} to {1 if value else 0}")
                                values.append(1 if value else 0)
                            elif isinstance(value, dict) or isinstance(value, list):
                                # Convert dictionaries and lists to JSON strings
                                logger.debug(f"  Converting complex type to JSON string")
                                values.append(json.dumps(value))
                            elif isinstance(value, Enum):
                                # Handle enum objects directly
                                logger.debug(f"  Converting Enum {value} to {value.value}")
                                values.append(value.value)
                            elif value is None:
                                logger.debug(f"  Passing None value as is")
                                values.append(None)
                            else:
                                # Force any other types to strings to avoid binding issues
                                if not isinstance(value, (str, int, float)):
                                    logger.debug(f"  Converting {type(value).__name__} to string")
                                    values.append(str(value))
                                else:
                                    logger.debug(f"  Passing {type(value).__name__} value as is")
                                    values.append(value)

                        # Build and execute INSERT statement
                        placeholders = ", ".join(["?"] * len(columns))
                        sql = f"INSERT INTO {entity_type} ({', '.join(columns)}) VALUES ({placeholders})"

                        # Debug print SQL and values
                        logger.debug(f"Executing SQL: {sql}")
                        for i, val in enumerate(values):
                            logger.debug(f"  Parameter {i + 1}: {val} (type: {type(val).__name__})")

                        try:
                            cursor.execute(sql, values)
                        except Exception as e:
                            logger.error(f"SQL Execution Error: {str(e)}")
                            logger.error(f"SQL Statement: {sql}")
                            logger.error(f"Values: {values}")

                            # Try converting all values to strings as a fallback
                            string_values = [str(v) if v is not None else None for v in values]
                            logger.warning("Attempting to retry with all values converted to strings")

                            try:
                                cursor.execute(sql, string_values)
                                logger.info("SQL retry succeeded with string conversion")
                            except Exception as retry_error:
                                logger.error(f"SQL Retry Error: {str(retry_error)}")
                                raise  # Re-raise the original error for consistent error messages

                        # Get the ID of the inserted entity
                        cursor.execute("SELECT last_insert_rowid()")
                        new_id = cursor.fetchone()[0]

                        # Store the ID for future FK references
                        if entity_type not in entity_ids:
                            entity_ids[entity_type] = {}
                        entity_ids[entity_type][idx] = new_id

                        entity_count += 1
                        logger.debug(f"Inserted {entity_type} at index {idx} with ID {new_id}")
                    else:
                        logger.warning(f"Skipping {entity_type} at index {idx}: no valid columns found")

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
    db = SessionLocal()
    try:
        # Cache: { "entity_type": { json_index: db_id } }
        entity_ids: Dict[str, Dict[int, Any]] = {}

        for entity_type in entities_order:
            if entity_type in seed_data:
                logger.info(f"--- Seeding {entity_type} ---")
                entities_data = seed_data[entity_type]

                if not isinstance(entities_data, list):
                    logger.warning(f"Seed data for '{entity_type}' is not a list. Skipping.")
                    continue

                # Process each entity one at a time
                entity_count = 0
                for idx, item_data in enumerate(entities_data, 1):
                    if not isinstance(item_data, dict):
                        logger.warning(f"Item at index {idx} for '{entity_type}' is not a dictionary. Skipping.")
                        continue

                    try:
                        # 1. Get the model class
                        model = model_map.get(entity_type)
                        if not model:
                            logger.warning(f"Unknown entity type '{entity_type}'. Skipping.")
                            continue

                        # 2. Decamelize keys and apply overrides
                        data = decamelize_keys(item_data)
                        if entity_type in overrides_by_entity:
                            data = apply_overrides(data, overrides_by_entity[entity_type])

                        # 3. Handle special processing for materials
                        if entity_type == "materials" and "material_type" in data:
                            data = map_material_attributes(data, data["material_type"])

                        # 4. Handle complex fields
                        for key, value in list(data.items()):
                            if isinstance(value, (dict, list)):
                                # SQLAlchemy can handle JSON serialization for some DB types
                                # but we still need to explicitly mark it for others
                                try:
                                    data[key] = json.dumps(value)
                                except:
                                    pass  # Let SQLAlchemy try to handle it

                        # 5. Handle enum values
                        for key, value in list(data.items()):
                            if isinstance(value, str):
                                enum_class = get_enum_class_for_field(entity_type, key)
                                if enum_class:
                                    enum_value = get_enum_member_by_value(enum_class, value)
                                    if enum_value:
                                        data[key] = enum_value

                        # 6. Resolve foreign key references
                        for key in list(data.keys()):
                            if key.endswith("_id") and isinstance(data[key], int):
                                original_id = data[key]
                                fk_entity_type = None

                                # Map field name to referenced entity type
                                if key == "supplier_id":
                                    fk_entity_type = "suppliers"
                                elif key == "customer_id":
                                    fk_entity_type = "customers"
                                # Add other mappings as needed...

                                # If we know the referenced entity type and have an ID mapping
                                if fk_entity_type and fk_entity_type in entity_ids and original_id in entity_ids[
                                    fk_entity_type]:
                                    data[key] = entity_ids[fk_entity_type][original_id]
                                    logger.debug(f"Mapped FK {key}: {original_id} -> {data[key]}")

                        # 7. Handle password hashing for users
                        if entity_type == "users" and "password" in data:
                            data["hashed_password"] = get_password_hash(data.pop("password"))

                        # 8. Create and add the entity
                        entity = model(**data)
                        db.add(entity)
                        db.flush()

                        # 9. Store the new ID in our cache
                        if entity_type not in entity_ids:
                            entity_ids[entity_type] = {}
                        entity_ids[entity_type][idx] = entity.id

                        entity_count += 1
                        logger.debug(f"Created {entity_type} with ID {entity.id}")

                    except Exception as e:
                        logger.error(f"Error creating {entity_type} at index {idx}: {e}")
                        logger.error(f"Data: {item_data}")
                        logger.exception("Details:")
                        db.rollback()
                        raise

                logger.info(f"Created {entity_count} {entity_type} records")

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

    # Enable debug logging if requested
    if args.debug:
        logging.getLogger('__main__').setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    # See if we need to diagnose the database
    if args.diagnose:
        logger.info("Running database diagnostics...")
        success = run_database_diagnostics(args.verbose_diagnostics, args.fix_missing_tables)
        if success:
            logger.info("Database diagnostics completed successfully.")
            return
        elif args.fix_missing_tables:
            logger.info("Database diagnostics completed with fixes applied.")
            return
        else:
            logger.error("Database diagnostics found issues. Run with --fix-missing-tables to attempt repair.")
            sys.exit(1)

    # Check if we're only ensuring media tables exist
    if args.ensure_media_tables:
        logger.info("Ensuring media tables exist...")
        if ensure_media_tables_exist():
            logger.info("Media tables exist or were created successfully.")
            return
        else:
            logger.error("Failed to ensure media tables exist.")
            sys.exit(1)

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
    if args.seed or args.demo:
        logger.info("Starting database seeding process...")
        if not seed_database(args):
            logger.error("Database seeding failed, exiting.")
            sys.exit(1)
        else:
            logger.info("Database seeding completed.")

    # Step 4: Ensure media tables exist
    if not args.ensure_media_tables:  # Skip if already done
        if not ensure_media_tables_exist():
            logger.error("Failed to ensure media tables exist.")
            sys.exit(1)
        else:
            logger.info("Media tables exist or were created successfully.")

    logger.info("--- Database setup process finished successfully ---")


if __name__ == "__main__":
    main()