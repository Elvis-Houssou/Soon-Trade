import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Identity, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.modules.identity.models import Organization, User
from app.modules.purchase_requests.models import PurchaseRequest


class SourcingCase(Base):
    """Dossier de sourcing d'une demande qualifiée. Strictement interne."""

    __tablename__ = "sourcing_cases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    number: Mapped[int] = mapped_column(Identity(), unique=True)
    # Unicité : une demande n'ouvre qu'un seul dossier.
    request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_requests.id"), unique=True)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)

    request: Mapped[PurchaseRequest] = relationship()
    assignee: Mapped[User | None] = relationship()
    candidates: Mapped[list[SourcingCandidate]] = relationship(order_by="SourcingCandidate.id")
    notes: Mapped[list[SourcingNote]] = relationship(order_by="SourcingNote.id")

    @property
    def reference(self) -> str:
        return f"ST-SRC-{self.created_at.year}-{self.number:04d}"


class SourcingCandidate(Base):
    """Fournisseur présélectionné dans un dossier. Le fournisseur n'en sait rien."""

    __tablename__ = "sourcing_candidates"
    __table_args__ = (UniqueConstraint("case_id", "organization_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sourcing_cases.id"), index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    added_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))

    organization: Mapped[Organization] = relationship()


class SourcingNote(Base):
    """Note interne d'un dossier. Table à part : aucune réponse client ne peut la contenir."""

    __tablename__ = "sourcing_notes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sourcing_cases.id"), index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(String(4000))

    author: Mapped[User] = relationship()
