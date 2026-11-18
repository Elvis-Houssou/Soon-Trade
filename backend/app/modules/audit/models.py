import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.db import Base


class AuditLog(Base):
    """Journal en insertion seule : aucune route ne modifie ni ne supprime une ligne."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    # Pas de clé étrangère : la trace doit survivre à la désactivation d'un compte.
    actor_id: Mapped[uuid.UUID | None]
    action: Mapped[str] = mapped_column(String(80), index=True)
    subject: Mapped[str] = mapped_column(String(320), index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    ip: Mapped[str | None] = mapped_column(String(45))


def record(
    session: Session,
    action: str,
    subject: str,
    *,
    actor_id: uuid.UUID | None = None,
    ip: str | None = None,
    **details: Any,
) -> None:
    """Ajoute une trace dans la transaction en cours. Jamais de secret dans `details`."""
    session.add(AuditLog(actor_id=actor_id, action=action, subject=subject, details=details, ip=ip))
