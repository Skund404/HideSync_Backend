#!/usr/bin/env python
"""
HideSync Database Diagnostics Tool
"""

import os
import sys
import psutil
import gc
import time
from pathlib import Path
import logging

# Add project root to Python path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pysqlcipher3.dbapi2 as sqlcipher
from app.core.config import settings
from app.core.key_manager import KeyManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_memory_usage():
    """Get current memory usage in MB"""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    return memory_info.rss / (1024 * 1024)


def test_direct_query(db_path, key, table_name, limit=100):
    """Test direct query with pysqlcipher3"""
    logger.info(f"Testing direct query on {table_name} with limit {limit}")

    # Memory before
    mem_before = get_memory_usage()
    logger.info(f"Memory before: {mem_before:.2f} MB")

    # Execute query
    conn = sqlcipher.connect(db_path)
    cursor = conn.cursor()

    # Configure encryption
    cursor.execute(f"PRAGMA key = \"x'{key}'\";")
    cursor.execute("PRAGMA cipher_page_size = 4096;")
    cursor.execute("PRAGMA kdf_iter = 256000;")
    cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
    cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")

    # Execute and fetch
    start_time = time.time()
    cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit}")
    rows = cursor.fetchall()
    end_time = time.time()

    # Clean up
    cursor.close()
    conn.close()

    # Memory after
    mem_after = get_memory_usage()
    logger.info(f"Memory after: {mem_after:.2f} MB")
    logger.info(f"Memory increase: {mem_after - mem_before:.2f} MB")
    logger.info(f"Time taken: {end_time - start_time:.4f} seconds")
    logger.info(f"Retrieved {len(rows)} rows")

    return rows, mem_after - mem_before, end_time - start_time


def test_session_query(db_path, table_name, limit=100):
    """Test query using SQLCipherSession"""
    from app.db.session import SQLCipherSession, EnhancedSQLCipherPool
    from app.db.models.base import Base

    # Find model class for the table
    model_class = None
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        if hasattr(cls, '__tablename__') and cls.__tablename__ == table_name:
            model_class = cls
            break

    if not model_class:
        logger.error(f"No model class found for table {table_name}")
        return None, 0, 0

    logger.info(f"Testing session query on {table_name} with limit {limit}")

    # Memory before
    mem_before = get_memory_usage()
    logger.info(f"Memory before: {mem_before:.2f} MB")

    # Create connection pool and session with reduced settings
    pool = EnhancedSQLCipherPool(
        db_path,
        pool_size=2,  # Reduced from 5
        max_overflow=3,  # Reduced from 10
        timeout=10,
        health_check_interval=60
    )
    session = SQLCipherSession(pool)

    # Execute query
    start_time = time.time()
    query = session.query(model_class).limit(limit)
    results = query.all()
    end_time = time.time()

    # Clean up
    session.close()
    pool.dispose()

    # Force garbage collection
    gc.collect()

    # Memory after
    mem_after = get_memory_usage()
    logger.info(f"Memory after: {mem_after:.2f} MB")
    logger.info(f"Memory increase: {mem_after - mem_before:.2f} MB")
    logger.info(f"Time taken: {end_time - start_time:.4f} seconds")
    logger.info(f"Retrieved {len(results)} objects")

    return results, mem_after - mem_before, end_time - start_time


def test_batch_sizes(db_path, key, table_name, batch_sizes=[10, 50, 100, 500]):
    """Test different batch sizes for memory impact"""
    logger.info(f"Testing batch sizes on {table_name}")

    results = []
    for batch_size in batch_sizes:
        logger.info(f"Testing batch size: {batch_size}")

        # Memory before
        mem_before = get_memory_usage()

        # Execute query in batches
        conn = sqlcipher.connect(db_path)
        cursor = conn.cursor()

        # Configure encryption
        cursor.execute(f"PRAGMA key = \"x'{key}'\";")
        cursor.execute("PRAGMA cipher_page_size = 4096;")
        cursor.execute("PRAGMA kdf_iter = 256000;")
        cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
        cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")

        # Execute query
        start_time = time.time()
        cursor.execute(f"SELECT * FROM {table_name}")

        total_rows = 0
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            total_rows += len(rows)

        end_time = time.time()

        # Clean up
        cursor.close()
        conn.close()

        # Memory after
        mem_after = get_memory_usage()
        results.append({
            'batch_size': batch_size,
            'memory_increase': mem_after - mem_before,
            'time_taken': end_time - start_time,
            'total_rows': total_rows
        })

        # Force garbage collection
        gc.collect()

        logger.info(f"Batch size {batch_size}: Memory increase {mem_after - mem_before:.2f} MB, "
                    f"Time: {end_time - start_time:.4f}s, Rows: {total_rows}")

    # Find optimal batch size
    sorted_results = sorted(results, key=lambda x: x['memory_increase'])
    optimal_size = sorted_results[0]['batch_size']
    logger.info(f"Optimal batch size: {optimal_size}")

    return results


def main():
    """Main function to run database diagnostics"""
    import argparse

    parser = argparse.ArgumentParser(description="HideSync Database Diagnostics")
    parser.add_argument("--table", default="storage_locations", help="Table to test")
    parser.add_argument("--limit", type=int, default=100, help="Query limit")
    parser.add_argument("--test", choices=["direct", "session", "batch", "all"],
                        default="all", help="Test to run")

    args = parser.parse_args()

    # Get database path and key
    db_path = os.path.abspath(settings.DATABASE_PATH)
    key = KeyManager.get_database_encryption_key()

    logger.info("Starting database diagnostics")
    logger.info(f"Database path: {db_path}")
    logger.info(f"Initial memory usage: {get_memory_usage():.2f} MB")

    # Run tests
    if args.test == "direct" or args.test == "all":
        test_direct_query(db_path, key, args.table, args.limit)

    if args.test == "session" or args.test == "all":
        test_session_query(db_path, args.table, args.limit)

    if args.test == "batch" or args.test == "all":
        test_batch_sizes(db_path, key, args.table)

    logger.info("Database diagnostics completed")
    logger.info(f"Final memory usage: {get_memory_usage():.2f} MB")


if __name__ == "__main__":
    main()