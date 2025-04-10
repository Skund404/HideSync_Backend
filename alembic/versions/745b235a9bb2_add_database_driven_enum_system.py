"""Add database driven enum system

Revision ID: 745b235a9bb2
Revises: b93e666ee3f4
Create Date: 2025-04-10 01:00:35.170546

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '745b235a9bb2'
down_revision: Union[str, None] = 'b93e666ee3f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
