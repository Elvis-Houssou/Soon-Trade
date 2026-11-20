# Politique de données personnelles — projet

> **PROJET À FAIRE VALIDER PAR UN JURISTE** en Côte d'Ivoire (loi n° 2013-450 relative à
> la protection des données à caractère personnel, autorité : ARTCI) et, pour les
> utilisateurs européens, au regard du RGPD. Ce document décrit ce que fait réellement la
> plateforme ; il ne constitue pas un avis juridique.

## Responsable du traitement

SOON TRADE — coordonnées, représentant et éventuel délégué à la protection des données :
**à compléter**.

## Données traitées

| Catégorie | Exemples | Finalité | Base proposée |
|---|---|---|---|
| Comptes | nom, adresse e-mail, rôle, langue, mot de passe (empreinte Argon2 uniquement) | Accès à la plateforme | Contrat |
| Organisations | raison sociale, adresse, téléphone, RCCM, numéro fiscal | Vérification et relation commerciale | Contrat, obligation légale |
| Documents | pièces administratives, preuves de livraison, pièces d'offres | Vérification, exécution des commandes | Contrat |
| Activité | demandes, offres, propositions, commandes, réclamations, messages | Exécution des transactions | Contrat |
| Sécurité | journal d'audit (auteur, action, date, adresse IP), sessions | Sécurité, preuve | Intérêt légitime |

Aucune donnée n'est vendue ni utilisée pour de la publicité. Aucun cookie de mesure
d'audience : seuls un cookie de session (`HttpOnly`), un cookie de langue et le thème
mémorisé dans le navigateur (stockage local) sont utilisés.

## Destinataires et sous-traitants

| Sous-traitant | Rôle | Localisation (À VÉRIFIER selon l'offre retenue) |
|---|---|---|
| Render | Base de données | UE (Francfort) |
| Cloudflare R2 (ou AWS S3) | Stockage des documents | UE (juridiction UE à activer sur R2 ; eu-west-3 sur AWS) |
| Render | Hébergement de l'API | UE (Francfort) |
| Vercel | Hébergement du site | Réseau mondial |
| Resend | Envoi des e-mails | États-Unis |
| Cloudflare | DNS, protection | Réseau mondial |

Les transferts hors de Côte d'Ivoire ou de l'UE sont **à encadrer** (clauses
contractuelles, autorisation ARTCI le cas échéant).

Cloisonnement : un acheteur ne voit jamais l'identité d'un fournisseur, et inversement ;
seule l'équipe SOON TRADE fait l'intermédiation.

## Durées de conservation proposées (À VALIDER)

| Donnée | Durée |
|---|---|
| Compte actif | Durée de la relation |
| Compte fermé | 3 ans après la dernière activité, puis anonymisation |
| Commandes, documents de transaction | 10 ans (obligations comptables, à confirmer) |
| Journal d'audit | 5 ans |
| Messages | 3 ans après la dernière activité de la conversation |
| Sauvegardes | Voir `docs/operations/sauvegardes.md` |

**Non encore développé** : suppression et anonymisation automatiques à l'échéance.

## Droits des personnes

Accès, rectification, opposition et suppression, dans les limites des obligations légales
de conservation. Demande à adresser à : **à compléter** ; réponse sous 30 jours.

**Non encore développé** : export des données d'un utilisateur et suppression de compte en
libre-service. En attendant, une demande se traite à la main par l'administrateur, et
l'action est tracée au journal d'audit.

## Sécurité

Chiffrement en transit (TLS) et au repos (base et bucket chiffrés par l'hébergeur),
cloisonnement par organisation testé automatiquement, permissions par rôle, journal
d'audit, sauvegardes testées. Détails : `docs/security/audit-securite.md`.
