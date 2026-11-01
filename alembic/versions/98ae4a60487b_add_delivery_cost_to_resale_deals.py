"""add delivery cost to resale deals

Revision ID: 98ae4a60487b
Revises: fd9fd955b5c2
Create Date: 2026-11-01 22:50:03.009484

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '98ae4a60487b'
down_revision: Union[str, Sequence[str], None] = 'fd9fd955b5c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


import sqlalchemy as sa
from alembic import op




def upgrade() -> None:
    op.add_column(
        "resale_deals",
        sa.Column(
            "delivery_cost",
            sa.Numeric(12, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )




def downgrade() -> None:
    op.drop_column("resale_deals", "delivery_cost")