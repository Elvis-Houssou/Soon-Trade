import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from app.modules.crm import service
from app.modules.identity.deps import DbSession, Principal, client_ip, require_permission
from app.modules.identity.models import Organization
from app.modules.identity.permissions import CRM_NOTE, ORGANIZATION_READ_ALL

router = APIRouter(tags=["crm"])


class ClientOut(BaseModel):
    id: uuid.UUID
    name: str
    kind: str
    city: str | None
    verification_status: str
    last_activity: datetime | None
    requests: int
    orders: int
    open_claims: int
    conversations: int


class EntryOut(BaseModel):
    at: datetime
    kind: str
    reference: str
    status: str | None
    label: str
    link: str | None
    author: str | None


class ClientFileOut(ClientOut):
    timeline: list[EntryOut]


class NoteIn(BaseModel):
    body: Annotated[str, Field(min_length=1, max_length=4000)]


Reader = Annotated[Principal, Depends(require_permission(ORGANIZATION_READ_ALL))]
Writer = Annotated[Principal, Depends(require_permission(CRM_NOTE))]


def _client(session: DbSession, organization: Organization) -> dict[str, object]:
    return {
        "id": organization.id,
        "name": organization.name,
        "kind": organization.kind,
        "city": organization.city,
        "verification_status": organization.verification_status,
        **service.summary(session, organization),
    }


@router.get("/internal/crm")
def list_clients(session: DbSession, _: Reader) -> list[ClientOut]:
    """Acheteurs et fournisseurs, le plus récemment actif d'abord."""
    rows = [ClientOut.model_validate(_client(session, o)) for o in service.clients(session)]
    return sorted(rows, key=lambda c: c.last_activity.timestamp() if c.last_activity else 0, reverse=True)


def _file(session: DbSession, organization_id: uuid.UUID) -> ClientFileOut:
    organization = service.get_client(session, organization_id)
    return ClientFileOut.model_validate(
        {
            **_client(session, organization),
            "timeline": [
                EntryOut.model_validate(e, from_attributes=True)
                for e in service.timeline(session, organization)
            ],
        }
    )


@router.get("/internal/crm/{organization_id}")
def client_file(organization_id: uuid.UUID, session: DbSession, _: Reader) -> ClientFileOut:
    return _file(session, organization_id)


@router.post("/internal/crm/{organization_id}/notes", status_code=status.HTTP_201_CREATED)
def add_note(
    organization_id: uuid.UUID, body: NoteIn, request: Request, session: DbSession, principal: Writer
) -> ClientFileOut:
    organization = service.get_client(session, organization_id)
    service.add_note(session, organization, body.body, actor=principal.user, ip=client_ip(request))
    session.commit()
    return _file(session, organization_id)
