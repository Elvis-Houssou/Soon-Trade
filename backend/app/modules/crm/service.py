"""Historique relationnel : tout ce qui s'est passé avec un client, au même endroit."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.audit.models import record
from app.modules.claims.models import Claim
from app.modules.crm.models import OrganizationNote
from app.modules.identity.models import Organization, User
from app.modules.messaging.models import Conversation
from app.modules.orders.models import Order, SupplierOrder
from app.modules.organizations.service import get_client_organization
from app.modules.proposals.models import BuyerProposal
from app.modules.purchase_requests.models import PurchaseRequest
from app.modules.solicitations.models import SupplierOffer, SupplierSolicitation
from app.modules.sourcing.models import SourcingCase


@dataclass
class Entry:
    at: datetime
    kind: str  # request, proposal, order, claim, conversation, solicitation, offer, supplier_order, note
    reference: str
    status: str | None
    label: str
    # Page interne où l'objet se consulte.
    link: str | None
    author: str | None = None


def clients(session: Session) -> list[Organization]:
    return list(
        session.scalars(
            select(Organization)
            .where(Organization.kind.in_(("buyer", "supplier")))
            .order_by(Organization.name)
        )
    )


def timeline(session: Session, organization: Organization) -> list[Entry]:
    """shortcut: assemblé à la lecture, sans pagination ; une table d'événements dédiée
    deviendra utile quand un client cumulera des centaines d'objets."""
    org_id = organization.id
    entries: list[Entry] = []
    if organization.kind == "buyer":
        for r in session.scalars(
            select(PurchaseRequest).where(
                PurchaseRequest.organization_id == org_id, PurchaseRequest.status != "draft"
            )
        ):
            entries.append(
                Entry(r.created_at, "request", r.reference, r.status, r.product_name, "internal/demandes")
            )
        for p in session.scalars(
            select(BuyerProposal)
            .join(SourcingCase, SourcingCase.id == BuyerProposal.case_id)
            .join(PurchaseRequest, PurchaseRequest.id == SourcingCase.request_id)
            .where(PurchaseRequest.organization_id == org_id)
        ):
            entries.append(
                Entry(
                    p.created_at,
                    "proposal",
                    p.reference,
                    p.state,
                    p.request_reference,
                    f"internal/propositions?id={p.id}",
                )
            )
        for o in session.scalars(select(Order).where(Order.organization_id == org_id)):
            entries.append(
                Entry(
                    o.created_at,
                    "order",
                    o.reference,
                    o.status,
                    o.proposal_reference,
                    f"internal/commandes?id={o.id}",
                )
            )
        for c in session.scalars(select(Claim).where(Claim.organization_id == org_id)):
            entries.append(
                Entry(c.created_at, "claim", c.reference, c.status, c.subject, "internal/reclamations")
            )
    else:
        for s in session.scalars(
            select(SupplierSolicitation).where(
                SupplierSolicitation.organization_id == org_id, SupplierSolicitation.status != "draft"
            )
        ):
            entries.append(
                Entry(
                    s.created_at,
                    "solicitation",
                    s.reference,
                    s.state,
                    s.product_name,
                    "internal/sollicitations",
                )
            )
        for offer in session.scalars(
            select(SupplierOffer)
            .join(SupplierSolicitation, SupplierSolicitation.id == SupplierOffer.solicitation_id)
            .where(SupplierSolicitation.organization_id == org_id)
        ):
            entries.append(
                Entry(
                    offer.created_at,
                    "offer",
                    offer.reference,
                    offer.state,
                    offer.solicitation.product_name,
                    "internal/offres",
                )
            )
        for part in session.scalars(select(SupplierOrder).where(SupplierOrder.organization_id == org_id)):
            entries.append(
                Entry(
                    part.created_at,
                    "supplier_order",
                    part.reference,
                    part.order.status,
                    part.order.reference,
                    f"internal/commandes?id={part.order_id}",
                )
            )
    for conv in session.scalars(select(Conversation).where(Conversation.organization_id == org_id)):
        entries.append(
            Entry(
                conv.last_message_at,
                "conversation",
                conv.reference,
                conv.status,
                conv.subject,
                f"internal/messages?id={conv.id}",
            )
        )
    for note in session.scalars(select(OrganizationNote).where(OrganizationNote.organization_id == org_id)):
        entries.append(Entry(note.created_at, "note", "", None, note.body, None, note.author_name))
    return sorted(entries, key=lambda e: e.at, reverse=True)


def add_note(session: Session, organization: Organization, body: str, *, actor: User, ip: str | None) -> None:
    text = body.strip()
    if not text:
        raise AppError("Ce champ est obligatoire.")
    session.add(OrganizationNote(organization_id=organization.id, author_id=actor.id, body=text))
    # Le contenu de la note ne part pas dans le journal d'audit.
    record(session, "crm.note_added", str(organization.id), actor_id=actor.id, ip=ip)


def summary(session: Session, organization: Organization) -> dict[str, object]:
    entries = timeline(session, organization)

    def count(*kinds: str) -> int:
        return sum(1 for e in entries if e.kind in kinds)

    return {
        "last_activity": entries[0].at if entries else None,
        "requests": count("request", "solicitation"),
        "orders": count("order", "supplier_order"),
        "open_claims": sum(1 for e in entries if e.kind == "claim" and e.status in ("open", "under_review")),
        "conversations": count("conversation"),
    }


def get_client(session: Session, organization_id: uuid.UUID) -> Organization:
    return get_client_organization(session, organization_id)
