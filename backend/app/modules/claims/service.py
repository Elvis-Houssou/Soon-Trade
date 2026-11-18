"""Réclamations des acheteurs : ouverture, prise en charge, résolution, litige de commande."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, Conflict, NotFound
from app.modules.audit.models import record
from app.modules.claims.models import Claim, ClaimEvent
from app.modules.identity.models import Organization, User
from app.modules.identity.permissions import CLAIM_HANDLE
from app.modules.notifications import service as notifications
from app.modules.orders import service as orders
from app.modules.orders.models import Order

# À VALIDER : une réclamation s'ouvre de la confirmation à la livraison, pas après clôture.
CLAIMABLE = frozenset({"confirmed", "in_preparation", "shipped", "delivered", "in_dispute"})
# Le schéma de référence : seule une commande partie peut passer en litige.
DISPUTABLE = frozenset({"shipped", "delivered"})
ACTIVE = frozenset({"open", "under_review"})
# action -> (états de départ permis, état d'arrivée).
ACTIONS: dict[str, tuple[frozenset[str], str]] = {
    "review": (frozenset({"open"}), "under_review"),
    "resolve": (frozenset({"under_review"}), "resolved"),
    "reject": (frozenset({"under_review"}), "rejected"),
    "close": (frozenset({"resolved", "rejected"}), "closed"),
}
# Réponses de SOON TRADE : elles sont lues par l'acheteur, un message est donc exigé.
NEEDS_ANSWER = frozenset({"resolve", "reject"})


def _clean(value: str | None) -> str | None:
    return value.strip() or None if value else None


def _event(
    session: Session, claim: Claim, target: str, *, actor: User, ip: str | None, message: str | None = None
) -> None:
    previous = None if target == "open" and not claim.events else claim.status
    claim.events.append(
        ClaimEvent(
            claim_id=claim.id,
            actor_id=actor.id,
            from_status=previous,
            to_status=target,
            message=_clean(message),
        )
    )
    record(
        session,
        f"claim.{target}",
        claim.reference,
        actor_id=actor.id,
        ip=ip,
        previous=previous,
        status=target,
    )
    claim.status = target


def _active_claims(session: Session, order: Order, *, besides: uuid.UUID | None = None) -> int:
    query = select(Claim.id).where(Claim.order_id == order.id, Claim.status.in_(ACTIVE))
    if besides is not None:
        query = query.where(Claim.id != besides)
    return len(list(session.scalars(query)))


def _end_dispute_if_last(session: Session, claim: Claim, *, actor: User, ip: str | None) -> None:
    order = orders.get(session, claim.order_id, lock=True)
    if order.status == "in_dispute" and _active_claims(session, order, besides=claim.id) == 0:
        target = order.status_before_dispute or "delivered"
        order.status_before_dispute = None
        orders.set_status(session, order, target, actor=actor, ip=ip)


# --- Côté acheteur ---------------------------------------------------------------------


def open_claim(
    session: Session, organization: Organization, fields: dict[str, Any], *, actor: User, ip: str | None
) -> Claim:
    order = orders.get_for_buyer(session, organization, fields.pop("order_id"))
    order = orders.get(session, order.id, lock=True)
    if order.status not in CLAIMABLE:
        raise Conflict("Cette commande n'accepte pas de réclamation dans son état actuel.")
    delivery_id = fields.pop("delivery_id", None)
    if delivery_id is not None and not any(d.id == delivery_id for d in order.deliveries):
        raise NotFound("Livraison introuvable.")
    subject, description = _clean(fields.pop("subject")), _clean(fields.pop("description"))
    if not subject or not description:
        raise AppError("Ce champ est obligatoire.")
    claim = Claim(
        order_id=order.id,
        organization_id=organization.id,
        delivery_id=delivery_id,
        created_by_id=actor.id,
        subject=subject,
        description=description,
        **fields,
    )
    session.add(claim)
    session.flush()
    _event(session, claim, "open", actor=actor, ip=ip)
    if order.status in DISPUTABLE:
        order.status_before_dispute = order.status
        orders.set_status(session, order, "in_dispute", actor=None, ip=ip)
    session.flush()
    session.refresh(claim, ["events"])
    return claim


def list_for_buyer(session: Session, organization: Organization) -> list[Claim]:
    return list(
        session.scalars(
            select(Claim).where(Claim.organization_id == organization.id).order_by(Claim.number.desc())
        )
    )


def get_for_buyer(
    session: Session, organization: Organization, claim_id: uuid.UUID, *, lock: bool = False
) -> Claim:
    query = select(Claim).where(Claim.id == claim_id, Claim.organization_id == organization.id)
    claim = session.scalar(query.with_for_update() if lock else query)
    if not claim:
        raise NotFound("Réclamation introuvable.")
    return claim


def buyer_close(session: Session, claim: Claim, *, actor: User, ip: str | None) -> None:
    """L'acheteur prend acte de la réponse et clôt lui-même sa réclamation."""
    if claim.status not in ACTIONS["close"][0]:
        raise Conflict("Cette réclamation attend encore une réponse de SOON TRADE.")
    _event(session, claim, "closed", actor=actor, ip=ip)
    session.flush()
    session.refresh(claim, ["events"])


# --- Vue interne --------------------------------------------------------------------------


def list_all(session: Session) -> list[Claim]:
    return list(session.scalars(select(Claim).order_by(Claim.number.desc())))


def get(session: Session, claim_id: uuid.UUID, *, lock: bool = False) -> Claim:
    query = select(Claim).where(Claim.id == claim_id)
    claim = session.scalar(query.with_for_update() if lock else query)
    if not claim:
        raise NotFound("Réclamation introuvable.")
    return claim


def act(
    session: Session, claim: Claim, action: str, *, actor: User, ip: str | None, message: str | None = None
) -> None:
    sources, target = ACTIONS[action]
    if claim.status not in sources:
        raise Conflict("Cette action n'est pas possible dans l'état actuel de la réclamation.")
    if action in NEEDS_ANSWER:
        answer = _clean(message)
        if not answer:
            raise AppError("Rédigez la réponse à l'acheteur.")
        claim.resolution = answer
        _end_dispute_if_last(session, claim, actor=actor, ip=ip)
    _event(session, claim, target, actor=actor, ip=ip, message=message)
    session.flush()
    session.refresh(claim, ["events"])


def notify_opened(session: Session, claim: Claim) -> None:
    """Après validation : ceux qui prennent en charge les réclamations sont prévenus."""
    notifications.notify(
        session,
        notifications.staff_with(session, CLAIM_HANDLE),
        "claim_opened",
        link="internal/reclamations",
        params={"reference": claim.reference, "buyer": claim.buyer_name},
    )


def notify_answered(session: Session, claim: Claim) -> None:
    """Après validation : l'acheteur apprend que SOON TRADE a répondu (la réponse reste dans l'espace)."""
    notifications.notify(
        session,
        notifications.members(session, claim.organization_id),
        "claim_answered",
        link="buyer/reclamations",
        params={"reference": claim.reference},
        email={"reference": claim.reference},
    )
