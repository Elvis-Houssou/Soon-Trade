# Matrice rôles / permissions

> **Rôles DÉCIDÉS le 14 novembre 2026** : le porteur du projet a délégué la définition
> des rôles internes ; la liste ci-dessous fait donc référence. Les lignes encore
> marquées **À VALIDER** dans le dernier tableau restent ouvertes.

## Inscription sur invitation (DÉCIDÉ)

Au lancement, personne ne s'inscrit librement, ni acheteur ni fournisseur.

- Un collaborateur interne habilité (`admin`, `sales_agent` pour un acheteur,
  `sourcing_agent` pour un fournisseur) crée l'organisation et invite son premier
  utilisateur, qui en devient le propriétaire (`buyer_owner` ou `supplier_owner`).
- Le propriétaire invite ensuite les membres de sa propre organisation.
- Les collaborateurs internes sont invités par un `admin`.
- Une invitation est un lien à usage unique, à durée limitée, lié à une adresse e-mail,
  à une organisation et à un rôle ; seul son condensat est stocké.
- Il n'existe aucun endpoint d'inscription publique. L'ouverture ultérieure de
  l'inscription libre sera un réglage, pas une refonte.

## Principes (DÉCIDÉS par le README)

- Chaque permission est vérifiée côté backend, sur chaque endpoint et chaque ressource.
- Une permission ne suffit pas : l'appartenance de la ressource à l'organisation de
  l'utilisateur est contrôlée en plus (périmètre).
- Aucun identifiant d'organisation transmis par le navigateur n'est cru sur parole.
- Les menus du frontend sont filtrés selon les permissions réelles, mais ce filtrage
  n'est jamais la protection.

## Format des permissions

`<ressource>:<action>` — par exemple `purchase_request:create`, `offer:compare`,
`payout:validate`. Actions : `read`, `create`, `update`, `validate`, `cancel`, `export`,
`admin`.

## Rôles proposés

### Côté client (portée : sa propre organisation uniquement)

| Rôle | Description |
|---|---|
| `buyer_owner` | Administre l'organisation acheteuse, ses membres, accepte les propositions. |
| `buyer_member` | Crée et suit les demandes ; ne gère pas les membres. |
| `supplier_owner` | Administre l'organisation fournisseur, ses membres, ses documents. |
| `supplier_member` | Gère catalogue, offres et livraisons. |

### Côté interne SOON TRADE

| Rôle | Description |
|---|---|
| `admin` | Utilisateurs, rôles, paramètres, audit. |
| `sourcing_agent` | Qualification, dossiers de sourcing, sollicitations, comparaison. |
| `sales_agent` | Propositions acheteurs, relation client, CRM. |
| `finance_agent` | Paiements, commissions, versements, rapprochement. |
| `logistics_agent` | Livraisons, preuves, incidents. |
| `support_agent` | Messagerie, réclamations. |
| `auditor` | Lecture seule, y compris le journal d'audit. |

## Matrice

Légende : **L** lire · **C** créer · **M** modifier · **V** valider · **A** annuler ·
**E** exporter · — aucun accès. « (soi) » = limité à sa propre organisation.

| Ressource | Acheteur | Fournisseur | Sourcing | Commercial | Finance | Logistique | Support | Auditeur |
|---|---|---|---|---|---|---|---|---|
| Demande d'achat | L C M A (soi) | — | L M V | L | L | L | L | L |
| Dossier de sourcing | — | — | L C M V | L | — | — | — | L |
| Sollicitation | — | L (soi) | L C M A | L | — | — | — | L |
| Offre fournisseur | — | L C M A (soi) | L V | L | — | — | — | L |
| Comparaison d'offres | — | — | L C | L | — | — | — | L |
| Proposition acheteur | L V (soi) | — | L | L C M V A | L | — | — | L |
| Commande | L (soi) | L (soi) | L | L C A | L | L M | L | L |
| Paiement | L (soi) | — | — | L | L V E | — | — | L |
| Commission | — | — | — | — | L E | — | — | L |
| Versement | — | L (soi) | — | — | L C V E | — | — | L |
| Livraison | L (soi) | L M (soi) | — | L | — | L C M V | L | L |
| Document | L C (soi) | L C (soi) | L V | L | L | L | L | L |
| Conversation | L C (soi) | L C (soi) | L C | L C | L C | L C | L C | L |
| Réclamation | L C (soi) | L (soi) | L | L | L | L M | L M V | L |
| Organisation | L M (soi) | L M (soi) | L V | L M | L | L | L | L |
| Utilisateurs et rôles | (soi, owner) | (soi, owner) | — | — | — | — | — | L |
| Journal d'audit | — | — | — | — | — | — | — | L |

`admin` détient toutes les permissions internes, sauf la modification du journal d'audit
et des écritures financières, qui n'est offerte à personne.

## Ce que chaque espace ne reçoit jamais

| Donnée | Acheteur | Fournisseur |
|---|---|---|
| Identité et coordonnées de l'autre partie | jamais | jamais |
| Offres brutes, liste des fournisseurs consultés | jamais | — |
| Offres concurrentes, liste des autres fournisseurs | — | jamais |
| Comparaisons et notes internes | jamais | jamais |
| Commission et marge de SOON TRADE | **À VALIDER** | **À VALIDER** |
| Prix payé par l'acheteur | — | **À VALIDER** |

## Tests obligatoires

Pour chaque ressource cloisonnée : un test d'accès croisé entre deux organisations du
même type, un test acheteur → ressource fournisseur, un test fournisseur → ressource
acheteur, et un test de rôle interne non autorisé. Un accès refusé pour cause de
périmètre répond 404, pas 403, afin de ne pas confirmer l'existence de la ressource.
