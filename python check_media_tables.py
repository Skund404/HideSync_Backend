#!/usr/bin/env python
"""
HideSync Database Comprehensive Report Script

This script provides a complete report of the database schema and contents,
including table structure, relationships, and data counts.
"""

import os
import sys
import json
from pathlib import Path
import logging
from datetime import datetime

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
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Define tables needed for media system
MEDIA_SYSTEM_TABLES = [
    'media_assets',
    'entity_media',
    'media_tags',
    'media_asset_tags'
]

# SQL statements to create missing tables if needed
CREATE_TABLE_STATEMENTS = {
    'entity_media': """
    CREATE TABLE entity_media (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        media_asset_id INTEGER NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id INTEGER NOT NULL,
        media_type TEXT,
        display_order INTEGER DEFAULT 0,
        caption TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        uuid TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        updated_at TIMESTAMP,
        FOREIGN KEY (media_asset_id) REFERENCES media_assets(id) ON DELETE CASCADE
    );
    """,
    'media_assets': """
    CREATE TABLE media_assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        file_path TEXT NOT NULL,
        file_size INTEGER,
        file_type TEXT,
        mime_type TEXT,
        width INTEGER,
        height INTEGER,
        duration INTEGER,
        title TEXT,
        description TEXT,
        alt_text TEXT,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP,
        uuid TEXT,
        is_public BOOLEAN DEFAULT FALSE,
        status TEXT DEFAULT 'active',
        metadata TEXT
    );
    """,
    'media_tags': """
    CREATE TABLE media_tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        slug TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP
    );
    """,
    'media_asset_tags': """
    CREATE TABLE media_asset_tags (
        media_asset_id INTEGER NOT NULL,
        tag_id INTEGER NOT NULL,
        PRIMARY KEY (media_asset_id, tag_id),
        FOREIGN KEY (media_asset_id) REFERENCES media_assets(id) ON DELETE CASCADE,
        FOREIGN KEY (tag_id) REFERENCES media_tags(id) ON DELETE CASCADE
    );
    """
}


def get_table_structure(cursor, table_name):
    """Get detailed structure of a table"""
    # Get columns
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()

    # Get foreign keys
    cursor.execute(f"PRAGMA foreign_key_list({table_name})")
    foreign_keys = cursor.fetchall()

    # Get indexes
    cursor.execute(f"PRAGMA index_list({table_name})")
    indexes = cursor.fetchall()

    return {
        "columns": columns,
        "foreign_keys": foreign_keys,
        "indexes": indexes
    }


def get_table_count(cursor, table_name):
    """Get the number of rows in a table"""
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        return count
    except Exception as e:
        logger.error(f"Error counting rows in {table_name}: {e}")
        return "Error"


def format_column_type(column_type):
    """Format column type for display"""
    if not column_type:
        return "UNKNOWN"
    column_type = column_type.upper()
    # Normalize common SQLite types
    if "INT" in column_type:
        return "INTEGER"
    if "CHAR" in column_type or "TEXT" in column_type or "CLOB" in column_type:
        return "TEXT"
    if "REAL" in column_type or "FLOA" in column_type or "DOUB" in column_type:
        return "REAL"
    if "BLOB" in column_type:
        return "BLOB"
    return column_type


def get_sample_data(cursor, table_name, limit=3):
    """Get sample data from a table"""
    try:
        cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit}")
        rows = cursor.fetchall()

        # Get column names
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in cursor.fetchall()]

        return columns, rows
    except Exception as e:
        logger.error(f"Error fetching sample data from {table_name}: {e}")
        return [], []


def generate_db_report(output_format="text", output_file=None):
    """Generate a comprehensive database report"""
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

    # Get database version and settings
    cursor.execute("SELECT sqlite_version()")
    sqlite_version = cursor.fetchone()[0]

    cursor.execute("PRAGMA cipher_version")
    cipher_version = cursor.fetchone()[0]

    # Get all tables in the database
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
    tables = [row[0] for row in cursor.fetchall()]

    # Get all views in the database
    cursor.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name;")
    views = [row[0] for row in cursor.fetchall()]

    # Collect report data
    report_data = {
        "database_info": {
            "path": db_path,
            "size_bytes": os.path.getsize(db_path) if os.path.exists(db_path) else "Unknown",
            "sqlite_version": sqlite_version,
            "cipher_version": cipher_version,
            "report_generated": datetime.now().isoformat()
        },
        "summary": {
            "total_tables": len(tables),
            "total_views": len(views),
            "tables": tables,
            "views": views,
            "missing_media_tables": [t for t in MEDIA_SYSTEM_TABLES if t not in tables]
        },
        "table_details": {},
        "view_details": {}
    }

    # Collect detailed info for each table
    for table in tables:
        structure = get_table_structure(cursor, table)
        count = get_table_count(cursor, table)
        column_names, sample_rows = get_sample_data(cursor, table)

        # Format column details
        columns = []
        for col in structure["columns"]:
            columns.append({
                "cid": col[0],
                "name": col[1],
                "type": format_column_type(col[2]),
                "notnull": bool(col[3]),
                "default_value": col[4],
                "is_primary_key": bool(col[5])
            })

        # Format foreign key details
        foreign_keys = []
        for fk in structure["foreign_keys"]:
            foreign_keys.append({
                "id": fk[0],
                "seq": fk[1],
                "table": fk[2],
                "from": fk[3],
                "to": fk[4],
                "on_update": fk[5],
                "on_delete": fk[6],
                "match": fk[7]
            })

        # Add to report
        report_data["table_details"][table] = {
            "row_count": count,
            "columns": columns,
            "foreign_keys": foreign_keys,
            "sample_data": {
                "columns": column_names,
                "rows": [list(row) for row in sample_rows]
            }
        }

    # Collect info for views
    for view in views:
        cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='view' AND name='{view}'")
        view_sql = cursor.fetchone()[0]
        column_names, sample_rows = get_sample_data(cursor, view)

        report_data["view_details"][view] = {
            "sql": view_sql,
            "sample_data": {
                "columns": column_names,
                "rows": [list(row) for row in sample_rows]
            }
        }

    conn.close()

    # Check for missing media tables
    missing_tables = report_data["summary"]["missing_media_tables"]

    # Format and output the report
    if output_format == "json":
        # Convert to JSON
        if output_file:
            with open(output_file, "w") as f:
                json.dump(report_data, f, indent=2)
            print(f"Database report saved to {output_file}")
        else:
            print(json.dumps(report_data, indent=2))
    else:
        # Text format (default)
        report_text = []
        report_text.append("=" * 80)
        report_text.append(f"HIDESYNC DATABASE REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_text.append("=" * 80)

        # Database info
        report_text.append("\nDATABASE INFORMATION:")
        report_text.append(f"Path: {db_path}")
        report_text.append(f"Size: {report_data['database_info']['size_bytes'] / (1024 * 1024):.2f} MB")
        report_text.append(f"SQLite Version: {sqlite_version}")
        report_text.append(f"SQLCipher Version: {cipher_version}")

        # Summary
        report_text.append("\nSUMMARY:")
        report_text.append(f"Total Tables: {len(tables)}")
        report_text.append(f"Total Views: {len(views)}")

        # Media system tables check
        report_text.append("\nMEDIA SYSTEM TABLES CHECK:")
        if missing_tables:
            report_text.append(f"❌ Missing tables: {', '.join(missing_tables)}")
        else:
            report_text.append("✅ All media system tables exist")

        # Tables list
        report_text.append("\nTABLES:")
        for idx, table in enumerate(tables, 1):
            count = report_data["table_details"][table]["row_count"]
            report_text.append(f"{idx}. {table} ({count} rows)")

        # Views list
        if views:
            report_text.append("\nVIEWS:")
            for idx, view in enumerate(views, 1):
                report_text.append(f"{idx}. {view}")

        # Table details
        report_text.append("\nTABLE DETAILS:")
        for table in tables:
            report_text.append("\n" + "-" * 80)
            report_text.append(f"TABLE: {table} ({report_data['table_details'][table]['row_count']} rows)")
            report_text.append("-" * 80)

            # Columns
            report_text.append("\nColumns:")
            for col in report_data["table_details"][table]["columns"]:
                pk_flag = "PK" if col["is_primary_key"] else "  "
                nn_flag = "NN" if col["notnull"] else "  "
                default = f"DEFAULT {col['default_value']}" if col["default_value"] is not None else ""
                report_text.append(f"  {col['name']:<20} {col['type']:<10} {pk_flag} {nn_flag} {default}")

            # Foreign Keys
            if report_data["table_details"][table]["foreign_keys"]:
                report_text.append("\nForeign Keys:")
                for fk in report_data["table_details"][table]["foreign_keys"]:
                    report_text.append(f"  {fk['from']} -> {fk['table']}({fk['to']}) ON DELETE {fk['on_delete']}")

            # Sample Data
            cols = report_data["table_details"][table]["sample_data"]["columns"]
            rows = report_data["table_details"][table]["sample_data"]["rows"]
            if cols and rows:
                report_text.append("\nSample Data:")
                col_header = " | ".join(f"{col:<15}" for col in cols)
                report_text.append("  " + col_header)
                report_text.append("  " + "-" * len(col_header))

                for row in rows:
                    formatted_row = []
                    for val in row:
                        if val is None:
                            formatted_row.append("NULL")
                        elif isinstance(val, str) and len(val) > 15:
                            formatted_row.append(f"{val[:12]}...")
                        else:
                            formatted_row.append(str(val))

                    report_text.append("  " + " | ".join(f"{val:<15}" for val in formatted_row))

        # Generate SQL for missing tables
        if missing_tables:
            report_text.append("\n" + "=" * 80)
            report_text.append("SQL TO CREATE MISSING MEDIA SYSTEM TABLES")
            report_text.append("=" * 80)

            for table in missing_tables:
                if table in CREATE_TABLE_STATEMENTS:
                    report_text.append(f"\n-- Create {table} table")
                    report_text.append(CREATE_TABLE_STATEMENTS[table])

        # Output the report
        report_str = "\n".join(report_text)
        if output_file:
            with open(output_file, "w") as f:
                f.write(report_str)
            print(f"Database report saved to {output_file}")
        else:
            print(report_str)

    return report_data


def apply_changes():
    """Apply the necessary changes to create missing tables"""
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

    # Get all tables in the database
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    existing_tables = [row[0] for row in cursor.fetchall()]

    # Find missing tables
    missing_tables = [table for table in MEDIA_SYSTEM_TABLES if table not in existing_tables]

    if not missing_tables:
        print("✅ No missing tables to create")
        return

    # Create tables in the right order to respect foreign key constraints
    for table in MEDIA_SYSTEM_TABLES:
        if table in missing_tables and table in CREATE_TABLE_STATEMENTS:
            print(f"Creating table: {table}")
            try:
                cursor.execute(CREATE_TABLE_STATEMENTS[table])
                print(f"✅ Table {table} created successfully")
            except Exception as e:
                print(f"❌ Failed to create table {table}: {e}")

    # Commit changes
    conn.commit()

    # Verify tables were created
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    updated_tables = [row[0] for row in cursor.fetchall()]

    still_missing = [table for table in MEDIA_SYSTEM_TABLES if table not in updated_tables]

    if still_missing:
        print(f"\n⚠️ Some tables are still missing: {', '.join(still_missing)}")
    else:
        print("\n✅ All required media system tables have been created")

    conn.close()


def main():
    """Main function to generate database report or apply changes"""
    import argparse

    parser = argparse.ArgumentParser(description="Generate a comprehensive database report or fix issues")
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (text or json)"
    )
    parser.add_argument(
        "--output",
        help="Output file path (if not specified, prints to console)"
    )
    parser.add_argument(
        "--apply-changes",
        action="store_true",
        help="Apply changes to create missing tables"
    )

    args = parser.parse_args()

    if args.apply_changes:
        print("Applying changes to create missing tables...")
        apply_changes()
    else:
        print("Generating database report...")
        generate_db_report(args.format, args.output)


if __name__ == "__main__":
    main()