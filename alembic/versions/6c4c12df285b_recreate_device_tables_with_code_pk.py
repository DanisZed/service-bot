from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "6c4c12df285b"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Удаляем внешний ключ и колонку, которая ссылается на старую таблицу device_subtype
    # Имя констрейнта можно оставить таким, если оно ровно такое, как в ошибке:
    # "service_request_device_subtype_id_fkey"
    op.drop_constraint(
        "service_request_device_subtype_id_fkey",
        "service_request",
        type_="foreignkey",
    )
    op.drop_column("service_request", "device_subtype_id")

    # 2. Дропаем старые таблицы
    op.drop_table("device_subtype")
    op.drop_table("device_category")

    # 3. Создаём новые таблицы по текущим моделям

    op.create_table(
        "device_category",
        sa.Column("code", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )

    op.create_table(
        "device_subtype",
        sa.Column("code", sa.String(length=64), primary_key=True),
        sa.Column(
            "category_code",
            sa.String(length=64),
            sa.ForeignKey("device_category.code", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )

    # 4. При необходимости можно добавить новую FK-колонку в service_request,
    #    чтобы ссылаться по коду, но в твоей модели ServiceRequest сейчас поле subtype=String,
    #    без FK, поэтому ничего не добавляем.


def downgrade() -> None:
    # Обратный порядок: дропаем новые таблицы, создаём старые и возвращаем колонку/FK
    op.drop_table("device_subtype")
    op.drop_table("device_category")

    op.create_table(
        "device_category",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
    )

    op.create_table(
        "device_subtype",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "category_id",
            sa.Integer,
            sa.ForeignKey("device_category.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
    )

    # Возвращаем колонку и FK в service_request
    op.add_column(
        "service_request",
        sa.Column("device_subtype_id", sa.Integer, nullable=True),
    )
    op.create_foreign_key(
        "service_request_device_subtype_id_fkey",
        "service_request",
        "device_subtype",
        ["device_subtype_id"],
        ["id"],
    )