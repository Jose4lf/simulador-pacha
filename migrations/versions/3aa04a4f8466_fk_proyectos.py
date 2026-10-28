"""fk proyectos

Revision ID: 3aa04a4f8466
Revises: 8dc8813663d2
Create Date: 2026-10-28 14:17:06.127622

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3aa04a4f8466'
down_revision: Union[str, None] = '8dc8813663d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Corrige una diferencia preexistente entre los modelos y PostgreSQL:
    # la tabla proyectos estaba vacía y sin estas dos claves foráneas.
    op.create_foreign_key(
        'fk_proyectos_equipo_id', 'proyectos', 'equipos',
        ['equipo_id'], ['id'], ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_proyectos_marca_destino_id', 'proyectos', 'marcas',
        ['marca_destino_id'], ['id'], ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_proyectos_marca_destino_id', 'proyectos', type_='foreignkey')
    op.drop_constraint('fk_proyectos_equipo_id', 'proyectos', type_='foreignkey')
