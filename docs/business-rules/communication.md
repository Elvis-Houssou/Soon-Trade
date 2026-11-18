# Messagerie, notifications et CRM — choix de la Phase 10

> **À VALIDER.** Ces règles sont des choix de mise en œuvre ; elles attendent une décision
> métier.

## Messagerie

- Une conversation relie **une seule** organisation cliente (acheteur ou fournisseur) à
  l'équipe SOON TRADE. Il n'existe donc aucun canal direct entre un acheteur et un
  fournisseur (README §5).
- Le client ouvre une conversation ou répond ; l'équipe peut aussi ouvrir une conversation
  avec n'importe quel client.
- Côté client, les messages de l'équipe sont signés « SOON TRADE », jamais d'un nom.
- Les collaborateurs peuvent laisser des **notes internes** dans un fil : elles ne sont
  jamais renvoyées au client.
- Une référence libre (demande, commande…) peut être associée à un fil, comme simple repère.
- Clore un fil n'empêche pas le client de répondre : un nouveau message le rouvre.
- Lecture : tout collaborateur ; écriture : tout collaborateur sauf l'auditeur.
- Pas de pièce jointe dans les messages pour l'instant.
- **Non traité** : détection automatique de coordonnées (téléphone, e-mail) dans un message
  envoyé à un client. À décider.

## Notifications

| Événement | Qui est prévenu | E-mail |
|---|---|---|
| Sollicitation envoyée | membres du fournisseur | oui |
| Offre reçue | équipe sourcing | non |
| Proposition envoyée | membres de l'acheteur | oui |
| Décision de l'acheteur sur une proposition | équipe commerciale | non |
| Commande confirmée | acheteur ; chaque fournisseur pour son bon | oui |
| Livraison partie, arrivée | membres de l'acheteur | oui |
| Réclamation ouverte | logistique et support | non |
| Réclamation résolue ou rejetée | membres de l'acheteur | oui |
| Précisions demandées, demande rejetée | membres de l'acheteur | oui |
| Message de l'équipe | membres du client | oui |
| Message d'un client | collaborateurs qui peuvent répondre | non |

- Les notifications internes restent dans l'application, pour ne pas noyer l'équipe
  d'e-mails.
- La personne à l'origine d'une action n'est pas prévenue de sa propre action.
- La cloche se met à jour toutes les 30 secondes.

## E-mails

- Ils sont envoyés en texte et en HTML, dans la langue de chaque destinataire : la dernière
  qu'il a affichée dans l'application (français par défaut).
- Une invitation part dans la langue de la personne qui invite.
- Un e-mail n'annonce qu'un événement, avec une référence et un lien vers l'espace : jamais
  de prix, de nom de l'autre partie ni le contenu d'un message (README §17).

## CRM

- La fiche d'un client rassemble son historique, reconstitué à partir des données :
  - acheteur : demandes, propositions, commandes, réclamations ;
  - fournisseur : sollicitations, offres, bons de commande ;
  - pour tous : conversations et notes de suivi.
- Les notes de suivi sont internes et ne se modifient pas.
- Lecture : tout collaborateur ; ajout de notes : tout collaborateur sauf l'auditeur.
