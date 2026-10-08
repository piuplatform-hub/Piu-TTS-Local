import asyncio
from logging.config import fileConfig
from sqlalchemy import pool, event
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from apps.server.src.config import settings
from apps.server.src.database import Base
from apps.server.src import models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url():
    cmd_url = config.get_main_option("sqlalchemy.url")
    if cmd_url and cmd_url != "sqlite:///data/studio.db":
        if cmd_url.startswith("sqlite:///") and not cmd_url.startswith("sqlite+aiosqlite:///"):
            cmd_url = cmd_url.replace("sqlite:///", "sqlite+aiosqlite:///")
        return cmd_url
    url = settings.get_database_url()
    return url


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # Crucial for SQLite schema alterations
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    # Enforce SQLite foreign keys
    connection.execute(sa_text := __import__("sqlalchemy").text("PRAGMA foreign_keys=ON"))
    connection.execute(__import__("sqlalchemy").text("PRAGMA journal_mode=WAL"))

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # Crucial for SQLite schema alterations
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.begin() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
