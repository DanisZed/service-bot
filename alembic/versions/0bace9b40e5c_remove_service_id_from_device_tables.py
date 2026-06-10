"""remove_service_id_from_device_tables

Revision ID: 0bace9b40e5c
Revises: 99ebe515dc11
Create Date: 2026-06-10 23:57:14.343831

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0bace9b40e5c'
down_revision: Union[str, Sequence[str], None] = '99ebe515dc11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Удаляем внешние ключи
    op.drop_constraint('device_category_service_id_fkey', 'device_category', type_='foreignkey')
    op.drop_constraint('device_subtype_service_id_fkey', 'device_subtype', type_='foreignkey')
    
    # Удаляем уникальные ограничения
    op.drop_constraint('device_category_service_id_master_id_name_key', 'device_category', type_='unique')
    op.drop_constraint('device_subtype_service_id_master_id_category_id_name_key', 'device_subtype', type_='unique')
    
    # Удаляем колонки service_id
    op.drop_column('device_category', 'service_id')
    op.drop_column('device_subtype', 'service_id')
    
    # Добавляем новые уникальные ограничения (без service_id)
    op.create_unique_constraint('uq_device_category_master_name', 'device_category', ['master_id', 'name'])
    op.create_unique_constraint('uq_device_subtype_master_category_name', 'device_subtype', ['master_id', 'category_id', 'name'])

def downgrade():
    # Восстановление (сложно, но можно прописать)
    pass
