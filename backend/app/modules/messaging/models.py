import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Identity, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.modules.identity.models import Organization, User


class Conversation(Base):
    """Fil entre UNE organisation cliente (acheteur ou fournisseur) et SOON TRADE.

    Une seule organisation cliente par fil : par construction, aucun canal direct entre un
    acheteur et un fournisseur (README §5 et §8).
    """

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    number: Mapped[int] = mapped_column(Identity(), unique=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    subject: Mapped[str] = mapped_column(String(200))
    # Référence d'objet évoqué (demande, commande…), saisie librement : simple repère.
    context_reference: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization: Mapped[Organization] = relationship()
    messages: Mapped[list[Message]] = relationship(order_by="Message.id")

    @property
    def reference(self) -> str:
        return f"ST-MSG-{self.created_at.year}-{self.number:04d}"

    @property
    def organization_name(self) -> str:
        return self.organization.name

    @property
    def organization_kind(self) -> str:
        return self.organization.kind


class Message(Base):
    """Message d'un fil. Insertion seule. `internal` : note entre collaborateurs, jamais montrée au client."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id"), index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    from_staff: Mapped[bool] = mapped_column(Boolean)
    internal: Mapped[bool] = mapped_column(Boolean, default=False)
    body: Mapped[str] = mapped_column(String(4000))

    author: Mapped[User] = relationship()

    @property
    def author_name(self) -> str:
        return self.author.full_name


class ConversationRead(Base):
    """Jusqu'où un utilisateur a lu un fil : sert au compteur de messages non lus."""

    __tablename__ = "conversation_reads"

    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
