"""Stockage privé des documents (README §16) : bucket S3, accès par URL pré-signée courte."""

from functools import lru_cache
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import get_settings


@lru_cache
def _client() -> Any:
    settings = get_settings()
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    if settings.s3_endpoint_url:
        # Émulateur local : le bucket est créé à la volée. En production il existe déjà,
        # privé, et l'application n'a pas le droit d'en créer.
        try:
            client.create_bucket(Bucket=settings.s3_bucket)
        except ClientError as error:
            if error.response["Error"]["Code"] not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
                raise
    return client


def put_object(key: str, data: bytes, content_type: str) -> None:
    _client().put_object(Bucket=get_settings().s3_bucket, Key=key, Body=data, ContentType=content_type)


def presigned_download_url(key: str, filename: str) -> str:
    """Lien de téléchargement temporaire. Jamais d'URL publique permanente."""
    settings = get_settings()
    safe_name = filename.replace('"', "").replace("\\", "")
    url: str = _client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.s3_bucket,
            "Key": key,
            "ResponseContentDisposition": f'attachment; filename="{safe_name}"',
        },
        ExpiresIn=settings.document_url_seconds,
    )
    return url
