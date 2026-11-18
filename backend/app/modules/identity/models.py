import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(primary_key=True, default=uuid.uuid7)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


def _instant() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True))


def _optional_instant() -> Mapped[datetime | None]:
    return mapped_column(DateTime(timezone=True))


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = (CheckConstraint("kind in ('buyer', 'supplier', 'internal')", name="organization_kind"),)

    id: Mapped[uuid.UUID] = _pk()
    created_at: Mapped[datetime] = _created()
    name: Mapped[str] = mapped_column(String(200))
    # Détermine l'espace accessible. Lu en base, jamais reçu du navigateur.
    kind: Mapped[str] = mapped_column(String(20))

    country: Mapped[str | None] = mapped_column(String(2))
    city: Mapped[str | None] = mapped_column(String(120))
    address: Mapped[str | None] = mapped_column(String(300))
    phone: Mapped[str | None] = mapped_column(String(40))
    registration_number: Mapped[str | None] = mapped_column(String(80))
    tax_number: Mapped[str | None] = mapped_column(String(80))

    # pending | verified | rejected | suspended. Décidé par SOON TRADE uniquement.
    verification_status: Mapped[str] = mapped_column(String(20), server_default="pending")
    # Note interne : ne figure dans aucune réponse destinée à l'organisation elle-même.
    verification_note: Mapped[str | None] = mapped_column(String(1000))


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _pk()
    created_at: Mapped[datetime] = _created()
    email: Mapped[str] = mapped_column(String(320), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    # Langue des e-mails : la dernière choisie dans l'application.
    locale: Mapped[str] = mapped_column(String(2), default="fr", server_default="fr")

    membership: Mapped[Membership] = relationship(back_populates="user")


class Membership(Base):
    """Rattachement d'un utilisateur à son organisation, avec son rôle.

    shortcut: une seule organisation par utilisateur (contrainte d'unicité) ;
    la lever le jour où une même personne doit agir pour plusieurs entreprises.
    """

    __tablename__ = "organization_members"

    id: Mapped[uuid.UUID] = _pk()
    created_at: Mapped[datetime] = _created()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    role: Mapped[str] = mapped_column(String(40))

    user: Mapped[User] = relationship(back_populates="membership")
    organization: Mapped[Organization] = relationship()


class UserSession(Base):
    """Session opaque : seul le condensat du jeton est stocké."""

    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = _pk()
    created_at: Mapped[datetime] = _created()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = _instant()
    revoked_at: Mapped[datetime | None] = _optional_instant()

    user: Mapped[User] = relationship()


class Invitation(Base):
    __tablename__ = "invitations"

    id: Mapped[uuid.UUID] = _pk()
    created_at: Mapped[datetime] = _created()
    email: Mapped[str] = mapped_column(String(320), index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    role: Mapped[str] = mapped_column(String(40))
    invited_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = _instant()
    accepted_at: Mapped[datetime | None] = _optional_instant()

    organization: Mapped[Organization] = relationship()


class PasswordReset(Base):
    __tablename__ = "password_resets"

    id: Mapped[uuid.UUID] = _pk()
    created_at: Mapped[datetime] = _created()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = _instant()
    used_at: Mapped[datetime | None] = _optional_instant()

    user: Mapped[User] = relationship()
