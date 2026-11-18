import string
from datetime import date

import pytest

from app.core import mail
from app.core.email import to_html
from app.modules.notifications import service as notification_service
from tests.test_solicitations_offers import NEED

OWNER, MEMBER, OTHER_BUYER = "owner@a.example.com", "member@a.example.com", "owner@b.example.com"
SALES, AUDITOR, SUPPLIER = "sales@st.example.com", "auditor@st.example.com", "owner@f.example.com"


@pytest.fixture
def sent(monkeypatch):
    captured: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        notification_service, "send_email", lambda to, subject, text: captured.append((to, subject, text))
    )
    return captured


def _kinds(client):
    return [n["kind"] for n in client.get("/notifications").json()["items"]]


def test_a_buyer_talks_only_to_soon_trade(world, login, sent):
    buyer, sales = login(OWNER), login(SALES)
    response = buyer.post(
        "/conversations",
        json={
            "subject": "Délai riz",
            "body": "Pouvez-vous livrer plus tôt ?",
            "context_reference": "ST-ACH-2026-0001",
        },
    )
    assert response.status_code == 201, response.text
    conversation = response.json()
    assert "message_from_client" in _kinds(sales)
    assert _kinds(buyer) == []  # l'auteur n'est pas prévenu de son propre message

    reply = sales.post(
        f"/internal/conversations/{conversation['id']}/messages", json={"body": "Oui, sous 10 jours."}
    )
    assert reply.status_code == 201
    sales.post(
        f"/internal/conversations/{conversation['id']}/messages",
        json={"body": "Note : vérifier le stock du fournisseur", "internal": True},
    )

    mine = buyer.get(f"/conversations/{conversation['id']}").json()
    assert [m["body"] for m in mine["messages"]] == ["Pouvez-vous livrer plus tôt ?", "Oui, sous 10 jours."]
    # L'équipe signe « SOON TRADE » : jamais de nom de collaborateur côté client.
    assert mine["messages"][1]["author_name"] is None and mine["messages"][1]["from_staff"] is True
    assert "Note" not in buyer.get("/conversations").text

    # Prévenus : les deux membres de l'acheteur, par l'application et par e-mail, sans le contenu.
    assert "message_received" in _kinds(buyer) and "message_received" in _kinds(login(MEMBER))
    assert {to for to, _, _ in sent} == {OWNER, MEMBER}
    assert all("10 jours" not in text for _, _, text in sent)

    # Cloisonnement : un autre acheteur et un fournisseur ne voient rien.
    for outsider in (login(OTHER_BUYER), login(SUPPLIER)):
        assert outsider.get("/conversations").json() == []
        assert outsider.get(f"/conversations/{conversation['id']}").status_code == 404
        assert (
            outsider.post(f"/conversations/{conversation['id']}/messages", json={"body": "x"}).status_code
            == 404
        )


def test_unread_close_and_permissions(world, login, sent):
    buyer, sales, auditor = login(OWNER), login(SALES), login(AUDITOR)
    conversation = buyer.post("/conversations", json={"subject": "Question", "body": "Bonjour"}).json()
    assert sales.get("/internal/conversations").json()[0]["unread"] is True
    sales.get(f"/internal/conversations/{conversation['id']}")
    assert sales.get("/internal/conversations").json()[0]["unread"] is False

    assert sales.post(f"/internal/conversations/{conversation['id']}/close").json()["status"] == "closed"
    # Un nouveau message du client rouvre le fil.
    buyer.post(f"/conversations/{conversation['id']}/messages", json={"body": "Encore une question"})
    assert sales.get(f"/internal/conversations/{conversation['id']}").json()["status"] == "open"

    # L'auditeur lit, mais n'écrit pas ; le client n'entre pas dans l'espace interne.
    assert auditor.get(f"/internal/conversations/{conversation['id']}").status_code == 200
    assert (
        auditor.post(f"/internal/conversations/{conversation['id']}/messages", json={"body": "x"}).status_code
        == 403
    )
    assert buyer.get("/internal/conversations").status_code == 403
    assert sales.post("/conversations", json={"subject": "x", "body": "y"}).status_code == 403


def test_staff_can_open_a_conversation_with_a_client_only(world, login, sent):
    sales = login(SALES)
    body = {"subject": "Votre catalogue", "body": "Pouvez-vous mettre à jour vos prix ?"}
    started = sales.post(
        "/internal/conversations", json={**body, "organization_id": str(world["supplier"].id)}
    )
    assert started.status_code == 201 and started.json()["organization_kind"] == "supplier"
    assert login(SUPPLIER).get("/conversations").json()[0]["subject"] == "Votre catalogue"
    # Pas de fil avec une organisation interne.
    assert (
        sales.post(
            "/internal/conversations", json={**body, "organization_id": str(world["internal"].id)}
        ).status_code
        == 404
    )


def test_notifications_are_private_and_can_be_marked_read(world, login, sent):
    buyer, sales = login(OWNER), login(SALES)
    conversation = buyer.post("/conversations", json={"subject": "Question", "body": "Bonjour"}).json()
    sales.post(f"/internal/conversations/{conversation['id']}/messages", json={"body": "Bonjour !"})
    mine = buyer.get("/notifications").json()
    assert mine["unread"] == 1 and mine["items"][0]["link"].startswith("buyer/messages?id=")
    theirs = sales.get("/notifications").json()["items"][0]["id"]
    # Marquer la notification d'un autre ne change rien pour lui.
    buyer.post("/notifications/read", json={"ids": [theirs]})
    assert sales.get("/notifications").json()["unread"] == 1
    assert buyer.post("/notifications/read", json={}).json()["unread"] == 0


def test_emails_follow_each_users_language(world, login, sent):
    buyer, sales = login(OWNER), login(SALES)
    assert buyer.patch("/auth/me", json={"locale": "de"}).json()["locale"] == "de"
    assert buyer.patch("/auth/me", json={"locale": "es"}).status_code == 422
    conversation = buyer.post("/conversations", json={"subject": "Question", "body": "Hallo"}).json()
    sales.post(f"/internal/conversations/{conversation['id']}/messages", json={"body": "Guten Tag"})
    by_recipient = {to: (subject, text) for to, subject, text in sent}
    assert by_recipient[OWNER][0] == "Neue Nachricht von SOON TRADE"
    assert "/de/buyer/messages" in by_recipient[OWNER][1]
    assert by_recipient[MEMBER][0] == "Nouveau message de SOON TRADE"


def test_qualification_steps_notify_the_buyer(world, login, sent):
    buyer, sourcing = login(OWNER), login("sourcing@st.example.com")
    rid = buyer.post("/purchase-requests", json=NEED).json()["id"]
    buyer.post(f"/purchase-requests/{rid}/submit")
    sourcing.post(f"/internal/purchase-requests/{rid}/request-info", json={"message": "Quelle variété ?"})
    assert "request_info_requested" in _kinds(buyer)
    assert any("ST-ACH" in subject for _, subject, _ in sent)
    assert all("variété" not in text for _, _, text in sent)


def test_crm_file_gathers_the_relationship(world, login, sent):
    buyer, sales = login(OWNER), login(SALES)
    buyer.post("/purchase-requests/" + buyer.post("/purchase-requests", json=NEED).json()["id"] + "/submit")
    buyer.post("/conversations", json={"subject": "Délai", "body": "Bonjour"})
    org_id = str(world["buyer_a"].id)
    assert (
        sales.post(
            f"/internal/crm/{org_id}/notes", json={"body": "Client exigeant sur les délais"}
        ).status_code
        == 201
    )

    clients = sales.get("/internal/crm").json()
    first = next(c for c in clients if c["id"] == org_id)
    assert (first["requests"], first["conversations"]) == (1, 1)
    file = sales.get(f"/internal/crm/{org_id}").json()
    assert {e["kind"] for e in file["timeline"]} == {"request", "conversation", "note"}
    assert next(e for e in file["timeline"] if e["kind"] == "note")["author"] == "Test"

    assert login(AUDITOR).get(f"/internal/crm/{org_id}").status_code == 200
    assert login(AUDITOR).post(f"/internal/crm/{org_id}/notes", json={"body": "x"}).status_code == 403
    assert buyer.get("/internal/crm").status_code == 403
    assert sales.get(f"/internal/crm/{world['internal'].id}").status_code == 404
    # La note ne sort jamais de l'espace interne.
    assert "exigeant" not in buyer.get("/conversations").text


def test_every_email_template_exists_in_three_languages_with_the_same_fields():
    for kind, versions in mail.TEMPLATES.items():
        assert set(versions) == set(mail.LOCALES), kind
        fields = {
            locale: {f for part in texts for _, f, _, _ in string.Formatter().parse(part) if f}
            for locale, texts in versions.items()
        }
        assert fields["fr"] == fields["en"] == fields["de"], kind
        values = {f: date(2026, 12, 1) for f in fields["fr"] - {"link"}}
        subject, text = mail.render(kind, "de", link="https://app.test/de/x", **values)
        assert subject and "https://app.test/de/x" in text
    assert mail.render("order_confirmed", "xx", reference="R")[0].startswith("Commande")


def test_html_version_escapes_content_and_links_urls():
    html = to_html("Bonjour <script>\n\nVoir https://app.test/fr/x")
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert '<a href="https://app.test/fr/x"' in html
