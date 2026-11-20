"""Protections transverses : configuration de production, en-têtes de sécurité, journal des requêtes."""

import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

from fastapi import FastAPI, Request, Response

from app.core.config import Settings

logger = logging.getLogger("app.request")

# Pages de documentation (désactivées en production) : elles chargent leurs scripts d'un CDN.
_DOCS = ("/docs", "/openapi.json")
_LOCAL_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0")  # noqa: S104 - liste de refus, pas une écoute


def production_problems(settings: Settings) -> list[str]:
    """Réglages dangereux hors développement. L'API refuse de démarrer tant qu'il en reste."""
    if settings.environment not in ("staging", "production"):
        return []
    problems = []
    if not settings.frontend_url.startswith("https://"):
        problems.append("FRONTEND_URL doit être en https.")
    if not settings.cors_origins or any(
        o == "*" or not o.startswith("https://") for o in settings.cors_origins
    ):
        problems.append("CORS_ORIGINS doit lister des origines https précises (jamais *).")
    if urlparse(settings.database_url.replace("+psycopg", "")).hostname in _LOCAL_HOSTS:
        problems.append("DATABASE_URL pointe vers une base locale.")
    if not (settings.resend_api_key or settings.brevo_api_key):
        problems.append("RESEND_API_KEY ou BREVO_API_KEY manquante : aucun e-mail ne partirait.")
    if settings.s3_endpoint_url and not settings.s3_endpoint_url.startswith("https://"):
        problems.append("S3_ENDPOINT_URL doit être vide (AWS) ou en https.")
    if settings.s3_access_key_id == "local" or settings.s3_secret_access_key == "local":  # noqa: S105
        problems.append("Les clés S3 sont celles de l'émulateur local.")
    if settings.seed_password:
        problems.append("SEED_PASSWORD ne doit pas exister hors développement.")
    return problems


def install(app: FastAPI, settings: Settings) -> None:
    """En-têtes de sécurité sur chaque réponse et une ligne de journal par requête."""
    strict_transport = settings.secure_cookies

    @app.middleware("http")
    async def secure(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        started = time.perf_counter()
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        response = await call_next(request)
        headers = response.headers
        headers["X-Request-ID"] = request_id
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "no-referrer")
        headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        # Réponses personnelles : aucun cache partagé ne doit les garder.
        headers.setdefault("Cache-Control", "no-store")
        if not request.url.path.startswith(_DOCS):
            headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        if strict_transport:
            headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        # Le modèle de route, jamais l'adresse réelle : les jetons d'invitation et de mot de
        # passe passent dans le chemin et ne doivent pas finir dans les journaux.
        route = request.scope.get("route")
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "route": getattr(route, "path", "unmatched"),
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )
        return response
