"""add resale items and deal item link

Revision ID: 0b1589b17552
Revises: c1602305c640
Create Date: 2026-10-27 10:52:09.918621

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0b1589b17552'
down_revision: Union[str, Sequence[str], None] = 'c1602305c640'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "part",
        sa.Column(
            "item_type",
            sa.String(length=32),
            nullable=False,
            server_default="part",
        ),
    )


    op.add_column(
        "resale_deals",
        sa.Column(
            "resale_item_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "part.id",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
    )


    op.create_index(
        "ix_resale_deals_resale_item_id",
        "resale_deals",
        ["resale_item_id"],
    )



def downgrade() -> None:
    op.drop_index(
        "ix_resale_deals_resale_item_id",
        table_name="resale_deals",
    )


    op.drop_column("resale_deals", "resale_item_id")
    op.drop_column("part", "item_type")