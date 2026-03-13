import math
import time
from datetime import UTC, datetime

import structlog

from src.api.schemas.topics import (
    DuplicateInfo,
    RankedTopic,
    RankTopicsRequest,
    RankTopicsResponse,
    RawTopic,
)
from src.config.settings import Settings
from src.services.embeddings import EmbeddingService

logger = structlog.get_logger()

_NEUTRAL_SCORE = 50.0


class TopicRankingService:
    def __init__(
        self,
        settings: Settings,
        embedding_service: EmbeddingService,
    ) -> None:
        self._settings = settings
        self._embedding = embedding_service
        self._validate_weights()

    def _validate_weights(self) -> None:
        total = (
            self._settings.relevance_weight
            + self._settings.recency_weight
            + self._settings.velocity_weight
            + self._settings.diversity_weight
        )
        if abs(total - 1.0) > 0.001:
            msg = f"Scoring weights must sum to 1.0, got {total}"
            raise ValueError(msg)

    def _score_relevance(
        self,
        topic: RawTopic,
        domain_keywords: list[str],
    ) -> float:
        if not domain_keywords:
            return _NEUTRAL_SCORE

        topic_tokens: set[str] = set()
        for text in [topic.title, topic.description]:
            topic_tokens.update(text.lower().split())
        for kw in topic.domain_keywords:
            topic_tokens.update(kw.lower().split())

        if not topic_tokens:
            return 0.0

        domain_tokens = {kw.lower() for kw in domain_keywords}
        intersection = topic_tokens & domain_tokens
        union = topic_tokens | domain_tokens

        if not union:
            return 0.0

        return (len(intersection) / len(union)) * 100

    # λ = ln(2)/24 — 24h gives score of 50
    _RECENCY_LAMBDA = math.log(2) / 24

    def _score_recency(self, topic: RawTopic) -> float:
        now = datetime.now(UTC)
        discovered = topic.discovered_at
        if discovered.tzinfo is None:
            discovered = discovered.replace(tzinfo=UTC)
        else:
            discovered = discovered.astimezone(UTC)
        hours_ago = max((now - discovered).total_seconds() / 3600, 0.0)
        return 100 * math.exp(-self._RECENCY_LAMBDA * hours_ago)

    def _score_velocity(
        self,
        topics: list[RawTopic],
    ) -> list[float]:
        velocities = [t.velocity for t in topics]
        min_v = min(velocities)
        max_v = max(velocities)
        if max_v == min_v:
            return [_NEUTRAL_SCORE] * len(topics)
        return [
            ((v - min_v) / (max_v - min_v)) * 100
            for v in velocities
        ]
