import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

# À VALIDER : liste de départ des unités de vente.
UNITS = ("kg", "tonne", "litre", "sac", "carton", "unite")
AVAILABILITIES = ("available", "limited", "unavailable")


class Category(Base):
    """Catégorie de produits, gérée par SOON TRADE. Taxonomie à valider : aucune n'est préremplie."""

    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    name: Mapped[str] = mapped_column(String(120), unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)


class Product(Base):
    """Produit du catalogue d'un fournisseur. Jamais visible d'un acheteur ni d'un autre fournisseur."""

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("min_order_quantity >= 0 and available_quantity >= 0", name="product_quantities"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(2000))
    unit: Mapped[str] = mapped_column(String(20))
    packaging: Mapped[str | None] = mapped_column(String(200))
    # NUMERIC, jamais de flottant binaire pour des quantités commerciales.
    min_order_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=Decimal(0))
    available_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=Decimal(0))
    availability: Mapped[str] = mapped_column(String(20), default="available")
    # Suppression logique : un produit retiré reste référençable par d'anciennes offres.
    is_active: Mapped[bool] = mapped_column(default=True)

    category: Mapped[Category] = relationship()
