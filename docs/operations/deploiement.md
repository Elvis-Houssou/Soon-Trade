# Déploiement — préproduction et production

> Plan prêt à l'emploi, **pas encore exécuté** : les comptes Render, Neon, AWS et le nom de
> domaine sont à créer. Les valeurs secrètes se saisissent dans chaque hébergeur, jamais
> dans le dépôt.

## Architecture cible

| Élément | Service | Rôle |
|---|---|---|
| Site (Next.js) | Vercel | Pages, en-têtes de sécurité (`frontend/next.config.ts`) |
| API (FastAPI) | Render, `render.yaml` | 2 processus, migrations avant chaque mise en service |
| Base PostgreSQL | Neon | Sauvegarde continue (PITR) |
| Documents | AWS S3, bucket privé | Liens de téléchargement signés, 120 s |
| E-mails | Resend, domaine vérifié | Transactionnels, fr / en / de |
| DNS et TLS | Cloudflare | Certificats, protection DDoS |

Deux environnements identiques : **préproduction** (`staging`) puis **production**. Chacun
a sa base, son bucket, sa clé Resend et ses comptes.

## Garde-fous automatiques

L'API **refuse de démarrer** en `staging` ou `production` si :
- `FRONTEND_URL` n'est pas en https ;
- `CORS_ORIGINS` est vide, contient `*` ou une origine http ;
- `DATABASE_URL` pointe vers une base locale ;
- `RESEND_API_KEY` manque ;
- S3 utilise l'émulateur local ou ses clés factices ;
- `SEED_PASSWORD` est défini.

Les règles sont dans `backend/app/core/hardening.py` et sont testées.

## Variables

**API** (Render) : `ENVIRONMENT`, `DATABASE_URL`, `CORS_ORIGINS` (ex.
`["https://app.soontrade.com"]`), `FRONTEND_URL`, `RESEND_API_KEY`, `EMAIL_FROM`,
`S3_BUCKET`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_ENDPOINT_URL`
vide.

**Site** (Vercel) : `NEXT_PUBLIC_API_URL` (ex. `https://api.soontrade.com`). Rien d'autre :
tout ce qui commence par `NEXT_PUBLIC_` est public.

## Mise en service, dans l'ordre

1. Neon : créer la base, copier l'URL de connexion (`postgresql+psycopg://…?sslmode=require`).
2. AWS : bucket privé (accès public bloqué, chiffrement par défaut, versionnage activé),
   utilisateur IAM limité à ce bucket (`s3:GetObject`, `s3:PutObject`).
3. Resend : vérifier le domaine (enregistrements DNS) ; créer une clé « Sending access »
   limitée à ce domaine.
4. Render : « New Blueprint » sur le dépôt → `render.yaml` ; saisir les variables secrètes.
5. Vercel : importer le dépôt, dossier `frontend`, variable `NEXT_PUBLIC_API_URL`.
6. Cloudflare : `app.` → Vercel, `api.` → Render ; TLS « Full (strict) » ; HSTS activé.
7. Vérifier : `GET https://api…/health/ready` répond `{"status":"ok","database":"up"}` ;
   lancer `pnpm verify:api` contre la préproduction (adapter l'adresse dans le script).
8. Créer le premier administrateur interne (invitation), **ne jamais** lancer `db:seed`.

## Mise à jour

`autoDeploy` est désactivé : chaque version se déploie à la main, d'abord en
préproduction, puis en production après vérification. Les migrations Alembic tournent
avant le démarrage (`preDeployCommand`) ; une migration qui échoue bloque la version.

## Retour arrière

Render : « Rollback » vers la version précédente. Si une migration a modifié le schéma,
restaurer la base au moment voulu (Neon, restauration à un instant donné) **avant** de
relancer l'ancienne version. Voir `sauvegardes.md`.
