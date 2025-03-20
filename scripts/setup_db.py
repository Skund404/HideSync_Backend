# File: scripts/setup_db.py
"""
Command-line script to set up the database.

This script initializes the database, creates all tables, and optionally
seeds the database with initial data. It should be run once before starting the application.
"""

import sys
import os
import logging
import json
import argparse
from pathlib import Path

# Add the parent directory to Python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_db_directory():
    """Create the database directory if it doesn't exist."""
    try:
        from app.core.config import settings
        db_path = Path(settings.DATABASE_PATH)
        db_dir = db_path.parent

        if db_dir != Path('.') and not db_dir.exists():
            logger.info(f"Creating database directory: {db_dir}")
            os.makedirs(db_dir, exist_ok=True)
    except Exception as e:
        logger.error(f"Error creating database directory: {str(e)}")
        raise


def drop_all_tables(engine):
    """
    Drop all tables using raw SQL rather than SQLAlchemy's drop_all.
    This is a more reliable approach when using SQLCipher.

    Args:
        engine: SQLAlchemy engine
    """
    # Create a connection
    connection = engine.connect()

    try:
        # Get all table names (excluding SQLite system tables)
        result = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in result]

        if tables:
            logger.info(f"Found tables to drop: {', '.join(tables)}")

            # Use a transaction to drop all tables
            trans = connection.begin()
            try:
                # Disable foreign key checks temporarily to avoid constraint issues
                connection.execute("PRAGMA foreign_keys = OFF")

                # Drop each table
                for table in tables:
                    connection.execute(f'DROP TABLE IF EXISTS "{table}"')

                # Re-enable foreign key checks
                connection.execute("PRAGMA foreign_keys = ON")

                # Commit the transaction
                trans.commit()
                logger.info("All tables dropped successfully")
            except Exception as e:
                trans.rollback()
                raise e
        else:
            logger.info("No tables found to drop")

    except Exception as e:
        logger.error(f"Error dropping tables: {str(e)}")
        raise
    finally:
        connection.close()


def main() -> None:
    """Set up the database with tables and optional seed data."""
    # Create argument parser
    parser = argparse.ArgumentParser(description="Set up the HideSync database.")
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Seed the database with initial data"
    )
    parser.add_argument(
        "--seed-file",
        type=str,
        default="./app/db/seed_data.json",
        help="Path to the seed data JSON file"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset the database before initialization (will drop all tables)"
    )

    args = parser.parse_args()

    # Create database directory if needed
    create_db_directory()

    # Import here to avoid circular imports
    from app.db.session import engine, init_db
    from app.core.config import settings

    # Display encryption status
    if settings.USE_SQLCIPHER:
        logger.info(f"Using SQLCipher encrypted database: {settings.DATABASE_PATH}")
    else:
        logger.info(f"Using standard SQLite database: {settings.DATABASE_PATH}")

    # Reset database if requested
    if args.reset:
        logger.info("Dropping all database tables...")
        try:
            # Use our custom drop tables function instead of Base.metadata.drop_all()
            drop_all_tables(engine)
        except Exception as e:
            logger.error(f"Error dropping tables: {str(e)}")
            sys.exit(1)

    # Initialize database
    logger.info("Setting up the database...")
    try:
        init_db()
        logger.info("Database setup completed successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        sys.exit(1)

    # Seed database if requested
    if args.seed:
        # Check for seed file
        seed_file = args.seed_file
        if not os.path.exists(seed_file):
            # If seed file doesn't exist in the specified path, look in app/db directory
            alt_path = os.path.join(os.path.dirname(__file__), "..", "app", "db", "seed_data.json")
            if os.path.exists(alt_path):
                seed_file = alt_path
                logger.info(f"Using seed file from alternative path: {seed_file}")
            else:
                logger.error(f"Seed file not found: {seed_file}")
                sys.exit(1)

        try:
            with open(seed_file, 'r') as f:
                seed_data = json.load(f)

            # Create seed_db.py module if it doesn't exist
            seed_db_path = os.path.join(os.path.dirname(__file__), "..", "app", "db", "seed_db.py")
            if not os.path.exists(seed_db_path):
                # First, create seed_db.py
                create_seed_db_module()

            # Import seeding function
            from app.db.seed_db import seed_database

            logger.info(f"Seeding database with data from {seed_file}")
            seed_database(seed_data)
            logger.info("Database seeding completed successfully")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in seed file: {seed_file}")
            logger.error(f"Error details: {str(e)}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error seeding database: {str(e)}")
            sys.exit(1)


def create_seed_db_module():
    """Create the seed_db.py module if it doesn't exist."""
    from pathlib import Path

    seed_db_path = Path(__file__).parent.parent / "app" / "db" / "seed_db.py"
    seed_db_content = """# File: app/db/seed_db.py
\"\"\"
Database seeding functionality for HideSync.

This module provides functions for populating the database with initial
or sample data for development and testing purposes.
\"\"\"

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.db.session import SessionLocal
from app.db.models import (
    Customer, Supplier, Material, LeatherMaterial, HardwareMaterial, SuppliesMaterial,
    Tool, StorageLocation, Pattern, Project, ProjectComponent, Sale, SaleItem,
    Purchase, PurchaseItem, TimelineTask, StorageCell, StorageAssignment, ProjectTemplate,
    DocumentationCategory, DocumentationResource, PickingList, PickingListItem,
    ToolMaintenance, ToolCheckout
)

logger = logging.getLogger(__name__)


def seed_database(seed_data: Dict[str, Any]) -> None:
    \"\"\"
    Seed the database with initial data.

    Args:
        seed_data: Dictionary containing seed data for various entities
    \"\"\"
    # Create a database session using the configured session factory
    session = SessionLocal()

    try:
        # Process the seed data in a specific order to respect foreign key constraints
        entities_order = [
            "documentation_categories",
            "documentation_resources",
            "suppliers", 
            "customers", 
            "storage_locations",
            "storage_cells",
            "materials", 
            "tools",
            "tool_maintenance",
            "patterns",
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
            "tool_checkouts"
        ]

        # Dictionary to store created entity IDs for reference
        entity_ids = {}

        for entity_type in entities_order:
            if entity_type in seed_data:
                seed_entity(session, entity_type, seed_data[entity_type], entity_ids)

        # Commit all changes at once
        session.commit()
        logger.info("Database seeding completed successfully")

    except Exception as e:
        session.rollback()
        logger.error(f"Error seeding database: {str(e)}")
        raise
    finally:
        session.close()


def seed_entity(session, entity_type: str, entities_data: List[Dict[str, Any]], 
                entity_ids: Dict[str, Dict[int, int]]) -> None:
    \"\"\"
    Seed a specific entity type.

    Args:
        session: SQLAlchemy database session
        entity_type: Type of entity to seed
        entities_data: List of entity data dictionaries
        entity_ids: Dictionary to store created entity IDs
    \"\"\"
    logger.info(f"Seeding {entity_type}...")

    # Get the appropriate model based on entity type
    model_map = {
        "documentation_categories": DocumentationCategory,
        "documentation_resources": DocumentationResource,
        "customers": Customer,
        "suppliers": Supplier,
        "materials": Material,  # Will handle subtypes separately
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
    }

    if entity_type not in model_map:
        logger.warning(f"Unknown entity type: {entity_type}")
        return

    model = model_map[entity_type]
    entity_ids[entity_type] = {}

    # Special handling for materials and related types
    if entity_type == "materials":
        seed_materials(session, entities_data, entity_ids)
    else:
        # Standard entity creation
        for idx, item_data in enumerate(entities_data, 1):
            try:
                # Create a copy of the data to avoid modifying the original
                data = item_data.copy()

                # Handle dates and timestamps
                for key, value in item_data.items():
                    if isinstance(value, str) and (
                        key.endswith('Date') or key.endswith('At') or key == 'timestamp'
                    ):
                        try:
                            data[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                        except ValueError:
                            # If date parsing fails, keep as string
                            pass

                # Handle foreign key references
                data = resolve_foreign_keys(data, entity_ids)

                # Create and add the entity
                entity = model(**data)
                session.add(entity)
                session.flush()  # Flush to get the ID without committing

                # Store the created entity's ID
                entity_ids[entity_type][idx] = entity.id

            except Exception as e:
                logger.error(f"Error creating {entity_type} entity (index {idx}): {str(e)}")
                raise


def seed_materials(session, materials_data: List[Dict[str, Any]], 
                   entity_ids: Dict[str, Dict[int, int]]) -> None:
    \"\"\"
    Seed materials with appropriate handling for material types.

    Args:
        session: SQLAlchemy database session
        materials_data: List of material data dictionaries
        entity_ids: Dictionary to store created entity IDs
    \"\"\"
    entity_ids["materials"] = {}

    for idx, material_data in enumerate(materials_data, 1):
        try:
            # Create a copy of the data to avoid modifying the original
            data = material_data.copy()

            # Handle foreign key references
            data = resolve_foreign_keys(data, entity_ids)

            # Determine material type and create the appropriate entity
            material_type = data.pop("materialType", "LEATHER")

            if material_type == "LEATHER":
                entity = LeatherMaterial(**data)
            elif material_type == "HARDWARE":
                entity = HardwareMaterial(**data)
            elif material_type == "SUPPLIES":
                entity = SuppliesMaterial(**data)
            else:
                # Default to base Material class
                entity = Material(**data)

            session.add(entity)
            session.flush()

            # Store the created entity's ID
            entity_ids["materials"][idx] = entity.id

        except Exception as e:
            logger.error(f"Error creating material entity (index {idx}): {str(e)}")
            raise


def resolve_foreign_keys(data: Dict[str, Any], entity_ids: Dict[str, Dict[int, int]]) -> Dict[str, Any]:
    \"\"\"
    Resolve foreign key references in seed data.

    Args:
        data: Entity data dictionary
        entity_ids: Dictionary of created entity IDs

    Returns:
        Updated entity data with resolved foreign keys
    \"\"\"
    # Create a copy to avoid modifying the original
    result = data.copy()

    # Define foreign key mappings (field name -> entity type)
    fk_mappings = {
        'supplierId': 'suppliers',
        'customerId': 'customers',
        'materialId': 'materials',
        'storageId': 'storage_locations',
        'patternId': 'patterns',
        'projectId': 'projects', 
        'project_id': 'projects',
        'templateId': 'project_templates',
        'saleId': 'sales',
        'sale_id': 'sales',
        'purchaseId': 'purchases',
        'purchase_id': 'purchases',
        'toolId': 'tools',
        'picking_list_id': 'picking_lists',
        'component_id': 'components',
        'fromStorageId': 'storage_locations',
        'toStorageId': 'storage_locations',
        'categoryId': 'documentation_categories'
    }

    # Replace seed indices with actual database IDs
    for field, entity_type in fk_mappings.items():
        if field in result and isinstance(result[field], int) and entity_type in entity_ids:
            seed_index = result[field]
            if seed_index in entity_ids[entity_type]:
                result[field] = entity_ids[entity_type][seed_index]

    return result
"""

    # Write the seed_db.py file
    with open(seed_db_path, 'w') as f:
        f.write(seed_db_content)

    logger.info(f"Created seed_db.py module at {seed_db_path}")


if __name__ == "__main__":
    main()