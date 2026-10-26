"""add part categories


Revision ID: a244e8f722a2
Revises: 9f53e16ad2cf
Create Date: 2026-10-27 01:17:13.483420


"""
from typing import Sequence, Union


from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision: str = 'a244e8f722a2'
down_revision: Union[str, Sequence[str], None] = '9f53e16ad2cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    op.create_table(
        "part_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "master_id",
            sa.BigInteger(),
            sa.ForeignKey("master.id", ondelete="CASCADE"),
            nullable=False,
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
        "ix_part_categories_master_id",
        "part_categories",
        ["master_id"],
    )


    op.create_unique_constraint(
        "uq_part_categories_master_id_name",
        "part_categories",
        ["master_id", "name"],
    )



def downgrade() -> None:
    op.drop_constraint(
        "uq_part_categories_master_id_name",
        "part_categories",
        type_="unique",
    )


    op.drop_index(
        "ix_part_categories_master_id",
        table_name="part_categories",
    )


    op.drop_table("part_categories")