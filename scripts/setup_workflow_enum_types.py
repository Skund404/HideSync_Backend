# File: scripts/setup_workflow_enum_types.py

import sys
from pathlib import Path

# Add project root to path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from app.db.session import SessionLocal
from app.db.models.dynamic_enum import EnumType
from sqlalchemy import text
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_workflow_enum_types():
    """
    Register workflow enum types and create their dynamic tables.
    This must be run BEFORE setup_workflow_enums.py
    """
    db = SessionLocal()
    try:
        logger.info("Starting workflow enum types setup...")

        # 1. Register enum types in enum_types table
        enum_types_to_register = [
            {
                'name': 'Workflow Step Type',
                'description': 'Types of workflow steps (instruction, material, tool, etc.)',
                'table_name': 'enum_value_workflow_step_type',
                'system_name': 'workflow_step_type'
            },
            {
                'name': 'Workflow Status',
                'description': 'Status values for workflows (draft, active, published, archived)',
                'table_name': 'enum_value_workflow_status',
                'system_name': 'workflow_status'
            },
            {
                'name': 'Workflow Connection Type',
                'description': 'Types of connections between workflow steps',
                'table_name': 'enum_value_workflow_connection_type',
                'system_name': 'workflow_connection_type'
            },
            {
                'name': 'Workflow Execution Status',
                'description': 'Execution status values (active, paused, completed, failed)',
                'table_name': 'enum_value_workflow_execution_status',
                'system_name': 'workflow_execution_status'
            }
        ]

        for enum_type_data in enum_types_to_register:
            try:
                # Check if enum type already exists
                existing = db.query(EnumType).filter(
                    EnumType.system_name == enum_type_data['system_name']
                ).first()

                if not existing:
                    # Create enum type record
                    enum_type = EnumType(**enum_type_data)
                    db.add(enum_type)
                    db.flush()
                    logger.info(f"✅ Registered enum type: {enum_type_data['system_name']}")

                    # 2. Create dynamic table for this enum type
                    table_name = enum_type_data['table_name']
                    create_table_sql = text(f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        code VARCHAR(100) UNIQUE NOT NULL,
                        display_order INTEGER DEFAULT 0,
                        is_system BOOLEAN DEFAULT 0,
                        parent_id INTEGER,
                        is_active BOOLEAN DEFAULT 1,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (parent_id) REFERENCES {table_name}(id)
                    );
                    """)

                    db.execute(create_table_sql)
                    logger.info(f"✅ Created dynamic table: {table_name}")

                    # Create indexes for performance
                    index_sql = text(f"""
                    CREATE INDEX IF NOT EXISTS idx_{table_name}_code ON {table_name}(code);
                    CREATE INDEX IF NOT EXISTS idx_{table_name}_active ON {table_name}(is_active);
                    CREATE INDEX IF NOT EXISTS idx_{table_name}_order ON {table_name}(display_order);
                    """)

                    db.execute(index_sql)
                    logger.info(f"✅ Created indexes for: {table_name}")

                else:
                    logger.info(f"⚠️  Enum type already exists: {enum_type_data['system_name']}")

            except Exception as e:
                logger.error(f"❌ Error creating enum type {enum_type_data['system_name']}: {e}")
                raise

        # 3. Create additional workflow-specific tables for translations
        create_translation_tables(db)

        # Commit all changes
        db.commit()
        logger.info("🎉 Workflow enum types setup completed successfully!")

        # Print summary
        print("\n" + "=" * 60)
        print("WORKFLOW ENUM TYPES SETUP COMPLETE")
        print("=" * 60)
        print("✅ Created enum types:")
        for enum_type_data in enum_types_to_register:
            print(f"   - {enum_type_data['system_name']}")
        print("\n✅ Created dynamic tables:")
        for enum_type_data in enum_types_to_register:
            print(f"   - {enum_type_data['table_name']}")
        print("\n🔄 Next step: Run 'python scripts/setup_workflow_enums.py'")
        print("=" * 60)

    except Exception as e:
        logger.error(f"❌ Error setting up workflow enum types: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def create_translation_tables(db):
    """Create translation tables for workflow enum values."""
    try:
        logger.info("Creating enum translation tables...")

        # Create translations table for workflow enum values
        translation_tables = [
            'enum_value_workflow_step_type_translations',
            'enum_value_workflow_status_translations',
            'enum_value_workflow_connection_type_translations',
            'enum_value_workflow_execution_status_translations'
        ]

        for table_name in translation_tables:
            base_table = table_name.replace('_translations', '')
            create_translation_sql = text(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                enum_value_id INTEGER NOT NULL,
                locale VARCHAR(10) NOT NULL DEFAULT 'en',
                display_text VARCHAR(200) NOT NULL,
                description TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (enum_value_id) REFERENCES {base_table}(id) ON DELETE CASCADE,
                UNIQUE(enum_value_id, locale)
            );
            """)

            db.execute(create_translation_sql)

            # Create indexes
            index_sql = text(f"""
            CREATE INDEX IF NOT EXISTS idx_{table_name}_enum_locale 
            ON {table_name}(enum_value_id, locale);
            """)

            db.execute(index_sql)
            logger.info(f"✅ Created translation table: {table_name}")

    except Exception as e:
        logger.error(f"❌ Error creating translation tables: {e}")
        raise


def verify_setup():
    """Verify that all enum types were created successfully."""
    db = SessionLocal()
    try:
        logger.info("Verifying enum types setup...")

        expected_types = [
            'workflow_step_type',
            'workflow_status',
            'workflow_connection_type',
            'workflow_execution_status'
        ]

        for system_name in expected_types:
            enum_type = db.query(EnumType).filter(
                EnumType.system_name == system_name
            ).first()

            if enum_type:
                logger.info(f"✅ Verified: {system_name} (ID: {enum_type.id})")
            else:
                logger.error(f"❌ Missing: {system_name}")
                return False

        logger.info("🎉 All enum types verified successfully!")
        return True

    except Exception as e:
        logger.error(f"❌ Error verifying setup: {e}")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    try:
        print("🚀 Starting Workflow Enum Types Setup...")
        print("This will register enum types and create dynamic tables.")
        print("-" * 60)

        setup_workflow_enum_types()

        # Verify the setup
        if verify_setup():
            print("\n✅ Setup verification passed!")
            print("\n🔄 Next steps:")
            print("1. Run: python scripts/setup_workflow_enums.py")
            print("2. Then you can start using the workflow system!")
        else:
            print("\n❌ Setup verification failed!")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)