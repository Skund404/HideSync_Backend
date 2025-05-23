# File: scripts/setup_workflow_enums.py

import sys
from pathlib import Path

# Add project root to path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from app.db.session import SessionLocal
from app.services.enum_service import EnumService
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_workflow_enums():
    """
    Setup workflow-specific enum values.
    This must be run AFTER setup_workflow_enum_types.py
    """
    db = SessionLocal()
    try:
        logger.info("Starting workflow enum values setup...")
        enum_service = EnumService(db)

        # Setup workflow step types
        setup_workflow_step_types(enum_service)

        # Setup workflow statuses
        setup_workflow_statuses(enum_service)

        # Setup workflow connection types
        setup_workflow_connection_types(enum_service)

        # Setup workflow execution statuses
        setup_workflow_execution_statuses(enum_service)

        logger.info("🎉 Workflow enum values setup completed successfully!")

        # Print summary
        print_setup_summary()

    except Exception as e:
        logger.error(f"❌ Error setting up workflow enums: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def setup_workflow_step_types(enum_service: EnumService):
    """Setup workflow step type enum values."""
    logger.info("Setting up workflow step types...")

    step_types = [
        {
            'code': 'instruction',
            'display_text': 'Instruction',
            'description': 'Step that provides instructions or guidance',
            'display_order': 1,
            'is_system': True
        },
        {
            'code': 'material',
            'display_text': 'Material Selection',
            'description': 'Step for selecting or preparing materials',
            'display_order': 2,
            'is_system': True
        },
        {
            'code': 'tool',
            'display_text': 'Tool Usage',
            'description': 'Step that involves using specific tools',
            'display_order': 3,
            'is_system': True
        },
        {
            'code': 'time',
            'display_text': 'Wait Time',
            'description': 'Step that requires waiting or drying time',
            'display_order': 4,
            'is_system': True
        },
        {
            'code': 'decision',
            'display_text': 'Decision Point',
            'description': 'Step where user makes a choice that affects workflow path',
            'display_order': 5,
            'is_system': True
        },
        {
            'code': 'milestone',
            'display_text': 'Milestone',
            'description': 'Important checkpoint or achievement in the workflow',
            'display_order': 6,
            'is_system': True
        },
        {
            'code': 'outcome',
            'display_text': 'Outcome',
            'description': 'Final result or end point of the workflow',
            'display_order': 7,
            'is_system': True
        },
        {
            'code': 'quality_check',
            'display_text': 'Quality Check',
            'description': 'Step for inspecting quality or validating results',
            'display_order': 8,
            'is_system': True
        },
        {
            'code': 'documentation',
            'display_text': 'Documentation',
            'description': 'Step for recording information or taking photos',
            'display_order': 9,
            'is_system': True
        }
    ]

    for step_type in step_types:
        try:
            enum_service.create_enum_value('workflow_step_type', step_type)
            logger.info(f"✅ Created step type: {step_type['code']}")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info(f"⚠️  Step type already exists: {step_type['code']}")
            else:
                logger.error(f"❌ Error creating step type {step_type['code']}: {e}")
                raise


def setup_workflow_statuses(enum_service: EnumService):
    """Setup workflow status enum values."""
    logger.info("Setting up workflow statuses...")

    statuses = [
        {
            'code': 'draft',
            'display_text': 'Draft',
            'description': 'Workflow is being created or edited',
            'display_order': 1,
            'is_system': True
        },
        {
            'code': 'active',
            'display_text': 'Active',
            'description': 'Workflow is ready for use and execution',
            'display_order': 2,
            'is_system': True
        },
        {
            'code': 'published',
            'display_text': 'Published',
            'description': 'Workflow is published as a template for others to use',
            'display_order': 3,
            'is_system': True
        },
        {
            'code': 'archived',
            'display_text': 'Archived',
            'description': 'Workflow is no longer active but preserved for reference',
            'display_order': 4,
            'is_system': True
        },
        {
            'code': 'deprecated',
            'display_text': 'Deprecated',
            'description': 'Workflow is outdated and should not be used for new executions',
            'display_order': 5,
            'is_system': True
        }
    ]

    for status in statuses:
        try:
            enum_service.create_enum_value('workflow_status', status)
            logger.info(f"✅ Created status: {status['code']}")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info(f"⚠️  Status already exists: {status['code']}")
            else:
                logger.error(f"❌ Error creating status {status['code']}: {e}")
                raise


def setup_workflow_connection_types(enum_service: EnumService):
    """Setup workflow connection type enum values."""
    logger.info("Setting up workflow connection types...")

    connection_types = [
        {
            'code': 'sequential',
            'display_text': 'Sequential',
            'description': 'Standard sequential flow from one step to the next',
            'display_order': 1,
            'is_system': True
        },
        {
            'code': 'conditional',
            'display_text': 'Conditional',
            'description': 'Connection that depends on a condition being met',
            'display_order': 2,
            'is_system': True
        },
        {
            'code': 'parallel',
            'display_text': 'Parallel',
            'description': 'Multiple steps can be executed simultaneously',
            'display_order': 3,
            'is_system': True
        },
        {
            'code': 'choice',
            'display_text': 'Choice',
            'description': 'User chooses which path to take',
            'display_order': 4,
            'is_system': True
        },
        {
            'code': 'fallback',
            'display_text': 'Fallback',
            'description': 'Alternative path if primary path fails',
            'display_order': 5,
            'is_system': True
        },
        {
            'code': 'loop',
            'display_text': 'Loop',
            'description': 'Connection that creates a loop or repetition',
            'display_order': 6,
            'is_system': True
        }
    ]

    for connection_type in connection_types:
        try:
            enum_service.create_enum_value('workflow_connection_type', connection_type)
            logger.info(f"✅ Created connection type: {connection_type['code']}")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info(f"⚠️  Connection type already exists: {connection_type['code']}")
            else:
                logger.error(f"❌ Error creating connection type {connection_type['code']}: {e}")
                raise


def setup_workflow_execution_statuses(enum_service: EnumService):
    """Setup workflow execution status enum values."""
    logger.info("Setting up workflow execution statuses...")

    execution_statuses = [
        {
            'code': 'active',
            'display_text': 'Active',
            'description': 'Workflow execution is currently in progress',
            'display_order': 1,
            'is_system': True
        },
        {
            'code': 'paused',
            'display_text': 'Paused',
            'description': 'Workflow execution is temporarily paused',
            'display_order': 2,
            'is_system': True
        },
        {
            'code': 'completed',
            'display_text': 'Completed',
            'description': 'Workflow execution finished successfully',
            'display_order': 3,
            'is_system': True
        },
        {
            'code': 'failed',
            'display_text': 'Failed',
            'description': 'Workflow execution encountered an error and could not complete',
            'display_order': 4,
            'is_system': True
        },
        {
            'code': 'cancelled',
            'display_text': 'Cancelled',
            'description': 'Workflow execution was cancelled by the user',
            'display_order': 5,
            'is_system': True
        },
        {
            'code': 'timeout',
            'display_text': 'Timeout',
            'description': 'Workflow execution exceeded the maximum allowed time',
            'display_order': 6,
            'is_system': True
        }
    ]

    for execution_status in execution_statuses:
        try:
            enum_service.create_enum_value('workflow_execution_status', execution_status)
            logger.info(f"✅ Created execution status: {execution_status['code']}")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info(f"⚠️  Execution status already exists: {execution_status['code']}")
            else:
                logger.error(f"❌ Error creating execution status {execution_status['code']}: {e}")
                raise


def print_setup_summary():
    """Print a summary of the enum setup."""
    print("\n" + "=" * 60)
    print("WORKFLOW ENUM VALUES SETUP COMPLETE")
    print("=" * 60)
    print("✅ Created enum values for:")
    print("   📋 Workflow Step Types (9 types)")
    print("      - instruction, material, tool, time, decision, milestone,")
    print("        outcome, quality_check, documentation")
    print("\n   🔄 Workflow Statuses (5 statuses)")
    print("      - draft, active, published, archived, deprecated")
    print("\n   🔗 Connection Types (6 types)")
    print("      - sequential, conditional, parallel, choice, fallback, loop")
    print("\n   ⚡ Execution Statuses (6 statuses)")
    print("      - active, paused, completed, failed, cancelled, timeout")
    print("\n🎉 Workflow system is now ready to use!")
    print("=" * 60)


def verify_enum_setup():
    """Verify that all enum values were created successfully."""
    db = SessionLocal()
    try:
        logger.info("Verifying enum values setup...")
        enum_service = EnumService(db)

        # Check each enum type has values
        enum_checks = [
            ('workflow_step_type', 9),
            ('workflow_status', 5),
            ('workflow_connection_type', 6),
            ('workflow_execution_status', 6)
        ]

        all_good = True
        for system_name, expected_count in enum_checks:
            try:
                values = enum_service.get_enum_values(system_name, 'en')
                actual_count = len(values)

                if actual_count >= expected_count:
                    logger.info(f"✅ {system_name}: {actual_count} values")
                else:
                    logger.error(f"❌ {system_name}: only {actual_count}/{expected_count} values")
                    all_good = False

            except Exception as e:
                logger.error(f"❌ Error checking {system_name}: {e}")
                all_good = False

        return all_good

    except Exception as e:
        logger.error(f"❌ Error verifying enum setup: {e}")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    try:
        print("🚀 Starting Workflow Enum Values Setup...")
        print("This will populate enum values for the workflow system.")
        print("-" * 60)

        setup_workflow_enums()

        # Verify the setup
        if verify_enum_setup():
            print("\n✅ Enum values verification passed!")
            print("\n🎯 Setup Complete! You can now:")
            print("1. Create workflows using the API")
            print("2. Start workflow executions")
            print("3. Import/export workflow presets")
            print("4. Use the workflow management system")
        else:
            print("\n❌ Enum values verification failed!")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        print("Make sure you ran 'setup_workflow_enum_types.py' first!")
        sys.exit(1)