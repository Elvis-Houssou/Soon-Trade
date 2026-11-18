# Authentification — choix retenus (Phase 3)

Le README (§12) laissait le mécanisme à arrêter « lors de la conception ». Voici ce qui
est en place et pourquoi.

## Sessions opaques en base, pas de JWT

À la connexion, l'API tire un jeton aléatoire de 256 bits, n'en stocke que le condensat
SHA-256 et le pose dans un cookie `st_session` (`HttpOnly`, `SameSite=Lax`, `Secure` hors
développement). Chaque requête retrouve la session en base.

Pourquoi pas un JWT : une session en base se révoque immédiatement (déconnexion, mot de
passe changé, compte désactivé) sans liste noire ni rotation de jetons, et il n'y a
aucune clé de signature à protéger. Le coût est une lecture en base par requête,
négligeable à l'échelle visée. Le README autorise explicitement « sessions ou jetons ».

Le navigateur ne voit jamais le jeton : rien n'est stocké dans `localStorage`.

## Règles en vigueur

| Sujet | Règle |
|---|---|
| Mots de passe | Argon2id (pwdlib), 10 à 128 caractères |
| Durée de session | 7 jours, puis reconnexion |
| Tentatives de connexion | 5 échecs en 15 minutes verrouillent l'adresse |
| Réponse à un échec | Identique que le compte existe ou non |
| Invitation | Lien à usage unique, 7 jours, une seule active par adresse |
| Mot de passe oublié | Lien à usage unique, 30 minutes ; ferme toutes les sessions |
| Jetons d'invitation et de réinitialisation | Seul le condensat est stocké |
| Inscription publique | Aucune route n'existe |
| Requêtes inter-sites | CORS limité à l'origine du frontend, `SameSite=Lax`, corps JSON |

Ces durées et seuils sont des valeurs de départ réglables dans `backend/app/core/config.py`.

## Vérification de l'adresse e-mail

Il n'y a pas d'étape séparée : un compte ne naît qu'en ouvrant un lien reçu à cette
adresse, ce qui prouve qu'elle est joignable.

## Où se fait le contrôle d'accès

Dans l'API, par les dépendances de `backend/app/modules/identity/deps.py` :
`current_principal` (session valide), `require_permission` (rôle) et `require_space`
(type d'organisation). L'organisation de l'utilisateur est toujours lue en base, jamais
dans la requête. Côté interface, la redirection vers la connexion ou vers le bon espace
n'est qu'un confort.

## Premier administrateur

```bash
cd backend
uv run python -m app.cli invite-admin prenom@exemple.com
```

La commande crée l'organisation interne si besoin et émet une invitation. Aucun mot de
passe ne transite par le terminal.

## Limites connues

- Sans clé Resend, les e-mails sont écrits dans les logs de l'API (développement
  uniquement ; l'API refuse de démarrer un envoi sans clé en préproduction et production).
- Les e-mails sont en texte brut et en français.
- L'adresse IP journalisée est celle de la connexion directe ; derrière Cloudflare ou
  Render il faudra lire l'en-tête du proxy de confiance.
- Pas encore de double authentification.
