# File: setup_database.py
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
import logging
import argparse
from pathlib import Path

# Add the project root directory to Python path
# Assuming this script is in the project root or in a direct subdirectory
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent if script_dir.name == "scripts" else script_dir
sys.path.append(str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_arguments():
    """Parse command line arguments."""
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
        help="Reset the database (delete and recreate it)"
    )
    return parser.parse_args()


def create_db_directory(db_path):
    """Create the database directory if it doesn't exist."""
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        logger.info(f"Creating database directory: {db_dir}")
        os.makedirs(db_dir, exist_ok=True)


def reset_database(db_path, encryption_key):
    """Reset the database by directly deleting and recreating it."""
    logger.info(f"Resetting database at {db_path}")

    # If database exists, delete it
    if os.path.exists(db_path):
        try:
            os.unlink(db_path)
            logger.info(f"Deleted existing database file: {db_path}")
        except Exception as e:
            logger.error(f"Error deleting database file: {str(e)}")
            return False

    # Create a new empty database with encryption
    try:
        # Import SQLCipher
        try:
            import pysqlcipher3.dbapi2 as sqlcipher
        except ImportError:
            logger.error("SQLCipher libraries not found. Please install pysqlcipher3.")
            return False

        conn = sqlcipher.connect(db_path)
        cursor = conn.cursor()

        # Set up encryption
        cursor.execute(f"PRAGMA key = '{encryption_key}'")
        cursor.execute("PRAGMA cipher_page_size = 4096")
        cursor.execute("PRAGMA kdf_iter = 64000")
        cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512")
        cursor.execute("PRAGMA foreign_keys = ON")

        # Create a simple test table to ensure the database is working
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


def initialize_database_schema():
    """Initialize database schema using SQLAlchemy models."""
    logger.info("Creating database tables...")

    try:
        # Import all models to ensure they're registered with SQLAlchemy
        import app.db.models

        # Import the SQLAlchemy engine and Base
        from app.db.models.base import Base
        from app.db.session import engine

        # Create the tables
        Base.metadata.create_all(bind=engine)

        logger.info("Database tables created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")
        return False


def seed_database(seed_file):
    """Seed the database with initial data."""
    if not os.path.exists(seed_file):
        # Try alternative paths
        alt_paths = [
            os.path.join("app", "db", "seed_data.json"),
            os.path.join(project_root, "app", "db", "seed_data.json")
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
        # Load the seed data
        with open(seed_file, 'r') as f:
            seed_data = json.load(f)

        # Import the session factory
        from app.db.session import SessionLocal

        # Create a database session
        session = SessionLocal()

        try:
            # Process each entity type in a specific order
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

            # Import all models
            from app.db.models import (
                Customer, Supplier, Material, LeatherMaterial, HardwareMaterial, SuppliesMaterial,
                Tool, StorageLocation, Pattern, Project, ProjectComponent, Sale, SaleItem,
                Purchase, PurchaseItem, TimelineTask, StorageCell, StorageAssignment, ProjectTemplate,
                DocumentationCategory, DocumentationResource, PickingList, PickingListItem,
                ToolMaintenance, ToolCheckout
            )

            # Map entity types to model classes
            model_map = {
                "documentation_categories": DocumentationCategory,
                "documentation_resources": DocumentationResource,
                "customers": Customer,
                "suppliers": Supplier,
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
            }

            # Dictionary to store created entity IDs
            entity_ids = {}

            # Import datetime for parsing
            from datetime import datetime

            # Process each entity type
            for entity_type in entities_order:
                if entity_type in seed_data:
                    logger.info(f"Seeding {entity_type}...")
                    entities_data = seed_data[entity_type]

                    if entity_type not in entity_ids:
                        entity_ids[entity_type] = {}

                    if entity_type == "materials":
                        # Special handling for materials
                        for idx, item_data in enumerate(entities_data, 1):
                            data = item_data.copy()

                            # Handle dates
                            for key, value in item_data.items():
                                if isinstance(value, str) and (key.endswith('Date') or key.endswith('At')):
                                    try:
                                        data[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                                    except ValueError:
                                        pass

                            # Handle foreign keys
                            for key in list(data.keys()):
                                if key.endswith('Id') and isinstance(data[key], int):
                                    fk_type = key[:-2].lower() + 's'  # e.g., supplierId -> suppliers
                                    if fk_type in entity_ids and data[key] in entity_ids[fk_type]:
                                        data[key] = entity_ids[fk_type][data[key]]

                            # Create the appropriate material type
                            material_type = data.pop("materialType", "LEATHER")

                            if material_type == "LEATHER":
                                entity = LeatherMaterial(**data)
                            elif material_type == "HARDWARE":
                                entity = HardwareMaterial(**data)
                            elif material_type == "SUPPLIES":
                                entity = SuppliesMaterial(**data)
                            else:
                                entity = Material(**data)

                            session.add(entity)
                            session.flush()
                            entity_ids[entity_type][idx] = entity.id
                    else:
                        # Standard entity creation
                        model = model_map.get(entity_type)
                        if not model:
                            logger.warning(f"Unknown entity type: {entity_type}")
                            continue

                        for idx, item_data in enumerate(entities_data, 1):
                            try:
                                data = item_data.copy()

                                # Handle dates
                                for key, value in item_data.items():
                                    if isinstance(value, str) and (key.endswith('Date') or key.endswith('At')):
                                        try:
                                            data[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                                        except ValueError:
                                            pass

                                # Handle foreign keys
                                for key in list(data.keys()):
                                    if key.endswith('Id') and isinstance(data[key], int):
                                        fk_type = key[:-2].lower() + 's'  # e.g., supplierId -> suppliers
                                        if fk_type in entity_ids and data[key] in entity_ids[fk_type]:
                                            data[key] = entity_ids[fk_type][data[key]]

                                # Handle 'project_id' (underscore format)
                                if 'project_id' in data and isinstance(data['project_id'], int):
                                    if 'projects' in entity_ids and data['project_id'] in entity_ids['projects']:
                                        data['project_id'] = entity_ids['projects'][data['project_id']]

                                entity = model(**data)
                                session.add(entity)
                                session.flush()
                                entity_ids[entity_type][idx] = entity.id
                            except Exception as e:
                                logger.error(f"Error creating {entity_type} entity (index {idx}): {str(e)}")
                                raise

            # Commit all changes
            session.commit()
            logger.info("Database seeding completed successfully")
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"Error seeding database: {str(e)}")
            return False
        finally:
            session.close()

    except Exception as e:
        logger.error(f"Error loading seed data: {str(e)}")
        return False


def main():
    """Main function."""
    args = parse_arguments()

    # Import settings
    from app.core.config import settings

    # Get database path and encryption key
    db_path = os.path.abspath(settings.DATABASE_PATH)
    encryption_key = settings.DATABASE_ENCRYPTION_KEY

    # Create database directory if needed
    create_db_directory(db_path)

    # Display encryption status
    if settings.USE_SQLCIPHER:
        logger.info(f"Using SQLCipher encrypted database: {db_path}")
    else:
        logger.info(f"Using standard SQLite database: {db_path}")

    # Reset database if requested
    if args.reset:
        if not reset_database(db_path, encryption_key):
            logger.error("Database reset failed, exiting.")
            sys.exit(1)

    # Initialize database schema
    if not initialize_database_schema():
        logger.error("Database schema initialization failed, exiting.")
        sys.exit(1)

    # Seed database if requested
    if args.seed and not seed_database(args.seed_file):
        logger.error("Database seeding failed, exiting.")
        sys.exit(1)

    logger.info("Database setup completed successfully")


if __name__ == "__main__":
    main()