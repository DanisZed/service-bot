"""initial schema v2

Revision ID: 9ac3e1d2ac4b
Revises: 
Create Date: 2026-05-12 22:11:49.911583

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "9ac3e1d2ac4b"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # client
    op.create_table(
        "client",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text, nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True, unique=True),
        sa.Column("primary_source", sa.String(length=32), nullable=True),
        sa.Column("max_user_id", sa.BigInteger, nullable=True),
        sa.Column("max_chat_id", sa.BigInteger, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # service_request
    op.create_table(
        "service_request",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="new"),
        sa.Column(
            "opened_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("in_work_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text, nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("user_external_id", sa.BigInteger, nullable=True),
        sa.Column("chat_external_id", sa.BigInteger, nullable=True),
        sa.Column("client_id", sa.BigInteger, sa.ForeignKey("client.id"), nullable=True),
        sa.Column("client_name", sa.Text, nullable=True),
        sa.Column("client_phone", sa.String(length=32), nullable=True),
        sa.Column("main_category", sa.String(length=64), nullable=False),
        sa.Column("subtype", sa.String(length=64), nullable=False),
        sa.Column("custom_device", sa.Text, nullable=True),
        sa.Column("service_title", sa.Text, nullable=True),
        sa.Column("problem_description", sa.Text, nullable=False),
        sa.Column("location_type", sa.String(length=32), nullable=False),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("address_details", sa.Text, nullable=True),
        sa.Column("date_iso", sa.Date, nullable=True),
        sa.Column("time_slot", sa.String(length=32), nullable=True),
        sa.Column("datetime_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("datetime_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="RUB"),
        sa.Column(
            "payment_status",
            sa.String(length=32),
            nullable=False,
            server_default="unpaid",
        ),
        sa.Column("paid_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("yandex_url", sa.Text, nullable=True),
        sa.Column("google_url", sa.Text, nullable=True),
        sa.Column("meta", sa.JSON, nullable=True),
    )

    # time_slot_booking
    op.create_table(
        "time_slot_booking",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "service_request_id",
            sa.BigInteger,
            sa.ForeignKey("service_request.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date_iso", sa.Date, nullable=False),
        sa.Column("time_slot", sa.String(length=32), nullable=False),
        sa.Column("datetime_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("datetime_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="active",
        ),
    )

    # device_category
    op.create_table(
        "device_category",
        sa.Column("code", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )

    # device_subtype
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
    op.drop_table("time_slot_booking")
    op.drop_table("service_request")
    op.drop_table("client")