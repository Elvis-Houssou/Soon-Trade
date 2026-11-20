"""Amorçage : crée l'organisation interne SOON TRADE et invite son premier administrateur.

    uv run python -m app.cli invite-admin prenom@exemple.com

Aucun mot de passe ne passe par la ligne de commande : l'administrateur le choisit
lui-même en ouvrant le lien d'invitation (envoyé par e-mail, ou écrit dans les logs
quand aucun fournisseur d'e-mail n'est configuré).
"""

import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_engine
from app.core.logging import configure_logging
from app.modules.identity import service
from app.modules.identity.models import Organization


def invite_admin(email: str) -> str:
    with Session(get_engine()) as session:
        organization = session.scalar(select(Organization).where(Organization.kind == "internal"))
        if not organization:
            organization = Organization(name="SOON TRADE", kind="internal")
            session.add(organization)
            session.flush()
        token = service.create_invitation(
            session, email=email, organization=organization, role="admin", invited_by=None, ip=None
        )
        session.commit()
    return f"{get_settings().frontend_url}/fr/invitation/{token}"


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "invite-admin":
        sys.exit(__doc__)
    configure_logging("WARNING")
    link = invite_admin(sys.argv[2])
    # Lien personnel : à transmettre uniquement à la personne invitée, il expire en 7 jours.
    print(f"Invitation créée (e-mail envoyé si Resend l'accepte). Lien direct : {link}")
