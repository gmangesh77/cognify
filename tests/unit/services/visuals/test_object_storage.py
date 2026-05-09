"""Tests for object_storage: LocalDisk, MinIO factory, key sanitization, selector."""

from __future__ import annotations

import pytest

from src.config.settings import Settings
from src.services.visuals.object_storage import (
    LocalDiskObjectStorage,
    MinioObjectStorage,
    ObjectStorageError,
    make_object_key,
    select_object_storage,
)


@pytest.mark.asyncio
async def test_local_disk_put_writes_file(tmp_path: pytest.TempPathFactory) -> None:
    storage = LocalDiskObjectStorage(str(tmp_path))
    result = await storage.put(
        key="visuals/2026/05/spec1-abc.png",
        content=b"\x89PNG\r\n\x1a\n",
        content_type="image/png",
    )
    assert result.local_path is not None
    assert result.url is None
    assert result.size_bytes == 8
    assert result.content_type == "image/png"
    # File actually exists.
    from pathlib import Path

    assert Path(result.local_path).read_bytes() == b"\x89PNG\r\n\x1a\n"


@pytest.mark.asyncio
async def test_local_disk_returns_hosted_url_when_base_configured(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """When given an api_base_url, the URL should point at the api's
    /generated_assets/ static mount so the dashboard + Insert into
    article flow can fetch the image without needing MinIO."""
    storage = LocalDiskObjectStorage(
        str(tmp_path / "generated_assets" / "visuals"),
        api_base_url="http://localhost:8000",
        public_path_prefix="generated_assets/visuals",
    )
    result = await storage.put(
        key="visuals/2026/05/spec1-abc.png",
        content=b"x",
        content_type="image/png",
    )
    assert result.url == (
        "http://localhost:8000/generated_assets/visuals/"
        "visuals/2026/05/spec1-abc.png"
    )


@pytest.mark.asyncio
async def test_local_disk_url_strips_trailing_base_slash(
    tmp_path: pytest.TempPathFactory,
) -> None:
    storage = LocalDiskObjectStorage(
        str(tmp_path),
        api_base_url="http://localhost:8000/",
        public_path_prefix="/generated_assets/visuals/",
    )
    result = await storage.put(
        key="hero.png", content=b"x", content_type="image/png"
    )
    assert result.url == "http://localhost:8000/generated_assets/visuals/hero.png"


@pytest.mark.asyncio
async def test_local_disk_creates_subdirectories(
    tmp_path: pytest.TempPathFactory,
) -> None:
    storage = LocalDiskObjectStorage(str(tmp_path))
    result = await storage.put(
        key="visuals/2026/05/deep/spec.png",
        content=b"x",
        content_type="image/png",
    )
    from pathlib import Path

    assert Path(result.local_path).exists()  # type: ignore[arg-type]


def test_make_object_key_format() -> None:
    key = make_object_key(spec_id="hero-1", ext="png")
    assert key.startswith("visuals/")
    assert "hero-1" in key
    assert key.endswith(".png")


def test_make_object_key_normalizes_extension() -> None:
    key = make_object_key(spec_id="x", ext=".JPEG")
    assert key.endswith(".jpeg")


def test_make_object_key_default_ext() -> None:
    key = make_object_key(spec_id="x", ext="")
    assert key.endswith(".png")


def test_make_object_key_requires_spec_id() -> None:
    with pytest.raises(ObjectStorageError):
        make_object_key(spec_id="", ext="png")


@pytest.mark.asyncio
async def test_local_disk_rejects_traversal_key(
    tmp_path: pytest.TempPathFactory,
) -> None:
    storage = LocalDiskObjectStorage(str(tmp_path))
    with pytest.raises(ObjectStorageError):
        await storage.put(key="../escape.png", content=b"x", content_type="image/png")


@pytest.mark.asyncio
async def test_local_disk_rejects_empty_key(tmp_path: pytest.TempPathFactory) -> None:
    storage = LocalDiskObjectStorage(str(tmp_path))
    with pytest.raises(ObjectStorageError):
        await storage.put(key="", content=b"x", content_type="image/png")


def test_minio_constructor_rejects_empty_credentials() -> None:
    with pytest.raises(ObjectStorageError):
        MinioObjectStorage(
            endpoint="",
            access_key="",
            secret_key="",
            bucket="b",
            public_url="https://cdn.example.com",
        )


@pytest.mark.asyncio
async def test_minio_put_raises_when_package_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When `minio` is not installed, put() raises a clear ObjectStorageError."""
    storage = MinioObjectStorage(
        endpoint="localhost:9000",
        access_key="ak",
        secret_key="sk",
        bucket="b",
        public_url="http://localhost:9000",
        secure=False,
    )
    # Force the lazy import to fail.
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "minio" or name.startswith("minio."):
            raise ImportError("simulated missing minio package")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(ObjectStorageError) as ei:
        await storage.put(key="visuals/x.png", content=b"x", content_type="image/png")
    assert "minio" in str(ei.value).lower()
    assert "uv add" in str(ei.value)


def test_select_falls_back_to_local_when_minio_disabled(
    tmp_path: pytest.TempPathFactory,
) -> None:
    settings = Settings(visuals_output_dir=str(tmp_path), minio_enabled=False)
    storage = select_object_storage(settings)
    assert storage.name == "local_disk"


def test_select_falls_back_when_minio_enabled_but_misconfigured(
    tmp_path: pytest.TempPathFactory,
) -> None:
    settings = Settings(
        visuals_output_dir=str(tmp_path),
        minio_enabled=True,
        # endpoint, keys, bucket all empty
    )
    storage = select_object_storage(settings)
    assert storage.name == "local_disk"


def test_select_returns_minio_when_fully_configured(
    tmp_path: pytest.TempPathFactory,
) -> None:
    settings = Settings(
        visuals_output_dir=str(tmp_path),
        minio_enabled=True,
        minio_endpoint="localhost:9000",
        minio_access_key="ak",
        minio_secret_key="sk",
        minio_bucket="visuals",
        minio_public_url="http://localhost:9000",
    )
    storage = select_object_storage(settings)
    assert storage.name == "minio"
