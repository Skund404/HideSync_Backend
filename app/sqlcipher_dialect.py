# app/sqlcipher_dialect.py (moved from app/db/sqlcipher_dialect.py)

from sqlalchemy.dialects.sqlite.pysqlite import SQLiteDialect_pysqlite
from typing import Optional, Any, Callable
import logging
import threading
import os
from functools import lru_cache

logger = logging.getLogger(__name__)

# SQLCipher configuration
SQLCIPHER_PRAGMAS = {
    "cipher_page_size": "4096",
    "kdf_iter": "256000",
    "cipher_hmac_algorithm": "HMAC_SHA512",
    "cipher_kdf_algorithm": "PBKDF2_HMAC_SHA512",
    "foreign_keys": "ON",
    "journal_mode": "WAL",
    "busy_timeout": "5000",
}


class SQLCipherDialect(SQLiteDialect_pysqlite):
    """Custom SQLAlchemy dialect for SQLCipher."""

    name = "sqlcipher"
    driver = "pysqlcipher3"

    @classmethod
    def dbapi(cls):
        """Return the database API module."""
        try:
            import pysqlcipher3.dbapi2 as sqlcipher

            return sqlcipher
        except ImportError as e:
            raise ImportError(
                "pysqlcipher3 module is required for SQLCipher support"
            ) from e

    def on_connect(self):
        """Called when a connection is created."""

        def _on_connect(conn):
            """Configure SQLCipher connection with encryption key."""
            try:
                thread_id = threading.get_ident()

                # Get encryption key
                encryption_key = self._get_encryption_key()
                if not encryption_key:
                    logger.error(
                        f"Thread {thread_id}: No encryption key available for SQLCipher connection"
                    )
                    raise ValueError("Missing encryption key for SQLCipher connection")

                # Format key for PRAGMA
                key_pragma = f"\"x'{encryption_key}'\""

                # Create cursor and set key IMMEDIATELY
                cursor = conn.cursor()
                cursor.execute(f"PRAGMA key = {key_pragma};")

                # Verify the key works
                try:
                    cursor.execute("SELECT 1").fetchone()
                except Exception as e:
                    logger.error(
                        f"Thread {thread_id}: SQLCipher key verification failed: {str(e)}"
                    )
                    raise ValueError(
                        f"SQLCipher encryption key verification failed: {str(e)}"
                    )

                # Set other PRAGMA statements
                for pragma, value in SQLCIPHER_PRAGMAS.items():
                    cursor.execute(f"PRAGMA {pragma}={value};")

                cursor.close()
                logger.debug(
                    f"Thread {thread_id}: SQLCipher connection configured successfully"
                )

            except Exception as e:
                thread_id = threading.get_ident()
                logger.error(
                    f"Thread {thread_id}: Error configuring SQLCipher connection: {str(e)}"
                )
                raise

        return _on_connect

    @lru_cache(maxsize=1)
    def _get_encryption_key(self) -> Optional[str]:
        """Get encryption key safely."""
        try:
            # Import here to avoid circular imports
            from app.core.key_manager import KeyManager

            return KeyManager.get_database_encryption_key()
        except ImportError:
            logger.error("Could not import KeyManager")
            return os.environ.get("SQLCIPHER_KEY")
        except Exception as e:
            logger.error(f"Error getting encryption key: {str(e)}")
            return None


# Register the dialect with SQLAlchemy
from sqlalchemy.dialects import registry

registry.register("sqlcipher", __name__, "SQLCipherDialect")
