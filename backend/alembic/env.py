from sqlalchemy import create_engine, pool

from alembic import context
from app.core.config import get_settings
from app.core.db import Base

# Chaque module importe ici ses modèles pour que l'autogénération les voie.
from app.modules.audit import models as _audit  # noqa: F401
from app.modules.catalog import models as _catalog  # noqa: F401
from app.modules.claims import models as _claims  # noqa: F401
from app.modules.crm import models as _crm  # noqa: F401
from app.modules.documents import models as _documents  # noqa: F401
from app.modules.identity import models as _identity  # noqa: F401
from app.modules.messaging import models as _messaging  # noqa: F401
from app.modules.notifications import models as _notifications  # noqa: F401
from app.modules.orders import models as _orders  # noqa: F401
from app.modules.proposals import models as _proposals  # noqa: F401
from app.modules.purchase_requests import models as _purchase_requests  # noqa: F401
from app.modules.solicitations import models as _solicitations  # noqa: F401
from app.modules.sourcing import models as _sourcing  # noqa: F401

target_metadata = Base.metadata
database_url = get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(database_url, poolclass=pool.NullPool, connect_args={"connect_timeout": 5})
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
