"""PublishingService — platform-agnostic orchestrator with retry."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog

from src.models.publishing import (
    Publication,
    PublicationEvent,
    PublicationResult,
    PublicationStatus,
    Transformer,
)

if TYPE_CHECKING:
    from src.models.content import SEOMetadata
    from src.models.publishing import Adapter

logger = structlog.get_logger()

_MAX_RETRIES = 3
_BACKOFF_BASE = 1.0  # seconds


@dataclass(frozen=True)
class PlatformPair:
    """A transformer + adapter pair for a single platform."""

    transformer: Transformer
    adapter: Adapter


def compute_seo_score(seo: SEOMetadata) -> int:
    """Compute 0-100 SEO completeness score from article metadata."""
    score = 0
    if seo.title:
        score += 20
    if seo.description:
        score += 20
    if seo.keywords:
        score += 20
    if seo.canonical_url:
        score += 15
    if seo.structured_data is not None:
        score += 25
    return score


class PublishingService:
    """Orchestrates publishing: load, transform, publish with retry."""

    def __init__(
        self,
        article_repo: object,
        pub_repo: object | None = None,
    ) -> None:
        self._article_repo = article_repo
        self._pub_repo = pub_repo
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
        result = await _with_retry(
            pair.adapter, payload, schedule_at, article_id, platform,
        )

        if self._pub_repo is not None:
            await self._persist_result(result, article)

        return result

    async def retry(self, publication_id: UUID) -> PublicationResult:
        """Re-publish a failed publication."""
        if self._pub_repo is None:
            msg = "Publication repository not configured"
            raise ValueError(msg)

        pub = await self._pub_repo.get(publication_id)
        if pub is None:
            msg = f"Publication {publication_id} not found"
            raise ValueError(msg)
        if pub.status != PublicationStatus.FAILED:
            msg = "Only failed publications can be retried"
            raise ValueError(msg)

        return await self.publish(pub.article_id, pub.platform)

    async def _persist_result(
        self, result: PublicationResult, article: object,
    ) -> None:
        """Create or update publication record after publish attempt."""
        now = datetime.now(UTC)
        event = PublicationEvent(
            timestamp=now,
            status=result.status,
            error_message=result.error_message,
        )
        seo_score = compute_seo_score(article.seo)

        existing = await self._pub_repo.get_by_article_platform(
            result.article_id, result.platform,
        )
        if existing is not None:
            updated = Publication(
                id=existing.id,
                article_id=existing.article_id,
                platform=existing.platform,
                status=result.status,
                external_id=result.external_id or existing.external_id,
                external_url=result.external_url or existing.external_url,
                published_at=result.published_at or existing.published_at,
                view_count=existing.view_count,
                seo_score=seo_score,
                error_message=result.error_message,
                event_history=[*existing.event_history, event],
                created_at=existing.created_at,
                updated_at=now,
            )
            await self._pub_repo.update(updated)
        else:
            new_pub = Publication(
                id=uuid4(),
                article_id=result.article_id,
                platform=result.platform,
                status=result.status,
                external_id=result.external_id,
                external_url=result.external_url,
                published_at=result.published_at,
                view_count=0,
                seo_score=seo_score,
                error_message=result.error_message,
                event_history=[event],
                created_at=now,
                updated_at=now,
            )
            await self._pub_repo.create(new_pub)

        logger.info(
            "publication_persisted",
            article_id=str(result.article_id),
            platform=result.platform,
            status=result.status,
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
