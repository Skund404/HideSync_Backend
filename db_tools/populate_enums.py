#!/usr/bin/env python
# scripts/populate_enums.py
"""
Set up and populate database enum tables with values from Python enums.

This script ensures the necessary tables for the dynamic enum system exist,
populates the enum type definitions, creates the specific value tables,
and then populates those tables based on app/db/models/enums.py.

It is designed to be idempotent - safe to run multiple times.

Usage:
    python scripts/populate_enums.py
"""

import os
import sys
import inspect
import logging
from enum import Enum
from sqlalchemy import text, inspect as sqlalchemy_inspect  # Renamed inspect

# Add the parent directory to sys.path to properly import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Configure Logging ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

try:
    # Import the database session management and models
    from app.db.session import SessionLocal, transaction, engine
    from app.db.models.dynamic_enum import EnumType, EnumTranslation
    from app.db.models.base import Base # Import Base for table creation
    import app.db.models.enums as enum_module
except ImportError as e:
    logger.error(f"Error importing required modules: {e}")
    logger.error("Ensure all dependencies are installed and paths are correct.")
    sys.exit(1)
except Exception as e:
    logger.error(f"An unexpected error occurred during imports: {e}")
    sys.exit(1)


# --- Enum Definitions (Copied from Alembic migration) ---
# This list defines which Python enums are managed by the database system.
MANAGED_ENUM_DEFINITIONS = [
    {
        "name": "MaterialType",
        "system_name": "materialType",
        "table_name": "enum_values_material_type",
        "description": "Types of materials (Leather, Hardware, etc.)" # Optional description
    },
    {
        "name": "MaterialStatus",
        "system_name": "materialStatus",
        "table_name": "enum_values_material_status",
        "description": "Inventory status for materials"
    },
    {
        "name": "HardwareType",
        "system_name": "hardwareType",
        "table_name": "enum_values_hardware_type",
    },
    {
        "name": "HardwareFinish",
        "system_name": "hardwareFinish",
        "table_name": "enum_values_hardware_finish",
    },
    {
        "name": "HardwareMaterialEnum", # Name matches Python Enum class
        "system_name": "hardwareMaterial", # system_name can differ if needed
        "table_name": "enum_values_hardware_material",
    },
    {
        "name": "LeatherType",
        "system_name": "leatherType",
        "table_name": "enum_values_leather_type",
    },
    {
        "name": "LeatherFinish",
        "system_name": "leatherFinish",
        "table_name": "enum_values_leather_finish",
    },
    {
        "name": "SupplierStatus",
        "system_name": "supplierStatus",
        "table_name": "enum_values_supplier_status",
    },
    {
        "name": "ProjectStatus",
        "system_name": "projectStatus",
        "table_name": "enum_values_project_status",
    },
    {
        "name": "ProjectType",
        "system_name": "projectType",
        "table_name": "enum_values_project_type",
    },
    {
        "name": "MeasurementUnit",
        "system_name": "measurementUnit",
        "table_name": "enum_values_measurement_unit",
    },
    # --- Add ALL other enums you want to manage dynamically ---
    # Example:
    {
        "name": "CustomerStatus",
        "system_name": "customerStatus",
        "table_name": "enum_values_customer_status",
    },
    {
        "name": "PaymentStatus",
        "system_name": "paymentStatus",
        "table_name": "enum_values_payment_status",
    },
    # Add SkillLevel, SaleStatus, ComponentType, etc.
    # Make sure the 'name' matches the class name in enums.py
]
# --- End Enum Definitions ---

# --- SQL Template for Enum Value Tables ---
ENUM_VALUE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS {table_name} (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) NOT NULL,
    display_order INTEGER NOT NULL DEFAULT 0,
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    parent_id INTEGER NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT {table_name}_unique_code UNIQUE(code)
    -- Optional: Add FK constraint if parent_id is used
    -- CONSTRAINT fk_{table_name}_parent FOREIGN KEY(parent_id) REFERENCES {table_name}(id)
);
"""
# Adjust SERIAL PRIMARY KEY syntax if not using PostgreSQL:
# For SQLite: id INTEGER PRIMARY KEY AUTOINCREMENT
# For MySQL: id INT AUTO_INCREMENT PRIMARY KEY
# Using SERIAL for broader compatibility guess, but ADJUST AS NEEDED for your DB.
# If using SQLite, use "INTEGER PRIMARY KEY AUTOINCREMENT" instead of "SERIAL PRIMARY KEY"

# --- Main Function ---
def setup_and_populate_enums():
    """Creates necessary tables and populates enum data."""
    logger.info("Starting dynamic enum setup and population script...")

    try:
        # 1. Ensure core tables exist (outside transaction initially)
        logger.info("Checking/Creating core enum tables (enum_types, enum_translations)...")
        # Use checkfirst=True to avoid errors if they already exist
        EnumType.__table__.create(bind=engine, checkfirst=True)
        EnumTranslation.__table__.create(bind=engine, checkfirst=True)
        logger.info("Core enum tables check/creation complete.")

        # Use the 'transaction' context manager for subsequent operations
        with transaction() as session:
            logger.info("Starting database transaction.")
            inspector = sqlalchemy_inspect(engine) # Get inspector for table checks

            # 2. Insert Enum Type Definitions if they don't exist
            logger.info("Checking/Inserting enum type definitions into enum_types...")
            result = session.execute(text("SELECT name FROM enum_types"))
            existing_enum_defs = {row[0] for row in result}
            definitions_added = 0
            for enum_def in MANAGED_ENUM_DEFINITIONS:
                if enum_def['name'] not in existing_enum_defs:
                    logger.info(f"  Adding definition for {enum_def['name']}...")
                    new_type = EnumType(
                        name=enum_def['name'],
                        system_name=enum_def['system_name'],
                        table_name=enum_def['table_name'],
                        description=enum_def.get('description') # Use .get for optional keys
                    )
                    session.add(new_type)
                    definitions_added += 1
                else:
                    logger.info(f"  Definition for {enum_def['name']} already exists.")
            if definitions_added > 0:
                logger.info(f"Added {definitions_added} new enum type definitions.")
                session.flush() # Ensure new types are persisted before creating value tables
            else:
                logger.info("No new enum type definitions needed.")

            # 3. Re-query to get all current enum types (including newly added)
            db_enum_types = session.query(EnumType).all()
            if not db_enum_types:
                logger.error("No enum types found in database after definition check. Cannot proceed.")
                return # Exit if definitions still missing

            enum_type_map = {et.name: et for et in db_enum_types}
            logger.info(f"Found {len(enum_type_map)} enum type definitions in database.")

            # 4. Ensure Enum Value Tables Exist
            logger.info("Checking/Creating specific enum value tables (enum_values_*)...")
            tables_created = 0
            for db_enum_type in db_enum_types:
                table_name = db_enum_type.table_name
                if not inspector.has_table(table_name):
                    logger.info(f"  Creating table {table_name}...")
                    try:
                         # Adjust SQL syntax for your specific DB if needed (e.g., SERIAL vs AUTOINCREMENT)
                         create_sql = ENUM_VALUE_TABLE_SQL.format(table_name=table_name)
                         # Use session.execute for DDL within transaction if dialect supports it,
                         # otherwise execute directly on engine connection outside transaction (less ideal)
                         session.execute(text(create_sql))
                         tables_created += 1
                    except Exception as table_create_e:
                         logger.error(f"  Failed to create table {table_name}: {table_create_e}")
                         # Optionally raise error or continue
                else:
                     logger.info(f"  Table {table_name} already exists.")
            if tables_created > 0:
                 logger.info(f"Created {tables_created} new enum value tables.")
                 # May need commit/flush depending on DB/dialect DDL handling in transactions
                 # session.flush() # Or session.commit() if necessary

            # 5. Populate Enum Values and Translations
            logger.info("Populating enum values and translations...")
            # Get all Enum classes from the enums module
            python_enum_classes = {}
            for name, obj in inspect.getmembers(enum_module):
                if inspect.isclass(obj) and issubclass(obj, Enum) and obj != Enum:
                    python_enum_classes[name] = obj
            logger.info(f"Found {len(python_enum_classes)} Python Enum classes in enums.py")


            # Process each managed enum type from the database
            for db_enum_type in db_enum_types:
                enum_name = db_enum_type.name
                table_name = db_enum_type.table_name

                if enum_name not in python_enum_classes:
                    logger.warning(f"Python Enum class '{enum_name}' not found in enums.py, skipping population for {table_name}.")
                    continue

                enum_class = python_enum_classes[enum_name]
                logger.info(f"Processing values for {enum_name} -> {table_name}")

                # Get existing codes from the specific value table
                try:
                    result = session.execute(text(f"SELECT code FROM {table_name}"))
                    existing_codes = {row[0] for row in result}
                except Exception as e:
                    logger.error(f"Error accessing table {table_name} for existing codes: {e}. Skipping {enum_name}.")
                    continue

                # Add each enum value from the Python class
                values_added = 0
                translations_added = 0
                for enum_item in enum_class:
                    code = enum_item.value # Assuming value is the string code

                    # Skip if value already exists in the value table
                    if code in existing_codes:
                        # logger.debug(f"  - Value '{code}' already exists in {table_name}, skipping insert.")
                        pass # Don't log every skip unless debugging
                    else:
                        # Insert the enum value
                        try:
                            session.execute(text(f"""
                            INSERT INTO {table_name} (code, is_system, display_order, is_active, created_at, updated_at)
                            VALUES (:code, TRUE, 0, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            """), {"code": code})
                            values_added += 1
                            logger.debug(f"  - Added value '{code}' to {table_name}.")
                        except Exception as e:
                            logger.error(f"  - Error adding value '{code}' to {table_name}: {e}")
                            continue # Skip translation if value insert failed

                    # Attempt to add/update English translation (idempotent using ON CONFLICT)
                    try:
                        # Basic transformation for display text
                        display_text = str(code).replace('_', ' ').title()
                        session.execute(text("""
                        INSERT INTO enum_translations
                        (enum_type, enum_value, locale, display_text, created_at, updated_at)
                        VALUES (:enum_type, :enum_value, 'en', :display_text, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT (enum_type, enum_value, locale) DO UPDATE SET
                          display_text = excluded.display_text,
                          updated_at = excluded.updated_at
                        """), {
                            "enum_type": enum_name,
                            "enum_value": code,
                            "display_text": display_text
                        })
                        # Note: ON CONFLICT syntax might vary slightly between DBs (e.g., MySQL uses ON DUPLICATE KEY UPDATE)
                        # This assumes SQLite or PostgreSQL compatible syntax. Adjust if needed.
                        translations_added += 1 # Count might be slightly off if only updates occur
                    except Exception as e:
                        logger.error(f"  - Error adding/updating translation for '{code}': {e}")

                logger.info(f"  Finished {enum_name}: Added {values_added} values, processed {translations_added} translations.")

            logger.info("Enum values and translations population complete.")
            logger.info("Transaction committed successfully.")

    except Exception as e:
        logger.error(f"An error occurred during the enum setup/population process: {e}")
        import traceback
        logger.error(traceback.format_exc())
        logger.warning("Transaction rolled back due to error.")
    finally:
        logger.info("Enum setup and population script finished.")


if __name__ == "__main__":
    setup_and_populate_enums()