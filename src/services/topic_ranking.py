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
        return [((v - min_v) / (max_v - min_v)) * 100 for v in velocities]

    def filter_by_domain(
        self,
        topics: list[RawTopic],
        domain: str,
        domain_keywords: list[str],
    ) -> list[RawTopic]:
        if not domain_keywords:
            return list(topics)

        kw_set = {kw.lower() for kw in domain_keywords}
        result: list[RawTopic] = []
        for topic in topics:
            tokens: set[str] = set()
            for text in [topic.title, topic.description]:
                tokens.update(text.lower().split())
            for tag in topic.domain_keywords:
                tokens.update(tag.lower().split())
            if tokens & kw_set:
                result.append(topic)

        logger.debug(
            "topics_filtered",
            before_count=len(topics),
            after_count=len(result),
            domain=domain,
        )
        return result

    def deduplicate(
        self,
        topics: list[RawTopic],
    ) -> tuple[list[RawTopic], dict[str, int], list[DuplicateInfo]]:
        if len(topics) <= 1:
            counts = {t.title: 1 for t in topics}
            return list(topics), counts, []

        texts = [f"{t.title} {t.description}" for t in topics]
        embeddings = self._embedding.embed(texts)
        sim_matrix = self._embedding.cosine_similarity_matrix(embeddings)
        threshold = self._settings.dedup_similarity_threshold

        visited = [False] * len(topics)
        groups: list[list[int]] = []
        for i in range(len(topics)):
            if visited[i]:
                continue
            group = [i]
            visited[i] = True
            for j in range(i + 1, len(topics)):
                if not visited[j] and sim_matrix[i][j] >= threshold:
                    group.append(j)
                    visited[j] = True
            groups.append(group)

        deduped: list[RawTopic] = []
        source_counts: dict[str, int] = {}
        dup_info: list[DuplicateInfo] = []

        for group in groups:
            group_topics = [topics[idx] for idx in group]
            winner_idx_in_group = max(
                range(len(group)),
                key=lambda i: group_topics[i].trend_score,  # noqa: B023
            )
            winner = group_topics[winner_idx_in_group]
            winner_orig_idx = group[winner_idx_in_group]
            sources = {t.source for t in group_topics}
            source_counts[winner.title] = len(sources)
            deduped.append(winner)

            for i, orig_idx in enumerate(group):
                if i != winner_idx_in_group:
                    dup_info.append(
                        DuplicateInfo(
                            title=group_topics[i].title,
                            source=group_topics[i].source,
                            duplicate_of=winner.title,
                            similarity=sim_matrix[orig_idx][winner_orig_idx],
                        )
                    )

        logger.debug(
            "duplicates_removed",
            removed_count=len(dup_info),
            groups_count=len(groups),
        )
        return deduped, source_counts, dup_info

    def _score_diversity(self, source_count: int) -> float:
        if source_count >= 3:
            return 100.0
        if source_count == 2:
            return 66.0
        return 33.0

    def calculate_scores(
        self,
        topics: list[RawTopic],
        domain_keywords: list[str],
        source_counts: dict[str, int],
    ) -> list[RankedTopic]:
        velocity_scores = self._score_velocity(topics)
        scored: list[tuple[float, RawTopic, int]] = []

        for i, topic in enumerate(topics):
            relevance = self._score_relevance(topic, domain_keywords)
            recency = self._score_recency(topic)
            velocity = velocity_scores[i]
            diversity = self._score_diversity(
                source_counts.get(topic.title, 1),
            )
            composite = (
                relevance * self._settings.relevance_weight
                + recency * self._settings.recency_weight
                + velocity * self._settings.velocity_weight
                + diversity * self._settings.diversity_weight
            )
            scored.append(
                (
                    composite,
                    topic,
                    source_counts.get(topic.title, 1),
                )
            )

        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            RankedTopic(
                **topic.model_dump(),
                composite_score=round(composite, 2),
                rank=rank,
                source_count=sc,
            )
            for rank, (composite, topic, sc) in enumerate(scored, start=1)
        ]

    async def rank_and_deduplicate(
        self,
        request: RankTopicsRequest,
    ) -> RankTopicsResponse:
        start = time.monotonic()
        total_input = len(request.topics)

        filtered = self.filter_by_domain(
            request.topics,
            request.domain,
            request.domain_keywords,
        )

        if not filtered:
            return RankTopicsResponse(
                ranked_topics=[],
                duplicates_removed=[],
                total_input=total_input,
                total_after_dedup=0,
                total_returned=0,
            )

        deduped, source_counts, dup_info = self.deduplicate(filtered)
        total_after_dedup = len(deduped)

        ranked = self.calculate_scores(
            deduped,
            request.domain_keywords,
            source_counts,
        )

        top = ranked[: request.top_n]

        duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "topics_ranked",
            input_count=total_input,
            dedup_count=total_after_dedup,
            returned_count=len(top),
            duration_ms=round(duration_ms),
        )

        return RankTopicsResponse(
            ranked_topics=top,
            duplicates_removed=dup_info,
            total_input=total_input,
            total_after_dedup=total_after_dedup,
            total_returned=len(top),
        )
