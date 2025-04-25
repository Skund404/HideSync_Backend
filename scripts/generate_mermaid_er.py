# scripts/generate_mermaid_er.py
import sys
import os

# Add the project root (the parent of 'app' and 'scripts') to sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.db.models.base import Base
from sqlalchemy import Table, MetaData, inspect
import re

def mermaid_type(sqlatype):
    t = str(sqlatype)
    if "INTEGER" in t:
        return "int"
    if "VARCHAR" in t or "TEXT" in t or "STRING" in t:
        return "string"
    if "BOOLEAN" in t:
        return "boolean"
    if "FLOAT" in t or "DECIMAL" in t:
        return "float"
    if "DATETIME" in t or "DATE" in t:
        return "datetime"
    return "string"

def get_table_comment(table):
    return table.comment or ""

def get_column_comment(col):
    return col.comment or ""

def is_association_table(table):
    # Heuristic: association tables have only FKs, all columns are part of PK, and at least 2 FKs
    if len(table.foreign_keys) < 2:
        return False
    pk_cols = set([col.name for col in table.primary_key.columns])
    fk_cols = set([fk.parent.name for fk in table.foreign_keys])
    return pk_cols == fk_cols and len(table.columns) == len(pk_cols)

def format_column(col):
    coltype = mermaid_type(col.type)
    pk = " PK" if col.primary_key else ""
    fk = " FK" if col.foreign_keys else ""
    nullable = "" if col.nullable or col.primary_key else " NOT NULL"
    unique = " UNIQUE" if col.unique else ""
    comment = f" // {get_column_comment(col)}" if get_column_comment(col) else ""
    return f"{coltype} {col.name}{pk}{fk}{unique}{nullable}{comment}"

def format_table(table):
    comment = get_table_comment(table)
    comment_line = f"%% {comment}" if comment else ""
    lines = []
    if comment_line:
        lines.append(f"    {comment_line}")
    lines.append(f"    {table.name} {{")
    for col in table.columns:
        lines.append(f"        {format_column(col)}")
    lines.append("    }")
    # --- Polymorphic note for materials table ---
    if table.name == "materials":
        lines.append('    %% Polymorphic: material_type discriminator')
        lines.append('    %% Subclasses: LeatherMaterial, HardwareMaterial, SuppliesMaterial, WoodMaterial')
        lines.append('    %% Each subclass uses a subset of these columns')
    return "\n".join(lines)

def format_unique_constraints(table):
    lines = []
    for uc in table.constraints:
        if hasattr(uc, "columns") and getattr(uc, "unique", False):
            cols = ", ".join([col.name for col in uc.columns])
            lines.append(f"    %% UNIQUE({cols})")
    return lines

def get_relationships(metadata):
    """Return a list of (left_table, right_table, left_col, right_col, rel_type, assoc_table)"""
    rels = []
    for table in metadata.sorted_tables:
        for fk in table.foreign_keys:
            left_table = table.name
            right_table = fk.column.table.name
            left_col = fk.parent.name
            right_col = fk.column.name
            # Check for association table (many-to-many)
            assoc_table = None
            rel_type = "one-to-many"
            if is_association_table(table):
                # This is a many-to-many association table
                # Find the other FK
                other_fks = [f for f in table.foreign_keys if f != fk]
                if other_fks:
                    other_fk = other_fks[0]
                    rels.append((fk.column.table.name, other_fk.column.table.name, fk.column.name, other_fk.column.name, "many-to-many", table.name))
                continue
            rels.append((left_table, right_table, left_col, right_col, rel_type, assoc_table))
    return rels

def format_relationship(left, right, left_col, right_col, rel_type, assoc_table=None):
    # Mermaid: Table1 ||--o{ Table2 : "FK"
    if rel_type == "many-to-many" and assoc_table:
        # Show as two one-to-manys via the association table
        return [
            f"    {assoc_table} }}o--|| {left} : \"M2M\"",
            f"    {assoc_table} }}o--|| {right} : \"M2M\""
        ]
    # For one-to-many, left (child) o{--|| right (parent)
    return [f"    {left} }}o--|| {right} : \"{left_col}→{right_col}\""]

def generate_mermaid_er(metadata):
    lines = ["erDiagram"]
    # Tables and columns
    for table in metadata.sorted_tables:
        lines.append(format_table(table))
        lines.extend(format_unique_constraints(table))
    # Relationships
    rels = get_relationships(metadata)
    rel_lines = set()
    for rel in rels:
        for l in format_relationship(*rel):
            rel_lines.add(l)
    lines.extend(sorted(rel_lines))
    return "\n".join(lines)

if __name__ == "__main__":
    print(generate_mermaid_er(Base.metadata))
