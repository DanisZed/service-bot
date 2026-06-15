"""add_address_website_phone_to_service_center

Revision ID: b9418a5a5205
Revises: 0bace9b40e5c
Create Date: 2026-06-16 00:49:25.474781

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9418a5a5205'
down_revision: Union[str, Sequence[str], None] = '0bace9b40e5c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column('service_center', sa.Column('address', sa.Text(), nullable=True))
    op.add_column('service_center', sa.Column('website', sa.String(255), nullable=True))
    op.add_column('service_center', sa.Column('phone', sa.String(32), nullable=True))

def downgrade():
    op.drop_column('service_center', 'address')
    op.drop_column('service_center', 'website')
    op.drop_column('service_center', 'phone')
