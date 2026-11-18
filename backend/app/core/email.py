import html
import logging
import re

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_LINK = re.compile(r"https?://[^\s<]+")


def to_html(text: str) -> str:
    """Version HTML sobre du texte : paragraphes, liens cliquables, bandeau de marque."""
    paragraphs = []
    for block in text.split("\n\n"):
        escaped = html.escape(block).replace("\n", "<br>")
        linked = _LINK.sub(
            lambda m: f'<a href="{m.group(0)}" style="color:#6c3bff">{m.group(0)}</a>', escaped
        )
        paragraphs.append(f'<p style="margin:0 0 16px;line-height:1.5">{linked}</p>')
    return (
        '<div style="font-family:Arial,sans-serif;color:#0f172a;max-width:560px;margin:0 auto">'
        '<div style="background:linear-gradient(105deg,#2a1470,#5a2be6 55%,#8b66ff);color:#fff;'
        'padding:18px 24px;border-radius:14px 14px 0 0;font-weight:700;letter-spacing:.04em">SOON TRADE</div>'
        f'<div style="border:1px solid #e2e8f0;border-top:0;border-radius:0 0 14px 14px;padding:24px">'
        f"{''.join(paragraphs)}</div></div>"
    )


def send_email(to: str, subject: str, text: str) -> None:
    """Point d'envoi unique des e-mails transactionnels (README §17), en texte et en HTML."""
    settings = get_settings()
    if not settings.resend_api_key:
        if settings.environment in ("staging", "production"):
            raise RuntimeError("RESEND_API_KEY manquante : aucun e-mail ne peut partir.")
        logger.info("email_not_sent_no_provider", extra={"to": to, "subject": subject, "text": text})
        return
    response = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        json={
            "from": settings.email_from,
            "to": [to],
            "subject": subject,
            "text": text,
            "html": to_html(text),
        },
        timeout=10,
    )
    response.raise_for_status()
