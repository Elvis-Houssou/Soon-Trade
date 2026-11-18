import re

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.hardening import production_problems
from app.main import app

# Les seules routes ouvertes sans session. Toute nouvelle route est protégée par défaut :
# si elle doit être publique, elle s'ajoute ici, en connaissance de cause.
PUBLIC = {
    ("GET", "/health"),
    ("GET", "/health/ready"),
    ("POST", "/auth/login"),
    ("POST", "/auth/logout"),
    ("POST", "/auth/password/forgot"),
    ("POST", "/auth/password/reset"),
    ("GET", "/invitations/{token}"),
    ("POST", "/invitations/{token}/accept"),
}
ZERO = "00000000-0000-7000-8000-000000000000"


def _concrete(path: str) -> str:
    """Remplace chaque paramètre par une valeur plausible (identifiant ou action connue)."""
    return re.sub(r"\{[^}]+\}", ZERO, path)


def _protected_routes() -> list[tuple[str, str]]:
    """Inventaire tiré du schéma OpenAPI : il liste toutes les routes de tous les modules."""
    return [
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
        if (method.upper(), path) not in PUBLIC
    ]


@pytest.mark.parametrize(("method", "path"), _protected_routes())
def test_every_route_refuses_an_anonymous_visitor(db, method, path):
    response = TestClient(app).request(method, _concrete(path), json={})
    # L'authentification passe avant tout : même un chemin factice répond 401, jamais 2xx ni 404.
    assert response.status_code == 401, (method, path, response.status_code)


def test_inventory_is_not_empty():
    assert len(_protected_routes()) > 80


def test_security_headers_on_every_response(db):
    response = TestClient(app).get("/health")
    headers = response.headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "no-referrer"
    assert headers["cache-control"] == "no-store"
    assert "default-src 'none'" in headers["content-security-policy"]
    assert len(headers["x-request-id"]) == 32
    # HSTS seulement derrière https (préproduction et production).
    assert "strict-transport-security" not in headers
    assert TestClient(app).get("/health", headers={"x-request-id": "abc"}).headers["x-request-id"] == "abc"


def test_production_refuses_dangerous_settings():
    unsafe = Settings(
        environment="production",
        frontend_url="http://soontrade.test",
        cors_origins=["*"],
        database_url="postgresql+psycopg://u:p@127.0.0.1:5432/db",
        resend_api_key=None,
        s3_endpoint_url="http://127.0.0.1:9090",
        seed_password="demo-password",  # noqa: S106 - valeur de test
    )
    problems = production_problems(unsafe)
    assert len(problems) == 7
    safe = Settings(
        environment="production",
        frontend_url="https://app.soontrade.com",
        cors_origins=["https://app.soontrade.com"],
        database_url="postgresql+psycopg://u:p@db.example.net:5432/db",
        resend_api_key="re_test",
        s3_endpoint_url=None,
        s3_access_key_id="AKIA-test",
        s3_secret_access_key="secret-test",  # noqa: S106 - valeur de test
        seed_password=None,
    )
    assert production_problems(safe) == []
    assert production_problems(Settings(environment="local")) == []
