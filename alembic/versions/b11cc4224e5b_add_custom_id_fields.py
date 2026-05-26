"""add custom id fields

Revision ID: b11cc4224e5b
Revises: 9ac3e1d2ac4b
Create Date: 2026-05-26 19:50:48.140901

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b11cc4224e5b'
down_revision: Union[str, None] = '9ac3e1d2ac4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ========== Таблица master ==========
    
    # 1. Добавить lastname после name
    op.add_column('master', sa.Column('lastname', sa.Text, nullable=True))
    
    # 2. Добавить service_name
    op.add_column('master', sa.Column('service_name', sa.Text, nullable=True))
    
    # 3. Добавить master_id (уникальный строковый ID формата МСТР + 7 цифр)
    op.add_column('master', sa.Column('master_id', sa.String(12), nullable=True, unique=True))
    op.create_index('ix_master_master_id', 'master', ['master_id'])
    
    # 4. Добавить is_admin
    op.add_column('master', sa.Column('is_admin', sa.Integer, nullable=False, server_default='0'))
    
    # ========== Таблица service_request ==========
    
    # 5. Добавить service_name
    op.add_column('service_request', sa.Column('service_name', sa.Text, nullable=True))
    
    # 6. Добавить service_id (уникальный строковый ID формата СРВС + 6 цифр)
    op.add_column('service_request', sa.Column('service_id', sa.String(10), nullable=True, unique=True))
    op.create_index('ix_service_request_service_id', 'service_request', ['service_id'])
    
    # 7. Добавить service_name в service_request
    op.add_column('service_request', sa.Column('service_name', sa.Text, nullable=True))
    op.create_index('ix_service_request_service_name', 'service_request', ['service_name'])


def downgrade() -> None:
    # ========== Таблица service_request ==========
    op.drop_index('ix_service_request_service_name', table_name='service_request')
    op.drop_column('service_request', 'service_name')
    op.drop_index('ix_service_request_service_id', table_name='service_request')
    op.drop_column('service_request', 'service_id')
    
    # ========== Таблица master ==========
    op.drop_column('master', 'is_admin')
    op.drop_index('ix_master_master_id', table_name='master')
    op.drop_column('master', 'master_id')
    op.drop_column('master', 'service_name')
    op.drop_column('master', 'lastname')