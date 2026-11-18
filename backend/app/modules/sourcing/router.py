"""Routes strictement internes : ni acheteur ni fournisseur n'a de permission `sourcing:*`."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.modules.identity.deps import DbSession, Principal, client_ip, require_permission
from app.modules.identity.permissions import SOURCING_MANAGE, SOURCING_READ
from app.modules.purchase_requests.router import InternalRequestOut
from app.modules.sourcing import service

router = APIRouter(prefix="/sourcing", tags=["sourcing"])

Reader = Annotated[Principal, Depends(require_permission(SOURCING_READ))]
Manager = Annotated[Principal, Depends(require_permission(SOURCING_MANAGE))]


class UserRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str


class SupplierRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    city: str | None


class CandidateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    created_at: datetime
    organization: SupplierRef


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    body: str
    author: UserRef


class CaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference: str
    created_at: datetime
    request: InternalRequestOut
    assignee: UserRef | None
    candidates: list[CandidateOut]
    notes: list[NoteOut]


class SupplierProductOut(BaseModel):
    product_id: uuid.UUID
    product_name: str
    category_name: str
    unit: str
    packaging: str | None
    available_quantity: Decimal
    availability: str
    supplier: SupplierRef


class CaseIn(BaseModel):
    request_id: uuid.UUID


class AssignIn(BaseModel):
    assignee_id: uuid.UUID


class CandidateIn(BaseModel):
    organization_id: uuid.UUID


class NoteIn(BaseModel):
    body: Annotated[str, Field(min_length=1, max_length=4000)]


@router.get("/cases")
def list_cases(session: DbSession, _: Reader) -> list[CaseOut]:
    return [CaseOut.model_validate(c) for c in service.list_cases(session)]


@router.post("/cases", status_code=status.HTTP_201_CREATED)
def open_case(body: CaseIn, request: Request, session: DbSession, principal: Manager) -> CaseOut:
    case = service.open_case(session, body.request_id, actor=principal.user, ip=client_ip(request))
    session.commit()
    return CaseOut.model_validate(case)


@router.get("/cases/{case_id}")
def get_case(case_id: uuid.UUID, session: DbSession, _: Reader) -> CaseOut:
    return CaseOut.model_validate(service.get_case(session, case_id))


@router.patch("/cases/{case_id}")
def assign_case(
    case_id: uuid.UUID, body: AssignIn, request: Request, session: DbSession, principal: Manager
) -> CaseOut:
    case = service.assign(session, case_id, body.assignee_id, actor=principal.user, ip=client_ip(request))
    session.commit()
    return CaseOut.model_validate(case)


@router.post("/cases/{case_id}/candidates", status_code=status.HTTP_201_CREATED)
def add_candidate(
    case_id: uuid.UUID, body: CandidateIn, request: Request, session: DbSession, principal: Manager
) -> CaseOut:
    case = service.add_candidate(
        session, case_id, body.organization_id, actor=principal.user, ip=client_ip(request)
    )
    session.commit()
    return CaseOut.model_validate(case)


@router.delete("/cases/{case_id}/candidates/{organization_id}")
def remove_candidate(
    case_id: uuid.UUID, organization_id: uuid.UUID, request: Request, session: DbSession, principal: Manager
) -> CaseOut:
    case = service.remove_candidate(
        session, case_id, organization_id, actor=principal.user, ip=client_ip(request)
    )
    session.commit()
    return CaseOut.model_validate(case)


@router.post("/cases/{case_id}/notes", status_code=status.HTTP_201_CREATED)
def add_note(
    case_id: uuid.UUID, body: NoteIn, request: Request, session: DbSession, principal: Manager
) -> CaseOut:
    case = service.add_note(session, case_id, body.body, actor=principal.user, ip=client_ip(request))
    session.commit()
    return CaseOut.model_validate(case)


@router.get("/assignees")
def list_assignees(session: DbSession, _: Manager) -> list[UserRef]:
    return [UserRef.model_validate(u) for u in service.assignable_users(session)]


@router.get("/suppliers")
def search_suppliers(
    session: DbSession,
    _: Reader,
    q: Annotated[str | None, Query(max_length=200)] = None,
    category_id: uuid.UUID | None = None,
) -> list[SupplierProductOut]:
    """Recherche dans les catalogues des fournisseurs vérifiés."""
    return [
        SupplierProductOut(
            product_id=product.id,
            product_name=product.name,
            category_name=category.name,
            unit=product.unit,
            packaging=product.packaging,
            available_quantity=product.available_quantity,
            availability=product.availability,
            supplier=SupplierRef.model_validate(supplier),
        )
        for product, supplier, category in service.search_products(session, q=q, category_id=category_id)
    ]
