from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Base déclarative commune à tous les modèles des modules métier."""


@lru_cache
def get_engine() -> Engine:
    # pool_pre_ping : Neon suspend les connexions inactives, on les revalide à l'emprunt.
    return create_engine(get_settings().database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5})


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """Dépendance FastAPI : une session par requête, fermée en sortie."""
    with _session_factory()() as session:
        yield session
