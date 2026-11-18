# Supervision et alertes

## Signaux déjà en place

- **Santé** : `GET /health` (le processus répond) et `GET /health/ready` (la base répond,
  sinon 503). Render s'en sert pour ne mettre en service qu'une version saine.
- **Journal** : une ligne JSON par requête, avec `request_id`, méthode, **modèle de route**
  (jamais l'adresse réelle, qui peut contenir un jeton), statut et durée en ms. L'en-tête
  `X-Request-ID` est renvoyé au client : il permet de retrouver une requête signalée par
  un utilisateur.
- **Erreurs** : toute exception non prévue est journalisée avec sa trace et répond un 500
  sans détail.
- **E-mails** : un échec d'envoi est journalisé (`*_email_failed`) sans bloquer l'action.
- **Journal d'audit** : actions sensibles, consultable par l'auditeur et l'administrateur.

## Alertes à brancher (À FAIRE au déploiement)

| Alerte | Source | Seuil proposé (À VALIDER) |
|---|---|---|
| API injoignable | Sonde externe (ex. Better Stack, UptimeRobot) sur `/health/ready` | 2 échecs consécutifs à 1 min |
| Erreurs serveur | Journaux Render → outil de logs | plus de 1 % de 5xx sur 5 min |
| Lenteur | Journaux (`duration_ms`) | 95e centile au-delà de 800 ms sur 10 min |
| E-mails en échec | Journaux (`*_email_failed`) | toute occurrence en production |
| Base | Tableau de bord Neon | stockage au-delà de 80 %, connexions saturées |

Suivi d'erreurs détaillé : brancher Sentry (ou équivalent) côté API et site une fois le
compte créé ; ne jamais y envoyer de corps de requête (données personnelles).

## Test de charge

```bash
pnpm load:api              # 20 utilisateurs simultanés, 30 s, contre l'API locale
```

Seuils d'acceptation (À VALIDER) : 95e centile ≤ 800 ms et moins de 1 % d'erreurs, pour
quelques dizaines d'utilisateurs simultanés (plateforme B2B).

| Date | Configuration | Débit | Médiane | 95e centile | Erreurs | Résultat |
|---|---|---|---|---|---|---|
| 18/11/2026 | portable, 1 processus | 37/s | 458 ms | 871 ms | 0 | échec |
| 18/11/2026 | portable, 4 processus | 48/s | 248 ms | 952 ms | 0 | échec |
| 18/11/2026 | 4 processus, listes chargées en une fois | 87/s | 199 ms | 358 ms | 0 | **réussi** |

Le premier échec venait des listes de demandes et de sollicitations, qui lisaient les
relations une ligne à la fois ; elles sont désormais chargées en quelques requêtes.
À refaire sur la préproduction réelle, car un portable partagé avec la base et le
générateur de charge ne mesure qu'un ordre de grandeur.
