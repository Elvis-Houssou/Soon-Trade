from decimal import Decimal

import pytest
from sqlalchemy import select

from app.modules.audit.models import AuditLog
from app.modules.catalog.models import Category, Product
from app.modules.identity.models import User

# --- Profil d'organisation -----------------------------------------------------


def test_owner_updates_their_profile_and_only_the_allowed_fields(world, login):
    owner = login("owner@a.example.com")
    response = owner.patch("/organization", json={"city": "  Abidjan ", "country": "CI", "phone": ""})
    assert response.status_code == 200
    body = response.json()
    assert body["city"] == "Abidjan" and body["country"] == "CI" and body["phone"] is None

    # Nom, type et statut de vérification ne se modifient pas soi-même.
    for forbidden in ({"name": "Autre"}, {"kind": "internal"}, {"verification_status": "verified"}):
        assert owner.patch("/organization", json=forbidden).status_code == 422
    assert owner.get("/organization").json()["name"] == "Acheteur A"


def test_member_reads_but_cannot_edit_the_profile(world, login):
    member = login("member@a.example.com")
    assert member.get("/organization").status_code == 200
    assert member.patch("/organization", json={"city": "Bouaké"}).status_code == 403


def test_profile_never_exposes_the_internal_note(world, login):
    login("sourcing@st.example.com").post(
        f"/organizations/{world['supplier'].id}/verification",
        json={"status": "rejected", "note": "RCCM illisible, relancer"},
    )
    profile = login("owner@f.example.com").get("/organization").json()
    assert profile["verification_status"] == "rejected"
    assert "verification_note" not in profile and "RCCM" not in str(profile)


# --- Membres -------------------------------------------------------------------


def test_owner_sees_only_their_own_members(world, login):
    emails = {m["email"] for m in login("owner@a.example.com").get("/members").json()}
    assert emails == {"owner@a.example.com", "member@a.example.com"}
    assert login("member@a.example.com").get("/members").status_code == 403


def test_owner_cannot_touch_a_member_of_another_organization(world, login, db):
    target = db.scalar(select(User).where(User.email == "owner@b.example.com"))
    response = login("owner@a.example.com").patch(f"/members/{target.id}", json={"is_active": False})
    assert response.status_code == 404
    db.refresh(target)
    assert target.is_active


def test_deactivating_a_member_closes_their_session(world, login, db):
    member = login("member@a.example.com")
    target = db.scalar(select(User).where(User.email == "member@a.example.com"))
    response = login("owner@a.example.com").patch(f"/members/{target.id}", json={"is_active": False})
    assert response.status_code == 200 and response.json()["is_active"] is False
    assert member.get("/auth/me").status_code == 401


def test_owner_cannot_change_their_own_access_nor_grant_a_foreign_role(world, login, db):
    owner = login("owner@a.example.com")
    me = db.scalar(select(User).where(User.email == "owner@a.example.com"))
    member = db.scalar(select(User).where(User.email == "member@a.example.com"))
    assert owner.patch(f"/members/{me.id}", json={"is_active": False}).status_code == 400
    assert owner.patch(f"/members/{member.id}", json={"role": "admin"}).status_code == 400
    assert owner.patch(f"/members/{member.id}", json={"role": "buyer_owner"}).json()["role"] == "buyer_owner"


def test_pending_invitations_are_listed_and_cancellable_by_their_organization_only(world, login, emails):
    owner_a = login("owner@a.example.com")
    owner_a.post("/invitations", json={"email": "futur@a.example.com", "role": "buyer_member"})
    (invitation,) = owner_a.get("/invitations").json()
    assert invitation["email"] == "futur@a.example.com" and "token" not in str(invitation)

    owner_b = login("owner@b.example.com")
    assert owner_b.get("/invitations").json() == []
    assert owner_b.delete(f"/invitations/{invitation['id']}").status_code == 404
    assert owner_a.delete(f"/invitations/{invitation['id']}").status_code == 204
    assert owner_a.get("/invitations").json() == []


# --- Annuaire interne et vérification ------------------------------------------


@pytest.mark.parametrize(
    ("email", "expected"),
    [
        ("admin@st.example.com", 200),
        ("sales@st.example.com", 200),
        ("auditor@st.example.com", 200),
        ("owner@a.example.com", 403),
        ("owner@f.example.com", 403),
    ],
)
def test_directory_is_internal_only(world, login, email, expected):
    response = login(email).get("/organizations", params={"kind": "supplier"})
    assert response.status_code == expected
    if expected == 200:
        assert {o["name"] for o in response.json()} == {"Fournisseur", "Fournisseur concurrent"}


@pytest.mark.parametrize(
    ("email", "expected"),
    [("admin@st.example.com", 200), ("sourcing@st.example.com", 200), ("sales@st.example.com", 403)],
)
def test_who_may_verify_a_supplier(world, login, db, email, expected):
    response = login(email).post(
        f"/organizations/{world['supplier'].id}/verification", json={"status": "verified"}
    )
    assert response.status_code == expected
    if expected == 200:
        assert db.scalar(select(AuditLog).where(AuditLog.action == "supplier.verification_changed"))


def test_verification_applies_to_suppliers_only(world, login):
    sourcing = login("sourcing@st.example.com")
    for target in (world["buyer_a"], world["internal"]):
        response = sourcing.post(f"/organizations/{target.id}/verification", json={"status": "verified"})
        assert response.status_code in (400, 404)


# --- Catégories ----------------------------------------------------------------


@pytest.fixture
def category(db):
    category = Category(name="Céréales")
    db.add(category)
    db.flush()
    return category


def test_categories_are_managed_internally_and_readable_by_everyone_logged_in(world, login, category):
    assert login("owner@f.example.com").post("/categories", json={"name": "Huiles"}).status_code == 403
    assert login("sales@st.example.com").post("/categories", json={"name": "Huiles"}).status_code == 403
    sourcing = login("sourcing@st.example.com")
    assert sourcing.post("/categories", json={"name": "Huiles"}).status_code == 201
    assert sourcing.post("/categories", json={"name": "Huiles"}).status_code == 409
    names = [c["name"] for c in login("owner@a.example.com").get("/categories").json()]
    assert names == ["Céréales", "Huiles"]


# --- Catalogue -----------------------------------------------------------------

RICE = {"name": "Riz blanc", "unit": "tonne", "available_quantity": "80.5", "packaging": "Sacs de 50 kg"}


@pytest.fixture
def rice(world, login, category):
    response = login("member@f.example.com").post("/products", json={**RICE, "category_id": str(category.id)})
    assert response.status_code == 201, response.text
    return response.json()


def test_supplier_manages_their_catalogue(world, login, rice, db):
    supplier = login("owner@f.example.com")
    assert Decimal(rice["available_quantity"]) == Decimal("80.5") and rice["availability"] == "available"

    updated = supplier.patch(
        f"/products/{rice['id']}", json={"available_quantity": "0", "availability": "unavailable"}
    )
    assert updated.status_code == 200 and updated.json()["availability"] == "unavailable"

    assert supplier.delete(f"/products/{rice['id']}").status_code == 204
    assert supplier.get("/products").json() == []
    # Suppression logique : la ligne reste en base.
    assert db.scalar(select(Product).where(Product.name == "Riz blanc")).is_active is False


def test_a_supplier_never_sees_or_edits_a_competitor_catalogue(world, login, rice):
    competitor = login("owner@g.example.com")
    assert competitor.get("/products").json() == []
    assert competitor.patch(f"/products/{rice['id']}", json={"name": "Piraté"}).status_code == 404
    assert competitor.delete(f"/products/{rice['id']}").status_code == 404
    assert competitor.get(f"/organizations/{world['supplier'].id}/products").status_code == 403
    assert login("owner@f.example.com").get("/products").json()[0]["name"] == "Riz blanc"


def test_buyers_have_no_access_to_any_catalogue(world, login, rice, category):
    buyer = login("owner@a.example.com")
    assert buyer.get("/products").status_code == 403
    assert buyer.post("/products", json={**RICE, "category_id": str(category.id)}).status_code == 403
    assert buyer.get(f"/organizations/{world['supplier'].id}/products").status_code == 403


def test_organization_id_in_the_body_cannot_redirect_a_product(world, login, category):
    response = login("owner@f.example.com").post(
        "/products",
        json={**RICE, "category_id": str(category.id), "organization_id": str(world["other_supplier"].id)},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("email", "expected"),
    [("sourcing@st.example.com", 200), ("sales@st.example.com", 200), ("finance@st.example.com", 403)],
)
def test_internal_reads_a_supplier_catalogue_for_sourcing(world, login, rice, make_user, email, expected):
    if email.startswith("finance"):
        make_user(email, "finance_agent", world["internal"])
    response = login(email).get(f"/organizations/{world['supplier'].id}/products")
    assert response.status_code == expected
    if expected == 200:
        assert [p["name"] for p in response.json()] == ["Riz blanc"]


@pytest.mark.parametrize(
    "bad",
    [
        {"unit": "palette"},
        {"available_quantity": "-1"},
        {"availability": "bientot"},
        {"name": "R"},
        {"available_quantity": "1.23456"},
    ],
)
def test_invalid_products_are_refused(world, login, category, bad):
    payload = {**RICE, "category_id": str(category.id), **bad}
    assert login("owner@f.example.com").post("/products", json=payload).status_code == 422


def test_products_need_an_active_category(world, login, category, db):
    category.is_active = False
    db.flush()
    payload = {**RICE, "category_id": str(category.id)}
    assert login("owner@f.example.com").post("/products", json=payload).status_code == 400
