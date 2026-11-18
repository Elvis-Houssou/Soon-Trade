"""Demandes d'achat : création, modification et machine à états."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError, Conflict, NotFound
from app.modules.audit.models import record
from app.modules.catalog.models import Category
from app.modules.identity.models import Organization, User
from app.modules.notifications import service as notifications
from app.modules.purchase_requests.models import PurchaseRequest, PurchaseRequestEvent

# action -> (états de départ permis, état d'arrivée). Toute autre combinaison répond 409.
# À VALIDER : l'annulation depuis « informations demandées » n'est pas dans le schéma de
# référence ; elle est permise pour qu'un acheteur ne reste pas bloqué.
TRANSITIONS: dict[str, tuple[frozenset[str], str]] = {
    "submit": (frozenset({"draft", "info_requested"}), "submitted"),
    "request_info": (frozenset({"submitted"}), "info_requested"),
    "qualify": (frozenset({"submitted"}), "qualified"),
    "reject": (frozenset({"submitted"}), "rejected"),
    "open_sourcing": (frozenset({"qualified"}), "in_sourcing"),
    # Posées par le module des propositions, jamais appelées directement par une route.
    "proposal_sent": (frozenset({"in_sourcing"}), "proposal_sent"),
    "proposal_reopened": (frozenset({"proposal_sent"}), "in_sourcing"),
    "proposal_accepted": (frozenset({"proposal_sent"}), "accepted"),
    "proposal_refused": (frozenset({"proposal_sent"}), "closed"),
    "cancel": (
        frozenset({"draft", "submitted", "info_requested", "qualified", "in_sourcing"}),
        "cancelled",
    ),
}
# Historique, auteurs et acheteur chargés avec la liste, pas une requête par ligne.
_LISTED = (
    selectinload(PurchaseRequest.history).selectinload(PurchaseRequestEvent.actor),
    selectinload(PurchaseRequest.organization),
)
EDITABLE = frozenset({"draft", "info_requested"})
REQUIRED = frozenset({"product_name", "quantity", "unit", "delivery_location"})


def _clean(fields: dict[str, Any]) -> dict[str, Any]:
    return {k: (v.strip() or None) if isinstance(v, str) else v for k, v in fields.items()}


def _check_category(session: Session, category_id: uuid.UUID | None) -> None:
    if category_id is None:
        return
    category = session.get(Category, category_id)
    if not category or not category.is_active:
        raise AppError("Cette catégorie n'est pas disponible.")


def list_for_organization(session: Session, organization: Organization) -> list[PurchaseRequest]:
    # shortcut: pas de pagination ; à ajouter quand un acheteur dépassera quelques centaines de demandes.
    return list(
        session.scalars(
            select(PurchaseRequest)
            .options(*_LISTED)
            .where(PurchaseRequest.organization_id == organization.id)
            .order_by(PurchaseRequest.number.desc())
        )
    )


def list_all(session: Session) -> list[PurchaseRequest]:
    """Vue interne. Les brouillons restent privés à l'acheteur tant qu'ils ne sont pas soumis."""
    return list(
        session.scalars(
            select(PurchaseRequest)
            .options(*_LISTED)
            .where(PurchaseRequest.status != "draft")
            .order_by(PurchaseRequest.number.desc())
        )
    )


def get(
    session: Session,
    request_id: uuid.UUID,
    *,
    organization: Organization | None = None,
    lock: bool = False,
) -> PurchaseRequest:
    """`organization` fait le cloisonnement : la demande d'un autre acheteur est « introuvable »."""
    query = select(PurchaseRequest).where(PurchaseRequest.id == request_id)
    if organization is not None:
        query = query.where(PurchaseRequest.organization_id == organization.id)
    else:
        query = query.where(PurchaseRequest.status != "draft")
    if lock:
        # Deux actions simultanées sur la même demande passent l'une après l'autre.
        query = query.with_for_update()
    request = session.scalar(query)
    if not request:
        raise NotFound("Demande introuvable.")
    return request


def create(
    session: Session, organization: Organization, fields: dict[str, Any], *, actor: User, ip: str | None
) -> PurchaseRequest:
    _check_category(session, fields.get("category_id"))
    # L'organisation vient de la session, jamais de la requête.
    request = PurchaseRequest(organization_id=organization.id, created_by_id=actor.id, **_clean(fields))
    session.add(request)
    session.flush()
    session.add(PurchaseRequestEvent(request_id=request.id, actor_id=actor.id, to_status="draft"))
    record(session, "purchase_request.created", request.reference, actor_id=actor.id, ip=ip)
    return request


def update(
    session: Session, request: PurchaseRequest, changes: dict[str, Any], *, actor: User, ip: str | None
) -> None:
    if request.status not in EDITABLE:
        raise Conflict("Cette demande n'est plus modifiable.")
    if "category_id" in changes:
        _check_category(session, changes["category_id"])
    for field, value in _clean(changes).items():
        if value is None and field in REQUIRED:
            raise AppError("Ce champ est obligatoire.")
        setattr(request, field, value)
    record(
        session,
        "purchase_request.updated",
        request.reference,
        actor_id=actor.id,
        ip=ip,
        fields=sorted(changes),
    )


def transition(
    session: Session,
    request: PurchaseRequest,
    action: str,
    *,
    actor: User,
    ip: str | None,
    message: str | None = None,
) -> None:
    sources, target = TRANSITIONS[action]
    if request.status not in sources:
        raise Conflict("Cette action n'est pas possible dans l'état actuel de la demande.")
    message = message.strip() or None if message else None
    session.add(
        PurchaseRequestEvent(
            request_id=request.id,
            actor_id=actor.id,
            from_status=request.status,
            to_status=target,
            message=message,
        )
    )
    record(
        session,
        f"purchase_request.{action}",
        request.reference,
        actor_id=actor.id,
        ip=ip,
        previous=request.status,
        status=target,
    )
    request.status = target
    session.flush()
    session.refresh(request, ["history"])


def notify_buyer(session: Session, request: PurchaseRequest, action: str) -> None:
    """Après validation : l'acheteur est prévenu quand SOON TRADE attend quelque chose de lui
    ou ne retient pas sa demande. Le message lui-même reste dans l'espace."""
    kind = {"request_info": "request_info_requested", "reject": "request_rejected"}.get(action)
    if kind is None:
        return
    notifications.notify(
        session,
        notifications.members(session, request.organization_id),
        kind,
        link="buyer/demandes",
        params={"reference": request.reference},
        email={"reference": request.reference},
    )
