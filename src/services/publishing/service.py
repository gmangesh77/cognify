"""PublishingService — platform-agnostic orchestrator with retry."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from src.models.publishing import PublicationResult, PublicationStatus, Transformer

if TYPE_CHECKING:
    from src.models.publishing import Adapter

logger = structlog.get_logger()

_MAX_RETRIES = 3
_BACKOFF_BASE = 1.0  # seconds


@dataclass(frozen=True)
class PlatformPair:
    """A transformer + adapter pair for a single platform."""

    transformer: Transformer
    adapter: Adapter


class PublishingService:
    """Orchestrates publishing: load, transform, publish with retry."""

    def __init__(self, article_repo: object) -> None:
        self._article_repo = article_repo
        self._platforms: dict[str, PlatformPair] = {}

    def register(self, platform: str, pair: PlatformPair) -> None:
        self._platforms[platform] = pair
        logger.info("platform_registered", platform=platform)

    async def publish(
        self,
        article_id: UUID,
        platform: str,
        schedule_at: datetime | None = None,
    ) -> PublicationResult:
        logger.info(
            "publish_started",
            article_id=str(article_id),
            platform=platform,
        )
        article = await self._article_repo.get(article_id)
        if article is None:
            return _failed(article_id, platform, "Article not found")

        pair = self._platforms.get(platform)
        if pair is None:
            return _failed(article_id, platform, f"Unknown platform: {platform}")

        payload = pair.transformer.transform(article)
        return await _with_retry(
            pair.adapter, payload, schedule_at, article_id, platform,
        )


async def _with_retry(
    adapter: Adapter,
    payload: object,
    schedule_at: datetime | None,
    article_id: UUID,
    platform: str,
) -> PublicationResult:
    """Retry on transient errors (exceptions), not permanent failures."""
    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            result = await adapter.publish(payload, schedule_at)  # type: ignore[arg-type]
            _log_result(result, article_id, platform)
            return result
        except Exception as exc:
            last_error = exc
            wait = _BACKOFF_BASE * (2 ** attempt)
            logger.warning(
                "publish_retry",
                attempt=attempt + 1,
                platform=platform,
                error=str(exc),
            )
            await asyncio.sleep(wait)
    logger.error(
        "publish_exhausted_retries",
        article_id=str(article_id),
        platform=platform,
    )
    return _failed(article_id, platform, f"Retries exhausted: {last_error}")


def _log_result(
    result: PublicationResult, article_id: UUID, platform: str,
) -> None:
    if result.status == PublicationStatus.SUCCESS:
        logger.info(
            "publish_succeeded",
            article_id=str(article_id),
            platform=platform,
        )
    else:
        logger.warning(
            "publish_failed",
            article_id=str(article_id),
            platform=platform,
            error=result.error_message,
        )


def _failed(
    article_id: UUID, platform: str, message: str,
) -> PublicationResult:
    return PublicationResult(
        article_id=article_id,
        platform=platform,
        status=PublicationStatus.FAILED,
        error_message=message,
    )
