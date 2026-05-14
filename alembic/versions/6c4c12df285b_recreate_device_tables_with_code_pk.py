from typing import Sequence, Union
from sqlalchemy import text
from alembic import op
import sqlalchemy as sa

revision: str = "6c4c12df285b"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    
    conn.execute(
        text("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.table_constraints tc
                    WHERE tc.constraint_name = 'service_request_device_subtype_id_fkey'
                      AND tc.table_name = 'service_request'
                      AND tc.constraint_type = 'FOREIGN KEY'
                ) THEN
                    ALTER TABLE service_request
                    DROP CONSTRAINT service_request_device_subtype_id_fkey;
                END IF;
            END$$;
        """)
    )
    op.drop_column("service_request", "device_subtype_id")

    op.drop_table("device_subtype")
    op.drop_table("device_category")

    op.create_table(
        "device_category",
        sa.Column("code", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )

    op.create_table(
        "device_subtype",
        sa.Column("code", sa.String(length=64), primary_key=True),
        sa.Column(
            "category_code",
            sa.String(length=64),
            sa.ForeignKey("device_category.code", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("device_subtype")
    op.drop_table("device_category")

    op.create_table(
        "device_category",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
    )

    op.create_table(
        "device_subtype",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "category_id",
            sa.Integer,
            sa.ForeignKey("device_category.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
    )

    op.add_column(
        "service_request",
        sa.Column("device_subtype_id", sa.Integer, nullable=True),
    )
    op.create_foreign_key(
        "service_request_device_subtype_id_fkey",
        "service_request",
        "device_subtype",
        ["device_subtype_id"],
        ["id"],
    )