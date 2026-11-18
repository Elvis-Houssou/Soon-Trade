import json
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.modules.notifications import service as notification_service
from app.modules.proposals import service as proposal_service
from tests.test_solicitations_offers import NEED, OFFER, _solicit

SALES, ADMIN = "sales@st.example.com", "admin@st.example.com"
OWNER, MEMBER = "owner@a.example.com", "member@a.example.com"


@pytest.fixture
def emails(monkeypatch):
    sent: list[tuple[str, str]] = []
    capture = lambda to, subject, text: sent.append((to, text))  # noqa: E731
    monkeypatch.setattr(notification_service, "send_email", capture)
    return sent


@pytest.fixture
def case(world, login, db, emails):
    """Dossier dont l'offre du fournisseur a été retenue (350 000 FCFA la tonne, 40 t)."""
    world["supplier"].verification_status = "verified"
    db.flush()
    buyer, sourcing = login(OWNER), login("sourcing@st.example.com")
    rid = buyer.post("/purchase-requests", json=NEED).json()["id"]
    buyer.post(f"/purchase-requests/{rid}/submit")
    sourcing.post(f"/internal/purchase-requests/{rid}/qualify")
    case = sourcing.post("/sourcing/cases", json={"request_id": rid}).json()
    sourcing.post(
        f"/sourcing/cases/{case['id']}/candidates", json={"organization_id": str(world["supplier"].id)}
    )
    solicitation = _solicit(login, case, world["supplier"])
    offer = login("owner@f.example.com").post(f"/solicitations/{solicitation['id']}/offer", json=OFFER).json()
    for action in ("review", "retain"):
        response = sourcing.post(f"/sourcing/offers/{offer['offer']['id']}/{action}")
        assert response.status_code == 200, response.text
    return {**case, "request_id": rid, "offer_id": offer["offer"]["id"]}


def _content(proposal, **changes):
    """Contenu complet de la version courante, avec une marge de 10 %, à renvoyer en PUT."""
    current = proposal["versions"][-1]
    body = {
        "lead_time_days": current["lead_time_days"],
        "valid_until": current["valid_until"],
        "delivery_location": current["delivery_location"],
        "conditions": "Paiement à la commande.",
        "message": "Voici notre proposition.",
        "lines": [
            {
                "product_name": line["product_name"],
                "quantity": line["quantity"],
                "unit": line["unit"],
                "unit_price": "385000",
                "offer_id": line["offer_id"],
            }
            for line in current["lines"]
        ],
    }
    return {**body, **changes}


def _sent(login, case):
    """Proposition préparée par le commercial, validée et envoyée par l'administrateur."""
    sales = login(SALES)
    proposal = sales.post(f"/sourcing/cases/{case['id']}/proposal").json()
    proposal = sales.put(f"/internal/proposals/{proposal['id']}", json=_content(proposal)).json()
    assert sales.post(f"/internal/proposals/{proposal['id']}/submit").status_code == 200
    response = login(ADMIN).post(f"/internal/proposals/{proposal['id']}/validation/send")
    assert response.status_code == 200, response.text
    return response.json()


def test_full_cycle_from_retained_offer_to_accepted_version(world, login, case, emails):
    sales, admin, buyer = login(SALES), login(ADMIN), login(OWNER)

    response = sales.post(f"/sourcing/cases/{case['id']}/proposal")
    assert response.status_code == 201, response.text
    draft = response.json()
    line = draft["versions"][0]["lines"][0]
    # Prérempli au prix fournisseur : la marge reste à fixer.
    assert (line["product_name"], Decimal(line["unit_price"]), line["supplier_name"]) == (
        "Riz blanc",
        Decimal("350000"),
        "Fournisseur",
    )
    assert Decimal(draft["versions"][0]["margin"]) == 0
    assert sales.post(f"/sourcing/cases/{case['id']}/proposal").status_code == 409

    # Rien n'est visible de l'acheteur avant l'envoi.
    assert buyer.get("/proposals").json() == []
    assert buyer.get(f"/proposals/{draft['id']}").status_code == 404

    updated = sales.put(f"/internal/proposals/{draft['id']}", json=_content(draft)).json()
    assert updated["versions"][0]["total"] == "15400000.00"
    assert updated["versions"][0]["margin"] == "1400000.00"

    assert sales.post(f"/internal/proposals/{draft['id']}/submit").json()["status"] == "pending_validation"
    # Quatre yeux : celui qui a soumis ne valide pas.
    assert sales.post(f"/internal/proposals/{draft['id']}/validation/send").status_code == 403
    assert sales.put(f"/internal/proposals/{draft['id']}", json=_content(draft)).status_code == 409
    sent = admin.post(f"/internal/proposals/{draft['id']}/validation/send").json()
    assert sent["status"] == "sent"
    assert buyer.get(f"/purchase-requests/{case['request_id']}").json()["status"] == "proposal_sent"

    # E-mail sans prix ni contenu, à chaque membre actif de l'acheteur.
    to_buyer = [text for to, text in emails if to.endswith("@a.example.com")]
    assert len(to_buyer) == 2 and all("385" not in text and "Riz" not in text for text in to_buyer)

    mine = buyer.get(f"/proposals/{draft['id']}").json()
    assert mine["status"] == "sent" and mine["versions"][0]["total"] == "15400000.00"

    # Modification demandée : la demande repasse en sourcing, l'acheteur garde la version 1.
    assert buyer.post(f"/proposals/{draft['id']}/request_changes", json={}).status_code == 400
    response = buyer.post(
        f"/proposals/{draft['id']}/request_changes", json={"message": "Livraison en 2 fois"}
    )
    assert response.json()["status"] == "changes_requested"
    assert buyer.get(f"/purchase-requests/{case['request_id']}").json()["status"] == "in_sourcing"

    revised = sales.post(f"/internal/proposals/{draft['id']}/revise").json()
    assert revised["status"] == "draft" and [v["version"] for v in revised["versions"]] == [1, 2]
    assert buyer.get(f"/proposals/{draft['id']}").json()["status"] == "changes_requested"
    assert len(buyer.get(f"/proposals/{draft['id']}").json()["versions"]) == 1

    sales.put(
        f"/internal/proposals/{draft['id']}", json=_content(revised, conditions="Livraison en deux fois.")
    )
    sales.post(f"/internal/proposals/{draft['id']}/submit")
    admin.post(f"/internal/proposals/{draft['id']}/validation/send")

    mine = buyer.get(f"/proposals/{draft['id']}").json()
    assert [v["version"] for v in mine["versions"]] == [1, 2]
    assert mine["versions"][1]["conditions"] == "Livraison en deux fois."
    accepted = buyer.post(f"/proposals/{draft['id']}/accept").json()
    assert (accepted["status"], accepted["accepted_version"]) == ("accepted", 2)
    assert buyer.get(f"/purchase-requests/{case['request_id']}").json()["status"] == "accepted"

    # Figée : plus aucune décision ni modification.
    assert buyer.post(f"/proposals/{draft['id']}/refuse").status_code == 409
    assert sales.post(f"/internal/proposals/{draft['id']}/revise").status_code == 409
    assert sales.put(f"/internal/proposals/{draft['id']}", json=_content(revised)).status_code == 409


def test_buyer_never_sees_supplier_cost_or_internal_messages(world, login, case):
    sales, admin = login(SALES), login(ADMIN)
    proposal = sales.post(f"/sourcing/cases/{case['id']}/proposal").json()
    sales.put(f"/internal/proposals/{proposal['id']}", json=_content(proposal))
    sales.post(f"/internal/proposals/{proposal['id']}/submit")
    admin.post(
        f"/internal/proposals/{proposal['id']}/validation/return",
        json={"message": "Marge trop basse, ALERTE"},
    )
    sales.post(f"/internal/proposals/{proposal['id']}/submit")
    admin.post(f"/internal/proposals/{proposal['id']}/validation/send")

    for email in (OWNER, MEMBER):
        raw = login(email).get(f"/proposals/{proposal['id']}").text
        for secret in ("Fournisseur", "350000", "ALERTE", "margin", "offer", "supplier", "Admin", "Sales"):
            assert secret not in raw, secret
        body = json.loads(raw)
        assert [e["to_status"] for e in body["history"]] == ["sent"]


def test_isolation_and_permissions(world, login, case):
    proposal = _sent(login, case)
    other_buyer = login("owner@b.example.com")
    assert other_buyer.get("/proposals").json() == []
    assert other_buyer.get(f"/proposals/{proposal['id']}").status_code == 404
    assert other_buyer.post(f"/proposals/{proposal['id']}/accept").status_code == 404

    # Le membre lit mais n'engage pas l'organisation.
    member = login(MEMBER)
    assert member.get(f"/proposals/{proposal['id']}").status_code == 200
    assert member.post(f"/proposals/{proposal['id']}/accept").status_code == 403

    supplier = login("owner@f.example.com")
    assert supplier.get("/proposals").status_code == 403
    assert supplier.get(f"/internal/proposals/{proposal['id']}").status_code == 403

    sourcing = login("sourcing@st.example.com")
    assert sourcing.get(f"/internal/proposals/{proposal['id']}").status_code == 200
    assert sourcing.post(f"/internal/proposals/{proposal['id']}/validation/return").status_code == 403
    assert login("auditor@st.example.com").get("/internal/proposals").status_code == 200
    assert login(OWNER).get("/internal/proposals").status_code == 403


def test_validity_cannot_exceed_source_offers(login, case):
    sales = login(SALES)
    proposal = sales.post(f"/sourcing/cases/{case['id']}/proposal").json()
    # L'offre est valable 10 jours : la proposition est bornée d'office à 7.
    assert proposal["versions"][0]["valid_until"] == (date.today() + timedelta(days=7)).isoformat()
    too_long = (date.today() + timedelta(days=20)).isoformat()
    sales.put(f"/internal/proposals/{proposal['id']}", json=_content(proposal, valid_until=too_long))
    response = sales.post(f"/internal/proposals/{proposal['id']}/submit")
    assert response.status_code == 400 and "validité" in response.json()["error"]["message"]


def test_lines_only_rely_on_retained_offers_of_the_case(login, case):
    sales = login(SALES)
    proposal = sales.post(f"/sourcing/cases/{case['id']}/proposal").json()
    body = _content(proposal)
    body["lines"].append(
        {
            "product_name": "Transport",
            "quantity": "1",
            "unit": "unite",
            "unit_price": "250000",
            "offer_id": None,
        }
    )
    updated = sales.put(f"/internal/proposals/{proposal['id']}", json=body).json()
    assert updated["versions"][0]["total"] == "15650000.00"

    body["lines"][0]["offer_id"] = "00000000-0000-7000-8000-000000000000"
    assert sales.put(f"/internal/proposals/{proposal['id']}", json=body).status_code == 400


def test_refusal_closes_the_request(login, case):
    proposal = _sent(login, case)
    buyer = login(OWNER)
    refused = buyer.post(f"/proposals/{proposal['id']}/refuse", json={"message": "Trop cher"}).json()
    assert refused["status"] == "refused"
    assert refused["history"][-1]["message"] == "Trop cher"
    assert buyer.get(f"/purchase-requests/{case['request_id']}").json()["status"] == "closed"


def test_expired_proposal_cannot_be_accepted_but_can_be_revised(login, case, db):
    proposal = _sent(login, case)
    stored = proposal_service.get(db, proposal["id"])
    stored.current.valid_until = date.today() - timedelta(days=1)
    db.flush()

    buyer = login(OWNER)
    assert buyer.get(f"/proposals/{proposal['id']}").json()["status"] == "expired"
    assert buyer.post(f"/proposals/{proposal['id']}/accept").status_code == 409

    revised = login(SALES).post(f"/internal/proposals/{proposal['id']}/revise").json()
    assert revised["status"] == "draft"
    assert revised["versions"][-1]["valid_until"] == date.today().isoformat()
    assert buyer.get(f"/purchase-requests/{case['request_id']}").json()["status"] == "in_sourcing"


def test_cancelled_draft_frees_the_case(login, case):
    sales = login(SALES)
    first = sales.post(f"/sourcing/cases/{case['id']}/proposal").json()
    assert sales.post(f"/internal/proposals/{first['id']}/cancel").json()["status"] == "cancelled"
    assert sales.post(f"/sourcing/cases/{case['id']}/proposal").status_code == 201


def test_no_proposal_without_a_retained_offer(world, login, db, emails):
    world["supplier"].verification_status = "verified"
    db.flush()
    buyer, sourcing = login(OWNER), login("sourcing@st.example.com")
    rid = buyer.post("/purchase-requests", json=NEED).json()["id"]
    buyer.post(f"/purchase-requests/{rid}/submit")
    sourcing.post(f"/internal/purchase-requests/{rid}/qualify")
    case = sourcing.post("/sourcing/cases", json={"request_id": rid}).json()
    response = login(SALES).post(f"/sourcing/cases/{case['id']}/proposal")
    assert response.status_code == 400
