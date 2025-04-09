#!/usr/bin/env python
"""
Comprehensive Database Write and Read Diagnostic Script
"""

import os
import sys
import logging
from pathlib import Path

# Add project root to Python path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent if script_dir.name == "scripts" else script_dir
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def diagnose_database_operations():
    """
    Comprehensive diagnostic for database write and read operations
    """
    try:
        # Import necessary modules
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import sessionmaker
        from app.core.config import settings
        from app.db.session import SessionLocal, EncryptionManager, use_sqlcipher
        from app.db.models.supplier import Supplier

        # Database connection details
        logger.info("Database Connection Configuration:")
        logger.info(f"Database Path: {settings.DATABASE_PATH}")
        logger.info(f"SQLCipher Enabled: {use_sqlcipher}")

        # Create a session
        db = SessionLocal()

        try:
            # Test write operation
            logger.info("\n--- TESTING WRITE OPERATION ---")
            test_supplier = Supplier(
                name="Diagnostic Test Supplier",
                category="LEATHER",
                contact_name="Test Contact",
                email="test@diagnostic.com",
                phone="555-123-123",
                address="123 Test St, Diagnostic City, DC 12345",
                website="https://diagnostic-test.com",
                status="ACTIVE",
                notes="Diagnostic test supplier for debugging",
            )

            # Add and commit the new supplier
            db.add(test_supplier)
            db.commit()
            logger.info(f"Test supplier created with ID: {test_supplier.id}")

            # Immediate read back
            logger.info("\n--- IMMEDIATE READ BACK ---")
            read_supplier = (
                db.query(Supplier)
                .filter(Supplier.name == "Diagnostic Test Supplier")
                .first()
            )

            if read_supplier:
                logger.info("Successfully read back the test supplier:")
                logger.info(f"Supplier ID: {read_supplier.id}")
                logger.info(f"Supplier Name: {read_supplier.name}")
                logger.info(f"Supplier Email: {read_supplier.email}")
            else:
                logger.error(
                    "CRITICAL: Unable to read back the newly created supplier!"
                )

            # Verify all suppliers
            logger.info("\n--- ALL SUPPLIERS ---")
            all_suppliers = db.query(Supplier).all()
            logger.info(f"Total suppliers in database: {len(all_suppliers)}")
            for supplier in all_suppliers:
                logger.info(
                    f"ID: {supplier.id}, Name: {supplier.name}, Email: {supplier.email}"
                )

        except Exception as write_error:
            logger.error(f"Write/Read operation failed: {write_error}")
            import traceback

            traceback.print_exc()
            db.rollback()

        finally:
            # Always close the session
            db.close()

    except Exception as e:
        logger.error(f"Diagnostic script failed: {e}")
        import traceback

        traceback.print_exc()


def main():
    """
    Main function to run database diagnostics
    """
    diagnose_database_operations()


if __name__ == "__main__":
    main()
