"""add parent id to part categories


Revision ID: b9d0dbd823f1
Revises: a244e8f722a2
Create Date: 2026-10-27 01:51:43.051326


"""
from typing import Sequence, Union


from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision: str = 'b9d0dbd823f1'
down_revision: Union[str, Sequence[str], None] = 'a244e8f722a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    op.add_column(
        "part_categories",
        sa.Column(
            "parent_id",
            sa.Integer(),
            sa.ForeignKey(
                "part_categories.id",
                ondelete="CASCADE",
            ),
            nullable=True,
        ),
    )


    op.create_index(
        "ix_part_categories_parent_id",
        "part_categories",
        ["parent_id"],
    )


    op.drop_constraint(
        "uq_part_categories_master_id_name",
        "part_categories",
        type_="unique",
    )


    op.create_unique_constraint(
        "uq_part_categories_master_parent_name",
        "part_categories",
        ["master_id", "parent_id", "name"],
    )



def downgrade() -> None:
    op.drop_constraint(
        "uq_part_categories_master_parent_name",
        "part_categories",
        type_="unique",
    )


    op.create_unique_constraint(
        "uq_part_categories_master_id_name",
        "part_categories",
        ["master_id", "name"],
    )


    op.drop_index(
        "ix_part_categories_parent_id",
        table_name="part_categories",
    )


    op.drop_column("part_categories", "parent_id")