#!/usr/bin/env python
# scripts/populate_enums.py
"""
Populate database enum tables with values from existing Python enums.

This script reads all enum values from app/db/models/enums.py and populates
the corresponding database tables for the database-driven enum system.

Usage:
    python scripts/populate_enums.py
"""

import os
import sys
import inspect
from enum import Enum
from sqlalchemy import text

# Add the parent directory to sys.path to properly import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the database session management
# Use 'transaction' instead of 'db_session' based on your codebase
from app.db.session import SessionLocal, transaction, engine
from app.db.models.dynamic_enum import EnumType
import app.db.models.enums as enum_module


def populate_enum_values():
    """Populate database enum tables with values from Python enums."""
    print("Starting enum population script...")

    # Get all Enum classes from the enums module
    enum_classes = {}
    for name, obj in inspect.getmembers(enum_module):
        if inspect.isclass(obj) and issubclass(obj, Enum) and obj != Enum:
            enum_classes[name] = obj

    print(f"Found {len(enum_classes)} enum classes in enums.py")

    # Use the 'transaction' context manager from app.db.session
    with transaction() as session:
        # Get all enum types from the database
        enum_types = session.query(EnumType).all()
        if not enum_types:
            print("No enum types found in database. Have you run the migration?")
            return

        enum_type_map = {et.name: et for et in enum_types}

        # Process each enum class
        for enum_name, enum_class in enum_classes.items():
            if enum_name not in enum_type_map:
                print(f"Warning: Database enum type for {enum_name} not found, skipping...")
                continue

            enum_type = enum_type_map[enum_name]
            table_name = enum_type.table_name

            print(f"Processing {enum_name} -> {table_name}")

            # Check if table exists
            try:
                # Get existing values to avoid duplicates
                result = session.execute(text(f"SELECT code FROM {table_name}"))
                existing_codes = {row[0] for row in result}
            except Exception as e:
                print(f"Error accessing table {table_name}: {e}")
                print(f"Skipping enum {enum_name}")
                continue

            # Add each enum value
            values_added = 0
            for enum_item in enum_class:
                code = enum_item.value

                # Skip if already exists
                if code in existing_codes:
                    print(f"  - Value '{code}' already exists, skipping")
                    continue

                # Insert the enum value
                try:
                    session.execute(text(f"""
                    INSERT INTO {table_name} (code, is_system, display_order, is_active, created_at, updated_at)
                    VALUES (:code, TRUE, 0, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """), {"code": code})

                    # Add English translation
                    display_text = code.replace('_', ' ').title()
                    session.execute(text("""
                    INSERT INTO enum_translations 
                    (enum_type, enum_value, locale, display_text, created_at, updated_at)
                    VALUES (:enum_type, :enum_value, 'en', :display_text, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (enum_type, enum_value, locale) DO NOTHING
                    """), {
                        "enum_type": enum_name,
                        "enum_value": code,
                        "display_text": display_text
                    })

                    values_added += 1
                except Exception as e:
                    print(f"  - Error adding value '{code}': {e}")

            print(f"  Added {values_added} values to {table_name}")

        # No need for explicit commit here - the 'transaction' context manager handles it
        print("Enum population completed successfully!")


if __name__ == "__main__":
    populate_enum_values()