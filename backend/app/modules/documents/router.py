import secrets
import uuid
from datetime import datetime
from pathlib import PurePath
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Form, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import storage
from app.core.config import get_settings
from app.core.errors import AppError, NotFound
from app.modules.audit.models import record
from app.modules.documents.models import Document
from app.modules.identity.deps import CurrentPrincipal, DbSession, Principal, client_ip, require_permission
from app.modules.identity.permissions import DOCUMENT_READ_ALL, DOCUMENT_REVIEW, DOCUMENT_UPLOAD
from app.modules.organizations.service import get_client_organization

router = APIRouter(tags=["documents"])

DocumentType = Literal[
    "company_registration", "tax_certificate", "id_document", "offer_attachment", "delivery_proof", "other"
]

# Type déclaré -> signature attendue au début du fichier. Le type annoncé par le
# navigateur ne suffit pas : on vérifie aussi les premiers octets.
ALLOWED_TYPES = {
    "application/pdf": b"%PDF-",
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
}


class DocumentOut(BaseModel):
    """Vue de l'organisation : ni clé de stockage, ni note interne."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    doc_type: str
    filename: str
    size_bytes: int
    status: str


class InternalDocumentOut(DocumentOut):
    review_note: str | None


class ReviewIn(BaseModel):
    status: Literal["approved", "rejected"]
    note: Annotated[str, Field(max_length=1000)] | None = None


class DownloadOut(BaseModel):
    url: str
    expires_in: int


def _documents_of(session: Session, organization_id: uuid.UUID) -> list[Document]:
    return list(
        session.scalars(
            select(Document)
            .where(Document.organization_id == organization_id)
            .order_by(Document.created_at.desc())
        )
    )


@router.get("/documents")
def list_my_documents(session: DbSession, principal: CurrentPrincipal) -> list[DocumentOut]:
    return [DocumentOut.model_validate(d) for d in _documents_of(session, principal.organization.id)]


async def save_upload(
    session: Session, principal: Principal, doc_type: str, file: UploadFile, *, ip: str | None
) -> Document:
    """Contrôle et stocke un fichier pour l'organisation de `principal`. Ne valide pas la transaction."""
    max_bytes = get_settings().document_max_bytes
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise AppError("Le fichier dépasse la taille maximale autorisée.")
    signature = ALLOWED_TYPES.get(file.content_type or "")
    if signature is None or not data.startswith(signature):
        raise AppError("Format non accepté. Envoyez un PDF, un JPEG ou un PNG.")

    document = Document(
        organization_id=principal.organization.id,  # jamais lu dans la requête
        uploaded_by_id=principal.user.id,
        doc_type=doc_type,
        # Seul le nom de fichier est gardé, sans chemin ; la clé de stockage, elle, est aléatoire.
        filename=PurePath((file.filename or "document").replace("\\", "/")).name[:255],
        content_type=file.content_type or "",
        size_bytes=len(data),
        storage_key=secrets.token_urlsafe(32),
    )
    storage.put_object(document.storage_key, data, document.content_type)
    session.add(document)
    record(session, "document.uploaded", document.filename, actor_id=principal.user.id, ip=ip)
    session.flush()
    return document


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    session: DbSession,
    principal: Annotated[Principal, Depends(require_permission(DOCUMENT_UPLOAD))],
    doc_type: Annotated[DocumentType, Form()],
    file: UploadFile,
) -> DocumentOut:
    document = await save_upload(session, principal, doc_type, file, ip=client_ip(request))
    session.commit()
    return DocumentOut.model_validate(document)


@router.get("/documents/{document_id}/url")
def download_url(
    document_id: uuid.UUID, request: Request, session: DbSession, principal: CurrentPrincipal
) -> DownloadOut:
    document = session.get(Document, document_id)
    own = document is not None and document.organization_id == principal.organization.id
    if document is None or not (own or DOCUMENT_READ_ALL in principal.permissions):
        # Même réponse que le document existe ou non : ne rien révéler aux autres organisations.
        raise NotFound("Document introuvable.")
    record(
        session, "document.download_link", str(document.id), actor_id=principal.user.id, ip=client_ip(request)
    )
    session.commit()
    return DownloadOut(
        url=storage.presigned_download_url(document.storage_key, document.filename),
        expires_in=get_settings().document_url_seconds,
    )


@router.get("/organizations/{organization_id}/documents")
def list_organization_documents(
    organization_id: uuid.UUID,
    session: DbSession,
    _: Annotated[Principal, Depends(require_permission(DOCUMENT_READ_ALL))],
) -> list[InternalDocumentOut]:
    organization = get_client_organization(session, organization_id)
    return [InternalDocumentOut.model_validate(d) for d in _documents_of(session, organization.id)]


@router.post("/documents/{document_id}/review")
def review_document(
    document_id: uuid.UUID,
    body: ReviewIn,
    request: Request,
    session: DbSession,
    principal: Annotated[Principal, Depends(require_permission(DOCUMENT_REVIEW))],
) -> InternalDocumentOut:
    document = session.get(Document, document_id)
    if not document:
        raise NotFound("Document introuvable.")
    document.status = body.status
    document.review_note = (body.note or "").strip() or None
    record(
        session,
        "document.reviewed",
        str(document.id),
        actor_id=principal.user.id,
        ip=client_ip(request),
        status=body.status,
    )
    session.commit()
    return InternalDocumentOut.model_validate(document)
