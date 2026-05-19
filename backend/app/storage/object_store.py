from __future__ import annotations

import io
import json
from typing import Any

from minio import Minio

from app.config import get_settings


def _build_client() -> Minio | None:
    settings = get_settings()
    if not settings.minio_endpoint or not settings.minio_access_key or not settings.minio_secret_key:
        return None
    return Minio(
        settings.minio_endpoint.replace("http://", "").replace("https://", ""),
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def ensure_bucket(client: Minio, bucket: str) -> None:
    if client.bucket_exists(bucket):
        return
    client.make_bucket(bucket)


def upload_json(bucket: str, object_name: str, payload: dict[str, Any]) -> None:
    client = _build_client()
    if client is None:
        return
    ensure_bucket(client, bucket)
    data = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    client.put_object(bucket, object_name, io.BytesIO(data), length=len(data), content_type="application/json")
