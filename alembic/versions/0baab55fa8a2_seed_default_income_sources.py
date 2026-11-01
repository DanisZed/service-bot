"""seed default income sources

Revision ID: 0baab55fa8a2
Revises: c4bdeccdfc17
Create Date: 2026-11-02 01:06:48.521227

"""
from typing import Sequence, Union


from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "0baab55fa8a2"
down_revision: Union[str, Sequence[str], None] = "c4bdeccdfc17"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_SOURCES = [
    "Субаренда",
    "Продажа б/у запчастей",
    "Доставка",
    "Другое",
]


def upgrade() -> None:
    connection = op.get_bind()


    for source_name in DEFAULT_SOURCES:
        connection.execute(
            text(
                """
                INSERT INTO income_source (master_id, name)
                SELECT m.id, :source_name
                FROM master m
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM income_source s
                    WHERE s.master_id = m.id
                      AND lower(s.name) = lower(:source_name)
                )
                """
            ),
            {"source_name": source_name},
        )


def downgrade() -> None:
    pass