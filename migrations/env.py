"""Configuración de Alembic para PACHA (SQLAlchemy puro, sin Flask-SQLAlchemy)."""
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from config import Config
from core.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _url():
    """Permite apuntar a una BD temporal durante la generación de migraciones."""
    return (
        os.environ.get("ALEMBIC_DATABASE_URL")
        or Config.DATABASE_URL
        or Config.SQLITE_FALLBACK_URL
    )


def run_migrations_offline():
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    seccion = config.get_section(config.config_ini_section) or {}
    seccion["sqlalchemy.url"] = _url()

    connectable = engine_from_config(
        seccion,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
