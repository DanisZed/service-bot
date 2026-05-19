from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "9ac3e1d2ac4b"
down_revision: Union[str, Sequence[str], None] = "6c4c12df285b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Схема уже существует в рабочей БД.
    # Эта миграция использовалась для начального создания таблиц,
    # но на текущей базе ничего делать не должна.
    pass


def downgrade() -> None:
    # Для отката тоже ничего не делаем.
    pass