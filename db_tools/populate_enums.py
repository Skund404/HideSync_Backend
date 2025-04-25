#!/usr/bin/env python
# scripts/populate_enums.py
"""
Set up and populate database enum tables with values from Python enums.

This script ensures the necessary tables for the dynamic enum system exist,
populates the enum type definitions, creates the specific value tables,
and then populates those tables based on app/db/models/enums.py.

It is designed to be idempotent - safe to run multiple times.

Usage:
    python -m scripts.populate_enums  (Run from project root)
"""

import os
import sys
import inspect
import logging
import traceback
from enum import Enum
from sqlalchemy import text, inspect as sqlalchemy_inspect, MetaData, Table, Column, Integer, String, Boolean, ForeignKey, DateTime, Text, UniqueConstraint, PrimaryKeyConstraint
from sqlalchemy.exc import SQLAlchemyError, ProgrammingError, IntegrityError

# Add the parent directory to sys.path to properly import app modules
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
     sys.path.insert(0, project_root)

# --- Configure Logging ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

try:
    # Import the database session management and models
    from app.db.session import SessionLocal, transaction, engine
    from app.db.models.dynamic_enum import EnumType, EnumTranslation
    from app.db.models.base import Base
    # Ensure this path correctly points to your Python enums file
    import app.db.models.enums as enum_module
except ImportError as e:
    logger.error(f"Error importing required modules: {e}")
    logger.error("Ensure this script is run from the project root or adjust sys.path.")
    logger.error(f"Current sys.path: {sys.path}")
    sys.exit(1)
except Exception as e:
    logger.error(f"An unexpected error occurred during imports: {e}")
    sys.exit(1)


# --- Enum Definitions (List which Python Enums to manage) ---
# This list defines which Python enums are managed by the database system.
# The 'name' MUST match the Python Enum class name in app/db/models/enums.py
# 'system_name' is used for API lookups.
# 'table_name' is the DB table holding values for this type.
MANAGED_ENUM_DEFINITIONS = [
    {"name": "AnimalSource", "system_name": "animalSource", "table_name": "enum_values_animal_source", "description": "Source animal for leather"},
    {"name": "CommunicationChannel", "system_name": "communicationChannel", "table_name": "enum_values_communication_channel", "description": "Channels used for communication"},
    {"name": "CommunicationType", "system_name": "communicationType", "table_name": "enum_values_communication_type", "description": "Types of communication interactions"},
    {"name": "ComponentType", "system_name": "componentType", "table_name": "enum_values_component_type", "description": "Types of components used in projects"},
    {"name": "CustomerSource", "system_name": "customerSource", "table_name": "enum_values_customer_source", "description": "How customers were acquired"},
    {"name": "CustomerStatus", "system_name": "customerStatus", "table_name": "enum_values_customer_status", "description": "Status of a customer account"},
    {"name": "CustomerTier", "system_name": "customerTier", "table_name": "enum_values_customer_tier", "description": "Tier or level of a customer"},
    {"name": "DocumentationCategory", "system_name": "documentationCategory", "table_name": "enum_values_documentation_category", "description": "Categories for documentation resources"},
    {"name": "EdgeFinishType", "system_name": "edgeFinishType", "table_name": "enum_values_edge_finish_type", "description": "Methods for finishing leather edges"},
    {"name": "HardwareFinish", "system_name": "hardwareFinish", "table_name": "enum_values_hardware_finish", "description": "Finishes applied to hardware"},
    {"name": "HardwareMaterialEnum", "system_name": "hardwareMaterial", "table_name": "enum_values_hardware_material", "description": "Materials used for hardware"}, # Adjusted system_name based on previous list
    {"name": "HardwareType", "system_name": "hardwareType", "table_name": "enum_values_hardware_type", "description": "Types of hardware components"},
    {"name": "InventoryAdjustmentType", "system_name": "inventoryAdjustmentType", "table_name": "enum_values_inventory_adjustment_type", "description": "Reasons for inventory adjustments"},
    {"name": "InventoryStatus", "system_name": "inventoryStatus", "table_name": "enum_values_inventory_status", "description": "Status of inventory items"},
    {"name": "InventoryTransactionType", "system_name": "inventoryTransactionType", "table_name": "enum_values_inventory_transaction_type", "description": "Types of inventory transactions"},
    {"name": "LeatherFinish", "system_name": "leatherFinish", "table_name": "enum_values_leather_finish", "description": "Finishes applied to leather"},
    {"name": "LeatherType", "system_name": "leatherType", "table_name": "enum_values_leather_type", "description": "Types or tanning methods of leather"},
    {"name": "MaterialQualityGrade", "system_name": "materialQualityGrade", "table_name": "enum_values_material_quality_grade", "description": "Quality grading for materials"},
    {"name": "MaterialStatus", "system_name": "materialStatus", "table_name": "enum_values_material_status", "description": "Availability status of materials"},
    {"name": "MaterialType", "system_name": "materialType", "table_name": "enum_values_material_type", "description": "General types of materials used"},
    {"name": "MeasurementUnit", "system_name": "measurementUnit", "table_name": "enum_values_measurement_unit", "description": "Units for measuring materials or items"},
    {"name": "PaymentStatus", "system_name": "paymentStatus", "table_name": "enum_values_payment_status", "description": "Status of payments for sales/purchases"},
    {"name": "PickingListItemStatus", "system_name": "pickingListItemStatus", "table_name": "enum_values_picking_list_item_status", "description": "Status of individual items on a picking list"},
    {"name": "PickingListStatus", "system_name": "pickingListStatus", "table_name": "enum_values_picking_list_status", "description": "Overall status of a picking list"},
    {"name": "ProjectStatus", "system_name": "projectStatus", "table_name": "enum_values_project_status", "description": "Stages in the lifecycle of a project"},
    {"name": "ProjectType", "system_name": "projectType", "table_name": "enum_values_project_type", "description": "Types of projects undertaken"},
    {"name": "PurchaseOrderStatus", "system_name": "purchaseOrderStatus", "table_name": "enum_values_purchase_order_status", "description": "Status of purchase orders"},
    {"name": "QualityGrade", "system_name": "qualityGrade", "table_name": "enum_values_quality_grade", "description": "Quality grading for finished products"},
    {"name": "SaleStatus", "system_name": "saleStatus", "table_name": "enum_values_sale_status", "description": "Status of sales orders"},
    {"name": "SkillLevel", "system_name": "skillLevel", "table_name": "enum_values_skill_level", "description": "Skill levels for tasks or users"},
    {"name": "StorageLocationStatus", "system_name": "storageLocationStatus", "table_name": "enum_values_storage_location_status", "description": "Status of a storage location"},
    {"name": "StorageLocationType", "system_name": "storageLocationType", "table_name": "enum_values_storage_location_type", "description": "Types of storage locations"},
    {"name": "StorageSection", "system_name": "storageSection", "table_name": "enum_values_storage_section", "description": "Sections within a storage area"},
    {"name": "SupplierStatus", "system_name": "supplierStatus", "table_name": "enum_values_supplier_status", "description": "Status of a supplier"},
    {"name": "SuppliesMaterialType", "system_name": "suppliesMaterialType", "table_name": "enum_values_supplies_material_type", "description": "Types of consumable supplies"},
    {"name": "TannageType", "system_name": "tannageType", "table_name": "enum_values_tannage_type", "description": "Leather tanning methods"},
    {"name": "TimelineTaskStatus", "system_name": "timelineTaskStatus", "table_name": "enum_values_timeline_task_status", "description": "Status of tasks within a project timeline"},
    {"name": "ToolCategory", "system_name": "toolCategory", "table_name": "enum_values_tool_category", "description": "Categories of tools"},
    {"name": "ToolListStatus", "system_name": "toolListStatus", "table_name": "enum_values_tool_list_status", "description": "Status of a tool list for a project"},
    {"name": "ToolStatus", "system_name": "toolStatus", "table_name": "enum_values_tool_status", "description": "Availability status of a tool"},
    {"name": "ToolType", "system_name": "toolType", "table_name": "enum_values_tool_type", "description": "General types of tools"},
    {"name": "TransactionType", "system_name": "transactionType", "table_name": "enum_values_transaction_type", "description": "Types of financial or inventory transactions"},
    {"name": "FulfillmentStatus", "system_name": "fulfillmentStatus", "table_name": "enum_values_fulfillment_status", "description": "Status of order fulfillment"},
    {"name": "PatternFileType", "system_name": "patternFileType", "table_name": "enum_values_pattern_file_type", "description": "File types for patterns"},
    {"name": "FileType", "system_name": "fileType", "table_name": "enum_values_file_type", "description": "General file types"},
    {"name": "UserRole", "system_name": "userRole", "table_name": "enum_values_user_role", "description": "Roles assignable to users"}, # Assuming UserRole is managed

    # --- ADDED ENUMS ---
    {
        "name": "ToolCondition", # Must match Python class name in enums.py
        "system_name": "toolCondition", # Used for API lookups (camelCase)
        "table_name": "enum_values_tool_condition", # DB table name
        "description": "Physical condition of a tool"
    },
    {
        "name": "MaintenanceType", # Must match Python class name in enums.py
        "system_name": "maintenanceType", # Used for API lookups (camelCase)
        "table_name": "enum_values_maintenance_type", # DB table name
        "description": "Type of maintenance action for a tool"
    },
{
        "name": "WoodType",
        "system_name": "woodType",
        "table_name": "enum_values_wood_type",
        "description": "Species or type of wood"
    },
    {
        "name": "WoodGrain",
        "system_name": "woodGrain",
        "table_name": "enum_values_wood_grain",
        "description": "Grain pattern of wood"
    },
    {
        "name": "WoodFinish",
        "system_name": "woodFinish",
        "table_name": "enum_values_wood_finish",
        "description": "Surface finish applied to wood"
    },
    # --- END ADDED ENUMS ---
]
# --- End Enum Definitions ---

# --- SQL Template for Enum Value Tables (SQLite Compatible) ---
ENUM_VALUE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS "{table_name}" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(100) NOT NULL,
    display_order INTEGER NOT NULL DEFAULT 0,
    is_system BOOLEAN NOT NULL DEFAULT 0 CHECK (is_system IN (0, 1)),
    is_active BOOLEAN NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    parent_id INTEGER NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "{table_name}_unique_code" UNIQUE(code)
    -- Optional: Add FK constraint (ensure target table name is also quoted)
    -- CONSTRAINT "fk_{table_name}_parent" FOREIGN KEY(parent_id) REFERENCES "{table_name}"(id)
);
"""

# --- Main Function ---
def setup_and_populate_enums():
    """Creates necessary tables and populates enum data."""
    logger.info("Starting dynamic enum setup and population script...")

    try:
        # 1. Ensure core tables exist using Base metadata
        logger.info("Checking/Creating core enum tables (enum_types, enum_translations)...")
        # Use Base.metadata for potentially unmanaged tables if needed
        # Base.metadata.create_all(bind=engine, tables=[EnumType.__table__, EnumTranslation.__table__], checkfirst=True)
        # Or create individually if Base isn't tracking them (less common)
        EnumType.__table__.create(bind=engine, checkfirst=True)
        EnumTranslation.__table__.create(bind=engine, checkfirst=True)
        logger.info("Core enum tables check/creation complete.")

        # Use the 'transaction' context manager for subsequent operations
        with transaction() as session:
            logger.info("Starting database transaction.")
            inspector = sqlalchemy_inspect(engine)

            # 2. Check/Insert Enum Type Definitions
            logger.info("Checking/Inserting enum type definitions into enum_types...")
            result = session.execute(text("SELECT name FROM enum_types"))
            existing_enum_defs = {row[0] for row in result}
            definitions_added = 0
            definitions_updated = 0
            for enum_def in MANAGED_ENUM_DEFINITIONS:
                default_desc = f"Values for {enum_def['name']}"
                description = enum_def.get('description', default_desc) or default_desc # Ensure description isn't empty

                if enum_def['name'] not in existing_enum_defs:
                    logger.info(f"  Adding definition for {enum_def['name']}...")
                    new_type = EnumType(
                        name=enum_def['name'],
                        system_name=enum_def['system_name'],
                        table_name=enum_def['table_name'],
                        description=description
                    )
                    session.add(new_type)
                    definitions_added += 1
                else:
                    # Update description/system_name/table_name if changed
                    existing = session.query(EnumType).filter_by(name=enum_def['name']).first()
                    needs_update = False
                    if existing:
                        if existing.description != description:
                            existing.description = description
                            needs_update = True
                            logger.info(f"  Updating description for {enum_def['name']}")
                        if existing.system_name != enum_def['system_name']:
                            existing.system_name = enum_def['system_name']
                            needs_update = True
                            logger.info(f"  Updating system_name for {enum_def['name']} to {enum_def['system_name']}")
                        if existing.table_name != enum_def['table_name']:
                             existing.table_name = enum_def['table_name']
                             needs_update = True
                             logger.info(f"  Updating table_name for {enum_def['name']} to {enum_def['table_name']}")

                        if needs_update:
                            definitions_updated += 1

            if definitions_added > 0:
                logger.info(f"Added {definitions_added} new enum type definitions.")
            if definitions_updated > 0:
                logger.info(f"Updated {definitions_updated} existing enum type definitions.")

            if definitions_added > 0 or definitions_updated > 0:
                session.flush() # Persist changes before continuing
            else:
                 logger.info("No new enum type definitions added or updated.")


            # 3. Re-query to get all current enum types (including newly added)
            db_enum_types = session.query(EnumType).all()
            if not db_enum_types:
                logger.error("No enum types found in database after definition check. Cannot proceed.")
                return

            enum_type_map = {et.name: et for et in db_enum_types}
            logger.info(f"Processing {len(enum_type_map)} enum type definitions from database.")

            # 4. Ensure Enum Value Tables Exist
            logger.info("Checking/Creating specific enum value tables (enum_values_*)...")
            tables_created_count = 0
            for db_enum_type in db_enum_types:
                table_name = db_enum_type.table_name
                if not table_name:
                     logger.warning(f"Enum type '{db_enum_type.name}' has no table_name defined. Skipping table creation.")
                     continue
                try:
                    if not inspector.has_table(table_name):
                        logger.info(f"  Creating table '{table_name}'...")
                        create_sql = ENUM_VALUE_TABLE_SQL.format(table_name=table_name)
                        session.execute(text(create_sql))
                        tables_created_count += 1
                except ProgrammingError as pe:
                     # Handle cases where table might exist but inspector misses it (less common)
                     if "already exists" in str(pe).lower():
                          logger.warning(f"  Table '{table_name}' likely exists despite inspector check (Error: {pe}). Proceeding cautiously.")
                     else:
                          logger.error(f"  FATAL: ProgrammingError creating/verifying table '{table_name}': {pe}")
                          raise pe
                except Exception as table_create_e:
                    logger.error(f"  FATAL: Failed to create or verify table '{table_name}': {table_create_e}")
                    raise table_create_e # Stop the process

            if tables_created_count > 0:
                 logger.info(f"Created {tables_created_count} new enum value tables.")
                 session.flush() # Ensure tables exist before populating

            # 5. Populate Enum Values and Translations
            logger.info("Populating enum values and translations...")
            python_enum_classes = {
                name: obj for name, obj in inspect.getmembers(enum_module)
                if inspect.isclass(obj) and issubclass(obj, Enum) and obj != Enum
            }
            logger.info(f"Found {len(python_enum_classes)} Python Enum classes in enums module.")

            total_values_added = 0
            total_translations_processed = 0

            for db_enum_type in db_enum_types:
                enum_name = db_enum_type.name
                table_name = db_enum_type.table_name
                system_name = db_enum_type.system_name # Use system_name for translation key

                if not table_name:
                     logger.warning(f"Skipping population for enum type '{enum_name}' due to missing table name.")
                     continue

                if enum_name not in python_enum_classes:
                    logger.warning(f"Python Enum class '{enum_name}' not found, skipping population for '{table_name}'.")
                    continue

                enum_class = python_enum_classes[enum_name]
                logger.info(f"Processing values for {enum_name} ({system_name}) -> '{table_name}'")

                try:
                    # Query existing codes specifically for this table
                    result = session.execute(text(f'SELECT code FROM "{table_name}"'))
                    existing_codes = {row[0] for row in result}
                    logger.debug(f"  Found {len(existing_codes)} existing codes in '{table_name}'.")
                except ProgrammingError as pe:
                     logger.error(f"Table '{table_name}' not found when querying codes for {enum_name}: {pe}. Check table creation step. Skipping.")
                     continue
                except Exception as e:
                    logger.error(f"Error reading existing codes from '{table_name}': {e}. Skipping {enum_name}.")
                    continue

                values_added_thistype = 0
                translations_processed_thistype = 0
                for i, enum_item in enumerate(enum_class):
                    try:
                        # Use .name for the code IF values are auto() or complex objects
                        # Use .value if values are simple strings/numbers
                        # Adjust this based on how your enums are defined
                        if isinstance(enum_item.value, str) or isinstance(enum_item.value, int):
                            code = str(enum_item.value)
                        else:
                             # Fallback to name if value is complex (like auto())
                            code = enum_item.name
                            logger.warning(f"  Enum item {enum_name}.{enum_item.name} has complex value '{enum_item.value}'. Using '.name' ('{code}') as code.")

                        display_text_en = code.replace('_', ' ').title() # Default EN display text
                    except Exception as e:
                         logger.error(f"  Could not get value/name for enum item {enum_item} in {enum_name}: {e}")
                         continue

                    # --- Value Population ---
                    if code not in existing_codes:
                        try:
                            # Use parameterized query for safety
                            insert_sql = text(f"""
                            INSERT INTO "{table_name}" (code, is_system, display_order, is_active)
                            VALUES (:code, :is_system, :display_order, :is_active)
                            """)
                            session.execute(insert_sql, {
                                "code": code, "is_system": False, "display_order": i, "is_active": True
                            })
                            values_added_thistype += 1
                            total_values_added += 1
                            existing_codes.add(code) # Add to set to avoid duplicate translation attempts in same run
                        except IntegrityError:
                            logger.warning(f"  - IntegrityError (likely duplicate code '{code}') inserting into '{table_name}'. Assuming exists, continuing.")
                            existing_codes.add(code) # Ensure it's marked as existing
                        except Exception as e:
                            logger.error(f"  - Error adding value '{code}' to '{table_name}': {e}")
                            continue # Skip translation if value failed

                    # --- Translation Population (English Default) ---
                    # Check if translation already exists before attempting insert/update
                    try:
                        translation_exists_sql = text("""
                        SELECT 1 FROM enum_translations
                        WHERE enum_type = :enum_type AND enum_value = :enum_value AND locale = 'en'
                        LIMIT 1
                        """)
                        exists_result = session.execute(translation_exists_sql, {
                            "enum_type": system_name, # Use system_name for linking
                            "enum_value": code
                        }).scalar_one_or_none()

                        if not exists_result:
                             # Insert only if it doesn't exist
                             trans_insert_sql = text("""
                             INSERT INTO enum_translations
                             (enum_type, enum_value, locale, display_text, created_at, updated_at)
                             VALUES (:enum_type, :enum_value, 'en', :display_text, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                             """)
                             session.execute(trans_insert_sql, {
                                 "enum_type": system_name, # Use system_name
                                 "enum_value": code,
                                 "display_text": display_text_en
                             })
                             translations_processed_thistype += 1
                             total_translations_processed += 1
                        # else: # Optionally update if needed, but ON CONFLICT was removed
                        #    logger.debug(f"  - Translation for {system_name} / {code} / 'en' already exists. Skipping insert.")
                        #    translations_processed_thistype += 1 # Count as processed even if skipped
                        #    total_translations_processed += 1


                    except IntegrityError as ie:
                         logger.warning(f"  - IntegrityError processing translation for '{system_name}/{code}': {ie}. Skipping.")
                    except Exception as e:
                        logger.error(f"  - Error adding/checking 'en' translation for '{system_name}/{code}': {e}")


                logger.info(f"  Finished {enum_name}: Added {values_added_thistype} values, processed {translations_processed_thistype} 'en' translations.")

            logger.info(f"Enum population complete. Total values added: {total_values_added}. Total translations processed: {total_translations_processed}.")
            logger.info("Committing transaction.")
            # Commit happens automatically when 'with transaction()' block exits without error

    except Exception as e:
        logger.error(f"A critical error occurred during the enum setup/population process: {e}")
        logger.error(traceback.format_exc()) # Use traceback import
        logger.warning("Transaction rolled back due to critical error.")
    finally:
        logger.info("Enum setup and population script finished.")


if __name__ == "__main__":
    setup_and_populate_enums()