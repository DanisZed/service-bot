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
    # 2. ТАБЛИЦА КАТЕГОРИЙ (с проверкой существования)
    # ============================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS device_category (
            id SERIAL PRIMARY KEY,
            service_id VARCHAR(10),
            master_id BIGINT,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            sort_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            FOREIGN KEY(service_id) REFERENCES master(service_id) ON DELETE CASCADE,
            FOREIGN KEY(master_id) REFERENCES master(id) ON DELETE CASCADE,
            CHECK ((service_id IS NOT NULL AND master_id IS NULL) OR (service_id IS NULL AND master_id IS NOT NULL)),
            UNIQUE(service_id, master_id, name)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_device_category_service_id ON device_category(service_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_device_category_master_id ON device_category(master_id);")
    
    # ============================================
    # 3. ТАБЛИЦА ВИДОВ ТЕХНИКИ (с проверкой существования)
    # ============================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS device_subtype (
            id SERIAL PRIMARY KEY,
            service_id VARCHAR(10),
            master_id BIGINT,
            category_id INTEGER NOT NULL,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            price NUMERIC(12, 2),
            duration_minutes INTEGER,
            sort_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            FOREIGN KEY(service_id) REFERENCES master(service_id) ON DELETE CASCADE,
            FOREIGN KEY(master_id) REFERENCES master(id) ON DELETE CASCADE,
            FOREIGN KEY(category_id) REFERENCES device_category(id) ON DELETE CASCADE,
            CHECK ((service_id IS NOT NULL AND master_id IS NULL) OR (service_id IS NULL AND master_id IS NOT NULL)),
            UNIQUE(service_id, master_id, category_id, name)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_device_subtype_service_id ON device_subtype(service_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_device_subtype_master_id ON device_subtype(master_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_device_subtype_category ON device_subtype(category_id);")
    
    # ============================================
    # 4. ТАБЛИЦА ИСТОЧНИКОВ ЗАЯВОК (с проверкой существования)
    # ============================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS lead_source (
            id SERIAL PRIMARY KEY,
            service_id VARCHAR(10),
            master_id BIGINT,
            name VARCHAR(100) NOT NULL,
            code VARCHAR(50),
            description TEXT,
            is_active BOOLEAN DEFAULT TRUE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            FOREIGN KEY(service_id) REFERENCES master(service_id) ON DELETE CASCADE,
            FOREIGN KEY(master_id) REFERENCES master(id) ON DELETE CASCADE,
            CHECK ((service_id IS NOT NULL AND master_id IS NULL) OR (service_id IS NULL AND master_id IS NOT NULL)),
            UNIQUE(service_id, master_id, name)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_lead_source_service_id ON lead_source(service_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_lead_source_master_id ON lead_source(master_id);")
    
    # ============================================
    # 5. ТАБЛИЦА РЕКЛАМНЫХ БЮДЖЕТОВ (с проверкой существования)
    # ============================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS ad_budget (
            id SERIAL PRIMARY KEY,
            source_id INTEGER NOT NULL,
            budget_date DATE NOT NULL,
            amount NUMERIC(12, 2) NOT NULL,
            currency VARCHAR(8) DEFAULT 'RUB',
            description TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            FOREIGN KEY(source_id) REFERENCES lead_source(id) ON DELETE CASCADE,
            UNIQUE(source_id, budget_date)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_ad_budget_source_id ON ad_budget(source_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ad_budget_date ON ad_budget(budget_date);")
    
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
    op.execute("ALTER TABLE service_request DROP CONSTRAINT IF EXISTS fk_service_request_lead_source")
    op.execute("DROP INDEX IF EXISTS ix_service_request_what_was_done")
    op.execute("ALTER TABLE service_request DROP COLUMN IF EXISTS what_was_done")
    op.execute("DROP INDEX IF EXISTS ix_service_request_lead_source_id")
    op.execute("ALTER TABLE service_request DROP COLUMN IF EXISTS lead_source_id")
    op.execute("DROP INDEX IF EXISTS ix_service_request_parts_cost")
    op.execute("ALTER TABLE service_request DROP COLUMN IF EXISTS parts_cost")
    
    op.execute("DROP TABLE IF EXISTS ad_budget")
    op.execute("DROP TABLE IF EXISTS lead_source")
    op.execute("DROP TABLE IF EXISTS device_subtype")
    op.execute("DROP TABLE IF EXISTS device_category")
    
    op.execute("DROP INDEX IF EXISTS ix_master_service_id")
    op.execute("ALTER TABLE master DROP COLUMN IF EXISTS service_id")