import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ContactRequest(Base):
    """Message laissé depuis le site public par un acheteur ou un fournisseur intéressé.
    Conservé en base pour qu'aucune demande ne se perde si l'e-mail à l'équipe échoue."""

    __tablename__ = "contact_requests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    profile: Mapped[str] = mapped_column(String(20))  # buyer, supplier, other
    name: Mapped[str] = mapped_column(String(120))
    company: Mapped[str | None] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(Text)
    locale: Mapped[str] = mapped_column(String(5))
    ip: Mapped[str | None] = mapped_column(String(64), index=True)
