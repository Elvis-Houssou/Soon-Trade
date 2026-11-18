import os
import re
from collections.abc import Callable, Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import Settings

# Les tests tournent dans leur propre base : ils ne voient ni ne modifient jamais les
# données de développement. Défini avant tout import de l'application.
_dev_url = make_url(Settings().database_url)
TEST_DATABASE = f"{_dev_url.database}_test"
os.environ["DATABASE_URL"] = _dev_url.set(database=TEST_DATABASE).render_as_string(hide_password=False)
os.environ["ENVIRONMENT"] = "test"
os.environ["RESEND_API_KEY"] = ""

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from alembic import command  # noqa: E402
from app.core.db import get_engine, get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.identity import service  # noqa: E402
from app.modules.identity.models import Membership, Organization, User  # noqa: E402
from app.modules.identity.security import hash_password  # noqa: E402

PASSWORD = "mot-de-passe-solide"
# Un seul hachage Argon2 pour toute la suite : c'est l'opération la plus lente.
_PASSWORD_HASH = hash_password(PASSWORD)


@pytest.fixture(scope="session")
def _schema() -> None:
    try:
        admin = create_engine(_dev_url, isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 5})
        with admin.connect() as connection:
            exists = connection.scalar(
                text("select 1 from pg_database where datname = :n"), {"n": TEST_DATABASE}
            )
            if not exists:
                connection.execute(text(f'create database "{TEST_DATABASE}"'))
        admin.dispose()
    except OperationalError:
        pytest.skip("PostgreSQL injoignable : lancer `pnpm db:up`")
    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture
def db(_schema: None) -> Iterator[Session]:
    """Session dans une transaction annulée en fin de test : la base reste intacte."""
    connection = get_engine().connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    app.dependency_overrides[get_session] = lambda: session
    yield session
    app.dependency_overrides.clear()
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def emails(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Capture (destinataire, texte) au lieu d'envoyer."""
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(service, "send_email", lambda to, subject, text: sent.append((to, text)))
    return sent


def token_in(text: str) -> str:
    match = re.search(r"/(?:invitation|mot-de-passe)/([\w-]+)", text)
    assert match, text
    return match.group(1)


@pytest.fixture
def make_user(db: Session) -> Callable[..., User]:
    def _make(email: str, role: str, organization: Organization, *, active: bool = True) -> User:
        user = User(email=email, full_name="Test", password_hash=_PASSWORD_HASH, is_active=active)
        db.add(user)
        db.flush()
        db.add(Membership(user_id=user.id, organization_id=organization.id, role=role))
        db.flush()
        return user

    return _make


@pytest.fixture
def make_org(db: Session) -> Callable[..., Organization]:
    def _make(name: str, kind: str) -> Organization:
        organization = Organization(name=name, kind=kind)
        db.add(organization)
        db.flush()
        return organization

    return _make


@pytest.fixture
def login(db: Session) -> Callable[[str], TestClient]:
    """Un client HTTP par acteur, avec son propre cookie de session."""

    def _login(email: str) -> TestClient:
        client = TestClient(app)
        response = client.post("/auth/login", json={"email": email, "password": PASSWORD})
        assert response.status_code == 200, response.text
        return client

    return _login


@pytest.fixture
def world(make_org, make_user):
    """Une organisation interne, deux acheteurs concurrents et un fournisseur."""
    internal = make_org("SOON TRADE", "internal")
    buyer_a = make_org("Acheteur A", "buyer")
    buyer_b = make_org("Acheteur B", "buyer")
    supplier = make_org("Fournisseur", "supplier")
    make_user("admin@st.example.com", "admin", internal)
    make_user("sales@st.example.com", "sales_agent", internal)
    make_user("sourcing@st.example.com", "sourcing_agent", internal)
    make_user("auditor@st.example.com", "auditor", internal)
    make_user("owner@a.example.com", "buyer_owner", buyer_a)
    make_user("member@a.example.com", "buyer_member", buyer_a)
    make_user("owner@b.example.com", "buyer_owner", buyer_b)
    make_user("owner@f.example.com", "supplier_owner", supplier)
    make_user("member@f.example.com", "supplier_member", supplier)
    other_supplier = make_org("Fournisseur concurrent", "supplier")
    make_user("owner@g.example.com", "supplier_owner", other_supplier)
    return {
        "internal": internal,
        "buyer_a": buyer_a,
        "buyer_b": buyer_b,
        "supplier": supplier,
        "other_supplier": other_supplier,
    }
