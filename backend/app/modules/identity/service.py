"""Règles métier de l'identité. Aucune dépendance à HTTP : les routes ne font qu'appeler ici."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core import mail
from app.core.config import get_settings
from app.core.email import send_email
from app.core.errors import AppError, Conflict, NotFound, TooManyRequests, Unauthorized
from app.modules.audit.models import AuditLog, record
from app.modules.identity.models import (
    Invitation,
    Membership,
    Organization,
    PasswordReset,
    User,
    UserSession,
)
from app.modules.identity.permissions import OWNER_ROLE, ROLE_KIND, Kind
from app.modules.identity.security import (
    DUMMY_HASH,
    hash_password,
    hash_token,
    new_token,
    verify_password,
)


def _now() -> datetime:
    return datetime.now(UTC)


def normalize_email(email: str) -> str:
    return email.strip().lower()


# --- Connexion et sessions -------------------------------------------------


def authenticate(session: Session, email: str, password: str, ip: str | None) -> User:
    settings = get_settings()
    email = normalize_email(email)

    since = _now() - timedelta(minutes=settings.login_lockout_minutes)
    failures = session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.action == "auth.login_failed", AuditLog.subject == email, AuditLog.created_at >= since
        )
    )
    if (failures or 0) >= settings.login_max_failures:
        raise TooManyRequests("Trop de tentatives. Réessayez dans quelques minutes.")

    user = session.scalar(select(User).where(User.email == email))
    valid = verify_password(password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid or not user.is_active:
        record(session, "auth.login_failed", email, ip=ip)
        session.commit()
        # Même message dans tous les cas : ne pas révéler si le compte existe.
        raise Unauthorized("Adresse e-mail ou mot de passe incorrect.")

    record(session, "auth.login", email, actor_id=user.id, ip=ip)
    return user


def create_session(session: Session, user: User) -> str:
    raw, token_hash = new_token()
    expires = _now() + timedelta(days=get_settings().session_days)
    session.add(UserSession(user_id=user.id, token_hash=token_hash, expires_at=expires))
    return raw


def user_for_session_token(session: Session, raw: str) -> User | None:
    user = session.scalar(
        select(User)
        .join(UserSession, UserSession.user_id == User.id)
        .where(
            UserSession.token_hash == hash_token(raw),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > _now(),
            User.is_active,
        )
    )
    return user


def revoke_session(session: Session, raw: str) -> None:
    session.execute(
        update(UserSession).where(UserSession.token_hash == hash_token(raw)).values(revoked_at=_now())
    )


def _revoke_all_sessions(session: Session, user: User) -> None:
    session.execute(
        update(UserSession)
        .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


# --- Invitations -------------------------------------------------------------


def create_invitation(
    session: Session,
    *,
    email: str,
    organization: Organization,
    role: str,
    invited_by: User | None,
    ip: str | None,
) -> str:
    email = normalize_email(email)
    if ROLE_KIND.get(role) != organization.kind:
        raise AppError("Ce rôle n'existe pas pour ce type d'organisation.")
    if session.scalar(select(User.id).where(User.email == email)):
        raise Conflict("Un compte existe déjà pour cette adresse.")

    # Une seule invitation active par adresse : la nouvelle remplace l'ancienne.
    session.execute(delete(Invitation).where(Invitation.email == email, Invitation.accepted_at.is_(None)))
    raw, token_hash = new_token()
    session.add(
        Invitation(
            email=email,
            organization_id=organization.id,
            role=role,
            invited_by_id=invited_by.id if invited_by else None,
            token_hash=token_hash,
            expires_at=_now() + timedelta(days=get_settings().invitation_days),
        )
    )
    record(
        session,
        "invitation.created",
        email,
        actor_id=invited_by.id if invited_by else None,
        ip=ip,
        organization_id=str(organization.id),
        role=role,
    )
    # La langue de l'invité est inconnue : on écrit dans celle de la personne qui invite.
    locale = invited_by.locale if invited_by else "fr"
    subject, text = mail.render(
        "invitation",
        locale,
        link=f"{get_settings().frontend_url}/{locale}/invitation/{raw}",
        organization=organization.name,
        days=get_settings().invitation_days,
    )
    send_email(email, subject, text)
    return raw


def create_organization_with_owner(
    session: Session, *, name: str, kind: Kind, owner_email: str, created_by: User, ip: str | None
) -> Organization:
    # À VALIDER : seuls les fournisseurs passent par une vérification ; un acheteur est actif d'emblée.
    status = "pending" if kind == "supplier" else "verified"
    organization = Organization(name=name.strip(), kind=kind, verification_status=status)
    session.add(organization)
    session.flush()
    record(session, "organization.created", str(organization.id), actor_id=created_by.id, ip=ip, kind=kind)
    create_invitation(
        session,
        email=owner_email,
        organization=organization,
        role=OWNER_ROLE[kind],
        invited_by=created_by,
        ip=ip,
    )
    return organization


def valid_invitation(session: Session, raw: str) -> Invitation:
    invitation = session.scalar(
        select(Invitation).where(
            Invitation.token_hash == hash_token(raw),
            Invitation.accepted_at.is_(None),
            Invitation.expires_at > _now(),
        )
    )
    if not invitation:
        raise NotFound("Cette invitation est invalide ou a expiré.")
    return invitation


def accept_invitation(session: Session, raw: str, *, full_name: str, password: str, ip: str | None) -> User:
    invitation = valid_invitation(session, raw)
    if session.scalar(select(User.id).where(User.email == invitation.email)):
        raise Conflict("Un compte existe déjà pour cette adresse.")

    user = User(email=invitation.email, full_name=full_name.strip(), password_hash=hash_password(password))
    session.add(user)
    session.flush()
    session.add(Membership(user_id=user.id, organization_id=invitation.organization_id, role=invitation.role))
    invitation.accepted_at = _now()
    record(session, "invitation.accepted", invitation.email, actor_id=user.id, ip=ip)
    return user


# --- Mot de passe oublié -----------------------------------------------------


def request_password_reset(session: Session, email: str, ip: str | None) -> None:
    """Ne dit jamais si l'adresse correspond à un compte."""
    email = normalize_email(email)
    record(session, "password.reset_requested", email, ip=ip)
    user = session.scalar(select(User).where(User.email == email, User.is_active))
    if not user:
        return
    raw, token_hash = new_token()
    minutes = get_settings().password_reset_minutes
    session.add(
        PasswordReset(user_id=user.id, token_hash=token_hash, expires_at=_now() + timedelta(minutes=minutes))
    )
    subject, text = mail.render(
        "password_reset",
        user.locale,
        link=f"{get_settings().frontend_url}/{user.locale}/mot-de-passe/{raw}",
        minutes=minutes,
    )
    send_email(email, subject, text)


def reset_password(session: Session, raw: str, password: str, ip: str | None) -> None:
    reset = session.scalar(
        select(PasswordReset).where(
            PasswordReset.token_hash == hash_token(raw),
            PasswordReset.used_at.is_(None),
            PasswordReset.expires_at > _now(),
        )
    )
    if not reset:
        raise NotFound("Ce lien est invalide ou a expiré.")
    reset.used_at = _now()
    reset.user.password_hash = hash_password(password)
    # Un mot de passe changé ferme toutes les sessions ouvertes.
    _revoke_all_sessions(session, reset.user)
    record(session, "password.reset", reset.user.email, actor_id=reset.user.id, ip=ip)
