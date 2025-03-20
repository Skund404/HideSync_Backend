# File: scripts/generate_key.py
"""
Script to generate a secure encryption key for HideSync.

This script creates a secure key file for database encryption,
ensuring proper file permissions and location.
"""

import sys
import os
import logging
import secrets
import argparse
from pathlib import Path

# Add the parent directory to Python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.core.key_manager import KeyManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Generate a secure encryption key for HideSync")
    parser.add_argument(
        "--key",
        help="Provide a specific key (not recommended). If not provided, a secure random key will be generated."
    )
    parser.add_argument(
        "--path",
        help=f"Path to store the key file (default: {settings.KEY_FILE_PATH})"
    )
    parser.add_argument(
        "--length",
        type=int,
        default=32,
        help="Length of the generated key in bytes (default: 32 = 256 bits)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing key file if it exists"
    )

    return parser.parse_args()


def main():
    """Generate a secure encryption key."""
    args = parse_args()

    # Get key path
    key_path = args.path or settings.KEY_FILE_PATH

    # Check if key file exists
    if os.path.exists(key_path) and not args.force:
        logger.error(f"Key file already exists at {key_path}. Use --force to overwrite.")
        return 1

    # Generate or use provided key
    if args.key:
        logger.warning("Using provided key. This is less secure than generating a random key.")
        key = args.key
    else:
        key = secrets.token_hex(args.length)
        logger.info(f"Generated random {args.length * 8}-bit key")

    try:
        # Create key directory if needed
        key_dir = os.path.dirname(key_path)
        if not os.path.exists(key_dir):
            os.makedirs(key_dir, mode=0o700)  # Secure directory permissions
            logger.info(f"Created key directory: {key_dir}")

        # Write key to file with secure permissions
        with open(key_path, 'w') as f:
            f.write(key)

        # Set permissions to read-only by owner (0400)
        os.chmod(key_path, 0o400)

        logger.info(f"Key file created successfully at {key_path}")
        logger.info(f"Permissions set to read-only by owner (0400)")
        logger.info("IMPORTANT: Keep this key secure and backup safely!")

        # Provide instructions for setting in environment
        logger.info("\nTo use this key with environment variable method:")
        logger.info(f"export {settings.KEY_ENVIRONMENT_VARIABLE}='{key}'")

        return 0
    except Exception as e:
        logger.error(f"Error creating key file: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())