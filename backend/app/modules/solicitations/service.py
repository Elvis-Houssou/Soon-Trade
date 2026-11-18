"""Sollicitations fournisseurs et offres : envoi, réponse, versions, arbitrage interne."""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError, Conflict, NotFound
from app.modules.audit.models import record
from app.modules.documents.models import Document
from app.modules.identity.models import Organization, User
from app.modules.identity.permissions import SOURCING_MANAGE
from app.modules.notifications import service as notifications
from app.modules.solicitations.models import SupplierOffer, SupplierOfferVersion, SupplierSolicitation, today
from app.modules.sourcing import service as sourcing

logger = logging.getLogger(__name__)

# Tout ce que les listes affichent, chargé en quelques requêtes au lieu d'une par ligne.
_LISTED = (
    selectinload(SupplierSolicitation.offer)
    .selectinload(SupplierOffer.versions)
    .selectinload(SupplierOfferVersion.attachments),
    selectinload(SupplierSolicitation.organization),
    selectinload(SupplierSolicitation.case),
    selectinload(SupplierSolicitation.created_by),
)

# À VALIDER : délai de réponse proposé par défaut, modifiable avant l'envoi.
DEFAULT_DEADLINE_DAYS = 7
EDITABLE_FIELDS = (
    "product_name",
    "quantity",
    "unit",
    "specifications",
    "packaging",
    "delivery_location",
    "desired_date",
)
REQUIRED = frozenset({"product_name", "quantity", "unit", "delivery_location", "response_deadline"})
# action interne -> (états de départ permis, état d'arrivée).
OFFER_DECISIONS: dict[str, tuple[frozenset[str], str]] = {
    "review": (frozenset({"submitted"}), "under_review"),
    "retain": (frozenset({"under_review"}), "retained"),
    "reject": (frozenset({"under_review"}), "not_retained"),
}
MAX_ATTACHMENTS = 10


def _audit(session: Session, action: str, subject: str, actor: User, ip: str | None, **details: Any) -> None:
    record(session, action, subject, actor_id=actor.id, ip=ip, **details)


def _clean(fields: dict[str, Any]) -> dict[str, Any]:
    return {k: (v.strip() or None) if isinstance(v, str) else v for k, v in fields.items()}


# --- Côté interne --------------------------------------------------------------


def list_all(session: Session) -> list[SupplierSolicitation]:
    # shortcut: pas de pagination ; à ajouter quand le volume le demandera.
    return list(
        session.scalars(
            select(SupplierSolicitation).options(*_LISTED).order_by(SupplierSolicitation.number.desc())
        )
    )


def list_for_case(session: Session, case_id: uuid.UUID) -> list[SupplierSolicitation]:
    sourcing.get_case(session, case_id)
    return list(
        session.scalars(
            select(SupplierSolicitation)
            .options(*_LISTED)
            .where(SupplierSolicitation.case_id == case_id)
            .order_by(SupplierSolicitation.number)
        )
    )


def get(session: Session, solicitation_id: uuid.UUID, *, lock: bool = False) -> SupplierSolicitation:
    query = select(SupplierSolicitation).where(SupplierSolicitation.id == solicitation_id)
    solicitation = session.scalar(query.with_for_update() if lock else query)
    if not solicitation:
        raise NotFound("Sollicitation introuvable.")
    return solicitation


def _check_supplier(supplier: Organization) -> None:
    if supplier.verification_status != "verified":
        raise AppError("Seul un fournisseur vérifié peut être sollicité.")


def create(
    session: Session, case_id: uuid.UUID, organization_id: uuid.UUID, *, actor: User, ip: str | None
) -> SupplierSolicitation:
    """Brouillon prérempli depuis la demande, à relire avant l'envoi.

    Les « informations utiles » de l'acheteur ne sont pas recopiées : elles peuvent le désigner.
    """
    case = sourcing.active_case(session, case_id)
    candidate = next((c for c in case.candidates if c.organization_id == organization_id), None)
    if not candidate:
        raise AppError("Présélectionnez d'abord ce fournisseur dans le dossier.")
    _check_supplier(candidate.organization)
    exists = session.scalar(
        select(SupplierSolicitation.id).where(
            SupplierSolicitation.case_id == case.id, SupplierSolicitation.organization_id == organization_id
        )
    )
    if exists:
        raise Conflict("Ce fournisseur a déjà une sollicitation pour ce dossier.")
    request = case.request
    solicitation = SupplierSolicitation(
        case_id=case.id,
        organization_id=organization_id,
        created_by_id=actor.id,
        response_deadline=today() + timedelta(days=DEFAULT_DEADLINE_DAYS),
        **{field: getattr(request, field) for field in EDITABLE_FIELDS},
    )
    session.add(solicitation)
    session.flush()
    _audit(session, "solicitation.created", solicitation.reference, actor, ip, case=case.reference)
    return solicitation


def update(
    session: Session,
    solicitation: SupplierSolicitation,
    changes: dict[str, Any],
    *,
    actor: User,
    ip: str | None,
) -> None:
    if solicitation.status != "draft":
        raise Conflict("Une sollicitation envoyée ne se modifie plus.")
    for field, value in _clean(changes).items():
        if value is None and field in REQUIRED:
            raise AppError("Ce champ est obligatoire.")
        setattr(solicitation, field, value)
    _audit(session, "solicitation.updated", solicitation.reference, actor, ip, fields=sorted(changes))


def send(session: Session, solicitation: SupplierSolicitation, *, actor: User, ip: str | None) -> None:
    if solicitation.status != "draft":
        raise Conflict("Cette sollicitation a déjà été envoyée.")
    if solicitation.case.request.status != "in_sourcing":
        raise Conflict("Ce dossier n'est plus actif.")
    _check_supplier(solicitation.organization)
    if solicitation.response_deadline < today():
        raise AppError("La date limite de réponse est déjà passée.")
    solicitation.status = "sent"
    solicitation.sent_at = datetime.now(UTC)
    _audit(session, "solicitation.sent", solicitation.reference, actor, ip, previous="draft", status="sent")


def notify_supplier(session: Session, solicitation: SupplierSolicitation) -> None:
    """Après validation de la transaction. Le message ne contient rien de confidentiel (README §17)."""
    reference = solicitation.reference
    notifications.notify(
        session,
        notifications.members(session, solicitation.organization_id),
        "solicitation_received",
        link=f"supplier/sollicitations?id={solicitation.id}",
        params={"reference": reference},
        email={"reference": reference, "deadline": solicitation.response_deadline},
    )


def cancel(session: Session, solicitation: SupplierSolicitation, *, actor: User, ip: str | None) -> None:
    previous = solicitation.state
    if solicitation.status not in ("draft", "sent", "viewed"):
        raise Conflict("Cette sollicitation ne peut plus être annulée.")
    solicitation.status = "cancelled"
    _audit(session, "solicitation.cancelled", solicitation.reference, actor, ip, previous=previous)


def get_offer(session: Session, offer_id: uuid.UUID) -> SupplierOffer:
    offer = session.scalar(select(SupplierOffer).where(SupplierOffer.id == offer_id).with_for_update())
    if not offer:
        raise NotFound("Offre introuvable.")
    return offer


def decide(session: Session, offer: SupplierOffer, action: str, *, actor: User, ip: str | None) -> None:
    sources, target = OFFER_DECISIONS[action]
    previous = offer.state
    if previous not in sources:
        raise Conflict("Cette action n'est pas possible dans l'état actuel de l'offre.")
    if offer.solicitation.case.request.status != "in_sourcing":
        raise Conflict("Ce dossier n'est plus actif.")
    offer.status = target
    _audit(session, f"offer.{action}", offer.reference, actor, ip, previous=previous, status=target)


# --- Côté fournisseur ----------------------------------------------------------


def list_for_supplier(session: Session, organization: Organization) -> list[SupplierSolicitation]:
    """Les brouillons restent internes tant qu'ils ne sont pas envoyés."""
    return list(
        session.scalars(
            select(SupplierSolicitation)
            .options(*_LISTED)
            .where(
                SupplierSolicitation.organization_id == organization.id,
                SupplierSolicitation.status != "draft",
            )
            .order_by(SupplierSolicitation.number.desc())
        )
    )


def get_for_supplier(
    session: Session, organization: Organization, solicitation_id: uuid.UUID, *, lock: bool = False
) -> SupplierSolicitation:
    """Filtre sur l'organisation = cloisonnement : la sollicitation d'un autre est « introuvable »."""
    query = select(SupplierSolicitation).where(
        SupplierSolicitation.id == solicitation_id,
        SupplierSolicitation.organization_id == organization.id,
        SupplierSolicitation.status != "draft",
    )
    solicitation = session.scalar(query.with_for_update() if lock else query)
    if not solicitation:
        raise NotFound("Sollicitation introuvable.")
    return solicitation


def mark_viewed(session: Session, solicitation: SupplierSolicitation, *, actor: User, ip: str | None) -> None:
    if solicitation.status == "sent":
        solicitation.status = "viewed"
        solicitation.viewed_at = datetime.now(UTC)
        _audit(
            session,
            "solicitation.viewed",
            solicitation.reference,
            actor,
            ip,
            previous="sent",
            status="viewed",
        )


def decline(
    session: Session, solicitation: SupplierSolicitation, reason: str | None, *, actor: User, ip: str | None
) -> None:
    previous = solicitation.state
    if previous not in ("sent", "viewed"):
        raise Conflict("Cette sollicitation ne peut plus être déclinée.")
    solicitation.status = "declined"
    solicitation.decline_reason = reason.strip() or None if reason else None
    _audit(session, "solicitation.declined", solicitation.reference, actor, ip, previous=previous)


def _version(
    session: Session, solicitation: SupplierSolicitation, fields: dict[str, Any], *, number: int, actor: User
) -> SupplierOfferVersion:
    if fields["valid_until"] < today():
        raise AppError("La date de validité de l'offre est déjà passée.")
    attachment_ids = set(fields.pop("attachment_ids", []))
    attachments = list(
        session.scalars(
            select(Document).where(
                Document.id.in_(attachment_ids), Document.organization_id == solicitation.organization_id
            )
        )
    )
    if len(attachments) != len(attachment_ids):
        # Le document d'une autre organisation est « introuvable », comme partout ailleurs.
        raise NotFound("Document introuvable.")
    return SupplierOfferVersion(
        version=number, created_by_id=actor.id, attachments=attachments, **_clean(fields)
    )


def submit_offer(
    session: Session,
    solicitation: SupplierSolicitation,
    fields: dict[str, Any],
    *,
    actor: User,
    ip: str | None,
) -> SupplierOffer:
    previous = solicitation.state
    if previous not in ("sent", "viewed") or solicitation.offer is not None:
        raise Conflict("Cette sollicitation n'accepte plus de réponse.")
    # Validée avant de créer l'offre : un refus ne doit rien laisser attaché à la sollicitation.
    version = _version(session, solicitation, fields, number=1, actor=actor)
    offer = SupplierOffer(solicitation=solicitation, versions=[version])
    solicitation.status = "answered"
    session.add(offer)
    session.flush()
    _audit(session, "offer.submitted", offer.reference, actor, ip, solicitation=solicitation.reference)
    return offer


def _own_offer(solicitation: SupplierSolicitation) -> SupplierOffer:
    if solicitation.offer is None:
        raise NotFound("Offre introuvable.")
    return solicitation.offer


def revise_offer(
    session: Session,
    solicitation: SupplierSolicitation,
    fields: dict[str, Any],
    *,
    actor: User,
    ip: str | None,
) -> SupplierOffer:
    offer = _own_offer(solicitation)
    if offer.state != "submitted":
        raise Conflict("Cette offre ne peut plus être modifiée.")
    number = len(offer.versions) + 1
    offer.versions.append(_version(session, solicitation, fields, number=number, actor=actor))
    session.flush()
    _audit(session, "offer.revised", offer.reference, actor, ip, version=number)
    return offer


def withdraw_offer(
    session: Session, solicitation: SupplierSolicitation, *, actor: User, ip: str | None
) -> SupplierOffer:
    offer = _own_offer(solicitation)
    if offer.state != "submitted":
        raise Conflict("Cette offre ne peut plus être retirée.")
    offer.status = "withdrawn"
    _audit(session, "offer.withdrawn", offer.reference, actor, ip, previous="submitted", status="withdrawn")
    return offer


def notify_offer(session: Session, solicitation: SupplierSolicitation) -> None:
    """Après validation : l'équipe sourcing apprend qu'une offre est arrivée."""
    offer = solicitation.offer
    if offer is None:
        return
    notifications.notify(
        session,
        notifications.staff_with(session, SOURCING_MANAGE),
        "offer_received",
        link="internal/offres",
        params={"reference": offer.reference, "supplier": solicitation.supplier_name},
    )
