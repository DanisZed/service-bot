"""add public_id and warranty to resale deals

Revision ID: fd9fd955b5c2
Revises: fc61a3d3f77a
Create Date: 2026-11-01 21:41:21.204202

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fd9fd955b5c2'
down_revision: Union[str, Sequence[str], None] = 'fc61a3d3f77a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "resale_deals",
        sa.Column(
            "public_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            unique=True,
        ),
    )


    op.add_column(
        "resale_deals",
        sa.Column("warranty_months", sa.Integer(), nullable=True),
    )




def downgrade() -> None:
    op.drop_column("resale_deals", "warranty_months")
    op.drop_column("resale_deals", "public_id")