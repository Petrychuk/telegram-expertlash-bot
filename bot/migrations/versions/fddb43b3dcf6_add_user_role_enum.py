"""add user role enum

Revision ID: fddb43b3dcf6
Revises: 33e92ef624cf
Create Date: 2025-09-16 18:13:53.774744
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'fddb43b3dcf6'
down_revision: Union[str, Sequence[str], None] = '33e92ef624cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# создаём Enum-тип вручную
userrole = sa.Enum('student', 'teacher', 'admin', name='userrole')

def upgrade() -> None:
    # сначала создаём сам ENUM-тип в Postgres
    userrole.create(op.get_bind(), checkfirst=True)

    # затем добавляем колонку
    op.add_column(
        'users',
        sa.Column('role', userrole, server_default='student', nullable=False)
    )


def downgrade() -> None:
    # откат: удаляем колонку и сам Enum-тип
    op.drop_column('users', 'role')
    userrole.drop(op.get_bind(), checkfirst=True)
