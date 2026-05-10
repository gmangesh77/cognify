"""Object storage abstraction for rendered visuals.

Defines the `ObjectStorage` Protocol and ships two concrete implementations:

- `LocalDiskObjectStorage` — writes bytes to `visuals_output_dir`, returns a
  relative path. Used in dev and as a fallback when MinIO is disabled.
- `MinioObjectStorage` — uploads to a MinIO/S3 bucket, returns a public URL.
  Lazily imports the `minio` package on construction so deployments without
  MinIO never need the dependency. Phase 6 (production rollout) is when
  the real client is wired up; until then the Protocol + LocalDisk pair
  satisfies the boundary contract.

`select_object_storage(settings)` resolves the right implementation based
on `settings.minio_enabled` and the presence of MinIO credentials.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import structlog

from src.config.settings import Settings

logger = structlog.get_logger()


@dataclass(frozen=True)
class StoredObject:
    """Result of a successful upload.

    `url` is set when the storage backend can produce one (MinIO with
    `minio_public_url` configured, or any future CDN-backed storage).
    `local_path` is set when the bytes were written to local disk.
    Callers prefer `url` over `local_path` when both are present.
    """

    key: str
    url: str | None
    local_path: str | None
    size_bytes: int
    content_type: str


class ObjectStorageError(Exception):
    """Base error for object-storage failures."""


class ObjectStorage(Protocol):
    """Contract for visual asset storage backends."""

    @property
    def name(self) -> str:
        """Lowercase name (e.g. 'local_disk', 'minio'). For logging only."""
        ...

    async def put(
        self,
        *,
        key: str,
        content: bytes,
        content_type: str,
    ) -> StoredObject:
        """Persist `content` and return a `StoredObject` describing where."""
        ...


class LocalDiskObjectStorage:
    """Writes bytes to disk under `output_dir`.

    When `api_base_url` + `public_path_prefix` are supplied, the
    returned `StoredObject.url` is `${api_base_url}/${public_path_prefix}/${key}`,
    pointing at the api's static `/generated_assets/` mount so the
    dashboard's "Insert into article" flow can persist a hosted URL
    without needing MinIO. Otherwise `url=None` (legacy behavior; the
    render endpoint then falls back to base64).
    """

    def __init__(
        self,
        output_dir: str,
        api_base_url: str = "",
        public_path_prefix: str = "",
    ) -> None:
        self._dir = Path(output_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._api_base = api_base_url.rstrip("/")
        self._prefix = public_path_prefix.strip("/")

    @property
    def name(self) -> str:
        return "local_disk"

    async def put(
        self,
        *,
        key: str,
        content: bytes,
        content_type: str,
    ) -> StoredObject:
        sanitized = _sanitize_key(key)
        target = self._dir / sanitized
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        url = self._build_url(sanitized) if self._api_base and self._prefix else None
        return StoredObject(
            key=sanitized,
            url=url,
            local_path=str(target),
            size_bytes=len(content),
            content_type=content_type,
        )

    def _build_url(self, key: str) -> str:
        return f"{self._api_base}/{self._prefix}/{key}"


class MinioObjectStorage:
    """MinIO/S3-backed storage.

    The `minio` package is imported lazily so deployments that don't
    enable MinIO never need it. If `minio_enabled=True` but the package
    is missing, `ensure_bucket()` raises a clear `ObjectStorageError`
    naming the missing dependency.
    """

    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        public_url: str,
        secure: bool = False,
        region: str = "us-east-1",
    ) -> None:
        if not endpoint or not access_key or not secret_key:
            raise ObjectStorageError(
                "MinioObjectStorage requires endpoint, access_key, secret_key"
            )
        self._endpoint = endpoint
        self._access_key = access_key
        self._secret_key = secret_key
        self._bucket = bucket
        self._public_url = public_url.rstrip("/")
        self._secure = secure
        self._region = region
        self._client: object | None = None

    @property
    def name(self) -> str:
        return "minio"

    def _build_client(self) -> object:
        try:
            from minio import Minio  # noqa: I001
        except ImportError as exc:
            raise ObjectStorageError(
                "minio_enabled=True but the 'minio' package is not installed. "
                "Add it via `uv add minio` (Phase 6 production rollout)."
            ) from exc
        return Minio(
            self._endpoint,
            access_key=self._access_key,
            secret_key=self._secret_key,
            secure=self._secure,
            region=self._region,
        )

    def _client_lazy(self) -> object:
        if self._client is None:
            self._client = self._build_client()
        return self._client

    async def put(
        self,
        *,
        key: str,
        content: bytes,
        content_type: str,
    ) -> StoredObject:
        sanitized = _sanitize_key(key)
        client = self._client_lazy()
        # MinIO SDK is sync; run in a thread pool to keep the event loop free.
        import asyncio
        from io import BytesIO

        def _do_put() -> None:
            client.put_object(  # type: ignore[attr-defined]
                self._bucket,
                sanitized,
                BytesIO(content),
                length=len(content),
                content_type=content_type,
            )

        try:
            await asyncio.to_thread(_do_put)
        except Exception as exc:  # narrow: minio raises various subclasses
            logger.warning(
                "minio_put_failed", bucket=self._bucket, key=sanitized, error=str(exc)
            )
            raise ObjectStorageError(f"MinIO put failed: {exc}") from exc
        url = (
            f"{self._public_url}/{self._bucket}/{sanitized}"
            if self._public_url
            else None
        )
        return StoredObject(
            key=sanitized,
            url=url,
            local_path=None,
            size_bytes=len(content),
            content_type=content_type,
        )


def _sanitize_key(key: str) -> str:
    """Strip directory traversal and ensure the key is safe for filesystem + S3."""
    cleaned = key.strip().lstrip("/").replace("\\", "/")
    if ".." in cleaned.split("/"):
        raise ObjectStorageError(f"object key {key!r} contains '..' segment")
    if not cleaned:
        raise ObjectStorageError("object key may not be empty")
    return cleaned


def make_object_key(*, spec_id: str, ext: str = "png") -> str:
    """Build a key under ``visuals/<yyyy>/<mm>/<spec_id>-<hash>.<ext>``."""
    if not spec_id:
        raise ObjectStorageError("spec_id is required for object key")
    ts = time.gmtime()
    digest = hashlib.sha1(f"{spec_id}-{time.time_ns()}".encode()).hexdigest()[:10]
    safe_ext = ext.lstrip(".").lower() or "png"
    return f"visuals/{ts.tm_year:04d}/{ts.tm_mon:02d}/{spec_id}-{digest}.{safe_ext}"


def select_object_storage(settings: Settings) -> ObjectStorage:
    """Resolve the right `ObjectStorage` for the given settings.

    - When `minio_enabled` is True AND every MinIO setting is provided:
      returns `MinioObjectStorage`. The actual `minio` package import is
      deferred until the first `put()` call.
    - Otherwise: returns `LocalDiskObjectStorage` rooted at
      `settings.visuals_output_dir`.
    """
    if settings.minio_enabled and _minio_config_complete(settings):
        return MinioObjectStorage(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket=settings.minio_bucket,
            public_url=settings.minio_public_url,
            secure=settings.minio_use_ssl,
            region=settings.minio_region,
        )
    if settings.minio_enabled:
        logger.warning(
            "minio_misconfigured_falling_back_to_local",
            missing=_minio_missing_fields(settings),
        )
    # Derive a public URL prefix from visuals_output_dir relative to the
    # api's static-assets root (`generated_assets/`), so the dashboard can
    # fetch the rendered image and the Insert into article flow can persist
    # a hosted URL even without MinIO.
    out_dir = settings.visuals_output_dir.replace("\\", "/").lstrip("/")
    public_prefix = out_dir if out_dir.startswith("generated_assets/") else ""
    return LocalDiskObjectStorage(
        settings.visuals_output_dir,
        api_base_url=settings.api_base_url,
        public_path_prefix=public_prefix,
    )


def _minio_config_complete(settings: Settings) -> bool:
    return all(
        [
            settings.minio_endpoint,
            settings.minio_access_key,
            settings.minio_secret_key,
            settings.minio_bucket,
        ]
    )


def _minio_missing_fields(settings: Settings) -> list[str]:
    missing: list[str] = []
    if not settings.minio_endpoint:
        missing.append("minio_endpoint")
    if not settings.minio_access_key:
        missing.append("minio_access_key")
    if not settings.minio_secret_key:
        missing.append("minio_secret_key")
    if not settings.minio_bucket:
        missing.append("minio_bucket")
    return missing


__all__ = [
    "LocalDiskObjectStorage",
    "MinioObjectStorage",
    "ObjectStorage",
    "ObjectStorageError",
    "StoredObject",
    "make_object_key",
    "select_object_storage",
]
