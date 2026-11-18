"""Textes des e-mails transactionnels, en français, anglais et allemand (README §17).

Règle commune : jamais de prix, de nom de l'autre partie ni de contenu confidentiel ; un
e-mail annonce un événement et renvoie vers l'espace, où l'information est cloisonnée.

shortcut: gabarits en Python plutôt qu'en React Email, pour rester dans l'API ; à
reconsidérer si le service marketing doit éditer les e-mails lui-même.
"""

from datetime import date
from typing import Any

LOCALES = ("fr", "en", "de")

# type -> langue -> (objet, corps). Les champs entre accolades viennent de `render`.
TEMPLATES: dict[str, dict[str, tuple[str, str]]] = {
    "invitation": {
        "fr": (
            "Votre invitation SOON TRADE",
            "Vous êtes invité à rejoindre {organization} sur SOON TRADE.\n\nCréez votre compte : {link}\n\n"
            "Ce lien est personnel et expire dans {days} jours.",
        ),
        "en": (
            "Your SOON TRADE invitation",
            "You are invited to join {organization} on SOON TRADE.\n\nCreate your account: {link}\n\n"
            "This link is personal and expires in {days} days.",
        ),
        "de": (
            "Ihre Einladung zu SOON TRADE",
            "Sie sind eingeladen, {organization} auf SOON TRADE beizutreten.\n\nKonto erstellen: {link}\n\n"
            "Dieser Link ist persönlich und läuft in {days} Tagen ab.",
        ),
    },
    "password_reset": {
        "fr": (
            "Réinitialisation de votre mot de passe SOON TRADE",
            "Choisissez un nouveau mot de passe : {link}\n\nCe lien expire dans {minutes} minutes. "
            "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.",
        ),
        "en": (
            "Reset your SOON TRADE password",
            "Choose a new password: {link}\n\nThis link expires in {minutes} minutes. "
            "If you did not ask for this, ignore this message.",
        ),
        "de": (
            "Ihr SOON TRADE Passwort zurücksetzen",
            "Wählen Sie ein neues Passwort: {link}\n\nDieser Link läuft in {minutes} Minuten ab. "
            "Wenn Sie das nicht angefordert haben, ignorieren Sie diese Nachricht.",
        ),
    },
    "solicitation_received": {
        "fr": (
            "Nouvelle sollicitation SOON TRADE {reference}",
            "SOON TRADE vous adresse une sollicitation ({reference}).\n\nRépondez avant le {deadline}.",
        ),
        "en": (
            "New SOON TRADE solicitation {reference}",
            "SOON TRADE has sent you a solicitation ({reference}).\n\nPlease reply by {deadline}.",
        ),
        "de": (
            "Neue Anfrage von SOON TRADE {reference}",
            "SOON TRADE hat Ihnen eine Anfrage gesendet ({reference}).\n\n"
            "Bitte antworten Sie bis {deadline}.",
        ),
    },
    "proposal_received": {
        "fr": (
            "Proposition SOON TRADE {reference}",
            "SOON TRADE vous adresse une proposition ({reference}) pour votre demande {request}.\n\n"
            "Consultez-la avant le {valid_until}.",
        ),
        "en": (
            "SOON TRADE proposal {reference}",
            "SOON TRADE has sent you a proposal ({reference}) for your request {request}.\n\n"
            "Please review it by {valid_until}.",
        ),
        "de": (
            "Angebot von SOON TRADE {reference}",
            "SOON TRADE hat Ihnen ein Angebot ({reference}) zu Ihrer Anfrage {request} gesendet.\n\n"
            "Bitte prüfen Sie es bis {valid_until}.",
        ),
    },
    "order_confirmed": {
        "fr": ("Commande SOON TRADE {reference} confirmée", "Votre commande {reference} est confirmée."),
        "en": ("SOON TRADE order {reference} confirmed", "Your order {reference} is confirmed."),
        "de": ("Bestellung {reference} bestätigt", "Ihre Bestellung {reference} ist bestätigt."),
    },
    "supplier_order_received": {
        "fr": (
            "Bon de commande SOON TRADE {reference}",
            "SOON TRADE vous adresse le bon de commande {reference}.",
        ),
        "en": (
            "SOON TRADE purchase order {reference}",
            "SOON TRADE has sent you purchase order {reference}.",
        ),
        "de": (
            "Bestellung von SOON TRADE {reference}",
            "SOON TRADE hat Ihnen die Bestellung {reference} gesendet.",
        ),
    },
    "delivery_shipped": {
        "fr": (
            "Livraison {reference} en route",
            "La livraison {reference} de votre commande {order} est en route.",
        ),
        "en": (
            "Delivery {reference} on its way",
            "Delivery {reference} for your order {order} is on its way.",
        ),
        "de": (
            "Lieferung {reference} unterwegs",
            "Die Lieferung {reference} Ihrer Bestellung {order} ist unterwegs.",
        ),
    },
    "delivery_delivered": {
        "fr": (
            "Livraison {reference} arrivée",
            "La livraison {reference} de votre commande {order} est arrivée. Confirmez la réception "
            "ou ouvrez une réclamation depuis votre espace.",
        ),
        "en": (
            "Delivery {reference} arrived",
            "Delivery {reference} for your order {order} has arrived. Confirm receipt or open a claim "
            "from your account.",
        ),
        "de": (
            "Lieferung {reference} angekommen",
            "Die Lieferung {reference} Ihrer Bestellung {order} ist angekommen. Bestätigen Sie den Empfang "
            "oder eröffnen Sie eine Reklamation in Ihrem Bereich.",
        ),
    },
    "claim_answered": {
        "fr": (
            "Réponse à votre réclamation {reference}",
            "SOON TRADE a répondu à votre réclamation {reference}.",
        ),
        "en": ("Answer to your claim {reference}", "SOON TRADE has answered your claim {reference}."),
        "de": (
            "Antwort auf Ihre Reklamation {reference}",
            "SOON TRADE hat Ihre Reklamation {reference} beantwortet.",
        ),
    },
    "request_info_requested": {
        "fr": (
            "Précisions demandées sur votre demande {reference}",
            "SOON TRADE a besoin de précisions sur votre demande {reference}.",
        ),
        "en": (
            "More details needed on your request {reference}",
            "SOON TRADE needs more details on your request {reference}.",
        ),
        "de": (
            "Rückfrage zu Ihrer Anfrage {reference}",
            "SOON TRADE benötigt weitere Angaben zu Ihrer Anfrage {reference}.",
        ),
    },
    "request_rejected": {
        "fr": (
            "Votre demande {reference}",
            "Votre demande {reference} n'a pas pu être retenue. Le motif est dans votre espace.",
        ),
        "en": (
            "Your request {reference}",
            "Your request {reference} could not be accepted. The reason is in your account.",
        ),
        "de": (
            "Ihre Anfrage {reference}",
            "Ihre Anfrage {reference} konnte nicht angenommen werden. Den Grund finden Sie in Ihrem Bereich.",
        ),
    },
    "message_received": {
        "fr": ("Nouveau message de SOON TRADE", "SOON TRADE vous a écrit dans la conversation {reference}."),
        "en": ("New message from SOON TRADE", "SOON TRADE has written to you in conversation {reference}."),
        "de": (
            "Neue Nachricht von SOON TRADE",
            "SOON TRADE hat Ihnen in der Unterhaltung {reference} geschrieben.",
        ),
    },
}

FOOTER = {
    "fr": "Depuis votre espace : {link}",
    "en": "From your account: {link}",
    "de": "In Ihrem Bereich: {link}",
}


def format_date(value: date, locale: str) -> str:
    return value.strftime({"fr": "%d/%m/%Y", "de": "%d.%m.%Y"}.get(locale, "%Y-%m-%d"))


def render(kind: str, locale: str, *, link: str | None = None, **params: Any) -> tuple[str, str]:
    """Objet et corps dans la langue de l'utilisateur (français par défaut)."""
    locale = locale if locale in LOCALES else "fr"
    values = {k: format_date(v, locale) if isinstance(v, date) else v for k, v in params.items()}
    subject, body = TEMPLATES[kind][locale]
    text = body.format(link=link, **values)
    if link and "{link}" not in body:
        text += "\n\n" + FOOTER[locale].format(link=link)
    return subject.format(**values), text
