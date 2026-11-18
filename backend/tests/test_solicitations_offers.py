import re
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.modules.audit.models import AuditLog
from app.modules.documents.models import Document
from app.modules.notifications import service as notification_service
from app.modules.solicitations import models as solicitation_models

NEED = {
    "product_name": "Riz blanc",
    "quantity": "40",
    "unit": "tonne",
    "delivery_location": "Abidjan",
    "additional_info": "Pour la cantine de la société Acheteur A",
}
IN_TEN_DAYS = (date.today() + timedelta(days=10)).isoformat()
OFFER = {"unit_price": "350000", "quantity": "40", "lead_time_days": 12, "valid_until": IN_TEN_DAYS}


@pytest.fixture
def sent_emails(monkeypatch):
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(notification_service, "send_email", lambda to, subject, text: sent.append((to, text)))
    return sent


@pytest.fixture
def case(world, login, db):
    """Dossier ouvert, les deux fournisseurs vérifiés et présélectionnés."""
    for supplier in (world["supplier"], world["other_supplier"]):
        supplier.verification_status = "verified"
    db.flush()
    buyer, sourcing = login("owner@a.example.com"), login("sourcing@st.example.com")
    rid = buyer.post("/purchase-requests", json=NEED).json()["id"]
    buyer.post(f"/purchase-requests/{rid}/submit")
    sourcing.post(f"/internal/purchase-requests/{rid}/qualify")
    case = sourcing.post("/sourcing/cases", json={"request_id": rid}).json()
    for supplier in (world["supplier"], world["other_supplier"]):
        response = sourcing.post(
            f"/sourcing/cases/{case['id']}/candidates", json={"organization_id": str(supplier.id)}
        )
        assert response.status_code == 201, response.text
    return case


def _solicit(login, case, supplier, *, send=True):
    sourcing = login("sourcing@st.example.com")
    response = sourcing.post(
        f"/sourcing/cases/{case['id']}/solicitations", json={"organization_id": str(supplier.id)}
    )
    assert response.status_code == 201, response.text
    solicitation = response.json()
    if send:
        response = sourcing.post(f"/sourcing/solicitations/{solicitation['id']}/send")
        assert response.status_code == 200, response.text
        solicitation = response.json()
    return solicitation


@pytest.fixture
def solicitation(world, login, case, sent_emails):
    return _solicit(login, case, world["supplier"])


@pytest.fixture
def offer(login, solicitation):
    response = login("owner@f.example.com").post(f"/solicitations/{solicitation['id']}/offer", json=OFFER)
    assert response.status_code == 201, response.text
    return response.json()["offer"]


# --- Préparation et envoi -------------------------------------------------------


def test_internal_prepares_edits_and_sends_a_solicitation(world, login, case, sent_emails, db):
    sourcing = login("sourcing@st.example.com")
    draft = _solicit(login, case, world["supplier"], send=False)
    assert re.fullmatch(r"ST-SOL-\d{4}-\d{4,}", draft["reference"])
    assert draft["status"] == "draft" and draft["product_name"] == "Riz blanc"
    assert draft["supplier_name"] == "Fournisseur" and draft["case_reference"] == case["reference"]
    # Les informations libres de l'acheteur ne sont pas recopiées : elles peuvent le désigner.
    assert "cantine" not in str(draft) and "Acheteur A" not in str(draft)

    edited = sourcing.patch(
        f"/sourcing/solicitations/{draft['id']}",
        json={"delivery_location": "Zone portuaire d'Abidjan", "message": "Prix rendu Abidjan svp"},
    )
    assert edited.status_code == 200 and edited.json()["delivery_location"] == "Zone portuaire d'Abidjan"
    assert sent_emails == []

    sent = sourcing.post(f"/sourcing/solicitations/{draft['id']}/send").json()
    assert sent["status"] == "sent" and sent["sent_at"]
    assert {to for to, _ in sent_emails} == {"owner@f.example.com", "member@f.example.com"}
    # L'e-mail ne dit rien du besoin : il renvoie vers l'espace sécurisé.
    assert all("Riz" not in text and "Abidjan" not in text for _, text in sent_emails)
    assert sourcing.patch(f"/sourcing/solicitations/{draft['id']}", json={"message": "x"}).status_code == 409
    assert sourcing.post(f"/sourcing/solicitations/{draft['id']}/send").status_code == 409
    assert db.scalar(select(AuditLog).where(AuditLog.action == "solicitation.sent"))


def test_who_can_be_solicited(world, login, case, make_org, db):
    sourcing = login("sourcing@st.example.com")
    path = f"/sourcing/cases/{case['id']}/solicitations"
    outsider = make_org("Non présélectionné", "supplier")
    outsider.verification_status = "verified"
    db.flush()
    assert sourcing.post(path, json={"organization_id": str(outsider.id)}).status_code == 400
    assert sourcing.post(path, json={"organization_id": str(world["buyer_b"].id)}).status_code == 400

    _solicit(login, case, world["supplier"], send=False)
    assert sourcing.post(path, json={"organization_id": str(world["supplier"].id)}).status_code == 409

    # Un fournisseur suspendu après sa présélection ne reçoit plus rien.
    draft = _solicit(login, case, world["other_supplier"], send=False)
    world["other_supplier"].verification_status = "suspended"
    db.flush()
    assert sourcing.post(f"/sourcing/solicitations/{draft['id']}/send").status_code == 400


def test_drafts_stay_internal(world, login, case):
    draft = _solicit(login, case, world["supplier"], send=False)
    supplier = login("owner@f.example.com")
    assert supplier.get("/solicitations").json() == []
    assert supplier.get(f"/solicitations/{draft['id']}").status_code == 404
    assert supplier.post(f"/solicitations/{draft['id']}/offer", json=OFFER).status_code == 404


# --- Réponse du fournisseur -----------------------------------------------------


def test_supplier_opens_answers_and_revises(world, login, solicitation, db):
    supplier = login("member@f.example.com")
    (listed,) = supplier.get("/solicitations").json()
    assert listed["status"] == "sent"
    opened = supplier.get(f"/solicitations/{solicitation['id']}").json()
    assert opened["status"] == "viewed"

    document = Document(
        organization_id=world["supplier"].id,
        uploaded_by_id=db.scalar(select(AuditLog.actor_id).where(AuditLog.action == "solicitation.viewed")),
        doc_type="offer_attachment",
        filename="fiche-riz.pdf",
        content_type="application/pdf",
        size_bytes=10,
        storage_key="cle-fiche-riz",
    )
    db.add(document)
    db.flush()
    answered = supplier.post(
        f"/solicitations/{solicitation['id']}/offer", json={**OFFER, "attachment_ids": [str(document.id)]}
    )
    assert answered.status_code == 201, answered.text
    body = answered.json()
    assert body["status"] == "answered"
    offer = body["offer"]
    assert re.fullmatch(r"ST-OFF-\d{4}-\d{4,}", offer["reference"]) and offer["status"] == "submitted"
    (first,) = offer["versions"]
    assert Decimal(first["total"]) == Decimal("14000000") and first["currency"] == "XOF"
    assert first["attachments"] == [{"id": str(document.id), "filename": "fiche-riz.pdf"}]
    assert supplier.post(f"/solicitations/{solicitation['id']}/offer", json=OFFER).status_code == 409

    revised = supplier.put(
        f"/solicitations/{solicitation['id']}/offer", json={**OFFER, "unit_price": "340000"}
    )
    versions = revised.json()["offer"]["versions"]
    assert [Decimal(v["unit_price"]) for v in versions] == [Decimal(350000), Decimal(340000)]
    assert versions[1]["attachments"] == []

    internal = (
        login("sales@st.example.com").get(f"/sourcing/cases/{solicitation['case_id']}/solicitations").json()
    )
    assert len(internal[0]["offer"]["versions"]) == 2 and internal[0]["viewed_at"]


@pytest.mark.parametrize(
    "bad",
    [
        {"unit_price": "0"},
        {"unit_price": "-5"},
        {"unit_price": "1.234"},
        {"quantity": "0"},
        {"lead_time_days": -1},
        {"currency": "EUR"},
        {"supplier_id": "00000000-0000-0000-0000-000000000000"},
    ],
)
def test_invalid_offers_are_refused(login, solicitation, bad):
    response = login("owner@f.example.com").post(
        f"/solicitations/{solicitation['id']}/offer", json={**OFFER, **bad}
    )
    assert response.status_code == 422


def test_offer_dates_and_attachments_are_checked(world, login, solicitation, db, make_user):
    supplier = login("owner@f.example.com")
    path = f"/solicitations/{solicitation['id']}/offer"
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    assert supplier.post(path, json={**OFFER, "valid_until": yesterday}).status_code == 400
    foreign = Document(
        organization_id=world["other_supplier"].id,
        uploaded_by_id=make_user("x@g.example.com", "supplier_member", world["other_supplier"]).id,
        doc_type="offer_attachment",
        filename="autre.pdf",
        content_type="application/pdf",
        size_bytes=10,
        storage_key="cle-autre",
    )
    db.add(foreign)
    db.flush()
    assert supplier.post(path, json={**OFFER, "attachment_ids": [str(foreign.id)]}).status_code == 404
    assert supplier.get("/solicitations").json()[0]["offer"] is None


def test_withdrawal_and_decline(world, login, case, offer, solicitation, sent_emails):
    supplier = login("owner@f.example.com")
    sid = solicitation["id"]
    assert supplier.post(f"/solicitations/{sid}/decline", json={}).status_code == 409
    withdrawn = supplier.post(f"/solicitations/{sid}/offer/withdraw").json()
    assert withdrawn["offer"]["status"] == "withdrawn"
    assert supplier.post(f"/solicitations/{sid}/offer/withdraw").status_code == 409
    assert supplier.put(f"/solicitations/{sid}/offer", json=OFFER).status_code == 409

    other = _solicit(login, case, world["other_supplier"])
    competitor = login("owner@g.example.com")
    declined = competitor.post(f"/solicitations/{other['id']}/decline", json={"message": "Plus de stock"})
    assert declined.json()["status"] == "declined"
    assert competitor.post(f"/solicitations/{other['id']}/offer", json=OFFER).status_code == 409
    internal = login("sourcing@st.example.com").get(f"/sourcing/cases/{case['id']}/solicitations").json()
    assert internal[1]["decline_reason"] == "Plus de stock"


# --- Arbitrage interne et comparaison ------------------------------------------


def test_review_then_retain_or_reject(world, login, case, offer, solicitation, sent_emails):
    sourcing, supplier = login("sourcing@st.example.com"), login("owner@f.example.com")
    oid = offer["id"]
    # On ne retient pas une offre qui n'est pas en analyse.
    assert sourcing.post(f"/sourcing/offers/{oid}/retain").status_code == 409
    assert sourcing.post(f"/sourcing/offers/{oid}/review").json()["offer"]["status"] == "under_review"
    # En analyse, le fournisseur ne la modifie ni ne la retire plus.
    assert supplier.put(f"/solicitations/{solicitation['id']}/offer", json=OFFER).status_code == 409
    assert supplier.post(f"/solicitations/{solicitation['id']}/offer/withdraw").status_code == 409
    assert sourcing.post(f"/sourcing/offers/{oid}/retain").json()["offer"]["status"] == "retained"
    assert sourcing.post(f"/sourcing/offers/{oid}/reject").status_code == 409
    assert sourcing.post(f"/sourcing/offers/{oid}/promote").status_code == 422
    assert supplier.get(f"/solicitations/{solicitation['id']}").json()["offer"]["status"] == "retained"

    other = _solicit(login, case, world["other_supplier"])
    rival = (
        login("owner@g.example.com").post(f"/solicitations/{other['id']}/offer", json=OFFER).json()["offer"]
    )
    sourcing.post(f"/sourcing/offers/{rival['id']}/review")
    assert sourcing.post(f"/sourcing/offers/{rival['id']}/reject").json()["offer"]["status"] == "not_retained"

    compared = sourcing.get(f"/sourcing/cases/{case['id']}/solicitations").json()
    assert [(s["supplier_name"], s["offer"]["status"]) for s in compared] == [
        ("Fournisseur", "retained"),
        ("Fournisseur concurrent", "not_retained"),
    ]


def test_cancellation_rules(world, login, case, offer, solicitation, sent_emails):
    sourcing = login("sourcing@st.example.com")
    # Une sollicitation à laquelle le fournisseur a répondu ne s'annule plus.
    assert sourcing.post(f"/sourcing/solicitations/{solicitation['id']}/cancel").status_code == 409
    other = _solicit(login, case, world["other_supplier"])
    assert sourcing.post(f"/sourcing/solicitations/{other['id']}/cancel").json()["status"] == "cancelled"
    competitor = login("owner@g.example.com")
    assert competitor.get("/solicitations").json()[0]["status"] == "cancelled"
    assert competitor.post(f"/solicitations/{other['id']}/offer", json=OFFER).status_code == 409


def test_a_cancelled_request_freezes_solicitations_and_offers(world, login, case, offer, sent_emails):
    draft = _solicit(login, case, world["other_supplier"], send=False)
    login("owner@a.example.com").post(f"/purchase-requests/{case['request']['id']}/cancel")
    sourcing = login("sourcing@st.example.com")
    assert sourcing.post(f"/sourcing/solicitations/{draft['id']}/send").status_code == 409
    assert sourcing.post(f"/sourcing/offers/{offer['id']}/review").status_code == 409


def test_deadlines_and_validity_expire(world, login, case, offer, solicitation, sent_emails, monkeypatch):
    other = _solicit(login, case, world["other_supplier"])
    monkeypatch.setattr(solicitation_models, "today", lambda: date.today() + timedelta(days=30))
    competitor = login("owner@g.example.com")
    assert competitor.get(f"/solicitations/{other['id']}").json()["status"] == "expired"
    assert competitor.post(f"/solicitations/{other['id']}/offer", json=OFFER).status_code == 409
    assert competitor.post(f"/solicitations/{other['id']}/decline", json={}).status_code == 409

    # La réponse déjà donnée reste « répondue », mais l'offre a dépassé sa validité.
    mine = login("owner@f.example.com").get(f"/solicitations/{solicitation['id']}").json()
    assert mine["status"] == "answered" and mine["offer"]["status"] == "expired"
    assert login("sourcing@st.example.com").post(f"/sourcing/offers/{offer['id']}/review").status_code == 409


# --- Cloisonnement --------------------------------------------------------------


def test_a_supplier_never_sees_competitors_or_the_buyer(world, login, case, offer, solicitation, sent_emails):
    other = _solicit(login, case, world["other_supplier"])
    login("owner@g.example.com").post(
        f"/solicitations/{other['id']}/offer", json={**OFFER, "unit_price": "1"}
    )
    login("sourcing@st.example.com").post(
        f"/sourcing/cases/{case['id']}/notes", json={"body": "Marge visée 8 %, ne pas divulguer"}
    )

    supplier = login("owner@f.example.com")
    sid = solicitation["id"]
    for response in (supplier.get("/solicitations"), supplier.get(f"/solicitations/{sid}")):
        text = response.text
        assert response.status_code == 200
        for leaked in (
            "Acheteur A",
            "concurrent",
            "Marge",
            "ST-SRC",
            "ST-ACH",
            case["id"],
            other["id"],
            str(world["other_supplier"].id),
            str(world["buyer_a"].id),
            "Test",  # nom du collaborateur interne
        ):
            assert leaked not in text, leaked
        body = response.json()
        mine = body[0] if isinstance(body, list) else body
        assert not {"case_id", "case_reference", "supplier_name", "created_by", "organization_id"} & set(mine)

    # Ni lecture, ni action sur la sollicitation d'un concurrent.
    for method, path, payload in [
        ("get", f"/solicitations/{other['id']}", None),
        ("post", f"/solicitations/{other['id']}/decline", {}),
        ("post", f"/solicitations/{other['id']}/offer", OFFER),
        ("put", f"/solicitations/{other['id']}/offer", OFFER),
        ("post", f"/solicitations/{other['id']}/offer/withdraw", None),
    ]:
        assert (
            getattr(supplier, method)(path, **({"json": payload} if payload is not None else {})).status_code
            == 404
        )


@pytest.mark.parametrize("email", ["owner@f.example.com", "owner@a.example.com"])
def test_clients_have_no_access_to_internal_routes(world, login, case, offer, solicitation, email):
    client = login(email)
    for method, path in [
        ("get", "/sourcing/solicitations"),
        ("get", f"/sourcing/cases/{case['id']}/solicitations"),
        ("post", f"/sourcing/cases/{case['id']}/solicitations"),
        ("patch", f"/sourcing/solicitations/{solicitation['id']}"),
        ("post", f"/sourcing/solicitations/{solicitation['id']}/send"),
        ("post", f"/sourcing/solicitations/{solicitation['id']}/cancel"),
        ("post", f"/sourcing/offers/{offer['id']}/review"),
    ]:
        assert getattr(client, method)(path).status_code == 403, path


def test_buyers_have_no_access_to_solicitations_nor_offers(world, login, case, offer, solicitation):
    buyer = login("owner@a.example.com")
    assert buyer.get("/solicitations").status_code == 403
    assert buyer.get(f"/solicitations/{solicitation['id']}").status_code == 403
    assert buyer.post(f"/solicitations/{solicitation['id']}/offer", json=OFFER).status_code == 403
    request = buyer.get(f"/purchase-requests/{case['request']['id']}").text
    for leaked in ("350000", "ST-SOL", "ST-OFF", "Fournisseur", offer["id"]):
        assert leaked not in request, leaked


@pytest.mark.parametrize(
    ("email", "role", "reads"),
    [
        ("sales@st.example.com", None, 200),
        ("auditor@st.example.com", None, 200),
        ("finance@st.example.com", "finance_agent", 403),
    ],
)
def test_internal_roles_without_the_right_cannot_act(
    world, login, make_user, case, offer, solicitation, email, role, reads
):
    if role:
        make_user(email, role, world["internal"])
    client = login(email)
    assert client.get("/sourcing/solicitations").status_code == reads
    assert client.get(f"/sourcing/cases/{case['id']}/solicitations").status_code == reads
    assert client.post(f"/sourcing/offers/{offer['id']}/review").status_code == 403
    assert client.post(f"/sourcing/solicitations/{solicitation['id']}/cancel").status_code == 403
    response = client.post(
        f"/sourcing/cases/{case['id']}/solicitations",
        json={"organization_id": str(world["other_supplier"].id)},
    )
    assert response.status_code == 403
    # Les rôles internes n'ont pas accès aux routes du fournisseur.
    assert client.get("/solicitations").status_code == 403
