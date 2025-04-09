#!/usr/bin/env python
"""
Database Structure Extraction Script
Displays the complete structure of an SQLCipher database including tables, columns,
data types, constraints, indexes, and foreign keys.
"""

import os
import sys
import json
from pathlib import Path
import logging
from collections import defaultdict

# Add project root to Python path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent if script_dir.name == "scripts" else script_dir
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pysqlcipher3.dbapi2 as sqlcipher
from app.core.config import settings
from app.core.key_manager import KeyManager

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def extract_tables(cursor):
    """Extract all tables from the database"""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
    )
    tables = [row[0] for row in cursor.fetchall()]
    logger.info(f"Found {len(tables)} tables")
    return tables


def extract_table_info(cursor, table_name):
    """Extract column information for a specific table"""
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = []

    for row in cursor.fetchall():
        # cid, name, type, notnull, dflt_value, pk
        column = {
            "cid": row[0],
            "name": row[1],
            "type": row[2],
            "notNull": bool(row[3]),
            "defaultValue": row[4],
            "primaryKey": bool(row[5]),
        }
        columns.append(column)

    return columns


def extract_foreign_keys(cursor, table_name):
    """Extract foreign key constraints for a specific table"""
    cursor.execute(f"PRAGMA foreign_key_list({table_name});")
    foreign_keys = []

    for row in cursor.fetchall():
        # id, seq, table, from, to, on_update, on_delete, match
        foreign_key = {
            "id": row[0],
            "seq": row[1],
            "table": row[2],
            "from": row[3],
            "to": row[4],
            "onUpdate": row[5],
            "onDelete": row[6],
            "match": row[7],
        }
        foreign_keys.append(foreign_key)

    return foreign_keys


def extract_indexes(cursor, table_name):
    """Extract indexes for a specific table"""
    cursor.execute(f"PRAGMA index_list({table_name});")
    indexes = []

    for row in cursor.fetchall():
        # seq, name, unique, origin, partial
        index_info = {
            "seq": row[0],
            "name": row[1],
            "unique": bool(row[2]),
            "origin": row[3],
            "partial": bool(row[4]) if len(row) > 4 else False,
        }

        # Get the columns in this index
        cursor.execute(f"PRAGMA index_info({index_info['name']});")
        index_columns = []

        for idx_col in cursor.fetchall():
            # seqno, cid, name
            index_columns.append(
                {"seqno": idx_col[0], "cid": idx_col[1], "name": idx_col[2]}
            )

        index_info["columns"] = index_columns
        indexes.append(index_info)

    return indexes


def extract_triggers(cursor, table_name):
    """Extract triggers associated with a specific table"""
    cursor.execute(
        f"SELECT name, sql FROM sqlite_master WHERE type='trigger' AND tbl_name='{table_name}';"
    )
    triggers = []

    for row in cursor.fetchall():
        trigger = {"name": row[0], "sql": row[1]}
        triggers.append(trigger)

    return triggers


def extract_views(cursor):
    """Extract all views from the database"""
    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='view';")
    views = []

    for row in cursor.fetchall():
        view = {"name": row[0], "sql": row[1]}
        views.append(view)

    return views


def extract_database_structure():
    """Extract the complete structure of the SQLCipher database"""
    db_path = os.path.abspath(settings.DATABASE_PATH)
    key = KeyManager.get_database_encryption_key()

    # Establish connection
    conn = sqlcipher.connect(db_path)
    cursor = conn.cursor()

    # Configure encryption with hex key approach
    cursor.execute(f"PRAGMA key = \"x'{key}'\";")
    cursor.execute("PRAGMA cipher_page_size = 4096;")
    cursor.execute("PRAGMA kdf_iter = 256000;")
    cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
    cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Extract database structure
    db_structure = {"tables": {}, "views": extract_views(cursor)}

    # Get all tables
    tables = extract_tables(cursor)

    # Extract detailed information for each table
    for table_name in tables:
        table_structure = {
            "columns": extract_table_info(cursor, table_name),
            "foreignKeys": extract_foreign_keys(cursor, table_name),
            "indexes": extract_indexes(cursor, table_name),
            "triggers": extract_triggers(cursor, table_name),
        }

        # Get the CREATE TABLE statement
        cursor.execute(
            f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}';"
        )
        create_statement = cursor.fetchone()
        if create_statement:
            table_structure["createStatement"] = create_statement[0]

        db_structure["tables"][table_name] = table_structure

    conn.close()
    return db_structure


def print_table_structure(table_name, table_info):
    """Print the structure of a table in a readable format"""
    print(f"\n{'=' * 80}")
    print(f"TABLE: {table_name}")
    print(f"{'=' * 80}")

    print("\nCOLUMNS:")
    print(f"{'Name':<20} {'Type':<15} {'PK':<5} {'Not Null':<10} {'Default':<20}")
    print(f"{'-' * 20} {'-' * 15} {'-' * 5} {'-' * 10} {'-' * 20}")

    for col in table_info["columns"]:
        pk = "✓" if col["primaryKey"] else ""
        not_null = "✓" if col["notNull"] else ""
        default = str(col["defaultValue"]) if col["defaultValue"] is not None else ""
        print(
            f"{col['name']:<20} {col['type']:<15} {pk:<5} {not_null:<10} {default:<20}"
        )

    if table_info["foreignKeys"]:
        print("\nFOREIGN KEYS:")
        print(f"{'Column':<20} {'References':<30} {'On Update':<15} {'On Delete':<15}")
        print(f"{'-' * 20} {'-' * 30} {'-' * 15} {'-' * 15}")

        for fk in table_info["foreignKeys"]:
            references = f"{fk['table']}({fk['to']})"
            print(
                f"{fk['from']:<20} {references:<30} {fk['onUpdate']:<15} {fk['onDelete']:<15}"
            )

    if table_info["indexes"]:
        print("\nINDEXES:")
        for idx in table_info["indexes"]:
            unique = "UNIQUE " if idx["unique"] else ""
            columns = ", ".join([col["name"] for col in idx["columns"]])
            print(f"  - {unique}INDEX {idx['name']} ({columns})")

    if table_info["triggers"]:
        print("\nTRIGGERS:")
        for trigger in table_info["triggers"]:
            print(f"  - {trigger['name']}")


def main():
    """Main function to extract and display database structure"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract and display database structure"
    )
    parser.add_argument("--output", help="Path to save the extracted structure as JSON")
    parser.add_argument("--table", help="Show structure for a specific table only")
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (text or json)",
    )

    args = parser.parse_args()

    # Extract database structure
    db_structure = extract_database_structure()

    # Output based on format and options
    if args.format == "text":
        if args.table:
            if args.table in db_structure["tables"]:
                print_table_structure(args.table, db_structure["tables"][args.table])
            else:
                print(f"Table '{args.table}' not found in the database.")
        else:
            # Print all tables
            for table_name, table_info in db_structure["tables"].items():
                print_table_structure(table_name, table_info)

            # Print views
            if db_structure["views"]:
                print("\n\nVIEWS:")
                for view in db_structure["views"]:
                    print(f"\n{'-' * 80}")
                    print(f"VIEW: {view['name']}")
                    print(f"{'-' * 80}")
                    print(view["sql"])

    # Save to JSON if output path is provided
    if args.output:
        output_path = os.path.abspath(args.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(db_structure, f, indent=2, ensure_ascii=False)

        logger.info(f"Database structure saved to {output_path}")

    # Print summary
    table_count = len(db_structure["tables"])
    view_count = len(db_structure["views"])
    print(f"\nSummary: {table_count} tables, {view_count} views found in the database.")
    print(f"Tables: {list(db_structure['tables'].keys())}")


if __name__ == "__main__":
    main()
