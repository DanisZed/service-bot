"""add_assigned_master_id_to_service_request

Revision ID: b317aa666221
Revises: 82b2afc846df
Create Date: 2026-06-10 00:48:24.016375

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b317aa666221'
down_revision: Union[str, Sequence[str], None] = '82b2afc846df'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column('service_request', sa.Column('assigned_master_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key('fk_service_request_assigned_master_id', 'service_request', 'master', ['assigned_master_id'], ['id'], ondelete='SET NULL')
    # возможно, индекс
    op.create_index('ix_service_request_assigned_master_id', 'service_request', ['assigned_master_id'])
