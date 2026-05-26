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
    # ========== ТАБЛИЦА master ==========
    
    # 1. Добавляем lastname (после name)
    op.execute("""
        DO $$ 
        BEGIN 
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='master' AND column_name='lastname') THEN
                ALTER TABLE master ADD COLUMN lastname TEXT;
            END IF;
        END $$;
    """)
    
    # 2. Добавляем service_name
    op.execute("""
        DO $$ 
        BEGIN 
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='master' AND column_name='service_name') THEN
                ALTER TABLE master ADD COLUMN service_name TEXT;
            END IF;
        END $$;
    """)
    
    # 3. Добавляем master_id (уникальный строковый ID)
    op.execute("""
        DO $$ 
        BEGIN 
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='master' AND column_name='master_id') THEN
                ALTER TABLE master ADD COLUMN master_id VARCHAR(12) UNIQUE;
                CREATE INDEX ix_master_master_id ON master(master_id);
            END IF;
        END $$;
    """)
    
    # 4. Добавляем is_admin
    op.execute("""
        DO $$ 
        BEGIN 
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='master' AND column_name='is_admin') THEN
                ALTER TABLE master ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0;
            END IF;
        END $$;
    """)
    
    # ========== ТАБЛИЦА service_request ==========
    
    # 5. Добавляем service_name
    op.execute("""
        DO $$ 
        BEGIN 
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='service_request' AND column_name='service_name') THEN
                ALTER TABLE service_request ADD COLUMN service_name TEXT;
                CREATE INDEX ix_service_request_service_name ON service_request(service_name);
            END IF;
        END $$;
    """)
    
    # 6. Добавляем service_id (уникальный строковый ID)
    op.execute("""
        DO $$ 
        BEGIN 
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='service_request' AND column_name='service_id') THEN
                ALTER TABLE service_request ADD COLUMN service_id VARCHAR(10) UNIQUE;
                CREATE INDEX ix_service_request_service_id ON service_request(service_id);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # ========== ТАБЛИЦА service_request ==========
    
    # Удаляем service_id
    op.execute("""
        DO $$ 
        BEGIN 
            IF EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name='service_request' AND column_name='service_id') THEN
                DROP INDEX IF EXISTS ix_service_request_service_id;
                ALTER TABLE service_request DROP COLUMN service_id;
            END IF;
        END $$;
    """)
    
    # Удаляем service_name
    op.execute("""
        DO $$ 
        BEGIN 
            IF EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name='service_request' AND column_name='service_name') THEN
                DROP INDEX IF EXISTS ix_service_request_service_name;
                ALTER TABLE service_request DROP COLUMN service_name;
            END IF;
        END $$;
    """)
    
    # ========== ТАБЛИЦА master ==========
    
    # Удаляем is_admin
    op.execute("""
        DO $$ 
        BEGIN 
            IF EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name='master' AND column_name='is_admin') THEN
                ALTER TABLE master DROP COLUMN is_admin;
            END IF;
        END $$;
    """)
    
    # Удаляем master_id
    op.execute("""
        DO $$ 
        BEGIN 
            IF EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name='master' AND column_name='master_id') THEN
                DROP INDEX IF EXISTS ix_master_master_id;
                ALTER TABLE master DROP COLUMN master_id;
            END IF;
        END $$;
    """)
    
    # Удаляем service_name
    op.execute("""
        DO $$ 
        BEGIN 
            IF EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name='master' AND column_name='service_name') THEN
                ALTER TABLE master DROP COLUMN service_name;
            END IF;
        END $$;
    """)
    
    # Удаляем lastname
    op.execute("""
        DO $$ 
        BEGIN 
            IF EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name='master' AND column_name='lastname') THEN
                ALTER TABLE master DROP COLUMN lastname;
            END IF;
        END $$;
    """)