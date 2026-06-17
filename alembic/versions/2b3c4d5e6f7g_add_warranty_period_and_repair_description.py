"""add_warranty_period_and_repair_description

Revision ID: 2b3c4d5e6f7g
Revises: 1a07705ddf4b
Create Date: 2026-06-17 21:09:59.622959

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b3c4d5e6f7g'
down_revision: Union[str, Sequence[str], None] = '1a07705ddf4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('service_request', sa.Column('repair_description', sa.Text(), nullable=False, server_default=''))
    op.add_column('service_request', sa.Column('warranty_period', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('service_request', 'warranty_period')
    op.drop_column('service_request', 'repair_description')
