"""service center ownership and dispatcher requests

Revision ID: 832cae1913e6
Revises: 0b1589b17552
Create Date: 2026-10-29 20:49:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "832cae1913e6"
down_revision: Union[str, Sequence[str], None] = "0b1589b17552"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Справочники получают владельца-сервисный центр.
    for table_name in (
        "lead_source",
        "device_category",
        "device_subtype",
    ):
        op.add_column(
            table_name,
            sa.Column("service_center_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            f"fk_{table_name}_service_center",
            table_name,
            "service_center",
            ["service_center_id"],
            ["id"],
            ondelete="CASCADE",
        )

    # 2. Заявки получают сервисный центр и данные диспетчерской передачи.
    op.add_column(
        "service_request",
        sa.Column("service_center_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "service_request",
        sa.Column(
            "is_from_dispatcher",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "service_request",
        sa.Column(
            "dispatcher_commission_percent",
            sa.Numeric(5, 2),
            nullable=True,
        ),
    )
    op.add_column(
        "service_request",
        sa.Column(
            "dispatcher_fee_amount",
            sa.Numeric(12, 2),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_service_request_service_center",
        "service_request",
        "service_center",
        ["service_center_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 3. Процент диспетчера в настройках мастера.
    op.add_column(
        "master",
        sa.Column(
            "dispatcher_commission_percent",
            sa.Numeric(5, 2),
            nullable=True,
        ),
    )

    # 4. Текущие общие справочники передаём сервисному центру №2.
    op.execute("""
        UPDATE lead_source
        SET service_center_id = 2
        WHERE master_id IS NULL;
    """)

    op.execute("""
        UPDATE device_category
        SET service_center_id = 2
        WHERE master_id IS NULL;
    """)

    op.execute("""
        UPDATE device_subtype
        SET service_center_id = 2
        WHERE master_id IS NULL;
    """)

    # 5. Существующие заявки мастеров сервисного центра №2
    # становятся заявками этого сервисного центра.
    op.execute("""
        UPDATE service_request AS sr
        SET service_center_id = m.service_center_id,
            is_from_dispatcher = (
                sr.assigned_master_id IS NOT NULL
                AND sr.master_id <> sr.assigned_master_id
            )
        FROM master AS m
        WHERE sr.master_id = m.id
          AND m.service_center_id = 2;
    """)

    # 6. Для уже переданных заявок фиксируем процент диспетчера.
    op.execute("""
        UPDATE service_request AS sr
        SET dispatcher_commission_percent = m.dispatcher_commission_percent
        FROM master AS m
        WHERE sr.assigned_master_id = m.id
          AND sr.is_from_dispatcher = true;
    """)

    # 7. Защита общих справочников сервисного центра от дублей.
    op.create_index(
        "uq_lead_source_center_name",
        "lead_source",
        ["service_center_id", "name"],
        unique=True,
        postgresql_where=sa.text("master_id IS NULL"),
    )

    op.create_index(
        "uq_device_category_center_name",
        "device_category",
        ["service_center_id", "name"],
        unique=True,
        postgresql_where=sa.text("master_id IS NULL"),
    )

    op.create_index(
        "uq_device_subtype_center_category_name",
        "device_subtype",
        ["service_center_id", "category_id", "name"],
        unique=True,
        postgresql_where=sa.text("master_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_device_subtype_center_category_name",
        table_name="device_subtype",
    )
    op.drop_index(
        "uq_device_category_center_name",
        table_name="device_category",
    )
    op.drop_index(
        "uq_lead_source_center_name",
        table_name="lead_source",
    )

    op.drop_constraint(
        "fk_service_request_service_center",
        "service_request",
        type_="foreignkey",
    )
    op.drop_column("service_request", "dispatcher_fee_amount")
    op.drop_column("service_request", "dispatcher_commission_percent")
    op.drop_column("service_request", "is_from_dispatcher")
    op.drop_column("service_request", "service_center_id")

    op.drop_column("master", "dispatcher_commission_percent")

    for table_name in (
        "lead_source",
        "device_category",
        "device_subtype",
    ):
        op.drop_constraint(
            f"fk_{table_name}_service_center",
            table_name,
            type_="foreignkey",
        )
        op.drop_column(table_name, "service_center_id")