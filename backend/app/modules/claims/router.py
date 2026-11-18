import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.modules.claims import service
from app.modules.claims.models import Claim
from app.modules.identity.deps import DbSession, Principal, client_ip, require_permission
from app.modules.identity.permissions import CLAIM_CREATE, CLAIM_DECIDE, CLAIM_HANDLE, CLAIM_READ_ALL

router = APIRouter(tags=["claims"])

Category = Literal["quantity", "quality", "delay", "damage", "other"]


class ClaimEventOut(BaseModel):
    """Sans nom de collaborateur."""

    model_config = ConfigDict(from_attributes=True)

    created_at: datetime
    to_status: str
    message: str | None


class InternalClaimEventOut(ClaimEventOut):
    from_status: str | None
    actor_name: str


class ClaimOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference: str
    status: str
    created_at: datetime
    order_id: uuid.UUID
    order_reference: str
    delivery_id: uuid.UUID | None
    delivery_reference: str | None
    category: str
    subject: str
    description: str
    resolution: str | None
    history: list[ClaimEventOut] = Field(validation_alias="events")


class InternalClaimOut(ClaimOut):
    buyer_name: str
    history: list[InternalClaimEventOut] = Field(validation_alias="events")  # type: ignore[assignment]


class ClaimIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: uuid.UUID
    delivery_id: uuid.UUID | None = None
    category: Category
    subject: Annotated[str, Field(min_length=3, max_length=200)]
    description: Annotated[str, Field(min_length=3, max_length=4000)]


class AnswerIn(BaseModel):
    message: Annotated[str, Field(max_length=2000)] | None = None


# --- Espace acheteur ---------------------------------------------------------------------

Claimant = Annotated[Principal, Depends(require_permission(CLAIM_CREATE))]


def _mine(claim: Claim) -> ClaimOut:
    return ClaimOut.model_validate(claim)


@router.get("/claims")
def list_my_claims(session: DbSession, principal: Claimant) -> list[ClaimOut]:
    return [_mine(c) for c in service.list_for_buyer(session, principal.organization)]


@router.post("/claims", status_code=status.HTTP_201_CREATED)
def open_claim(body: ClaimIn, request: Request, session: DbSession, principal: Claimant) -> ClaimOut:
    claim = service.open_claim(
        session, principal.organization, body.model_dump(), actor=principal.user, ip=client_ip(request)
    )
    session.commit()
    service.notify_opened(session, claim)
    return _mine(claim)


@router.get("/claims/{claim_id}")
def get_my_claim(claim_id: uuid.UUID, session: DbSession, principal: Claimant) -> ClaimOut:
    return _mine(service.get_for_buyer(session, principal.organization, claim_id))


@router.post("/claims/{claim_id}/close")
def close_my_claim(
    claim_id: uuid.UUID, request: Request, session: DbSession, principal: Claimant
) -> ClaimOut:
    claim = service.get_for_buyer(session, principal.organization, claim_id, lock=True)
    service.buyer_close(session, claim, actor=principal.user, ip=client_ip(request))
    session.commit()
    return _mine(claim)


# --- Espace interne ---------------------------------------------------------------------------

Reader = Annotated[Principal, Depends(require_permission(CLAIM_READ_ALL))]
Handler = Annotated[Principal, Depends(require_permission(CLAIM_HANDLE))]
Decider = Annotated[Principal, Depends(require_permission(CLAIM_DECIDE))]


@router.get("/internal/claims")
def list_claims(session: DbSession, _: Reader) -> list[InternalClaimOut]:
    return [InternalClaimOut.model_validate(c) for c in service.list_all(session)]


@router.get("/internal/claims/{claim_id}")
def get_claim(claim_id: uuid.UUID, session: DbSession, _: Reader) -> InternalClaimOut:
    return InternalClaimOut.model_validate(service.get(session, claim_id))


def _act(
    session: DbSession,
    principal: Principal,
    request: Request,
    claim_id: uuid.UUID,
    action: str,
    message: str | None,
) -> InternalClaimOut:
    claim = service.get(session, claim_id, lock=True)
    service.act(session, claim, action, actor=principal.user, ip=client_ip(request), message=message)
    session.commit()
    if action in service.NEEDS_ANSWER:
        service.notify_answered(session, claim)
    return InternalClaimOut.model_validate(claim)


@router.post("/internal/claims/{claim_id}/review")
def review_claim(
    claim_id: uuid.UUID, request: Request, session: DbSession, principal: Handler
) -> InternalClaimOut:
    return _act(session, principal, request, claim_id, "review", None)


@router.post("/internal/claims/{claim_id}/{action}")
def decide_claim(
    claim_id: uuid.UUID,
    action: Literal["resolve", "reject", "close"],
    request: Request,
    session: DbSession,
    principal: Decider,
    body: AnswerIn | None = None,
) -> InternalClaimOut:
    """Résoudre ou rejeter exige une réponse, lue par l'acheteur."""
    return _act(session, principal, request, claim_id, action, body.message if body else None)
