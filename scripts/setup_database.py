#!/usr/bin/env python
"""
Comprehensive database setup script for HideSync.

This script handles everything related to database setup:
1. Creating/resetting the database
2. Creating tables by running SQLAlchemy model creation code
3. Optionally seeding the database with initial data

It handles SQLCipher encryption directly to avoid integration issues.
"""

import os
import sys
import json
import re
import logging
import argparse
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

# Add the project root directory to Python path.
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent if script_dir.name == "scripts" else script_dir
sys.path.append(str(project_root))

# Configure logging.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def camel_to_snake(name: str) -> str:
    """
    Convert a camelCase string to snake_case.
    """
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def decamelize_keys(data: Any) -> Any:
    """
    Recursively convert all keys in dictionaries (and lists) from camelCase to snake_case.
    """
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
    for old_key, new_key in overrides.items():
        if old_key in data:
            data[new_key] = data.pop(old_key)
    return data


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Set up the HideSync database.")
    parser.add_argument(
        "--seed", action="store_true", help="Seed the database with initial data"
    )
    parser.add_argument(
        "--seed-file",
        type=str,
        default="./app/db/seed_data.json",
        help="Path to the seed data JSON file",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset the database (delete and recreate it)",
    )
    return parser.parse_args()


def create_db_directory(db_path: str):
    """Create the database directory if it doesn't exist."""
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        logger.info(f"Creating database directory: {db_dir}")
        os.makedirs(db_dir, exist_ok=True)


def reset_database(db_path: str, encryption_key: str) -> bool:
    """Reset the database by deleting and recreating the file."""
    logger.info(f"Resetting database at {db_path}")
    if os.path.exists(db_path):
        try:
            os.unlink(db_path)
            logger.info(f"Deleted existing database file: {db_path}")
        except Exception as e:
            logger.error(f"Error deleting database file: {str(e)}")
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
        # Create and drop a test table
        cursor.execute("CREATE TABLE _test_table (id INTEGER PRIMARY KEY)")
        cursor.execute("DROP TABLE _test_table")
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("Empty encrypted database created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating new database: {str(e)}")
        return False


def initialize_database_schema() -> bool:
    """Initialize database schema using SQLAlchemy models."""
    logger.info("Creating database tables...")
    try:
        import app.db.models  # Ensures models are registered.
        from app.db.models.base import Base
        from app.db.session import engine

        logger.info(f"Engine details: {engine}")
        logger.info("Registered models:")
        for table_name, table in Base.metadata.tables.items():
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
        return False


def map_material_attributes(data: Dict[str, Any], material_type: str) -> Dict[str, Any]:
    """
    Apply custom mapping for material attributes.
    For HARDWARE materials, for example, convert "color" to "hardware_color".
    """
    result = data.copy()
    if material_type == "LEATHER":
        pass
    elif material_type == "HARDWARE":
        if "color" in result:
            result["hardware_color"] = result.pop("color")
        if "finish" in result:
            result["hardware_finish"] = result.pop("finish")
    elif material_type == "SUPPLIES":
        if "color" in result:
            result["supplies_color"] = result.pop("color")
        if "finish" in result:
            result["supplies_finish"] = result.pop("finish")
    return result


def seed_database(seed_file: str) -> bool:
    """
    Seed the database using a JSON file.
    This function decamelizes keys and applies entity-specific overrides.
    """
    if not os.path.exists(seed_file):
        alt_paths = [
            os.path.join("app", "db", "seed_data.json"),
            os.path.join(project_root, "app", "db", "seed_data.json"),
        ]
        for path in alt_paths:
            if os.path.exists(path):
                seed_file = path
                logger.info(f"Using seed file from alternative path: {seed_file}")
                break
        else:
            logger.error(f"Seed file not found: {seed_file}")
            return False

    try:
        with open(seed_file, "r") as f:
            seed_data = json.load(f)
    except Exception as e:
        logger.error(f"Error loading seed data: {str(e)}")
        return False

    # Define custom key overrides per entity type.
    overrides_by_entity = {
        "materials": {
            "cost": "cost_price",
            "price": "cost_price",
            "depositamount": "deposit_amount",
        },
        "sales": {
            "createdat": "created_at",
            "paymentstatus": "payment_status",
            "fulfillmentstatus": "fulfillment_status",
            "depositamount": "deposit_amount",
        },
        "sale_items": {
            "cost_price": "price",  # For sale items, if the seed data provides costPrice, rename it to price.
        },
        # Add other entity-specific overrides as needed.
    }

    def create_entity(
        entity_type: str,
        item_data: Dict[str, Any],
        session,
        entity_ids: Dict[str, Dict[int, str]],
    ):
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
        )

        model_map = {
            "documentation_categories": DocumentationCategory,
            "documentation_resources": DocumentationResource,
            "suppliers": Supplier,
            "customers": Customer,
            "materials": Material,
            "tools": Tool,
            "tool_maintenance": ToolMaintenance,
            "tool_checkouts": ToolCheckout,
            "storage_locations": StorageLocation,
            "storage_cells": StorageCell,
            "storage_assignments": StorageAssignment,
            "patterns": Pattern,
            "project_templates": ProjectTemplate,
            "projects": Project,
            "project_components": ProjectComponent,
            "timeline_tasks": TimelineTask,
            "sales": Sale,
            "sale_items": SaleItem,
            "purchases": Purchase,
            "purchase_items": PurchaseItem,
            "picking_lists": PickingList,
            "picking_list_items": PickingListItem,
            "users": User,
        }

        model = model_map.get(entity_type)
        if not model:
            logger.warning(f"Unknown entity type: {entity_type}")
            return None

        # Decamelize all keys.
        data = decamelize_keys(item_data)

        # Apply any custom overrides for this entity type.
        if entity_type in overrides_by_entity:
            data = apply_overrides(data, overrides_by_entity[entity_type])

        # Remove extra keys not handled by models.
        if entity_type == "projects" and "completion_percentage" in data:
            del data["completion_percentage"]

        if entity_type == "project_templates":
            for extra in ["estimated_duration", "estimated_cost", "is_public"]:
                data.pop(extra, None)

        # Special handling for project_components.
        if entity_type == "project_components":
            if "component_id" not in data or data["component_id"] is None:
                extra = {}
                for key in ["name", "description", "component_type"]:
                    if key in data:
                        extra[key] = data.pop(key)
                try:
                    from app.db.models.component import Component
                except ImportError:
                    logger.error("Component model could not be imported.")
                    raise
                new_comp = Component(**extra)
                session.add(new_comp)
                session.flush()
                data["component_id"] = new_comp.id

        # Convert date strings.
        for key, value in data.items():
            if isinstance(value, str) and (key.endswith("date") or key.endswith("at")):
                try:
                    data[key] = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    pass

        # Update foreign keys based on previously seeded entities.
        for key in list(data.keys()):
            if key.endswith("_id") and isinstance(data[key], int):
                fk_type = key[:-3] + "s"
                if fk_type in entity_ids and data[key] in entity_ids[fk_type]:
                    data[key] = entity_ids[fk_type][data[key]]

        # For materials, use specialized subclasses.
        if entity_type == "materials":
            material_type = data.pop("material_type", "LEATHER").upper()
            data = map_material_attributes(data, material_type)
            if data.get("reorder_point") is None:
                data["reorder_point"] = 0.0
            if material_type == "LEATHER":
                entity = LeatherMaterial(**data)
            elif material_type == "HARDWARE":
                entity = HardwareMaterial(**data)
            elif material_type == "SUPPLIES":
                entity = SuppliesMaterial(**data)
            else:
                entity = Material(**data)
        else:
            entity = model(**data)

        return entity

    # Define entity seeding order.
    entities_order = [
        "documentation_categories",
        "documentation_resources",
        "suppliers",
        "customers",
        "storage_locations",
        "storage_cells",
        "materials",
        "tools",
        "projects",
        "project_templates",
        "project_components",
        "tool_maintenance",
        "tool_checkouts",
        "patterns",
        "timeline_tasks",
        "sales",
        "sale_items",
        "purchases",
        "purchase_items",
        "picking_lists",
        "picking_list_items",
        "storage_assignments",
        "users",
    ]

    from app.db.session import SessionLocal

    try:
        session = SessionLocal()
        entity_ids = {}  # Track new IDs for foreign key resolution.

        for entity_type in entities_order:
            if entity_type in seed_data:
                logger.info(f"Seeding {entity_type}...")
                entities_data = seed_data[entity_type]
                if entity_type not in entity_ids:
                    entity_ids[entity_type] = {}

                for idx, item_data in enumerate(entities_data, 1):
                    try:
                        entity = create_entity(
                            entity_type, item_data, session, entity_ids
                        )
                        if entity is not None:
                            session.add(entity)
                            session.flush()  # Get assigned ID.
                            entity_ids[entity_type][idx] = entity.id
                        else:
                            logger.warning(
                                f"Skipping entity creation for {entity_type} (index {idx})"
                            )
                    except Exception as e:
                        session.rollback()
                        logger.error(
                            f"Error creating {entity_type} entity (index {idx}): {str(e)}"
                        )
                        raise
        session.commit()
        logger.info("Database seeding completed successfully")
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"Error seeding database: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())
        return False
    finally:
        session.close()


def main():
    """Main function."""
    args = parse_arguments()

    from app.core.config import settings

    db_path = os.path.abspath(settings.DATABASE_PATH)
    encryption_key = settings.DATABASE_ENCRYPTION_KEY

    create_db_directory(db_path)

    if settings.USE_SQLCIPHER:
        logger.info(f"Using SQLCipher encrypted database: {db_path}")
    else:
        logger.info(f"Using standard SQLite database: {db_path}")

    if args.reset:
        if not reset_database(db_path, encryption_key):
            logger.error("Database reset failed, exiting.")
            sys.exit(1)

    if not initialize_database_schema():
        logger.error("Database schema initialization failed, exiting.")
        sys.exit(1)

    if args.seed and not seed_database(args.seed_file):
        logger.error("Database seeding failed, exiting.")
        sys.exit(1)

    logger.info("Database setup completed successfully")


if __name__ == "__main__":
    main()
