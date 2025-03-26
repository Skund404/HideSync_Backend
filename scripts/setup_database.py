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
from typing import Dict, Any, List, Optional # Added List, Optional
from datetime import datetime
from app.db.session import SessionLocal, engine

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
        # Import models here to ensure they are registered with Base.metadata
        # Import specific models needed later if not covered by a general import
        from app.db import models # Assuming __init__.py imports all model modules
        from app.db.models.base import Base
        from app.db.session import engine

        logger.info(f"Engine details: {engine}")
        logger.info("Registered models:")
        # Sort table names for consistent output
        for table_name in sorted(Base.metadata.tables.keys()):
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
        logger.error(traceback.format_exc()) # Log full traceback
        return False


def map_material_attributes(data: Dict[str, Any], material_type: str) -> Dict[str, Any]:
    """
    Apply custom mapping for material attributes based on type.
    """
    result = data.copy()
    if material_type == "HARDWARE":
        if "color" in result:
            result["hardware_color"] = result.pop("color")
        if "finish" in result:
            result["hardware_finish"] = result.pop("finish")
        # Add other hardware-specific mappings if needed
    elif material_type == "SUPPLIES":
        if "color" in result:
            result["supplies_color"] = result.pop("color")
        if "finish" in result:
            result["supplies_finish"] = result.pop("finish")
        # Add other supplies-specific mappings if needed
    # No specific mappings needed for LEATHER in this example
    return result


# ... (imports and other functions remain the same) ...

def seed_database(seed_file: str) -> bool:
    """
    Seed the database using a JSON file.
    Handles key conversion, overrides, and relationship linking.
    """
    # ... (file loading remains the same) ...

    # Define custom key overrides per entity type.
    overrides_by_entity = {
        "materials": {
            "cost": "cost_price",
            # "price": "selling_price", # <<< REMOVE THIS LINE
        },
        "sales": {
            "createdat": "created_at",
            "paymentstatus": "payment_status",
            "fulfillmentstatus": "fulfillment_status",
            "depositamount": "deposit_amount",
            "customerid": "customer_id",
        },
        "sale_items": {
            # No specific overrides needed here based on JSON
        },
        "purchases": {
             "supplierid": "supplier_id",
        },
        "tools": {
             "supplierid": "supplier_id",
        },
        # Add other entity-specific overrides as needed.
    }

    # --- Import models needed within create_entity ---
    from app.db.models import (
        Customer, Supplier, Material, LeatherMaterial, HardwareMaterial,
        SuppliesMaterial, Tool, StorageLocation, StorageCell, StorageAssignment,
        ProjectTemplate, DocumentationCategory, DocumentationResource,
        PickingList, PickingListItem, ToolMaintenance, ToolCheckout, User,
        Project, ProjectComponent, Sale, SaleItem, PurchaseItem, Purchase,
        Pattern, TimelineTask, Component
    )
    # --- End model imports ---

    model_map = {
        # ... (model_map remains the same) ...
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


    def create_entity(
        entity_type: str,
        item_data: Dict[str, Any],
        session,
        entity_ids: Dict[str, Dict[int, str]],
        idx: int # Pass index for better logging
    ) -> Optional[Any]: # Return type hint
        """Creates a single entity instance, handling relationships."""

        # ... (model lookup, decamelize, overrides, pre-processing remain the same) ...
        model = model_map.get(entity_type)
        if not model:
            logger.warning(f"Unknown entity type: {entity_type} at index {idx}")
            return None
        data = decamelize_keys(item_data)
        if entity_type in overrides_by_entity:
            data = apply_overrides(data, overrides_by_entity[entity_type])
        # ... (special handling for docs, projects, etc. remains the same) ...
        related_category_slug: Optional[str] = None
        if entity_type == "documentation_resources" and "category" in data:
            # ... (category handling) ...
            category_identifier = data.pop("category")
            if category_identifier:
                related_category_slug = str(category_identifier).lower().replace(" ", "-")
                logger.debug(f"  Extracted category slug '{related_category_slug}' for resource index {idx}")

        if entity_type == "project_components":
            # ... (component creation handling) ...
            if "component_id" not in data or data["component_id"] is None:
                comp_data = {}
                for key in ["name", "description", "component_type"]:
                    if key in data:
                        comp_data[key] = data.pop(key)
                if comp_data:
                    logger.info(f"  Creating associated Component for project_component index {idx}")
                    try:
                        new_comp = Component(**comp_data)
                        session.add(new_comp)
                        session.flush()
                        data["component_id"] = new_comp.id
                        logger.info(f"    Created Component with ID: {new_comp.id}")
                    except Exception as comp_e:
                        logger.error(f"    Error creating associated Component: {comp_e}")
                        raise
                else:
                     logger.warning(f"  Missing component_id and component data for project_component index {idx}")


        # 4. Convert date strings (handle potential errors)
        # ... (date conversion remains the same) ...
        for key, value in data.items():
            if isinstance(value, str) and (key.endswith("_date") or key.endswith("_at")):
                try:
                    data[key] = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    logger.warning(f"  Could not parse date string '{value}' for key '{key}' in {entity_type} index {idx}. Skipping conversion.")
                    pass

        # 5. Update foreign keys based on previously seeded entities (using UUIDs/IDs)
        for key in list(data.keys()):
            if key.endswith("_id") and isinstance(data[key], int):
                original_fk_index = data[key]
                fk_entity_type = None

                # --- MODIFICATION FOR storage_id ---
                if key == "storage_id":
                    fk_entity_type = "storage_locations"
                # --- END MODIFICATION ---
                else:
                    # Default logic: remove '_id', add 's'
                    fk_entity_type = key[:-3] + "s"
                    # Add more specific mappings here if needed (e.g., 'category_id' -> 'documentation_categories')
                    if key == "category_id" and entity_type == "documentation_category_assignments": # Example specific mapping
                         fk_entity_type = "documentation_categories"
                    elif key == "resource_id" and entity_type == "documentation_category_assignments": # Example specific mapping
                         fk_entity_type = "documentation_resources"


                if fk_entity_type and fk_entity_type in entity_ids and original_fk_index in entity_ids[fk_entity_type]:
                    new_db_id = entity_ids[fk_entity_type][original_fk_index]
                    data[key] = new_db_id
                    logger.debug(f"  Mapped FK {key}: index {original_fk_index} -> DB ID {new_db_id}")
                elif fk_entity_type: # Only warn if we determined a type but couldn't map
                    logger.warning(f"  Could not map FK {key}: index {original_fk_index} for {entity_type} index {idx}. Related entity '{fk_entity_type}' index not found in cache.")
                # else: key didn't match standard pattern and wasn't specifically handled

        # 6. Create the entity instance
        # ... (try...except block remains the same, including material/user handling) ...
        # ... (post-creation relationship handling remains the same) ...
        entity = None
        try:
            if entity_type == "materials":
                material_type = data.pop("material_type", "LEATHER").upper()
                data = map_material_attributes(data, material_type)
                if data.get("reorder_point") is None: data["reorder_point"] = 0.0
                if material_type == "LEATHER": model_to_use = LeatherMaterial
                elif material_type == "HARDWARE": model_to_use = HardwareMaterial
                elif material_type == "SUPPLIES": model_to_use = SuppliesMaterial
                else:
                    logger.warning(f"  Unknown material_type '{material_type}' for material index {idx}. Using base Material.")
                    model_to_use = Material
                entity = model_to_use(**data)
            elif entity_type == "users" and "plain_password" in data:
                 from app.core.security import get_password_hash
                 plain_password = data.pop("plain_password")
                 data["hashed_password"] = get_password_hash(plain_password)
                 entity = model(**data)
            else:
                entity = model(**data)

            if entity:
                session.add(entity)
                session.flush()
                logger.debug(f"  Created {entity_type} instance (ID: {entity.id}) for index {idx}")
                if entity_type == "documentation_resources" and related_category_slug:
                    category_obj = session.query(DocumentationCategory).filter_by(slug=related_category_slug).first()
                    if category_obj:
                        entity.categories.append(category_obj)
                        logger.debug(f"    Appended category '{category_obj.name}' to resource '{entity.title}'")
                    else:
                        logger.warning(f"    Category slug '{related_category_slug}' not found for resource '{entity.title}'.")
                if entity_type == "users" and "roles" in item_data:
                    from app.db.models.role import Role
                    role_names = item_data["roles"]
                    for role_name in role_names:
                        role_obj = session.query(Role).filter_by(name=role_name).first()
                        if role_obj:
                             entity.roles.append(role_obj)
                             logger.debug(f"    Assigned role '{role_name}' to user '{entity.email}'")
                        else:
                             logger.warning(f"    Role '{role_name}' not found for user '{entity.email}'.")
            return entity
        except TypeError as e:
            logger.error(f"  TypeError creating {entity_type} index {idx}: {e}")
            logger.error(f"    Data passed: {data}")
            raise
        except Exception as e:
            logger.error(f"  Error during instance creation/flush for {entity_type} index {idx}: {e}")
            raise


    # ... (entities_order list remains the same) ...
    entities_order = [
        "documentation_categories",
        # "permissions",
        # "roles",
        "suppliers",
        "customers",
        "storage_locations",
        "storage_cells", # Depends on storage_locations
        "materials", # Depends on suppliers
        "tools", # Depends on suppliers
        "patterns",
        "components", # Depends on patterns (optional)
        "component_materials", # Depends on components, materials
        "project_templates",
        "project_template_components", # Depends on project_templates, components
        "projects", # Depends on customers, project_templates (optional)
        "project_components", # Depends on projects, components
        "timeline_tasks", # Depends on projects
        "sales", # Depends on customers, projects (optional)
        # Ensure products are seeded before sale_items if FK exists
        "products", # Assuming Product model exists and needs seeding
        "sale_items", # Depends on sales, products
        "purchases", # Depends on suppliers
        "purchase_items", # Depends on purchases, materials
        "picking_lists", # Depends on projects (optional), sales (optional)
        "picking_list_items", # Depends on picking_lists, materials, components
        "storage_assignments", # Depends on materials, storage_locations
        "tool_maintenance", # Depends on tools
        "tool_checkouts", # Depends on tools, projects (optional)
        "users", # Seed users
        "documentation_resources", # Seed resources AFTER categories
        # Add other entities in correct dependency order
    ]
    # Remove the dynamic insertion for products, ensure it's explicitly in the order
    # if "products" not in entities_order and "sale_items" in entities_order:
    #      try:
    #          sale_items_index = entities_order.index("sale_items")
    #          entities_order.insert(sale_items_index, "products")
    #      except ValueError:
    #          pass


    # ... (session handling and main loop remain the same) ...
    session = None
    try:
        session = SessionLocal()
        entity_ids: Dict[str, Dict[int, Any]] = {}
        for entity_type in entities_order:
            if entity_type in seed_data:
                logger.info(f"Seeding {entity_type}...")
                entities_data = seed_data[entity_type]
                if not isinstance(entities_data, list):
                     logger.warning(f"Seed data for '{entity_type}' is not a list. Skipping.")
                     continue
                if entity_type not in entity_ids:
                    entity_ids[entity_type] = {}
                for idx, item_data in enumerate(entities_data, 1):
                    if not isinstance(item_data, dict):
                        logger.warning(f"Item at index {idx} for '{entity_type}' is not a dictionary. Skipping.")
                        continue
                    try:
                        entity = create_entity(
                            entity_type, item_data, session, entity_ids, idx
                        )
                        if entity is not None and hasattr(entity, 'id'):
                            entity_ids[entity_type][idx] = entity.id
                        elif entity is None:
                             logger.warning(
                                f"Skipped entity creation for {entity_type} (index {idx})"
                            )
                    except Exception as e:
                        session.rollback()
                        logger.error(
                            f"Error processing {entity_type} entity (JSON index {idx}): {str(e)}"
                        )
                        raise
        session.commit()
        logger.info("Database seeding completed successfully")
        return True
    except Exception as e:
        if session: session.rollback()
        logger.error(f"Error seeding database: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    finally:
        if session: session.close()


# ... (main function remains the same) ...
def main():
    """Main function."""
    args = parse_arguments()
    try:
        from app.core.config import settings
    except ImportError:
        logger.error("Could not import settings. Ensure app/core/config.py exists and PYTHONPATH is correct.")
        sys.exit(1)

    db_path = os.path.abspath(settings.DATABASE_PATH)
    encryption_key = settings.DATABASE_ENCRYPTION_KEY
    create_db_directory(db_path)

    if settings.USE_SQLCIPHER: logger.info(f"Using SQLCipher encrypted database: {db_path}")
    else: logger.info(f"Using standard SQLite database: {db_path}")

    if args.reset:
        if not reset_database(db_path, encryption_key):
            logger.error("Database reset failed, exiting.")
            sys.exit(1)

    if not initialize_database_schema():
        logger.error("Database schema initialization failed, exiting.")
        sys.exit(1)

    if args.seed:
        seed_file_path = args.seed_file
        if not os.path.isabs(seed_file_path):
             path_from_root = project_root / seed_file_path
             if path_from_root.exists(): seed_file_path = str(path_from_root)
             else:
                 path_from_script = script_dir / seed_file_path
                 if path_from_script.exists(): seed_file_path = str(path_from_script)

        if not seed_database(seed_file_path):
            logger.error("Database seeding failed, exiting.")
            sys.exit(1)

    logger.info("Database setup completed successfully")

if __name__ == "__main__":
    main()
