"""add_avatar_url_to_master

Revision ID: e12abe6074e4
Revises: b11cc4224e5b
Create Date: 2026-05-29 23:56:24.736585

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e12abe6074e4'
down_revision: Union[str, Sequence[str], None] = 'b11cc4224e5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Добавляем колонку avatar_url в таблицу master
    op.add_column('master', sa.Column('avatar_url', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Удаляем колонку avatar_url из таблицы master
    op.drop_column('master', 'avatar_url')