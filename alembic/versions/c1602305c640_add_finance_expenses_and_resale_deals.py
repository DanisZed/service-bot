"""add finance expenses and resale deals


Revision ID: c1602305c640
Revises: b9d0dbd823f1
Create Date: 2026-10-27


"""
from typing import Sequence, Union


from alembic import op
import sqlalchemy as sa



revision: str = "c1602305c640"
down_revision: Union[str, Sequence[str], None] = "b9d0dbd823f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    op.create_table(
        "expense_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "master_id",
            sa.BigInteger(),
            sa.ForeignKey("master.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            sa.Integer(),
            sa.ForeignKey(
                "expense_categories.id",
                ondelete="CASCADE",
            ),
            nullable=True,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


    op.create_index(
        "ix_expense_categories_master_id",
        "expense_categories",
        ["master_id"],
    )


    op.create_index(
        "ix_expense_categories_parent_id",
        "expense_categories",
        ["parent_id"],
    )


    op.create_unique_constraint(
        "uq_expense_categories_master_parent_name",
        "expense_categories",
        ["master_id", "parent_id", "name"],
    )


    op.create_table(
        "resale_deals",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "master_id",
            sa.BigInteger(),
            sa.ForeignKey("master.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="purchased",
        ),
        sa.Column(
            "purchase_amount",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "sale_amount",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


    op.create_index(
        "ix_resale_deals_master_id",
        "resale_deals",
        ["master_id"],
    )


    op.create_table(
        "expenses",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "master_id",
            sa.BigInteger(),
            sa.ForeignKey("master.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey(
                "expense_categories.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "resale_deal_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "resale_deals.id",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("spent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


    op.create_index(
        "ix_expenses_master_id",
        "expenses",
        ["master_id"],
    )


    op.create_index(
        "ix_expenses_category_id",
        "expenses",
        ["category_id"],
    )


    op.create_index(
        "ix_expenses_resale_deal_id",
        "expenses",
        ["resale_deal_id"],
    )


    op.create_table(
        "resale_deal_parts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "deal_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "resale_deals.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "part_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "part.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "batch_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "part_batch.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


    op.create_index(
        "ix_resale_deal_parts_deal_id",
        "resale_deal_parts",
        ["deal_id"],
    )


    op.create_index(
        "ix_resale_deal_parts_part_id",
        "resale_deal_parts",
        ["part_id"],
    )


    op.create_index(
        "ix_resale_deal_parts_batch_id",
        "resale_deal_parts",
        ["batch_id"],
    )



def downgrade() -> None:
    op.drop_table("resale_deal_parts")
    op.drop_table("expenses")
    op.drop_table("resale_deals")
    op.drop_table("expense_categories")