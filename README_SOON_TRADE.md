# SOON TRADE --- README projet & cahier des charges de référence

> Document de référence destiné à Claude et à toute personne intervenant
> sur le projet. Il rassemble les décisions fonctionnelles, métier,
> techniques et graphiques validées pour concevoir et développer SOON
> TRADE étape par étape.
>
> **Nom officiel : SOON TRADE** --- toujours deux mots.

## 1. Mission et règles de lecture

Ce fichier doit permettre à un agent de développement de comprendre le
produit, ses règles métier, ses espaces, son architecture, son identité
visuelle et l'ordre de réalisation.

-   **DÉCIDÉ** : choix retenu, à respecter.
-   **À VALIDER** : point nécessitant une confirmation métier,
    juridique, contractuelle ou technique.
-   Les versions logicielles et tarifs de services doivent être
    revérifiés avant implémentation.
-   Ne jamais transformer une hypothèse en règle métier sans validation.
-   Ne pas remplacer les choix visuels approuvés par une direction
    artistique générique.

### Consigne à Claude

Agir comme un architecte logiciel et développeur senior. Développer
progressivement, avec architecture maintenable, sécurité et tests. Avant
chaque grande étape : expliquer le périmètre, identifier les
dépendances, proposer la structure, implémenter par lots, écrire les
tests, vérifier les permissions et documenter le résultat. Ne pas
générer toute l'application en un seul bloc.

------------------------------------------------------------------------

# PARTIE I --- VISION DU PRODUIT

## 2. Présentation

**SOON TRADE** est une plateforme B2B de sourcing, d'approvisionnement
et d'intermédiation commerciale. Le lancement est ancré en Côte
d'Ivoire, notamment à Abidjan, avec une première orientation vers le
commerce de gros agroalimentaire. La plateforme doit pouvoir évoluer
vers d'autres catégories de marchandises et le commerce international.

SOON TRADE accompagne les acheteurs professionnels dans la recherche de
produits et fournisseurs. L'équipe SOON TRADE effectue le sourcing,
consulte les fournisseurs, compare les offres, prépare les propositions
et coordonne les transactions et livraisons.

### Proposition de valeur

-   **Acheteur :** exprimer un besoin et recevoir une proposition
    structurée sans devoir rechercher et négocier avec plusieurs
    fournisseurs.
-   **Fournisseur :** recevoir des demandes commerciales qualifiées et
    transmettre ses offres à un interlocuteur central.
-   **SOON TRADE :** orchestrer le sourcing, les propositions, les
    commandes, les paiements, la logistique et le suivi.

## 3. Ce que SOON TRADE n'est pas

**DÉCIDÉ : SOON TRADE n'est pas une marketplace ouverte.**

Les vendeurs ne publient pas librement pour être contactés directement
par les acheteurs. Il ne faut pas créer un annuaire public qui met
directement les deux parties en relation.

SOON TRADE est une plateforme d'intermédiation : l'équipe centrale
maîtrise le processus.

### Confidentialité fondamentale

Les acheteurs et fournisseurs ne voient pas par défaut : - l'identité et
les coordonnées privées de l'autre partie ; - les tableaux de bord et
données privées de l'autre partie ; - les offres concurrentes ; - les
négociations, notes et commentaires internes ; - les documents et
données auxquels ils ne sont pas autorisés à accéder.

Acheteurs et fournisseurs communiquent avec SOON TRADE, pas directement
entre eux. Cette séparation doit être appliquée côté serveur et dans les
requêtes de données, jamais uniquement par masquage dans l'interface.

------------------------------------------------------------------------

# PARTIE II --- PARCOURS ET ESPACES

## 4. Parcours commercial principal

1.  L'acheteur soumet une demande structurée : produit, quantité,
    spécifications, localisation, délai, conditionnement et informations
    utiles.
2.  SOON TRADE reçoit et qualifie la demande, demande des précisions si
    nécessaire et ouvre un dossier de sourcing.
3.  SOON TRADE identifie des fournisseurs potentiels et leur adresse des
    sollicitations ciblées.
4.  Les fournisseurs répondent à SOON TRADE avec prix, quantités,
    disponibilités, délais, conditions et documents.
5.  SOON TRADE analyse et compare les offres en interne.
6.  SOON TRADE prépare une proposition commerciale destinée à
    l'acheteur.
7.  L'acheteur accepte, refuse ou demande une modification.
8.  Une commande est créée et suivie.
9.  Le paiement, les commissions et les versements sont tracés et
    rapprochés.
10. La livraison, les preuves, les réclamations éventuelles et la
    clôture sont suivies.

Ne pas inventer de transitions de statut qui contournent les validations
internes.

## 5. Les trois espaces privés

Les trois espaces partagent un système de design et certains composants,
mais leurs menus, permissions, données et workflows sont distincts.

### 5.1 Espace acheteur

Fonctionnalités : - profil et organisation ; - création et suivi des
demandes d'approvisionnement ; - complément d'informations demandé par
SOON TRADE ; - consultation des propositions ; - acceptation, refus ou
demande de modification ; - commandes ; - paiements et historique des
transactions le concernant ; - suivi des livraisons et justificatifs
autorisés ; - messagerie avec SOON TRADE ; - réclamations ; - documents
et paramètres.

L'acheteur ne voit pas les offres brutes, la liste des fournisseurs
consultés, leurs coordonnées privées, les comparaisons internes ou les
notes de SOON TRADE.

### 5.2 Espace fournisseur

Fonctionnalités : - profil et organisation fournisseur ; - informations
administratives et documents ; - catalogue de produits ; -
caractéristiques, unités, conditionnements et disponibilités ; -
sollicitations reçues de SOON TRADE ; - réponses structurées : prix,
quantité, délai, conditions, validité et pièces jointes ; -
modification/retrait d'une offre selon son état ; - commandes attribuées
; - préparation et livraison ; - paiements, montants dus et versements
; - messagerie avec SOON TRADE.

Le fournisseur ne voit pas l'identité ni les coordonnées privées de
l'acheteur, les offres concurrentes ou les comparaisons internes.

### 5.3 Espace interne SOON TRADE

Centre de pilotage des opérations, avec permissions granulaires : -
tableau de bord ; - acheteurs et organisations ; - fournisseurs et
vérification ; - demandes d'achat ; - dossiers de sourcing ; - recherche
et sélection fournisseurs ; - sollicitations fournisseurs ; - offres
reçues et comparaisons ; - propositions acheteurs ; - commandes ; -
paiements et rapprochements ; - commissions et versements ; - logistique
et livraisons ; - documents ; - messagerie centralisée ; - réclamations
et litiges ; - CRM ; - rapports et indicateurs ; - utilisateurs, rôles
et permissions ; - journal d'audit et paramètres.

Tous les collaborateurs ne disposent pas automatiquement de tous les
droits.

------------------------------------------------------------------------

# PARTIE III --- MODÈLE ÉCONOMIQUE ET PAIEMENT

## 6. Commission : exemple de référence

  Élément                                     Montant
  ------------------------------------ --------------
  Total payé par l'acheteur              800 000 FCFA
  Commission SOON TRADE (10 %)            80 000 FCFA
  Montant net destiné au fournisseur     720 000 FCFA

Dans cet exemple, le fournisseur reçoit 720 000 FCFA avant les éventuels
frais de paiement ou autres frais prévus contractuellement. Le total
acheteur ne doit pas être confondu avec le net fournisseur.

**Exemple retenu :** commission de 10 %.\
**À VALIDER :** assiette exacte, taxes, frais de paiement, frais
logistiques, cas de remboursement, partie supportant les frais et
exceptions.

### 6.1 Simulation indicative de frais Jèko déjà discutée

Hypothèses précédemment examinées : - encaissement à 1,5 % de 800 000
FCFA : 12 000 FCFA ; - versement mobile money à 1,5 % de 720 000 FCFA :
10 800 FCFA ; - frais totaux indicatifs : 22 800 FCFA ; - commission
brute de 80 000 FCFA moins ces frais : 57 200 FCFA avant autres charges
et taxes.

Ce ne sont pas des tarifs contractuels garantis. Confirmer les tarifs
actuels directement auprès de Jèko.

## 7. Architecture financière

La finance ne doit pas être un simple CRUD.

Exigences : - journal financier traçable et, autant que possible,
immuable ; - écritures correctives plutôt que modification silencieuse
d'écritures passées ; - clés d'idempotence pour éviter les doubles
opérations ; - webhooks vérifiés selon la documentation du prestataire
; - rapprochement paiements / commandes / commissions / versements ; -
gestion des paiements partiels uniquement si le modèle les autorise ; -
remboursements, annulations, échecs, litiges et versements en attente
; - historique des changements d'état ; - distinction entre brut
acheteur, frais, commission, net fournisseur et montant réellement versé
; - un retour navigateur vers une page de succès ne suffit jamais à
confirmer un paiement : confirmation côté serveur obligatoire.

Entités financières envisagées : `Payment`, `LedgerEntry`,
`CommissionEntry`, `Settlement`/`Payout`, `Refund`,
`PaymentWebhookEvent`, `ReconciliationRecord`.

## 8. Jèko et validation réglementaire

**Prestataire préféré à étudier : Jèko** (avec `è`).

Documentation identifiée : - https://jeko.africa/ -
https://developer.jeko.africa/ -
https://developer.jeko.africa/docs/service_providers/escrow -
https://developer.jeko.africa/docs/service_providers/operating-merchants

Les recherches précédentes ont évoqué encaissements, versements,
webhooks et une fonction nommée Escrow. Claude doit relire la
documentation officielle actuelle et confirmer les conditions
contractuelles avant de coder le flux réel.

À confirmer auprès de Jèko : - éligibilité de SOON TRADE et accès
Service Provider ; - encaissement et versements aux fournisseurs ; -
gestion de commission et montant net ; - fonctionnement réel du service
Escrow ; - libération, remboursement et durée de conservation ; -
remboursements et versements partiels ; - frais, taxes, délais, plafonds
et KYC ; - signature et sécurité des webhooks ; - sandbox ou procédure
de test ; - documents réglementaires et contrats.

Des informations antérieures évoquaient l'absence possible de sandbox
séparé et l'usage d'un magasin de test dédié. À revérifier. Ne jamais
effectuer de tests réels non autorisés avec de vrais fonds.

### Prudence juridique

La collecte, la conservation ou le transfert de fonds appartenant à des
tiers peut relever d'obligations réglementaires dans l'espace
UMOA/BCEAO. Le schéma doit être validé par un conseil juridique
compétent en Côte d'Ivoire et par le prestataire autorisé.

-   Ne pas appeler automatiquement le mécanisme « escrow » réglementé.
-   Une fonctionnalité technique du prestataire ne suffit pas à valider
    le modèle juridique.
-   Faire valider les contrats acheteur/fournisseur/SOON TRADE, le
    mandat, la commission, le traitement des fonds, les remboursements
    et les responsabilités.
-   Les implications OHADA évoquées précédemment doivent être vérifiées
    par un professionnel du droit. Ne pas transformer une interprétation
    non validée en règle logicielle.

------------------------------------------------------------------------

# PARTIE IV --- ARCHITECTURE ET DONNÉES

## 9. Architecture générale

**DÉCIDÉ : monolithe modulaire au départ, pas de microservices.**

Objectifs : simplicité de lancement, cohérence transactionnelle,
séparation claire des domaines et possibilité d'extraction ultérieure si
les besoins le justifient.

-   Frontend : une application Next.js avec layouts et routes séparés
    pour acheteur, fournisseur et interne.
-   Backend : API FastAPI organisée par domaines métier.
-   Les règles métier, autorisations et contrôles d'accès sont appliqués
    côté backend.
-   API documentée OpenAPI.
-   validation stricte, gestion centralisée des erreurs, logs
    structurés, migrations versionnées, transactions DB, audit, tests et
    sauvegardes.

## 10. Modules métier

1.  Identity & Access
2.  Buyer Management
3.  Supplier Management
4.  Catalog
5.  Purchase Requests
6.  Sourcing
7.  Supplier Solicitations
8.  Supplier Offers
9.  Buyer Proposals
10. Orders
11. Payments
12. Finance & Ledger
13. Logistics & Deliveries
14. Documents
15. Messaging
16. Claims
17. CRM
18. Notifications
19. Reporting
20. Audit & Administration

## 11. Entités de données de référence

`User`, `Organization`, `OrganizationMember`, `Role`, `Permission`,
`PurchaseRequest`, `SourcingCase`, `SupplierSolicitation`,
`SupplierOffer`, `BuyerProposal`, `Order`, `OrderItem`, `Payment`,
`LedgerEntry`, `CommissionEntry`, `Settlement`/`Payout`, `Delivery`,
`Document`, `Conversation`, `Message`, `Claim`, `Notification`,
`AuditLog`.

Principes : - clés primaires et étrangères explicites ; - dates de
création et modification, suppression logique si appropriée ; - statuts
explicites et transitions documentées ; - argent stocké en unités
entières ou `NUMERIC`, jamais en flottants binaires ; - devise
enregistrée sur les objets financiers ; - conserver une copie des
conditions acceptées au moment de la commande ; - distinguer les données
internes de sourcing de celles publiées dans une proposition ; - ne pas
exposer les identifiants et relations internes sensibles dans les
réponses API ; - encadrer la suppression des données financières et
d'audit.

## 12. Sécurité et isolation

### Autorisation

RBAC avec rôles et permissions granulaires. Contrôle d'accès sur chaque
endpoint et chaque ressource. Vérifier l'appartenance à l'organisation
et le rôle dans le contexte de la ressource. Distinguer consulter,
créer, modifier, valider, annuler, exporter et administrer.

### Cloisonnement

-   acheteur : uniquement ses demandes, propositions, commandes,
    paiements, livraisons, messages et réclamations ;
-   fournisseur : uniquement son profil, ses sollicitations, offres,
    commandes, versements et messages ;
-   fournisseur : aucune liste des autres fournisseurs ni accès aux
    offres concurrentes ;
-   acheteur : aucun accès aux offres brutes ou à l'identité privée des
    fournisseurs ;
-   collaborateur interne : uniquement les modules et opérations
    autorisés ;
-   notes internes : jamais renvoyées dans les DTO destinés aux clients.

Ne jamais faire confiance à un `organization_id`, `buyer_id`,
`supplier_id` ou identifiant transmis par le navigateur sans
vérification backend. Ajouter des tests d'accès croisé entre
organisations et rôles.

### Authentification

Prévoir mots de passe hachés avec Argon2, sessions ou jetons sécurisés,
renouvellement, révocation et déconnexion. Si cookies : `HttpOnly`,
`Secure` en production et `SameSite` adapté. Ne pas stocker les secrets
d'authentification dans `localStorage`. Le choix précis JWT
avec cookies doit être arrêté lors de la conception.

------------------------------------------------------------------------

# PARTIE V --- STACK TECHNIQUE

## 13. Stack de référence

Les versions exactes doivent être vérifiées à l'initialisation :
uniquement des versions stables et compatibles, jamais Canary/alpha/bêta
en production.

### Frontend

  Technologie              Usage
  ------------------------ ---------------------------------
  Next.js 16               Framework web
  React 19                 UI
  TypeScript               Typage
  Tailwind CSS 4           Styles
  shadcn/ui                Composants
  Radix UI                 Primitives accessibles
  Lucide                   Icônes
  Motion / Framer Motion   Animations
  Zustand                  État client partagé
  TanStack Query           Données serveur et cache client
  TanStack Table           Tables
  React Hook Form          Formulaires
  Zod                      Validation frontend
  Recharts                 Graphiques
  next-intl                Internationalisation

Ne pas dupliquer les états : TanStack Query pour les données serveur,
Zustand pour les états d'interface partagés.

### Backend

  Technologie                  Usage
  ---------------------------- -------------------------------------
  Python                       Langage
  FastAPI                      API REST
  Pydantic                     Schémas et validation
  SQLAlchemy                   ORM
  Alembic                      Migrations
  Psycopg 3                    Driver PostgreSQL
  HTTPX                        Appels HTTP
  pwdlib + Argon2              Hachage mots de passe
  JWT                          Authentification selon architecture
  Celery                       Tâches asynchrones
  Redis                        Broker/cache

### Services et infrastructure

  Service            Choix                           Rôle
  ------------------ ------------------------------- ---------------------------
  PostgreSQL         Neon                            Base de données
  Frontend           Vercel                          Hébergement Next.js
  Backend            Render                          Hébergement FastAPI
  Cache/broker       Redis, éventuellement Upstash   Cache et tâches
  Fichiers           S3 / AWS S3                     Documents privés
  E-mails            Resend                          E-mails transactionnels
  Templates e-mail   React Email                     Modèles
  Paiement           Jèko                            À valider
  DNS/protection     Cloudflare                      DNS et protection de base
  Code source        GitHub                          Dépôt
  CI/CD              GitHub Actions                  Automatisation
  Conteneurs         Docker                          Environnements

Choix explicitement retenus : - S3 plutôt que Cloudinary ; - Resend
plutôt que Brevo ; - Jèko plutôt que Geopay comme prestataire à étudier
; - Cloudflare pour DNS et protection de base, sans ajouter tous ses
produits.

### Outils de développement

`pnpm`, `uv`, Docker Compose, Postman ou Bruno, DBeaver, Figma, Mermaid,
OpenAPI, GitHub Actions, Renovate ou Dependabot.

### Versions

Des versions précises ont été évoquées dans les échanges, mais elles ne
constituent pas une matrice garantie. Vérifier les versions stables
courantes et compatibilités de Node, Next, React, Tailwind, Python,
FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, Redis et Celery.
Verrouiller `pnpm-lock.yaml` et `uv.lock`. Python 3.14 avait été
privilégié à une version plus récente pour la maturité de l'écosystème,
sous réserve de compatibilité des dépendances.

------------------------------------------------------------------------

# PARTIE VI --- INFRASTRUCTURE ET COÛTS

## 14. Objectif de lancement

Viser environ **50 utilisateurs** au départ et limiter les coûts, en
utilisant si possible les offres gratuites ou crédits. Distinguer
développement local, démonstration/préproduction et production. Les
offres gratuites ont des limites et ne doivent pas être considérées
comme gratuites à vie.

## 15. Rôle des services

-   **Vercel :** frontend Next.js et CDN déjà fourni. Vérifier les
    conditions du plan pour l'usage commercial.
-   **Render :** API FastAPI. L'offre gratuite peut s'endormir après
    inactivité et n'est pas adaptée à une production critique. Les
    workers de fond peuvent nécessiter une offre payante.
-   **Neon :** PostgreSQL ; surveiller stockage, calcul, connexions et
    quotas.
-   **Redis/Upstash :** cache et broker ; surveiller quotas et latence.
-   **S3 :** bucket privé, URL pré-signées à durée limitée, limites de
    taille/type, alertes de budget et politique de cycle de vie. Pas de
    gratuité illimitée.
-   **Resend :** e-mails transactionnels ; vérifier quotas et domaines.
    Centraliser l'envoi côté backend.
-   **Cloudflare :** DNS, protection de base et proxy HTTP correctement
    configuré. Vercel fournit déjà un CDN frontend, Render héberge l'API
    et S3 stocke les fichiers. Ne pas ajouter initialement R2, Workers,
    Images ou CloudFront sans besoin précis.

Exemple de sous-domaines possible : `soontrade.com`,
`app.soontrade.com`, `api.soontrade.com` (à confirmer selon le domaine
acquis).

### Précautions Cloudflare

Ne pas mettre en cache les endpoints de paiement ou webhooks. Configurer
correctement les IP clientes et en-têtes proxy. Ne pas activer le proxy
partout sans analyser les effets. Vérifier TLS entre Cloudflare et les
hébergeurs.

### Tâches de fond

Celery + Redis pour e-mails, notifications, génération de documents,
tâches longues, planifications et rapprochements. Ne pas détourner un
service web gratuit en worker permanent. Exécuter localement en
développement et prévoir un worker dédié en production lorsque
nécessaire.

------------------------------------------------------------------------

# PARTIE VII --- DOCUMENTS ET NOTIFICATIONS

## 16. Stockage S3

Utiliser un bucket privé pour documents administratifs fournisseurs,
fiches produits, devis, factures, reçus, preuves de livraison et pièces
de réclamation.

-   accès contrôlé par le backend ;
-   URL pré-signées courtes ;
-   aucune URL publique permanente pour les documents privés ;
-   validation MIME et taille ;
-   noms internes non prévisibles ;
-   métadonnées en base ;
-   politique de rétention et suppression à définir.

## 17. E-mails Resend

Utiliser Resend et React Email. Centraliser l'envoi dans le
backend/module de notification.

Événements possibles : création de compte, vérification e-mail,
réinitialisation de mot de passe, sollicitation fournisseur, proposition
acheteur, changement de commande, confirmation de paiement après
vérification serveur, livraison, demande d'information,
réclamation/résolution.

Ne pas inclure de données confidentielles inutiles dans les e-mails :
inviter l'utilisateur à consulter son espace sécurisé.

------------------------------------------------------------------------

# PARTIE VIII --- MARQUE ET DIRECTION ARTISTIQUE

## 18. Identité

**SOON TRADE.**

-   **Soon :** ce qui arrive, anticipation, opportunités à venir.
-   **Trade :** commerce, échanges, approvisionnement et commerce
    international.

Le logo typographique présenté par l'utilisateur et approuvé est la
référence officielle. **Ne pas le remplacer par un logo générique ni le
réinventer sans demande explicite.** Utiliser le fichier source approuvé
s'il est présent dans les assets du projet.

## 19. Direction graphique retenue

Direction SaaS moderne, premium, claire et légèrement futuriste.

Principes : - thème clair par défaut ; - thèmes **Light, Dark, System**
; - surfaces blanches ou très claires en thème clair ; - accents
violets/lavande ; - cartes arrondies ; - ombres douces ; - typographie
moderne et lisible ; - espaces généreux et hiérarchie claire ; -
navigation latérale compacte ; - panneaux modulaires ; - animations
expressives mais utiles ; - même langage visuel pour les trois espaces,
workflows distincts.

Le thème sombre doit être conçu comme une vraie déclinaison. Le thème
système suit le réglage de l'appareil.

### À éviter

-   esthétique de trading financier, crypto ou bourse ;
-   interfaces surchargées ;
-   animations permanentes gênantes ;
-   photos de personnes comme décoration ;
-   emojis comme système d'icônes ;
-   changement arbitraire du logo.

## 20. Design system et motion

Centraliser les tokens : couleurs, surfaces, texte, bordures, états,
rayons, ombres, espacements, typographie, tailles, transitions et focus.

La palette exacte doit être tirée du logo/maquettes approuvés ou fixée
dans Figma puis centralisée. Le violet/lavande est l'accent retenu ; ne
pas introduire une palette concurrente sans validation.

Animations prévues : - transitions de navigation ; - apparition
progressive de sections ; - chiffres/statistiques animés ; -
micro-interactions boutons/cartes ; - feedback loading/succès ; -
transitions d'étapes de workflow ; - animations spring mesurées.

Utiliser Motion/Framer Motion avec parcimonie et respecter
`prefers-reduced-motion`.

## 21. Maquettes

Trois concepts visuels ont été travaillés : acheteur, fournisseur et
administration. Des thèmes clair et sombre ont également été examinés.
Les images sont des références de direction artistique, pas du code
fonctionnel.

À l'intégration : - respecter le logo ; - garder le langage visuel
global ; - adapter le contenu au vrai workflow ; - ne pas reproduire
aveuglément les données fictives ; - créer des composants réutilisables
; - prévoir états vides, erreurs, chargements et responsive.

Si les maquettes originales ne sont pas dans le dépôt, demander leur
ajout dans `docs/design/` ou `public/brand/`. Ne pas prétendre qu'elles
sont disponibles si ce n'est pas le cas.

------------------------------------------------------------------------

# PARTIE IX --- NAVIGATION, RESPONSIVE ET ACCESSIBILITÉ

## 22. Navigation indicative

### Acheteur

Vue d'ensemble, Mes demandes, Propositions, Commandes, Paiements,
Livraisons, Messages, Réclamations, Documents, Organisation/paramètres.

### Fournisseur

Vue d'ensemble, Sollicitations, Mes offres, Catalogue/produits,
Disponibilités/stock, Commandes, Livraisons, Paiements/versements,
Messages, Documents, Profil/paramètres.

### Interne

Vue d'ensemble, Demandes acheteurs, Sourcing, Fournisseurs,
Sollicitations, Offres reçues, Propositions acheteurs, Commandes,
Paiements, Commissions, Versements, Logistique, Réclamations, CRM,
Documents, Rapports, Utilisateurs/permissions, Paramètres, Audit.

Menus filtrés selon les permissions réelles.

## 23. Responsive et accessibilité

-   desktop prioritaire pour les opérations internes riches en tableaux
    ;
-   expérience mobile pleinement utilisable pour acheteurs et
    fournisseurs ;
-   tableaux adaptés au mobile ;
-   formulaires utilisables sur petits écrans ;
-   navigation clavier ;
-   contrastes accessibles ;
-   labels et erreurs explicites ;
-   focus visible ;
-   ne pas communiquer un état uniquement par la couleur.

------------------------------------------------------------------------

# PARTIE X --- ORGANISATION DU CODE ET QUALITÉ

## 24. Structure indicative du monorepo

``` text
soon-trade/
├── README.md
├── docs/
│   ├── product/
│   ├── architecture/
│   ├── business-rules/
│   ├── api/
│   ├── security/
│   └── design/
├── frontend/                    # Next.js
│      ├── app/
│      │   ├── (public)/
│      │   ├── (auth)/
│      │   ├── buyer/
│      │   ├── supplier/
│      │   └── internal/
│      ├── components/
│      ├── features/
│      ├── lib/
│      ├── hooks/
│      ├── styles/
│      └── tests/
├── backend/                    # FastAPI
│       ├── app/
│       │   ├── core/
│       │   ├── modules/
│       │   │   ├── identity/
│       │   │   ├── organizations/
│       │   │   ├── buyers/
│       │   │   ├── suppliers/
│       │   │   ├── catalog/
│       │   │   ├── purchase_requests/
│       │   │   ├── sourcing/
│       │   │   ├── solicitations/
│       │   │   ├── offers/
│       │   │   ├── proposals/
│       │   │   ├── orders/
│       │   │   ├── payments/
│       │   │   ├── finance/
│       │   │   ├── logistics/
│       │   │   ├── documents/
│       │   │   ├── messaging/
│       │   │   ├── claims/
│       │   │   ├── notifications/
│       │   │   ├── reporting/
│       │   │   └── audit/
│       │   ├── integrations/
│       │   │   ├── jeko/
│       │   │   ├── s3/
│       │   │   └── resend/
│       │   └── main.py
│       ├── alembic/
│       ├── tests/
│       └── pyproject.toml
├── packages/
│   ├── contracts/
│   └── config/
├── infra/
│   ├── docker/
│   └── compose.yaml
├── .github/
│   └── workflows/
├── pnpm-workspace.yaml
├── package.json
└── .env.example
```

Structure indicative : ne pas multiplier les packages partagés
inutilement.

## 25. Conventions et tests

-   TypeScript strict et Python typé ;
-   logique métier hors des routes HTTP et composants UI ;
-   responsabilités explicites ;
-   pas de permission uniquement côté client ;
-   pas de secrets dans Git ;
-   pas de duplication des calculs financiers.

Tests backend : services métier, API, migrations, autorisations,
isolation, idempotence, transitions, webhooks, commissions et montants
nets.

Tests frontend : composants critiques, formulaires, workflows, rôles,
états loading/empty/error/success et responsive.

Scénario end-to-end minimum : 1. acheteur crée une demande ; 2.
collaborateur qualifie et ouvre le sourcing ; 3. fournisseur répond à
une sollicitation ; 4. SOON TRADE prépare une proposition ; 5. acheteur
accepte ; 6. commande créée ; 7. paiement confirmé par webhook ; 8.
logistique mise à jour ; 9. versement et commission rapprochés ; 10.
acheteur et fournisseur ne peuvent pas accéder aux données privées l'un
de l'autre.

------------------------------------------------------------------------

# PARTIE XI --- PLAN DE DÉVELOPPEMENT STEP BY STEP

## 26. Phases de réalisation

### Phase 0 --- Cadrage final

-   règles métier et glossaire ;
-   diagrammes de parcours ;
-   matrice rôles/permissions ;
-   statuts et transitions ;
-   validation commission/assiette ;
-   validation juridique du flux financier ;
-   confirmation prestataire.

**Sortie :** règles critiques documentées et points ouverts identifiés.

### Phase 1 --- Initialisation

-   monorepo ;
-   pnpm et uv ;
-   Next.js, FastAPI, PostgreSQL ;
-   Docker Compose ;
-   `.env.example` ;
-   lint, formatage, typage, tests ;
-   GitHub Actions ;
-   commandes de démarrage documentées.

**Sortie :** frontend et API démarrent localement, connexion DB
fonctionnelle, tests de base réussis.

### Phase 2 --- Design system

-   logo ;
-   tokens ;
-   thèmes Light/Dark/System ;
-   layouts des trois espaces ;
-   composants UI ;
-   responsive et accessibilité ;
-   animations de base.

**Sortie :** trois espaces visuellement cohérents.

### Phase 3 --- Identité et permissions

-   inscription/connexion ;
-   vérification e-mail ;
-   récupération mot de passe ;
-   organisations et membres ;
-   rôles et permissions ;
-   guards frontend et contrôles backend ;
-   audit des opérations sensibles.

**Sortie :** chaque profil n'accède qu'à son espace et ses données.

### Phase 4 --- Acheteurs et fournisseurs

-   profils et organisations ;
-   vérification fournisseurs ;
-   documents administratifs ;
-   catégories, catalogue et disponibilités.

**Sortie :** données de base gérées et isolées.

### Phase 5 --- Demandes et sourcing

-   demande acheteur ;
-   qualification interne ;
-   dossier de sourcing ;
-   assignation collaborateur ;
-   recherche fournisseurs ;
-   commentaires et actions internes.

**Sortie :** demande transformable en dossier de sourcing.

### Phase 6 --- Sollicitations et offres

-   création/envoi de sollicitations ;
-   notification fournisseur ;
-   réponse structurée ;
-   validité, modification et retrait ;
-   comparaison interne.

**Sortie :** comparaison possible sans révéler les fournisseurs entre
eux.

### Phase 7 --- Propositions acheteurs

-   proposition à partir d'offres ;
-   prix, quantités, délais et conditions ;
-   validation interne ;
-   présentation à l'acheteur ;
-   acceptation/refus/modification ;
-   conservation de la version acceptée.

**Sortie :** l'acheteur voit uniquement sa proposition.

### Phase 8 --- Commandes et logistique

-   commande depuis proposition acceptée ;
-   figer lignes et conditions ;
-   préparation ;
-   livraisons et preuves ;
-   incidents et réclamations.

**Sortie :** suivi de l'acceptation à la livraison.

### Phase 9 --- Paiements et finance

À réaliser après validation contractuelle et réglementaire : -
environnement de test prestataire ; - encaissement et vérification ; -
webhooks idempotents ; - ledger ; - commission et net fournisseur ; -
remboursements et annulations ; - rapprochement ; - versements.

**Sortie :** opérations traçables, rapprochées et testées sans double
comptabilisation.

### Phase 10 --- Messagerie, notifications et CRM

-   conversations acheteur/SOON TRADE ;
-   conversations fournisseur/SOON TRADE ;
-   notifications in-app ;
-   e-mails transactionnels ;
-   historique relationnel ;
-   confidentialité.

**Sortie :** communication centralisée sans canal direct non autorisé.

### Phase 11 --- Reporting et administration

-   dashboards selon rôle ;
-   indicateurs opérationnels ;
-   rapports commerciaux et financiers ;
-   exports autorisés ;
-   audit ;
-   gestion des rôles et paramètres.

**Sortie :** pilotage opérationnel et historique complet.

### Phase 12 --- Préproduction et production

-   audit sécurité ;
-   tests d'isolation ;
-   tests de charge adaptés ;
-   sauvegardes et restauration ;
-   monitoring et alertes ;
-   DNS/TLS ;
-   vérification secrets ;
-   politique données personnelles ;
-   validation juridique et contractuelle ;
-   procédures de support et d'incident.

**Sortie :** plateforme prête pour les premiers utilisateurs.

------------------------------------------------------------------------

# PARTIE XII --- POINTS À CONFIRMER

## 27. Registre des points ouverts

  -----------------------------------------------------------------------
  Sujet                   État                    Action
  ----------------------- ----------------------- -----------------------
  Commission de 10 %      Exemple de référence    Confirmer assiette,
                                                  exceptions et frais

  Jèko                    Prestataire préféré     Confirmer contrat, API,
                                                  tarifs, flux et sandbox

  Escrow / conservation   Non validé              Validation juridique et
  de fonds                juridiquement           prestataire

  Remboursements partiels À définir               Règles commerciales

  Paiements partiels      À définir               Confirmer si autorisés
  acheteur                                        

  Versements partiels     À définir               Confirmer cas d'usage
  fournisseur                                     

  Statuts détaillés       À spécifier             Machines à états

  Documents KYC           À spécifier             Liste et processus de
  fournisseurs                                    vérification

  Logistique              À détailler             Transporteurs,
                                                  responsabilités,
                                                  preuves

  Langues                 i18n prévu              Langues de lancement

  Domaine                 Non communiqué ici      Confirmer domaine et
                                                  sous-domaines

  Logo et maquettes       Visuellement approuvés  Ajouter les fichiers
  sources                                         originaux au dépôt

  Hébergement production  Options retenues        Vérifier coûts et
                                                  quotas actuels

  Conservation des        À définir               Politique légale et
  données                                         opérationnelle
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# PARTIE XIII --- DIRECTIVES FINALES À CLAUDE

## 28. Décisions impératives

1.  Le nom est **SOON TRADE**, deux mots.
2.  Plateforme B2B de sourcing/intermédiation, pas marketplace ouverte.
3.  Trois espaces séparés : acheteur, fournisseur, interne.
4.  Acheteur et fournisseur ne communiquent pas directement et ne voient
    pas leurs données privées respectives.
5.  SOON TRADE pilote sourcing, offres, propositions, commandes et
    suivi.
6.  Distinguer montant acheteur, commission, frais et net fournisseur.
7.  Finance idempotente, traçable et rapprochée.
8.  Valider le flux de paiement et la conservation des fonds avant
    production.
9.  Monolithe modulaire au départ.
10. Next.js/React/TypeScript côté frontend ; FastAPI/Python/PostgreSQL
    côté backend.
11. S3 privé, Resend et Jèko (à valider).
12. Cloudflare principalement pour DNS et protection de base.
13. Interface claire par défaut, thèmes clair/sombre/système.
14. Direction artistique premium, lumineuse, violette/lavande, cartes
    arrondies, espaces généreux, animations utiles.
15. Conserver le logo approuvé.
16. Appliquer la sécurité côté backend, jamais uniquement dans
    l'interface.
17. Développer étape par étape, avec tests et documentation.
18. Vérifier versions, tarifs et capacités actuels ; ne pas inventer les
    fonctionnalités d'un prestataire.

## 29. Première mission de Claude

Ne pas commencer par coder tous les modules.

1.  Lire ce README intégralement.
2.  Produire une synthèse de compréhension du produit.
3.  Proposer le diagramme des trois espaces et du parcours de sourcing.
4.  Proposer la matrice rôles/permissions.
5.  Définir les machines à états des demandes, sollicitations, offres,
    propositions, commandes, paiements et livraisons.
6.  Proposer le modèle de données initial et les relations.
7.  Proposer l'arborescence finale du monorepo.
8.  Identifier les points bloquants et questions à valider.
9.  Attendre la validation du cadrage avant de générer le socle
    technique.

**Objectif final :** construire une plateforme SOON TRADE sécurisée,
cohérente, évolutive et exploitable, fidèle au modèle d'intermédiation
et aux décisions consignées dans ce document.
