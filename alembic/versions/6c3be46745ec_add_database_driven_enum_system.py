"""Add database driven enum system

Revision ID: 6c3be46745ec
Revises: 5305a08d4450
Create Date: 2025-04-10 00:46:45.642665

"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c3be46745ec'
down_revision: Union[str, None] = '5305a08d4450'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


