"""Commandes, bons de commande fournisseurs et livraisons."""

import logging
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, Conflict, NotFound
from app.modules.audit.models import record
from app.modules.documents.models import Document
from app.modules.identity.models import Organization, User
from app.modules.notifications import service as notifications
from app.modules.orders.models import (
    TERMS_SCHEMA,
    Delivery,
    DeliveryEvent,
    DeliveryProof,
    Order,
    OrderEvent,
    SupplierOrder,
)
from app.modules.proposals.models import BuyerProposal, BuyerProposalLine

logger = logging.getLogger(__name__)

# action manuelle -> (états de départ permis, état d'arrivée). Expédition, livraison et
# litige se posent d'eux-mêmes, au fil des livraisons et des réclamations.
ORDER_ACTIONS: dict[str, tuple[frozenset[str], str]] = {
    # À VALIDER : la confirmation n'attend pas encore le paiement (Phase 9).
    "confirm": (frozenset({"created"}), "confirmed"),
    "prepare": (frozenset({"confirmed"}), "in_preparation"),
    "cancel": (frozenset({"created", "confirmed", "in_preparation"}), "cancelled"),
    "close": (frozenset({"delivered"}), "closed"),
}
# Où une nouvelle livraison peut être planifiée.
DELIVERY_PLANNABLE = frozenset({"confirmed", "in_preparation", "shipped"})
DELIVERY_ACTIONS: dict[str, tuple[frozenset[str], str]] = {
    "prepare": (frozenset({"planned"}), "in_preparation"),
    "ship": (frozenset({"planned", "in_preparation"}), "in_transit"),
    "deliver": (frozenset({"in_transit"}), "delivered"),
    "confirm": (frozenset({"delivered"}), "confirmed"),
    "incident": (frozenset({"in_transit", "delivered"}), "incident"),
    "resume": (frozenset({"incident"}), "in_transit"),
}
# Ce que le fournisseur peut faire sur la livraison de son bon ; le reste revient à la logistique.
SUPPLIER_DELIVERY_ACTIONS = frozenset({"prepare", "ship", "deliver"})
ARRIVED = frozenset({"delivered", "confirmed"})


def _clean(value: str | None) -> str | None:
    return value.strip() or None if value else None


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


def set_status(
    session: Session,
    order: Order,
    target: str,
    *,
    actor: User | None,
    ip: str | None,
    message: str | None = None,
) -> None:
    previous = order.status
    # Par la collection : une réponse construite dans la même requête voit l'événement.
    order.events.append(
        OrderEvent(
            order_id=order.id,
            actor_id=actor.id if actor else None,
            from_status=previous,
            to_status=target,
            message=_clean(message),
        )
    )
    record(
        session,
        f"order.{target}",
        order.reference,
        actor_id=actor.id if actor else None,
        ip=ip,
        previous=previous,
        status=target,
    )
    order.status = target


# --- Création depuis une proposition acceptée -------------------------------------


def _line_terms(line: BuyerProposalLine, unit_price: Decimal) -> dict[str, str]:
    """Ligne figée au prix donné : prix de vente pour l'acheteur, prix d'achat pour le fournisseur."""
    return {
        "product_name": line.product_name,
        "quantity": str(line.quantity),
        "unit": line.unit,
        "unit_price": _money(unit_price),
        "total": _money(unit_price * line.quantity),
    }


def create_from_proposal(session: Session, proposal: BuyerProposal, *, actor: User, ip: str | None) -> Order:
    """Appelée dans la transaction de l'acceptation : la commande et la décision vont ensemble."""
    version = next(v for v in proposal.versions if v.version == proposal.accepted_version)
    terms = {
        "schema": TERMS_SCHEMA,
        "proposal_reference": proposal.reference,
        "version": version.version,
        "currency": version.currency,
        "lead_time_days": version.lead_time_days,
        "valid_until": version.valid_until.isoformat(),
        "delivery_location": version.delivery_location,
        "conditions": version.conditions,
        "message": version.message,
        "lines": [_line_terms(line, line.unit_price) for line in version.lines],
    }
    order = Order(
        proposal_id=proposal.id,
        organization_id=proposal.request.organization_id,
        created_by_id=actor.id,
        currency=version.currency,
        buyer_total=version.total,
        terms=terms,
    )
    # Une part par offre fournisseur reprise ; les lignes libres (transport…) restent à SOON TRADE.
    by_offer: dict[uuid.UUID, list[BuyerProposalLine]] = defaultdict(list)
    for line in version.lines:
        if line.offer_id is not None:
            by_offer[line.offer_id].append(line)
    for lines in by_offer.values():
        offer = lines[0].offer
        costs = [(line, line.supplier_unit_price) for line in lines]
        if offer is None or any(price is None for _, price in costs):
            raise AppError("Une ligne reprise d'une offre n'a pas de prix d'achat.")
        order.supplier_orders.append(
            SupplierOrder(
                organization_id=offer.solicitation.organization_id,
                offer_id=offer.id,
                currency=version.currency,
                supplier_total=sum(
                    (Decimal(price or 0) * line.quantity for line, price in costs), Decimal("0")
                ).quantize(Decimal("0.01")),
                terms={
                    "schema": TERMS_SCHEMA,
                    "currency": version.currency,
                    "lead_time_days": offer.current.lead_time_days,
                    "delivery_location": version.delivery_location,
                    "lines": [_line_terms(line, Decimal(price or 0)) for line, price in costs],
                },
            )
        )
    session.add(order)
    session.flush()
    order.events.append(OrderEvent(actor_id=actor.id, to_status="created"))
    record(session, "order.created", order.reference, actor_id=actor.id, ip=ip, proposal=proposal.reference)
    return order


# --- Vue interne ---------------------------------------------------------------------


def list_all(session: Session) -> list[Order]:
    # shortcut: pas de pagination ; à ajouter quand le volume le demandera.
    return list(session.scalars(select(Order).order_by(Order.number.desc())))


def get(session: Session, order_id: uuid.UUID, *, lock: bool = False) -> Order:
    query = select(Order).where(Order.id == order_id)
    order = session.scalar(query.with_for_update() if lock else query)
    if not order:
        raise NotFound("Commande introuvable.")
    return order


def act(
    session: Session, order: Order, action: str, *, actor: User, ip: str | None, message: str | None = None
) -> None:
    sources, target = ORDER_ACTIONS[action]
    if order.status not in sources:
        raise Conflict("Cette action n'est pas possible dans l'état actuel de la commande.")
    if action == "cancel":
        if not _clean(message):
            raise AppError("Indiquez le motif de l'annulation : il sera lu par l'acheteur.")
        if any(d.status not in ("planned", "in_preparation") for d in order.deliveries):
            raise Conflict("Une livraison est déjà partie : la commande ne s'annule plus.")
    if action == "close" and any(d.status not in ARRIVED for d in order.deliveries):
        raise Conflict("Toutes les livraisons doivent être arrivées avant la clôture.")
    if action == "confirm":
        now = datetime.now(UTC)
        order.confirmed_at = now
        for part in order.supplier_orders:
            part.released_at = now
    set_status(session, order, target, actor=actor, ip=ip, message=message)
    session.flush()
    session.refresh(order, ["events"])


def notify_confirmed(session: Session, order: Order) -> None:
    """Après validation : l'acheteur apprend la confirmation ; chaque fournisseur reçoit son bon."""
    notifications.notify(
        session,
        notifications.members(session, order.organization_id),
        "order_confirmed",
        link=f"buyer/commandes?id={order.id}",
        params={"reference": order.reference},
        email={"reference": order.reference},
    )
    for part in order.supplier_orders:
        notifications.notify(
            session,
            notifications.members(session, part.organization_id),
            "supplier_order_received",
            link=f"supplier/commandes?id={part.id}",
            params={"reference": part.reference},
            email={"reference": part.reference},
        )


def notify_delivery(session: Session, delivery: Delivery, action: str) -> None:
    """Après validation : l'acheteur suit le départ et l'arrivée de ses livraisons."""
    kind = {"ship": "delivery_shipped", "deliver": "delivery_delivered"}.get(action)
    if kind is None:
        return
    order = delivery.order
    params = {"reference": delivery.reference, "order": order.reference}
    notifications.notify(
        session,
        notifications.members(session, order.organization_id),
        kind,
        link=f"buyer/commandes?id={order.id}",
        params=params,
        email=params,
    )


# --- Livraisons ------------------------------------------------------------------------


def get_delivery(session: Session, delivery_id: uuid.UUID, *, lock: bool = False) -> Delivery:
    query = select(Delivery).where(Delivery.id == delivery_id)
    delivery = session.scalar(query.with_for_update() if lock else query)
    if not delivery:
        raise NotFound("Livraison introuvable.")
    return delivery


def plan_delivery(
    session: Session, order: Order, fields: dict[str, Any], *, actor: User, ip: str | None
) -> Delivery:
    if order.status not in DELIVERY_PLANNABLE:
        raise Conflict("Une livraison ne se planifie que sur une commande confirmée et non livrée.")
    part_id = fields.pop("supplier_order_id", None)
    if part_id is not None and not any(p.id == part_id for p in order.supplier_orders):
        raise NotFound("Bon de commande introuvable.")
    description = _clean(fields.pop("description"))
    if not description:
        raise AppError("Ce champ est obligatoire.")
    delivery = Delivery(
        order_id=order.id,
        supplier_order_id=part_id,
        created_by_id=actor.id,
        description=description,
        planned_date=fields["planned_date"],
        carrier=_clean(fields.get("carrier")),
        tracking_number=_clean(fields.get("tracking_number")),
    )
    session.add(delivery)
    session.flush()
    delivery.events.append(DeliveryEvent(actor_id=actor.id, to_status="planned"))
    record(session, "delivery.planned", delivery.reference, actor_id=actor.id, ip=ip, order=order.reference)
    session.flush()
    session.refresh(order, ["deliveries"])
    return delivery


def update_delivery(
    session: Session, delivery: Delivery, changes: dict[str, Any], *, actor: User, ip: str | None
) -> None:
    if delivery.status in ARRIVED:
        raise Conflict("Une livraison arrivée ne se modifie plus.")
    for field, value in changes.items():
        value = _clean(value) if isinstance(value, str) else value
        if value is None and field in ("description", "planned_date"):
            raise AppError("Ce champ est obligatoire.")
        setattr(delivery, field, value)
    record(session, "delivery.updated", delivery.reference, actor_id=actor.id, ip=ip, fields=sorted(changes))


def _sync_order(session: Session, order: Order, *, ip: str | None) -> None:
    """Expédiée dès qu'une livraison part ; livrée quand toutes sont arrivées. Pendant un
    litige, c'est le statut à retrouver qui avance."""
    current = (order.status_before_dispute or "delivered") if order.status == "in_dispute" else order.status
    deliveries = order.deliveries
    target = current
    if current in ("confirmed", "in_preparation") and any(d.shipped_at for d in deliveries):
        target = "shipped"
    if target == "shipped" and deliveries and all(d.status in ARRIVED for d in deliveries):
        target = "delivered"
    if target == current:
        return
    if order.status == "in_dispute":
        order.status_before_dispute = target
        record(session, "order.dispute_status_updated", order.reference, actor_id=None, ip=ip, status=target)
    else:
        set_status(session, order, target, actor=None, ip=ip)


def move_delivery(
    session: Session,
    delivery: Delivery,
    action: str,
    *,
    actor: User,
    ip: str | None,
    message: str | None = None,
) -> None:
    sources, target = DELIVERY_ACTIONS[action]
    previous = delivery.status
    if previous not in sources:
        raise Conflict("Cette action n'est pas possible dans l'état actuel de la livraison.")
    if delivery.order.status in ("cancelled", "closed", "created"):
        raise Conflict("Cette commande n'est plus suivie.")
    if action == "incident" and not _clean(message):
        raise AppError("Décrivez l'incident.")
    now = datetime.now(UTC)
    if action == "ship":
        delivery.shipped_at = now
    elif action == "deliver":
        delivery.delivered_at = now
    elif action == "confirm":
        delivery.confirmed_at = now
    delivery.events.append(
        DeliveryEvent(
            delivery_id=delivery.id,
            actor_id=actor.id,
            from_status=previous,
            to_status=target,
            message=_clean(message),
        )
    )
    record(
        session,
        f"delivery.{action}",
        delivery.reference,
        actor_id=actor.id,
        ip=ip,
        previous=previous,
        status=target,
    )
    delivery.status = target
    session.flush()
    _sync_order(session, delivery.order, ip=ip)
    session.flush()
    session.refresh(delivery, ["events"])


def add_proof(
    session: Session,
    delivery: Delivery,
    document: Document,
    *,
    organization: Organization,
    buyer_visible: bool,
    actor: User,
    ip: str | None,
) -> None:
    """`document` vient d'être déposé par l'organisation de celui qui l'ajoute."""
    session.add(
        DeliveryProof(
            delivery_id=delivery.id,
            document_id=document.id,
            added_by_id=actor.id,
            # Seule l'équipe SOON TRADE publie une preuve à l'acheteur.
            buyer_visible=buyer_visible and organization.kind == "internal",
        )
    )
    record(
        session,
        "delivery.proof_added",
        delivery.reference,
        actor_id=actor.id,
        ip=ip,
        document=str(document.id),
    )
    session.flush()
    session.refresh(delivery, ["proofs"])


def proof_of(delivery: Delivery, document_id: uuid.UUID) -> DeliveryProof:
    proof = next((p for p in delivery.proofs if p.document_id == document_id), None)
    if proof is None:
        raise NotFound("Document introuvable.")
    return proof


# --- Côté acheteur --------------------------------------------------------------------


def list_for_buyer(session: Session, organization: Organization) -> list[Order]:
    return list(
        session.scalars(
            select(Order).where(Order.organization_id == organization.id).order_by(Order.number.desc())
        )
    )


def get_for_buyer(session: Session, organization: Organization, order_id: uuid.UUID) -> Order:
    order = session.scalar(
        select(Order).where(Order.id == order_id, Order.organization_id == organization.id)
    )
    if not order:
        raise NotFound("Commande introuvable.")
    return order


def buyer_delivery(
    session: Session, organization: Organization, delivery_id: uuid.UUID, *, lock: bool = False
) -> Delivery:
    query = (
        select(Delivery)
        .join(Order, Order.id == Delivery.order_id)
        .where(Delivery.id == delivery_id, Order.organization_id == organization.id)
    )
    delivery = session.scalar(query.with_for_update(of=Delivery) if lock else query)
    if not delivery:
        raise NotFound("Livraison introuvable.")
    return delivery


# --- Côté fournisseur -------------------------------------------------------------------


def list_for_supplier(session: Session, organization: Organization) -> list[SupplierOrder]:
    """Seulement ses bons, et seulement une fois la commande confirmée."""
    return list(
        session.scalars(
            select(SupplierOrder)
            .where(SupplierOrder.organization_id == organization.id, SupplierOrder.released_at.is_not(None))
            .order_by(SupplierOrder.number.desc())
        )
    )


def get_for_supplier(session: Session, organization: Organization, part_id: uuid.UUID) -> SupplierOrder:
    part = session.scalar(
        select(SupplierOrder).where(
            SupplierOrder.id == part_id,
            SupplierOrder.organization_id == organization.id,
            SupplierOrder.released_at.is_not(None),
        )
    )
    if not part:
        raise NotFound("Bon de commande introuvable.")
    return part


def supplier_delivery(
    session: Session, organization: Organization, delivery_id: uuid.UUID, *, lock: bool = False
) -> Delivery:
    query = (
        select(Delivery)
        .join(SupplierOrder, SupplierOrder.id == Delivery.supplier_order_id)
        .where(
            Delivery.id == delivery_id,
            SupplierOrder.organization_id == organization.id,
            SupplierOrder.released_at.is_not(None),
        )
    )
    delivery = session.scalar(query.with_for_update(of=Delivery) if lock else query)
    if not delivery:
        raise NotFound("Livraison introuvable.")
    return delivery
