"""Tests for the visuals-to-MinIO backfill script (Phase 6 / VISUAL-009)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from scripts.backfill_visuals_to_minio import (
    iter_local_visuals,
    run_backfill,
)
from src.services.visuals.object_storage import LocalDiskObjectStorage


def _seed(root: Path, rel: str, contents: bytes = b"x") -> Path:
    """Create a file under `root/rel` and return its path."""
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(contents)
    return p


class TestIterLocalVisuals:
    def test_walks_default_subtrees(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed(root, "generated_assets/visuals/2026/05/cover.png")
            _seed(root, "generated_assets/illustrations/abc/hero.png")
            _seed(root, "generated_assets/charts/bar.png")
            _seed(root, "generated_assets/diagrams/flow.png")
            # Non-image file is skipped.
            _seed(root, "generated_assets/visuals/notes.txt")
            plans = iter_local_visuals(project_root=root)
            keys = sorted(p.key for p in plans)
            assert keys == [
                "generated_assets/charts/bar.png",
                "generated_assets/diagrams/flow.png",
                "generated_assets/illustrations/abc/hero.png",
                "generated_assets/visuals/2026/05/cover.png",
            ]

    def test_skips_unknown_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed(root, "generated_assets/visuals/cover.zip")
            _seed(root, "generated_assets/visuals/cover.txt")
            plans = iter_local_visuals(project_root=root)
            assert plans == []

    def test_returns_empty_when_subtree_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assert iter_local_visuals(project_root=root) == []

    def test_resolves_mime_from_extension(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed(root, "generated_assets/visuals/a.png")
            _seed(root, "generated_assets/visuals/b.jpg")
            _seed(root, "generated_assets/visuals/c.webp")
            _seed(root, "generated_assets/visuals/d.svg")
            plans = iter_local_visuals(project_root=root)
            mime_by_ext = {p.source.suffix: p.mime_type for p in plans}
            assert mime_by_ext == {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".webp": "image/webp",
                ".svg": "image/svg+xml",
            }


@pytest.mark.asyncio
class TestRunBackfill:
    async def test_uploads_every_planned_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed(root, "generated_assets/visuals/cover.png", b"PNG-bytes")
            _seed(root, "generated_assets/visuals/foo.png", b"more-bytes")
            plans = iter_local_visuals(project_root=root)
            with tempfile.TemporaryDirectory() as bucket:
                storage = LocalDiskObjectStorage(bucket)
                result = await run_backfill(storage=storage, plans=plans)
                assert result.files_seen == 2
                assert result.uploaded == 2
                assert result.skipped == 0
                assert result.failed == 0
                # Files actually written to the bucket dir.
                bucket_root = Path(bucket)
                assert (
                    bucket_root / "generated_assets" / "visuals" / "cover.png"
                ).exists()
                assert (
                    bucket_root / "generated_assets" / "visuals" / "foo.png"
                ).exists()

    async def test_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed(root, "generated_assets/visuals/cover.png")
            plans = iter_local_visuals(project_root=root)
            with tempfile.TemporaryDirectory() as bucket:
                storage = LocalDiskObjectStorage(bucket)
                result = await run_backfill(storage=storage, plans=plans, dry_run=True)
                assert result.uploaded == 1
                assert result.failed == 0
                # Bucket is empty — dry run skipped the actual put().
                bucket_root = Path(bucket)
                assert not list(bucket_root.rglob("*.png"))

    async def test_already_uploaded_set_marks_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed(root, "generated_assets/visuals/cover.png")
            _seed(root, "generated_assets/visuals/foo.png")
            plans = iter_local_visuals(project_root=root)
            with tempfile.TemporaryDirectory() as bucket:
                storage = LocalDiskObjectStorage(bucket)
                already = {"generated_assets/visuals/cover.png"}
                result = await run_backfill(
                    storage=storage, plans=plans, already_uploaded=already
                )
                assert result.uploaded == 1
                assert result.skipped == 1
                assert result.keys_skipped == ("generated_assets/visuals/cover.png",)

    async def test_records_failures_when_storage_raises(self) -> None:
        class _BoomStorage:
            name = "boom"

            async def put(self, *, key: str, content: bytes, content_type: str):  # type: ignore[no-untyped-def]
                raise RuntimeError("backend down")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed(root, "generated_assets/visuals/cover.png")
            plans = iter_local_visuals(project_root=root)
            result = await run_backfill(
                storage=_BoomStorage(),  # type: ignore[arg-type]
                plans=plans,
            )
            assert result.uploaded == 0
            assert result.failed == 1
            assert result.keys_failed == ("generated_assets/visuals/cover.png",)
