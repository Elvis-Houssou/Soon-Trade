"""Indicateurs, rapports et exports, calculés sur les données réelles.

shortcut: tout est agrégé à la demande, sans tables de synthèse ; à revoir quand les
volumes rendront les écrans lents (vues matérialisées ou tâche de nuit).
"""

import csv
import io
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.claims.models import Claim
from app.modules.identity.models import Organization
from app.modules.orders.models import Delivery, Order, SupplierOrder
from app.modules.proposals.models import BuyerProposal
from app.modules.purchase_requests.models import PurchaseRequest
from app.modules.solicitations.models import SupplierOffer, SupplierSolicitation
from app.modules.sourcing.models import SourcingCase

ACTIVE_ORDER = ("confirmed", "in_preparation", "shipped", "delivered", "in_dispute")
ZERO = Decimal("0.00")


def _months(count: int, today: date | None = None) -> list[str]:
    """Les `count` derniers mois, du plus ancien au plus récent, au format AAAA-MM."""
    today = today or datetime.now(UTC).date()
    year, month = today.year, today.month
    keys = []
    for _ in range(count):
        keys.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(keys))


def _month(value: datetime) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def _assignee(case: SourcingCase | None) -> str | None:
    return case.assignee.full_name if case and case.assignee else None


def _in_range(value: datetime, start: date | None, end: date | None) -> bool:
    day = value.date()
    return (start is None or day >= start) and (end is None or day <= end)


# --- Tableaux de bord ---------------------------------------------------------------------------


def internal_dashboard(session: Session) -> dict[str, Any]:
    requests = list(session.scalars(select(PurchaseRequest).where(PurchaseRequest.status != "draft")))
    proposals = list(session.scalars(select(BuyerProposal)))
    orders = list(session.scalars(select(Order)))
    deliveries = list(session.scalars(select(Delivery)))
    offers = list(session.scalars(select(SupplierOffer)))
    open_claims = (
        session.scalar(select(func.count(Claim.id)).where(Claim.status.in_(("open", "under_review")))) or 0
    )
    live = [o for o in orders if o.status != "cancelled"]
    cost = sum((p.supplier_total for o in live for p in o.supplier_orders), ZERO)
    revenue = sum((o.buyer_total for o in live), ZERO)
    months = _months(6)
    per_month = Counter(_month(r.created_at) for r in requests)
    recent = sorted(
        [
            *(("request", r.created_at, r.reference, r.status, r.buyer_name) for r in requests),
            *(("order", o.created_at, o.reference, o.status, o.buyer_name) for o in orders),
            *(("offer", f.created_at, f.reference, f.state, f.solicitation.supplier_name) for f in offers),
        ],
        key=lambda row: row[1],
        reverse=True,
    )[:6]
    cases = {c.request_id: c for c in session.scalars(select(SourcingCase))}
    in_progress = [
        r
        for r in sorted(requests, key=lambda r: r.created_at, reverse=True)
        if r.status in ("submitted", "info_requested", "qualified", "in_sourcing", "proposal_sent")
    ][:6]
    return {
        "counts": {
            "to_qualify": sum(1 for r in requests if r.status in ("submitted", "info_requested")),
            "in_sourcing": sum(1 for r in requests if r.status == "in_sourcing"),
            "proposals_open": sum(
                1
                for p in proposals
                if p.state in ("draft", "pending_validation", "sent", "changes_requested")
            ),
            "orders_active": sum(1 for o in orders if o.status in ACTIVE_ORDER),
            "deliveries_in_transit": sum(1 for d in deliveries if d.status in ("in_transit", "incident")),
            "open_claims": open_claims,
        },
        "money": {"currency": "XOF", "revenue": revenue, "margin": revenue - cost},
        "workflow": {
            "requests": len(requests),
            "sourcing": sum(
                1
                for r in requests
                if r.status not in ("submitted", "info_requested", "qualified", "rejected", "cancelled")
            ),
            "offers": len(offers),
            "proposals": sum(1 for p in proposals if p.sent_versions),
            "orders": len(live),
            "deliveries": len(deliveries),
            "closed": sum(1 for o in orders if o.status == "closed"),
        },
        "trend": [{"month": m, "value": per_month.get(m, 0)} for m in months],
        "in_progress": [
            {
                "id": r.id,
                "reference": r.reference,
                "buyer": r.buyer_name,
                "product": r.product_name,
                "quantity": r.quantity,
                "unit": r.unit,
                "status": r.status,
                "assignee": _assignee(cases.get(r.id)),
                "created_at": r.created_at,
            }
            for r in in_progress
        ],
        "recent": [
            {"kind": kind, "at": at, "reference": reference, "status": status, "party": party}
            for kind, at, reference, status, party in recent
        ],
    }


def buyer_dashboard(session: Session, organization: Organization) -> dict[str, Any]:
    requests = list(
        session.scalars(select(PurchaseRequest).where(PurchaseRequest.organization_id == organization.id))
    )
    orders = list(session.scalars(select(Order).where(Order.organization_id == organization.id)))
    proposals = list(
        session.scalars(
            select(BuyerProposal)
            .join(SourcingCase, SourcingCase.id == BuyerProposal.case_id)
            .join(PurchaseRequest, PurchaseRequest.id == SourcingCase.request_id)
            .where(PurchaseRequest.organization_id == organization.id)
        )
    )
    claims = list(session.scalars(select(Claim).where(Claim.organization_id == organization.id)))
    deliveries = [d for o in orders for d in o.deliveries]
    live = [o for o in orders if o.status != "cancelled"]
    months = _months(6)
    spend: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for o in live:
        spend[_month(o.created_at)] += o.buyer_total
    return {
        "counts": {
            "requests_active": sum(
                1 for r in requests if r.status not in ("accepted", "closed", "rejected", "cancelled")
            ),
            "proposals_waiting": sum(1 for p in proposals if p.state == "sent"),
            "orders_active": sum(1 for o in orders if o.status in ACTIVE_ORDER),
            "deliveries_in_transit": sum(1 for d in deliveries if d.status == "in_transit"),
            "deliveries_to_confirm": sum(1 for d in deliveries if d.status == "delivered"),
            "open_claims": sum(1 for c in claims if c.status in ("open", "under_review")),
        },
        "money": {"currency": "XOF", "spend": sum((o.buyer_total for o in live), ZERO)},
        "trend": [{"month": m, "value": spend.get(m, ZERO)} for m in months],
        "recent_requests": [
            {
                "id": r.id,
                "reference": r.reference,
                "product": r.product_name,
                "quantity": r.quantity,
                "unit": r.unit,
                "status": r.status,
                "created_at": r.created_at,
            }
            for r in sorted(requests, key=lambda r: r.created_at, reverse=True)[:5]
        ],
    }


def supplier_dashboard(session: Session, organization: Organization) -> dict[str, Any]:
    solicitations = list(
        session.scalars(
            select(SupplierSolicitation).where(
                SupplierSolicitation.organization_id == organization.id,
                SupplierSolicitation.status != "draft",
            )
        )
    )
    offers = [s.offer for s in solicitations if s.offer]
    parts = list(
        session.scalars(
            select(SupplierOrder).where(
                SupplierOrder.organization_id == organization.id, SupplierOrder.released_at.is_not(None)
            )
        )
    )
    live = [p for p in parts if p.order.status != "cancelled"]
    deliveries = [d for p in parts for d in p.deliveries]
    months = _months(6)
    sales: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for p in live:
        sales[_month(p.released_at or p.created_at)] += p.supplier_total
    return {
        "counts": {
            "solicitations_open": sum(1 for s in solicitations if s.state in ("sent", "viewed")),
            "offers_pending": sum(1 for o in offers if o.state in ("submitted", "under_review")),
            "offers_retained": sum(1 for o in offers if o.state == "retained"),
            "orders_active": sum(1 for p in parts if p.supplier_state in ACTIVE_ORDER),
            "deliveries_to_ship": sum(1 for d in deliveries if d.status in ("planned", "in_preparation")),
        },
        "money": {"currency": "XOF", "sales": sum((p.supplier_total for p in live), ZERO)},
        "trend": [{"month": m, "value": sales.get(m, ZERO)} for m in months],
        "open_solicitations": [
            {
                "id": s.id,
                "reference": s.reference,
                "product": s.product_name,
                "quantity": s.quantity,
                "unit": s.unit,
                "deadline": s.response_deadline,
                "status": s.state,
            }
            for s in sorted(solicitations, key=lambda s: s.response_deadline)
            if s.state in ("sent", "viewed")
        ][:5],
    }


# --- Rapports internes ------------------------------------------------------------------------------


def commercial_report(session: Session, start: date | None, end: date | None) -> dict[str, Any]:
    """Entonnoir, chiffre d'affaires et marge sur la période, meilleurs clients et fournisseurs."""
    requests = [
        r
        for r in session.scalars(select(PurchaseRequest).where(PurchaseRequest.status != "draft"))
        if _in_range(r.created_at, start, end)
    ]
    proposals = [p for p in session.scalars(select(BuyerProposal)) if _in_range(p.created_at, start, end)]
    orders = [
        o
        for o in session.scalars(select(Order).where(Order.status != "cancelled"))
        if _in_range(o.created_at, start, end)
    ]
    sent = sum(1 for p in proposals if p.sent_versions)
    accepted = sum(1 for p in proposals if p.status == "accepted")
    revenue = sum((o.buyer_total for o in orders), ZERO)
    cost = sum((p.supplier_total for o in orders for p in o.supplier_orders), ZERO)
    buyers: dict[str, Decimal] = defaultdict(lambda: ZERO)
    suppliers: dict[str, Decimal] = defaultdict(lambda: ZERO)
    monthly: dict[str, dict[str, Decimal]] = defaultdict(lambda: {"revenue": ZERO, "margin": ZERO})
    for o in orders:
        buyers[o.buyer_name] += o.buyer_total
        order_cost = sum((p.supplier_total for p in o.supplier_orders), ZERO)
        monthly[_month(o.created_at)]["revenue"] += o.buyer_total
        monthly[_month(o.created_at)]["margin"] += o.buyer_total - order_cost
        for p in o.supplier_orders:
            suppliers[p.supplier_name] += p.supplier_total

    def top(values: dict[str, Decimal]) -> list[dict[str, Any]]:
        return [
            {"name": k, "amount": v}
            for k, v in sorted(values.items(), key=lambda kv: kv[1], reverse=True)[:5]
        ]

    def rate(part: int, whole: int) -> float | None:
        return round(part / whole, 4) if whole else None

    return {
        "currency": "XOF",
        "funnel": {
            "requests": len(requests),
            "proposals_sent": sent,
            "accepted": accepted,
            "orders": len(orders),
        },
        "rates": {"proposal_rate": rate(sent, len(requests)), "acceptance_rate": rate(accepted, sent)},
        "revenue": revenue,
        "cost": cost,
        "margin": revenue - cost,
        "margin_rate": float(round((revenue - cost) / revenue, 4)) if revenue else None,
        "average_order": (revenue / len(orders)).quantize(Decimal("0.01")) if orders else None,
        "top_buyers": top(buyers),
        "top_suppliers": top(suppliers),
        "monthly": [{"month": m, **v} for m, v in sorted(monthly.items())],
        "open_claims": sum(1 for c in session.scalars(select(Claim)) if c.status in ("open", "under_review")),
    }


# --- Exports CSV -------------------------------------------------------------------------------------

EXPORTS = ("requests", "orders", "deliveries", "claims")


def _rows(session: Session, kind: str) -> tuple[list[str], Iterable[list[Any]]]:
    if kind == "requests":
        return (
            ["reference", "date", "acheteur", "produit", "quantite", "unite", "lieu", "statut"],
            (
                [
                    r.reference,
                    r.created_at.date(),
                    r.buyer_name,
                    r.product_name,
                    r.quantity,
                    r.unit,
                    r.delivery_location,
                    r.status,
                ]
                for r in session.scalars(
                    select(PurchaseRequest)
                    .where(PurchaseRequest.status != "draft")
                    .order_by(PurchaseRequest.number)
                )
            ),
        )
    if kind == "orders":

        def order_row(o: Order) -> list[Any]:
            cost = sum((p.supplier_total for p in o.supplier_orders), ZERO)
            return [
                o.reference,
                o.created_at.date(),
                o.buyer_name,
                o.proposal_reference,
                o.status,
                o.currency,
                o.buyer_total,
                cost,
                o.buyer_total - cost,
            ]

        return (
            [
                "reference",
                "date",
                "acheteur",
                "proposition",
                "statut",
                "devise",
                "montant_acheteur",
                "cout_achat",
                "marge",
            ],
            (order_row(o) for o in session.scalars(select(Order).order_by(Order.number))),
        )
    if kind == "deliveries":
        return (
            [
                "reference",
                "commande",
                "fournisseur",
                "date_prevue",
                "transporteur",
                "suivi",
                "statut",
                "partie_le",
                "arrivee_le",
            ],
            (
                [
                    d.reference,
                    d.order_reference,
                    d.supplier_name or "",
                    d.planned_date,
                    d.carrier or "",
                    d.tracking_number or "",
                    d.status,
                    d.shipped_at.date() if d.shipped_at else "",
                    d.delivered_at.date() if d.delivered_at else "",
                ]
                for d in session.scalars(select(Delivery).order_by(Delivery.number))
            ),
        )
    return (
        ["reference", "date", "acheteur", "commande", "motif", "objet", "statut"],
        (
            [
                c.reference,
                c.created_at.date(),
                c.buyer_name,
                c.order_reference,
                c.category,
                c.subject,
                c.status,
            ]
            for c in session.scalars(select(Claim).order_by(Claim.number))
        ),
    )


def _safe(value: Any) -> str:
    """Neutralise l'injection de formule dans un tableur (=, +, -, @ en tête d'un texte saisi).
    Les montants restent des nombres, même négatifs."""
    text = str(value)
    if isinstance(value, (int, float, Decimal)):
        return text
    return f"'{text}" if text[:1] in ("=", "+", "-", "@") else text


def export_csv(session: Session, kind: str) -> str:
    """CSV séparé par des points-virgules (tableurs en français), précédé d'un BOM UTF-8."""
    header, rows = _rows(session, kind)
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(header)
    for row in rows:
        writer.writerow([_safe(v) for v in row])
    return "﻿" + buffer.getvalue()
