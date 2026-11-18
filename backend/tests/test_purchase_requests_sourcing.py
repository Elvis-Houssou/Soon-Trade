import re
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.modules.audit.models import AuditLog
from app.modules.catalog.models import Category, Product
from app.modules.purchase_requests.models import PurchaseRequestEvent

RICE = {"product_name": "Riz blanc", "quantity": "25.5", "unit": "tonne", "delivery_location": "Abidjan"}
INTERNAL_KEYS = ("assignee", "candidates", "notes", "actor", "buyer_name", "sourcing", "case")


@pytest.fixture
def draft(world, login):
    response = login("member@a.example.com").post("/purchase-requests", json=RICE)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def submitted(draft, login):
    response = login("owner@a.example.com").post(f"/purchase-requests/{draft['id']}/submit")
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def case(submitted, login):
    """Demande qualifiée, dossier ouvert par l'agent de sourcing."""
    sourcing = login("sourcing@st.example.com")
    assert sourcing.post(f"/internal/purchase-requests/{submitted['id']}/qualify").status_code == 200
    response = sourcing.post("/sourcing/cases", json={"request_id": submitted["id"]})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def verified_supplier(world, db):
    """Le fournisseur est vérifié et vend du riz ; son concurrent, non vérifié, aussi."""
    world["supplier"].verification_status = "verified"
    category = Category(name="Céréales")
    db.add(category)
    db.flush()
    for organization in (world["supplier"], world["other_supplier"]):
        db.add(
            Product(organization_id=organization.id, category_id=category.id, name="Riz long", unit="tonne")
        )
    db.add(
        Product(
            organization_id=world["supplier"].id,
            category_id=category.id,
            name="Riz retiré",
            unit="tonne",
            is_active=False,
        )
    )
    db.flush()
    return category


# --- Acheteur ------------------------------------------------------------------


def test_buyer_creates_edits_and_submits_a_request(world, login, draft, db):
    buyer = login("owner@a.example.com")
    assert re.fullmatch(r"ST-ACH-\d{4}-\d{4,}", draft["reference"])
    assert draft["status"] == "draft" and Decimal(draft["quantity"]) == Decimal("25.5")

    edited = buyer.patch(f"/purchase-requests/{draft['id']}", json={"quantity": "30", "packaging": " Sacs "})
    assert edited.status_code == 200
    assert Decimal(edited.json()["quantity"]) == 30 and edited.json()["packaging"] == "Sacs"

    submitted = buyer.post(f"/purchase-requests/{draft['id']}/submit").json()
    assert submitted["status"] == "submitted"
    assert [e["to_status"] for e in submitted["history"]] == ["draft", "submitted"]
    # Une demande soumise ne se modifie plus.
    assert buyer.patch(f"/purchase-requests/{draft['id']}", json={"quantity": "1"}).status_code == 409
    assert db.scalar(select(AuditLog).where(AuditLog.action == "purchase_request.submit"))


@pytest.mark.parametrize(
    "bad",
    [
        {"quantity": "0"},
        {"quantity": "-3"},
        {"unit": "palette"},
        {"product_name": "R"},
        {"delivery_location": ""},
        {"status": "qualified"},
        {"organization_id": "00000000-0000-0000-0000-000000000000"},
    ],
)
def test_invalid_requests_are_refused(world, login, bad):
    assert login("owner@a.example.com").post("/purchase-requests", json={**RICE, **bad}).status_code == 422


def test_a_buyer_never_sees_or_touches_another_buyer_request(world, login, draft):
    rival = login("owner@b.example.com")
    assert rival.get("/purchase-requests").json() == []
    assert rival.get(f"/purchase-requests/{draft['id']}").status_code == 404
    assert rival.patch(f"/purchase-requests/{draft['id']}", json={"quantity": "1"}).status_code == 404
    assert rival.post(f"/purchase-requests/{draft['id']}/submit").status_code == 404
    assert rival.post(f"/purchase-requests/{draft['id']}/cancel").status_code == 404
    # Un collègue de la même organisation, lui, la voit.
    assert [r["id"] for r in login("owner@a.example.com").get("/purchase-requests").json()] == [draft["id"]]


@pytest.mark.parametrize("email", ["owner@f.example.com", "member@f.example.com"])
def test_suppliers_have_no_access_at_all(world, login, case, email):
    supplier = login(email)
    rid, cid = case["request"]["id"], case["id"]
    for method, path in [
        ("get", "/purchase-requests"),
        ("post", "/purchase-requests"),
        ("get", f"/purchase-requests/{rid}"),
        ("post", f"/purchase-requests/{rid}/cancel"),
        ("get", "/internal/purchase-requests"),
        ("get", f"/internal/purchase-requests/{rid}"),
        ("post", f"/internal/purchase-requests/{rid}/qualify"),
        ("get", "/sourcing/cases"),
        ("get", f"/sourcing/cases/{cid}"),
        ("post", "/sourcing/cases"),
        ("post", f"/sourcing/cases/{cid}/notes"),
        ("post", f"/sourcing/cases/{cid}/candidates"),
        ("get", "/sourcing/suppliers"),
        ("get", "/sourcing/assignees"),
    ]:
        assert getattr(supplier, method)(path).status_code == 403, path


def test_buyers_have_no_access_to_internal_and_sourcing_routes(world, login, case):
    buyer = login("owner@a.example.com")
    for path in (
        "/internal/purchase-requests",
        f"/internal/purchase-requests/{case['request']['id']}",
        "/sourcing/cases",
        f"/sourcing/cases/{case['id']}",
        "/sourcing/suppliers",
    ):
        assert buyer.get(path).status_code == 403, path
    assert buyer.post(f"/internal/purchase-requests/{case['request']['id']}/qualify").status_code == 403


# --- Qualification interne -----------------------------------------------------


def test_info_request_round_trip_then_qualification(world, login, submitted, db):
    sourcing, buyer = login("sourcing@st.example.com"), login("owner@a.example.com")
    rid = submitted["id"]

    assert sourcing.post(f"/internal/purchase-requests/{rid}/request-info", json={}).status_code == 422
    asked = sourcing.post(
        f"/internal/purchase-requests/{rid}/request-info", json={"message": "Quel taux de brisure ?"}
    )
    assert asked.status_code == 200 and asked.json()["status"] == "info_requested"
    assert asked.json()["buyer_name"] == "Acheteur A"

    mine = buyer.get(f"/purchase-requests/{rid}").json()
    assert mine["status"] == "info_requested" and mine["history"][-1]["message"] == "Quel taux de brisure ?"
    # L'acheteur complète sa demande puis répond.
    assert (
        buyer.patch(f"/purchase-requests/{rid}", json={"specifications": "5 % de brisure"}).status_code == 200
    )
    answered = buyer.post(f"/purchase-requests/{rid}/submit", json={"message": "5 %, voir la fiche"})
    assert answered.json()["status"] == "submitted"

    qualified = sourcing.post(f"/internal/purchase-requests/{rid}/qualify").json()
    assert qualified["status"] == "qualified"
    assert qualified["history"][-1]["actor_name"] == "Test"
    assert qualified["history"][-2]["message"] == "5 %, voir la fiche"

    events = db.scalars(select(PurchaseRequestEvent).order_by(PurchaseRequestEvent.id)).all()
    assert [(e.from_status, e.to_status) for e in events] == [
        (None, "draft"),
        ("draft", "submitted"),
        ("submitted", "info_requested"),
        ("info_requested", "submitted"),
        ("submitted", "qualified"),
    ]
    assert all(e.actor_id for e in events)


def test_rejection_needs_a_reason_the_buyer_can_read(world, login, submitted):
    sourcing = login("sourcing@st.example.com")
    rid = submitted["id"]
    assert sourcing.post(f"/internal/purchase-requests/{rid}/reject", json={"message": ""}).status_code == 422
    rejected = sourcing.post(f"/internal/purchase-requests/{rid}/reject", json={"message": "Hors périmètre"})
    assert rejected.json()["status"] == "rejected"
    mine = login("owner@a.example.com").get(f"/purchase-requests/{rid}").json()
    assert mine["status"] == "rejected" and mine["history"][-1]["message"] == "Hors périmètre"


def test_invalid_transitions_answer_409(world, login, draft):
    buyer, sourcing = login("owner@a.example.com"), login("sourcing@st.example.com")
    rid = draft["id"]
    # Un brouillon n'existe pas pour l'équipe interne.
    assert sourcing.get(f"/internal/purchase-requests/{rid}").status_code == 404
    assert sourcing.post(f"/internal/purchase-requests/{rid}/qualify").status_code == 404
    assert sourcing.get("/internal/purchase-requests").json() == []

    buyer.post(f"/purchase-requests/{rid}/submit")
    assert buyer.post(f"/purchase-requests/{rid}/submit").status_code == 409
    # Pas de dossier de sourcing sans qualification.
    assert sourcing.post("/sourcing/cases", json={"request_id": rid}).status_code == 409

    sourcing.post(f"/internal/purchase-requests/{rid}/qualify")
    for action, body in (
        ("qualify", None),
        ("reject", {"message": "trop tard"}),
        ("request-info", {"message": "?!?"}),
    ):
        assert sourcing.post(f"/internal/purchase-requests/{rid}/{action}", json=body).status_code == 409

    assert buyer.post(f"/purchase-requests/{rid}/cancel").json()["status"] == "cancelled"
    assert buyer.post(f"/purchase-requests/{rid}/cancel").status_code == 409
    assert buyer.post(f"/purchase-requests/{rid}/submit").status_code == 409
    assert sourcing.post("/sourcing/cases", json={"request_id": rid}).status_code == 409


@pytest.mark.parametrize(
    ("email", "role", "reads", "reads_sourcing"),
    [
        ("sales@st.example.com", None, 200, 200),
        ("auditor@st.example.com", None, 200, 200),
        ("finance@st.example.com", "finance_agent", 200, 403),
        ("support@st.example.com", "support_agent", 200, 403),
    ],
)
def test_internal_roles_without_the_right_cannot_act(
    world, login, make_user, case, verified_supplier, email, role, reads, reads_sourcing
):
    if role:
        make_user(email, role, world["internal"])
    client = login(email)
    rid, cid = case["request"]["id"], case["id"]
    assert client.get("/internal/purchase-requests").status_code == reads
    assert client.get("/sourcing/cases").status_code == reads_sourcing
    assert client.get("/sourcing/suppliers").status_code == reads_sourcing
    # Aucun de ces rôles ne qualifie ni ne modifie un dossier.
    assert client.post(f"/internal/purchase-requests/{rid}/qualify").status_code == 403
    assert (
        client.post(f"/internal/purchase-requests/{rid}/reject", json={"message": "non"}).status_code == 403
    )
    assert client.post("/sourcing/cases", json={"request_id": rid}).status_code == 403
    assert client.post(f"/sourcing/cases/{cid}/notes", json={"body": "x"}).status_code == 403
    assert (
        client.post(
            f"/sourcing/cases/{cid}/candidates", json={"organization_id": str(world["supplier"].id)}
        ).status_code
        == 403
    )
    assert client.get("/sourcing/assignees").status_code == 403


# --- Dossier de sourcing -------------------------------------------------------


def test_a_qualified_request_opens_exactly_one_case(world, login, case, db):
    assert re.fullmatch(r"ST-SRC-\d{4}-\d{4,}", case["reference"])
    assert case["request"]["status"] == "in_sourcing" and case["request"]["buyer_name"] == "Acheteur A"
    # Assigné par défaut à la personne qui l'ouvre.
    assert case["assignee"]["full_name"] == "Test"
    again = login("admin@st.example.com").post("/sourcing/cases", json={"request_id": case["request"]["id"]})
    assert again.status_code == 409
    assert len(login("sales@st.example.com").get("/sourcing/cases").json()) == 1
    assert db.scalar(select(AuditLog).where(AuditLog.action == "sourcing_case.opened"))


def test_assignment_goes_to_sourcing_capable_staff_only(world, login, case, db):
    from app.modules.identity.models import User

    sourcing = login("sourcing@st.example.com")
    emails = {"admin@st.example.com", "sourcing@st.example.com"}
    users = {u.email: u for u in db.scalars(select(User))}
    assignees = {a["id"] for a in sourcing.get("/sourcing/assignees").json()}
    assert assignees == {str(users[e].id) for e in emails}

    ok = sourcing.patch(
        f"/sourcing/cases/{case['id']}", json={"assignee_id": str(users["admin@st.example.com"].id)}
    )
    assert ok.status_code == 200 and ok.json()["assignee"]["id"] == str(users["admin@st.example.com"].id)
    for outsider in ("sales@st.example.com", "owner@a.example.com", "owner@f.example.com"):
        response = sourcing.patch(
            f"/sourcing/cases/{case['id']}", json={"assignee_id": str(users[outsider].id)}
        )
        assert response.status_code == 400


def test_search_returns_active_products_of_verified_suppliers_only(world, login, case, verified_supplier):
    sourcing = login("sourcing@st.example.com")
    found = sourcing.get("/sourcing/suppliers", params={"q": "riz"}).json()
    assert [(p["product_name"], p["supplier"]["name"]) for p in found] == [("Riz long", "Fournisseur")]
    assert found[0]["category_name"] == "Céréales"
    assert (
        len(sourcing.get("/sourcing/suppliers", params={"category_id": str(verified_supplier.id)}).json())
        == 1
    )
    assert sourcing.get("/sourcing/suppliers", params={"q": "cacao"}).json() == []
    # Le caractère joker n'est pas interprété.
    assert sourcing.get("/sourcing/suppliers", params={"q": "%"}).json() == []


def test_shortlist_and_internal_notes(world, login, case, verified_supplier):
    sourcing = login("sourcing@st.example.com")
    cid = case["id"]
    supplier = {"organization_id": str(world["supplier"].id)}

    added = sourcing.post(f"/sourcing/cases/{cid}/candidates", json=supplier)
    assert added.status_code == 201
    assert [c["organization"]["name"] for c in added.json()["candidates"]] == ["Fournisseur"]
    assert sourcing.post(f"/sourcing/cases/{cid}/candidates", json=supplier).status_code == 409
    # Ni un fournisseur non vérifié, ni un acheteur, ni l'organisation interne.
    for other, expected in (
        (world["other_supplier"], 400),
        (world["buyer_b"], 404),
        (world["internal"], 404),
    ):
        response = sourcing.post(f"/sourcing/cases/{cid}/candidates", json={"organization_id": str(other.id)})
        assert response.status_code == expected

    noted = sourcing.post(f"/sourcing/cases/{cid}/notes", json={"body": "Marge visée 8 %, ne pas divulguer"})
    assert noted.status_code == 201 and noted.json()["notes"][0]["author"]["full_name"] == "Test"

    removed = sourcing.delete(f"/sourcing/cases/{cid}/candidates/{world['supplier'].id}")
    assert removed.status_code == 200 and removed.json()["candidates"] == []
    assert sourcing.delete(f"/sourcing/cases/{cid}/candidates/{world['supplier'].id}").status_code == 404


def test_buyer_responses_never_contain_internal_data(world, login, case, verified_supplier):
    sourcing, buyer = login("sourcing@st.example.com"), login("owner@a.example.com")
    cid = case["id"]
    sourcing.post(f"/sourcing/cases/{cid}/candidates", json={"organization_id": str(world["supplier"].id)})
    sourcing.post(f"/sourcing/cases/{cid}/notes", json={"body": "Marge visée 8 %, ne pas divulguer"})

    for response in (
        buyer.get("/purchase-requests"),
        buyer.get(f"/purchase-requests/{case['request']['id']}"),
    ):
        text = response.text
        assert response.status_code == 200 and '"in_sourcing"' in text
        for leaked in ("Marge", "Fournisseur", "ST-SRC", "Test", cid, str(world["supplier"].id)):
            assert leaked not in text, leaked
        body = response.json()
        mine = body[0] if isinstance(body, list) else body
        assert not [k for k in mine if any(word in k for word in INTERNAL_KEYS)]
        assert set(mine["history"][0]) == {"created_at", "from_status", "to_status", "message"}


def test_cancelling_a_request_freezes_its_case(world, login, case, verified_supplier):
    sourcing = login("sourcing@st.example.com")
    cid = case["id"]
    cancelled = login("owner@a.example.com").post(
        f"/purchase-requests/{case['request']['id']}/cancel", json={"message": "Besoin couvert"}
    )
    assert cancelled.json()["status"] == "cancelled"
    assert sourcing.get(f"/sourcing/cases/{cid}").json()["request"]["status"] == "cancelled"
    response = sourcing.post(
        f"/sourcing/cases/{cid}/candidates", json={"organization_id": str(world["supplier"].id)}
    )
    assert response.status_code == 409
    assert (
        sourcing.post(f"/sourcing/cases/{cid}/notes", json={"body": "Annulée par le client"}).status_code
        == 201
    )
