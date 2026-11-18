import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Identity, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.modules.identity.models import User
from app.modules.orders.models import Delivery, Order

CLAIM_STATUSES = ("open", "under_review", "resolved", "rejected", "closed")
# À VALIDER : motifs de départ.
CLAIM_CATEGORIES = ("quantity", "quality", "delay", "damage", "other")


class Claim(Base):
    """Réclamation d'un acheteur sur une commande, traitée par SOON TRADE."""

    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    number: Mapped[int] = mapped_column(Identity(), unique=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    # Acheteur, recopié pour cloisonner.
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    delivery_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("deliveries.id"))
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)

    category: Mapped[str] = mapped_column(String(20))
    subject: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(4000))
    # Réponse de SOON TRADE, lue par l'acheteur.
    resolution: Mapped[str | None] = mapped_column(String(2000))

    order: Mapped[Order] = relationship()
    delivery: Mapped[Delivery | None] = relationship()
    events: Mapped[list[ClaimEvent]] = relationship(order_by="ClaimEvent.id")

    @property
    def reference(self) -> str:
        return f"ST-REC-{self.created_at.year}-{self.number:04d}"

    @property
    def order_reference(self) -> str:
        return self.order.reference

    @property
    def delivery_reference(self) -> str | None:
        return self.delivery.reference if self.delivery else None

    @property
    def buyer_name(self) -> str:
        return self.order.buyer_name


class ClaimEvent(Base):
    """Historique d'une réclamation. Insertion seule."""

    __tablename__ = "claim_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claims.id"), index=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    message: Mapped[str | None] = mapped_column(String(2000))

    actor: Mapped[User] = relationship()

    @property
    def actor_name(self) -> str:
        return self.actor.full_name
