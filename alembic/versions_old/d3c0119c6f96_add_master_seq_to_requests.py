from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = "d3c0119c6f96"
down_revision = "9ac3e1d2ac4b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Добавляем колонку master_seq в таблицу заявок
    op.add_column(
        "service_request",
        sa.Column("master_seq", sa.Integer(), nullable=True),
    )

    # 2. Заполняем master_seq для существующих заявок
    conn = op.get_bind()
    conn.execute(
        text(
            """
            UPDATE service_request r
            SET master_seq = sub.seq
            FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                         PARTITION BY master_id
                         ORDER BY id
                       ) AS seq
                FROM service_request
            ) AS sub
            WHERE r.id = sub.id;
            """
        )
    )


def downgrade() -> None:
    op.drop_column("service_request", "master_seq")