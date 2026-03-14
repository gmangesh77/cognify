import math
import time
from datetime import UTC, datetime

import structlog

from src.api.schemas.topics import RawTopic
from src.api.schemas.trends import ArxivFetchResponse
from src.services.arxiv_client import ArxivClient, ArxivPaper

logger = structlog.get_logger()

# 7-day half-life for recency decay
_RECENCY_LAMBDA = math.log(2) / 7


class ArxivService:
    def __init__(self, client: ArxivClient) -> None:
        self._client = client

    @staticmethod
    def calculate_score(
        days_ago: float,
        num_categories: int,
        abstract_length: int,
    ) -> float:
        recency = math.exp(-_RECENCY_LAMBDA * days_ago) * 100
        cat_bonus = min(60.0, num_categories * 15.0)
        abs_bonus = min(40.0, abstract_length / 25)
        citation = cat_bonus + abs_bonus
        raw = recency * 0.6 + citation * 0.4
        return min(100.0, raw)

    @staticmethod
    def calculate_velocity(days_ago: float) -> float:
        return 1.0 / max(1.0, days_ago)

    @staticmethod
    def filter_by_domain(
        papers: list[ArxivPaper],
        domain_keywords: list[str],
    ) -> list[tuple[ArxivPaper, list[str]]]:
        results: list[tuple[ArxivPaper, list[str]]] = []
        for paper in papers:
            title = paper["title"].lower()
            abstract = paper["abstract"].lower()
            cats = " ".join(paper["categories"]).lower()
            authors = " ".join(paper["authors"]).lower()
            text = f"{title} {abstract} {cats} {authors}"
            matched = [kw for kw in domain_keywords if kw.lower() in text]
            if matched:
                results.append((paper, matched))
        return results

    @staticmethod
    def map_to_raw_topic(
        paper: ArxivPaper,
        score: float,
        velocity: float,
        matched_keywords: list[str],
    ) -> RawTopic:
        return RawTopic(
            title=paper["title"],
            description=paper["abstract"][:200],
            source="arxiv",
            external_url=paper["abs_url"],
            trend_score=score,
            velocity=velocity,
            discovered_at=datetime.now(UTC),
            domain_keywords=matched_keywords,
        )

    @staticmethod
    def _deduplicate(
        topics: list[RawTopic],
    ) -> list[RawTopic]:
        if not topics:
            return []
        by_url: dict[str, RawTopic] = {}
        for topic in topics:
            url = topic.external_url
            if url in by_url:
                if topic.trend_score > by_url[url].trend_score:
                    by_url[url] = topic
            else:
                by_url[url] = topic
        return list(by_url.values())

    async def fetch_and_normalize(
        self,
        domain_keywords: list[str],
        categories: list[str],
        max_results: int,
    ) -> ArxivFetchResponse:
        start = time.monotonic()
        logger.info(
            "arxiv_fetch_started",
            domain_keywords=domain_keywords,
            categories=categories,
            max_results=max_results,
        )
        papers = await self._client.fetch_papers(
            categories,
            max_results,
            sort_by="submittedDate",
        )
        total_fetched = len(papers)
        filtered = self.filter_by_domain(
            papers,
            domain_keywords,
        )
        logger.debug(
            "arxiv_items_filtered",
            before_count=total_fetched,
            after_count=len(filtered),
        )
        now = datetime.now(UTC)
        topics: list[RawTopic] = []
        for paper, kws in filtered:
            published = paper.get("published", "")
            try:
                pub_dt = datetime.fromisoformat(
                    published.replace("Z", "+00:00"),
                )
                days_ago = max(
                    0.0,
                    (now - pub_dt).total_seconds() / 86400,
                )
            except (ValueError, TypeError):
                days_ago = 30.0
            score = self.calculate_score(
                days_ago,
                len(paper["categories"]),
                len(paper["abstract"]),
            )
            velocity = self.calculate_velocity(days_ago)
            topics.append(
                self.map_to_raw_topic(paper, score, velocity, kws),
            )
        deduped = self._deduplicate(topics)
        duration_ms = round(
            (time.monotonic() - start) * 1000,
        )
        logger.info(
            "arxiv_fetch_completed",
            total_fetched=total_fetched,
            total_after_filter=len(topics),
            total_after_dedup=len(deduped),
            duration_ms=duration_ms,
        )
        return ArxivFetchResponse(
            topics=deduped,
            total_fetched=total_fetched,
            total_after_filter=len(topics),
        )
