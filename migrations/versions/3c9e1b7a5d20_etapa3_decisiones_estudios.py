"""Etapa 3: estado de decisiones, costo de estudios y resultados genéricos

Revision ID: 3c9e1b7a5d20
Revises: 77af1f3a6899
Create Date: 2026-10-28 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3c9e1b7a5d20'
down_revision: Union[str, None] = '77af1f3a6899'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Borrador vs. decisión efectiva. Las decisiones existentes se consideran
    # enviadas para no cambiar el comportamiento previo.
    op.add_column(
        'decisiones',
        sa.Column(
            'estado', sa.String(length=20), nullable=False,
            server_default='enviada',
        ),
    )
    op.add_column(
        'decisiones',
        sa.Column('actualizada', sa.DateTime(), nullable=True),
    )

    # Costo congelado al momento de la compra: el catálogo puede cambiar.
    op.add_column(
        'compras_estudios',
        sa.Column('costo', sa.Float(), nullable=False, server_default='0'),
    )

    # Resultados de estudios sin tabla específica (hábitos, ideales, tests).
    op.create_table(
        'estudio_resultados',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('compra_id', sa.Integer(), nullable=False),
        sa.Column('categoria', sa.String(length=40), nullable=False),
        sa.Column('entidad', sa.String(length=60), nullable=False),
        sa.Column('metrica', sa.String(length=40), nullable=False),
        sa.Column('valor', sa.Float(), nullable=True),
        sa.Column('texto', sa.String(length=120), nullable=True),
        sa.ForeignKeyConstraint(['compra_id'], ['compras_estudios.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_estudio_resultados_compra', 'estudio_resultados', ['compra_id']
    )


def downgrade() -> None:
    op.drop_index('ix_estudio_resultados_compra', table_name='estudio_resultados')
    op.drop_table('estudio_resultados')
    op.drop_column('compras_estudios', 'costo')
    op.drop_column('decisiones', 'actualizada')
    op.drop_column('decisiones', 'estado')
