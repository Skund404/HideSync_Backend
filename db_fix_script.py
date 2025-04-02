# db_fix_script.py
from sqlalchemy import text
from app.db.session import engine
import logging

logger = logging.getLogger(__name__)


def normalize_enum_values():
    """Fix case inconsistencies in enum columns."""
    # Map of table.column -> [(wrong_case, correct_case), ...]
    corrections = {
        "inventory.status": [
            ("in_stock", "IN_STOCK"),
            ("low_stock", "LOW_STOCK"),
            ("out_of_stock", "OUT_OF_STOCK"),
            ("discontinued", "DISCONTINUED"),
            ("on_order", "ON_ORDER"),
            ("backordered", "BACKORDERED"),
            ("active", "ACTIVE"),
        ],
        # Add other tables as needed
    }

    with engine.begin() as conn:
        for table_col, fixes in corrections.items():
            table, column = table_col.split(".")

            for wrong, correct in fixes:
                sql = text(f"UPDATE {table} SET {column} = :correct WHERE {column} = :wrong")
                result = conn.execute(sql, {"wrong": wrong, "correct": correct})
                if result.rowcount > 0:
                    logger.info(f"Fixed {result.rowcount} rows in {table}.{column}: '{wrong}' → '{correct}'")

    logger.info("Database enum normalization complete")


if __name__ == "__main__":
    normalize_enum_values()