"""password temporal y cambio obligatorio

Revision ID: 77af1f3a6899
Revises: 3aa04a4f8466
Create Date: 2026-10-28 14:23:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '77af1f3a6899'
down_revision: Union[str, None] = '3aa04a4f8466'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Marca de cambio obligatorio y fecha del último cambio de contraseña.
    op.add_column(
        'usuarios',
        sa.Column(
            'debe_cambiar_password',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        'usuarios',
        sa.Column('password_actualizada', sa.DateTime(), nullable=True),
    )

    # Las cuentas existentes conservan su contraseña actual, pero deberán
    # cambiarla en el primer inicio de sesión tras esta etapa.
    op.execute("UPDATE usuarios SET debe_cambiar_password = true")


def downgrade() -> None:
    op.drop_column('usuarios', 'password_actualizada')
    op.drop_column('usuarios', 'debe_cambiar_password')
