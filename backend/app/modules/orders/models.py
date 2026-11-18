import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Identity, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.modules.documents.models import Document
from app.modules.identity.models import Organization, User
from app.modules.proposals.models import BuyerProposal

ORDER_STATUSES = (
    "created",
    "confirmed",
    "in_preparation",
    "shipped",
    "delivered",
    "closed",
    "cancelled",
    "in_dispute",
)
DELIVERY_STATUSES = ("planned", "in_preparation", "in_transit", "delivered", "confirmed", "incident")
# Version du format des copies figées : un changement de format ne réécrit jamais l'ancien.
TERMS_SCHEMA = 1


class Order(Base):
    """Commande née d'une proposition acceptée.

    `terms` est la copie figée de la version acceptée (README §9) : modifier ensuite la
    proposition, une offre ou le catalogue ne change rien à une commande passée.
    """

    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    number: Mapped[int] = mapped_column(Identity(), unique=True)
    # Une proposition ne donne qu'une commande.
    proposal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("buyer_proposals.id"), unique=True)
    # Acheteur, recopié pour cloisonner sans traverser la proposition.
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="created", index=True)
    # Statut à retrouver quand le dernier litige se referme.
    status_before_dispute: Mapped[str | None] = mapped_column(String(20))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    currency: Mapped[str] = mapped_column(String(3))
    buyer_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    terms: Mapped[dict[str, Any]] = mapped_column(JSONB)

    proposal: Mapped[BuyerProposal] = relationship()
    organization: Mapped[Organization] = relationship()
    supplier_orders: Mapped[list[SupplierOrder]] = relationship(
        back_populates="order", order_by="SupplierOrder.number"
    )
    deliveries: Mapped[list[Delivery]] = relationship(back_populates="order", order_by="Delivery.number")
    events: Mapped[list[OrderEvent]] = relationship(order_by="OrderEvent.id")

    @property
    def reference(self) -> str:
        return f"ST-CMD-{self.created_at.year}-{self.number:04d}"

    @property
    def buyer_name(self) -> str:
        return self.organization.name

    @property
    def proposal_reference(self) -> str:
        return self.proposal.reference

    @property
    def request_reference(self) -> str:
        return self.proposal.request_reference


class OrderEvent(Base):
    """Historique de la commande. Insertion seule. Le message (motif d'annulation) va à l'acheteur."""

    __tablename__ = "order_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    # Absent pour un changement automatique (expédition, livraison, litige).
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    message: Mapped[str | None] = mapped_column(String(2000))

    actor: Mapped[User | None] = relationship()

    @property
    def actor_name(self) -> str | None:
        return self.actor.full_name if self.actor else None


class SupplierOrder(Base):
    """Bon de commande adressé à un fournisseur : sa part, à son prix. Ni acheteur, ni prix de vente."""

    __tablename__ = "supplier_orders"
    __table_args__ = (UniqueConstraint("order_id", "offer_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    number: Mapped[int] = mapped_column(Identity(), unique=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    offer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier_offers.id"))
    # Le fournisseur ne voit son bon qu'une fois la commande confirmée par SOON TRADE.
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    currency: Mapped[str] = mapped_column(String(3))
    supplier_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    terms: Mapped[dict[str, Any]] = mapped_column(JSONB)

    order: Mapped[Order] = relationship(back_populates="supplier_orders")
    organization: Mapped[Organization] = relationship()
    deliveries: Mapped[list[Delivery]] = relationship(
        back_populates="supplier_order", order_by="Delivery.number", viewonly=True
    )

    @property
    def reference(self) -> str:
        return f"ST-BC-{self.created_at.year}-{self.number:04d}"

    @property
    def supplier_name(self) -> str:
        return self.organization.name

    @property
    def supplier_state(self) -> str:
        """Statut vu par le fournisseur : un litige reste entre l'acheteur et SOON TRADE."""
        status = self.order.status
        if status == "in_dispute":
            return self.order.status_before_dispute or "delivered"
        return status


class Delivery(Base):
    """Livraison d'une commande, entière ou de la part d'un fournisseur."""

    __tablename__ = "deliveries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    number: Mapped[int] = mapped_column(Identity(), unique=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    supplier_order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("supplier_orders.id"), index=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="planned", index=True)

    # Visibles de l'acheteur et du fournisseur concerné.
    description: Mapped[str] = mapped_column(String(500))
    planned_date: Mapped[date]
    carrier: Mapped[str | None] = mapped_column(String(120))
    tracking_number: Mapped[str | None] = mapped_column(String(120))
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    order: Mapped[Order] = relationship(back_populates="deliveries")
    supplier_order: Mapped[SupplierOrder | None] = relationship(back_populates="deliveries")
    events: Mapped[list[DeliveryEvent]] = relationship(order_by="DeliveryEvent.id")
    proofs: Mapped[list[DeliveryProof]] = relationship(order_by="DeliveryProof.created_at")

    @property
    def reference(self) -> str:
        return f"ST-LIV-{self.created_at.year}-{self.number:04d}"

    @property
    def order_reference(self) -> str:
        return self.order.reference

    @property
    def supplier_name(self) -> str | None:
        return self.supplier_order.supplier_name if self.supplier_order else None

    @property
    def supplier_order_reference(self) -> str | None:
        return self.supplier_order.reference if self.supplier_order else None


class DeliveryEvent(Base):
    """Historique d'une livraison. Le message (incident) est interne : l'acheteur ne voit que l'état."""

    __tablename__ = "delivery_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    delivery_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("deliveries.id"), index=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    message: Mapped[str | None] = mapped_column(String(2000))

    actor: Mapped[User] = relationship()

    @property
    def actor_name(self) -> str:
        return self.actor.full_name


class DeliveryProof(Base):
    """Preuve de livraison (bon signé, photo…), stockée comme tout document privé."""

    __tablename__ = "delivery_proofs"

    delivery_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("deliveries.id"), primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    added_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    # À VALIDER : seule l'équipe SOON TRADE publie une preuve à l'acheteur ; celle d'un
    # fournisseur peut le désigner (en-tête, tampon) et reste interne.
    buyer_visible: Mapped[bool] = mapped_column(Boolean, default=False)

    document: Mapped[Document] = relationship()

    @property
    def filename(self) -> str:
        return self.document.filename

    @property
    def id(self) -> uuid.UUID:
        return self.document_id
