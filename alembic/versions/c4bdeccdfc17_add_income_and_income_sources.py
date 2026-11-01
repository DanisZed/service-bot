"""add income and income sources

Revision ID: c4bdeccdfc17
Revises: 98ae4a60487b
Create Date: 2026-11-02 01:05:14.295894

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4bdeccdfc17'
down_revision: Union[str, Sequence[str], None] = '98ae4a60487b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "income_source",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("master_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["master_id"],
            ["master.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


    op.create_index("ix_income_source_id", "income_source", ["id"])
    op.create_index("ix_income_source_master_id", "income_source", ["master_id"])


    op.create_table(
        "income",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("master_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("resale_deal_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["master_id"],
            ["master.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["income_source.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["resale_deal_id"],
            ["resale_deals.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


    op.create_index("ix_income_id", "income", ["id"])
    op.create_index("ix_income_master_id", "income", ["master_id"])
    op.create_index("ix_income_source_id", "income", ["source_id"])
    op.create_index("ix_income_received_at", "income", ["received_at"])


def downgrade() -> None:
    op.drop_index("ix_income_received_at", table_name="income")
    op.drop_index("ix_income_source_id", table_name="income")
    op.drop_index("ix_income_master_id", table_name="income")
    op.drop_index("ix_income_id", table_name="income")
    op.drop_table("income")


    op.drop_index("ix_income_source_master_id", table_name="income_source")
    op.drop_index("ix_income_source_id", table_name="income_source")
    op.drop_table("income_source")