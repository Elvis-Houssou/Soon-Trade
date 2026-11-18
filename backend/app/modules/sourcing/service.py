"""Dossiers de sourcing : ouverture, assignation, recherche et présélection, notes internes."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, Conflict, NotFound
from app.modules.audit.models import record
from app.modules.catalog.models import Category, Product
from app.modules.identity.models import Membership, Organization, User
from app.modules.identity.permissions import SOURCING_MANAGE, permissions_for
from app.modules.purchase_requests import service as requests
from app.modules.sourcing.models import SourcingCandidate, SourcingCase, SourcingNote


def list_cases(session: Session) -> list[SourcingCase]:
    return list(session.scalars(select(SourcingCase).order_by(SourcingCase.number.desc())))


def get_case(session: Session, case_id: uuid.UUID) -> SourcingCase:
    case = session.get(SourcingCase, case_id)
    if not case:
        raise NotFound("Dossier introuvable.")
    return case


def active_case(session: Session, case_id: uuid.UUID) -> SourcingCase:
    """À VALIDER : le dossier n'est modifiable que tant que la demande est « en sourcing »
    (il se fige si l'acheteur annule) ; les notes restent possibles."""
    case = get_case(session, case_id)
    if case.request.status != "in_sourcing":
        raise Conflict("Ce dossier n'est plus actif.")
    return case


def open_case(session: Session, request_id: uuid.UUID, *, actor: User, ip: str | None) -> SourcingCase:
    # Le verrou sur la demande et la transition « qualifiée -> en sourcing » garantissent
    # un seul dossier : le second appel trouve la demande déjà en sourcing et reçoit 409.
    request = requests.get(session, request_id, lock=True)
    requests.transition(session, request, "open_sourcing", actor=actor, ip=ip)
    # À VALIDER : le dossier est assigné par défaut à la personne qui l'ouvre.
    case = SourcingCase(request_id=request.id, assignee_id=actor.id)
    session.add(case)
    session.flush()
    record(session, "sourcing_case.opened", case.reference, actor_id=actor.id, ip=ip)
    return case


def assignable_users(session: Session) -> list[User]:
    """À VALIDER : un dossier s'assigne aux rôles qui peuvent le traiter (admin, agent de sourcing)."""
    members = session.scalars(
        select(Membership)
        .join(Organization, Organization.id == Membership.organization_id)
        .join(User, User.id == Membership.user_id)
        .where(Organization.kind == "internal", User.is_active)
        .order_by(User.full_name)
    )
    return [m.user for m in members if SOURCING_MANAGE in permissions_for(m.role)]


def assign(
    session: Session, case_id: uuid.UUID, assignee_id: uuid.UUID, *, actor: User, ip: str | None
) -> SourcingCase:
    case = active_case(session, case_id)
    assignee = next((u for u in assignable_users(session) if u.id == assignee_id), None)
    if not assignee:
        raise AppError("Ce collaborateur ne peut pas être assigné à un dossier.")
    case.assignee = assignee
    record(
        session, "sourcing_case.assigned", case.reference, actor_id=actor.id, ip=ip, assignee=assignee.email
    )
    return case


def search_products(
    session: Session, *, q: str | None, category_id: uuid.UUID | None
) -> list[tuple[Product, Organization, Category]]:
    """Produits actifs des fournisseurs vérifiés uniquement."""
    query = (
        select(Product, Organization, Category)
        .join(Organization, Organization.id == Product.organization_id)
        .join(Category, Category.id == Product.category_id)
        .where(
            Product.is_active, Organization.kind == "supplier", Organization.verification_status == "verified"
        )
        .order_by(Product.name, Organization.name)
        .limit(100)
    )
    if q and q.strip():
        query = query.where(Product.name.icontains(q.strip(), autoescape=True))
    if category_id:
        query = query.where(Product.category_id == category_id)
    return [(p, o, c) for p, o, c in session.execute(query)]


def add_candidate(
    session: Session, case_id: uuid.UUID, organization_id: uuid.UUID, *, actor: User, ip: str | None
) -> SourcingCase:
    case = active_case(session, case_id)
    supplier = session.get(Organization, organization_id)
    if not supplier or supplier.kind != "supplier":
        raise NotFound("Fournisseur introuvable.")
    if supplier.verification_status != "verified":
        raise AppError("Seul un fournisseur vérifié peut être présélectionné.")
    if any(c.organization_id == supplier.id for c in case.candidates):
        raise Conflict("Ce fournisseur est déjà présélectionné.")
    session.add(SourcingCandidate(case_id=case.id, organization_id=supplier.id, added_by_id=actor.id))
    record(
        session,
        "sourcing_case.candidate_added",
        case.reference,
        actor_id=actor.id,
        ip=ip,
        supplier=str(supplier.id),
    )
    session.flush()
    session.refresh(case, ["candidates"])
    return case


def remove_candidate(
    session: Session, case_id: uuid.UUID, organization_id: uuid.UUID, *, actor: User, ip: str | None
) -> SourcingCase:
    case = active_case(session, case_id)
    candidate = next((c for c in case.candidates if c.organization_id == organization_id), None)
    if not candidate:
        raise NotFound("Ce fournisseur n'est pas présélectionné.")
    session.delete(candidate)
    record(
        session,
        "sourcing_case.candidate_removed",
        case.reference,
        actor_id=actor.id,
        ip=ip,
        supplier=str(organization_id),
    )
    session.flush()
    session.refresh(case, ["candidates"])
    return case


def add_note(session: Session, case_id: uuid.UUID, body: str, *, actor: User, ip: str | None) -> SourcingCase:
    case = get_case(session, case_id)
    session.add(SourcingNote(case_id=case.id, author_id=actor.id, body=body.strip()))
    # Le contenu de la note ne part pas dans le journal d'audit.
    record(session, "sourcing_case.note_added", case.reference, actor_id=actor.id, ip=ip)
    session.flush()
    session.refresh(case, ["notes"])
    return case
