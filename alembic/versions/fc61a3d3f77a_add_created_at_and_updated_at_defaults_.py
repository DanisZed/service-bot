"""add created_at and updated_at defaults to part

Revision ID: fc61a3d3f77a
Revises: 832cae1913e6
Create Date: 2026-10-30 10:36:45.705256

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fc61a3d3f77a'
down_revision: Union[str, Sequence[str], None] = '832cae1913e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "part",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )


    op.alter_column(
        "part",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )




def downgrade() -> None:
    op.alter_column(
        "part",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=None,
    )


    op.alter_column(
        "part",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=None,
    )