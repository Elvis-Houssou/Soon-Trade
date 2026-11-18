import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.modules.identity.deps import CurrentPrincipal, DbSession, Principal, client_ip, require_permission
from app.modules.identity.models import Membership
from app.modules.identity.permissions import (
    MEMBER_INVITE,
    ORGANIZATION_READ_ALL,
    ORGANIZATION_UPDATE,
    SUPPLIER_VERIFY,
)
from app.modules.organizations import service

router = APIRouter(tags=["organizations"])

Short = Annotated[str, Field(max_length=120)]


class ProfileOut(BaseModel):
    """Ce que l'organisation voit d'elle-même : aucune note interne."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    kind: str
    country: str | None
    city: str | None
    address: str | None
    phone: str | None
    registration_number: str | None
    tax_number: str | None
    verification_status: str


class ProfileIn(BaseModel):
    """Le nom, le type et le statut de vérification ne sont pas modifiables par l'organisation."""

    model_config = ConfigDict(extra="forbid")

    country: Annotated[str, Field(pattern=r"^[A-Z]{2}$")] | None = None
    city: Short | None = None
    address: Annotated[str, Field(max_length=300)] | None = None
    phone: Annotated[str, Field(max_length=40)] | None = None
    registration_number: Annotated[str, Field(max_length=80)] | None = None
    tax_number: Annotated[str, Field(max_length=80)] | None = None


@router.get("/organization")
def my_organization(principal: CurrentPrincipal) -> ProfileOut:
    return ProfileOut.model_validate(principal.organization)


@router.patch("/organization")
def update_my_organization(
    body: ProfileIn,
    request: Request,
    session: DbSession,
    principal: Annotated[Principal, Depends(require_permission(ORGANIZATION_UPDATE))],
) -> ProfileOut:
    service.update_profile(
        session,
        principal.organization,
        body.model_dump(exclude_unset=True),
        actor=principal.user,
        ip=client_ip(request),
    )
    session.commit()
    return ProfileOut.model_validate(principal.organization)


# --- Membres de sa propre organisation ----------------------------------------


class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool


class PendingInvitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: str
    expires_at: datetime


class MemberIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Annotated[str, Field(max_length=40)] | None = None
    is_active: bool | None = None


ManagesMembers = Annotated[Principal, Depends(require_permission(MEMBER_INVITE))]


def _member(membership: Membership) -> MemberOut:
    user = membership.user
    return MemberOut(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=membership.role,
        is_active=user.is_active,
    )


@router.get("/members")
def list_members(session: DbSession, principal: ManagesMembers) -> list[MemberOut]:
    return [_member(m) for m in service.list_members(session, principal.organization)]


@router.patch("/members/{user_id}")
def update_member(
    user_id: uuid.UUID, body: MemberIn, request: Request, session: DbSession, principal: ManagesMembers
) -> MemberOut:
    membership = service.update_member(
        session,
        principal.organization,
        user_id,
        role=body.role,
        is_active=body.is_active,
        actor=principal.user,
        ip=client_ip(request),
    )
    session.commit()
    return _member(membership)


@router.get("/invitations")
def list_pending_invitations(session: DbSession, principal: ManagesMembers) -> list[PendingInvitationOut]:
    invitations = service.pending_invitations(session, principal.organization)
    return [PendingInvitationOut.model_validate(i) for i in invitations]


@router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_invitation(
    invitation_id: uuid.UUID, request: Request, session: DbSession, principal: ManagesMembers
) -> None:
    service.cancel_invitation(
        session, principal.organization, invitation_id, actor=principal.user, ip=client_ip(request)
    )
    session.commit()


# --- Annuaire interne ----------------------------------------------------------


class DirectoryOut(ProfileOut):
    """Vue interne : ajoute la note de vérification, jamais renvoyée au client."""

    verification_note: str | None
    created_at: datetime


class VerificationIn(BaseModel):
    status: Literal["pending", "verified", "rejected", "suspended"]
    note: Annotated[str, Field(max_length=1000)] | None = None


ReadsDirectory = Annotated[Principal, Depends(require_permission(ORGANIZATION_READ_ALL))]


@router.get("/organizations")
def list_organizations(
    kind: Literal["buyer", "supplier"], session: DbSession, _: ReadsDirectory
) -> list[DirectoryOut]:
    return [DirectoryOut.model_validate(o) for o in service.list_organizations(session, kind)]


@router.post("/organizations/{organization_id}/verification")
def set_verification(
    organization_id: uuid.UUID,
    body: VerificationIn,
    request: Request,
    session: DbSession,
    principal: Annotated[Principal, Depends(require_permission(SUPPLIER_VERIFY))],
) -> DirectoryOut:
    organization = service.get_client_organization(session, organization_id)
    service.set_verification(
        session, organization, status=body.status, note=body.note, actor=principal.user, ip=client_ip(request)
    )
    session.commit()
    return DirectoryOut.model_validate(organization)
