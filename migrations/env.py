import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import get_settings
from app.database import Base

# Import all models for autogenerate
from app.modules.auth.models import EmailVerificationToken, PasswordResetToken, User  # noqa: F401
from app.modules.collateral.models import CollateralType  # noqa: F401
from app.modules.invites.models import Invitation  # noqa: F401
from app.modules.audit.models import AuditLog  # noqa: F401
from app.modules.results.models import EadResult, LgdResult, OutputArtifact, PdResult  # noqa: F401
from app.modules.runs.models import Run, Upload  # noqa: F401
from app.modules.segments.models import Segment  # noqa: F401
from app.modules.sessions.models import RefreshToken, Session  # noqa: F401
from app.modules.tenants.models import Tenant, TenantMembership  # noqa: F401
from app.modules.platform.models import EngineVersion, ImpersonationSession  # noqa: F401
from app.modules.settings.models import NotificationPreferences  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
