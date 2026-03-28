"""Topic persistence with cross-scan deduplication.

Persists ranked topics to PostgreSQL, deduplicating against
existing topics using embedding cosine similarity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from src.api.schemas.topics import PersistedTopic, RankedTopic
    from src.db.repositories import PgTopicRepository
    from src.services.embeddings import EmbeddingService

logger = structlog.get_logger()


@dataclass(frozen=True)
class PersistResult:
    """Result of a topic persistence operation."""

    new_count: int
    updated_count: int
    total_persisted: int
    topic_ids: list[str] = field(default_factory=list)


class TopicPersistenceService:
    """Persists ranked topics with cross-scan dedup."""

    def __init__(
        self,
        repo: PgTopicRepository,
        embedding_service: EmbeddingService,
        threshold: float = 0.85,
    ) -> None:
        self._repo = repo
        self._embedding = embedding_service
        self._threshold = threshold

    async def persist_ranked_topics(
        self,
        topics: list[RankedTopic],
        domain: str,
    ) -> PersistResult:
        """Persist topics, deduping against existing DB topics."""
        if not topics:
            return PersistResult(0, 0, 0)

        existing, _ = await self._repo.list_by_domain(
            domain,
            page=1,
            size=500,
        )
        matches = self._find_matches(topics, existing)

        new_count = 0
        updated_count = 0
        topic_ids: list[str] = []
        for i, topic in enumerate(topics):
            match_id = matches.get(i)
            if match_id is not None:
                await self._repo.update_from_scan(match_id, topic)
                updated_count += 1
                topic_ids.append(str(match_id))
            else:
                new_id = await self._repo.create_from_ranked(topic, domain)
                new_count += 1
                topic_ids.append(str(new_id))

        logger.info(
            "topics_persisted",
            domain=domain,
            new=new_count,
            updated=updated_count,
        )
        return PersistResult(
            new_count=new_count,
            updated_count=updated_count,
            total_persisted=new_count + updated_count,
            topic_ids=topic_ids,
        )

    def _find_matches(
        self,
        new_topics: list[RankedTopic],
        existing: list[PersistedTopic],
    ) -> dict[int, object]:
        """Find which new topics match existing ones.

        Returns: {new_index: existing_topic_id}
        """
        if not existing:
            return {}

        new_titles = [t.title for t in new_topics]
        existing_titles = [t.title for t in existing]
        new_embs = self._embedding.embed(new_titles)
        existing_embs = self._embedding.embed(existing_titles)

        matches: dict[int, object] = {}
        for i, new_emb in enumerate(new_embs):
            best_sim = 0.0
            best_id = None
            for j, ex_emb in enumerate(existing_embs):
                sim = self._cosine_sim(new_emb, ex_emb)
                if sim > best_sim:
                    best_sim = sim
                    best_id = existing[j].id
            if best_sim >= self._threshold and best_id is not None:
                matches[i] = best_id
        return matches

    @staticmethod
    def _cosine_sim(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b, strict=True))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
