"""Dépendances FastAPI d'authentification et d'autorisation, réutilisées par tous les modules."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.errors import Forbidden, Unauthorized
from app.modules.identity import service
from app.modules.identity.models import Organization, User
from app.modules.identity.permissions import Kind, permissions_for

SESSION_COOKIE = "st_session"

DbSession = Annotated[Session, Depends(get_session)]


@dataclass(frozen=True)
class Principal:
    """Qui fait la requête. Tout vient de la base, rien du corps de la requête."""

    user: User
    organization: Organization
    role: str

    @property
    def permissions(self) -> frozenset[str]:
        return permissions_for(self.role)


def client_ip(request: Request) -> str | None:
    # Derrière Render, uvicorn tourne avec --proxy-headers (render.yaml) : `client.host`
    # porte alors l'adresse réelle transmise par le proxy, pas celle du proxy.
    return request.client.host if request.client else None


def current_principal(request: Request, session: DbSession) -> Principal:
    token = request.cookies.get(SESSION_COOKIE)
    user = service.user_for_session_token(session, token) if token else None
    if not user:
        raise Unauthorized("Connexion requise.")
    return Principal(user=user, organization=user.membership.organization, role=user.membership.role)


CurrentPrincipal = Annotated[Principal, Depends(current_principal)]


def require_permission(permission: str) -> Callable[[Principal], Principal]:
    def dependency(principal: CurrentPrincipal) -> Principal:
        if permission not in principal.permissions:
            raise Forbidden("Vous n'avez pas les droits pour cette action.")
        return principal

    return dependency


def require_space(kind: Kind) -> Callable[[Principal], Principal]:
    """Réserve une route à un espace : acheteur, fournisseur ou interne."""

    def dependency(principal: CurrentPrincipal) -> Principal:
        if principal.organization.kind != kind:
            raise Forbidden("Cet espace ne vous est pas accessible.")
        return principal

    return dependency
