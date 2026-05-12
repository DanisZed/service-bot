"""initial schema

Revision ID: 95f4ca8a9149
Revises:
Create Date: 2026-05-12 21:17:54.478449
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "95f4ca8a9149"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

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

    op.create_table(
        "client",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False, unique=True),
        sa.Column("telegram_id", sa.BigInteger, nullable=True, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "service_request",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "client_id",
            sa.Integer,
            sa.ForeignKey("client.id"),
            nullable=False,
        ),
        sa.Column(
            "device_category_id",
            sa.Integer,
            sa.ForeignKey("device_category.id"),
            nullable=False,
        ),
        sa.Column(
            "device_subtype_id",
            sa.Integer,
            sa.ForeignKey("device_subtype.id"),
            nullable=True,
        ),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="new",
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "time_slot_booking",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "request_id",
            sa.Integer,
            sa.ForeignKey("service_request.id"),
            nullable=False,
        ),
        sa.Column("start_time", sa.DateTime, nullable=False),
        sa.Column("end_time", sa.DateTime, nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_table("time_slot_booking")
    op.drop_table("service_request")
    op.drop_table("client")
    op.drop_table("device_subtype")
    op.drop_table("device_category")