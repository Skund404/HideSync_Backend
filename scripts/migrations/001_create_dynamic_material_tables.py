# scripts/migrations/001_create_dynamic_material_tables.py

"""
Migration to create Dynamic Material Management System tables.

This migration creates the following tables:
- material_types
- material_type_translations
- property_definitions
- property_definition_translations
- property_enum_options
- property_enum_mappings
- material_type_properties
- dynamic_materials
- material_property_values
- material_media
- material_tags
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey, DateTime, Text, Float,
    UniqueConstraint, MetaData, Table, func
)
from sqlalchemy.sql import text
from datetime import datetime
import uuid
import json

# Migration metadata
VERSION = "001"
DESCRIPTION = "Create Dynamic Material Management System tables"


def up(session):
    """
    Apply the migration.

    Args:
        session: SQLAlchemy Session
    """
    conn = session.connection()

    # Create material_types table
    conn.execute(text("""
    CREATE TABLE material_types (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        icon TEXT,
        color_scheme TEXT,
        ui_config TEXT,
        storage_config TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        created_by INTEGER REFERENCES users(id),
        updated_at TEXT,
        is_system INTEGER DEFAULT 0,
        visibility_level TEXT DEFAULT 'all'
    )
    """))

    # Create material_type_translations table
    conn.execute(text("""
    CREATE TABLE material_type_translations (
        id INTEGER PRIMARY KEY,
        material_type_id INTEGER REFERENCES material_types(id) ON DELETE CASCADE,
        locale TEXT NOT NULL,
        display_name TEXT NOT NULL,
        description TEXT,
        UNIQUE(material_type_id, locale)
    )
    """))

    # Create property_definitions table
    conn.execute(text("""
    CREATE TABLE property_definitions (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        data_type TEXT NOT NULL,
        group_name TEXT,
        unit TEXT,
        is_required INTEGER DEFAULT 0,
        has_multiple_values INTEGER DEFAULT 0,
        validation_rules TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        created_by INTEGER REFERENCES users(id),
        updated_at TEXT,
        is_system INTEGER DEFAULT 0,
        enum_type_id INTEGER REFERENCES enum_types(id)
    )
    """))

    # Create property_definition_translations table
    conn.execute(text("""
    CREATE TABLE property_definition_translations (
        id INTEGER PRIMARY KEY,
        property_id INTEGER REFERENCES property_definitions(id) ON DELETE CASCADE,
        locale TEXT NOT NULL,
        display_name TEXT NOT NULL,
        description TEXT,
        UNIQUE(property_id, locale)
    )
    """))

    # Create property_enum_options table
    conn.execute(text("""
    CREATE TABLE property_enum_options (
        id INTEGER PRIMARY KEY,
        property_id INTEGER REFERENCES property_definitions(id) ON DELETE CASCADE,
        value TEXT NOT NULL,
        display_value TEXT NOT NULL,
        color TEXT,
        display_order INTEGER DEFAULT 0,
        UNIQUE(property_id, value)
    )
    """))

    # Create property_enum_mappings table
    conn.execute(text("""
    CREATE TABLE property_enum_mappings (
        property_id INTEGER REFERENCES property_definitions(id) ON DELETE CASCADE,
        enum_type_id INTEGER REFERENCES enum_types(id) ON DELETE CASCADE,
        PRIMARY KEY (property_id, enum_type_id)
    )
    """))

    # Create material_type_properties table
    conn.execute(text("""
    CREATE TABLE material_type_properties (
        material_type_id INTEGER REFERENCES material_types(id) ON DELETE CASCADE,
        property_id INTEGER REFERENCES property_definitions(id) ON DELETE CASCADE,
        display_order INTEGER DEFAULT 0,
        is_required INTEGER,
        is_filterable INTEGER DEFAULT 1,
        is_displayed_in_list INTEGER DEFAULT 1,
        is_displayed_in_card INTEGER DEFAULT 1,
        default_value TEXT,
        PRIMARY KEY (material_type_id, property_id)
    )
    """))

    # Create dynamic_materials table
    conn.execute(text("""
    CREATE TABLE dynamic_materials (
        id INTEGER PRIMARY KEY,
        material_type_id INTEGER REFERENCES material_types(id) NOT NULL,
        name TEXT NOT NULL,
        status TEXT DEFAULT 'in_stock',
        quantity REAL DEFAULT 0,
        unit TEXT NOT NULL,
        quality TEXT,
        supplier_id INTEGER REFERENCES suppliers(id),
        supplier TEXT,
        sku TEXT,
        description TEXT,
        reorder_point REAL DEFAULT 0,
        supplier_sku TEXT,
        cost_price REAL,
        price REAL,
        storage_location TEXT,
        notes TEXT,
        thumbnail TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        created_by INTEGER REFERENCES users(id),
        updated_at TEXT
    )
    """))

    # Create material_property_values table
    conn.execute(text("""
    CREATE TABLE material_property_values (
        id INTEGER PRIMARY KEY,
        material_id INTEGER REFERENCES dynamic_materials(id) ON DELETE CASCADE NOT NULL,
        property_id INTEGER REFERENCES property_definitions(id) NOT NULL,
        value_string TEXT,
        value_number REAL,
        value_boolean INTEGER,
        value_date TEXT,
        value_enum_id INTEGER,
        value_file_id TEXT,
        value_reference_id INTEGER,
        UNIQUE(material_id, property_id)
    )
    """))

    # Create material_media table
    conn.execute(text("""
    CREATE TABLE material_media (
        id INTEGER PRIMARY KEY,
        material_id INTEGER REFERENCES dynamic_materials(id) ON DELETE CASCADE,
        media_asset_id TEXT REFERENCES media_assets(id) ON DELETE CASCADE,
        is_primary INTEGER DEFAULT 0,
        display_order INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """))

    # Create unique index for primary media
    conn.execute(text("""
    CREATE UNIQUE INDEX idx_material_primary_media 
    ON material_media(material_id) 
    WHERE is_primary = 1
    """))

    # Create material_tags table
    conn.execute(text("""
    CREATE TABLE material_tags (
        material_id INTEGER REFERENCES dynamic_materials(id) ON DELETE CASCADE,
        tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
        PRIMARY KEY (material_id, tag_id)
    )
    """))

    # Create indices for better performance
    conn.execute(text("CREATE INDEX idx_materials_material_type_id ON dynamic_materials(material_type_id)"))
    conn.execute(text("CREATE INDEX idx_materials_status ON dynamic_materials(status)"))
    conn.execute(text("CREATE INDEX idx_materials_name ON dynamic_materials(name)"))
    conn.execute(text("CREATE INDEX idx_materials_sku ON dynamic_materials(sku)"))
    conn.execute(text("CREATE INDEX idx_property_values_material_id ON material_property_values(material_id)"))
    conn.execute(text("CREATE INDEX idx_property_values_property_id ON material_property_values(property_id)"))

    # Create default system material types
    create_default_material_types(session)

    session.commit()


def down(session):
    """
    Revert the migration.

    Args:
        session: SQLAlchemy Session
    """
    conn = session.connection()

    # Drop tables in the opposite order of creation (respecting foreign keys)
    conn.execute(text("DROP TABLE IF EXISTS material_tags"))
    conn.execute(text("DROP TABLE IF EXISTS material_media"))
    conn.execute(text("DROP TABLE IF EXISTS material_property_values"))
    conn.execute(text("DROP TABLE IF EXISTS dynamic_materials"))
    conn.execute(text("DROP TABLE IF EXISTS material_type_properties"))
    conn.execute(text("DROP TABLE IF EXISTS property_enum_mappings"))
    conn.execute(text("DROP TABLE IF EXISTS property_enum_options"))
    conn.execute(text("DROP TABLE IF EXISTS property_definition_translations"))
    conn.execute(text("DROP TABLE IF EXISTS property_definitions"))
    conn.execute(text("DROP TABLE IF EXISTS material_type_translations"))
    conn.execute(text("DROP TABLE IF EXISTS material_types"))

    session.commit()


def create_default_material_types(session):
    """
    Create default system material types and properties.

    Args:
        session: SQLAlchemy Session
    """
    conn = session.connection()

    # Function to insert a material type with translations
    def insert_material_type(name, display_name, icon=None, color_scheme=None, is_system=True, visibility_level="all"):
        # Insert material type
        conn.execute(
            text(
                "INSERT INTO material_types (name, icon, color_scheme, is_system, visibility_level, created_at) VALUES (:name, :icon, :color_scheme, :is_system, :visibility_level, datetime('now'))"),
            {
                "name": name,
                "icon": icon,
                "color_scheme": color_scheme,
                "is_system": 1 if is_system else 0,
                "visibility_level": visibility_level
            }
        )

        # Get the ID of the inserted material type
        material_type_id = conn.execute(
            text("SELECT id FROM material_types WHERE name = :name"),
            {"name": name}
        ).scalar()

        # Insert English translation
        conn.execute(
            text(
                "INSERT INTO material_type_translations (material_type_id, locale, display_name) VALUES (:material_type_id, :locale, :display_name)"),
            {
                "material_type_id": material_type_id,
                "locale": "en",
                "display_name": display_name
            }
        )

        return material_type_id

    # Function to insert a property definition with translations
    def insert_property_definition(name, display_name, data_type, group_name=None, unit=None, is_required=False,
                                   has_multiple_values=False, is_system=True, validation_rules=None, enum_type_id=None):
        # Insert property definition
        conn.execute(
            text("""
            INSERT INTO property_definitions (
                name, data_type, group_name, unit, is_required, has_multiple_values, 
                is_system, validation_rules, enum_type_id, created_at
            ) VALUES (
                :name, :data_type, :group_name, :unit, :is_required, :has_multiple_values, 
                :is_system, :validation_rules, :enum_type_id, datetime('now')
            )
            """),
            {
                "name": name,
                "data_type": data_type,
                "group_name": group_name,
                "unit": unit,
                "is_required": 1 if is_required else 0,
                "has_multiple_values": 1 if has_multiple_values else 0,
                "is_system": 1 if is_system else 0,
                "validation_rules": json.dumps(validation_rules) if validation_rules else None,
                "enum_type_id": enum_type_id
            }
        )

        # Get the ID of the inserted property definition
        property_id = conn.execute(
            text("SELECT id FROM property_definitions WHERE name = :name"),
            {"name": name}
        ).scalar()

        # Insert English translation
        conn.execute(
            text(
                "INSERT INTO property_definition_translations (property_id, locale, display_name) VALUES (:property_id, :locale, :display_name)"),
            {
                "property_id": property_id,
                "locale": "en",
                "display_name": display_name
            }
        )

        return property_id

    # Function to assign properties to material types
    def assign_property(material_type_id, property_id, display_order=0, is_required=False, is_filterable=True,
                        is_displayed_in_list=True, is_displayed_in_card=True, default_value=None):
        conn.execute(
            text("""
            INSERT INTO material_type_properties (
                material_type_id, property_id, display_order, is_required, 
                is_filterable, is_displayed_in_list, is_displayed_in_card, default_value
            ) VALUES (
                :material_type_id, :property_id, :display_order, :is_required, 
                :is_filterable, :is_displayed_in_list, :is_displayed_in_card, :default_value
            )
            """),
            {
                "material_type_id": material_type_id,
                "property_id": property_id,
                "display_order": display_order,
                "is_required": 1 if is_required else 0,
                "is_filterable": 1 if is_filterable else 0,
                "is_displayed_in_list": 1 if is_displayed_in_list else 0,
                "is_displayed_in_card": 1 if is_displayed_in_card else 0,
                "default_value": json.dumps(default_value) if default_value is not None else None
            }
        )

    # Check if any enum type exists with system_name 'material_status'
    material_status_enum_id = conn.execute(
        text("SELECT id FROM enum_types WHERE system_name = 'material_status' LIMIT 1")
    ).scalar()

    # If not found, create a new enum type for material status
    if not material_status_enum_id:
        conn.execute(
            text("""
            INSERT INTO enum_types (name, description, table_name, system_name, created_at, updated_at)
            VALUES ('Material Status', 'Status values for materials', 'enum_values_material_status', 'material_status', datetime('now'), datetime('now'))
            """)
        )

        material_status_enum_id = conn.execute(
            text("SELECT id FROM enum_types WHERE system_name = 'material_status'")
        ).scalar()

        # Create table for enum values
        conn.execute(text(f"""
        CREATE TABLE enum_values_material_status (
            id INTEGER PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            display_order INTEGER DEFAULT 0,
            is_system INTEGER DEFAULT 0,
            parent_id INTEGER,
            is_active INTEGER DEFAULT 1
        )
        """))

        # Insert default values
        status_values = [
            ("in_stock", 0),
            ("low_stock", 1),
            ("out_of_stock", 2),
            ("on_order", 3),
            ("discontinued", 4)
        ]

        for code, display_order in status_values:
            conn.execute(
                text(f"""
                INSERT INTO enum_values_material_status (code, display_order, is_system, is_active)
                VALUES (:code, :display_order, 1, 1)
                """),
                {"code": code, "display_order": display_order}
            )

            # Add translation
            display_text = " ".join(word.capitalize() for word in code.split("_"))
            conn.execute(
                text("""
                INSERT INTO enum_translations (enum_type, enum_value, locale, display_text, created_at, updated_at)
                VALUES (:enum_type, :enum_value, :locale, :display_text, datetime('now'), datetime('now'))
                """),
                {
                    "enum_type": "Material Status",
                    "enum_value": code,
                    "locale": "en",
                    "display_text": display_text
                }
            )

    # Create common properties
    color_id = insert_property_definition(
        "color", "Color", "string", "Appearance",
        is_required=False, is_system=True
    )

    size_id = insert_property_definition(
        "size", "Size", "string", "Dimensions",
        is_required=False, is_system=True
    )

    weight_id = insert_property_definition(
        "weight", "Weight", "number", "Physical Properties",
        unit="g", is_required=False, is_system=True
    )

    origin_id = insert_property_definition(
        "origin", "Country of Origin", "string", "Source",
        is_required=False, is_system=True
    )

    status_id = insert_property_definition(
        "status", "Status", "enum", "Inventory",
        is_required=True, is_system=True,
        enum_type_id=material_status_enum_id
    )

    # Material-specific properties
    thickness_id = insert_property_definition(
        "thickness", "Thickness", "number", "Dimensions",
        unit="mm", is_required=False, is_system=True
    )

    dimensions_id = insert_property_definition(
        "dimensions", "Dimensions", "string", "Dimensions",
        is_required=False, is_system=True
    )

    # Create standard material types
    leather_id = insert_material_type(
        "leather", "Leather", icon="leather",
        color_scheme="brown", is_system=True
    )

    hardware_id = insert_material_type(
        "hardware", "Hardware", icon="hardware",
        color_scheme="steel", is_system=True
    )

    supplies_id = insert_material_type(
        "supplies", "Supplies", icon="supplies",
        color_scheme="green", is_system=True
    )

    # Assign properties to material types
    # Leather
    assign_property(leather_id, color_id, 0, False, True, True, True)
    assign_property(leather_id, thickness_id, 1, True, True, True, True)
    assign_property(leather_id, size_id, 2, False, True, True, True)
    assign_property(leather_id, weight_id, 3, False, True, False, True)
    assign_property(leather_id, origin_id, 4, False, True, False, True)
    assign_property(leather_id, status_id, 5, True, True, True, True, "in_stock")

    # Hardware
    assign_property(hardware_id, color_id, 0, False, True, True, True)
    assign_property(hardware_id, size_id, 1, True, True, True, True)
    assign_property(hardware_id, weight_id, 2, False, True, False, True)
    assign_property(hardware_id, dimensions_id, 3, False, True, False, True)
    assign_property(hardware_id, origin_id, 4, False, True, False, True)
    assign_property(hardware_id, status_id, 5, True, True, True, True, "in_stock")

    # Supplies
    assign_property(supplies_id, color_id, 0, False, True, True, True)
    assign_property(supplies_id, size_id, 1, False, True, True, True)
    assign_property(supplies_id, weight_id, 2, False, True, False, True)
    assign_property(supplies_id, origin_id, 3, False, True, False, True)
    assign_property(supplies_id, status_id, 4, True, True, True, True, "in_stock")