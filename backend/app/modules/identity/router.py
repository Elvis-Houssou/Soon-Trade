import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from app.core.config import get_settings
from app.core.errors import Forbidden
from app.modules.audit.models import AuditLog, record
from app.modules.identity import service
from app.modules.identity.deps import (
    SESSION_COOKIE,
    CurrentPrincipal,
    DbSession,
    Principal,
    client_ip,
    require_permission,
)
from app.modules.identity.models import User
from app.modules.identity.permissions import (
    AUDIT_READ,
    MEMBER_INVITE,
    ORGANIZATION_CREATE_BUYER,
    ORGANIZATION_CREATE_SUPPLIER,
)

router = APIRouter(tags=["identity"])

Password = Annotated[str, Field(min_length=10, max_length=128)]
Name = Annotated[str, Field(min_length=2, max_length=200)]


class OrganizationOut(BaseModel):
    id: uuid.UUID
    name: str
    kind: str


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    locale: str
    organization: OrganizationOut
    permissions: list[str]


def _me(principal: Principal) -> MeOut:
    organization = principal.organization
    return MeOut(
        id=principal.user.id,
        email=principal.user.email,
        full_name=principal.user.full_name,
        role=principal.role,
        locale=principal.user.locale,
        organization=OrganizationOut(id=organization.id, name=organization.name, kind=organization.kind),
        permissions=sorted(principal.permissions),
    )


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_days * 86400,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )


# --- Session -----------------------------------------------------------------


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


@router.post("/auth/login")
def login(body: LoginIn, request: Request, response: Response, session: DbSession) -> MeOut:
    user = service.authenticate(session, body.email, body.password, client_ip(request))
    token = service.create_session(session, user)
    session.commit()
    _set_session_cookie(response, token)
    return _me(Principal(user=user, organization=user.membership.organization, role=user.membership.role))


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, session: DbSession) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        service.revoke_session(session, token)
        session.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/auth/me")
def me(principal: CurrentPrincipal) -> MeOut:
    return _me(principal)


class PreferencesIn(BaseModel):
    locale: Literal["fr", "en", "de"]


@router.patch("/auth/me")
def update_preferences(body: PreferencesIn, session: DbSession, principal: CurrentPrincipal) -> MeOut:
    """Langue des e-mails : l'application l'aligne sur la langue affichée."""
    principal.user.locale = body.locale
    session.commit()
    return _me(principal)


# --- Mot de passe oublié -----------------------------------------------------


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str = Field(max_length=200)
    password: Password


@router.post("/auth/password/forgot", status_code=status.HTTP_204_NO_CONTENT)
def forgot_password(body: ForgotIn, request: Request, session: DbSession) -> None:
    service.request_password_reset(session, body.email, client_ip(request))
    session.commit()


@router.post("/auth/password/reset", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(body: ResetIn, request: Request, session: DbSession) -> None:
    service.reset_password(session, body.token, body.password, client_ip(request))
    session.commit()


# --- Invitations -------------------------------------------------------------


class InvitationIn(BaseModel):
    email: EmailStr
    role: str = Field(max_length=40)


class InvitationPreview(BaseModel):
    email: str
    organization_name: str
    role: str


class AcceptIn(BaseModel):
    full_name: Name
    password: Password


@router.post("/invitations", status_code=status.HTTP_201_CREATED)
def invite_member(
    body: InvitationIn,
    request: Request,
    session: DbSession,
    principal: Annotated[Principal, Depends(require_permission(MEMBER_INVITE))],
) -> None:
    """Invite dans sa propre organisation : l'organisation n'est jamais lue dans la requête."""
    service.create_invitation(
        session,
        email=body.email,
        organization=principal.organization,
        role=body.role,
        invited_by=principal.user,
        ip=client_ip(request),
    )
    session.commit()


@router.get("/invitations/{token}")
def preview_invitation(token: str, session: DbSession) -> InvitationPreview:
    invitation = service.valid_invitation(session, token)
    return InvitationPreview(
        email=invitation.email, organization_name=invitation.organization.name, role=invitation.role
    )


@router.post("/invitations/{token}/accept")
def accept_invitation(
    token: str, body: AcceptIn, request: Request, response: Response, session: DbSession
) -> MeOut:
    user = service.accept_invitation(
        session, token, full_name=body.full_name, password=body.password, ip=client_ip(request)
    )
    session_token = service.create_session(session, user)
    session.commit()
    _set_session_cookie(response, session_token)
    return _me(Principal(user=user, organization=user.membership.organization, role=user.membership.role))


# --- Organisations (côté interne) ---------------------------------------------


class OrganizationIn(BaseModel):
    name: Name
    kind: Literal["buyer", "supplier"]
    owner_email: EmailStr


@router.post("/organizations", status_code=status.HTTP_201_CREATED)
def create_organization(
    body: OrganizationIn, request: Request, session: DbSession, principal: CurrentPrincipal
) -> OrganizationOut:
    """Crée une organisation cliente et invite son propriétaire."""
    needed = ORGANIZATION_CREATE_BUYER if body.kind == "buyer" else ORGANIZATION_CREATE_SUPPLIER
    if needed not in principal.permissions:
        record(
            session,
            "access.denied",
            f"organization:create:{body.kind}",
            actor_id=principal.user.id,
            ip=client_ip(request),
        )
        session.commit()
        raise Forbidden("Vous n'avez pas les droits pour cette action.")
    organization = service.create_organization_with_owner(
        session,
        name=body.name,
        kind=body.kind,
        owner_email=body.owner_email,
        created_by=principal.user,
        ip=client_ip(request),
    )
    session.commit()
    return OrganizationOut(id=organization.id, name=organization.name, kind=organization.kind)


# --- Audit -------------------------------------------------------------------


class AuditOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    actor_id: uuid.UUID | None
    actor_name: str | None
    action: str
    subject: str
    details: dict[str, Any]
    ip: str | None


@router.get("/audit")
def list_audit(
    session: DbSession,
    _: Annotated[Principal, Depends(require_permission(AUDIT_READ))],
    action: Annotated[str, Field(max_length=80)] | None = None,
    q: Annotated[str, Field(max_length=200)] | None = None,
    before: uuid.UUID | None = None,
    limit: Annotated[int, Field(ge=1, le=200)] = 50,
) -> list[AuditOut]:
    """Journal en lecture seule, du plus récent au plus ancien. `action` filtre par préfixe
    (ex. « order. »), `q` cherche dans le sujet ; `before` (identifiant de la dernière ligne
    reçue) donne la page suivante. uuid7 : l'identifiant suit l'ordre d'écriture, même quand
    plusieurs lignes partagent la même heure (une transaction)."""
    query = (
        select(AuditLog, User.full_name)
        .outerjoin(User, User.id == AuditLog.actor_id)
        .order_by(AuditLog.id.desc())
        .limit(limit)
    )
    if action:
        query = query.where(AuditLog.action.startswith(action.strip(), autoescape=True))
    if q:
        query = query.where(AuditLog.subject.icontains(q.strip(), autoescape=True))
    if before:
        query = query.where(AuditLog.id < before)
    return [
        AuditOut(
            id=row.id,
            created_at=row.created_at,
            actor_id=row.actor_id,
            actor_name=name,
            action=row.action,
            subject=row.subject,
            details=row.details,
            ip=row.ip,
        )
        for row, name in session.execute(query)
    ]
