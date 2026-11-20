from typing import Literal

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, EmailStr, Field

from app.modules.contact import service
from app.modules.contact.models import ContactRequest
from app.modules.identity.deps import DbSession, client_ip

router = APIRouter(tags=["contact"])


class ContactIn(BaseModel):
    profile: Literal["buyer", "supplier", "other"]
    name: str = Field(min_length=2, max_length=120)
    company: str | None = Field(default=None, max_length=160)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    message: str = Field(min_length=10, max_length=3000)
    locale: Literal["fr", "en", "de"] = "fr"
    # Piège à robots : champ caché du formulaire, qu'un humain laisse vide.
    website: str | None = None


@router.post("/contact", status_code=status.HTTP_204_NO_CONTENT)
def contact(body: ContactIn, request: Request, session: DbSession) -> None:
    if body.website:
        return  # robot : on répond comme si tout allait bien, sans rien enregistrer
    service.submit(
        session,
        ContactRequest(
            profile=body.profile,
            name=body.name.strip(),
            company=(body.company or "").strip() or None,
            email=str(body.email),
            phone=(body.phone or "").strip() or None,
            message=body.message.strip(),
            locale=body.locale,
            ip=client_ip(request),
        ),
    )
