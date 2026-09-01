"""Request/response schemas for the prompt registry API (AUTHOR-012)."""

from datetime import datetime

from pydantic import BaseModel, Field


class PromptView(BaseModel):
    key: str
    step: str
    description: str
    variables: list[str]
    default_template: str
    template: str
    is_overridden: bool
    updated_by: str | None = None
    updated_at: datetime | None = None


class PromptListResponse(BaseModel):
    items: list[PromptView]


class UpdatePromptRequest(BaseModel):
    template: str = Field(min_length=1)
