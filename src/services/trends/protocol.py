from typing import Protocol

from pydantic import BaseModel, Field

from src.api.schemas.topics import RawTopic


class TrendFetchConfig(BaseModel):
    """Common parameters passed to every trend source."""

    domain_keywords: list[str] = Field(min_length=1)
    max_results: int = Field(default=30, ge=1, le=100)


class TrendSourceError(Exception):
    """Base error for all trend source failures."""

    def __init__(self, source_name: str, message: str) -> None:
        self.source_name = source_name
        super().__init__(f"[{source_name}] {message}")


class TrendSource(Protocol):
    """Contract that all trend sources must satisfy."""

    @property
    def source_name(self) -> str: ...

    async def fetch_and_normalize(
        self,
        config: TrendFetchConfig,
    ) -> list[RawTopic]: ...
