"""Jeu de données de démonstration pour le développement local.

    uv run python -m app.seed

Crée des comptes de test pour chaque espace, tous avec le mot de passe SEED_PASSWORD
du fichier `backend/.env`. Relancer la commande ne duplique rien. Refuse de tourner ailleurs
qu'en local : ces comptes n'ont rien à faire en préproduction ni en production.
"""

import sys
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_engine
from app.modules.catalog.models import Category, Product
from app.modules.identity.models import Membership, Organization, User
from app.modules.identity.security import hash_password

# (organisation, type, statut de vérification, [(e-mail, nom, rôle)])
ORGANIZATIONS = [
    (
        "SOON TRADE",
        "internal",
        "verified",
        [
            ("admin@demo.soontrade.com", "Awa Admin", "admin"),
            ("sourcing@demo.soontrade.com", "Koffi Sourcing", "sourcing_agent"),
            ("commercial@demo.soontrade.com", "Mariam Commercial", "sales_agent"),
            ("logistique@demo.soontrade.com", "Seydou Logistique", "logistics_agent"),
            ("support@demo.soontrade.com", "Adjoua Support", "support_agent"),
        ],
    ),
    (
        "Entreprise Traoré",
        "buyer",
        "verified",
        [
            ("acheteur@demo.soontrade.com", "Ibrahim Traoré", "buyer_owner"),
            ("acheteur.membre@demo.soontrade.com", "Fatou Traoré", "buyer_member"),
        ],
    ),
    (
        "Sodeci Agro",
        "supplier",
        "verified",
        [("fournisseur@demo.soontrade.com", "Yao Sodeci", "supplier_owner")],
    ),
    (
        "Coopérative Banana",
        "supplier",
        "pending",
        [("fournisseur2@demo.soontrade.com", "Aya Banana", "supplier_owner")],
    ),
]

# Taxonomie de démonstration uniquement : la vraie reste à valider.
CATEGORIES = ["Céréales", "Noix et oléagineux", "Huiles", "Légumineuses"]

# Produits de Sodeci Agro : (nom, catégorie, unité, conditionnement, stock, disponibilité)
PRODUCTS = [
    ("Riz blanc", "Céréales", "tonne", "Sacs de 50 kg", "80", "available"),
    ("Maïs grain", "Céréales", "tonne", "Sacs de 100 kg", "150", "available"),
    ("Noix de cajou", "Noix et oléagineux", "tonne", "Sacs de 80 kg", "30", "limited"),
    ("Haricot rouge", "Légumineuses", "tonne", "Sacs de 50 kg", "0", "unavailable"),
]


def seed(session: Session, password: str) -> None:
    password_hash = hash_password(password)
    organizations: dict[str, Organization] = {}
    for name, kind, status, members in ORGANIZATIONS:
        organization = session.scalar(
            select(Organization).where(Organization.name == name, Organization.kind == kind)
        )
        if not organization:
            organization = Organization(
                name=name, kind=kind, verification_status=status, country="CI", city="Abidjan"
            )
            session.add(organization)
            session.flush()
        organizations[name] = organization
        for email, full_name, role in members:
            user = session.scalar(select(User).where(User.email == email))
            if not user:
                user = User(email=email, full_name=full_name, password_hash=password_hash)
                session.add(user)
                session.flush()
                session.add(Membership(user_id=user.id, organization_id=organization.id, role=role))
            else:
                # Relancer le script réaligne le mot de passe sur SEED_PASSWORD.
                user.password_hash, user.is_active = password_hash, True

    categories: dict[str, Category] = {}
    for name in CATEGORIES:
        category = session.scalar(select(Category).where(Category.name == name))
        if not category:
            category = Category(name=name)
            session.add(category)
            session.flush()
        categories[name] = category

    supplier = organizations["Sodeci Agro"]
    for name, category_name, unit, packaging, stock, availability in PRODUCTS:
        exists = session.scalar(
            select(Product).where(Product.organization_id == supplier.id, Product.name == name)
        )
        if not exists:
            session.add(
                Product(
                    organization_id=supplier.id,
                    category_id=categories[category_name].id,
                    name=name,
                    unit=unit,
                    packaging=packaging,
                    available_quantity=Decimal(stock),
                    availability=availability,
                )
            )


if __name__ == "__main__":
    settings = get_settings()
    if settings.environment != "local":
        sys.exit("Refusé : le jeu de démonstration ne se charge qu'en environnement local.")
    if not settings.seed_password or len(settings.seed_password) < 10:
        sys.exit("Définissez SEED_PASSWORD (10 caractères minimum) dans le fichier backend/.env.")
    with Session(get_engine()) as db:
        seed(db, settings.seed_password)
        db.commit()
    print("Comptes de démonstration prêts (mot de passe : valeur de SEED_PASSWORD dans backend/.env) :")
    for _, _, _, members in ORGANIZATIONS:
        for email, _, role in members:
            print(f"  {email:38} {role}")
