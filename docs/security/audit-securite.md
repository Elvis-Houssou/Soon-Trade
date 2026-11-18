# Audit de sécurité — Phase 12

> Revue interne menée le 18/11/2026 sur le code. **Ne remplace pas** un test d'intrusion
> par un tiers avant l'ouverture au public (recommandé).

## Vérifié et couvert par des tests automatiques

| Point | Mesure | Preuve |
|---|---|---|
| Accès anonyme | 111 routes protégées répondent 401 sans session ; 8 routes publiques listées | `tests/test_hardening.py` (parcourt toutes les routes) |
| Cloisonnement | Une ressource d'une autre organisation répond 404 ; tests croisés acheteur ↔ acheteur, fournisseur ↔ fournisseur, acheteur ↔ fournisseur | tests de chaque module |
| Rôles | Chaque action vérifie une permission ; auditeur en lecture seule | `permissions.py`, tests de chaque module |
| Données confidentielles | L'acheteur ne voit ni fournisseur, ni prix d'achat, ni marge ; le fournisseur ni l'acheteur ni le prix de vente ; notes internes jamais renvoyées | tests de propositions, commandes, messagerie |
| Sessions | Cookie `HttpOnly`, `SameSite=Lax`, `Secure` hors local ; verrouillage après 5 échecs | `docs/security/authentification.md`, tests d'identité |
| Fichiers | Type vérifié sur les premiers octets, taille limitée, bucket privé, liens signés 120 s | tests de documents |
| Exports | Réservés à certains rôles, tracés, cellules protégées contre l'injection de formules | `tests/test_reporting.py` |
| En-têtes HTTP | API : `nosniff`, `DENY`, `no-referrer`, `no-store`, CSP `default-src 'none'`, HSTS hors local ; site : CSP, `DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy` | `tests/test_hardening.py`, vérifié sur le build de production |
| Configuration | L'API refuse de démarrer avec des réglages dangereux en préproduction ou production | `tests/test_hardening.py` |
| Journaux | Jamais de mot de passe, jeton ou contenu de message ; modèle de route au lieu de l'adresse réelle | `hardening.py`, revue |
| Secrets | Aucun `.env` ni motif de secret dans les fichiers du dépôt ; recherche gitleaks en CI | revue, `.github/workflows/ci.yml` |
| Dépendances | Aucune vulnérabilité connue (pnpm audit, pip-audit) ; contrôle en CI | 18/11/2026 |

## Points ouverts

- **CSP avec `'unsafe-inline'`** pour les scripts : choix du guide Next pour garder les
  pages statiques. Passer aux nonces si une exigence de conformité l'impose.
- **Limitation de débit** : seule la connexion est protégée (verrouillage). Ajouter une
  limite globale par adresse (Cloudflare ou Redis) avant l'ouverture au public.
- **Double authentification** pour les comptes internes : recommandée, non faite.
- **Détection de coordonnées** dans les messages (contournement de l'intermédiation) :
  non faite, voir `docs/business-rules/communication.md`.
- **Test d'intrusion externe** : à commander avant la production.
