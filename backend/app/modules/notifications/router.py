import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.modules.identity.deps import CurrentPrincipal, DbSession
from app.modules.notifications import service

router = APIRouter(tags=["notifications"])


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    kind: str
    params: dict[str, Any]
    link: str
    read_at: datetime | None


class NotificationsOut(BaseModel):
    unread: int
    items: list[NotificationOut]


class ReadIn(BaseModel):
    """Sans `ids`, tout est marqué comme lu."""

    ids: Annotated[list[uuid.UUID], Field(max_length=100)] | None = None


@router.get("/notifications")
def list_notifications(session: DbSession, principal: CurrentPrincipal) -> NotificationsOut:
    items, unread = service.latest(session, principal.user)
    return NotificationsOut(unread=unread, items=[NotificationOut.model_validate(n) for n in items])


@router.post("/notifications/read")
def read_notifications(body: ReadIn, session: DbSession, principal: CurrentPrincipal) -> NotificationsOut:
    service.mark_read(session, principal.user, body.ids)
    session.commit()
    return list_notifications(session, principal)
