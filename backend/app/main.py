from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core import hardening
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.modules.catalog.router import router as catalog_router
from app.modules.claims.router import router as claims_router
from app.modules.contact.router import router as contact_router
from app.modules.crm.router import router as crm_router
from app.modules.documents.router import router as documents_router
from app.modules.health.router import router as health_router
from app.modules.identity.router import router as identity_router
from app.modules.messaging.router import router as messaging_router
from app.modules.notifications.router import router as notifications_router
from app.modules.orders.router import router as orders_router
from app.modules.organizations.router import router as organizations_router
from app.modules.proposals.router import router as proposals_router
from app.modules.purchase_requests.router import router as purchase_requests_router
from app.modules.reporting.router import router as reporting_router
from app.modules.solicitations.router import router as solicitations_router
from app.modules.sourcing.router import router as sourcing_router


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    problems = hardening.production_problems(settings)
    if problems:
        raise RuntimeError("Configuration refusée : " + " ".join(problems))

    app = FastAPI(
        title="SOON TRADE API",
        version="0.1.0",
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
        # Nom du fichier des exports CSV, lu par le navigateur.
        expose_headers=["Content-Disposition"],
    )
    register_error_handlers(app)
    hardening.install(app, settings)
    app.include_router(health_router)
    app.include_router(identity_router)
    app.include_router(organizations_router)
    app.include_router(catalog_router)
    app.include_router(documents_router)
    app.include_router(purchase_requests_router)
    app.include_router(sourcing_router)
    app.include_router(solicitations_router)
    app.include_router(proposals_router)
    app.include_router(orders_router)
    app.include_router(claims_router)
    app.include_router(messaging_router)
    app.include_router(notifications_router)
    app.include_router(crm_router)
    app.include_router(reporting_router)
    app.include_router(contact_router)
    return app


app = create_app()
