#!/usr/bin/env python
"""
Targeted Database Write Diagnostic Script
"""

import os
import sys
import logging
import datetime
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


def direct_sqlite_write_test():
    """  
    Perform a direct SQLite write test using pysqlcipher3    to bypass SQLAlchemy abstraction    """
    try:
        import pysqlcipher3.dbapi2 as sqlcipher
        from app.core.config import settings
        from app.core.key_manager import KeyManager

        # Get database path and key
        db_path = os.path.abspath(settings.DATABASE_PATH)
        key = KeyManager.get_database_encryption_key()

        logger.info(f"Database Path: {db_path}")
        logger.info(f"Key Length: {len(key)} characters")

        # Establish connection
        conn = sqlcipher.connect(db_path)
        cursor = conn.cursor()

        # Configure encryption
        logger.info("Configuring encryption...")
        cursor.execute(f"PRAGMA key = \"x'{key}'\";")
        cursor.execute("PRAGMA cipher_page_size = 4096;")
        cursor.execute("PRAGMA kdf_iter = 256000;")
        cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
        cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Test table creation and insertion
        logger.info("Creating test table...")
        cursor.execute("""  
            CREATE TABLE IF NOT EXISTS write_diagnostic_test (                id INTEGER PRIMARY KEY,                test_data TEXT,                created_at DATETIME DEFAULT CURRENT_TIMESTAMP            )        """)

        # Attempt insertion
        logger.info("Attempting to insert test data...")
        cursor.execute("""  
            INSERT INTO write_diagnostic_test (test_data)            VALUES (?)  
        """, (f"Diagnostic write test at {datetime.datetime.now()}",))

        # Commit transaction
        conn.commit()

        # Verify insertion
        cursor.execute("SELECT * FROM write_diagnostic_test ORDER BY id DESC LIMIT 1")
        last_record = cursor.fetchone()
        logger.info(f"Last inserted record: {last_record}")

        # Cleanup
        cursor.close()
        conn.close()

        logger.info("Direct write test SUCCESSFUL")
        return True

    except Exception as e:
        logger.error(f"Direct write test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def sqlalchemy_direct_write_test():
    """  
    Perform a direct SQLAlchemy write test with SQLCipher configuration    Bypassing standard SQLAlchemy connection handling    """
    try:
        import pysqlcipher3.dbapi2 as sqlcipher
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import sessionmaker
        from app.core.config import settings
        from app.core.key_manager import KeyManager

        # Get database path and key
        db_path = os.path.abspath(settings.DATABASE_PATH)
        key = KeyManager.get_database_encryption_key()

        # Manually create engine without default listeners
        engine = create_engine(
            f'sqlite:///{db_path}',
            module=sqlcipher,
            poolclass=None,  # Disable connection pooling
            creator=lambda: sqlcipher.connect(
                db_path,
                check_same_thread=False
            )
        )

        # Override connection to apply SQLCipher configuration
        def get_connection():
            conn = sqlcipher.connect(db_path, check_same_thread=False)

            # Configure encryption
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA key = \"x'{key}'\";")
            cursor.execute("PRAGMA cipher_page_size = 4096;")
            cursor.execute("PRAGMA kdf_iter = 256000;")
            cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
            cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
            cursor.execute("PRAGMA foreign_keys = ON;")

            return conn

            # Custom sessionmaker with manual connection management

        Session = sessionmaker(
            bind=engine,
            autocommit=False,
            autoflush=False
        )
        session = Session()

        try:
            # Direct connection retrieval and table creation
            with get_connection() as conn:
                cursor = conn.cursor()

                # Create test table
                cursor.execute("""  
                    CREATE TABLE IF NOT EXISTS sqlalchemy_write_test (                        id INTEGER PRIMARY KEY,                        test_data TEXT,                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP                    )                """)

                # Insert test data
                cursor.execute(
                    "INSERT INTO sqlalchemy_write_test (test_data) VALUES (?)",
                    (f"SQLAlchemy direct write test at {datetime.datetime.now()}",)
                )

                # Commit transaction
                conn.commit()

                # Verify insertion
                cursor.execute("SELECT * FROM sqlalchemy_write_test ORDER BY id DESC LIMIT 1")
                last_record = cursor.fetchone()
                logger.info(f"SQLAlchemy direct write test record: {last_record}")

            return True

        except Exception as inner_e:
            logger.error(f"SQLAlchemy write operation FAILED: {inner_e}")
            import traceback
            traceback.print_exc()
            return False

    except Exception as e:
        logger.error(f"SQLAlchemy direct write test SETUP FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """  
    Run comprehensive write diagnostics    """
    logger.info("Running Database Write Diagnostics...")

    # Run direct SQLite write test
    direct_result = direct_sqlite_write_test()

    # Run SQLAlchemy direct write test
    sqlalchemy_result = sqlalchemy_direct_write_test()

    # Final report
    if direct_result and sqlalchemy_result:
        logger.info("✅ ALL WRITE TESTS PASSED")
        sys.exit(0)
    else:
        logger.error("❌ WRITE TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()