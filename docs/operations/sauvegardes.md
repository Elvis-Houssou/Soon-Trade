# Sauvegardes et restauration

## Ce qui est sauvegardé

| Donnée | Où | Comment | Rétention proposée (À VALIDER) |
|---|---|---|---|
| Base PostgreSQL | Neon | Sauvegarde continue, restauration à la seconde (PITR) | 7 jours (offre Launch) à 30 jours |
| Base PostgreSQL | Hors hébergeur | `scripts/backup.py save`, chaque semaine | 12 semaines, stockage chiffré séparé |
| Documents | S3 | Versionnage du bucket + réplication vers une autre région | 90 jours de versions |
| Configuration | Render, Vercel | Variables saisies dans chaque service, recopiées dans un coffre de mots de passe | — |

Objectifs proposés (À VALIDER) : perte de données maximale de 1 h (RPO), remise en
service en 4 h (RTO).

## Commandes

```bash
pnpm db:backup                          # base locale -> backups/soontrade-AAAAMMJJ-HHMMSS.dump
pnpm db:restore backups/FICHIER.dump    # -> base séparée « soontrade_restore », puis contrôle
```

La restauration **ne remplace jamais** la base de travail : elle crée une base à part, puis
compare la version du schéma et le nombre de comptes, demandes, commandes et lignes du
journal d'audit avec l'original.

## Exercice de restauration

À faire **chaque trimestre**, et après toute migration importante :

1. Sauvegarder, puis restaurer dans une base séparée.
2. Vérifier les contrôles affichés (tous « OK »).
3. Démarrer une API sur la copie et lancer `pnpm verify:api`.
4. Noter la date, la durée et le résultat ci-dessous.

| Date | Environnement | Taille | Durée | Résultat |
|---|---|---|---|---|
| 18/11/2026 | local | 146 Ko | < 10 s | OK : schéma `0e30f41a2654`, 9 comptes, 15 demandes, 1 commande, 412 lignes d'audit |
