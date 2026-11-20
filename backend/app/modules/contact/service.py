"""Formulaire de contact du site public : enregistrer, puis prévenir l'équipe."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.email import send_email
from app.core.errors import TooManyRequests
from app.modules.contact.models import ContactRequest
from app.modules.identity.permissions import ORGANIZATION_CREATE_BUYER, ORGANIZATION_CREATE_SUPPLIER
from app.modules.notifications.service import notify, staff_with

logger = logging.getLogger(__name__)
# À VALIDER : 5 messages par heure et par adresse IP, contre les envois automatiques.
MAX_PER_HOUR = 5
PROFILE_LABEL = {"buyer": "Acheteur", "supplier": "Fournisseur", "other": "Autre"}


def submit(session: Session, request: ContactRequest) -> None:
    since = datetime.now(UTC) - timedelta(hours=1)
    recent = session.scalar(
        select(func.count())
        .select_from(ContactRequest)
        .where(ContactRequest.ip == request.ip, ContactRequest.created_at >= since)
    )
    if request.ip and (recent or 0) >= MAX_PER_HOUR:
        raise TooManyRequests("Trop de messages envoyés. Réessayez plus tard.")
    session.add(request)
    session.commit()

    # Qui peut créer le compte demandé : ventes pour un acheteur, sourcing pour un fournisseur.
    permissions = {
        "buyer": [ORGANIZATION_CREATE_BUYER],
        "supplier": [ORGANIZATION_CREATE_SUPPLIER],
    }.get(request.profile, [ORGANIZATION_CREATE_BUYER, ORGANIZATION_CREATE_SUPPLIER])
    recipients = {u.id: u for p in permissions for u in staff_with(session, p)}.values()
    notify(
        session,
        recipients,
        "contact_received",
        link="internal/crm",
        params={"name": request.name, "profile": request.profile},
    )
    # Le message complet part par e-mail : « Répondre » écrit directement à la personne.
    text = "\n".join(
        [
            "Nouveau message depuis le site SOON TRADE.",
            "",
            f"Profil : {PROFILE_LABEL.get(request.profile, request.profile)}",
            f"Nom : {request.name}",
            f"Entreprise : {request.company or '-'}",
            f"E-mail : {request.email}",
            f"Téléphone : {request.phone or '-'}",
            "",
            request.message,
        ]
    )
    for user in recipients:
        try:
            send_email(user.email, f"Contact site : {request.name}", text, reply_to=request.email)
        except Exception:
            logger.exception("contact_email_failed")
