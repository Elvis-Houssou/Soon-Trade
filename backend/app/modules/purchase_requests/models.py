import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Identity, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.modules.identity.models import Organization, User

# Sous-ensemble de docs/business-rules/statuts-et-transitions.md en service (phases 5 à 7).
STATUSES = (
    "draft",
    "submitted",
    "info_requested",
    "qualified",
    "in_sourcing",
    "proposal_sent",
    "accepted",
    "closed",
    "rejected",
    "cancelled",
)


class PurchaseRequest(Base):
    """Demande d'achat d'un acheteur. Invisible des fournisseurs et des autres acheteurs."""

    __tablename__ = "purchase_requests"
    __table_args__ = (CheckConstraint("quantity > 0", name="purchase_request_quantity"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Numéro lisible, attribué par la base : sert à construire la référence.
    number: Mapped[int] = mapped_column(Identity(), unique=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)

    product_name: Mapped[str] = mapped_column(String(200))
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    unit: Mapped[str] = mapped_column(String(20))
    specifications: Mapped[str | None] = mapped_column(String(4000))
    packaging: Mapped[str | None] = mapped_column(String(200))
    delivery_location: Mapped[str] = mapped_column(String(300))
    desired_date: Mapped[date | None]
    additional_info: Mapped[str | None] = mapped_column(String(4000))

    organization: Mapped[Organization] = relationship()
    # uuid7 est ordonné dans le temps : l'identifiant donne l'ordre chronologique.
    history: Mapped[list[PurchaseRequestEvent]] = relationship(order_by="PurchaseRequestEvent.id")

    @property
    def reference(self) -> str:
        return f"ST-ACH-{self.created_at.year}-{self.number:04d}"

    @property
    def buyer_name(self) -> str:
        return self.organization.name


class PurchaseRequestEvent(Base):
    """Historique des changements d'état : qui, quand, de, vers, message. Insertion seule."""

    __tablename__ = "purchase_request_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_requests.id"), index=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    # Toujours destiné à l'acheteur (précision demandée, motif de rejet, réponse). Les
    # remarques internes vont dans les notes du dossier de sourcing, jamais ici.
    message: Mapped[str | None] = mapped_column(String(2000))

    actor: Mapped[User] = relationship()

    @property
    def actor_name(self) -> str:
        return self.actor.full_name
