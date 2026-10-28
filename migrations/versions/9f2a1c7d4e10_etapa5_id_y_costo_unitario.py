"""Etapa 5: costo unitario de marca, estado de aplicación y resultados de I&D

Revision ID: 9f2a1c7d4e10
Revises: 3c9e1b7a5d20
Create Date: 2026-10-28
"""
from alembic import op
import sqlalchemy as sa


revision = "9f2a1c7d4e10"
down_revision = "3c9e1b7a5d20"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "marcas",
        sa.Column("costo_unitario", sa.Float(), nullable=False,
                  server_default="0"),
    )
    op.add_column(
        "proyectos",
        sa.Column("anio_aplicacion", sa.Integer(), nullable=True),
    )
    op.add_column(
        "proyectos",
        sa.Column("costo_estandar", sa.Float(), nullable=True,
                  server_default="0"),
    )
    op.add_column(
        "proyectos",
        sa.Column("presupuesto_normal", sa.Float(), nullable=True,
                  server_default="0"),
    )
    op.add_column(
        "proyectos",
        sa.Column("probabilidad_calculada", sa.Float(), nullable=True,
                  server_default="0"),
    )

    op.create_table(
        "proyecto_resultados",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("proyecto_id", sa.Integer(), nullable=False),
        sa.Column("anio", sa.Integer(), nullable=False),
        sa.Column("resultado", sa.String(length=20), nullable=False),
        sa.Column("probabilidad", sa.Float(), nullable=True),
        sa.Column("presupuesto_normal", sa.Float(), nullable=True),
        sa.Column("presupuesto_asignado", sa.Float(), nullable=True),
        sa.Column("atributo_fallido", sa.Integer(), nullable=True),
        sa.Column("presupuesto_adicional", sa.Float(), nullable=True),
        sa.Column("costo_estandar", sa.Float(), nullable=True),
        sa.Column("costo_minimo", sa.Float(), nullable=True),
        sa.Column("detalle", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["proyecto_id"], ["proyectos.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_proyecto_resultados_proyecto", "proyecto_resultados",
        ["proyecto_id"],
    )

    # Costo unitario inicial: atributo físico 6 (costo pedido a I&D) del año
    # más reciente registrado para cada marca.
    op.execute(sa.text(
        """
        UPDATE marcas
           SET costo_unitario = COALESCE((
                SELECT a.valor
                  FROM atributos_fisicos a
                 WHERE a.marca_id = marcas.id AND a.numero = 6
                 ORDER BY a.anio DESC
                 LIMIT 1
           ), 0)
        """
    ))


def downgrade():
    op.drop_index(
        "ix_proyecto_resultados_proyecto", table_name="proyecto_resultados"
    )
    op.drop_table("proyecto_resultados")
    op.drop_column("proyectos", "probabilidad_calculada")
    op.drop_column("proyectos", "presupuesto_normal")
    op.drop_column("proyectos", "costo_estandar")
    op.drop_column("proyectos", "anio_aplicacion")
    op.drop_column("marcas", "costo_unitario")
