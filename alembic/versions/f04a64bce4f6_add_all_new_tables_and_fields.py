"""add_all_new_tables_and_fields

Revision ID: f04a64bce4f6
Revises: e4f96d22c4a8
Create Date: 2026-06-08 20:21:27.810784

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f04a64bce4f6'
down_revision: Union[str, None] = 'e4f96d22c4a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================
    # 1. ДОБАВЛЯЕМ НОВЫЕ ПОЛЯ В СУЩЕСТВУЮЩИЕ ТАБЛИЦЫ (с проверкой)
    # ============================================
    
    # В service_request добавляем parts_cost (стоимость запчастей)
    op.execute("""
        DO $$ 
        BEGIN 
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='service_request' AND column_name='parts_cost') THEN
                ALTER TABLE service_request ADD COLUMN parts_cost NUMERIC(12, 2);
                CREATE INDEX ix_service_request_parts_cost ON service_request(parts_cost);
            END IF;
        END $$;
    """)
    
    # В service_request добавляем lead_source_id (источник заявки)
    op.execute("""
        DO $$ 
        BEGIN 
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='service_request' AND column_name='lead_source_id') THEN
                ALTER TABLE service_request ADD COLUMN lead_source_id INTEGER;
                CREATE INDEX ix_service_request_lead_source_id ON service_request(lead_source_id);
            END IF;
        END $$;
    """)
    
    # В service_request добавляем what_was_done (что сделано) — пропускаем если есть
    op.execute("""
        DO $$ 
        BEGIN 
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='service_request' AND column_name='what_was_done') THEN
                ALTER TABLE service_request ADD COLUMN what_was_done TEXT;
                CREATE INDEX ix_service_request_what_was_done ON service_request(what_was_done);
            END IF;
        END $$;
    """)
    
    # В master добавляем service_id (если ещё нет)
    op.execute("""
        DO $$ 
        BEGIN 
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='master' AND column_name='service_id') THEN
                ALTER TABLE master ADD COLUMN service_id VARCHAR(10) UNIQUE;
                CREATE INDEX ix_master_service_id ON master(service_id);
            END IF;
        END $$;
    """)
    
    # ============================================
    # 2. ТАБЛИЦА КАТЕГОРИЙ (привязана к сервису/мастеру)
    # ============================================
    op.create_table(
        'device_category',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('service_id', sa.String(10), nullable=True),
        sa.Column('master_id', sa.BigInteger, nullable=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('sort_order', sa.Integer, server_default='0'),
        sa.Column('is_active', sa.Boolean, server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['service_id'], ['master.service_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['master_id'], ['master.id'], ondelete='CASCADE'),
        sa.CheckConstraint('(service_id IS NOT NULL AND master_id IS NULL) OR (service_id IS NULL AND master_id IS NOT NULL)'),
        sa.UniqueConstraint('service_id', 'master_id', 'name')
    )
    op.create_index('idx_device_category_service_id', 'device_category', ['service_id'])
    op.create_index('idx_device_category_master_id', 'device_category', ['master_id'])
    
    # ============================================
    # 3. ТАБЛИЦА ВИДОВ ТЕХНИКИ (привязана к сервису/мастеру)
    # ============================================
    op.create_table(
        'device_subtype',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('service_id', sa.String(10), nullable=True),
        sa.Column('master_id', sa.BigInteger, nullable=True),
        sa.Column('category_id', sa.Integer, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('price', sa.Numeric(12, 2), nullable=True),
        sa.Column('duration_minutes', sa.Integer, nullable=True),
        sa.Column('sort_order', sa.Integer, server_default='0'),
        sa.Column('is_active', sa.Boolean, server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['service_id'], ['master.service_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['master_id'], ['master.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['category_id'], ['device_category.id'], ondelete='CASCADE'),
        sa.CheckConstraint('(service_id IS NOT NULL AND master_id IS NULL) OR (service_id IS NULL AND master_id IS NOT NULL)'),
        sa.UniqueConstraint('service_id', 'master_id', 'category_id', 'name')
    )
    op.create_index('idx_device_subtype_service_id', 'device_subtype', ['service_id'])
    op.create_index('idx_device_subtype_master_id', 'device_subtype', ['master_id'])
    op.create_index('idx_device_subtype_category', 'device_subtype', ['category_id'])
    
    # ============================================
    # 4. ТАБЛИЦА ИСТОЧНИКОВ ЗАЯВОК
    # ============================================
    op.create_table(
        'lead_source',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('service_id', sa.String(10), nullable=True),
        sa.Column('master_id', sa.BigInteger, nullable=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('code', sa.String(50), nullable=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('is_active', sa.Boolean, server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['service_id'], ['master.service_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['master_id'], ['master.id'], ondelete='CASCADE'),
        sa.CheckConstraint('(service_id IS NOT NULL AND master_id IS NULL) OR (service_id IS NULL AND master_id IS NOT NULL)'),
        sa.UniqueConstraint('service_id', 'master_id', 'name')
    )
    op.create_index('idx_lead_source_service_id', 'lead_source', ['service_id'])
    op.create_index('idx_lead_source_master_id', 'lead_source', ['master_id'])
    
    # ============================================
    # 5. ТАБЛИЦА РЕКЛАМНЫХ БЮДЖЕТОВ
    # ============================================
    op.create_table(
        'ad_budget',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('source_id', sa.Integer, nullable=False),
        sa.Column('budget_date', sa.Date, nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('currency', sa.String(8), server_default='RUB'),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['source_id'], ['lead_source.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('source_id', 'budget_date')
    )
    op.create_index('idx_ad_budget_source_id', 'ad_budget', ['source_id'])
    op.create_index('idx_ad_budget_date', 'ad_budget', ['budget_date'])
    
    # ============================================
    # 6. ДОБАВЛЯЕМ СВЯЗЬ service_request С lead_source
    # ============================================
    op.execute("""
        DO $$ 
        BEGIN 
            IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints 
                          WHERE constraint_name='fk_service_request_lead_source') THEN
                ALTER TABLE service_request ADD CONSTRAINT fk_service_request_lead_source 
                FOREIGN KEY (lead_source_id) REFERENCES lead_source(id) ON DELETE SET NULL;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Удаляем связи и поля из service_request
    op.execute("ALTER TABLE service_request DROP CONSTRAINT IF EXISTS fk_service_request_lead_source")
    
    op.execute("DROP INDEX IF EXISTS ix_service_request_what_was_done")
    op.execute("ALTER TABLE service_request DROP COLUMN IF EXISTS what_was_done")
    
    op.execute("DROP INDEX IF EXISTS ix_service_request_lead_source_id")
    op.execute("ALTER TABLE service_request DROP COLUMN IF EXISTS lead_source_id")
    
    op.execute("DROP INDEX IF EXISTS ix_service_request_parts_cost")
    op.execute("ALTER TABLE service_request DROP COLUMN IF EXISTS parts_cost")
    
    # Удаляем таблицы
    op.drop_table('ad_budget')
    op.drop_table('lead_source')
    op.drop_table('device_subtype')
    op.drop_table('device_category')
    
    # Удаляем индекс и колонку service_id из master
    op.execute("DROP INDEX IF EXISTS ix_master_service_id")
    op.execute("ALTER TABLE master DROP COLUMN IF EXISTS service_id")