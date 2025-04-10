"""Change tool date/datetime columns to correct types

Revision ID: 5305a08d4450
Revises: a6166c9bf699
Create Date: 2025-04-09 14:19:45.423623

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5305a08d4450'
down_revision: Union[str, None] = 'a6166c9bf699'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)
        batch_op.create_index(batch_op.f('ix_users_full_name'), ['full_name'], unique=False)
        batch_op.create_index(batch_op.f('ix_users_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_users_username'), ['username'], unique=True)

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_username'))
        batch_op.drop_index(batch_op.f('ix_users_id'))
        batch_op.drop_index(batch_op.f('ix_users_full_name'))
        batch_op.drop_index(batch_op.f('ix_users_email'))

    # ### end Alembic commands ###
