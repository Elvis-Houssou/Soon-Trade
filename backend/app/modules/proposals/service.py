"""Propositions acheteurs : préparation, validation interne, envoi, décision de l'acheteur."""

import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, Conflict, Forbidden, NotFound
from app.modules.audit.models import record
from app.modules.identity.models import Organization, User
from app.modules.identity.permissions import PROPOSAL_MANAGE
from app.modules.notifications import service as notifications
from app.modules.orders import service as orders
from app.modules.proposals.models import (
    BuyerProposal,
    BuyerProposalEvent,
    BuyerProposalLine,
    BuyerProposalVersion,
)
from app.modules.purchase_requests import service as requests
from app.modules.purchase_requests.models import PurchaseRequest
from app.modules.solicitations.models import SupplierOffer, SupplierSolicitation, today
from app.modules.sourcing import service as sourcing
from app.modules.sourcing.models import SourcingCase

logger = logging.getLogger(__name__)

# À VALIDER : validité proposée par défaut, bornée par celle des offres reprises.
DEFAULT_VALIDITY_DAYS = 7
MAX_LINES = 20

# action -> (états de départ permis, état d'arrivée). « expired » est un état déduit.
INTERNAL_ACTIONS: dict[str, tuple[frozenset[str], str]] = {
    "submit": (frozenset({"draft"}), "pending_validation"),
    "return": (frozenset({"pending_validation"}), "draft"),
    "send": (frozenset({"pending_validation"}), "sent"),
    "revise": (frozenset({"changes_requested", "expired"}), "draft"),
    # À VALIDER : une proposition déjà envoyée ne s'annule pas, l'acheteur doit pouvoir décider.
    "cancel": (frozenset({"draft", "pending_validation", "changes_requested"}), "cancelled"),
}
BUYER_ACTIONS: dict[str, tuple[frozenset[str], str]] = {
    "accept": (frozenset({"sent"}), "accepted"),
    "refuse": (frozenset({"sent"}), "refused"),
    "request_changes": (frozenset({"sent"}), "changes_requested"),
}
# Effet sur la demande d'achat (README §4 : l'acheteur suit tout depuis sa demande).
REQUEST_EFFECT = {
    "send": "proposal_sent",
    "revise_expired": "proposal_reopened",
    "accept": "proposal_accepted",
    "refuse": "proposal_refused",
    "request_changes": "proposal_reopened",
}


def _clean(value: str | None) -> str | None:
    return value.strip() or None if value else None


def _event(
    session: Session,
    proposal: BuyerProposal,
    target: str,
    *,
    actor: User,
    ip: str | None,
    action: str,
    message: str | None = None,
) -> None:
    previous = None if action == "created" else proposal.state
    session.add(
        BuyerProposalEvent(
            proposal_id=proposal.id,
            actor_id=actor.id,
            from_status=previous,
            to_status=target,
            version=proposal.current.version,
            message=_clean(message),
        )
    )
    record(
        session,
        f"proposal.{action}",
        proposal.reference,
        actor_id=actor.id,
        ip=ip,
        previous=previous,
        status=target,
        version=proposal.current.version,
    )
    proposal.status = target


def _move_request(
    session: Session, proposal: BuyerProposal, effect: str, *, actor: User, ip: str | None
) -> None:
    request = requests.get(session, proposal.request.id, lock=True)
    requests.transition(session, request, effect, actor=actor, ip=ip)


# --- Côté interne --------------------------------------------------------------


def list_all(session: Session) -> list[BuyerProposal]:
    # shortcut: pas de pagination ; à ajouter quand le volume le demandera.
    return list(session.scalars(select(BuyerProposal).order_by(BuyerProposal.number.desc())))


def get(session: Session, proposal_id: uuid.UUID, *, lock: bool = False) -> BuyerProposal:
    query = select(BuyerProposal).where(BuyerProposal.id == proposal_id)
    proposal = session.scalar(query.with_for_update() if lock else query)
    if not proposal:
        raise NotFound("Proposition introuvable.")
    return proposal


def _retained_offers(session: Session, case: SourcingCase) -> dict[uuid.UUID, SupplierOffer]:
    offers = session.scalars(
        select(SupplierOffer)
        .join(SupplierSolicitation, SupplierSolicitation.id == SupplierOffer.solicitation_id)
        .where(SupplierSolicitation.case_id == case.id)
        .order_by(SupplierOffer.number)
    )
    return {offer.id: offer for offer in offers if offer.state == "retained"}


def create(session: Session, case_id: uuid.UUID, *, actor: User, ip: str | None) -> BuyerProposal:
    """Brouillon prérempli avec les offres retenues, au prix fournisseur : la marge reste à fixer."""
    case = sourcing.active_case(session, case_id)
    open_one = session.scalar(
        select(BuyerProposal.id).where(BuyerProposal.case_id == case.id, BuyerProposal.status != "cancelled")
    )
    if open_one:
        raise Conflict("Ce dossier a déjà une proposition en cours.")
    offers = list(_retained_offers(session, case).values())
    if not offers:
        raise AppError("Retenez d'abord au moins une offre dans ce dossier.")
    request = case.request
    version = BuyerProposalVersion(
        version=1,
        created_by_id=actor.id,
        lead_time_days=max(o.current.lead_time_days for o in offers),
        valid_until=min(
            today() + timedelta(days=DEFAULT_VALIDITY_DAYS), *(o.current.valid_until for o in offers)
        ),
        delivery_location=request.delivery_location,
        lines=[
            BuyerProposalLine(
                position=index,
                product_name=offer.solicitation.product_name,
                quantity=offer.current.quantity,
                unit=offer.solicitation.unit,
                unit_price=offer.current.unit_price,
                offer_id=offer.id,
                supplier_unit_price=offer.current.unit_price,
            )
            for index, offer in enumerate(offers)
        ],
    )
    proposal = BuyerProposal(case_id=case.id, created_by_id=actor.id, versions=[version])
    session.add(proposal)
    session.flush()
    _event(session, proposal, "draft", actor=actor, ip=ip, action="created")
    session.flush()
    session.refresh(proposal, ["events"])
    return proposal


def update(
    session: Session, proposal: BuyerProposal, fields: dict[str, Any], *, actor: User, ip: str | None
) -> None:
    """Remplace le contenu de la version en préparation (jamais une version déjà envoyée)."""
    if proposal.status != "draft":
        raise Conflict("Seule une proposition en préparation se modifie.")
    sourcing.active_case(session, proposal.case_id)
    offers = _retained_offers(session, proposal.case)
    version = proposal.current
    lines = fields.pop("lines")
    if not lines:
        raise AppError("Une proposition compte au moins une ligne.")
    new_lines = []
    for index, line in enumerate(lines):
        offer_id = line.pop("offer_id", None)
        offer = None
        if offer_id is not None:
            offer = offers.get(offer_id)
            if offer is None:
                raise AppError("Une ligne s'appuie sur une offre qui n'est pas retenue dans ce dossier.")
        product_name = _clean(line.pop("product_name"))
        if not product_name:
            raise AppError("Ce champ est obligatoire.")
        new_lines.append(
            BuyerProposalLine(
                position=index,
                product_name=product_name,
                offer_id=offer.id if offer else None,
                supplier_unit_price=offer.current.unit_price if offer else None,
                **line,
            )
        )
    version.lines = new_lines
    delivery_location = _clean(fields.pop("delivery_location"))
    if not delivery_location:
        raise AppError("Ce champ est obligatoire.")
    version.delivery_location = delivery_location
    version.conditions = _clean(fields.pop("conditions", None))
    version.message = _clean(fields.pop("message", None))
    for field, value in fields.items():
        setattr(version, field, value)
    session.flush()
    record(session, "proposal.updated", proposal.reference, actor_id=actor.id, ip=ip, version=version.version)


def _check_ready(session: Session, proposal: BuyerProposal) -> None:
    """Contrôles avant validation et avant envoi : rien ne part sur une base périmée."""
    sourcing.active_case(session, proposal.case_id)
    version = proposal.current
    if not version.lines:
        raise AppError("Une proposition compte au moins une ligne.")
    if version.valid_until < today():
        raise AppError("La date de validité de la proposition est déjà passée.")
    offers = _retained_offers(session, proposal.case)
    sources = [line.offer for line in version.lines if line.offer is not None]
    if any(offer.id not in offers for offer in sources):
        raise AppError("Une offre reprise n'est plus retenue ou a expiré.")
    # À VALIDER : SOON TRADE ne s'engage pas au-delà de ce que ses fournisseurs garantissent.
    limit: date | None = min((o.current.valid_until for o in sources), default=None)
    if limit is not None and version.valid_until > limit:
        raise AppError(f"La validité ne peut pas dépasser celle des offres reprises ({limit:%d/%m/%Y}).")


def act(
    session: Session,
    proposal: BuyerProposal,
    action: str,
    *,
    actor: User,
    ip: str | None,
    message: str | None = None,
) -> None:
    sources, target = INTERNAL_ACTIONS[action]
    previous = proposal.state
    if previous not in sources:
        raise Conflict("Cette action n'est pas possible dans l'état actuel de la proposition.")
    if action in ("submit", "send"):
        _check_ready(session, proposal)
    elif action in ("revise", "return"):
        sourcing.get_case(session, proposal.case_id)
    if action == "submit":
        proposal.submitted_by_id = actor.id
    if action == "send":
        # À VALIDER : principe des quatre yeux, celui qui prépare ne valide pas lui-même.
        if proposal.submitted_by_id == actor.id:
            raise Forbidden("Une autre personne que celle qui l'a soumise doit valider la proposition.")
        proposal.current.sent_at = datetime.now(UTC)
        _move_request(session, proposal, REQUEST_EFFECT["send"], actor=actor, ip=ip)
    if action == "revise":
        if previous == "expired":
            # La demande rouvre comme pour une demande de modification.
            _move_request(session, proposal, REQUEST_EFFECT["revise_expired"], actor=actor, ip=ip)
        _event(session, proposal, target, actor=actor, ip=ip, action=action, message=message)
        _new_version(session, proposal, actor=actor)
        return
    _event(session, proposal, target, actor=actor, ip=ip, action=action, message=message)
    session.flush()
    session.refresh(proposal, ["events"])


def _new_version(session: Session, proposal: BuyerProposal, *, actor: User) -> None:
    """Copie de la dernière version envoyée, prête à être retravaillée."""
    base = proposal.current
    proposal.versions.append(
        BuyerProposalVersion(
            version=base.version + 1,
            created_by_id=actor.id,
            currency=base.currency,
            lead_time_days=base.lead_time_days,
            valid_until=max(base.valid_until, today()),
            delivery_location=base.delivery_location,
            conditions=base.conditions,
            message=None,
            lines=[
                BuyerProposalLine(
                    position=line.position,
                    product_name=line.product_name,
                    quantity=line.quantity,
                    unit=line.unit,
                    unit_price=line.unit_price,
                    offer_id=line.offer_id,
                    supplier_unit_price=line.supplier_unit_price,
                )
                for line in base.lines
            ],
        )
    )
    session.flush()
    session.refresh(proposal, ["events"])


def notify_buyer(session: Session, proposal: BuyerProposal) -> None:
    """Après validation de la transaction. Ni prix ni contenu dans l'e-mail (README §17)."""
    notifications.notify(
        session,
        notifications.members(session, proposal.request.organization_id),
        "proposal_received",
        link=f"buyer/propositions?id={proposal.id}",
        params={"reference": proposal.reference},
        email={
            "reference": proposal.reference,
            "request": proposal.request_reference,
            "valid_until": proposal.current.valid_until,
        },
    )


# --- Côté acheteur ---------------------------------------------------------------


def _buyer_query(organization: Organization) -> Select[BuyerProposal]:
    """Cloisonnement : seulement les propositions de ses demandes, et seulement une fois envoyées."""
    return (
        select(BuyerProposal)
        .join(SourcingCase, SourcingCase.id == BuyerProposal.case_id)
        .join(PurchaseRequest, PurchaseRequest.id == SourcingCase.request_id)
        .where(
            PurchaseRequest.organization_id == organization.id,
            BuyerProposal.versions.any(BuyerProposalVersion.sent_at.is_not(None)),
        )
    )


def list_for_buyer(session: Session, organization: Organization) -> list[BuyerProposal]:
    return list(session.scalars(_buyer_query(organization).order_by(BuyerProposal.number.desc())))


def get_for_buyer(
    session: Session, organization: Organization, proposal_id: uuid.UUID, *, lock: bool = False
) -> BuyerProposal:
    query = _buyer_query(organization).where(BuyerProposal.id == proposal_id)
    proposal = session.scalar(query.with_for_update(of=BuyerProposal) if lock else query)
    if not proposal:
        raise NotFound("Proposition introuvable.")
    return proposal


def decide(
    session: Session,
    proposal: BuyerProposal,
    action: str,
    *,
    actor: User,
    ip: str | None,
    message: str | None = None,
) -> None:
    sources, target = BUYER_ACTIONS[action]
    if proposal.state not in sources:
        raise Conflict("Cette proposition n'attend plus de décision.")
    if action == "request_changes" and not _clean(message):
        raise AppError("Précisez la modification souhaitée.")
    if action == "accept":
        proposal.accepted_version = proposal.current.version
    _move_request(session, proposal, REQUEST_EFFECT[action], actor=actor, ip=ip)
    _event(session, proposal, target, actor=actor, ip=ip, action=action, message=message)
    session.flush()
    if action == "accept":
        # README §4 : l'acceptation crée la commande, dans la même transaction.
        orders.create_from_proposal(session, proposal, actor=actor, ip=ip)
    session.refresh(proposal, ["events"])


def notify_decision(session: Session, proposal: BuyerProposal, action: str, actor: User) -> None:
    """Après validation : l'équipe commerciale apprend la décision de l'acheteur."""
    notifications.notify(
        session,
        notifications.staff_with(session, PROPOSAL_MANAGE),
        "proposal_decided",
        link=f"internal/propositions?id={proposal.id}",
        params={"reference": proposal.reference, "decision": action, "buyer": proposal.buyer_name},
        besides=actor.id,
    )
