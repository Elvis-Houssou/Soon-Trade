import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError, Conflict, NotFound
from app.modules.audit.models import record
from app.modules.catalog.models import Category, Product
from app.modules.identity.deps import CurrentPrincipal, DbSession, Principal, client_ip, require_permission
from app.modules.identity.permissions import CATALOG_READ_ALL, CATEGORY_MANAGE, PRODUCT_MANAGE
from app.modules.organizations.service import get_client_organization

router = APIRouter(tags=["catalog"])

Unit = Literal["kg", "tonne", "litre", "sac", "carton", "unite"]
Availability = Literal["available", "limited", "unavailable"]
Quantity = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=3)]


# --- Catégories ----------------------------------------------------------------


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_active: bool


class CategoryIn(BaseModel):
    name: Annotated[str, Field(min_length=2, max_length=120)]


class CategoryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=2, max_length=120)] | None = None
    is_active: bool | None = None


ManagesCategories = Annotated[Principal, Depends(require_permission(CATEGORY_MANAGE))]


@router.get("/categories")
def list_categories(session: DbSession, _: CurrentPrincipal) -> list[CategoryOut]:
    """Lisible par tout utilisateur connecté : sert aux fournisseurs comme aux acheteurs."""
    return [CategoryOut.model_validate(c) for c in session.scalars(select(Category).order_by(Category.name))]


def _save_category(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise Conflict("Une catégorie porte déjà ce nom.") from error


@router.post("/categories", status_code=status.HTTP_201_CREATED)
def create_category(
    body: CategoryIn, request: Request, session: DbSession, principal: ManagesCategories
) -> CategoryOut:
    category = Category(name=body.name.strip())
    session.add(category)
    record(session, "category.created", category.name, actor_id=principal.user.id, ip=client_ip(request))
    _save_category(session)
    return CategoryOut.model_validate(category)


@router.patch("/categories/{category_id}")
def update_category(
    category_id: uuid.UUID,
    body: CategoryPatch,
    request: Request,
    session: DbSession,
    principal: ManagesCategories,
) -> CategoryOut:
    category = session.get(Category, category_id)
    if not category:
        raise NotFound("Catégorie introuvable.")
    if body.name is not None:
        category.name = body.name.strip()
    if body.is_active is not None:
        category.is_active = body.is_active
    record(session, "category.updated", category.name, actor_id=principal.user.id, ip=client_ip(request))
    _save_category(session)
    return CategoryOut.model_validate(category)


# --- Catalogue du fournisseur --------------------------------------------------


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    category_id: uuid.UUID
    description: str | None
    unit: str
    packaging: str | None
    min_order_quantity: Decimal
    available_quantity: Decimal
    availability: str
    updated_at: datetime


class ProductIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=2, max_length=200)]
    category_id: uuid.UUID
    description: Annotated[str, Field(max_length=2000)] | None = None
    unit: Unit
    packaging: Annotated[str, Field(max_length=200)] | None = None
    min_order_quantity: Quantity = Decimal(0)
    available_quantity: Quantity = Decimal(0)
    availability: Availability = "available"


class ProductPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=2, max_length=200)] | None = None
    category_id: uuid.UUID | None = None
    description: Annotated[str, Field(max_length=2000)] | None = None
    unit: Unit | None = None
    packaging: Annotated[str, Field(max_length=200)] | None = None
    min_order_quantity: Quantity | None = None
    available_quantity: Quantity | None = None
    availability: Availability | None = None


ManagesProducts = Annotated[Principal, Depends(require_permission(PRODUCT_MANAGE))]


def _active_products(session: Session, organization_id: uuid.UUID) -> list[ProductOut]:
    products = session.scalars(
        select(Product)
        .where(Product.organization_id == organization_id, Product.is_active)
        .order_by(Product.name)
    )
    return [ProductOut.model_validate(p) for p in products]


def _check_category(session: Session, category_id: uuid.UUID) -> None:
    category = session.get(Category, category_id)
    if not category or not category.is_active:
        raise AppError("Cette catégorie n'est pas disponible.")


def _own_product(session: Session, principal: Principal, product_id: uuid.UUID) -> Product:
    # Le filtre sur l'organisation fait le cloisonnement : le produit d'un autre est « introuvable ».
    product = session.scalar(
        select(Product).where(
            Product.id == product_id, Product.organization_id == principal.organization.id, Product.is_active
        )
    )
    if not product:
        raise NotFound("Produit introuvable.")
    return product


@router.get("/products")
def list_my_products(session: DbSession, principal: ManagesProducts) -> list[ProductOut]:
    return _active_products(session, principal.organization.id)


@router.post("/products", status_code=status.HTTP_201_CREATED)
def create_product(
    body: ProductIn, request: Request, session: DbSession, principal: ManagesProducts
) -> ProductOut:
    _check_category(session, body.category_id)
    # L'organisation vient de la session, jamais de la requête.
    product = Product(organization_id=principal.organization.id, **body.model_dump())
    session.add(product)
    record(session, "product.created", body.name, actor_id=principal.user.id, ip=client_ip(request))
    session.commit()
    return ProductOut.model_validate(product)


@router.patch("/products/{product_id}")
def update_product(
    product_id: uuid.UUID,
    body: ProductPatch,
    request: Request,
    session: DbSession,
    principal: ManagesProducts,
) -> ProductOut:
    product = _own_product(session, principal, product_id)
    changes: dict[str, Any] = body.model_dump(exclude_unset=True)
    if "category_id" in changes:
        _check_category(session, changes["category_id"])
    for field, value in changes.items():
        setattr(product, field, value)
    record(
        session,
        "product.updated",
        str(product.id),
        actor_id=principal.user.id,
        ip=client_ip(request),
        fields=sorted(changes),
    )
    session.commit()
    session.refresh(product)
    return ProductOut.model_validate(product)


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_product(
    product_id: uuid.UUID, request: Request, session: DbSession, principal: ManagesProducts
) -> None:
    product = _own_product(session, principal, product_id)
    product.is_active = False
    record(session, "product.archived", str(product.id), actor_id=principal.user.id, ip=client_ip(request))
    session.commit()


@router.get("/organizations/{organization_id}/products")
def list_supplier_products(
    organization_id: uuid.UUID,
    session: DbSession,
    _: Annotated[Principal, Depends(require_permission(CATALOG_READ_ALL))],
) -> list[ProductOut]:
    """Vue interne du catalogue d'un fournisseur, pour le sourcing."""
    return _active_products(session, get_client_organization(session, organization_id).id)
