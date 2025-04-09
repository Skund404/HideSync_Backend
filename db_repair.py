#!/usr/bin/env python
"""
Enhanced Database Repair Script for SQLCipher Database

This improved script can scan the entire database for date/time fields
and fix any problematic values.
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, date
import re
import time

# Add project root to Python path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent if script_dir.name == "scripts" else script_dir
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import SQLCipher connectivity
import pysqlcipher3.dbapi2 as sqlcipher
from app.core.config import settings
from app.core.key_manager import KeyManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('db_repair.log')
    ]
)
logger = logging.getLogger(__name__)


def fix_date_string(value, not_null=False):
    """Fix a problematic date string/value."""
    if value is None:
        return date.today().isoformat() if not_null else None

    if isinstance(value, int):
        # If it's just a year (like 2023), convert to a full date
        if 1900 < value < 2100:  # Reasonable year range
            return f"{value}-01-01"
        else:
            # Other integers, treat as timestamp if reasonable
            try:
                # Only try to convert if it could be a reasonable timestamp
                if 1000000000 < value < 9999999999:  # Between 2001 and 2286
                    d = date.fromtimestamp(value)
                    return d.isoformat()
            except (ValueError, OverflowError):
                pass

    if isinstance(value, str):
        # Handle ISO format with time part - extract just the date
        if 'T' in value:
            return value.split('T')[0]

        # Try to match a date pattern YYYY-MM-DD
        date_pattern = r'^\d{4}-\d{2}-\d{2}$'
        if re.match(date_pattern, value):
            return value

        # For other strings, try to parse as date if possible
        try:
            # Try various formats
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d']:
                try:
                    d = datetime.strptime(value, fmt).date()
                    return d.isoformat()
                except ValueError:
                    continue
        except Exception:
            pass

        # If we get here, couldn't parse the string
        logger.warning(f"Unrecognizable date format: {value}")

    # Default for non-null fields
    return date.today().isoformat() if not_null else None


def fix_datetime_string(value, not_null=False):
    """Fix a problematic datetime string/value."""
    now_iso = datetime.now().isoformat()

    if value is None:
        return now_iso if not_null else None

    if isinstance(value, int):
        # If it's just a year (like 2023), convert to a datetime
        if 1900 < value < 2100:  # Reasonable year range
            return f"{value}-01-01T00:00:00"
        else:
            # Other integers, treat as timestamp if reasonable
            try:
                # Only try to convert if it could be a reasonable timestamp
                if 1000000000 < value < 9999999999:  # Between 2001 and 2286
                    dt = datetime.fromtimestamp(value)
                    return dt.isoformat()
            except (ValueError, OverflowError):
                pass

    if isinstance(value, str):
        # Handle ISO format
        if 'T' in value:
            # Fix timezone designator
            if 'Z' in value:
                value = value.replace('Z', '+00:00')
            return value

        # If it's just a date string, add time component
        date_pattern = r'^\d{4}-\d{2}-\d{2}$'
        if re.match(date_pattern, value):
            return f"{value}T00:00:00"

        # If it contains spaces (like SQLite format), convert to ISO
        if ' ' in value:
            try:
                parts = value.split(' ')
                if len(parts) == 2:
                    return f"{parts[0]}T{parts[1]}"
            except:
                pass

        # Try to parse various datetime formats
        try:
            # Try various formats
            for fmt in ['%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S', '%m/%d/%Y %H:%M:%S']:
                try:
                    dt = datetime.strptime(value, fmt)
                    return dt.isoformat()
                except ValueError:
                    continue
        except Exception:
            pass

        # If we get here, couldn't parse the string
        logger.warning(f"Unrecognizable datetime format: {value}")

    # Default for non-null fields
    return now_iso if not_null else None


def detect_date_columns(cursor, table_name):
    """Detect potential date columns based on name and type."""
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = cursor.fetchall()

    date_columns = []
    datetime_columns = []

    for col in columns:
        col_name = col[1]
        col_type = col[2].upper() if col[2] else ""
        not_null = bool(col[3])

        # Check type - SQLite doesn't enforce types strictly
        is_date_type = "DATE" in col_type or col_type == "DATE"
        is_datetime_type = "TIME" in col_type or "TIMESTAMP" in col_type or col_type == "DATETIME"

        # Check name patterns for dates
        contains_date = any(pattern in col_name.lower() for pattern
                            in ["date", "day", "month", "year", "due", "when"])

        # Check name patterns specific to datetime
        contains_datetime = any(pattern in col_name.lower() for pattern
                                in ["timestamp", "created", "updated", "time", "at"])

        # Decide if it's a date or datetime
        if is_date_type or (contains_date and not contains_datetime and not is_datetime_type):
            date_columns.append({"name": col_name, "not_null": not_null})
        elif is_datetime_type or contains_datetime:
            datetime_columns.append({"name": col_name, "not_null": not_null})

    return date_columns, datetime_columns


def get_all_tables(cursor):
    """Get all table names in the database."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    return [row[0] for row in cursor.fetchall()]


def repair_database(dry_run=False, scan_all=False):
    """
    Repair date/time fields in the database.

    Args:
        dry_run: If True, don't actually update the database
        scan_all: If True, scan all tables in the database

    Returns:
        Dictionary with repair statistics
    """
    # Get database path and encryption key
    db_path = os.path.abspath(settings.DATABASE_PATH)
    logger.info(f"Using database: {db_path}")
    key = KeyManager.get_database_encryption_key()

    # Statistics tracking
    stats = {}

    # Known tables to process
    known_tables = {
        "tools": {
            "date_columns": [
                {"name": "purchase_date", "not_null": False},
                {"name": "last_maintenance", "not_null": False},
                {"name": "next_maintenance", "not_null": False},
                {"name": "due_date", "not_null": False},
            ],
            "datetime_columns": [
                {"name": "checked_out_date", "not_null": False},
                {"name": "created_at", "not_null": True},
                {"name": "updated_at", "not_null": True},
            ]
        },
        "tool_maintenance": {
            "date_columns": [
                {"name": "date", "not_null": False},
                {"name": "next_date", "not_null": False},
            ],
            "datetime_columns": [
                {"name": "created_at", "not_null": True},
                {"name": "updated_at", "not_null": True},
            ]
        },
        "tool_checkouts": {
            "date_columns": [
                {"name": "due_date", "not_null": True},
            ],
            "datetime_columns": [
                {"name": "checked_out_date", "not_null": True},
                {"name": "returned_date", "not_null": False},
                {"name": "created_at", "not_null": True},
                {"name": "updated_at", "not_null": True},
            ]
        }
    }

    # Establish connection
    conn = sqlcipher.connect(db_path)
    cursor = conn.cursor()

    # Configure encryption
    cursor.execute(f"PRAGMA key = \"x'{key}'\";")
    cursor.execute("PRAGMA cipher_page_size = 4096;")
    cursor.execute("PRAGMA kdf_iter = 256000;")
    cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
    cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
    cursor.execute("PRAGMA foreign_keys = OFF;")  # Turn off foreign keys during repair

    try:
        # Get all tables if scanning everything
        if scan_all:
            tables_to_process = get_all_tables(cursor)
            logger.info(f"Found {len(tables_to_process)} tables to scan")
        else:
            tables_to_process = list(known_tables.keys())
            logger.info(f"Using {len(tables_to_process)} predefined tables")

        # Process each table
        for table_name in tables_to_process:
            table_stats = {"processed": 0, "fixed": 0, "errors": 0}
            logger.info(f"Processing table: {table_name}")

            # Check if table exists
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';")
            if not cursor.fetchone():
                logger.warning(f"Table {table_name} does not exist, skipping")
                stats[table_name] = table_stats
                continue

            # Get columns from known config or detect them
            if table_name in known_tables:
                date_columns = known_tables[table_name]["date_columns"]
                datetime_columns = known_tables[table_name]["datetime_columns"]
                logger.info(f"Using predefined column config for {table_name}")
            else:
                # Auto-detect columns
                date_columns, datetime_columns = detect_date_columns(cursor, table_name)
                logger.info(
                    f"Auto-detected columns for {table_name}: {len(date_columns)} date, {len(datetime_columns)} datetime")

            # Skip if no date columns found
            if not date_columns and not datetime_columns:
                logger.info(f"No date or datetime columns found in {table_name}, skipping")
                stats[table_name] = table_stats
                continue

            # Get all rows from the table
            cursor.execute(f"SELECT * FROM {table_name};")
            rows = cursor.fetchall()

            # Get column names
            cursor.execute(f"PRAGMA table_info({table_name});")
            column_info = cursor.fetchall()
            column_names = [col[1] for col in column_info]

            # Process date/datetime columns
            date_indices = []
            for col_info in date_columns:
                col_name = col_info["name"]
                if col_name in column_names:
                    date_indices.append({
                        "index": column_names.index(col_name),
                        "name": col_name,
                        "not_null": col_info["not_null"]
                    })

            datetime_indices = []
            for col_info in datetime_columns:
                col_name = col_info["name"]
                if col_name in column_names:
                    datetime_indices.append({
                        "index": column_names.index(col_name),
                        "name": col_name,
                        "not_null": col_info["not_null"]
                    })

            # Process each row
            table_stats["processed"] = len(rows)
            for row_id, row in enumerate(rows, 1):
                try:
                    row_needs_update = False
                    updates = []

                    # Get the record ID and name for display
                    record_id = row[0]
                    record_name = row[1] if len(row) > 1 else record_id  # Use name if available, otherwise ID

                    # Process date columns
                    for col_info in date_indices:
                        idx = col_info["index"]
                        col_name = col_info["name"]
                        not_null = col_info["not_null"]
                        old_value = row[idx]

                        if old_value is not None and not isinstance(old_value, date):
                            fixed_value = fix_date_string(old_value, not_null)
                            if fixed_value != old_value:
                                updates.append((col_name, old_value, fixed_value))
                                row_needs_update = True

                    # Process datetime columns
                    for col_info in datetime_indices:
                        idx = col_info["index"]
                        col_name = col_info["name"]
                        not_null = col_info["not_null"]
                        old_value = row[idx]

                        if old_value is not None and not isinstance(old_value, datetime):
                            fixed_value = fix_datetime_string(old_value, not_null)
                            if fixed_value != old_value:
                                updates.append((col_name, old_value, fixed_value))
                                row_needs_update = True

                    # Update the row if needed
                    if row_needs_update:
                        update_clauses = []
                        update_values = []

                        for col_name, old_value, new_value in updates:
                            update_clauses.append(f"{col_name} = ?")
                            update_values.append(new_value)
                            logger.info(
                                f"{table_name} ID {record_name}: Fixing {col_name} from '{old_value}' to '{new_value}'")

                        if not dry_run and update_clauses:
                            sql = f"UPDATE {table_name} SET {', '.join(update_clauses)} WHERE id = ?"
                            update_values.append(record_id)
                            cursor.execute(sql, update_values)
                            table_stats["fixed"] += 1
                        elif dry_run and update_clauses:
                            table_stats["fixed"] += 1
                            logger.info(f"[DRY RUN] Would update {table_name} ID {record_name}")

                except Exception as e:
                    logger.error(f"Error processing {table_name} row {row_id}: {e}")
                    table_stats["errors"] += 1

            stats[table_name] = table_stats
            logger.info(f"Completed {table_name}: Processed {table_stats['processed']}, " +
                        f"Fixed {table_stats['fixed']}, Errors {table_stats['errors']}")

        # Commit changes if not in dry run mode
        if not dry_run:
            conn.commit()
            logger.info("Changes committed to database")
        else:
            conn.rollback()
            logger.info("Dry run complete - no changes were made")

    except Exception as e:
        logger.error(f"Database repair failed: {e}")
        conn.rollback()
        raise
    finally:
        # Re-enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON;")
        conn.close()

    return stats


def main():
    """Command-line entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Repair date/time fields in the database")
    parser.add_argument('--dry-run', action='store_true', help='Simulate repair without making changes')
    parser.add_argument('--scan-all', action='store_true', help='Scan all tables, not just known ones')
    parser.add_argument('--output', default=None,
                        help='Path to save repair statistics (default: no file output)')

    args = parser.parse_args()

    try:
        logger.info("Starting database repair")
        if args.dry_run:
            logger.info("DRY RUN MODE - No changes will be made")
        else:
            logger.info("LIVE MODE - CHANGES WILL BE MADE")

        if args.scan_all:
            logger.info("FULL SCAN MODE - Scanning all tables in the database")

        start_time = time.time()

        # Run the repair
        stats = repair_database(dry_run=args.dry_run, scan_all=args.scan_all)

        end_time = time.time()
        duration = end_time - start_time

        # Display summary
        print(f"\nRepair Summary (completed in {duration:.2f} seconds):")
        print("==============")
        for table, table_stats in stats.items():
            print(f"{table}: Processed {table_stats['processed']} rows, " +
                  f"Fixed {table_stats['fixed']}, Errors {table_stats['errors']}")

        # Save statistics if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "dry_run": args.dry_run,
                    "scan_all": args.scan_all,
                    "duration_seconds": duration,
                    "statistics": stats
                }, f, indent=2)
            logger.info(f"Repair statistics saved to {args.output}")

        return 0

    except Exception as e:
        logger.error(f"Repair failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())