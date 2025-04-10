"""...

Revision ID: 581bca8157e3
Revises: 5e55ea21105f
Create Date: 2025-04-10 02:09:24.478633

"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '581bca8157e3'
down_revision: Union[str, None] = '5e55ea21105f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Create enum_types table
    op.create_table(
        'enum_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('table_name', sa.String(length=100), nullable=False),
        sa.Column('system_name', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('table_name'),
        sa.UniqueConstraint('system_name')
    )

    # Create enum_translations table
    op.create_table(
        'enum_translations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('enum_type', sa.String(length=100), nullable=False),
        sa.Column('enum_value', sa.String(length=100), nullable=False),
        sa.Column('locale', sa.String(length=10), nullable=False),
        sa.Column('display_text', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('enum_type', 'enum_value', 'locale', name='uq_enum_translation')
    )

    # Create initial enum type tables
    enum_types = [
        {
            "name": "MaterialType",
            "system_name": "materialType",
            "table_name": "enum_values_material_type",
        },
        {
            "name": "MaterialStatus",
            "system_name": "materialStatus",
            "table_name": "enum_values_material_status",
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
            "name": "HardwareMaterial",
            "system_name": "hardwareMaterial",
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
    ]

    # Insert enum types
    for enum_type in enum_types:
        op.execute(f"""
        INSERT INTO enum_types (name, system_name, table_name, created_at, updated_at)
        VALUES (
            '{enum_type['name']}', 
            '{enum_type['system_name']}', 
            '{enum_type['table_name']}',
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        )
        """)

        # Create the enum values table
        op.execute(f"""
        CREATE TABLE {enum_type['table_name']} (
            id SERIAL PRIMARY KEY,
            code VARCHAR(100) NOT NULL,
            display_order INTEGER NOT NULL DEFAULT 0,
            is_system BOOLEAN NOT NULL DEFAULT FALSE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            parent_id INTEGER NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT {enum_type['table_name']}_unique_code UNIQUE(code)
        )
        """)

    # Create a Python script to populate enum values
    # This is executed separately after the migration
    op.execute("""
    -- Placeholder for executing the data population script
    -- The actual data population will be done by a Python script
    SELECT 1;
    """)


def downgrade():
    # Drop enum values tables for each enum type
    enum_tables = [
        'enum_values_material_type',
        'enum_values_material_status',
        'enum_values_hardware_type',
        'enum_values_hardware_finish',
        'enum_values_hardware_material',
        'enum_values_leather_type',
        'enum_values_leather_finish',
        'enum_values_supplier_status',
        'enum_values_project_status',
        'enum_values_project_type',
        'enum_values_measurement_unit',
    ]

    for table_name in enum_tables:
        op.drop_table(table_name)

    # Drop the enum_translations table
    op.drop_table('enum_translations')

    # Drop the enum_types table
    op.drop_table('enum_types')