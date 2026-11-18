# SOON TRADE

Plateforme B2B de sourcing et d'intermédiation commerciale.

- Cahier des charges de référence : [README_SOON_TRADE.md](README_SOON_TRADE.md)
- Audit et cadrage : [docs/product/00-audit-et-cadrage.md](docs/product/00-audit-et-cadrage.md)
- Maquettes : [docs/design/](docs/design/)
- Authentification : [docs/security/authentification.md](docs/security/authentification.md)
- Bilan du projet (fait, manquant, à valider) : [docs/bilan.md](docs/bilan.md)
- Mise en production : [docs/operations/](docs/operations/), sécurité :
  [docs/security/audit-securite.md](docs/security/audit-securite.md), données personnelles :
  [docs/legal/donnees-personnelles.md](docs/legal/donnees-personnelles.md)

## Prérequis

Node 22, [pnpm](https://pnpm.io) 12, [uv](https://docs.astral.sh/uv/) et Docker Desktop.
Python 3.14 est installé automatiquement par uv.

## Démarrer en local

Docker Desktop doit être lancé.

```bash
cp backend/.env.example backend/.env     # puis choisir une valeur pour SEED_PASSWORD
cp frontend/.env.example frontend/.env
pnpm install
pnpm db:up             # PostgreSQL, Redis et stockage S3 local
pnpm db:migrate
pnpm db:seed           # comptes et données de démonstration
pnpm dev:api           # API sur http://localhost:8000 (documentation : /docs)
pnpm dev:web           # Site sur http://localhost:3000
```

Chaque application a son fichier de configuration : `backend/.env` pour l'API (base de
données, e-mails, stockage, secrets) et `frontend/.env` pour le site (adresse de l'API
seulement, car tout ce qu'il contient est visible dans le navigateur).

Si `uv` n'est pas dans le PATH, remplacer `uv` par `python -m uv` dans les commandes du
dossier `backend/`.

### Services locaux

| Service | Adresse | Identifiants |
|---|---|---|
| PostgreSQL 18 | `127.0.0.1:5432`, base `soontrade` | `soontrade` / `soontrade` |
| Redis | `127.0.0.1:6380` | aucun |
| Stockage S3 (émulateur) | `http://127.0.0.1:9090` | aucun |

Ces identifiants ne valent que pour le développement local. Les tests utilisent une base
séparée, `soontrade_test`, créée automatiquement.

**pgAdmin** : enregistrer un serveur avec l'hôte `127.0.0.1`, le port `5432`, la base
`soontrade` et l'utilisateur `soontrade`, ou importer `infra/pgadmin-servers.json`
(Outils → Importer/Exporter des serveurs). Les tables sont sous
Bases de données → soontrade → Schémas → public → Tables.

### Comptes de démonstration

`pnpm db:seed` crée ces comptes, tous avec le mot de passe `SEED_PASSWORD` du fichier `backend/.env` :

| Adresse | Espace | Rôle |
|---|---|---|
| `admin@demo.soontrade.com` | Interne | Administrateur |
| `sourcing@demo.soontrade.com` | Interne | Sourcing |
| `commercial@demo.soontrade.com` | Interne | Commercial |
| `logistique@demo.soontrade.com` | Interne | Logistique |
| `support@demo.soontrade.com` | Interne | Support |
| `acheteur@demo.soontrade.com` | Acheteur | Propriétaire |
| `acheteur.membre@demo.soontrade.com` | Acheteur | Membre |
| `fournisseur@demo.soontrade.com` | Fournisseur (vérifié, avec catalogue) | Propriétaire |
| `fournisseur2@demo.soontrade.com` | Fournisseur (en attente) | Propriétaire |

## Vérifier

```bash
pnpm check:web    # lint, typage et build du frontend
pnpm check:api    # ruff, mypy et tests du backend
```

```bash
pnpm verify:api   # parcours complet contre l'API, la base et le stockage réellement lancés
pnpm load:api     # test de charge : 20 utilisateurs simultanés pendant 30 s
```

```bash
pnpm db:backup                          # sauvegarde de la base locale dans backups/
pnpm db:restore backups/FICHIER.dump    # restauration dans une base séparée, puis contrôle
```

## Organisation

| Dossier | Contenu |
|---|---|
| `frontend/` | Next.js 16, React 19, Tailwind CSS 4. Espaces `buyer`, `supplier`, `internal`. |
| `backend/` | FastAPI, SQLAlchemy, Alembic. Un dossier par domaine dans `app/modules/`. |
| `infra/` | Docker Compose pour le développement. |
| `docs/` | Produit, architecture, règles métier, sécurité, design. |

## Avancement

| Phase | État |
|---|---|
| 0 — Cadrage | Proposé, en attente de validation |
| 1 — Initialisation | Fait, sauf dépôt GitHub distant |
| 2 — Design system | Fait (logo en PNG, vectoriel à fournir) ; fr, en, de |
| 3 — Identité et permissions | Fait |
| 4 — Acheteurs et fournisseurs | Fait : profils, membres, vérification, documents, catégories, catalogue |
| 5 — Demandes et sourcing | Fait : demande d'achat, qualification, dossier de sourcing, assignation, recherche et présélection de fournisseurs, notes internes. Règles à valider : `docs/business-rules/statuts-et-transitions.md` |
| 6 — Sollicitations et offres | Fait : sollicitation relue puis envoyée (e-mail sans contenu confidentiel), réponse structurée avec pièces jointes, versions, retrait, refus, échéances, comparaison interne et arbitrage. Règles à valider : même fichier |
| 7 — Propositions acheteurs | Fait : proposition préparée depuis les offres retenues (prix de vente, marge interne, lignes libres), validation par une seconde personne, envoi (e-mail sans contenu), acceptation, refus ou demande de modification, versions, version acceptée figée. Règles à valider : même fichier |
| 8 — Commandes et logistique | Fait : commande créée à l'acceptation (conditions figées), bons fournisseurs à leur prix, confirmation, livraisons suivies par la logistique et le fournisseur, preuves, incidents, confirmation de réception, réclamations avec litige, clôture. Règles à valider : même fichier |
| 9 — Paiements et finance | Bloquée : validation juridique de la conservation des fonds et contrat Jèko attendus |
| 10 — Messagerie, notifications et CRM | Fait : conversations client ↔ SOON TRADE (aucun canal acheteur ↔ fournisseur), notes internes, notifications dans l'application, e-mails en fr, en, de (texte et HTML), fiche CRM avec historique et notes. Règles à valider : `docs/business-rules/communication.md` |
| 11 — Reporting et administration | Fait : tableaux de bord sur les données réelles (3 espaces), rapport commercial (entonnoir, chiffre d'affaires, marge, meilleurs clients et fournisseurs), exports CSV autorisés et tracés, journal d'audit filtrable. Commissions et paiements attendent la Phase 9 |
| 12 — Préproduction et production | Préparée : en-têtes de sécurité, refus de démarrer avec une configuration dangereuse, test d'accès anonyme sur toutes les routes, audit des dépendances et recherche de secrets en CI, sauvegarde et restauration testées, test de charge réussi, plan de déploiement (`render.yaml`), procédures. **Reste à exécuter** : comptes, domaine, déploiement, alertes, validation juridique |
