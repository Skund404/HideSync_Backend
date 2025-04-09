#!/usr/bin/env python
"""
Direct SQLCipher Database Connection Test
"""

import os
import pysqlcipher3.dbapi2 as sqlcipher
import logging


def test_sqlcipher_connection(key, db_path):
    """
    Attempt to directly connect to and interact with a SQLCipher database
    """
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)

    logger.info(f"Testing connection to database: {db_path}")
    logger.info(f"Key length: {len(key)} characters")

    try:
        # Attempt to connect
        conn = sqlcipher.connect(db_path)
        cursor = conn.cursor()

        # Try various key application methods
        key_methods = [
            f"PRAGMA key = \"x'{key}'\";",  # Hex-encoded key
            f"PRAGMA key = '{key}';",  # Raw key
            f"PRAGMA key = \"x'{key[:32]}'\";",  # First 32 chars of hex key
        ]

        successful_method = None
        for method in key_methods:
            try:
                logger.info(f"Trying key method: {method}")

                # Reset connection
                cursor.execute("PRAGMA rekey = '';")

                # Apply encryption key
                cursor.execute(method)

                # Standard SQLCipher configuration
                cursor.execute("PRAGMA cipher_page_size = 4096;")
                cursor.execute("PRAGMA kdf_iter = 256000;")
                cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
                cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
                cursor.execute("PRAGMA foreign_keys = ON;")

                # Attempt to read from the database
                cursor.execute("SELECT 1")
                result = cursor.fetchone()

                logger.info(f"Connection successful with method: {method}")
                logger.info(f"Test query result: {result}")

                successful_method = method
                break

            except Exception as method_error:
                logger.error(f"Method failed: {method}")
                logger.error(f"Error details: {method_error}")

        if not successful_method:
            logger.error("All connection methods failed")
            return False

        # Attempt to create a test table
        try:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS diagnostic_test (
                    id INTEGER PRIMARY KEY,
                    test_value TEXT
                )
            """
            )
            cursor.execute(
                "INSERT OR REPLACE INTO diagnostic_test (id, test_value) VALUES (1, 'SQLCipher Test')"
            )
            conn.commit()

            # Verify insertion
            cursor.execute("SELECT * FROM diagnostic_test")
            test_result = cursor.fetchone()
            logger.info(f"Test table contents: {test_result}")

        except Exception as table_error:
            logger.error(f"Error creating/testing table: {table_error}")
            return False

        return True

    except Exception as conn_error:
        logger.error(f"Connection failed: {conn_error}")
        return False
    finally:
        if "conn" in locals():
            conn.close()


def main():
    # Read key from file
    with open("/home/zombie/PycharmProjects/HideSync_Backend/dev_db.key", "r") as f:
        key = f.read().strip()

    # Database path
    db_path = "/home/zombie/PycharmProjects/HideSync_Backend/hidesync.db"

    # Run test
    test_sqlcipher_connection(key, db_path)


if __name__ == "__main__":
    main()
