"""Backfill local visual files into MinIO/S3 (Phase 6 / VISUAL-009).

Walks `settings.visuals_output_dir` (and the legacy chart/diagram/
illustration sub-trees) and uploads every file to the configured object
storage. Idempotent — already-uploaded objects are detected by key and
skipped, so the script can be run repeatedly.

Operationally this runs once during the storage rollout to migrate the
backlog of `/generated_assets/visuals/...` files that pre-date MinIO,
plus follow-up sweeps after edits. The corresponding
`canonical_articles.visuals[].url` rewrite is a separate one-shot SQL
migration documented in `docs/deployment/visual-storage-rollout.md`.

Usage:

    uv run python -m scripts.backfill_visuals_to_minio --dry-run
    uv run python -m scripts.backfill_visuals_to_minio

The script reads `Settings()` and uses `select_object_storage()` to
resolve the right backend, so the same code path drives staging and
production rollouts.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from src.config.settings import Settings
from src.services.visuals.object_storage import (
    LocalDiskObjectStorage,
    ObjectStorage,
    StoredObject,
    select_object_storage,
)

logger = logging.getLogger(__name__)

_MIME_BY_EXT: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".gif": "image/gif",
}

# Walk these subtrees under the project root. Order is informational only;
# the backfill is idempotent so duplicate keys across subtrees no-op.
_DEFAULT_SUBTREES: tuple[str, ...] = (
    "generated_assets/visuals",
    "generated_assets/illustrations",
    "generated_assets/charts",
    "generated_assets/diagrams",
)


@dataclass(frozen=True)
class BackfillResult:
    """Summary returned by `run_backfill`. Test-friendly data shape."""

    uploaded: int
    skipped: int
    failed: int
    files_seen: int
    keys_uploaded: tuple[str, ...]
    keys_skipped: tuple[str, ...]
    keys_failed: tuple[str, ...]


@dataclass(frozen=True)
class _Plan:
    """One file the backfill intends to (re-)upload."""

    source: Path
    key: str
    mime_type: str


def iter_local_visuals(
    *,
    project_root: Path,
    subtrees: Iterable[str] = _DEFAULT_SUBTREES,
) -> list[_Plan]:
    """Walk the visual subtrees and yield one `_Plan` per supported file."""
    plans: list[_Plan] = []
    for sub in subtrees:
        base = project_root / sub
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            mime = _MIME_BY_EXT.get(path.suffix.lower())
            if mime is None:
                continue
            rel = path.relative_to(project_root)
            key = str(rel).replace("\\", "/").lstrip("/")
            plans.append(_Plan(source=path, key=key, mime_type=mime))
    return plans


async def run_backfill(
    *,
    storage: ObjectStorage,
    plans: list[_Plan],
    dry_run: bool = False,
    already_uploaded: set[str] | None = None,
) -> BackfillResult:
    """Upload every plan, skipping any key in `already_uploaded`."""
    uploaded: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []
    seen = already_uploaded if already_uploaded is not None else set()

    for plan in plans:
        if plan.key in seen:
            skipped.append(plan.key)
            continue
        if dry_run:
            uploaded.append(plan.key)
            continue
        try:
            data = plan.source.read_bytes()
            stored: StoredObject = await storage.put(
                key=plan.key,
                content=data,
                content_type=plan.mime_type,
            )
            uploaded.append(stored.key)
        except Exception as exc:  # noqa: BLE001 — backfill must continue on errors
            logger.warning(
                "backfill_upload_failed",
                extra={"key": plan.key, "error": str(exc)},
            )
            failed.append(plan.key)

    return BackfillResult(
        uploaded=len(uploaded),
        skipped=len(skipped),
        failed=len(failed),
        files_seen=len(plans),
        keys_uploaded=tuple(uploaded),
        keys_skipped=tuple(skipped),
        keys_failed=tuple(failed),
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List the files that would be uploaded without writing anything.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root. Subtrees are resolved relative to this.",
    )
    return parser.parse_args(argv)


async def _main_async(args: argparse.Namespace) -> int:
    settings = Settings()
    storage = select_object_storage(settings)
    if isinstance(storage, LocalDiskObjectStorage):
        logger.warning(
            "backfill_local_disk_storage_selected",
            extra={"hint": "set COGNIFY_MINIO_ENABLED=true to upload to MinIO"},
        )
    plans = iter_local_visuals(project_root=args.project_root)
    logger.info("backfill_plan_built", extra={"file_count": len(plans)})
    result = await run_backfill(storage=storage, plans=plans, dry_run=args.dry_run)
    logger.info(
        "backfill_complete",
        extra={
            "uploaded": result.uploaded,
            "skipped": result.skipped,
            "failed": result.failed,
            "files_seen": result.files_seen,
            "dry_run": args.dry_run,
        },
    )
    return 1 if result.failed > 0 else 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = _parse_args(argv)
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
