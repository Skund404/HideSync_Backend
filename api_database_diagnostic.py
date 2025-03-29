#!/usr/bin/env python
"""
API and Database Interaction Diagnostic Script
"""

import os
import sys
import logging
import json
from pathlib import Path

# Add project root to Python path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent if script_dir.name == "scripts" else script_dir
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def diagnose_api_database_interaction():
    """
    Comprehensive diagnostic for API and database interaction
    """
    try:
        # Import necessary modules
        from app.db.session import SessionLocal
        from app.db.models.supplier import Supplier
        from app.schemas.supplier import SupplierCreate
        from app.api.deps import get_db
        from sqlalchemy.orm import Session

        logger.info("--- API DATABASE INTERACTION DIAGNOSTIC ---")

        # Create a database session
        db = next(get_db())

        try:
            # Prepare a test supplier data payload
            supplier_data = SupplierCreate(
                name="API Diagnostic Supplier",
                category="LEATHER",
                contact_name="API Test Contact",
                email="api-test@diagnostic.com",
                phone="555-API-TEST",
                address="456 API Test St, Diagnostic City, DC 54321",
                website="https://api-diagnostic-test.com",
                status="ACTIVE",
                notes="API diagnostic test supplier for debugging"
            )

            logger.info("Prepared Supplier Create Payload:")
            logger.info(json.dumps(supplier_data.dict(), indent=2))

            # Attempt to create supplier via database session
            new_supplier = Supplier(**supplier_data.dict())
            db.add(new_supplier)
            db.commit()
            db.refresh(new_supplier)

            logger.info(f"Supplier created via direct DB session. ID: {new_supplier.id}")

            # Verify supplier was created
            verify_supplier = db.query(Supplier).filter(
                Supplier.email == "api-test@diagnostic.com"
            ).first()

            if verify_supplier:
                logger.info("Verification Successful:")
                logger.info(f"Supplier ID: {verify_supplier.id}")
                logger.info(f"Supplier Name: {verify_supplier.name}")
            else:
                logger.error("CRITICAL: Unable to verify supplier creation!")

            # List all suppliers to check
            all_suppliers = db.query(Supplier).all()
            logger.info("\n--- ALL SUPPLIERS IN DATABASE ---")
            for supplier in all_suppliers:
                logger.info(f"ID: {supplier.id}, Name: {supplier.name}, Email: {supplier.email}")

        except Exception as create_error:
            logger.error(f"Supplier creation failed: {create_error}")
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
    Main function to run API and database diagnostics
    """
    diagnose_api_database_interaction()

if __name__ == "__main__":
    main()