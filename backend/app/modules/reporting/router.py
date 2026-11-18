from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from app.modules.audit.models import record
from app.modules.identity.deps import CurrentPrincipal, DbSession, Principal, client_ip, require_permission
from app.modules.identity.permissions import REPORT_EXPORT, REPORT_READ
from app.modules.reporting import service

router = APIRouter(tags=["reporting"])


@router.get("/dashboard")
def dashboard(session: DbSession, principal: CurrentPrincipal) -> dict[str, Any]:
    """Vue d'ensemble de l'espace : toujours limitée à ce que la personne a le droit de voir."""
    kind = principal.organization.kind
    if kind == "buyer":
        return service.buyer_dashboard(session, principal.organization)
    if kind == "supplier":
        return service.supplier_dashboard(session, principal.organization)
    data = service.internal_dashboard(session)
    if REPORT_READ not in principal.permissions:
        # Chiffre d'affaires et marge : réservés aux rôles qui lisent les rapports.
        data.pop("money")
    return data


@router.get("/internal/reports/commercial")
def commercial_report(
    session: DbSession,
    _: Annotated[Principal, Depends(require_permission(REPORT_READ))],
    start: date | None = None,
    end: date | None = None,
) -> dict[str, Any]:
    return service.commercial_report(session, start, end)


@router.get("/internal/exports/{kind}")
def export(
    kind: Literal["requests", "orders", "deliveries", "claims"],
    request: Request,
    session: DbSession,
    principal: Annotated[Principal, Depends(require_permission(REPORT_EXPORT))],
) -> Response:
    """Export autorisé et tracé : chaque téléchargement laisse une ligne dans le journal d'audit."""
    content = service.export_csv(session, kind)
    record(session, "report.exported", kind, actor_id=principal.user.id, ip=client_ip(request))
    session.commit()
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="soontrade-{kind}-{date.today().isoformat()}.csv"'
        },
    )
