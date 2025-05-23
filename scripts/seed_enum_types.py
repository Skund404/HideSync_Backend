# scripts/seed_enum_types.py
import logging
import os
import re
import sys
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.db.models.enums import (
    WorkflowStepType,
    WorkflowConnectionType,
    WorkflowStatus,
    WorkflowThemeStyle
)


# --- Path Adjustment ---
# Get the directory containing the 'scripts' folder (project root)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root) # Add project root to the beginning of the path
# --- End Path Adjustment ---

# --- Project Imports ---
# Try importing again with the potentially corrected path
try:
    from app.db.session import SessionLocal
    from app.db.models.dynamic_enum import EnumType
    # from app.core.config import settings # Uncomment if needed
    # Correct the import path based on the provided file structure
    import app.db.models.enums as project_enums # <--- CORRECTED IMPORT
    print("Successfully imported project modules.") # Add confirmation
except ImportError as e:
    print(f"Error importing project modules: {e}")
    print("Please ensure this script is run from the project root directory")
    print(f"Project root determined as: {project_root}")
    print(f"Current sys.path: {sys.path}")
    sys.exit(1)
# --- End Project Imports ---

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration: List the Python Enums from app.db.models.enums to Seed ---
# Add ALL Enum classes from app.db.models.enums that should be represented in the enum_types table.
# Exclude any enums that are purely static or configuration-based (like UserRole).
ENUM_CLASSES_TO_SEED = [
    project_enums.AnimalSource,
    project_enums.CommunicationChannel,
    project_enums.CommunicationType,
    project_enums.ComponentType,
    project_enums.CustomerSource,
    project_enums.CustomerStatus,
    project_enums.CustomerTier,
    project_enums.DocumentationCategory,
    project_enums.EdgeFinishType,
    project_enums.HardwareFinish,
    project_enums.HardwareMaterialEnum,
    project_enums.HardwareType,
    project_enums.InventoryAdjustmentType,
    project_enums.InventoryStatus,
    project_enums.InventoryTransactionType,
    project_enums.LeatherFinish,
    project_enums.LeatherType,
    project_enums.MaterialQualityGrade,
    project_enums.MaterialStatus,
    project_enums.MaterialType,
    project_enums.MeasurementUnit,
    project_enums.PaymentStatus,
    project_enums.PickingListItemStatus,
    project_enums.PickingListStatus,
    project_enums.ProjectStatus,
    project_enums.ProjectType,
    project_enums.PurchaseOrderStatus, # Using this one, assuming PurchaseStatus is legacy/duplicate
    project_enums.QualityGrade,
    project_enums.SaleStatus,
    project_enums.SkillLevel,
    project_enums.StorageLocationStatus,
    project_enums.StorageLocationType,
    project_enums.StorageSection,
    project_enums.SupplierStatus,
    project_enums.SuppliesMaterialType,
    project_enums.TannageType,
    project_enums.TimelineTaskStatus,
    project_enums.ToolCategory,
    project_enums.ToolListStatus,
    project_enums.ToolStatus,
    project_enums.ToolType,
    project_enums.TransactionType,
    project_enums.FulfillmentStatus,
    project_enums.PatternFileType,
    project_enums.FileType,
    # --- Add any other custom enums from app.db.models.enums if needed ---
    # --- DO NOT ADD UserRole unless you intend to manage it dynamically ---
]
# --- End Configuration ---

def generate_names(enum_class_name: str) -> tuple[str, str, str]:
    """Generates user-friendly name, system_name, and table_name from CamelCase class name."""
    # User-friendly name (e.g., "MaterialType" -> "Material Type")
    name = re.sub(r'(?<!^)(?=[A-Z])', ' ', enum_class_name).title()

    # System name (e.g., "MaterialType" -> "material_type")
    system_name = re.sub(r'(?<!^)(?=[A-Z])', '_', enum_class_name).lower()

    # Table name convention used by EnumService: "enum_value_{system_name}"
    table_name = f"enum_value_{system_name}"

    return name, system_name, table_name

def seed_enum_types_table(db: Session):
    """Checks the enum_types table and seeds it if empty."""
    try:
        logger.info("Checking 'enum_types' table...")
        existing_count = db.query(EnumType).count()

        if existing_count > 0:
            logger.info(f"Found {existing_count} entries in 'enum_types'. No seeding required.")
            # Optional: Add logic here to update descriptions or check for missing enums if needed
            return

        logger.info("'enum_types' table appears empty. Proceeding with seeding...")
        added_count = 0
        existing_system_names = set() # Keep track during this run

        for enum_class in ENUM_CLASSES_TO_SEED:
            if not hasattr(enum_class, '__name__'):
                logger.warning(f"Item {enum_class} in ENUM_CLASSES_TO_SEED is not a class. Skipping.")
                continue

            class_name = enum_class.__name__
            name, system_name, table_name = generate_names(class_name)

            # Prevent duplicate system_names within this seeding run
            if system_name in existing_system_names:
                 logger.warning(f"Duplicate system_name '{system_name}' generated for {class_name}. Skipping.")
                 continue

            logger.info(f"Preparing: Name='{name}', SystemName='{system_name}', TableName='{table_name}'")
            enum_type_entry = EnumType(
                name=name,
                system_name=system_name,
                table_name=table_name,
                description=f"Managed enum for {name}" # Auto-generated description
            )
            db.add(enum_type_entry)
            existing_system_names.add(system_name)
            added_count += 1

        if added_count > 0:
            logger.info(f"Committing {added_count} new enum types...")
            db.commit()
            logger.info(f"Successfully added {added_count} enum types to the 'enum_types' table.")
        else:
            logger.info("No new enum types were added.")

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during seeding: {e}", exc_info=True)
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"An unexpected error occurred during seeding: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    logger.info("Starting Enum Types Seeding Script...")
    # Assuming SessionLocal handles connection URL and SQLCipher key PRAGMA
    # logger.info(f"Using database defined via SessionLocal setup.")

    db: Session | None = None
    try:
        db = SessionLocal()
        logger.info("Database session obtained.")

        # Run the main seeding logic
        seed_enum_types_table(db)

        logger.info("Seeding script finished successfully.")

    except ImportError:
         # Error already printed in the import block
         pass # Exit handled in import block
    except SQLAlchemyError as e:
        logger.error(f"Failed to establish database session or perform operation: {e}", exc_info=True)
        logger.error("Check database connection details and SQLCipher key setup in app/db/session.py.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        if db:
            db.close()
            logger.info("Database session closed.")