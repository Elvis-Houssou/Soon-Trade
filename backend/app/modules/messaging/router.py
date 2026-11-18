import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.modules.identity.deps import DbSession, Principal, client_ip, require_permission
from app.modules.identity.models import Organization, User
from app.modules.identity.permissions import CONVERSATION_READ_ALL, CONVERSATION_REPLY, CONVERSATION_USE
from app.modules.messaging import service
from app.modules.messaging.models import Conversation, Message
from app.modules.notifications import service as notifications
from app.modules.organizations.service import get_client_organization

router = APIRouter(tags=["messaging"])

Body = Annotated[str, Field(min_length=1, max_length=4000)]
PREVIEW = 140


class MessageOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    from_staff: bool
    # Côté client, un message de l'équipe est signé « SOON TRADE », jamais d'un nom.
    author_name: str | None
    body: str


class InternalMessageOut(MessageOut):
    internal: bool


class SummaryOut(BaseModel):
    id: uuid.UUID
    reference: str
    subject: str
    context_reference: str | None
    status: str
    last_message_at: datetime
    last_message: str | None
    unread: bool


class InternalSummaryOut(SummaryOut):
    organization_id: uuid.UUID
    organization_name: str
    organization_kind: str


class ConversationOut(SummaryOut):
    messages: list[MessageOut]


class InternalConversationOut(InternalSummaryOut):
    messages: list[InternalMessageOut]


class StartIn(BaseModel):
    subject: Annotated[str, Field(min_length=2, max_length=200)]
    body: Body
    context_reference: Annotated[str, Field(max_length=40)] | None = None


class InternalStartIn(StartIn):
    organization_id: uuid.UUID


class PostIn(BaseModel):
    body: Body


class InternalPostIn(PostIn):
    internal: bool = False


def _summary(session: Session, conversation: Conversation, user: User, *, staff: bool) -> dict[str, object]:
    messages = service.visible(conversation, staff=staff)
    last = messages[-1].body if messages else None
    return {
        "id": conversation.id,
        "reference": conversation.reference,
        "subject": conversation.subject,
        "context_reference": conversation.context_reference,
        "status": conversation.status,
        "last_message_at": conversation.last_message_at,
        "last_message": last[:PREVIEW] if last else None,
        "unread": service.unread(session, conversation, user, staff=staff),
    }


def _client_message(message: Message) -> MessageOut:
    return MessageOut(
        id=message.id,
        created_at=message.created_at,
        from_staff=message.from_staff,
        author_name=None if message.from_staff else message.author_name,
        body=message.body,
    )


def _internal_extra(conversation: Conversation) -> dict[str, object]:
    return {
        "organization_id": conversation.organization_id,
        "organization_name": conversation.organization_name,
        "organization_kind": conversation.organization_kind,
    }


def _notify(session: Session, conversation: Conversation, message: Message, author: User) -> None:
    """Le client est prévenu d'un message de l'équipe ; l'équipe, d'un message du client."""
    if message.internal:
        return
    reference = conversation.reference
    if message.from_staff:
        notifications.notify(
            session,
            notifications.members(session, conversation.organization_id),
            "message_received",
            link=f"{conversation.organization_kind}/messages?id={conversation.id}",
            params={"reference": reference},
            email={"reference": reference},
        )
    else:
        notifications.notify(
            session,
            notifications.staff_with(session, CONVERSATION_REPLY),
            "message_from_client",
            link=f"internal/messages?id={conversation.id}",
            params={"reference": reference, "organization": conversation.organization_name},
            besides=author.id,
        )


# --- Espace client (acheteur ou fournisseur) -----------------------------------------------

Client = Annotated[Principal, Depends(require_permission(CONVERSATION_USE))]


def _client_view(session: Session, conversation: Conversation, user: User) -> ConversationOut:
    return ConversationOut.model_validate(
        {
            **_summary(session, conversation, user, staff=False),
            "messages": [_client_message(m) for m in service.visible(conversation, staff=False)],
        }
    )


@router.get("/conversations")
def list_my_conversations(session: DbSession, principal: Client) -> list[SummaryOut]:
    return [
        SummaryOut.model_validate(_summary(session, c, principal.user, staff=False))
        for c in service.list_for_client(session, principal.organization)
    ]


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
def start_conversation(
    body: StartIn, request: Request, session: DbSession, principal: Client
) -> ConversationOut:
    conversation = service.start(
        session,
        principal.organization,
        body.subject,
        body.body,
        context_reference=body.context_reference,
        actor=principal.user,
        staff=False,
        ip=client_ip(request),
    )
    session.commit()
    _notify(session, conversation, conversation.messages[-1], principal.user)
    return _client_view(session, conversation, principal.user)


@router.get("/conversations/{conversation_id}")
def read_my_conversation(
    conversation_id: uuid.UUID, session: DbSession, principal: Client
) -> ConversationOut:
    conversation = service.get_for_client(session, principal.organization, conversation_id)
    service.mark_read(session, conversation, principal.user)
    session.commit()
    return _client_view(session, conversation, principal.user)


@router.post("/conversations/{conversation_id}/messages", status_code=status.HTTP_201_CREATED)
def post_my_message(
    conversation_id: uuid.UUID, body: PostIn, request: Request, session: DbSession, principal: Client
) -> ConversationOut:
    conversation = service.get_for_client(session, principal.organization, conversation_id, lock=True)
    message = service.post(
        session,
        conversation,
        body.body,
        actor=principal.user,
        staff=False,
        internal=False,
        ip=client_ip(request),
    )
    session.commit()
    _notify(session, conversation, message, principal.user)
    return _client_view(session, conversation, principal.user)


# --- Espace interne ---------------------------------------------------------------------------

Reader = Annotated[Principal, Depends(require_permission(CONVERSATION_READ_ALL))]
Replier = Annotated[Principal, Depends(require_permission(CONVERSATION_REPLY))]


def _internal_view(session: Session, conversation: Conversation, user: User) -> InternalConversationOut:
    return InternalConversationOut.model_validate(
        {
            **_summary(session, conversation, user, staff=True),
            **_internal_extra(conversation),
            "messages": [
                InternalMessageOut(
                    id=m.id,
                    created_at=m.created_at,
                    from_staff=m.from_staff,
                    author_name=m.author_name,
                    body=m.body,
                    internal=m.internal,
                )
                for m in conversation.messages
            ],
        }
    )


@router.get("/internal/conversations")
def list_conversations(
    session: DbSession, principal: Reader, organization_id: uuid.UUID | None = None
) -> list[InternalSummaryOut]:
    return [
        InternalSummaryOut.model_validate(
            {**_summary(session, c, principal.user, staff=True), **_internal_extra(c)}
        )
        for c in service.list_all(session, organization_id)
    ]


@router.post("/internal/conversations", status_code=status.HTTP_201_CREATED)
def start_internal_conversation(
    body: InternalStartIn, request: Request, session: DbSession, principal: Replier
) -> InternalConversationOut:
    organization: Organization = get_client_organization(session, body.organization_id)
    conversation = service.start(
        session,
        organization,
        body.subject,
        body.body,
        context_reference=body.context_reference,
        actor=principal.user,
        staff=True,
        ip=client_ip(request),
    )
    session.commit()
    _notify(session, conversation, conversation.messages[-1], principal.user)
    return _internal_view(session, conversation, principal.user)


@router.get("/internal/conversations/{conversation_id}")
def read_conversation(
    conversation_id: uuid.UUID, session: DbSession, principal: Reader
) -> InternalConversationOut:
    conversation = service.get(session, conversation_id)
    service.mark_read(session, conversation, principal.user)
    session.commit()
    return _internal_view(session, conversation, principal.user)


@router.post("/internal/conversations/{conversation_id}/messages", status_code=status.HTTP_201_CREATED)
def post_internal_message(
    conversation_id: uuid.UUID, body: InternalPostIn, request: Request, session: DbSession, principal: Replier
) -> InternalConversationOut:
    conversation = service.get(session, conversation_id, lock=True)
    message = service.post(
        session,
        conversation,
        body.body,
        actor=principal.user,
        staff=True,
        internal=body.internal,
        ip=client_ip(request),
    )
    session.commit()
    _notify(session, conversation, message, principal.user)
    return _internal_view(session, conversation, principal.user)


@router.post("/internal/conversations/{conversation_id}/{action}")
def change_conversation(
    conversation_id: uuid.UUID,
    action: Literal["close", "reopen"],
    request: Request,
    session: DbSession,
    principal: Replier,
) -> InternalConversationOut:
    conversation = service.get(session, conversation_id, lock=True)
    service.set_status(
        session,
        conversation,
        "closed" if action == "close" else "open",
        actor=principal.user,
        ip=client_ip(request),
    )
    session.commit()
    return _internal_view(session, conversation, principal.user)
