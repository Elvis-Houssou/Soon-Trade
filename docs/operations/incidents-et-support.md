# Incidents et support

> Procédures proposées, **À VALIDER** par SOON TRADE (noms, astreinte, délais).

## Niveaux de gravité

| Niveau | Exemple | Prise en charge | Information des clients |
|---|---|---|---|
| Critique | Plateforme indisponible, fuite de données, accès d'une organisation aux données d'une autre | Immédiate, 24 h/24 | Sous 24 h ; autorité de protection des données selon la loi |
| Majeur | Une fonction clé bloquée (propositions, commandes, e-mails) | Dans l'heure ouvrée | Si plus de 4 h |
| Mineur | Défaut d'affichage, lenteur ponctuelle | Jour ouvré suivant | Non |

## Conduite d'un incident

1. **Constater** : alerte, ou signalement d'un client avec son `X-Request-ID` si possible.
2. **Nommer un responsable** : il coordonne et tient la chronologie.
3. **Contenir** :
   - indisponibilité : retour à la version précédente (Render « Rollback ») ;
   - fuite ou accès anormal : révoquer les sessions concernées (désactiver le compte),
     faire tourner les secrets exposés (Resend, S3, base) ;
   - données corrompues : restaurer à un instant donné dans une base séparée, comparer,
     puis basculer (voir `sauvegardes.md`).
4. **Rétablir** et vérifier : `/health/ready`, `pnpm verify:api` contre l'environnement.
5. **Informer** selon le tableau ci-dessus.
6. **Analyser sous 5 jours** : cause, chronologie, correctifs, test ajouté pour que le cas
   ne revienne pas. Le journal d'audit (`/audit`) sert de source de vérité.

## Faire tourner un secret

| Secret | Où le changer | Effet |
|---|---|---|
| Clé Resend | Resend → nouvelle clé → Render | Aucun |
| Clés S3 | AWS IAM → nouvelle clé → Render → supprimer l'ancienne | Aucun |
| Mot de passe de la base | Render → soontrade-db (rotation des identifiants) ; `DATABASE_URL` suit seule | Redémarrage de l'API |
| Sessions des utilisateurs | Désactiver puis réactiver le compte | Reconnexion demandée |

## Support aux utilisateurs

- **Canal unique** : la messagerie de l'application (Phase 10). Les demandes reçues
  ailleurs (téléphone, WhatsApp) y sont recopiées pour garder l'historique.
- **Délai de première réponse** proposé : 4 heures ouvrées.
- **Réclamations** sur une commande : le module Réclamations, avec réponse écrite
  obligatoire.
- **Jamais** demander un mot de passe : la réinitialisation se fait par « Mot de passe
  oublié ».
