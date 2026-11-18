import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Form, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field

from app.core import storage
from app.core.config import get_settings
from app.core.errors import NotFound
from app.modules.audit.models import record
from app.modules.documents.router import DownloadOut, save_upload
from app.modules.identity.deps import CurrentPrincipal, DbSession, Principal, client_ip, require_permission
from app.modules.identity.permissions import (
    DELIVERY_CONFIRM,
    DELIVERY_UPDATE,
    LOGISTICS_MANAGE,
    ORDER_MANAGE,
    ORDER_READ_ALL,
    ORDER_VIEW,
    SUPPLIER_ORDER_VIEW,
)
from app.modules.orders import service
from app.modules.orders.models import Delivery, DeliveryProof, Order, SupplierOrder

router = APIRouter(tags=["orders"])

Message = Annotated[str, Field(max_length=2000)]
Short = Annotated[str, Field(max_length=120)]


# --- Copies figées ----------------------------------------------------------------------


class LineOut(BaseModel):
    product_name: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    total: Decimal


class TermsOut(BaseModel):
    """Conditions acceptées par l'acheteur, telles qu'enregistrées à la création de la commande."""

    proposal_reference: str
    version: int
    currency: str
    lead_time_days: int
    valid_until: date
    delivery_location: str
    conditions: str | None
    message: str | None
    lines: list[LineOut]


class SupplierTermsOut(BaseModel):
    """La part du fournisseur, à son prix : ni acheteur, ni prix de vente."""

    currency: str
    lead_time_days: int
    delivery_location: str
    lines: list[LineOut]


# --- Livraisons ------------------------------------------------------------------------------


class ProofOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str


class InternalProofOut(ProofOut):
    buyer_visible: bool


class StatusEventOut(BaseModel):
    """Sans nom ni message : l'acheteur et le fournisseur suivent l'état, pas l'équipe."""

    model_config = ConfigDict(from_attributes=True)

    created_at: datetime
    to_status: str


class InternalStatusEventOut(StatusEventOut):
    from_status: str | None
    actor_name: str | None
    message: str | None


class DeliveryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference: str
    status: str
    description: str
    planned_date: date
    carrier: str | None
    tracking_number: str | None
    shipped_at: datetime | None
    delivered_at: datetime | None
    confirmed_at: datetime | None
    proofs: list[ProofOut]
    history: list[StatusEventOut]


class InternalDeliveryOut(DeliveryOut):
    order_id: uuid.UUID
    order_reference: str
    supplier_order_id: uuid.UUID | None
    supplier_order_reference: str | None
    supplier_name: str | None
    proofs: list[InternalProofOut]  # type: ignore[assignment]
    history: list[InternalStatusEventOut]  # type: ignore[assignment]


def _delivery(delivery: Delivery, proofs: list[DeliveryProof]) -> DeliveryOut:
    return DeliveryOut.model_validate(
        {**_fields(delivery), "proofs": proofs, "history": delivery.events}, from_attributes=True
    )


def _fields(delivery: Delivery) -> dict[str, Any]:
    return {
        name: getattr(delivery, name)
        for name in DeliveryOut.model_fields
        if name not in ("proofs", "history")
    }


def _internal_delivery(delivery: Delivery) -> InternalDeliveryOut:
    return InternalDeliveryOut.model_validate(
        {
            **_fields(delivery),
            "order_id": delivery.order_id,
            "order_reference": delivery.order_reference,
            "supplier_order_id": delivery.supplier_order_id,
            "supplier_order_reference": delivery.supplier_order_reference,
            "supplier_name": delivery.supplier_name,
            "proofs": delivery.proofs,
            "history": delivery.events,
        },
        from_attributes=True,
    )


def _buyer_delivery(delivery: Delivery) -> DeliveryOut:
    return _delivery(delivery, [p for p in delivery.proofs if p.buyer_visible])


def _supplier_delivery(delivery: Delivery, organization_id: uuid.UUID) -> DeliveryOut:
    return _delivery(delivery, [p for p in delivery.proofs if p.document.organization_id == organization_id])


# --- Commandes -------------------------------------------------------------------------------


class OrderEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    created_at: datetime
    to_status: str
    message: str | None


class InternalOrderEventOut(OrderEventOut):
    from_status: str | None
    actor_name: str | None


class BuyerOrderOut(BaseModel):
    """Ni fournisseur, ni bon de commande, ni prix d'achat."""

    id: uuid.UUID
    reference: str
    status: str
    created_at: datetime
    confirmed_at: datetime | None
    request_reference: str
    currency: str
    total: Decimal
    terms: TermsOut
    deliveries: list[DeliveryOut]
    history: list[OrderEventOut]

    @classmethod
    def of(cls, order: Order) -> BuyerOrderOut:
        return cls(
            id=order.id,
            reference=order.reference,
            status=order.status,
            created_at=order.created_at,
            confirmed_at=order.confirmed_at,
            request_reference=order.request_reference,
            currency=order.currency,
            total=order.buyer_total,
            terms=TermsOut.model_validate(order.terms),
            deliveries=[_buyer_delivery(d) for d in order.deliveries],
            history=[OrderEventOut.model_validate(e) for e in order.events],
        )


class SupplierOrderOut(BaseModel):
    id: uuid.UUID
    reference: str
    status: str
    released_at: datetime | None
    currency: str
    total: Decimal
    terms: SupplierTermsOut
    deliveries: list[DeliveryOut]

    @classmethod
    def of(cls, part: SupplierOrder) -> SupplierOrderOut:
        return cls(
            id=part.id,
            reference=part.reference,
            status=part.supplier_state,
            released_at=part.released_at,
            currency=part.currency,
            total=part.supplier_total,
            terms=SupplierTermsOut.model_validate(part.terms),
            deliveries=[_supplier_delivery(d, part.organization_id) for d in part.deliveries],
        )


class InternalPartOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference: str
    supplier_name: str
    released_at: datetime | None
    supplier_total: Decimal
    terms: SupplierTermsOut


class InternalOrderOut(BaseModel):
    id: uuid.UUID
    reference: str
    status: str
    status_before_dispute: str | None
    created_at: datetime
    confirmed_at: datetime | None
    buyer_name: str
    proposal_reference: str
    request_reference: str
    currency: str
    buyer_total: Decimal
    cost_total: Decimal
    margin: Decimal
    terms: TermsOut
    supplier_orders: list[InternalPartOut]
    deliveries: list[InternalDeliveryOut]
    events: list[InternalOrderEventOut]

    @classmethod
    def of(cls, order: Order) -> InternalOrderOut:
        cost = sum((p.supplier_total for p in order.supplier_orders), Decimal("0.00"))
        return cls(
            id=order.id,
            reference=order.reference,
            status=order.status,
            status_before_dispute=order.status_before_dispute,
            created_at=order.created_at,
            confirmed_at=order.confirmed_at,
            buyer_name=order.buyer_name,
            proposal_reference=order.proposal_reference,
            request_reference=order.request_reference,
            currency=order.currency,
            buyer_total=order.buyer_total,
            cost_total=cost,
            margin=order.buyer_total - cost,
            terms=TermsOut.model_validate(order.terms),
            supplier_orders=[InternalPartOut.model_validate(p) for p in order.supplier_orders],
            deliveries=[_internal_delivery(d) for d in order.deliveries],
            events=[InternalOrderEventOut.model_validate(e) for e in order.events],
        )


class DeliveryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: Annotated[str, Field(min_length=2, max_length=500)]
    planned_date: date
    carrier: Short | None = None
    tracking_number: Short | None = None
    supplier_order_id: uuid.UUID | None = None


class DeliveryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: Annotated[str, Field(min_length=2, max_length=500)] | None = None
    planned_date: date | None = None
    carrier: Short | None = None
    tracking_number: Short | None = None


class TrackingPatch(BaseModel):
    """Ce que le fournisseur renseigne sur sa livraison."""

    model_config = ConfigDict(extra="forbid")

    carrier: Short | None = None
    tracking_number: Short | None = None


class ReasonIn(BaseModel):
    message: Message | None = None


# --- Espace interne ------------------------------------------------------------------------------

Reader = Annotated[Principal, Depends(require_permission(ORDER_READ_ALL))]
Manager = Annotated[Principal, Depends(require_permission(ORDER_MANAGE))]
Logistics = Annotated[Principal, Depends(require_permission(LOGISTICS_MANAGE))]


@router.get("/internal/orders")
def list_orders(session: DbSession, _: Reader) -> list[InternalOrderOut]:
    return [InternalOrderOut.of(o) for o in service.list_all(session)]


@router.get("/internal/orders/{order_id}")
def get_order(order_id: uuid.UUID, session: DbSession, _: Reader) -> InternalOrderOut:
    return InternalOrderOut.of(service.get(session, order_id))


def _act(
    session: DbSession,
    principal: Principal,
    request: Request,
    order_id: uuid.UUID,
    action: str,
    message: str | None,
) -> InternalOrderOut:
    order = service.get(session, order_id, lock=True)
    service.act(session, order, action, actor=principal.user, ip=client_ip(request), message=message)
    session.commit()
    if action == "confirm":
        service.notify_confirmed(session, order)
    return InternalOrderOut.of(order)


@router.post("/internal/orders/{order_id}/deliveries", status_code=status.HTTP_201_CREATED)
def plan_delivery(
    order_id: uuid.UUID, body: DeliveryIn, request: Request, session: DbSession, principal: Logistics
) -> InternalOrderOut:
    order = service.get(session, order_id, lock=True)
    service.plan_delivery(session, order, body.model_dump(), actor=principal.user, ip=client_ip(request))
    session.commit()
    return InternalOrderOut.of(order)


@router.post("/internal/orders/{order_id}/prepare")
def prepare_order(
    order_id: uuid.UUID, request: Request, session: DbSession, principal: Logistics
) -> InternalOrderOut:
    return _act(session, principal, request, order_id, "prepare", None)


@router.post("/internal/orders/{order_id}/{action}")
def manage_order(
    order_id: uuid.UUID,
    action: Literal["confirm", "cancel", "close"],
    request: Request,
    session: DbSession,
    principal: Manager,
    body: ReasonIn | None = None,
) -> InternalOrderOut:
    return _act(session, principal, request, order_id, action, body.message if body else None)


@router.get("/internal/deliveries")
def list_deliveries(session: DbSession, _: Reader) -> list[InternalDeliveryOut]:
    """Vue « Logistique » : toutes les livraisons, la plus récente d'abord."""
    deliveries = [d for o in service.list_all(session) for d in o.deliveries]
    return [_internal_delivery(d) for d in sorted(deliveries, key=lambda d: d.number, reverse=True)]


@router.patch("/internal/deliveries/{delivery_id}")
def update_delivery(
    delivery_id: uuid.UUID, body: DeliveryPatch, request: Request, session: DbSession, principal: Logistics
) -> InternalOrderOut:
    delivery = service.get_delivery(session, delivery_id, lock=True)
    service.update_delivery(
        session, delivery, body.model_dump(exclude_unset=True), actor=principal.user, ip=client_ip(request)
    )
    session.commit()
    return InternalOrderOut.of(delivery.order)


@router.post("/internal/deliveries/{delivery_id}/proofs", status_code=status.HTTP_201_CREATED)
async def add_internal_proof(
    delivery_id: uuid.UUID,
    file: UploadFile,
    request: Request,
    session: DbSession,
    principal: Logistics,
    buyer_visible: Annotated[bool, Form()] = False,
) -> InternalOrderOut:
    delivery = service.get_delivery(session, delivery_id, lock=True)
    document = await save_upload(session, principal, "delivery_proof", file, ip=client_ip(request))
    service.add_proof(
        session,
        delivery,
        document,
        organization=principal.organization,
        buyer_visible=buyer_visible,
        actor=principal.user,
        ip=client_ip(request),
    )
    session.commit()
    return InternalOrderOut.of(delivery.order)


@router.post("/internal/deliveries/{delivery_id}/{action}")
def move_delivery(
    delivery_id: uuid.UUID,
    action: Literal["prepare", "ship", "deliver", "incident", "resume"],
    request: Request,
    session: DbSession,
    principal: Logistics,
    body: ReasonIn | None = None,
) -> InternalOrderOut:
    delivery = service.get_delivery(session, delivery_id, lock=True)
    service.move_delivery(
        session,
        delivery,
        action,
        actor=principal.user,
        ip=client_ip(request),
        message=body.message if body else None,
    )
    session.commit()
    service.notify_delivery(session, delivery, action)
    return InternalOrderOut.of(delivery.order)


# --- Preuve : un seul point de téléchargement, cloisonné selon l'espace -------------------------


@router.get("/deliveries/{delivery_id}/proofs/{document_id}/url")
def proof_url(
    delivery_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    session: DbSession,
    principal: CurrentPrincipal,
) -> DownloadOut:
    organization, permissions = principal.organization, principal.permissions
    if organization.kind == "internal" and ORDER_READ_ALL in permissions:
        proof = service.proof_of(service.get_delivery(session, delivery_id), document_id)
    elif organization.kind == "buyer" and ORDER_VIEW in permissions:
        proof = service.proof_of(service.buyer_delivery(session, organization, delivery_id), document_id)
        if not proof.buyer_visible:
            raise NotFound("Document introuvable.")
    elif organization.kind == "supplier" and SUPPLIER_ORDER_VIEW in permissions:
        proof = service.proof_of(service.supplier_delivery(session, organization, delivery_id), document_id)
        if proof.document.organization_id != organization.id:
            raise NotFound("Document introuvable.")
    else:
        raise NotFound("Document introuvable.")
    record(
        session, "delivery.proof_link", str(document_id), actor_id=principal.user.id, ip=client_ip(request)
    )
    session.commit()
    return DownloadOut(
        url=storage.presigned_download_url(proof.document.storage_key, proof.document.filename),
        expires_in=get_settings().document_url_seconds,
    )


# --- Espace acheteur -------------------------------------------------------------------------------

Buyer = Annotated[Principal, Depends(require_permission(ORDER_VIEW))]
Receiver = Annotated[Principal, Depends(require_permission(DELIVERY_CONFIRM))]


@router.get("/orders")
def list_my_orders(session: DbSession, principal: Buyer) -> list[BuyerOrderOut]:
    return [BuyerOrderOut.of(o) for o in service.list_for_buyer(session, principal.organization)]


@router.get("/orders/{order_id}")
def get_my_order(order_id: uuid.UUID, session: DbSession, principal: Buyer) -> BuyerOrderOut:
    return BuyerOrderOut.of(service.get_for_buyer(session, principal.organization, order_id))


@router.post("/deliveries/{delivery_id}/confirm")
def confirm_delivery(
    delivery_id: uuid.UUID, request: Request, session: DbSession, principal: Receiver
) -> BuyerOrderOut:
    """L'acheteur confirme la réception ; un problème se signale par une réclamation."""
    delivery = service.buyer_delivery(session, principal.organization, delivery_id, lock=True)
    service.move_delivery(session, delivery, "confirm", actor=principal.user, ip=client_ip(request))
    session.commit()
    return BuyerOrderOut.of(delivery.order)


# --- Espace fournisseur ----------------------------------------------------------------------------

Supplier = Annotated[Principal, Depends(require_permission(SUPPLIER_ORDER_VIEW))]
Shipper = Annotated[Principal, Depends(require_permission(DELIVERY_UPDATE))]


@router.get("/supplier-orders")
def list_my_supplier_orders(session: DbSession, principal: Supplier) -> list[SupplierOrderOut]:
    return [SupplierOrderOut.of(p) for p in service.list_for_supplier(session, principal.organization)]


@router.get("/supplier-orders/{part_id}")
def get_my_supplier_order(part_id: uuid.UUID, session: DbSession, principal: Supplier) -> SupplierOrderOut:
    return SupplierOrderOut.of(service.get_for_supplier(session, principal.organization, part_id))


def _part_of(delivery: Delivery) -> SupplierOrder:
    # `supplier_delivery` ne renvoie que des livraisons rattachées à un bon du fournisseur.
    if delivery.supplier_order is None:
        raise NotFound("Livraison introuvable.")
    return delivery.supplier_order


@router.patch("/supplier-deliveries/{delivery_id}")
def update_my_delivery(
    delivery_id: uuid.UUID, body: TrackingPatch, request: Request, session: DbSession, principal: Shipper
) -> SupplierOrderOut:
    delivery = service.supplier_delivery(session, principal.organization, delivery_id, lock=True)
    service.update_delivery(
        session, delivery, body.model_dump(exclude_unset=True), actor=principal.user, ip=client_ip(request)
    )
    session.commit()
    return SupplierOrderOut.of(_part_of(delivery))


@router.post("/supplier-deliveries/{delivery_id}/proofs", status_code=status.HTTP_201_CREATED)
async def add_my_proof(
    delivery_id: uuid.UUID, file: UploadFile, request: Request, session: DbSession, principal: Shipper
) -> SupplierOrderOut:
    delivery = service.supplier_delivery(session, principal.organization, delivery_id, lock=True)
    document = await save_upload(session, principal, "delivery_proof", file, ip=client_ip(request))
    service.add_proof(
        session,
        delivery,
        document,
        organization=principal.organization,
        buyer_visible=False,
        actor=principal.user,
        ip=client_ip(request),
    )
    session.commit()
    return SupplierOrderOut.of(_part_of(delivery))


@router.post("/supplier-deliveries/{delivery_id}/{action}")
def move_my_delivery(
    delivery_id: uuid.UUID,
    action: Literal["prepare", "ship", "deliver"],
    request: Request,
    session: DbSession,
    principal: Shipper,
) -> SupplierOrderOut:
    delivery = service.supplier_delivery(session, principal.organization, delivery_id, lock=True)
    service.move_delivery(session, delivery, action, actor=principal.user, ip=client_ip(request))
    session.commit()
    service.notify_delivery(session, delivery, action)
    return SupplierOrderOut.of(_part_of(delivery))
