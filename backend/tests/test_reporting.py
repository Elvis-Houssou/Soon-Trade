from decimal import Decimal

import pytest

from tests.test_orders_claims import SALES, _confirmed, bucket, emails, order, staff  # noqa: F401
from tests.test_proposals import OWNER, case  # noqa: F401
from tests.test_solicitations_offers import NEED

FINANCE = "finance@st.example.com"


@pytest.fixture
def finance(world, make_user):
    make_user(FINANCE, "finance_agent", world["internal"])


def test_dashboards_stay_within_each_space(login, order):  # noqa: F811
    _confirmed(login, order)
    mine = login(OWNER).get("/dashboard").json()
    assert mine["counts"]["orders_active"] == 1
    assert Decimal(mine["money"]["spend"]) == Decimal("15400000")
    other = login("owner@b.example.com").get("/dashboard").json()
    assert other["counts"]["orders_active"] == 0 and Decimal(other["money"]["spend"]) == 0

    supplier = login("owner@f.example.com").get("/dashboard").json()
    assert supplier["counts"]["orders_active"] == 1
    # Le fournisseur voit son chiffre (prix d'achat), jamais le prix de vente.
    assert Decimal(supplier["money"]["sales"]) == Decimal("14000000")
    assert "15400000" not in login("owner@f.example.com").get("/dashboard").text

    internal = login(SALES).get("/dashboard").json()
    assert internal["counts"]["orders_active"] == 1
    assert Decimal(internal["money"]["margin"]) == Decimal("1400000")
    # Sans droit de lecture des rapports, pas de chiffre d'affaires ni de marge.
    assert "money" not in login("sourcing@st.example.com").get("/dashboard").json()


def test_commercial_report(login, order):  # noqa: F811
    report = login(SALES).get("/internal/reports/commercial").json()
    assert report["funnel"] == {"requests": 1, "proposals_sent": 1, "accepted": 1, "orders": 1}
    assert report["rates"] == {"proposal_rate": 1.0, "acceptance_rate": 1.0}
    assert Decimal(report["margin"]) == Decimal("1400000")
    assert report["top_buyers"][0]["name"] == "Acheteur A"
    assert report["top_suppliers"][0]["name"] == "Fournisseur"
    empty = login(SALES).get("/internal/reports/commercial", params={"end": "2000-01-01"}).json()
    assert empty["funnel"]["orders"] == 0 and empty["average_order"] is None
    assert login("sourcing@st.example.com").get("/internal/reports/commercial").status_code == 403
    assert login(OWNER).get("/internal/reports/commercial").status_code == 403


def test_exports_are_restricted_traced_and_safe(world, login, finance):
    buyer = login(OWNER)
    rid = buyer.post("/purchase-requests", json={**NEED, "product_name": '=HYPERLINK("http://x")'}).json()[
        "id"
    ]
    buyer.post(f"/purchase-requests/{rid}/submit")

    response = login(FINANCE).get("/internal/exports/requests")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    text = response.content.decode("utf-8")
    assert text.startswith("﻿reference;date;acheteur")
    # Une cellule qui commencerait par « = » est neutralisée.
    assert "'=HYPERLINK" in text

    assert login(SALES).get("/internal/exports/requests").status_code == 403
    assert login(OWNER).get("/internal/exports/orders").status_code == 403
    assert login(FINANCE).get("/internal/exports/users").status_code == 422

    audit = login("admin@st.example.com").get("/audit", params={"action": "report."}).json()
    assert [(a["action"], a["subject"]) for a in audit] == [("report.exported", "requests")]
    assert audit[0]["actor_name"] == "Test"


def test_audit_filters_and_pages(world, login):
    admin = login("admin@st.example.com")
    buyer = login(OWNER)
    for _ in range(3):
        buyer.post("/purchase-requests", json=NEED)
    created = admin.get("/audit", params={"action": "purchase_request.created", "limit": 2}).json()
    assert len(created) == 2
    rest = admin.get(
        "/audit", params={"action": "purchase_request.created", "before": created[-1]["id"]}
    ).json()
    assert len(rest) == 1 and rest[0]["subject"] not in {c["subject"] for c in created}
    assert admin.get("/audit", params={"q": "ST-ACH"}).json()
    assert login(SALES).get("/audit").status_code == 403
