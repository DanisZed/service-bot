"""add_is_advertisable_to_lead_source

Revision ID: 82b2afc846df
Revises: f04a64bce4f6
Create Date: 2026-06-09 00:07:13.988438

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '82b2afc846df'
down_revision: Union[str, Sequence[str], None] = 'f04a64bce4f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляем поле is_advertisable в таблицу lead_source"""
    # Добавляем колонку с дефолтным значением False
    op.add_column(
        'lead_source', 
        sa.Column('is_advertisable', sa.Boolean(), nullable=False, server_default='false')
    )
    
    # Создаем индекс для быстрого поиска по этому полю
    op.create_index('idx_lead_source_is_advertisable', 'lead_source', ['is_advertisable'])


def downgrade() -> None:
    """Удаляем поле is_advertisable из таблицы lead_source"""
    # Удаляем индекс
    op.drop_index('idx_lead_source_is_advertisable', table_name='lead_source')
    
    # Удаляем колонку
    op.drop_column('lead_source', 'is_advertisable')