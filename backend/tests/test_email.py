from app.core import email
from app.core.config import Settings


def test_brevo_payload(monkeypatch):
    calls = []

    class _Ok:
        def raise_for_status(self):
            pass

    monkeypatch.setattr(
        email, "get_settings",
        lambda: Settings(brevo_api_key="k", email_from="SupportSoonTrade <moi@gmail.com>"),
    )
    monkeypatch.setattr(email.httpx, "post", lambda url, **kw: calls.append((url, kw)) or _Ok())
    email.send_email("client@exemple.com", "Sujet", "Bonjour")
    url, kw = calls[0]
    assert url == "https://api.brevo.com/v3/smtp/email"
    assert kw["headers"] == {"api-key": "k"}
    assert kw["json"]["sender"] == {"name": "SupportSoonTrade", "email": "moi@gmail.com"}
    assert kw["json"]["to"] == [{"email": "client@exemple.com"}]
