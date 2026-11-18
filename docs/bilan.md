# Bilan du projet — 18 novembre 2026

## 1. Où en est-on

| Phase | État |
|---|---|
| 0 — Cadrage | Proposé, **en attente de validation** |
| 1 — Initialisation | Fait (monorepo, CI) ; dépôt GitHub distant à créer |
| 2 — Design system | Fait (fr, en, de ; clair et sombre ; animations) ; logo vectoriel à fournir |
| 3 — Identité et permissions | Fait |
| 4 — Acheteurs et fournisseurs | Fait |
| 5 — Demandes et sourcing | Fait |
| 6 — Sollicitations et offres | Fait |
| 7 — Propositions acheteurs | Fait |
| 8 — Commandes et logistique | Fait |
| 9 — Paiements et finance | **Bloquée** (juriste, contrat Jèko) |
| 10 — Messagerie, notifications, CRM | Fait |
| 11 — Reporting et administration | Fait (sans commissions ni paiements, qui dépendent de la Phase 9) |
| 12 — Préproduction et production | **Préparée, pas exécutée** : il manque les comptes, le domaine et le déploiement |

**Le parcours de bout en bout fonctionne**, de la demande de l'acheteur jusqu'à la livraison
confirmée et la réclamation, sauf le paiement. Il a été vérifié dans le navigateur, dans les
trois langues, en clair et en sombre, sur mobile et sur grand écran.

**Contrôles** au 18/11/2026 :
- 279 tests backend (cloisonnement, permissions, règles, et toutes les routes testées sans
  session) ;
- 66 vérifications sur l'API réellement lancée ;
- lint, typage et build du frontend ;
- aucune vulnérabilité connue dans les dépendances ;
- sauvegarde et restauration testées ;
- test de charge réussi (20 utilisateurs, 95e centile à 358 ms).

## 2. Ce qui a été fait

**Acheteur**
- Organisation, membres et documents.
- Demandes d'achat : brouillon, soumission, réponse aux demandes de précisions.
- Propositions : accepter, refuser ou demander une modification ; versions successives.
- Commandes aux conditions figées, suivi des livraisons, confirmation de réception.
- Réclamations, messagerie avec SOON TRADE, notifications, tableau de bord.

**Fournisseur**
- Profil, documents et catalogue.
- Sollicitations reçues : offre, nouvelle version, retrait, refus motivé.
- Bons de commande à son prix, livraisons à faire avancer, preuves.
- Messagerie, notifications, tableau de bord.

**Équipe SOON TRADE**
- Qualification des demandes, dossiers de sourcing, recherche dans les catalogues,
  présélection.
- Sollicitations relues puis envoyées ; comparaison des offres.
- Propositions avec marge et validation par une seconde personne.
- Commandes et bons fournisseurs, logistique, preuves, incidents, réclamations et litiges.
- Messagerie avec notes internes, CRM, tableaux de bord, rapports, exports, journal
  d'audit.
- Gestion des membres, des rôles et des catégories.

**Socle**
- Cloisonnement par organisation : la ressource d'un autre répond 404.
- Permissions par rôle ; journal d'audit en insertion seule.
- E-mails dans les trois langues, en texte et en HTML.
- Stockage S3 privé, avec liens de téléchargement de 120 s.
- En-têtes de sécurité ; refus de démarrer avec une configuration dangereuse.
- CI : tests, recherche de secrets, audit des dépendances.

## 3. Ce qui manque

### Bloqué par une décision ou un tiers

- **Phase 9, paiements** :
  - avis d'un juriste en Côte d'Ivoire sur la conservation des fonds ;
  - contrat Jèko (accès, tarifs, environnement de test) ;
  - règles de commission (assiette, taxes, qui paie les frais) ;
  - paiements partiels, remboursements, versements.

  En découlent : écrans Paiements, Commissions et Versements, confirmation de commande
  après paiement, rapports financiers.
- **Mise en production** : comptes Render, Neon, AWS, Cloudflare ; nom de domaine ;
  domaine vérifié dans Resend. Sans ce dernier, les e-mails ne partent qu'à l'adresse du
  compte Resend.
- **Dépôt GitHub distant** : la CI ne tournera qu'une fois le dépôt poussé. Aucun commit
  n'existe encore.
- **Éléments graphiques** : logo vectoriel (SVG, clair et sombre) ; images des bandeaux,
  avec leurs droits d'usage.
- **Chiffres du site public** (+500 fournisseurs, etc.) : fictifs, à remplacer avant
  publication.

### À développer

**Avant l'ouverture au public**
- Limitation de débit globale par adresse IP (seule la connexion est protégée
  aujourd'hui).
- Double authentification des comptes internes.
- Test d'intrusion par un tiers.

**Exigé par la politique de données**
- Export des données d'un utilisateur et suppression de compte.
- Anonymisation automatique à l'échéance des durées de conservation.

**Communication et suivi**
- Pièces jointes dans les messages.
- Détection de coordonnées dans les messages, contre le contournement de
  l'intermédiation.
- Suivi des quantités par livraison (livraisons partielles).
- Réclamations visibles du fournisseur concerné (la matrice des rôles le prévoit).

**Confort et maintenance**
- Notifications en temps réel (aujourd'hui, relève toutes les 30 s).
- Pagination des listes, quand les volumes l'exigeront.
- Pages encore en attente dans la navigation :
  - « Paramètres » des comptes clients ;
  - « Documents » dans les trois espaces (aujourd'hui dans Organisation et Profil) ;
  - « Disponibilités et stock » du fournisseur (aujourd'hui, une disponibilité par produit du
    catalogue).
- Gestion des rôles en base (aujourd'hui dans le code).

### À exécuter au déploiement

Le guide est `docs/operations/deploiement.md`. Il faudra :
- brancher les alertes (`supervision.md`) ;
- refaire le test de charge et l'exercice de restauration sur la préproduction ;
- consigner les résultats dans `sauvegardes.md` et `supervision.md`.

## 4. Ce qui reste à valider

Chaque point est marqué « À VALIDER » dans le code ou la documentation.

### Produit et règles métier

Voir `docs/business-rules/statuts-et-transitions.md` et `communication.md`.

**Inscription et vérification**
- Inscription sur invitation uniquement.
- Seuls les fournisseurs passent une vérification ; un acheteur est actif d'emblée.
- Listes de départ : pièces administratives (KYC), catégories, unités de vente, motifs de
  réclamation.

**Demandes d'achat**
- Champs obligatoires dès le brouillon : produit, quantité, unité, lieu de livraison.
- Annulation permise depuis « précisions demandées ».
- L'équipe ne modifie jamais le contenu d'une demande.

**Sourcing**
- Le dossier est assigné à la personne qui l'ouvre ; il ne s'assigne qu'à un administrateur
  ou à un agent de sourcing.
- Il est figé dès que la demande quitte l'état « en sourcing ».

**Sollicitations et offres**
- Une seule sollicitation par fournisseur et par dossier.
- Date limite de réponse proposée à J+7.
- Prix en francs CFA uniquement ; quantité partielle permise.
- Une offre retirée ne peut pas être renvoyée ; plusieurs offres peuvent être retenues dans
  un même dossier.

**Propositions**
- Principe des quatre yeux : celui qui prépare ne valide pas.
- Validité de 7 jours, jamais au-delà de celle des offres reprises.
- Vendre sous le prix d'achat est permis : la marge négative est seulement signalée.
- Une proposition envoyée ne s'annule pas.
- Seul le propriétaire du compte acheteur accepte ou refuse.

**Commandes et livraisons**
- La commande est créée automatiquement à l'acceptation.
- Confirmation sans paiement en attendant la Phase 9.
- Un bon de commande par fournisseur, transmis seulement après confirmation.
- Passage automatique à « Expédiée » puis « Livrée ».
- Annulation impossible dès qu'une livraison est partie.
- Seule l'équipe publie une preuve à l'acheteur.

**Réclamations**
- Ouvertes de la confirmation à la livraison ; litige automatique sur une commande partie.
- Le fournisseur n'en voit rien.

**Messagerie et notifications**
- L'équipe peut écrire à n'importe quel client.
- Un message du client rouvre un fil clos.
- Pas d'e-mail pour les notifications internes.
- Une invitation part dans la langue de la personne qui invite.

**Rapports**
- Exports réservés à la finance, à l'administrateur et à l'auditeur.
- Chiffre d'affaires et marge visibles des seuls rôles qui lisent les rapports.

### Sécurité et données

- Authentification par cookie de session (`docs/security/authentification.md`).
- Matrice des rôles (`roles-permissions.md`) : visibilité de la marge et du prix payé par
  l'acheteur.
- Politique de données personnelles, durées de conservation, sous-traitants et transferts
  (`docs/legal/donnees-personnelles.md`) : **validation juridique requise**.

### Exploitation

- Rétention des sauvegardes, objectifs de reprise (RPO 1 h, RTO 4 h).
- Seuils d'alerte et de charge.
- Niveaux de gravité, astreinte, délais de support (`docs/operations/`).

## 5. Prochaines étapes conseillées

1. Valider le cadrage et les règles ci-dessus, même par lots.
2. Créer le dépôt GitHub, puis faire un premier commit.
3. Acheter le domaine, le vérifier dans Resend et créer les comptes d'hébergement ;
   déployer la préproduction en suivant `docs/operations/deploiement.md`.
4. Lancer la démarche juridique et le contrat Jèko, préalables à la Phase 9.
5. Avant l'ouverture au public : limitation de débit, double authentification des comptes
   internes, export et suppression des données personnelles, test d'intrusion.
