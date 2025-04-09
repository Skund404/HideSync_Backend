#!/usr/bin/env python
"""
This script will verify SQLCipher parameters by directly testing the database.
"""

import os
import sys
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add the project root to the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, ".."))
sys.path.insert(0, project_root)

# Import our modules
from app.core.key_manager import KeyManager
from app.db.session import EncryptionManager
from app.core.config import settings

# Get the proper database path
db_path = os.path.join(project_root, "hidesync.db")

logger.info(f"Project root: {project_root}")
logger.info(f"Testing database encryption with path: {db_path}")

# Get encryption key - no need to call an initialize method
key = KeyManager.get_database_encryption_key()
logger.info(f"Key retrieved: {key[:4]}...{key[-4:] if len(key) > 8 else ''}")

# Test database access using EncryptionManager directly
if not os.path.exists(db_path):
    logger.error(f"Database file not found: {db_path}")
    sys.exit(1)

logger.info(f"Testing database with EncryptionManager.test_encrypted_database")
success = EncryptionManager.test_encrypted_database(db_path)

if success:
    logger.info("✓ Successfully accessed encrypted database!")

    # Get a connection and list tables
    conn = EncryptionManager.get_encrypted_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    logger.info(f"Found {len(tables)} tables:")
    for table in tables:
        logger.info(f"  - {table[0]}")

    # Check for users table and count records
    try:
        cursor.execute("SELECT COUNT(*) FROM users;")
        user_count = cursor.fetchone()[0]
        logger.info(f"Users table has {user_count} records")

        # Print first user info
        cursor.execute("SELECT id, email, username FROM users LIMIT 1;")
        user = cursor.fetchone()
        if user:
            logger.info(
                f"First user: ID={user[0]}, Email={user[1]}, Username={user[2]}"
            )
    except Exception as e:
        logger.error(f"Error querying users table: {e}")

    cursor.close()
    conn.close()
else:
    logger.error("✗ Failed to access the database with EncryptionManager")

    # Dump encryption parameters for debugging
    logger.info("Current encryption parameters:")
    logger.info(f"  - Key loaded: {key is not None}")
    logger.info(f"  - Key length: {len(key) if key else 'N/A'}")
    logger.info(
        f"  - SQLCipher available: {EncryptionManager.is_sqlcipher_available()}"
    )

    # Try alternate cipher parameters
    logger.info("Trying alternate encryption parameters...")

    try:
        sqlcipher = EncryptionManager.get_sqlcipher_module()
        conn = sqlcipher.connect(db_path)
        cursor = conn.cursor()

        # Method 1: Standard SQLCipher 4
        try:
            logger.info("Method 1: Standard SQLCipher 4")
            cursor.execute(f"PRAGMA key='{key}';")
            cursor.execute("SELECT count(*) FROM sqlite_master;")
            result = cursor.fetchone()
            logger.info(f"✓ Method 1 succeeded! Found {result[0]} tables")
        except Exception as e:
            logger.error(f"✗ Method 1 failed: {e}")

        # Method 2: SQLCipher 3 compatibility
        try:
            logger.info("Method 2: SQLCipher 3 compatibility")
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA key='{key}';")
            cursor.execute("PRAGMA cipher_compatibility=3;")
            cursor.execute("SELECT count(*) FROM sqlite_master;")
            result = cursor.fetchone()
            logger.info(f"✓ Method 2 succeeded! Found {result[0]} tables")
        except Exception as e:
            logger.error(f"✗ Method 2 failed: {e}")

        # Method 3: Legacy mode
        try:
            logger.info("Method 3: Legacy mode with kdf_iter=64000")
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA key='{key}';")
            cursor.execute("PRAGMA cipher_compatibility=3;")
            cursor.execute("PRAGMA kdf_iter=64000;")
            cursor.execute("SELECT count(*) FROM sqlite_master;")
            result = cursor.fetchone()
            logger.info(f"✓ Method 3 succeeded! Found {result[0]} tables")
        except Exception as e:
            logger.error(f"✗ Method 3 failed: {e}")

        # Close resources
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error testing alternate methods: {e}")
