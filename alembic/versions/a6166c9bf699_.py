"""Change Tool date columns to Date/DateTime types and add constraints/indexes

Revision ID: a6166c9bf699
Revises: #<previous_revision_id_if_any> or None
Create Date: 2025-04-09 04:01:45.633364

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a6166c9bf699"  # Replace with your actual revision ID
down_revision: Union[str, None] = (
    None  # Replace with the previous revision ID if this isn't the first migration
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - adjusted! ###

    # Assuming these indexes already exist based on the error
    # If any DO NOT exist, uncomment the corresponding create_index line.
    with op.batch_alter_table("annotations", schema=None) as batch_op:
        # batch_op.create_index('ix_annotations_entity', ['entity_type', 'entity_id'], unique=False)
        # batch_op.create_index(batch_op.f('ix_annotations_entity_id'), ['entity_id'], unique=False)
        # batch_op.create_index(batch_op.f('ix_annotations_entity_type'), ['entity_type'], unique=False)
        # batch_op.create_index(batch_op.f('ix_annotations_id'), ['id'], unique=False)
        pass  # Keep block structure if all are commented

    with op.batch_alter_table("customers", schema=None) as batch_op:
        # batch_op.create_index(batch_op.f('ix_customers_email'), ['email'], unique=True)
        pass

    with op.batch_alter_table("entity_media", schema=None) as batch_op:
        # batch_op.create_index(batch_op.f('ix_entity_media_entity_id'), ['entity_id'], unique=False)
        # batch_op.create_index(batch_op.f('ix_entity_media_entity_type'), ['entity_type'], unique=False)
        pass

    with op.batch_alter_table("inventory", schema=None) as batch_op:
        # batch_op.create_index(batch_op.f('ix_inventory_item_id'), ['item_id'], unique=False)
        # batch_op.create_index(batch_op.f('ix_inventory_item_type'), ['item_type'], unique=False)
        pass

    with op.batch_alter_table("inventory_transactions", schema=None) as batch_op:
        # batch_op.create_index(batch_op.f('ix_inventory_transactions_item_id'), ['item_id'], unique=False)
        # batch_op.create_index(batch_op.f('ix_inventory_transactions_item_type'), ['item_type'], unique=False)
        pass

    with op.batch_alter_table("materials", schema=None) as batch_op:
        # batch_op.create_index(batch_op.f('ix_materials_sku'), ['sku'], unique=False)
        pass

    with op.batch_alter_table("media_asset_tags", schema=None) as batch_op:
        # batch_op.create_index(batch_op.f('ix_media_asset_tags_media_asset_id'), ['media_asset_id'], unique=False)
        # batch_op.create_index(batch_op.f('ix_media_asset_tags_tag_id'), ['tag_id'], unique=False)
        pass

    with op.batch_alter_table("media_assets", schema=None) as batch_op:
        # batch_op.create_index(batch_op.f('ix_media_assets_file_name'), ['file_name'], unique=False)
        # batch_op.create_index(batch_op.f('ix_media_assets_file_type'), ['file_type'], unique=False)
        pass

    with op.batch_alter_table("password_reset_tokens", schema=None) as batch_op:
        # batch_op.create_index(batch_op.f('ix_password_reset_tokens_id'), ['id'], unique=False)
        # batch_op.create_index(batch_op.f('ix_password_reset_tokens_token'), ['token'], unique=True)
        pass

    with op.batch_alter_table("patterns", schema=None) as batch_op:
        # batch_op.create_index(batch_op.f('ix_patterns_name'), ['name'], unique=False)
        pass

    with op.batch_alter_table("permissions", schema=None) as batch_op:
        # batch_op.create_index(batch_op.f('ix_permissions_code'), ['code'], unique=True)
        # batch_op.create_index(batch_op.f('ix_permissions_id'), ['id'], unique=False)
        pass

    with op.batch_alter_table("products", schema=None) as batch_op:
        # batch_op.create_index(batch_op.f('ix_products_sku'), ['sku'], unique=True)
        pass

    with op.batch_alter_table("roles", schema=None) as batch_op:
        # batch_op.create_index(batch_op.f('ix_roles_id'), ['id'], unique=False)
        # batch_op.create_index(batch_op.f('ix_roles_name'), ['name'], unique=True)
        pass

    with op.batch_alter_table("supplier_history", schema=None) as batch_op:
        # batch_op.create_index(batch_op.f('ix_supplier_history_change_date'), ['change_date'], unique=False)
        # batch_op.create_index(batch_op.f('ix_supplier_history_supplier_id'), ['supplier_id'], unique=False)
        pass

    with op.batch_alter_table("supplier_rating", schema=None) as batch_op:
        # batch_op.create_index(batch_op.f('ix_supplier_rating_rating_date'), ['rating_date'], unique=False)
        # batch_op.create_index(batch_op.f('ix_supplier_rating_supplier_id'), ['supplier_id'], unique=False)
        pass

    with op.batch_alter_table("suppliers", schema=None) as batch_op:
        # batch_op.create_index('idx_supplier_category', ['category'], unique=False)
        # batch_op.create_index('idx_supplier_name', ['name'], unique=False)
        # batch_op.create_index('idx_supplier_status', ['status'], unique=False)
        pass

    with op.batch_alter_table("tags", schema=None) as batch_op:
        # batch_op.create_index(batch_op.f('ix_tags_name'), ['name'], unique=True)
        pass

    # --- Keep these ALTER COLUMN operations ---
    with op.batch_alter_table("tool_checkouts", schema=None) as batch_op:
        batch_op.alter_column(
            "checked_out_date",
            existing_type=sa.VARCHAR(length=50),
            type_=sa.DateTime(),
            nullable=False,
        )
        batch_op.alter_column(
            "due_date",
            existing_type=sa.VARCHAR(length=50),
            type_=sa.Date(),
            nullable=False,
        )
        batch_op.alter_column(
            "returned_date",
            existing_type=sa.VARCHAR(length=50),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "status", existing_type=sa.VARCHAR(length=50), nullable=False
        )

    with op.batch_alter_table("tool_maintenance", schema=None) as batch_op:
        batch_op.alter_column(
            "date",
            existing_type=sa.VARCHAR(length=50),
            type_=sa.Date(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "status", existing_type=sa.VARCHAR(length=50), nullable=False
        )
        batch_op.alter_column(
            "next_date",
            existing_type=sa.VARCHAR(length=50),
            type_=sa.Date(),
            existing_nullable=True,
        )

    with op.batch_alter_table("tools", schema=None) as batch_op:
        batch_op.alter_column(
            "purchase_date",
            existing_type=sa.VARCHAR(length=50),
            type_=sa.Date(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "status", existing_type=sa.VARCHAR(length=50), nullable=False
        )
        batch_op.alter_column(
            "last_maintenance",
            existing_type=sa.VARCHAR(length=50),
            type_=sa.Date(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "next_maintenance",
            existing_type=sa.VARCHAR(length=50),
            type_=sa.Date(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "checked_out_date",
            existing_type=sa.VARCHAR(length=50),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "due_date",
            existing_type=sa.VARCHAR(length=50),
            type_=sa.Date(),
            existing_nullable=True,
        )
        # Keep the named unique constraint creation
        batch_op.create_unique_constraint("uq_tools_serial_number", ["serial_number"])

    with op.batch_alter_table("users", schema=None) as batch_op:
        # batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)
        # batch_op.create_index(batch_op.f('ix_users_full_name'), ['full_name'], unique=False)
        # batch_op.create_index(batch_op.f('ix_users_id'), ['id'], unique=False)
        # batch_op.create_index(batch_op.f('ix_users_username'), ['username'], unique=True)
        pass

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - adjusted! ###

    # Assuming these indexes already existed, so don't drop them on downgrade
    # If any were truly *new* with this migration, uncomment the corresponding drop_index.
    with op.batch_alter_table("users", schema=None) as batch_op:
        # batch_op.drop_index(batch_op.f('ix_users_username'))
        # batch_op.drop_index(batch_op.f('ix_users_id'))
        # batch_op.drop_index(batch_op.f('ix_users_full_name'))
        # batch_op.drop_index(batch_op.f('ix_users_email'))
        pass

    with op.batch_alter_table("tools", schema=None) as batch_op:
        # Drop the unique constraint added in upgrade
        batch_op.drop_constraint("uq_tools_serial_number", type_="unique")
        # Keep the alter_column calls to revert types/nullability
        batch_op.alter_column(
            "due_date",
            existing_type=sa.Date(),
            type_=sa.VARCHAR(length=50),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "checked_out_date",
            existing_type=sa.DateTime(),
            type_=sa.VARCHAR(length=50),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "next_maintenance",
            existing_type=sa.Date(),
            type_=sa.VARCHAR(length=50),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "last_maintenance",
            existing_type=sa.Date(),
            type_=sa.VARCHAR(length=50),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "status", existing_type=sa.VARCHAR(length=50), nullable=True
        )  # Assuming original was nullable
        batch_op.alter_column(
            "purchase_date",
            existing_type=sa.Date(),
            type_=sa.VARCHAR(length=50),
            existing_nullable=True,
        )

    with op.batch_alter_table("tool_maintenance", schema=None) as batch_op:
        batch_op.alter_column(
            "next_date",
            existing_type=sa.Date(),
            type_=sa.VARCHAR(length=50),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "status", existing_type=sa.VARCHAR(length=50), nullable=True
        )  # Assuming original was nullable
        batch_op.alter_column(
            "date",
            existing_type=sa.Date(),
            type_=sa.VARCHAR(length=50),
            existing_nullable=True,
        )

    with op.batch_alter_table("tool_checkouts", schema=None) as batch_op:
        batch_op.alter_column(
            "status", existing_type=sa.VARCHAR(length=50), nullable=True
        )  # Assuming original was nullable
        batch_op.alter_column(
            "returned_date",
            existing_type=sa.DateTime(),
            type_=sa.VARCHAR(length=50),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "due_date",
            existing_type=sa.Date(),
            type_=sa.VARCHAR(length=50),
            nullable=True,
        )  # Assuming original was nullable
        batch_op.alter_column(
            "checked_out_date",
            existing_type=sa.DateTime(),
            type_=sa.VARCHAR(length=50),
            nullable=True,
        )  # Assuming original was nullable

    with op.batch_alter_table("tags", schema=None) as batch_op:
        # batch_op.drop_index(batch_op.f('ix_tags_name'))
        pass

    with op.batch_alter_table("suppliers", schema=None) as batch_op:
        # batch_op.drop_index('idx_supplier_status')
        # batch_op.drop_index('idx_supplier_name')
        # batch_op.drop_index('idx_supplier_category')
        pass

    with op.batch_alter_table("supplier_rating", schema=None) as batch_op:
        # batch_op.drop_index(batch_op.f('ix_supplier_rating_supplier_id'))
        # batch_op.drop_index(batch_op.f('ix_supplier_rating_rating_date'))
        pass

    with op.batch_alter_table("supplier_history", schema=None) as batch_op:
        # batch_op.drop_index(batch_op.f('ix_supplier_history_supplier_id'))
        # batch_op.drop_index(batch_op.f('ix_supplier_history_change_date'))
        pass

    with op.batch_alter_table("roles", schema=None) as batch_op:
        # batch_op.drop_index(batch_op.f('ix_roles_name'))
        # batch_op.drop_index(batch_op.f('ix_roles_id'))
        pass

    with op.batch_alter_table("products", schema=None) as batch_op:
        # batch_op.drop_index(batch_op.f('ix_products_sku'))
        pass

    with op.batch_alter_table("permissions", schema=None) as batch_op:
        # batch_op.drop_index(batch_op.f('ix_permissions_id'))
        # batch_op.drop_index(batch_op.f('ix_permissions_code'))
        pass

    with op.batch_alter_table("patterns", schema=None) as batch_op:
        # batch_op.drop_index(batch_op.f('ix_patterns_name'))
        pass

    with op.batch_alter_table("password_reset_tokens", schema=None) as batch_op:
        # batch_op.drop_index(batch_op.f('ix_password_reset_tokens_token'))
        # batch_op.drop_index(batch_op.f('ix_password_reset_tokens_id'))
        pass

    with op.batch_alter_table("media_assets", schema=None) as batch_op:
        # batch_op.drop_index(batch_op.f('ix_media_assets_file_type'))
        # batch_op.drop_index(batch_op.f('ix_media_assets_file_name'))
        pass

    with op.batch_alter_table("media_asset_tags", schema=None) as batch_op:
        # batch_op.drop_index(batch_op.f('ix_media_asset_tags_tag_id'))
        # batch_op.drop_index(batch_op.f('ix_media_asset_tags_media_asset_id'))
        pass

    with op.batch_alter_table("materials", schema=None) as batch_op:
        # batch_op.drop_index(batch_op.f('ix_materials_sku'))
        pass

    with op.batch_alter_table("inventory_transactions", schema=None) as batch_op:
        # batch_op.drop_index(batch_op.f('ix_inventory_transactions_item_type'))
        # batch_op.drop_index(batch_op.f('ix_inventory_transactions_item_id'))
        pass

    with op.batch_alter_table("inventory", schema=None) as batch_op:
        # batch_op.drop_index(batch_op.f('ix_inventory_item_type'))
        # batch_op.drop_index(batch_op.f('ix_inventory_item_id'))
        pass

    with op.batch_alter_table("entity_media", schema=None) as batch_op:
        # batch_op.drop_index(batch_op.f('ix_entity_media_entity_type'))
        # batch_op.drop_index(batch_op.f('ix_entity_media_entity_id'))
        pass

    with op.batch_alter_table("customers", schema=None) as batch_op:
        # batch_op.drop_index(batch_op.f('ix_customers_email'))
        pass

    with op.batch_alter_table("annotations", schema=None) as batch_op:
        # batch_op.drop_index(batch_op.f('ix_annotations_id'))
        # batch_op.drop_index(batch_op.f('ix_annotations_entity_type'))
        # batch_op.drop_index(batch_op.f('ix_annotations_entity_id'))
        # batch_op.drop_index('ix_annotations_entity')
        pass

    # ### end Alembic commands ###
