"""Repurpose a CanonicalArticle into a standalone LinkedIn post (AUTHOR-013).

Pure apart from the LLM call: no DB, no HTTP. The API layer binds the
`linkedin_repurpose` tracked step + session id and calls
`repurpose_to_linkedin` directly; the resulting draft is edited by the
user in the frontend modal and published via the `linkedin_post`
platform + `PublishingService`'s `content_override` seam (ADR-004: this
module never imports from `src.services.publishing.service`).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, ValidationError

from src.agents.content.humanizer import fix_mechanical
from src.agents.content.slop_scorer import score_text
from src.agents.prompts import render_prompt
from src.services.content.section_rewriter import model_label
from src.utils.llm_json import parse_llm_json

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

    from src.models.content import CanonicalArticle

MAX_POST_CHARS = 3000
_MAX_HASHTAGS = 5
_MAX_KEY_CLAIMS = 6
_HASHTAG_STRIP_RE = re.compile(r"[^a-z0-9]")


@dataclass(frozen=True)
class RepurposeInput:
    """Input to `repurpose_to_linkedin`."""

    article: CanonicalArticle
    instruction: str | None = None


class LinkedInPostDraft(BaseModel, frozen=True):
    """A generated (and possibly length-truncated) LinkedIn post draft."""

    hook: str
    beats: list[str]
    cta: str
    hashtags: list[str]
    text: str
    char_count: int
    slop_score: int
    slop_rating: str
    model: str
    truncated: bool


class _RawDraft(BaseModel):
    """The model's raw JSON output before hashtag sanitisation / assembly."""

    hook: str
    beats: list[str] = Field(min_length=1, max_length=5)
    cta: str
    hashtags: list[str] = Field(default_factory=list)


async def repurpose_to_linkedin(
    inp: RepurposeInput, llm: BaseChatModel
) -> LinkedInPostDraft:
    """Turn `inp.article` into a standalone LinkedIn post draft."""
    article = inp.article
    system_prompt = render_prompt("linkedin_repurpose.system")
    user_prompt = _user_prompt(article, inp.instruction)

    raw = await _draft_with_parse_retry(llm, system_prompt, user_prompt)
    hashtags, text = _assemble(raw)
    truncated = False

    if len(text) > MAX_POST_CHARS:
        shorter_prompt = user_prompt + "\n\n" + render_prompt("linkedin_repurpose.shorter")
        raw = await _draft_with_parse_retry(llm, system_prompt, shorter_prompt)
        hashtags, text = _assemble(raw)
        if len(text) > MAX_POST_CHARS:
            text = _truncate_to_limit(text, MAX_POST_CHARS)
            truncated = True

    score = score_text(text)
    return LinkedInPostDraft(
        hook=raw.hook,
        beats=raw.beats,
        cta=raw.cta,
        hashtags=hashtags,
        text=text,
        char_count=len(text),
        slop_score=score.score,
        slop_rating=score.rating,
        model=model_label(llm),
        truncated=truncated,
    )


def _user_prompt(article: CanonicalArticle, instruction: str | None) -> str:
    instruction_block = f"Editor instruction: {instruction}" if instruction else ""
    return render_prompt(
        "linkedin_repurpose.user",
        title=article.title,
        summary=article.summary,
        key_claims=_key_claims_block(article),
        instruction=instruction_block,
    )


def _key_claims_block(article: CanonicalArticle) -> str:
    claims = article.key_claims[:_MAX_KEY_CLAIMS]
    if not claims:
        return "- (none)"
    return "\n".join(f"- {claim}" for claim in claims)


async def _draft_once(
    llm: BaseChatModel, system_prompt: str, user_prompt: str
) -> _RawDraft:
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    response = await llm.ainvoke(messages)
    data = parse_llm_json(str(response.content))
    return _RawDraft.model_validate(data)


async def _draft_with_parse_retry(
    llm: BaseChatModel, system_prompt: str, user_prompt: str
) -> _RawDraft:
    """One LLM call; on unparseable/invalid output retry once, then raise."""
    try:
        return await _draft_once(llm, system_prompt, user_prompt)
    except (json.JSONDecodeError, ValidationError):
        pass
    try:
        return await _draft_once(llm, system_prompt, user_prompt)
    except (json.JSONDecodeError, ValidationError) as exc:
        msg = "linkedin repurpose: unparseable model output"
        raise ValueError(msg) from exc


def _assemble(raw: _RawDraft) -> tuple[list[str], str]:
    hashtags = _build_hashtags(raw.hashtags)
    text = _compose_text(raw.hook, raw.beats, raw.cta, hashtags)
    return hashtags, fix_mechanical(text)


def _build_hashtags(tags: list[str]) -> list[str]:
    result: list[str] = []
    for tag in tags:
        clean = _HASHTAG_STRIP_RE.sub("", tag.lower())
        if not clean:
            continue
        candidate = f"#{clean}"
        if candidate in result:
            continue
        result.append(candidate)
        if len(result) >= _MAX_HASHTAGS:
            break
    return result


def _compose_text(hook: str, beats: list[str], cta: str, hashtags: list[str]) -> str:
    text = "\n\n".join([hook, "\n\n".join(beats[:3]), cta])
    if hashtags:
        text += "\n\n" + " ".join(hashtags)
    return text


def _truncate_to_limit(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    window = text[:limit]
    boundary = max(window.rfind(". "), window.rfind("? "), window.rfind("! "))
    if boundary > 0:
        return window[: boundary + 1].rstrip()
    return window.rstrip()


__all__ = [
    "MAX_POST_CHARS",
    "LinkedInPostDraft",
    "RepurposeInput",
    "repurpose_to_linkedin",
]
