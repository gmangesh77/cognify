"""Publishing pipeline contracts — transformer/adapter protocols.

These protocols define the contract between the Publishing Service
and platform-specific implementations. See ADR-004 for rationale.
"""

from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, Field

from src.models.content import CanonicalArticle


class PlatformPayload(BaseModel):
    """Base model for platform-specific output.

    Each platform transformer subclasses this with platform-specific fields.
    """

    platform: str = Field(min_length=1)
    article_id: UUID
    content: str = Field(min_length=1)
    metadata: dict[str, str | int | bool] = Field(default_factory=dict)


class PublicationStatus(StrEnum):
    """Status of a publish operation."""

    SUCCESS = "success"
    FAILED = "failed"
    SCHEDULED = "scheduled"


class PublicationResult(BaseModel):
    """Result of a publish operation returned by adapters."""

    article_id: UUID
    platform: str
    status: PublicationStatus
    external_id: str | None = None
    external_url: str | None = None
    published_at: datetime | None = None
    error_message: str | None = None


@runtime_checkable
class Transformer(Protocol):
    """Pure function contract: CanonicalArticle -> PlatformPayload.

    No I/O. Must be unit-testable without mocks.
    """

    def transform(self, article: CanonicalArticle) -> PlatformPayload: ...


@runtime_checkable
class Adapter(Protocol):
    """I/O contract: PlatformPayload -> external platform API.

    Raise exceptions for transient/retryable failures (network, rate limit).
    Return PublicationResult(status=FAILED) for permanent failures.
    """

    async def publish(
        self,
        payload: PlatformPayload,
        schedule_at: datetime | None = None,
    ) -> PublicationResult: ...
