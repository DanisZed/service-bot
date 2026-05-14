"""add master_seq to requests

Revision ID: d3c0119c6f96
Revises: 
Create Date: 2026-05-14 17:49:22.367190

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = "add_master_seq_to_requests"
down_revision = "9ac3e1d2ac4b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. добавить колонку
    op.add_column(
        "requests",
        sa.Column("master_seq", sa.Integer(), nullable=True),
    )

    # 2. заполнить master_seq для уже существующих заявок
    conn = op.get_bind()

    # сгруппировать по master_id и пронумеровать по возрастанию id
    # синтаксис для PostgreSQL (window-функция)
    conn.execute(
        text(
            """
            UPDATE requests r
            SET master_seq = sub.seq
            FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                         PARTITION BY master_id
                         ORDER BY id
                       ) AS seq
                FROM requests
            ) AS sub
            WHERE r.id = sub.id;
            """
        )
    )

    # 3. при желании можно сделать колонку NOT NULL
    # op.alter_column("requests", "master_seq", nullable=False)


def downgrade() -> None:
    op.drop_column("requests", "master_seq")