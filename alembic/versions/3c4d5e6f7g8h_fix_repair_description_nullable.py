"""fix_repair_description_nullable

Revision ID: 3c4d5e6f7g8h
Revises: 2b3c4d5e6f7g
Create Date: 2026-06-17 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '3c4d5e6f7g8h'
down_revision = '2b3c4d5e6f7g'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('service_request', 'repair_description', nullable=True)


def downgrade():
    op.alter_column('service_request', 'repair_description', nullable=False)