import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.modules.catalog.router import Unit
from app.modules.identity.deps import DbSession, Principal, client_ip, require_permission
from app.modules.identity.permissions import SOLICITATION_RESPOND, SOURCING_MANAGE, SOURCING_READ
from app.modules.solicitations import service
from app.modules.sourcing.router import UserRef

router = APIRouter(tags=["solicitations"])

Quantity = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=3)]
Long = Annotated[str, Field(max_length=4000)]


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str


class OfferVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version: int
    created_at: datetime
    unit_price: Decimal
    currency: str
    quantity: Decimal
    total: Decimal
    lead_time_days: int
    valid_until: date
    packaging: str | None
    conditions: str | None
    attachments: list[AttachmentOut]


class OfferOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference: str
    status: str = Field(validation_alias="state")
    versions: list[OfferVersionOut]


class SolicitationOut(BaseModel):
    """Ce que le fournisseur voit : le besoin tel que SOON TRADE l'a rédigé. Ni acheteur,
    ni dossier, ni autres fournisseurs consultés."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference: str
    status: str = Field(validation_alias="state")
    sent_at: datetime | None
    product_name: str
    quantity: Decimal
    unit: str
    specifications: str | None
    packaging: str | None
    delivery_location: str
    desired_date: date | None
    response_deadline: date
    message: str | None
    decline_reason: str | None
    offer: OfferOut | None


class InternalSolicitationOut(SolicitationOut):
    created_at: datetime
    organization_id: uuid.UUID
    supplier_name: str
    case_id: uuid.UUID
    case_reference: str
    created_by: UserRef
    viewed_at: datetime | None


class SolicitationIn(BaseModel):
    organization_id: uuid.UUID


class SolicitationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_name: Annotated[str, Field(min_length=2, max_length=200)] | None = None
    quantity: Quantity | None = None
    unit: Unit | None = None
    specifications: Long | None = None
    packaging: Annotated[str, Field(max_length=200)] | None = None
    delivery_location: Annotated[str, Field(min_length=2, max_length=300)] | None = None
    desired_date: date | None = None
    response_deadline: date | None = None
    message: Annotated[str, Field(max_length=2000)] | None = None


class OfferIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_price: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
    # À VALIDER : les offres sont libellées en francs CFA uniquement, pour être comparables.
    currency: Literal["XOF"] = "XOF"
    quantity: Quantity
    lead_time_days: Annotated[int, Field(ge=0, le=365)]
    valid_until: date
    packaging: Annotated[str, Field(max_length=200)] | None = None
    conditions: Long | None = None
    attachment_ids: Annotated[list[uuid.UUID], Field(max_length=service.MAX_ATTACHMENTS)] = []


class ReasonIn(BaseModel):
    message: Annotated[str, Field(max_length=2000)] | None = None


# --- Espace interne --------------------------------------------------------------

Reader = Annotated[Principal, Depends(require_permission(SOURCING_READ))]
Manager = Annotated[Principal, Depends(require_permission(SOURCING_MANAGE))]


def _internal(solicitation: object) -> InternalSolicitationOut:
    return InternalSolicitationOut.model_validate(solicitation)


@router.get("/sourcing/solicitations")
def list_solicitations(session: DbSession, _: Reader) -> list[InternalSolicitationOut]:
    return [_internal(s) for s in service.list_all(session)]


@router.get("/sourcing/cases/{case_id}/solicitations")
def list_case_solicitations(
    case_id: uuid.UUID, session: DbSession, _: Reader
) -> list[InternalSolicitationOut]:
    """Sollicitations et offres d'un dossier : la base de la comparaison interne."""
    return [_internal(s) for s in service.list_for_case(session, case_id)]


@router.post("/sourcing/cases/{case_id}/solicitations", status_code=status.HTTP_201_CREATED)
def create_solicitation(
    case_id: uuid.UUID, body: SolicitationIn, request: Request, session: DbSession, principal: Manager
) -> InternalSolicitationOut:
    created = service.create(
        session, case_id, body.organization_id, actor=principal.user, ip=client_ip(request)
    )
    session.commit()
    return _internal(created)


@router.patch("/sourcing/solicitations/{solicitation_id}")
def update_solicitation(
    solicitation_id: uuid.UUID,
    body: SolicitationPatch,
    request: Request,
    session: DbSession,
    principal: Manager,
) -> InternalSolicitationOut:
    solicitation = service.get(session, solicitation_id, lock=True)
    service.update(
        session,
        solicitation,
        body.model_dump(exclude_unset=True),
        actor=principal.user,
        ip=client_ip(request),
    )
    session.commit()
    return _internal(solicitation)


@router.post("/sourcing/solicitations/{solicitation_id}/send")
def send_solicitation(
    solicitation_id: uuid.UUID, request: Request, session: DbSession, principal: Manager
) -> InternalSolicitationOut:
    solicitation = service.get(session, solicitation_id, lock=True)
    service.send(session, solicitation, actor=principal.user, ip=client_ip(request))
    session.commit()
    service.notify_supplier(session, solicitation)
    return _internal(solicitation)


@router.post("/sourcing/solicitations/{solicitation_id}/cancel")
def cancel_solicitation(
    solicitation_id: uuid.UUID, request: Request, session: DbSession, principal: Manager
) -> InternalSolicitationOut:
    solicitation = service.get(session, solicitation_id, lock=True)
    service.cancel(session, solicitation, actor=principal.user, ip=client_ip(request))
    session.commit()
    return _internal(solicitation)


@router.post("/sourcing/offers/{offer_id}/{action}")
def decide_offer(
    offer_id: uuid.UUID,
    action: Literal["review", "retain", "reject"],
    request: Request,
    session: DbSession,
    principal: Manager,
) -> InternalSolicitationOut:
    offer = service.get_offer(session, offer_id)
    service.decide(session, offer, action, actor=principal.user, ip=client_ip(request))
    session.commit()
    return _internal(offer.solicitation)


# --- Espace fournisseur ----------------------------------------------------------

Supplier = Annotated[Principal, Depends(require_permission(SOLICITATION_RESPOND))]


@router.get("/solicitations")
def list_my_solicitations(session: DbSession, principal: Supplier) -> list[SolicitationOut]:
    return [
        SolicitationOut.model_validate(s) for s in service.list_for_supplier(session, principal.organization)
    ]


@router.get("/solicitations/{solicitation_id}")
def get_my_solicitation(
    solicitation_id: uuid.UUID, request: Request, session: DbSession, principal: Supplier
) -> SolicitationOut:
    """L'ouverture par le fournisseur fait passer la sollicitation à « consultée »."""
    mine = service.get_for_supplier(session, principal.organization, solicitation_id, lock=True)
    service.mark_viewed(session, mine, actor=principal.user, ip=client_ip(request))
    session.commit()
    return SolicitationOut.model_validate(mine)


@router.post("/solicitations/{solicitation_id}/decline")
def decline_solicitation(
    solicitation_id: uuid.UUID, body: ReasonIn, request: Request, session: DbSession, principal: Supplier
) -> SolicitationOut:
    mine = service.get_for_supplier(session, principal.organization, solicitation_id, lock=True)
    service.decline(session, mine, body.message, actor=principal.user, ip=client_ip(request))
    session.commit()
    return SolicitationOut.model_validate(mine)


@router.post("/solicitations/{solicitation_id}/offer", status_code=status.HTTP_201_CREATED)
def submit_offer(
    solicitation_id: uuid.UUID, body: OfferIn, request: Request, session: DbSession, principal: Supplier
) -> SolicitationOut:
    mine = service.get_for_supplier(session, principal.organization, solicitation_id, lock=True)
    service.submit_offer(session, mine, body.model_dump(), actor=principal.user, ip=client_ip(request))
    session.commit()
    service.notify_offer(session, mine)
    return SolicitationOut.model_validate(mine)


@router.put("/solicitations/{solicitation_id}/offer")
def revise_offer(
    solicitation_id: uuid.UUID, body: OfferIn, request: Request, session: DbSession, principal: Supplier
) -> SolicitationOut:
    """Le contenu complet est renvoyé à chaque modification ; il devient une nouvelle version."""
    mine = service.get_for_supplier(session, principal.organization, solicitation_id, lock=True)
    service.revise_offer(session, mine, body.model_dump(), actor=principal.user, ip=client_ip(request))
    session.commit()
    return SolicitationOut.model_validate(mine)


@router.post("/solicitations/{solicitation_id}/offer/withdraw")
def withdraw_offer(
    solicitation_id: uuid.UUID, request: Request, session: DbSession, principal: Supplier
) -> SolicitationOut:
    mine = service.get_for_supplier(session, principal.organization, solicitation_id, lock=True)
    service.withdraw_offer(session, mine, actor=principal.user, ip=client_ip(request))
    session.commit()
    return SolicitationOut.model_validate(mine)
