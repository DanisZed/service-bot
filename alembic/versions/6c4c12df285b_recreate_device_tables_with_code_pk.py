from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "6c4c12df285b"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # На новых базах эта миграция не нужна: таблиц ещё нет.
    # Вся актуальная схема создаётся в 9ac3e1d2ac4b_initial_schema_v2.
    pass


def downgrade() -> None:
    # Для отката тоже ничего не делаем.
    pass