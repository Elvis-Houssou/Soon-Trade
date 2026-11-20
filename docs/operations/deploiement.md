# Déploiement sur Vercel (site), Render (API) et Neon (base)

Tout ce qui se configure dans le dépôt est prêt : `render.yaml` (API),
`frontend/next.config.ts` (relais `/api`, en-têtes de sécurité). Restent les comptes et les
clés, que **toi seul** saisis dans chaque service. Aucune clé ne va dans le dépôt.

## Comment ça s'articule

```
Navigateur ──► soon-trade.vercel.app ──(/api/*)──► soontrade-api.onrender.com ──► PostgreSQL Neon
                                                                            └──► Stockage R2 ou S3
```

Le navigateur ne parle **qu'au site Vercel** : Vercel relaie `/api/*` vers Render. Sans ce
relais, le site (`vercel.app`) et l'API (`onrender.com`) seraient deux sites différents, et
les navigateurs n'enverraient pas le cookie de session à l'API : la connexion ne tiendrait
pas. Avec un nom de domaine (ex. `app.soontrade.com` et `api.soontrade.com`), le relais
reste valable.

## Coût indicatif

**Tout est gratuit pour démarrer.**

- Render, plan `free` :
  - l'API se met en veille après 15 min sans visite ; le réveil prend 30 à 60 s (voir
    « Éviter la veille ») ;
  - pas d'onglet Shell ;
  - 0,1 processeur.

  Passer au plan `0.5c-512mb` (environ 7 $ par mois) quand l'usage le justifiera : on change
  `plan` dans `render.yaml`.
- Neon : gratuit pour démarrer (0,5 Go). La base se met en veille après 5 min sans activité
  et se réveille en une seconde environ à la requête suivante.
- Vercel Hobby : gratuit (Pro si usage commercial).
- Cloudflare R2 : gratuit jusqu'à 10 Go.
- Resend : gratuit jusqu'à 3 000 e-mails par mois.

## Étape 0 — Base PostgreSQL sur Neon

1. Crée un compte sur neon.tech, puis un projet :
   - nom : `soontrade` ;
   - région : **AWS Europe Central 1 (Frankfurt)**, la même que l'API ;
   - PostgreSQL 17 ou plus récent.
2. Ouvre **Connect**, choisis la branche `main` et la base `neondb` (ou crée `soontrade`).
3. Désactive **Connection pooling** pour obtenir l'adresse **directe** : l'hôte ne doit
   pas contenir `-pooler`.
4. Copie l'adresse. Elle a la forme
   `postgresql://utilisateur:motdepasse@ep-xxx.eu-central-1.aws.neon.tech/neondb?sslmode=require`.
   Garde-la pour l'étape 3 : c'est un secret, ne la colle nulle part ailleurs.

Le préfixe `postgresql://` est converti automatiquement pour le pilote de l'API. Les
tables sont créées par les migrations au premier déploiement.

## Étape 1 — Stockage des documents (Cloudflare R2, le plus simple)

1. Crée un compte Cloudflare, puis ouvre **R2** et crée un bucket `soontrade-documents`
   (accès public : **désactivé**).
2. Va dans **R2 → Gérer les jetons d'API** et crée un jeton :
   - permission « Lecture et écriture d'objets » ;
   - limité à ce bucket.
3. Note quatre valeurs :
   - l'ID de clé d'accès ;
   - la clé secrète ;
   - le point de terminaison : `https://<id-compte>.r2.cloudflarestorage.com` ;
   - le nom du bucket.

(Avec AWS S3 à la place : bucket privé en `eu-west-3`, utilisateur IAM limité à ce bucket,
et point de terminaison laissé vide.)

## Étape 2 — Site sur Vercel

1. Va sur vercel.com, choisis **Add New → Project**, puis importe le dépôt GitHub
   `Elvis-Houssou/Soon-Trade`.
2. Réglages du projet :
   - **Root Directory** : `frontend` (Vercel installe tout de même depuis la racine du
     monorepo) ;
   - **Framework** : Next.js (détecté).
3. Variables d'environnement (Production) :

   | Nom | Valeur |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | `/api` |
   | `API_PROXY_TARGET` | `https://soontrade-api.onrender.com` (adresse de l'étape 3) |
   | `ENABLE_EXPERIMENTAL_COREPACK` | `1` (pour utiliser le pnpm 12 épinglé du projet) |

4. Lance **Deploy**, puis note l'adresse du site (ex. `https://soon-trade.vercel.app`).
   Tant que l'API n'est pas en ligne, seules les pages publiques fonctionnent : c'est
   normal.

## Étape 3 — API et base sur Render

1. Va sur render.com, choisis **New → Blueprint**, puis sélectionne le dépôt. Render lit
   `render.yaml` et propose le service `soontrade-api`.
2. Render demande les valeurs marquées `sync: false` :

   | Nom | Valeur |
   |---|---|
   | `DATABASE_URL` | l'adresse Neon **directe** de l'étape 0 |
   | `FRONTEND_URL` | `https://soon-trade.vercel.app` (adresse de l'étape 2) |
   | `CORS_ORIGINS` | `["https://soon-trade.vercel.app"]` |
   | `RESEND_API_KEY` | ta clé Resend (de préférence une nouvelle, propre à la production) |
   | `EMAIL_FROM` | `SupportSoonTrade <onboarding@resend.dev>` tant qu'aucun domaine n'est vérifié |
   | `S3_ENDPOINT_URL` | `https://<id-compte>.r2.cloudflarestorage.com` (vide pour AWS) |
   | `S3_REGION` | `auto` pour R2 (`eu-west-3` pour AWS) |
   | `S3_BUCKET` | `soontrade-documents` |
   | `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | les valeurs de l'étape 1 |

3. Valide. Render construit l'API ; au démarrage, elle applique les migrations sur Neon, puis
   accepte le trafic. Le premier démarrage prend une à deux minutes.
4. Vérifie que `https://soontrade-api.onrender.com/health/ready` répond
   `{"status":"ok","database":"up"}`.

**Si l'API refuse de démarrer**, ses journaux affichent « Configuration refusée : … » avec
la liste des réglages à corriger :
- une adresse en http au lieu de https ;
- une clé manquante ;
- les clés S3 de l'émulateur local.

Ce garde-fou est volontaire.

Si l'adresse Render n'est pas `soontrade-api.onrender.com`, corrige `API_PROXY_TARGET` sur
Vercel et redéploie le site.

## Étape 4 — Premier administrateur

Les comptes de démonstration n'existent pas en production : `db:seed` y est refusé. Le plan
gratuit de Render n'a pas d'onglet Shell : la commande se lance **depuis ton ordinateur**,
directement contre la base Neon, une fois l'API démarrée au moins une fois (les tables
existent alors).

Dans PowerShell, depuis le dossier du projet :

```powershell
cd backend
$env:DATABASE_URL = "COLLE-ICI-L-ADRESSE-NEON-DIRECTE"
$env:FRONTEND_URL = "https://soon-trade.vercel.app"
python -m uv run python -m app.cli invite-admin ton-adresse@exemple.com
Remove-Item Env:DATABASE_URL, Env:FRONTEND_URL
```

1. La commande affiche le lien d'invitation, et l'e-mail part si Resend l'accepte. Sans
   domaine vérifié, Resend n'envoie qu'à l'adresse de ton compte Resend : invite cette
   adresse-là.
2. La dernière ligne efface l'adresse de la base de la session PowerShell : rien n'est
   écrit dans un fichier.
3. Ouvre le lien, choisis ton mot de passe : tu es administrateur. Invite ensuite l'équipe
   depuis **Utilisateurs et permissions**.

## Éviter la veille (plan gratuit)

Après 15 min sans visite, Render endort l'API. La première page suivante attend son réveil
(30 à 60 s) et peut afficher une erreur : il suffit alors de recharger.

Pour l'éviter, une sonde gratuite (UptimeRobot, Better Stack…) peut appeler
`https://soontrade-api.onrender.com/health` toutes les 10 minutes. Elle sert en même temps
d'alerte de disponibilité. Les 750 heures gratuites mensuelles de Render couvrent un service
allumé en continu.

## Étape 5 — Vérifications

1. Ouvre le site, connecte-toi, et contrôle que la session tient d'une page à l'autre.
2. Dépose un document (Organisation → Documents), puis rouvre-le : cela vérifie le
   stockage.
3. Crée un acheteur et un fournisseur depuis l'espace interne, puis fais un parcours
   complet : demande, sollicitation, offre, proposition, commande.

## Mises à jour

`autoDeploy` est désactivé sur Render. Une fois `main` poussée et la CI verte :
- **Render** : **Manual Deploy → Deploy latest commit** ; les migrations passent au démarrage,
  avant d'accepter le trafic.
- **Vercel** : déploie seul à chaque push ; on peut le désactiver dans **Settings → Git**.

**Retour arrière** :
- Render : **Rollback** vers la version précédente.
- Vercel : **Promote** d'un déploiement antérieur.
- Si une migration a modifié le schéma, restaure d'abord la base à l'instant voulu
  (**Neon → Backup & Restore**, restauration à un instant donné). Voir `sauvegardes.md`.

## Plus tard : nom de domaine

1. Achète le domaine, puis pointe `app.` vers Vercel et `api.` vers Render.
2. Vérifie le domaine dans Resend et mets
   `EMAIL_FROM=SupportSoonTrade <support@ton-domaine>`.
3. Remplace l'adresse `vercel.app` par la nouvelle dans `FRONTEND_URL` et `CORS_ORIGINS`
   (Render), puis l'adresse Render dans `API_PROXY_TARGET` (Vercel).

## Limites connues

- Les documents passent par le relais Vercel. Si un dépôt proche de la limite de 10 Mo
  échoue en production, abaisser `DOCUMENT_MAX_BYTES` ou faire déposer les fichiers
  directement sur R2 par lien signé : **À VÉRIFIER** au premier essai réel.
- Les e-mails ne partent qu'à l'adresse du compte Resend tant que le domaine n'est pas
  vérifié.
