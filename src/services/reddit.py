import math
import time
from datetime import UTC, datetime
from difflib import SequenceMatcher

import structlog

from src.api.schemas.topics import RawTopic
from src.api.schemas.trends import RedditFetchResponse
from src.services.reddit_client import (
    RedditAPIError,
    RedditClient,
    RedditPostResponse,
)

logger = structlog.get_logger()

# 12-hour half-life for recency decay
_RECENCY_LAMBDA = math.log(2) / 12


class RedditService:
    def __init__(
        self,
        client: RedditClient,
        score_cap: float,
    ) -> None:
        self._client = client
        self._score_cap = score_cap

    @staticmethod
    def calculate_score(
        score: int,
        num_comments: int,
        hours_ago: float,
        score_cap: float,
    ) -> float:
        hours = max(1.0, hours_ago)
        comment_velocity = num_comments / hours
        recency_bonus = 100.0 * math.exp(
            -_RECENCY_LAMBDA * hours_ago,
        )
        raw = (
            (score * 0.3)
            + (comment_velocity * 0.5)
            + (recency_bonus * 0.2)
        )
        return min(100.0, (raw / score_cap) * 100)

    @staticmethod
    def calculate_velocity(
        score: int,
        hours_ago: float,
    ) -> float:
        hours = max(1.0, hours_ago)
        return score / hours
