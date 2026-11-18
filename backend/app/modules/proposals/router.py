import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.modules.catalog.router import Unit
from app.modules.identity.deps import DbSession, Principal, client_ip, require_permission
from app.modules.identity.permissions import (
    PROPOSAL_DECIDE,
    PROPOSAL_MANAGE,
    PROPOSAL_READ_ALL,
    PROPOSAL_VALIDATE,
    PROPOSAL_VIEW,
)
from app.modules.proposals import service
from app.modules.proposals.models import BuyerProposal
from app.modules.sourcing.router import UserRef

router = APIRouter(tags=["proposals"])

Money = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
Quantity = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=3)]
Message = Annotated[str, Field(max_length=2000)]

# Événements que l'acheteur voit : ceux qui le concernent. Retours de validation et
# brouillons internes restent invisibles.
BUYER_EVENTS = frozenset({"sent", "changes_requested", "accepted", "refused"})


# --- Ce que voit l'acheteur -------------------------------------------------------


class BuyerLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_name: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    total: Decimal


class BuyerVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version: int
    sent_at: datetime | None
    currency: str
    lead_time_days: int
    valid_until: date
    delivery_location: str
    conditions: str | None
    message: str | None
    total: Decimal
    lines: list[BuyerLineOut]


class BuyerEventOut(BaseModel):
    """Sans nom de collaborateur : l'acheteur s'adresse à SOON TRADE, pas à une personne."""

    model_config = ConfigDict(from_attributes=True)

    created_at: datetime
    to_status: str
    version: int
    message: str | None


class BuyerProposalOut(BaseModel):
    """Ni fournisseur, ni offre d'origine, ni prix d'achat, ni marge, ni note interne."""

    id: uuid.UUID
    reference: str
    status: str
    request_id: uuid.UUID
    request_reference: str
    accepted_version: int | None
    versions: list[BuyerVersionOut]
    history: list[BuyerEventOut]

    @classmethod
    def of(cls, proposal: BuyerProposal) -> BuyerProposalOut:
        return cls(
            id=proposal.id,
            reference=proposal.reference,
            status=proposal.buyer_state,
            request_id=proposal.request_id,
            request_reference=proposal.request_reference,
            accepted_version=proposal.accepted_version,
            versions=[BuyerVersionOut.model_validate(v) for v in proposal.sent_versions],
            history=[BuyerEventOut.model_validate(e) for e in proposal.events if e.to_status in BUYER_EVENTS],
        )


# --- Vue interne ------------------------------------------------------------------


class InternalLineOut(BuyerLineOut):
    offer_id: uuid.UUID | None
    offer_reference: str | None
    supplier_name: str | None
    supplier_unit_price: Decimal | None
    cost_total: Decimal


class InternalVersionOut(BuyerVersionOut):
    created_at: datetime
    cost_total: Decimal
    margin: Decimal
    lines: list[InternalLineOut]  # type: ignore[assignment]


class InternalEventOut(BuyerEventOut):
    from_status: str | None
    actor_name: str


class InternalProposalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference: str
    status: str = Field(validation_alias="state")
    created_at: datetime
    case_id: uuid.UUID
    case_reference: str
    request_id: uuid.UUID
    request_reference: str
    buyer_name: str
    created_by: UserRef
    submitted_by: UserRef | None
    accepted_version: int | None
    versions: list[InternalVersionOut]
    events: list[InternalEventOut]


class LineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_name: Annotated[str, Field(min_length=2, max_length=200)]
    quantity: Quantity
    unit: Unit
    unit_price: Money
    offer_id: uuid.UUID | None = None


class ProposalIn(BaseModel):
    """Contenu complet de la version en préparation : il remplace le précédent."""

    model_config = ConfigDict(extra="forbid")

    # À VALIDER : propositions en francs CFA uniquement, comme les offres.
    currency: Literal["XOF"] = "XOF"
    lead_time_days: Annotated[int, Field(ge=0, le=365)]
    valid_until: date
    delivery_location: Annotated[str, Field(min_length=2, max_length=300)]
    conditions: Annotated[str, Field(max_length=4000)] | None = None
    message: Message | None = None
    lines: Annotated[list[LineIn], Field(min_length=1, max_length=service.MAX_LINES)]


class ReasonIn(BaseModel):
    message: Message | None = None


Reader = Annotated[Principal, Depends(require_permission(PROPOSAL_READ_ALL))]
Manager = Annotated[Principal, Depends(require_permission(PROPOSAL_MANAGE))]
Validator = Annotated[Principal, Depends(require_permission(PROPOSAL_VALIDATE))]


def _internal(proposal: BuyerProposal) -> InternalProposalOut:
    return InternalProposalOut.model_validate(proposal)


@router.get("/internal/proposals")
def list_proposals(session: DbSession, _: Reader) -> list[InternalProposalOut]:
    return [_internal(p) for p in service.list_all(session)]


@router.get("/internal/proposals/{proposal_id}")
def get_proposal(proposal_id: uuid.UUID, session: DbSession, _: Reader) -> InternalProposalOut:
    return _internal(service.get(session, proposal_id))


@router.post("/sourcing/cases/{case_id}/proposal", status_code=status.HTTP_201_CREATED)
def create_proposal(
    case_id: uuid.UUID, request: Request, session: DbSession, principal: Manager
) -> InternalProposalOut:
    created = service.create(session, case_id, actor=principal.user, ip=client_ip(request))
    session.commit()
    return _internal(created)


@router.put("/internal/proposals/{proposal_id}")
def update_proposal(
    proposal_id: uuid.UUID, body: ProposalIn, request: Request, session: DbSession, principal: Manager
) -> InternalProposalOut:
    proposal = service.get(session, proposal_id, lock=True)
    service.update(session, proposal, body.model_dump(), actor=principal.user, ip=client_ip(request))
    session.commit()
    return _internal(proposal)


def _act(
    session: DbSession,
    principal: Principal,
    request: Request,
    proposal_id: uuid.UUID,
    action: str,
    message: str | None,
) -> InternalProposalOut:
    proposal = service.get(session, proposal_id, lock=True)
    service.act(session, proposal, action, actor=principal.user, ip=client_ip(request), message=message)
    session.commit()
    if action == "send":
        service.notify_buyer(session, proposal)
    return _internal(proposal)


@router.post("/internal/proposals/{proposal_id}/{action}")
def manage_proposal(
    proposal_id: uuid.UUID,
    action: Literal["submit", "revise", "cancel"],
    request: Request,
    session: DbSession,
    principal: Manager,
    body: ReasonIn | None = None,
) -> InternalProposalOut:
    return _act(session, principal, request, proposal_id, action, body.message if body else None)


@router.post("/internal/proposals/{proposal_id}/validation/{action}")
def validate_proposal(
    proposal_id: uuid.UUID,
    action: Literal["send", "return"],
    request: Request,
    session: DbSession,
    principal: Validator,
    body: ReasonIn | None = None,
) -> InternalProposalOut:
    """Valider et envoyer à l'acheteur, ou renvoyer en préparation avec un motif (interne)."""
    return _act(session, principal, request, proposal_id, action, body.message if body else None)


# --- Espace acheteur ---------------------------------------------------------------

Viewer = Annotated[Principal, Depends(require_permission(PROPOSAL_VIEW))]
Decider = Annotated[Principal, Depends(require_permission(PROPOSAL_DECIDE))]


@router.get("/proposals")
def list_my_proposals(session: DbSession, principal: Viewer) -> list[BuyerProposalOut]:
    return [BuyerProposalOut.of(p) for p in service.list_for_buyer(session, principal.organization)]


@router.get("/proposals/{proposal_id}")
def get_my_proposal(proposal_id: uuid.UUID, session: DbSession, principal: Viewer) -> BuyerProposalOut:
    return BuyerProposalOut.of(service.get_for_buyer(session, principal.organization, proposal_id))


@router.post("/proposals/{proposal_id}/{action}")
def decide_proposal(
    proposal_id: uuid.UUID,
    action: Literal["accept", "refuse", "request_changes"],
    request: Request,
    session: DbSession,
    principal: Decider,
    body: ReasonIn | None = None,
) -> BuyerProposalOut:
    mine = service.get_for_buyer(session, principal.organization, proposal_id, lock=True)
    service.decide(
        session,
        mine,
        action,
        actor=principal.user,
        ip=client_ip(request),
        message=body.message if body and action != "accept" else None,
    )
    session.commit()
    service.notify_decision(session, mine, action, principal.user)
    return BuyerProposalOut.of(mine)
