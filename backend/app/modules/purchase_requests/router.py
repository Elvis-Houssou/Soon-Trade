import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.modules.catalog.router import Unit
from app.modules.identity.deps import DbSession, Principal, client_ip, require_permission
from app.modules.identity.permissions import (
    PURCHASE_REQUEST_MANAGE,
    PURCHASE_REQUEST_QUALIFY,
    PURCHASE_REQUEST_READ_ALL,
)
from app.modules.purchase_requests import service

router = APIRouter(tags=["purchase-requests"])

Quantity = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=3)]
Long = Annotated[str, Field(max_length=4000)]
Message = Annotated[str, Field(max_length=2000)]


class RequestFields(BaseModel):
    product_name: str
    category_id: uuid.UUID | None
    quantity: Decimal
    unit: str
    specifications: str | None
    packaging: str | None
    delivery_location: str
    desired_date: date | None
    additional_info: str | None


class BuyerEventOut(BaseModel):
    """Historique vu par l'acheteur : sans l'auteur, pour ne pas révéler le collaborateur."""

    model_config = ConfigDict(from_attributes=True)

    created_at: datetime
    from_status: str | None
    to_status: str
    message: str | None


class BuyerRequestOut(RequestFields):
    """Ce que l'acheteur voit de sa demande : rien d'interne (dossier, assignation, notes)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference: str
    status: str
    created_at: datetime
    history: list[BuyerEventOut]


class InternalEventOut(BuyerEventOut):
    actor_name: str


class InternalRequestOut(BuyerRequestOut):
    buyer_name: str
    history: list[InternalEventOut]  # type: ignore[assignment]


class RequestIn(BaseModel):
    # À VALIDER : champs obligatoires dès le brouillon = produit, quantité, unité, lieu de livraison.
    model_config = ConfigDict(extra="forbid")

    product_name: Annotated[str, Field(min_length=2, max_length=200)]
    category_id: uuid.UUID | None = None
    quantity: Quantity
    unit: Unit
    specifications: Long | None = None
    packaging: Annotated[str, Field(max_length=200)] | None = None
    delivery_location: Annotated[str, Field(min_length=2, max_length=300)]
    desired_date: date | None = None
    additional_info: Long | None = None


class RequestPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_name: Annotated[str, Field(min_length=2, max_length=200)] | None = None
    category_id: uuid.UUID | None = None
    quantity: Quantity | None = None
    unit: Unit | None = None
    specifications: Long | None = None
    packaging: Annotated[str, Field(max_length=200)] | None = None
    delivery_location: Annotated[str, Field(min_length=2, max_length=300)] | None = None
    desired_date: date | None = None
    additional_info: Long | None = None


class OptionalMessage(BaseModel):
    message: Message | None = None


class RequiredMessage(BaseModel):
    message: Annotated[str, Field(min_length=3, max_length=2000)]


# --- Espace acheteur -------------------------------------------------------------

Buyer = Annotated[Principal, Depends(require_permission(PURCHASE_REQUEST_MANAGE))]


@router.get("/purchase-requests")
def list_my_requests(session: DbSession, principal: Buyer) -> list[BuyerRequestOut]:
    requests = service.list_for_organization(session, principal.organization)
    return [BuyerRequestOut.model_validate(r) for r in requests]


@router.post("/purchase-requests", status_code=status.HTTP_201_CREATED)
def create_request(
    body: RequestIn, request: Request, session: DbSession, principal: Buyer
) -> BuyerRequestOut:
    created = service.create(
        session, principal.organization, body.model_dump(), actor=principal.user, ip=client_ip(request)
    )
    session.commit()
    return BuyerRequestOut.model_validate(created)


@router.get("/purchase-requests/{request_id}")
def get_my_request(request_id: uuid.UUID, session: DbSession, principal: Buyer) -> BuyerRequestOut:
    return BuyerRequestOut.model_validate(
        service.get(session, request_id, organization=principal.organization)
    )


@router.patch("/purchase-requests/{request_id}")
def update_my_request(
    request_id: uuid.UUID, body: RequestPatch, request: Request, session: DbSession, principal: Buyer
) -> BuyerRequestOut:
    mine = service.get(session, request_id, organization=principal.organization, lock=True)
    changes = body.model_dump(exclude_unset=True)
    service.update(session, mine, changes, actor=principal.user, ip=client_ip(request))
    session.commit()
    return BuyerRequestOut.model_validate(mine)


def _buyer_action(action: str, with_message: bool) -> None:
    @router.post(f"/purchase-requests/{{request_id}}/{action}", name=f"{action}_my_request")
    def endpoint(
        request_id: uuid.UUID,
        request: Request,
        session: DbSession,
        principal: Buyer,
        body: OptionalMessage | None = None,
    ) -> BuyerRequestOut:
        mine = service.get(session, request_id, organization=principal.organization, lock=True)
        service.transition(
            session,
            mine,
            action,
            actor=principal.user,
            ip=client_ip(request),
            message=body.message if body and with_message else None,
        )
        session.commit()
        return BuyerRequestOut.model_validate(mine)


_buyer_action("submit", with_message=True)  # le message sert de réponse à une demande de précisions
_buyer_action("cancel", with_message=True)


# --- Espace interne --------------------------------------------------------------

Reader = Annotated[Principal, Depends(require_permission(PURCHASE_REQUEST_READ_ALL))]
Qualifier = Annotated[Principal, Depends(require_permission(PURCHASE_REQUEST_QUALIFY))]


@router.get("/internal/purchase-requests")
def list_all_requests(session: DbSession, _: Reader) -> list[InternalRequestOut]:
    return [InternalRequestOut.model_validate(r) for r in service.list_all(session)]


@router.get("/internal/purchase-requests/{request_id}")
def get_request(request_id: uuid.UUID, session: DbSession, _: Reader) -> InternalRequestOut:
    return InternalRequestOut.model_validate(service.get(session, request_id))


def _qualify(
    session: DbSession,
    principal: Principal,
    request: Request,
    request_id: uuid.UUID,
    action: str,
    message: str | None,
) -> InternalRequestOut:
    target = service.get(session, request_id, lock=True)
    service.transition(session, target, action, actor=principal.user, ip=client_ip(request), message=message)
    session.commit()
    service.notify_buyer(session, target, action)
    return InternalRequestOut.model_validate(target)


@router.post("/internal/purchase-requests/{request_id}/request-info")
def request_info(
    request_id: uuid.UUID, body: RequiredMessage, request: Request, session: DbSession, principal: Qualifier
) -> InternalRequestOut:
    return _qualify(session, principal, request, request_id, "request_info", body.message)


@router.post("/internal/purchase-requests/{request_id}/qualify")
def qualify(
    request_id: uuid.UUID, request: Request, session: DbSession, principal: Qualifier
) -> InternalRequestOut:
    return _qualify(session, principal, request, request_id, "qualify", None)


@router.post("/internal/purchase-requests/{request_id}/reject")
def reject(
    request_id: uuid.UUID, body: RequiredMessage, request: Request, session: DbSession, principal: Qualifier
) -> InternalRequestOut:
    return _qualify(session, principal, request, request_id, "reject", body.message)
