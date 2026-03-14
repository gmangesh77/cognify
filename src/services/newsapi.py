import math
import time
from datetime import UTC, datetime
from difflib import SequenceMatcher

import structlog

from src.api.schemas.topics import RawTopic
from src.api.schemas.trends import NewsAPIFetchResponse
from src.services.newsapi_client import NewsAPIArticle, NewsAPIClient

logger = structlog.get_logger()

# 6-hour half-life for recency decay
_RECENCY_LAMBDA = math.log(2) / 6


class NewsAPIService:
    def __init__(self, client: NewsAPIClient) -> None:
        self._client = client

    @staticmethod
    def calculate_score(
        index: int,
        total: int,
        hours_ago: float,
        num_keywords: int,
    ) -> float:
        if total == 0:
            return 0.0
        position = max(0.0, 100 - (index * (100 / total)))
        recency = math.exp(-_RECENCY_LAMBDA * hours_ago)
        keyword = min(20.0, num_keywords * 5.0)
        return min(100.0, position * 0.5 + recency * 30 + keyword)

    @staticmethod
    def calculate_velocity(hours_ago: float) -> float:
        return 1.0 / max(1.0, hours_ago)

    @staticmethod
    def filter_by_domain(
        articles: list[NewsAPIArticle],
        domain_keywords: list[str],
    ) -> list[tuple[NewsAPIArticle, list[str]]]:
        results: list[tuple[NewsAPIArticle, list[str]]] = []
        for article in articles:
            title = article["title"].lower()
            desc = (article.get("description") or "").lower()
            source_name = article["source"]["name"].lower()
            content = (article.get("content") or "").lower()
            text = f"{title} {desc} {source_name} {content}"
            matched = [
                kw
                for kw in domain_keywords
                if kw.lower() in text
            ]
            if matched:
                results.append((article, matched))
        return results

    @staticmethod
    def map_to_raw_topic(
        article: NewsAPIArticle,
        score: float,
        velocity: float,
        matched_keywords: list[str],
    ) -> RawTopic:
        desc = article.get("description") or ""
        return RawTopic(
            title=article["title"],
            description=desc[:200],
            source="newsapi",
            external_url=article["url"],
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

        # Pass 1: exact URL dedup — keep highest score
        by_url: dict[str, RawTopic] = {}
        for topic in topics:
            url = topic.external_url
            if url in by_url:
                if topic.trend_score > by_url[url].trend_score:
                    by_url[url] = topic
            else:
                by_url[url] = topic
        unique = list(by_url.values())

        # Pass 2: fuzzy title dedup
        merged: set[int] = set()
        result: list[RawTopic] = []
        for i, topic_a in enumerate(unique):
            if i in merged:
                continue
            best = topic_a
            for j in range(i + 1, len(unique)):
                if j in merged:
                    continue
                ratio = SequenceMatcher(
                    None,
                    topic_a.title.lower(),
                    unique[j].title.lower(),
                ).ratio()
                if ratio > 0.85:
                    merged.add(j)
                    if unique[j].trend_score > best.trend_score:
                        best = unique[j]
            result.append(best)
        return result

    async def fetch_and_normalize(
        self,
        domain_keywords: list[str],
        category: str,
        country: str,
        max_results: int,
    ) -> NewsAPIFetchResponse:
        start = time.monotonic()
        logger.info(
            "newsapi_fetch_started",
            domain_keywords=domain_keywords,
            category=category,
            country=country,
            max_results=max_results,
        )
        articles = await self._client.fetch_top_headlines(
            category,
            country,
            max_results,
        )
        total_fetched = len(articles)
        filtered = self.filter_by_domain(
            articles,
            domain_keywords,
        )
        logger.debug(
            "newsapi_items_filtered",
            before_count=total_fetched,
            after_count=len(filtered),
            domain_keywords=domain_keywords,
        )
        now = datetime.now(UTC)
        topics: list[RawTopic] = []
        total = len(filtered)
        for index, (article, kws) in enumerate(filtered):
            published = article.get("publishedAt") or ""
            try:
                pub_dt = datetime.fromisoformat(
                    published.replace("Z", "+00:00"),
                )
                hours_ago = max(
                    0.0,
                    (now - pub_dt).total_seconds() / 3600,
                )
            except (ValueError, TypeError):
                hours_ago = 24.0  # fallback for bad dates
            score = self.calculate_score(
                index, total, hours_ago, len(kws),
            )
            velocity = self.calculate_velocity(hours_ago)
            topics.append(
                self.map_to_raw_topic(article, score, velocity, kws),
            )
        deduped = self._deduplicate(topics)
        duration_ms = round(
            (time.monotonic() - start) * 1000,
        )
        logger.info(
            "newsapi_fetch_completed",
            total_fetched=total_fetched,
            total_after_filter=len(topics),
            total_after_dedup=len(deduped),
            duration_ms=duration_ms,
        )
        return NewsAPIFetchResponse(
            topics=deduped,
            total_fetched=total_fetched,
            total_after_filter=len(topics),
        )
