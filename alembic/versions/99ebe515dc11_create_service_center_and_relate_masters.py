"""create_service_center_and_relate_masters

Revision ID: 99ebe515dc11
Revises: b317aa666221
Create Date: 2026-06-10 02:28:28.393524

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '99ebe515dc11'
down_revision: Union[str, Sequence[str], None] = 'b317aa666221'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade():
    # 1. Создаём таблицу service_center
    op.create_table('service_center',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('service_id', sa.String(10), nullable=False),
        sa.Column('service_name', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('service_id')
    )
    op.create_index('ix_service_center_service_id', 'service_center', ['service_id'])

    # 2. Переносим уникальные пары (service_id, service_name) из master в service_center
    # Получаем уникальные значения service_id, service_name из master (где service_id не NULL)
    connection = op.get_bind()
    # Для PostgreSQL можно выполнить INSERT ... SELECT DISTINCT
    op.execute("""
        INSERT INTO service_center (service_id, service_name, created_at, updated_at)
        SELECT DISTINCT service_id, service_name, now(), now()
        FROM master
        WHERE service_id IS NOT NULL
    """)

    # 3. Добавляем колонку service_center_id в master
    op.add_column('master', sa.Column('service_center_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_master_service_center_id', 'master', 'service_center', ['service_center_id'], ['id'], ondelete='SET NULL')

    # 4. Заполняем service_center_id на основе старых service_id
    op.execute("""
        UPDATE master
        SET service_center_id = sc.id
        FROM service_center sc
        WHERE master.service_id = sc.service_id
    """)

    # 5. Удаляем старые колонки (если больше не нужны)
    op.drop_constraint('master_service_id_key', 'master', type_='unique')
    op.drop_column('master', 'service_id')
    op.drop_column('master', 'service_name')

def downgrade():
    # Восстановление (сложно, но можно описать)
    op.add_column('master', sa.Column('service_id', sa.String(10), nullable=True))
    op.add_column('master', sa.Column('service_name', sa.Text(), nullable=True))
    op.create_unique_constraint('master_service_id_key', 'master', ['service_id'])

    # Заполняем из service_center
    op.execute("""
        UPDATE master
        SET service_id = sc.service_id, service_name = sc.service_name
        FROM service_center sc
        WHERE master.service_center_id = sc.id
    """)

    op.drop_constraint('master_service_id_key', 'master', type_='unique', cascade=True)
    op.drop_column('master', 'service_center_id')
    op.drop_table('service_center')