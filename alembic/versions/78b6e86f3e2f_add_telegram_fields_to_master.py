"""add_telegram_fields_to_master

Revision ID: 78b6e86f3e2f
Revises: d3c0119c6f96
Create Date: 2026-05-18 
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision = "78b6e86f3e2f"  # оставь тот, что сгенерировался
down_revision = "d3c0119c6f96"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем поля Telegram
    op.add_column('master', sa.Column('telegram_user_id', sa.BigInteger(), nullable=True, unique=True))
    op.add_column('master', sa.Column('telegram_chat_id', sa.BigInteger(), nullable=True))
    op.add_column('master', sa.Column('telegram_auth_code', sa.String(10), nullable=True))
    op.add_column('master', sa.Column('telegram_code_expires_at', sa.DateTime(timezone=True), nullable=True))
    
    # Создаём индекс для быстрого поиска по коду
    op.create_index('ix_master_telegram_auth_code', 'master', ['telegram_auth_code'])


def downgrade() -> None:
    op.drop_index('ix_master_telegram_auth_code')
    op.drop_column('master', 'telegram_code_expires_at')
    op.drop_column('master', 'telegram_auth_code')
    op.drop_column('master', 'telegram_chat_id')
    op.drop_column('master', 'telegram_user_id')