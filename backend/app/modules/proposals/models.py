import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.modules.identity.models import User
from app.modules.purchase_requests.models import PurchaseRequest
from app.modules.solicitations.models import SupplierOffer, today
from app.modules.sourcing.models import SourcingCase

# Statuts enregistrés. « expired » n'est jamais écrit : il se déduit de la validité (voir `state`).
PROPOSAL_STATUSES = (
    "draft",
    "pending_validation",
    "sent",
    "changes_requested",
    "accepted",
    "refused",
    "cancelled",
)


class BuyerProposal(Base):
    """Proposition commerciale de SOON TRADE à un acheteur.

    Elle est construite à partir d'offres fournisseurs, mais l'acheteur n'en voit que le
    contenu publié : ni fournisseur, ni prix d'achat, ni marge.
    """

    __tablename__ = "buyer_proposals"
    __table_args__ = (
        # Une seule proposition en cours par dossier ; une proposition annulée libère la place.
        Index(
            "uq_buyer_proposals_open_case",
            "case_id",
            unique=True,
            postgresql_where=text("status <> 'cancelled'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    number: Mapped[int] = mapped_column(Identity(), unique=True)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sourcing_cases.id"), index=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    # Qui a demandé la validation : une autre personne doit valider (principe des quatre yeux).
    submitted_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    accepted_version: Mapped[int | None]

    case: Mapped[SourcingCase] = relationship()
    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id])
    submitted_by: Mapped[User | None] = relationship(foreign_keys=[submitted_by_id])
    versions: Mapped[list[BuyerProposalVersion]] = relationship(order_by="BuyerProposalVersion.version")
    # uuid7 est ordonné dans le temps : l'identifiant donne l'ordre chronologique.
    events: Mapped[list[BuyerProposalEvent]] = relationship(order_by="BuyerProposalEvent.id")

    @property
    def reference(self) -> str:
        return f"ST-PRO-{self.created_at.year}-{self.number:04d}"

    @property
    def request(self) -> PurchaseRequest:
        return self.case.request

    @property
    def current(self) -> BuyerProposalVersion:
        return self.versions[-1]

    @property
    def sent_versions(self) -> list[BuyerProposalVersion]:
        return [v for v in self.versions if v.sent_at is not None]

    @property
    def state(self) -> str:
        """Statut interne affiché : une proposition envoyée expire après sa date de validité."""
        if self.status == "sent" and self.current.valid_until < today():
            return "expired"
        return self.status

    @property
    def buyer_state(self) -> str:
        """Statut vu par l'acheteur : tant qu'une nouvelle version se prépare, sa demande de
        modification est « en cours de traitement »."""
        if self.status in ("draft", "pending_validation"):
            return "changes_requested"
        return self.state

    @property
    def case_reference(self) -> str:
        return self.case.reference

    @property
    def request_id(self) -> uuid.UUID:
        return self.request.id

    @property
    def request_reference(self) -> str:
        return self.request.reference

    @property
    def buyer_name(self) -> str:
        return self.request.organization.name


class BuyerProposalVersion(Base):
    """Contenu d'une proposition. Figée dès son envoi : une modification est une nouvelle version."""

    __tablename__ = "buyer_proposal_versions"
    __table_args__ = (
        UniqueConstraint("proposal_id", "version"),
        CheckConstraint("lead_time_days >= 0", name="proposal_lead_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    proposal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("buyer_proposals.id"), index=True)
    version: Mapped[int]
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    currency: Mapped[str] = mapped_column(String(3), default="XOF")
    lead_time_days: Mapped[int]
    valid_until: Mapped[date]
    delivery_location: Mapped[str] = mapped_column(String(300))
    # Conditions publiées à l'acheteur (paiement, livraison, garanties…).
    conditions: Mapped[str | None] = mapped_column(String(4000))
    message: Mapped[str | None] = mapped_column(String(2000))

    lines: Mapped[list[BuyerProposalLine]] = relationship(
        order_by="BuyerProposalLine.position", cascade="all, delete-orphan"
    )

    @property
    def total(self) -> Decimal:
        return sum((line.total for line in self.lines), Decimal("0.00"))

    @property
    def cost_total(self) -> Decimal:
        return sum((line.cost_total for line in self.lines), Decimal("0.00"))

    @property
    def margin(self) -> Decimal:
        return self.total - self.cost_total


class BuyerProposalLine(Base):
    """Ligne de proposition. `offer_id` et `supplier_unit_price` sont strictement internes."""

    __tablename__ = "buyer_proposal_lines"
    __table_args__ = (CheckConstraint("quantity > 0 and unit_price > 0", name="proposal_line_values"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("buyer_proposal_versions.id"), index=True)
    position: Mapped[int]
    product_name: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    unit: Mapped[str] = mapped_column(String(20))
    # NUMERIC et devise portée par la version : jamais de flottant pour un montant.
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    # Offre fournisseur d'origine et son prix au moment de la reprise (pour la marge).
    # Absents pour une ligne sans fournisseur (transport, service…).
    offer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("supplier_offers.id"))
    supplier_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    offer: Mapped[SupplierOffer | None] = relationship()

    @property
    def total(self) -> Decimal:
        return (self.unit_price * self.quantity).quantize(Decimal("0.01"))

    @property
    def cost_total(self) -> Decimal:
        if self.supplier_unit_price is None:
            return Decimal("0.00")
        return (self.supplier_unit_price * self.quantity).quantize(Decimal("0.01"))

    @property
    def offer_reference(self) -> str | None:
        return self.offer.reference if self.offer else None

    @property
    def supplier_name(self) -> str | None:
        return self.offer.solicitation.supplier_name if self.offer else None


class BuyerProposalEvent(Base):
    """Historique des changements d'état. Insertion seule.

    Les messages de retour de validation sont internes ; ceux de l'acheteur (demande de
    modification, motif de refus) sont les siens. Le schéma acheteur filtre (voir router).
    """

    __tablename__ = "buyer_proposal_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    proposal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("buyer_proposals.id"), index=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    version: Mapped[int]
    message: Mapped[str | None] = mapped_column(String(2000))

    actor: Mapped[User] = relationship()

    @property
    def actor_name(self) -> str:
        return self.actor.full_name
