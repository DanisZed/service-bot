"""add visit reminder sent at

Revision ID: f3c14f9a865d
Revises: 1da9ece302a4
Create Date: 2026-10-19 21:33:32.928742

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3c14f9a865d'
down_revision: Union[str, Sequence[str], None] = '1da9ece302a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "service_request",
        sa.Column(
            "visit_reminder_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "service_request",
        "visit_reminder_sent_at",
    )