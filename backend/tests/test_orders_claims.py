from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.core import storage
from app.modules.notifications import service as notification_service
from tests.test_proposals import ADMIN, OWNER, SALES, _sent, case  # noqa: F401  (fixture réutilisée)

LOGISTICS, SUPPORT = "logistics@st.example.com", "support@st.example.com"
SUPPLIER, OTHER_SUPPLIER = "owner@f.example.com", "owner@g.example.com"
PDF = b"%PDF-1.7 preuve"
SOON = (date.today() + timedelta(days=5)).isoformat()


@pytest.fixture
def emails(monkeypatch):
    sent: list[tuple[str, str]] = []
    capture = lambda to, subject, text: sent.append((to, text))  # noqa: E731
    monkeypatch.setattr(notification_service, "send_email", capture)
    return sent


@pytest.fixture
def bucket(monkeypatch):
    monkeypatch.setattr(storage, "put_object", lambda key, data, content_type: None)
    monkeypatch.setattr(storage, "presigned_download_url", lambda key, filename: f"https://s3.test/{key}")


@pytest.fixture
def staff(world, make_user):
    make_user(LOGISTICS, "logistics_agent", world["internal"])
    make_user(SUPPORT, "support_agent", world["internal"])


@pytest.fixture
def order(login, case, staff):  # noqa: F811
    """Proposition (385 000 FCFA la tonne, achetée 350 000) acceptée par l'acheteur."""
    proposal = _sent(login, case)
    response = login(OWNER).post(f"/proposals/{proposal['id']}/accept")
    assert response.status_code == 200, response.text
    return login(SALES).get("/internal/orders").json()[0]


def _confirmed(login, order):
    response = login(SALES).post(f"/internal/orders/{order['id']}/confirm")
    assert response.status_code == 200, response.text
    return response.json()


def _planned(login, order):
    """Commande confirmée, en préparation, une livraison planifiée pour la part du fournisseur."""
    _confirmed(login, order)
    logistics = login(LOGISTICS)
    assert logistics.post(f"/internal/orders/{order['id']}/prepare").json()["status"] == "in_preparation"
    body = {
        "description": "40 t de riz, en deux camions",
        "planned_date": SOON,
        "carrier": "Transports Ivoire",
        "supplier_order_id": order["supplier_orders"][0]["id"],
    }
    response = logistics.post(f"/internal/orders/{order['id']}/deliveries", json=body)
    assert response.status_code == 201, response.text
    return response.json()["deliveries"][0]


def test_acceptance_creates_a_frozen_order_and_a_supplier_order(login, order):
    assert order["status"] == "created"
    assert order["terms"]["lines"][0]["unit_price"] == "385000.00"
    assert Decimal(order["buyer_total"]) == Decimal("15400000")
    part = order["supplier_orders"][0]
    assert part["terms"]["lines"][0]["unit_price"] == "350000.00" and part["released_at"] is None
    assert Decimal(order["margin"]) == Decimal("1400000")

    mine = login(OWNER).get("/orders").json()
    assert [o["status"] for o in mine] == ["created"]
    assert mine[0]["terms"]["version"] == 1
    # Le fournisseur ne voit rien avant la confirmation par SOON TRADE.
    assert login(SUPPLIER).get("/supplier-orders").json() == []


def test_confirmation_releases_the_supplier_order_without_buyer_data(login, order, emails):
    _confirmed(login, order)
    raw = login(SUPPLIER).get("/supplier-orders").text
    for secret in ("Acheteur", "385000", "15400000", "ST-CMD", "ST-PRO", "ST-ACH"):
        assert secret not in raw, secret
    part = login(SUPPLIER).get("/supplier-orders").json()[0]
    assert part["status"] == "confirmed" and part["terms"]["lines"][0]["unit_price"] == "350000.00"

    raw = login(OWNER).get(f"/orders/{order['id']}").text
    for secret in ("Fournisseur", "350000", "ST-BC", "margin", "supplier"):
        assert secret not in raw, secret
    notified = {to for to, _ in emails}
    assert {"owner@a.example.com", "owner@f.example.com"} <= notified
    assert all("385" not in text and "350" not in text for _, text in emails)


def test_delivery_cycle_drives_the_order_to_closure(login, order):
    delivery = _planned(login, order)
    supplier, buyer, sales = login(SUPPLIER), login(OWNER), login(SALES)

    assert (
        supplier.patch(
            f"/supplier-deliveries/{delivery['id']}", json={"tracking_number": "TI-42"}
        ).status_code
        == 200
    )
    assert supplier.post(f"/supplier-deliveries/{delivery['id']}/ship").json()["status"] == "shipped"
    assert buyer.get(f"/orders/{order['id']}").json()["status"] == "shipped"
    # L'acheteur ne confirme pas une livraison encore en route.
    assert buyer.post(f"/deliveries/{delivery['id']}/confirm").status_code == 409
    supplier.post(f"/supplier-deliveries/{delivery['id']}/deliver")
    assert sales.get(f"/internal/orders/{order['id']}").json()["status"] == "delivered"

    mine = buyer.post(f"/deliveries/{delivery['id']}/confirm").json()
    assert mine["deliveries"][0]["status"] == "confirmed"
    assert mine["deliveries"][0]["tracking_number"] == "TI-42"
    assert [e["to_status"] for e in mine["history"]] == [
        "created",
        "confirmed",
        "in_preparation",
        "shipped",
        "delivered",
    ]

    closed = sales.post(f"/internal/orders/{order['id']}/close").json()
    assert closed["status"] == "closed"
    assert supplier.get("/supplier-orders").json()[0]["status"] == "closed"


def test_order_rules(login, order):
    sales, logistics = login(SALES), login(LOGISTICS)
    # Pas de livraison avant confirmation ; annulation motivée.
    body = {"description": "Lot", "planned_date": SOON}
    assert logistics.post(f"/internal/orders/{order['id']}/deliveries", json=body).status_code == 409
    assert sales.post(f"/internal/orders/{order['id']}/cancel", json={}).status_code == 400
    delivery = _planned(login, order)
    assert sales.post(f"/internal/orders/{order['id']}/close").status_code == 409
    logistics.post(f"/internal/deliveries/{delivery['id']}/ship")
    # Une livraison partie : plus d'annulation.
    assert sales.post(f"/internal/orders/{order['id']}/cancel", json={"message": "Erreur"}).status_code == 409
    assert logistics.post(f"/internal/deliveries/{delivery['id']}/incident", json={}).status_code == 400
    incident = logistics.post(
        f"/internal/deliveries/{delivery['id']}/incident", json={"message": "Camion en panne"}
    )
    assert incident.json()["deliveries"][0]["status"] == "incident"
    # L'acheteur voit l'état, jamais la note interne.
    raw = login(OWNER).get(f"/orders/{order['id']}").text
    assert "incident" in raw and "panne" not in raw
    assert (
        logistics.post(f"/internal/deliveries/{delivery['id']}/resume").json()["deliveries"][0]["status"]
        == "in_transit"
    )


def test_cancellation_reason_reaches_the_buyer(login, order):
    _confirmed(login, order)
    login(SALES).post(
        f"/internal/orders/{order['id']}/cancel", json={"message": "Rupture chez le fournisseur"}
    )
    mine = login(OWNER).get(f"/orders/{order['id']}").json()
    assert mine["status"] == "cancelled" and mine["history"][-1]["message"] == "Rupture chez le fournisseur"
    assert login(SUPPLIER).get("/supplier-orders").json()[0]["status"] == "cancelled"


def test_isolation_and_permissions(login, order):
    delivery = _planned(login, order)
    part_id = order["supplier_orders"][0]["id"]

    other_buyer = login("owner@b.example.com")
    assert other_buyer.get("/orders").json() == []
    assert other_buyer.get(f"/orders/{order['id']}").status_code == 404
    assert other_buyer.post(f"/deliveries/{delivery['id']}/confirm").status_code == 404

    other_supplier = login(OTHER_SUPPLIER)
    assert other_supplier.get("/supplier-orders").json() == []
    assert other_supplier.get(f"/supplier-orders/{part_id}").status_code == 404
    assert other_supplier.post(f"/supplier-deliveries/{delivery['id']}/ship").status_code == 404

    assert login(OWNER).get("/supplier-orders").status_code == 403
    assert login(SUPPLIER).get("/orders").status_code == 403
    assert login(SUPPLIER).get("/internal/orders").status_code == 403

    sourcing = login("sourcing@st.example.com")
    assert sourcing.get(f"/internal/orders/{order['id']}").status_code == 200
    assert sourcing.post(f"/internal/orders/{order['id']}/close").status_code == 403
    assert login(SALES).post(f"/internal/deliveries/{delivery['id']}/ship").status_code == 403
    assert login("auditor@st.example.com").get("/internal/deliveries").status_code == 200


def test_delivery_proofs_respect_each_space(login, order, bucket):
    delivery = _planned(login, order)
    logistics, supplier, buyer = login(LOGISTICS), login(SUPPLIER), login(OWNER)
    files = {"file": ("bon.pdf", PDF, "application/pdf")}

    response = logistics.post(
        f"/internal/deliveries/{delivery['id']}/proofs", files=files, data={"buyer_visible": "true"}
    )
    assert response.status_code == 201, response.text
    internal_doc = response.json()["deliveries"][0]["proofs"][0]["id"]
    # Même en le demandant, la preuve d'un fournisseur ne devient pas visible de l'acheteur.
    response = supplier.post(
        f"/supplier-deliveries/{delivery['id']}/proofs", files=files, data={"buyer_visible": "true"}
    )
    supplier_doc = response.json()["deliveries"][0]["proofs"][0]["id"]
    # Contrôle du format, comme pour tout document.
    fake = {"file": ("bon.pdf", b"pas un pdf", "application/pdf")}
    assert logistics.post(f"/internal/deliveries/{delivery['id']}/proofs", files=fake).status_code == 400
    # Le personnel interne ne dépose toujours rien par le dépôt libre.
    assert logistics.post("/documents", files=files, data={"doc_type": "delivery_proof"}).status_code == 403

    mine = buyer.get(f"/orders/{order['id']}").json()["deliveries"][0]["proofs"]
    assert [p["id"] for p in mine] == [internal_doc]
    url = f"/deliveries/{delivery['id']}/proofs"
    assert buyer.get(f"{url}/{internal_doc}/url").status_code == 200
    assert buyer.get(f"{url}/{supplier_doc}/url").status_code == 404
    assert supplier.get(f"{url}/{supplier_doc}/url").status_code == 200
    assert supplier.get(f"{url}/{internal_doc}/url").status_code == 404
    assert login(OTHER_SUPPLIER).get(f"{url}/{supplier_doc}/url").status_code == 404
    assert login(SALES).get(f"{url}/{supplier_doc}/url").status_code == 200


def test_claim_puts_the_order_in_dispute_until_answered(login, order):
    delivery = _planned(login, order)
    supplier, buyer, support = login(SUPPLIER), login(OWNER), login(SUPPORT)
    supplier.post(f"/supplier-deliveries/{delivery['id']}/ship")

    claim = {
        "order_id": order["id"],
        "delivery_id": delivery["id"],
        "category": "delay",
        "subject": "Retard",
        "description": "Toujours rien reçu.",
    }
    response = buyer.post("/claims", json=claim)
    assert response.status_code == 201, response.text
    claim_id = response.json()["id"]
    assert buyer.get(f"/orders/{order['id']}").json()["status"] == "in_dispute"
    # Le litige reste entre l'acheteur et SOON TRADE.
    assert supplier.get("/supplier-orders").json()[0]["status"] == "shipped"

    # Les livraisons continuent d'avancer pendant le litige.
    supplier.post(f"/supplier-deliveries/{delivery['id']}/deliver")
    assert login(SALES).get(f"/internal/orders/{order['id']}").json()["status_before_dispute"] == "delivered"

    assert (
        login(LOGISTICS).post(f"/internal/claims/{claim_id}/resolve", json={"message": "x"}).status_code
        == 403
    )
    assert support.post(f"/internal/claims/{claim_id}/review").json()["status"] == "under_review"
    assert support.post(f"/internal/claims/{claim_id}/resolve", json={}).status_code == 400
    resolved = support.post(
        f"/internal/claims/{claim_id}/resolve", json={"message": "Livré ce matin, geste commercial."}
    )
    assert resolved.json()["status"] == "resolved"
    assert buyer.get(f"/orders/{order['id']}").json()["status"] == "delivered"

    mine = buyer.get(f"/claims/{claim_id}").json()
    assert mine["resolution"] == "Livré ce matin, geste commercial."
    assert "actor_name" not in str(mine)
    assert buyer.post(f"/claims/{claim_id}/close").json()["status"] == "closed"


def test_claim_rules_and_isolation(login, order):
    buyer = login(OWNER)
    claim = {
        "order_id": order["id"],
        "category": "quality",
        "subject": "Qualité",
        "description": "Grains cassés",
    }
    # Pas de réclamation sur une commande pas encore confirmée.
    assert buyer.post("/claims", json=claim).status_code == 409
    _confirmed(login, order)
    claim_id = buyer.post("/claims", json=claim).json()["id"]
    # Avant expédition, pas de litige : la commande garde son statut.
    assert buyer.get(f"/orders/{order['id']}").json()["status"] == "confirmed"
    assert buyer.post(f"/claims/{claim_id}/close").status_code == 409

    other = login("owner@b.example.com")
    assert other.get("/claims").json() == []
    assert other.get(f"/claims/{claim_id}").status_code == 404
    assert other.post("/claims", json=claim).status_code == 404
    assert login(SUPPLIER).get("/claims").status_code == 403
    assert login(SUPPORT).get("/internal/claims").json()[0]["buyer_name"] == "Acheteur A"
