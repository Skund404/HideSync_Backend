#!/usr/bin/env python
"""
db_tools/manage_db.py

Comprehensive Database Management Script for HideSync
Provides a unified interface for creating, seeding, and validating the database.
"""

import os
import sys
import logging
from pathlib import Path
import importlib.util

# Add project root to Python path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_module_from_path(module_name, file_path):
    """Load a Python module from a file path"""
    try:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        logger.error(f"Error loading module {module_name} from {file_path}: {e}")
        return None


def create_db():
    """Create the database using create_db.py"""
    create_db_path = os.path.join(script_dir, "create_db.py")
    if not os.path.exists(create_db_path):
        logger.error(f"Could not find create_db.py at {create_db_path}")
        return False

    logger.info("Creating database...")
    create_db_module = load_module_from_path("create_db", create_db_path)
    if create_db_module and hasattr(create_db_module, "main"):
        return create_db_module.main()
    else:
        logger.error("Failed to load create_db module")
        return False


def seed_db(seed_file=None):
    """Seed the database using seed_db.py"""
    seed_db_path = os.path.join(script_dir, "seed_db.py")
    if not os.path.exists(seed_db_path):
        logger.error(f"Could not find seed_db.py at {seed_db_path}")
        return False

    logger.info("Seeding database...")

    # We need to temporarily modify sys.argv to pass arguments to the module's main function
    original_argv = sys.argv.copy()

    try:
        # Set up arguments for seed_db.py
        sys.argv = [seed_db_path]
        if seed_file:
            sys.argv.extend(["--seed-file", seed_file])

        seed_db_module = load_module_from_path("seed_db", seed_db_path)
        if seed_db_module and hasattr(seed_db_module, "main"):
            return seed_db_module.main()
        else:
            logger.error("Failed to load seed_db module")
            return False
    finally:
        # Restore original argv
        sys.argv = original_argv


def validate_db():
    """Validate the database using validate_db.py"""
    validate_db_path = os.path.join(script_dir, "validate_db.py")
    if not os.path.exists(validate_db_path):
        logger.error(f"Could not find validate_db.py at {validate_db_path}")
        return False

    logger.info("Validating database...")
    validate_db_module = load_module_from_path("validate_db", validate_db_path)
    if validate_db_module and hasattr(validate_db_module, "main"):
        return validate_db_module.main()
    else:
        logger.error("Failed to load validate_db module")
        return False


def main():
    """Main function for database management"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Manage HideSync database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m db_tools.manage_db --create --seed
  python -m db_tools.manage_db --validate
  python -m db_tools.manage_db --reset --seed --seed-file custom_seed.json
        """
    )

    parser.add_argument(
        "--create",
        action="store_true",
        help="Create the database"
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Seed the database with initial data"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate the database structure and content"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset (delete and recreate) the database"
    )
    parser.add_argument(
        "--seed-file",
        type=str,
        default=None,
        help="Path to the seed data JSON file"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    args = parser.parse_args()

    # Set logging level based on verbosity
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")

    # Check if at least one action is specified
    if not (args.create or args.seed or args.validate or args.reset):
        parser.print_help()
        logger.error("Please specify at least one action (--create, --seed, --validate, or --reset)")
        return False

    # Perform actions in the requested order
    success = True

    if args.reset:
        logger.info("Reset requested, will create database from scratch")
        args.create = True

    if args.create:
        if not create_db():
            logger.error("Database creation failed")
            success = False

    if args.seed and success:
        if not seed_db(args.seed_file):
            logger.error("Database seeding failed")
            success = False

    if args.validate and success:
        if not validate_db():
            logger.error("Database validation failed")
            success = False

    if success:
        logger.info("All database operations completed successfully")
        return True
    else:
        logger.error("One or more database operations failed")
        return False


if __name__ == "__main__":
    if main():
        sys.exit(0)
    else:
        sys.exit(1)