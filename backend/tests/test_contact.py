import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import app
from app.modules.contact import service
from app.modules.contact.models import ContactRequest

FORM = {
    "profile": "supplier",
    "name": "Awa Koné",
    "company": "Coopérative du Nord",
    "email": "awa@coop.example.com",
    "phone": "+225 01 02 03 04",
    "message": "Nous produisons 200 tonnes d'igname par an et cherchons des acheteurs.",
}


@pytest.fixture
def mails(monkeypatch):
    sent: list[tuple[str, str, str | None]] = []
    monkeypatch.setattr(
        service, "send_email", lambda to, subject, text, reply_to=None: sent.append((to, text, reply_to))
    )
    return sent


def _count(db):
    return db.scalar(select(func.count()).select_from(ContactRequest))


def test_a_supplier_message_reaches_the_sourcing_team(world, db, login, mails):
    response = TestClient(app).post("/contact", json=FORM)
    assert response.status_code == 204, response.text
    assert _count(db) == 1
    recipients = {to for to, _, _ in mails}
    # Le sourcing crée les comptes fournisseurs ; les ventes ne sont pas dérangées.
    assert {"sourcing@st.example.com", "admin@st.example.com"} <= recipients
    assert "sales@st.example.com" not in recipients
    assert all(reply == FORM["email"] and "igname" in text for _, text, reply in mails)
    kinds = [n["kind"] for n in login("sourcing@st.example.com").get("/notifications").json()["items"]]
    assert "contact_received" in kinds


def test_a_buyer_message_reaches_sales(world, mails):
    TestClient(app).post("/contact", json=FORM | {"profile": "buyer"})
    recipients = {to for to, _, _ in mails}
    assert "sales@st.example.com" in recipients and "sourcing@st.example.com" not in recipients


def test_the_honeypot_drops_robots_silently(world, db, mails):
    assert TestClient(app).post("/contact", json=FORM | {"website": "spam.example"}).status_code == 204
    assert _count(db) == 0 and mails == []


def test_messages_are_limited_per_address(world, mails):
    client = TestClient(app)
    for _ in range(service.MAX_PER_HOUR):
        assert client.post("/contact", json=FORM).status_code == 204
    assert client.post("/contact", json=FORM).status_code == 429


def test_an_empty_message_is_refused(world, db):
    assert TestClient(app).post("/contact", json=FORM | {"message": "Bonjour"}).status_code == 422
    assert _count(db) == 0
