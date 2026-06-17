"""add_warranty_period_and_repair_description

Revision ID: 1da9ece302a4
Revises: b9418a5a5205
Create Date: 2026-06-17 21:09:59.622959

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1da9ece302a4'
down_revision: Union[str, Sequence[str], None] = 'b9418a5a5205'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('service_request', sa.Column('repair_description', sa.Text(), nullable=False, server_default=''))
    op.add_column('service_request', sa.Column('warranty_period', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('service_request', 'warranty_period')
    op.drop_column('service_request', 'repair_description')
