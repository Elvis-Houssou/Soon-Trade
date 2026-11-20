from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Configuration lue depuis l'environnement, puis depuis `backend/.env`."""

    # Chemin absolu : le fichier est trouvé quel que soit le dossier de lancement.
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    environment: Literal["local", "test", "staging", "production"] = "local"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://soontrade:soontrade@127.0.0.1:5432/soontrade"
    cors_origins: list[str] = ["http://localhost:3000"]
    frontend_url: str = "http://localhost:3000"

    # Sans clé Resend, les e-mails sont écrits dans les logs (développement uniquement).
    resend_api_key: str | None = None
    # Brevo : envoie sans domaine, depuis une adresse simplement vérifiée (prioritaire sur Resend).
    brevo_api_key: str | None = None
    email_from: str = "SOON TRADE <no-reply@soontrade.com>"

    # Mot de passe commun des comptes de démonstration (`python -m app.seed`, local uniquement).
    seed_password: str | None = None

    # Stockage des documents : S3 en production, émulateur S3 de infra/compose.yaml en local.
    s3_endpoint_url: str | None = "http://127.0.0.1:9090"
    s3_bucket: str = "soon-trade-documents"
    s3_region: str = "eu-west-3"
    s3_access_key_id: str = "local"
    s3_secret_access_key: str = "local"  # noqa: S105 - valeur factice de l'émulateur local
    document_max_bytes: int = 10 * 1024 * 1024
    document_url_seconds: int = 120

    session_days: int = 7
    invitation_days: int = 7
    password_reset_minutes: int = 30
    login_max_failures: int = 5
    login_lockout_minutes: int = 15

    @field_validator("database_url")
    @classmethod
    def _psycopg_driver(cls, value: str) -> str:
        """Les hébergeurs donnent « postgres:// » ou « postgresql:// » ; le pilote installé est psycopg 3."""
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix) :]
        return value

    @property
    def secure_cookies(self) -> bool:
        return self.environment in ("staging", "production")

    @property
    def docs_enabled(self) -> bool:
        return self.environment != "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
