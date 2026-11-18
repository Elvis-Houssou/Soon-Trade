"""Profil d'organisation, membres, annuaire interne et vérification des fournisseurs."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFound
from app.modules.audit.models import record
from app.modules.identity.models import Invitation, Membership, Organization, User, UserSession
from app.modules.identity.permissions import ROLE_KIND

VERIFICATION_STATUSES = ("pending", "verified", "rejected", "suspended")


def update_profile(
    session: Session, organization: Organization, changes: dict[str, Any], *, actor: User, ip: str | None
) -> None:
    for field, value in changes.items():
        setattr(organization, field, value.strip() or None if isinstance(value, str) else value)
    record(
        session,
        "organization.updated",
        str(organization.id),
        actor_id=actor.id,
        ip=ip,
        fields=sorted(changes),
    )


# --- Membres -----------------------------------------------------------------


def list_members(session: Session, organization: Organization) -> list[Membership]:
    return list(
        session.scalars(
            select(Membership)
            .join(User, User.id == Membership.user_id)
            .where(Membership.organization_id == organization.id)
            .order_by(User.full_name)
        )
    )


def pending_invitations(session: Session, organization: Organization) -> list[Invitation]:
    return list(
        session.scalars(
            select(Invitation)
            .where(Invitation.organization_id == organization.id, Invitation.accepted_at.is_(None))
            .order_by(Invitation.created_at.desc())
        )
    )


def cancel_invitation(
    session: Session, organization: Organization, invitation_id: uuid.UUID, *, actor: User, ip: str | None
) -> None:
    # Le filtre sur l'organisation fait le cloisonnement : une invitation d'autrui est « introuvable ».
    deleted = session.execute(
        delete(Invitation).where(
            Invitation.id == invitation_id,
            Invitation.organization_id == organization.id,
            Invitation.accepted_at.is_(None),
        )
    )
    if not deleted.rowcount:  # type: ignore[attr-defined]
        raise NotFound("Invitation introuvable.")
    record(session, "invitation.cancelled", str(invitation_id), actor_id=actor.id, ip=ip)


def update_member(
    session: Session,
    organization: Organization,
    user_id: uuid.UUID,
    *,
    role: str | None,
    is_active: bool | None,
    actor: User,
    ip: str | None,
) -> Membership:
    membership = session.scalar(
        select(Membership).where(Membership.user_id == user_id, Membership.organization_id == organization.id)
    )
    if not membership:
        raise NotFound("Membre introuvable.")
    if user_id == actor.id:
        # Garantit aussi qu'une organisation garde toujours un propriétaire actif.
        raise AppError("Vous ne pouvez pas modifier votre propre accès.")

    if role is not None and role != membership.role:
        if ROLE_KIND.get(role) != organization.kind:
            raise AppError("Ce rôle n'existe pas pour ce type d'organisation.")
        record(
            session,
            "member.role_changed",
            membership.user.email,
            actor_id=actor.id,
            ip=ip,
            previous=membership.role,
            role=role,
        )
        membership.role = role

    if is_active is not None and is_active != membership.user.is_active:
        membership.user.is_active = is_active
        if not is_active:
            session.execute(
                update(UserSession).where(UserSession.user_id == user_id).values(revoked_at=datetime.now(UTC))
            )
        record(
            session,
            "member.activated" if is_active else "member.deactivated",
            membership.user.email,
            actor_id=actor.id,
            ip=ip,
        )
    return membership


# --- Annuaire interne --------------------------------------------------------


def list_organizations(session: Session, kind: str) -> list[Organization]:
    return list(
        session.scalars(select(Organization).where(Organization.kind == kind).order_by(Organization.name))
    )


def get_client_organization(session: Session, organization_id: uuid.UUID) -> Organization:
    organization = session.get(Organization, organization_id)
    if not organization or organization.kind == "internal":
        raise NotFound("Organisation introuvable.")
    return organization


def set_verification(
    session: Session,
    organization: Organization,
    *,
    status: str,
    note: str | None,
    actor: User,
    ip: str | None,
) -> None:
    if organization.kind != "supplier":
        raise AppError("Seuls les fournisseurs font l'objet d'une vérification.")
    record(
        session,
        "supplier.verification_changed",
        str(organization.id),
        actor_id=actor.id,
        ip=ip,
        previous=organization.verification_status,
        status=status,
    )
    organization.verification_status = status
    organization.verification_note = note.strip() or None if note else None
