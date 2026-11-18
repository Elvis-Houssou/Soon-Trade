import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# À VALIDER : liste de départ des pièces administratives (KYC).
DOCUMENT_TYPES = (
    "company_registration",
    "tax_certificate",
    "id_document",
    "offer_attachment",
    "delivery_proof",
    "other",
)
STATUSES = ("pending", "approved", "rejected")


class Document(Base):
    """Métadonnées d'un document privé. Le fichier est dans le bucket S3, sous une clé imprévisible."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    doc_type: Mapped[str] = mapped_column(String(40))
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int]
    storage_key: Mapped[str] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # Note interne : absente des réponses destinées à l'organisation.
    review_note: Mapped[str | None] = mapped_column(String(1000))
