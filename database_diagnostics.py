# Save as database_diagnostics.py
# !/usr/bin/env python
"""
HideSync Database Diagnostics Script
"""

import os
import sys
import json
from pathlib import Path
import logging

# Add project root to Python path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent if script_dir.name == "scripts" else script_dir
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def check_key_file():
    """
    Check key file configuration and contents
    """
    from app.core.config import settings

    print("\n--- KEY FILE DIAGNOSTICS ---")
    key_file_path = os.path.abspath(settings.KEY_FILE_PATH)

    # Check file existence
    if not os.path.exists(key_file_path):
        print(f"❌ Key file NOT FOUND at: {key_file_path}")
        return False

    # Check file permissions
    file_stat = os.stat(key_file_path)
    print(f"Key File Path: {key_file_path}")
    print(f"File Permissions: {oct(file_stat.st_mode & 0o777)}")

    # Read key file
    try:
        with open(key_file_path, 'r') as f:
            key = f.read().strip()

        print(f"Key Length: {len(key)} characters")
        print(f"Key (first 10 chars): {key[:10]}...")

        # Basic key validation
        if len(key) < 16:
            print("❌ WARNING: Key seems very short. This might indicate an issue.")

        return True
    except Exception as e:
        print(f"❌ Error reading key file: {e}")
        return False


def check_database_file():
    """
    Check database file configuration and existence
    """
    from app.core.config import settings

    print("\n--- DATABASE FILE DIAGNOSTICS ---")
    db_path = os.path.abspath(settings.DATABASE_PATH)

    # Check database file existence
    if not os.path.exists(db_path):
        print(f"❌ Database file NOT FOUND at: {db_path}")
        return False

    # Get file details
    db_stat = os.stat(db_path)
    print(f"Database Path: {db_path}")
    print(f"File Size: {db_stat.st_size} bytes")
    print(f"File Permissions: {oct(db_stat.st_mode & 0o777)}")

    return True


def test_database_connection():
    """
    Attempt to connect to the database and get basic info
    """
    print("\n--- DATABASE CONNECTION TEST ---")
    try:
        from app.db.session import EncryptionManager, use_sqlcipher
        from app.core.config import settings

        if not use_sqlcipher:
            print("❌ SQLCipher is not enabled in settings")
            return False

        db_path = os.path.abspath(settings.DATABASE_PATH)

        # Direct SQLCipher connection test
        sqlcipher = EncryptionManager.get_sqlcipher_module()
        conn = sqlcipher.connect(db_path)
        cursor = conn.cursor()

        # Configure encryption
        key_pragma_value = EncryptionManager.format_key_for_pragma()
        cursor.execute(f"PRAGMA key = {key_pragma_value};")
        cursor.execute("PRAGMA cipher_page_size = 4096;")
        cursor.execute("PRAGMA kdf_iter = 256000;")
        cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
        cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")

        # Get table info
        cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table';")
        table_count = cursor.fetchone()[0]

        print(f"✅ Successfully connected to database")
        print(f"Total Tables: {table_count}")

        # List table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("\nTables in Database:")
        for table in tables:
            print(f"- {table[0]}")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Database Connection Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_sqlcipher_configuration():
    """
    Check SQLCipher library and configuration
    """
    print("\n--- SQLCIPHER CONFIGURATION ---")
    try:
        import pysqlcipher3
        print("✅ pysqlcipher3 library is installed")

        # Check library version
        print(f"SQLCipher Version: {pysqlcipher3.__version__}")
    except ImportError:
        print("❌ pysqlcipher3 library is NOT installed")
        print("Install with: pip install pysqlcipher3")
        return False

    return True


def main():
    """
    Run all diagnostic checks
    """
    print("HideSync Database Diagnostics")
    print("=" * 40)

    # Run all checks
    key_check = check_key_file()
    db_file_check = check_database_file()
    sqlcipher_check = check_sqlcipher_configuration()
    conn_check = test_database_connection()

    # Summary
    print("\n--- DIAGNOSTIC SUMMARY ---")
    print(f"Key File Check:     {'✅ PASSED' if key_check else '❌ FAILED'}")
    print(f"Database File Check: {'✅ PASSED' if db_file_check else '❌ FAILED'}")
    print(f"SQLCipher Config:    {'✅ PASSED' if sqlcipher_check else '❌ FAILED'}")
    print(f"Database Connection: {'✅ PASSED' if conn_check else '❌ FAILED'}")

    # Recommendations
    if not (key_check and db_file_check and sqlcipher_check and conn_check):
        print("\nRECOMMENDATIONS:")
        print("1. Verify your .env configuration")
        print("2. Check that the database key matches the one used during creation")
        print("3. Reinstall pysqlcipher3 if needed")
        print("4. Consider recreating the database if all else fails")


if __name__ == "__main__":
    main()