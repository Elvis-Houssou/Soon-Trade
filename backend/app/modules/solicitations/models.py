import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Identity,
    Numeric,
    String,
    Table,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.modules.documents.models import Document
from app.modules.identity.models import Organization, User
from app.modules.sourcing.models import SourcingCase

# Statuts enregistrés. « expired » n'est jamais écrit : il se déduit de la date (voir `state`).
SOLICITATION_STATUSES = ("draft", "sent", "viewed", "answered", "declined", "cancelled")
OFFER_STATUSES = ("submitted", "withdrawn", "under_review", "retained", "not_retained")


def today() -> date:
    return datetime.now(UTC).date()


class SupplierSolicitation(Base):
    """Demande de prix adressée par SOON TRADE à un fournisseur.

    Elle porte sa propre copie du besoin, relue par l'équipe avant l'envoi : le
    fournisseur ne voit jamais la demande de l'acheteur, ni son identité.
    """

    __tablename__ = "supplier_solicitations"
    __table_args__ = (
        # À VALIDER : un seul envoi par fournisseur et par dossier.
        UniqueConstraint("case_id", "organization_id"),
        CheckConstraint("quantity > 0", name="solicitation_quantity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    number: Mapped[int] = mapped_column(Identity(), unique=True)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sourcing_cases.id"), index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)

    product_name: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    unit: Mapped[str] = mapped_column(String(20))
    specifications: Mapped[str | None] = mapped_column(String(4000))
    packaging: Mapped[str | None] = mapped_column(String(200))
    delivery_location: Mapped[str] = mapped_column(String(300))
    desired_date: Mapped[date | None]
    response_deadline: Mapped[date]
    message: Mapped[str | None] = mapped_column(String(2000))

    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Motif du fournisseur qui décline : lu par l'équipe interne.
    decline_reason: Mapped[str | None] = mapped_column(String(2000))

    case: Mapped[SourcingCase] = relationship()
    organization: Mapped[Organization] = relationship()
    created_by: Mapped[User] = relationship()
    offer: Mapped[SupplierOffer | None] = relationship(back_populates="solicitation")

    @property
    def reference(self) -> str:
        return f"ST-SOL-{self.created_at.year}-{self.number:04d}"

    @property
    def state(self) -> str:
        """Statut affiché : une sollicitation sans réponse expire après sa date limite."""
        if self.status in ("sent", "viewed") and self.response_deadline < today():
            return "expired"
        return self.status

    @property
    def supplier_name(self) -> str:
        return self.organization.name

    @property
    def case_reference(self) -> str:
        return self.case.reference


offer_attachments = Table(
    "offer_attachments",
    Base.metadata,
    Column("version_id", ForeignKey("supplier_offer_versions.id"), primary_key=True),
    Column("document_id", ForeignKey("documents.id"), primary_key=True),
)


class SupplierOffer(Base):
    """Réponse d'un fournisseur à une sollicitation. Chaque modification ajoute une version."""

    __tablename__ = "supplier_offers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    number: Mapped[int] = mapped_column(Identity(), unique=True)
    solicitation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier_solicitations.id"), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="submitted", index=True)

    solicitation: Mapped[SupplierSolicitation] = relationship(back_populates="offer")
    versions: Mapped[list[SupplierOfferVersion]] = relationship(order_by="SupplierOfferVersion.version")

    @property
    def reference(self) -> str:
        return f"ST-OFF-{self.created_at.year}-{self.number:04d}"

    @property
    def current(self) -> SupplierOfferVersion:
        return self.versions[-1]

    @property
    def state(self) -> str:
        """À VALIDER : une offre encore en jeu expire à la fin de sa date de validité."""
        if self.status in ("submitted", "under_review", "retained") and self.current.valid_until < today():
            return "expired"
        return self.status


class SupplierOfferVersion(Base):
    """Contenu d'une offre à un instant donné. Insertion seule : une modification est une nouvelle ligne."""

    __tablename__ = "supplier_offer_versions"
    __table_args__ = (
        UniqueConstraint("offer_id", "version"),
        CheckConstraint("unit_price > 0 and quantity > 0 and lead_time_days >= 0", name="offer_values"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    offer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier_offers.id"), index=True)
    version: Mapped[int]
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))

    # NUMERIC et devise explicite : jamais de flottant pour un montant.
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="XOF")
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    lead_time_days: Mapped[int]
    valid_until: Mapped[date]
    packaging: Mapped[str | None] = mapped_column(String(200))
    conditions: Mapped[str | None] = mapped_column(String(4000))

    attachments: Mapped[list[Document]] = relationship(
        secondary=offer_attachments, order_by=Document.created_at
    )

    @property
    def total(self) -> Decimal:
        return (self.unit_price * self.quantity).quantize(Decimal("0.01"))
