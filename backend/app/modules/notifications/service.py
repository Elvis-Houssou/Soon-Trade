"""Notifications dans l'application et e-mails transactionnels, envoyés aux mêmes moments."""

import logging
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core import mail
from app.core.config import get_settings
from app.core.email import send_email
from app.modules.identity.models import Membership, Organization, User
from app.modules.identity.permissions import permissions_for
from app.modules.notifications.models import Notification

logger = logging.getLogger(__name__)
LIST_SIZE = 30


def members(session: Session, organization_id: uuid.UUID) -> list[User]:
    """Comptes actifs d'une organisation."""
    return list(
        session.scalars(
            select(User)
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.organization_id == organization_id, User.is_active)
        )
    )


def staff_with(session: Session, permission: str) -> list[User]:
    """Collaborateurs SOON TRADE actifs qui détiennent la permission."""
    rows = session.execute(
        select(User, Membership.role)
        .join(Membership, Membership.user_id == User.id)
        .join(Organization, Organization.id == Membership.organization_id)
        .where(Organization.kind == "internal", User.is_active)
    )
    return [user for user, role in rows if permission in permissions_for(role)]


def notify(
    session: Session,
    recipients: Iterable[User],
    kind: str,
    *,
    link: str,
    params: dict[str, str] | None = None,
    email: dict[str, Any] | None = None,
    besides: uuid.UUID | None = None,
) -> None:
    """À appeler après la validation de l'action : enregistre les notifications, puis envoie
    un e-mail dans la langue de chacun si `email` (les champs du gabarit) est fourni.

    `besides` : l'auteur de l'action, qui n'a pas à être prévenu de ce qu'il vient de faire.
    """
    users = [u for u in {u.id: u for u in recipients}.values() if u.id != besides]
    for user in users:
        session.add(Notification(user_id=user.id, kind=kind, params=params or {}, link=link))
    session.commit()
    if email is None or kind not in mail.TEMPLATES:
        return
    base = get_settings().frontend_url
    for user in users:
        subject, text = mail.render(kind, user.locale, link=f"{base}/{user.locale}/{link}", **email)
        try:
            send_email(user.email, subject, text)
        except Exception:
            # La notification est enregistrée et visible dans l'espace : un e-mail perdu ne l'annule pas.
            logger.exception("notification_email_failed", extra={"kind": kind})


# --- Lecture par l'utilisateur ---------------------------------------------------------


def latest(session: Session, user: User) -> tuple[list[Notification], int]:
    items = list(
        session.scalars(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.id.desc())
            .limit(LIST_SIZE)
        )
    )
    unread = session.scalars(
        select(Notification.id).where(Notification.user_id == user.id, Notification.read_at.is_(None))
    ).all()
    return items, len(unread)


def mark_read(session: Session, user: User, ids: list[uuid.UUID] | None) -> None:
    """Sans liste : tout marquer comme lu. Le filtre sur l'utilisateur fait le cloisonnement."""
    query = update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
    if ids is not None:
        query = query.where(Notification.id.in_(ids))
    session.execute(query.values(read_at=datetime.now(UTC)))
