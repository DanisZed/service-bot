"""add parts inventory

Revision ID: ef116693712a
Revises: f3c14f9a865d
Create Date: 2026-10-25 22:04:46.652274

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ef116693712a"
down_revision: Union[str, Sequence[str], None] = "f3c14f9a865d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "part",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("master_id", sa.BigInteger(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["master_id"], ["master.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_part_master_id"),
        "part",
        ["master_id"],
        unique=False,
    )

    op.create_table(
        "part_batch",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("part_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity_initial", sa.Integer(), nullable=False),
        sa.Column("quantity_remaining", sa.Integer(), nullable=False),
        sa.Column(
            "purchase_price",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("supplier", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["part_id"], ["part.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_part_batch_part_id"),
        "part_batch",
        ["part_id"],
        unique=False,
    )

    op.create_table(
        "request_part",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("request_id", sa.BigInteger(), nullable=False),
        sa.Column("part_id", sa.BigInteger(), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "unit_cost",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column(
            "total_cost",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["part_batch.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["part_id"],
            ["part.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["service_request.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_request_part_batch_id"),
        "request_part",
        ["batch_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_request_part_part_id"),
        "request_part",
        ["part_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_request_part_request_id"),
        "request_part",
        ["request_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_request_part_request_id"),
        table_name="request_part",
    )
    op.drop_index(
        op.f("ix_request_part_part_id"),
        table_name="request_part",
    )
    op.drop_index(
        op.f("ix_request_part_batch_id"),
        table_name="request_part",
    )
    op.drop_table("request_part")

    op.drop_index(
        op.f("ix_part_batch_part_id"),
        table_name="part_batch",
    )
    op.drop_table("part_batch")

    op.drop_index(
        op.f("ix_part_master_id"),
        table_name="part",
    )
    op.drop_table("part")