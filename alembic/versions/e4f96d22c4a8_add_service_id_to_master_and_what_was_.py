"""add_service_id_to_master_and_what_was_done_to_service_request

Revision ID: e4f96d22c4a8
Revises: e12abe6074e4
Create Date: 2026-06-04 22:18:05.022257

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4f96d22c4a8'
down_revision: Union[str, Sequence[str], None] = 'e12abe6074e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Добавляем service_id в таблицу master
    op.add_column('master', sa.Column('service_id', sa.String(10), nullable=True, unique=True))
    op.create_index('ix_master_service_id', 'master', ['service_id'])
    
    # Добавляем what_was_done в таблицу service_request
    op.add_column('service_request', sa.Column('what_was_done', sa.Text(), nullable=True))
    op.create_index('ix_service_request_what_was_done', 'service_request', ['what_was_done'])


def downgrade() -> None:
    """Downgrade schema."""
    # Удаляем what_was_done из service_request
    op.drop_index('ix_service_request_what_was_done', table_name='service_request')
    op.drop_column('service_request', 'what_was_done')
    
    # Удаляем service_id из master
    op.drop_index('ix_master_service_id', table_name='master')
    op.drop_column('master', 'service_id')