import pytest
from sqlalchemy import select

from app.core import storage
from app.modules.documents.models import Document

PDF = b"%PDF-1.7 contenu de test"


@pytest.fixture
def bucket(monkeypatch):
    """Remplace le bucket S3 par un dictionnaire en mémoire."""
    objects: dict[str, bytes] = {}
    monkeypatch.setattr(storage, "put_object", lambda key, data, content_type: objects.__setitem__(key, data))
    monkeypatch.setattr(
        storage, "presigned_download_url", lambda key, filename: f"https://s3.test/{key}?signature"
    )
    return objects


def upload(
    client, *, name="rccm.pdf", data=PDF, content_type="application/pdf", doc_type="company_registration"
):
    return client.post("/documents", data={"doc_type": doc_type}, files={"file": (name, data, content_type)})


def test_supplier_uploads_a_document_stored_under_an_unpredictable_key(world, login, bucket, db):
    response = upload(login("member@f.example.com"))
    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "rccm.pdf" and body["status"] == "pending" and body["size_bytes"] == len(PDF)
    # Ni la clé de stockage ni la note interne ne sortent vers l'organisation.
    assert "storage_key" not in body and "review_note" not in body

    document = db.scalar(select(Document))
    assert document.organization_id == world["supplier"].id
    assert "rccm" not in document.storage_key and bucket[document.storage_key] == PDF


@pytest.mark.parametrize(
    ("name", "data", "content_type"),
    [
        ("virus.exe", b"MZ\x90\x00", "application/octet-stream"),
        ("faux.pdf", b"MZ\x90\x00 pas un pdf", "application/pdf"),  # type annoncé mensonger
        ("page.html", b"<script>alert(1)</script>", "text/html"),
        ("image.png", PDF, "image/png"),
    ],
)
def test_only_real_pdf_and_images_are_accepted(world, login, bucket, name, data, content_type):
    response = upload(login("owner@f.example.com"), name=name, data=data, content_type=content_type)
    assert response.status_code == 400
    assert bucket == {}


def test_oversized_files_are_refused(world, login, bucket, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "document_max_bytes", 100)
    response = upload(login("owner@f.example.com"), data=b"%PDF-" + b"x" * 200)
    assert response.status_code == 400 and bucket == {}


def test_path_in_filename_is_dropped(world, login, bucket):
    response = upload(login("owner@f.example.com"), name="..\\..\\secrets/../rccm.pdf")
    assert response.json()["filename"] == "rccm.pdf"


def test_documents_are_invisible_to_other_organizations(world, login, bucket):
    document_id = upload(login("owner@f.example.com")).json()["id"]

    for other in ("owner@g.example.com", "owner@a.example.com"):  # fournisseur concurrent, acheteur
        client = login(other)
        assert client.get("/documents").json() == []
        assert client.get(f"/documents/{document_id}/url").status_code == 404
        assert client.get(f"/organizations/{world['supplier'].id}/documents").status_code == 403
        assert client.post(f"/documents/{document_id}/review", json={"status": "approved"}).status_code == 403

    owner = login("owner@f.example.com")
    assert [d["id"] for d in owner.get("/documents").json()] == [document_id]
    link = owner.get(f"/documents/{document_id}/url").json()
    assert link["url"].startswith("https://s3.test/") and link["expires_in"] <= 300


def test_internal_staff_cannot_upload_on_behalf_of_anyone(world, login, bucket):
    assert upload(login("admin@st.example.com")).status_code == 403


@pytest.mark.parametrize(
    ("email", "can_read", "can_review"),
    [
        ("admin@st.example.com", True, True),
        ("sourcing@st.example.com", True, True),
        ("sales@st.example.com", True, False),
        ("auditor@st.example.com", True, False),
    ],
)
def test_internal_reading_and_review_follow_the_role(world, login, bucket, email, can_read, can_review):
    document_id = upload(login("owner@f.example.com")).json()["id"]
    client = login(email)
    listing = client.get(f"/organizations/{world['supplier'].id}/documents")
    assert (listing.status_code == 200) is can_read
    assert (client.get(f"/documents/{document_id}/url").status_code == 200) is can_read
    review = client.post(f"/documents/{document_id}/review", json={"status": "rejected", "note": "Illisible"})
    assert (review.status_code == 200) is can_review
    if can_review:
        assert review.json()["review_note"] == "Illisible"
        mine = login("owner@f.example.com").get("/documents").json()[0]
        assert mine["status"] == "rejected" and "Illisible" not in str(mine)


def test_unknown_document_type_is_refused(world, login, bucket):
    assert upload(login("owner@f.example.com"), doc_type="passeport-diplomatique").status_code == 422
