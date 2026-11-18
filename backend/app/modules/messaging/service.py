"""Messagerie centralisée : chaque client ne parle qu'à SOON TRADE."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFound
from app.modules.audit.models import record
from app.modules.identity.models import Organization, User
from app.modules.messaging.models import Conversation, ConversationRead, Message


def _clean(value: str | None) -> str | None:
    return value.strip() or None if value else None


def visible(conversation: Conversation, *, staff: bool) -> list[Message]:
    return [m for m in conversation.messages if staff or not m.internal]


def unread(session: Session, conversation: Conversation, user: User, *, staff: bool) -> bool:
    """Un message d'autrui, visible de l'utilisateur, arrivé après sa dernière lecture."""
    read_at = session.scalar(
        select(ConversationRead.read_at).where(
            ConversationRead.conversation_id == conversation.id, ConversationRead.user_id == user.id
        )
    )
    return any(
        m.author_id != user.id and (read_at is None or m.created_at > read_at)
        for m in visible(conversation, staff=staff)
    )


def mark_read(session: Session, conversation: Conversation, user: User) -> None:
    now = datetime.now(UTC)
    read = session.get(ConversationRead, (conversation.id, user.id))
    if read:
        read.read_at = now
    else:
        session.add(ConversationRead(conversation_id=conversation.id, user_id=user.id, read_at=now))


def start(
    session: Session,
    organization: Organization,
    subject: str,
    body: str,
    *,
    context_reference: str | None,
    actor: User,
    staff: bool,
    ip: str | None,
) -> Conversation:
    if organization.kind not in ("buyer", "supplier"):
        raise NotFound("Organisation introuvable.")
    subject_text, text = _clean(subject), _clean(body)
    if not subject_text or not text:
        raise AppError("Ce champ est obligatoire.")
    conversation = Conversation(
        organization_id=organization.id,
        created_by_id=actor.id,
        subject=subject_text,
        context_reference=_clean(context_reference),
    )
    session.add(conversation)
    session.flush()
    post(session, conversation, text, actor=actor, staff=staff, internal=False, ip=ip)
    return conversation


def post(
    session: Session,
    conversation: Conversation,
    body: str,
    *,
    actor: User,
    staff: bool,
    internal: bool,
    ip: str | None,
) -> Message:
    text = _clean(body)
    if not text:
        raise AppError("Ce champ est obligatoire.")
    # À VALIDER : un nouveau message rouvre un fil clos (sauf une note interne).
    if conversation.status == "closed" and not internal:
        conversation.status = "open"
    message = Message(
        conversation_id=conversation.id,
        author_id=actor.id,
        from_staff=staff,
        internal=internal and staff,
        body=text,
    )
    conversation.messages.append(message)
    conversation.last_message_at = datetime.now(UTC)
    session.flush()
    mark_read(session, conversation, actor)
    # Le contenu ne part pas dans le journal d'audit.
    record(
        session, "message.posted", conversation.reference, actor_id=actor.id, ip=ip, internal=message.internal
    )
    return message


def set_status(
    session: Session, conversation: Conversation, status: str, *, actor: User, ip: str | None
) -> None:
    conversation.status = status
    record(session, f"conversation.{status}", conversation.reference, actor_id=actor.id, ip=ip)


# --- Accès ------------------------------------------------------------------------------


def list_for_client(session: Session, organization: Organization) -> list[Conversation]:
    return list(
        session.scalars(
            select(Conversation)
            .where(Conversation.organization_id == organization.id)
            .order_by(Conversation.last_message_at.desc())
        )
    )


def get_for_client(
    session: Session, organization: Organization, conversation_id: uuid.UUID, *, lock: bool = False
) -> Conversation:
    """Filtre sur l'organisation = cloisonnement : le fil d'un autre est « introuvable »."""
    query = select(Conversation).where(
        Conversation.id == conversation_id, Conversation.organization_id == organization.id
    )
    conversation = session.scalar(query.with_for_update() if lock else query)
    if not conversation:
        raise NotFound("Conversation introuvable.")
    return conversation


def list_all(session: Session, organization_id: uuid.UUID | None = None) -> list[Conversation]:
    # shortcut: pas de pagination ; à ajouter quand le volume le demandera.
    query = select(Conversation).order_by(Conversation.last_message_at.desc())
    if organization_id is not None:
        query = query.where(Conversation.organization_id == organization_id)
    return list(session.scalars(query))


def get(session: Session, conversation_id: uuid.UUID, *, lock: bool = False) -> Conversation:
    query = select(Conversation).where(Conversation.id == conversation_id)
    conversation = session.scalar(query.with_for_update() if lock else query)
    if not conversation:
        raise NotFound("Conversation introuvable.")
    return conversation
