import os
import logging
import binascii
import pysqlcipher3.dbapi2 as sqlcipher


def create_encrypted_database(key, db_path):
    """
    Explicitly create an encrypted SQLCipher database with comprehensive initialization
    """
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

    # Remove existing database files if they exist
    for ext in ['', '-shm', '-wal']:
        full_path = db_path + ext
        if os.path.exists(full_path):
            os.remove(full_path)
            logger.info(f"Removed existing file: {full_path}")

    try:
        # Connect to the database
        conn = sqlcipher.connect(db_path)
        cursor = conn.cursor()

        # Explicit key setup with detailed configuration
        # Use direct string interpolation for PRAGMA statements
        cursor.execute(f"PRAGMA key = \"x'{key}'\";")
        cursor.execute("PRAGMA cipher_page_size = 4096;")
        cursor.execute("PRAGMA kdf_iter = 256000;")
        cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
        cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Create a test table to verify encryption works
        cursor.execute("""
            CREATE TABLE test_encryption (
                id INTEGER PRIMARY KEY,
                value TEXT
            )
        """)

        # Insert a test record
        cursor.execute("INSERT INTO test_encryption (value) VALUES ('Test Encryption')")
        conn.commit()

        # Close and reopen the connection to verify encryption
        conn.close()

        # Reopen with the same key
        conn = sqlcipher.connect(db_path)
        cursor = conn.cursor()

        # Attempt to decrypt
        cursor.execute(f"PRAGMA key = \"x'{key}'\";")

        # Try to read the test table
        cursor.execute("SELECT * FROM test_encryption")
        result = cursor.fetchone()
        logger.info(f"Test record retrieved: {result}")

        conn.close()
        logger.info("Encrypted database created and verified successfully")
        return True

    except Exception as e:
        logger.error(f"Error creating encrypted database: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    # Read key from file
    with open('/home/zombie/PycharmProjects/HideSync_Backend/dev_db.key', 'r') as f:
        key = f.read().strip()

    # Database path
    db_path = "/home/zombie/PycharmProjects/HideSync_Backend/hidesync.db"

    # Create encrypted database
    create_encrypted_database(key, db_path)


if __name__ == "__main__":
    main()