"""Tests for repurpose_to_linkedin (AUTHOR-013)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage, SystemMessage

from src.agents.prompts import DEFAULT_PROMPTS, bind_prompt_overrides
from src.models.content import CanonicalArticle
from src.services.publishing.linkedin.repurpose import (
    MAX_POST_CHARS,
    RepurposeInput,
    repurpose_to_linkedin,
)

VALID_JSON = (
    '{"hook": "AI agents are eating the backlog.", '
    '"beats": ["First beat expands claim one.", '
    '"Second beat expands claim two.", '
    '"Third beat wraps it up nicely."], '
    '"cta": "Read the full article for the details.", '
    '"hashtags": ["AI", "Agentic-AI", "ai", "DevOps", "Cloud", "Security"]}'
)


def _long_beats_json() -> str:
    # Many short "sentence. " runs so a real sentence boundary exists well
    # before the 3,000-char cutoff (a single unbroken run of characters,
    # as in one giant word, would have no boundary to truncate at).
    filler = "This is filler text for length. " * 120
    return (
        '{"hook": "Short hook.", '
        f'"beats": ["Beat one. {filler}", "Beat two.", "Beat three."], '
        '"cta": "Read more.", "hashtags": ["ai", "cloud"]}'
    )


class TestRepurposeToLinkedin:
    async def test_draft_fields_and_assembly(
        self, sample_article: CanonicalArticle
    ) -> None:
        llm = FakeListChatModel(responses=[VALID_JSON])
        draft = await repurpose_to_linkedin(RepurposeInput(article=sample_article), llm)

        assert draft.hook == "AI agents are eating the backlog."
        assert draft.beats == [
            "First beat expands claim one.",
            "Second beat expands claim two.",
            "Third beat wraps it up nicely.",
        ]
        assert draft.cta == "Read the full article for the details."
        # hashtags: sanitised, deduped (AI/ai collide), capped at 5
        assert draft.hashtags == ["#ai", "#agenticai", "#devops", "#cloud", "#security"]
        # assembly order: hook, beats, cta, hashtags
        assert draft.text.startswith(draft.hook)
        assert draft.cta in draft.text
        assert draft.text.endswith(" ".join(draft.hashtags))
        assert draft.char_count == len(draft.text)
        assert isinstance(draft.slop_score, int)
        assert draft.truncated is False

    async def test_over_limit_then_short_reply_uses_second(
        self, sample_article: CanonicalArticle
    ) -> None:
        llm = FakeListChatModel(
            responses=[_long_beats_json(), VALID_JSON],
        )
        draft = await repurpose_to_linkedin(RepurposeInput(article=sample_article), llm)
        assert draft.truncated is False
        assert draft.hook == "AI agents are eating the backlog."
        assert len(draft.text) <= MAX_POST_CHARS

    async def test_both_over_limit_truncates_at_sentence_boundary(
        self, sample_article: CanonicalArticle
    ) -> None:
        llm = FakeListChatModel(
            responses=[_long_beats_json(), _long_beats_json()],
        )
        draft = await repurpose_to_linkedin(RepurposeInput(article=sample_article), llm)
        assert draft.truncated is True
        assert len(draft.text) <= MAX_POST_CHARS
        # truncated at a sentence boundary — ends with terminal punctuation
        assert draft.text.rstrip()[-1] in ".?!"

    async def test_garbage_twice_raises(self, sample_article: CanonicalArticle) -> None:
        llm = FakeListChatModel(responses=["not json", "still not json"])
        with pytest.raises(ValueError, match="unparseable"):
            await repurpose_to_linkedin(RepurposeInput(article=sample_article), llm)

    async def test_bound_system_override_reaches_system_message(
        self, sample_article: CanonicalArticle
    ) -> None:
        llm = AsyncMock()
        llm.ainvoke.return_value = AIMessage(content=VALID_JSON)
        key = "linkedin_repurpose.system"
        override = "CUSTOM SYSTEM PROMPT FOR LINKEDIN"
        with bind_prompt_overrides({key: override}):
            await repurpose_to_linkedin(RepurposeInput(article=sample_article), llm)
        messages = llm.ainvoke.call_args_list[0].args[0]
        system_messages = [m for m in messages if isinstance(m, SystemMessage)]
        assert system_messages
        assert system_messages[0].content == override
        assert DEFAULT_PROMPTS[key].template != override
