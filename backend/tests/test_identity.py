from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.main import app
from app.modules.audit.models import AuditLog
from app.modules.identity.models import Invitation, Organization, User, UserSession
from tests.conftest import PASSWORD, token_in

NEW_PASSWORD = "un-autre-mot-de-passe"


# --- Connexion ---------------------------------------------------------------


def test_login_sets_an_httponly_cookie_and_me_describes_the_user(world, login):
    client = TestClient(app)
    response = client.post("/auth/login", json={"email": "Owner@A.example.com", "password": PASSWORD})
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie

    me = client.get("/auth/me").json()
    assert me["email"] == "owner@a.example.com"
    assert me["role"] == "buyer_owner"
    assert me["organization"] == {"id": str(world["buyer_a"].id), "name": "Acheteur A", "kind": "buyer"}
    assert me["permissions"] == [
        "claim:create",
        "conversation:use",
        "delivery:confirm",
        "document:upload",
        "member:invite",
        "order:view",
        "organization:update",
        "proposal:decide",
        "proposal:view",
        "purchase_request:manage",
    ]
    assert "password" not in str(me)


def test_wrong_password_and_unknown_email_get_the_same_answer(world):
    client = TestClient(app)
    wrong = client.post(
        "/auth/login", json={"email": "owner@a.example.com", "password": "mauvais-mot-de-passe"}
    )
    unknown = client.post("/auth/login", json={"email": "personne@a.example.com", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert "set-cookie" not in wrong.headers


def test_account_locks_after_repeated_failures(world):
    client = TestClient(app)
    for _ in range(5):
        client.post("/auth/login", json={"email": "owner@a.example.com", "password": "mauvais-mot-de-passe"})
    response = client.post("/auth/login", json={"email": "owner@a.example.com", "password": PASSWORD})
    assert response.status_code == 429


def test_inactive_user_cannot_log_in(world, make_user):
    make_user("parti@a.example.com", "buyer_member", world["buyer_a"], active=False)
    response = TestClient(app).post(
        "/auth/login", json={"email": "parti@a.example.com", "password": PASSWORD}
    )
    assert response.status_code == 401


def test_me_requires_a_session(db):
    assert TestClient(app).get("/auth/me").status_code == 401
    assert TestClient(app, cookies={"st_session": "jeton-invente"}).get("/auth/me").status_code == 401


def test_logout_revokes_the_session_server_side(world, login):
    client = login("owner@a.example.com")
    token = client.cookies["st_session"]
    assert client.post("/auth/logout").status_code == 204
    # Rejouer l'ancien cookie ne marche plus : la session est révoquée en base.
    assert TestClient(app, cookies={"st_session": token}).get("/auth/me").status_code == 401


def test_expired_session_is_rejected(world, login, db):
    client = login("owner@a.example.com")
    db.execute(update(UserSession).values(expires_at=datetime.now(UTC) - timedelta(minutes=1)))
    assert client.get("/auth/me").status_code == 401


def test_deactivating_a_user_ends_their_sessions(world, login, db):
    client = login("member@a.example.com")
    db.execute(update(User).where(User.email == "member@a.example.com").values(is_active=False))
    assert client.get("/auth/me").status_code == 401


# --- Invitations -------------------------------------------------------------


def test_internal_creates_a_buyer_and_its_owner_joins_by_invitation(world, login, emails, db):
    admin = login("admin@st.example.com")
    created = admin.post(
        "/organizations",
        json={"name": "Entreprise Traoré", "kind": "buyer", "owner_email": "traore@c.example.com"},
    )
    assert created.status_code == 201
    to, text = emails[0]
    assert to == "traore@c.example.com"
    token = token_in(text)

    visitor = TestClient(app)
    preview = visitor.get(f"/invitations/{token}").json()
    assert preview == {
        "email": "traore@c.example.com",
        "organization_name": "Entreprise Traoré",
        "role": "buyer_owner",
    }

    accepted = visitor.post(
        f"/invitations/{token}/accept", json={"full_name": "A. Traoré", "password": NEW_PASSWORD}
    )
    assert accepted.status_code == 200
    me = visitor.get("/auth/me").json()
    assert me["role"] == "buyer_owner" and me["organization"]["id"] == created.json()["id"]

    # Usage unique.
    assert visitor.get(f"/invitations/{token}").status_code == 404
    assert (
        TestClient(app)
        .post(f"/invitations/{token}/accept", json={"full_name": "Autre", "password": NEW_PASSWORD})
        .status_code
        == 404
    )
    # Le jeton n'est jamais stocké en clair.
    assert token not in {row.token_hash for row in db.scalars(select(Invitation))}


def test_there_is_no_public_signup(db):
    client = TestClient(app)
    for path in ("/auth/register", "/auth/signup", "/users"):
        assert client.post(path, json={"email": "x@x.example.com", "password": PASSWORD}).status_code == 404


def test_owner_invites_into_their_own_organization_only(world, login, emails, db):
    owner = login("owner@a.example.com")
    # Un identifiant d'organisation glissé dans la requête est ignoré.
    response = owner.post(
        "/invitations",
        json={
            "email": "nouveau@a.example.com",
            "role": "buyer_member",
            "organization_id": str(world["buyer_b"].id),
        },
    )
    assert response.status_code == 201
    invitation = db.scalar(select(Invitation).where(Invitation.email == "nouveau@a.example.com"))
    assert invitation.organization_id == world["buyer_a"].id


def test_member_without_permission_cannot_invite(world, login, emails):
    response = login("member@a.example.com").post(
        "/invitations", json={"email": "x@a.example.com", "role": "buyer_member"}
    )
    assert response.status_code == 403
    assert emails == []


@pytest.mark.parametrize("role", ["admin", "supplier_owner", "finance_agent", "role-invente"])
def test_owner_cannot_grant_a_role_from_another_space(world, login, emails, role):
    response = login("owner@a.example.com").post(
        "/invitations", json={"email": "x@a.example.com", "role": role}
    )
    assert response.status_code == 400
    assert emails == []


def test_inviting_an_existing_account_is_refused(world, login, emails):
    response = login("owner@a.example.com").post(
        "/invitations", json={"email": "owner@b.example.com", "role": "buyer_member"}
    )
    assert response.status_code == 409


def test_expired_invitation_is_rejected(world, login, emails, db):
    login("owner@a.example.com").post(
        "/invitations", json={"email": "tard@a.example.com", "role": "buyer_member"}
    )
    token = token_in(emails[0][1])
    db.execute(update(Invitation).values(expires_at=datetime.now(UTC) - timedelta(minutes=1)))
    assert TestClient(app).get(f"/invitations/{token}").status_code == 404


def test_a_new_invitation_replaces_the_previous_one(world, login, emails):
    owner = login("owner@a.example.com")
    owner.post("/invitations", json={"email": "deux@a.example.com", "role": "buyer_member"})
    owner.post("/invitations", json={"email": "deux@a.example.com", "role": "buyer_member"})
    first, second = (token_in(text) for _, text in emails)
    assert TestClient(app).get(f"/invitations/{first}").status_code == 404
    assert TestClient(app).get(f"/invitations/{second}").status_code == 200


def test_short_password_is_refused_on_acceptance(world, login, emails):
    login("owner@a.example.com").post(
        "/invitations", json={"email": "court@a.example.com", "role": "buyer_member"}
    )
    token = token_in(emails[0][1])
    response = TestClient(app).post(
        f"/invitations/{token}/accept", json={"full_name": "Court", "password": "court"}
    )
    assert response.status_code == 422


# --- Permissions entre rôles et espaces ---------------------------------------


@pytest.mark.parametrize(
    ("email", "kind", "expected"),
    [
        ("admin@st.example.com", "buyer", 201),
        ("admin@st.example.com", "supplier", 201),
        ("sales@st.example.com", "buyer", 201),
        ("sales@st.example.com", "supplier", 403),
        ("sourcing@st.example.com", "supplier", 201),
        ("sourcing@st.example.com", "buyer", 403),
        ("auditor@st.example.com", "buyer", 403),
        ("owner@a.example.com", "buyer", 403),
        ("owner@f.example.com", "supplier", 403),
    ],
)
def test_who_may_create_which_organization(world, login, emails, db, email, kind, expected):
    before = len(db.scalars(select(Organization)).all())
    response = login(email).post(
        "/organizations", json={"name": "Nouvelle", "kind": kind, "owner_email": "n@n.example.com"}
    )
    assert response.status_code == expected
    assert len(db.scalars(select(Organization)).all()) == before + (expected == 201)


def test_nobody_can_create_an_internal_organization_through_the_api(world, login):
    response = login("admin@st.example.com").post(
        "/organizations", json={"name": "Faux interne", "kind": "internal", "owner_email": "n@n.example.com"}
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("email", "expected"),
    [
        ("admin@st.example.com", 200),
        ("auditor@st.example.com", 200),
        ("sales@st.example.com", 403),
        ("owner@a.example.com", 403),
    ],
)
def test_audit_log_is_reserved_to_admin_and_auditor(world, login, email, expected):
    assert login(email).get("/audit").status_code == expected


def test_sensitive_actions_are_audited_without_secrets(world, login, emails, db):
    login("admin@st.example.com").post(
        "/organizations", json={"name": "Tracée", "kind": "buyer", "owner_email": "t@t.example.com"}
    )
    login("owner@a.example.com").post(
        "/organizations", json={"name": "Non", "kind": "buyer", "owner_email": "n@n.example.com"}
    )
    rows = db.scalars(select(AuditLog)).all()
    actions = {row.action for row in rows}
    assert {"auth.login", "organization.created", "invitation.created", "access.denied"} <= actions
    dump = " ".join(f"{row.subject} {row.details}" for row in rows)
    assert PASSWORD not in dump and token_in(emails[0][1]) not in dump


# --- Mot de passe oublié -----------------------------------------------------


def test_forgot_password_never_reveals_whether_the_account_exists(world, emails):
    client = TestClient(app)
    known = client.post("/auth/password/forgot", json={"email": "owner@a.example.com"})
    unknown = client.post("/auth/password/forgot", json={"email": "personne@a.example.com"})
    assert known.status_code == unknown.status_code == 204
    assert [to for to, _ in emails] == ["owner@a.example.com"]


def test_reset_changes_the_password_and_closes_open_sessions(world, login, emails):
    old_session = login("owner@a.example.com")
    TestClient(app).post("/auth/password/forgot", json={"email": "owner@a.example.com"})
    token = token_in(emails[0][1])

    client = TestClient(app)
    assert (
        client.post("/auth/password/reset", json={"token": token, "password": NEW_PASSWORD}).status_code
        == 204
    )
    assert old_session.get("/auth/me").status_code == 401
    assert (
        client.post("/auth/login", json={"email": "owner@a.example.com", "password": PASSWORD}).status_code
        == 401
    )
    assert (
        client.post(
            "/auth/login", json={"email": "owner@a.example.com", "password": NEW_PASSWORD}
        ).status_code
        == 200
    )
    # Usage unique.
    assert client.post("/auth/password/reset", json={"token": token, "password": PASSWORD}).status_code == 404
