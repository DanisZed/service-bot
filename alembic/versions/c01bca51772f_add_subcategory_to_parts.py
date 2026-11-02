"""add subcategory to parts

Revision ID: c01bca51772f
Revises: 0baab55fa8a2
Create Date: 2026-11-02 17:03:36.319285

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c01bca51772f'
down_revision: Union[str, Sequence[str], None] = '0baab55fa8a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "part",
        sa.Column("subcategory", sa.String(length=100), nullable=True),
    )


    op.execute(
        """
        UPDATE part p
        SET subcategory = p.category,
            category = parent_category.name
        FROM part_categories child_category
        JOIN part_categories parent_category
          ON parent_category.id = child_category.parent_id
        WHERE p.category = child_category.name
        """
    )


    op.create_index(
        "ix_part_subcategory",
        "part",
        ["subcategory"],
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE part p
        SET category = COALESCE(p.subcategory, p.category)
        WHERE p.subcategory IS NOT NULL
        """
    )


    op.drop_index("ix_part_subcategory", table_name="part")
    op.drop_column("part", "subcategory")