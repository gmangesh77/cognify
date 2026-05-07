"""Visual-generation HTTP API.

Phase 1 (VISUAL-004): exposes the visual-style catalogue, persona register,
and banned-cliché block as a single boot-time fetch for the frontend
(`GET /api/v1/visuals/styles`). This is the only endpoint shipped in
Phase 1 — `/visuals/plan`, `/visuals/render`, etc. land in Phase 4.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from src.services.visuals.banned_cliches import BANNED_CLICHES_BLOCK
from src.services.visuals.persona_directions import (
    DEFAULT_PERSONA,
    PERSONA_VISUAL_DIRECTIONS,
)
from src.services.visuals.visual_styles import (
    ROLE_STYLE_DEFAULTS,
    VISUAL_STYLES,
    planner_catalogue_block,
)

visuals_router = APIRouter(prefix="/visuals")


class StyleEntry(BaseModel):
    key: str
    label: str
    category: Literal["photo", "illustration", "editorial", "technical"]
    default_aspect: Literal["16:9", "1:1", "4:3", "3:4", "4:5"]
    short_desc: str
    prompt_fragment: str


class PersonaEntry(BaseModel):
    key: str
    direction: str


class StylesResponse(BaseModel):
    styles: list[StyleEntry]
    role_defaults: dict[str, str]
    personas: list[PersonaEntry]
    default_persona: str
    banned_cliches_block: str
    planner_catalogue_block: str


@visuals_router.get("/styles", response_model=StylesResponse)
async def get_visual_styles() -> StylesResponse:
    """Return the full visual-style catalogue, persona register, and cliché block.

    Single source of truth (ADR-005). The frontend boots, calls this once,
    and caches. There is no mirrored TypeScript catalogue — everything in
    this response is owned by `src/services/visuals/`.
    """
    return StylesResponse(
        styles=[
            StyleEntry.model_validate(entry) for entry in VISUAL_STYLES.values()
        ],
        role_defaults=dict(ROLE_STYLE_DEFAULTS),
        personas=[
            PersonaEntry(key=key, direction=direction)
            for key, direction in PERSONA_VISUAL_DIRECTIONS.items()
        ],
        default_persona=DEFAULT_PERSONA,
        banned_cliches_block=BANNED_CLICHES_BLOCK,
        planner_catalogue_block=planner_catalogue_block(),
    )


__all__ = ["visuals_router"]
