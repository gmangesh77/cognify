# CONTENT-006: Content Humanization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a two-layer content humanization system: prompt engineering at generation time (Layer 1) plus a `humanize` pipeline node with slop scoring, mechanical fixes, and LLM rewrite for flagged sections (Layer 2).

**Architecture:** Slop detection ported from slop-radar (200+ phrases, 14 structural patterns, scoring 0-100). Mechanical fixes (em-dash replacement, hedge stripping) applied to all sections. LLM rewrite triggered only for sections scoring < 70. Humanize node is non-fatal — never blocks the pipeline.

**Tech Stack:** Python 3.12+, LangGraph, LangChain FakeLLM, Pydantic, pytest, structlog, regex

**Spec:** `docs/superpowers/specs/2026-03-20-content-006-content-humanization-design.md`

**Test command:** `uv run pytest --cov=src --cov-report=term-missing`

**Single test:** `uv run pytest tests/path/to/test.py::TestClass::test_name -v`

**Worktree:** `D:\Workbench\github\cognify-content-006` (branch `feature/CONTENT-006-content-humanization`)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `src/models/content_pipeline.py` | Modify | Add Violation, SlopScore models |
| `src/agents/content/slop_phrases.py` | Create | 200+ categorized phrases in 8 categories |
| `src/agents/content/slop_patterns.py` | Create | PatternRule model + 14 structural patterns |
| `src/agents/content/slop_scorer.py` | Create | score_text(), score_section(), rating logic, repetitive openers |
| `src/agents/content/humanizer.py` | Create | fix_mechanical(), rewrite_section() |
| `src/agents/content/humanize_node.py` | Create | make_humanize_node() factory |
| `src/agents/content/pipeline.py` | Modify | Add humanize node between manage_citations and seo_optimize |
| `src/agents/content/outline_generator.py` | Modify | Append style rules to system prompt |
| `src/agents/content/section_drafter.py` | Modify | Append style rules to system prompt |
| `tests/unit/models/test_content_pipeline_models.py` | Modify | Tests for Violation, SlopScore |
| `tests/unit/agents/content/test_slop_scorer.py` | Create | Tests for scoring engine |
| `tests/unit/agents/content/test_humanizer.py` | Create | Tests for mechanical fixes + rewrite |
| `tests/unit/agents/content/test_humanize_node.py` | Create | Tests for pipeline node |
| `tests/unit/agents/content/test_prompt_updates.py` | Create | Tests for prompt style rules |
| `tests/unit/agents/content/test_pipeline.py` | Modify | Test humanize node in full graph |

---

## Task 1: Data Models — Violation, SlopScore

**Files:**
- Modify: `src/models/content_pipeline.py`
- Modify: `tests/unit/models/test_content_pipeline_models.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/unit/models/test_content_pipeline_models.py`:

```python
from src.models.content_pipeline import SlopScore, Violation


class TestViolation:
    def test_construct(self) -> None:
        v = Violation(category="buzzwords", phrase="delve", sentence_index=2)
        assert v.category == "buzzwords"
        assert v.sentence_index == 2

    def test_frozen(self) -> None:
        v = Violation(category="buzzwords", phrase="delve", sentence_index=0)
        with pytest.raises(ValidationError):
            v.phrase = "changed"  # type: ignore[misc]


class TestSlopScore:
    def test_construct(self) -> None:
        v = Violation(category="buzzwords", phrase="delve", sentence_index=0)
        score = SlopScore(
            score=75, rating="MOSTLY_CLEAN",
            violations=[v], phrase_deductions=2, pattern_deductions=0,
        )
        assert score.score == 75
        assert len(score.violations) == 1

    def test_frozen(self) -> None:
        score = SlopScore(
            score=100, rating="HUMAN",
            violations=[], phrase_deductions=0, pattern_deductions=0,
        )
        with pytest.raises(ValidationError):
            score.score = 50  # type: ignore[misc]
```

- [ ] **Step 2: Run tests — should fail**

Run: `uv run pytest tests/unit/models/test_content_pipeline_models.py::TestViolation -v`

- [ ] **Step 3: Add models to content_pipeline.py**

Add after the `SEOResult` class in `src/models/content_pipeline.py`:

```python
class Violation(BaseModel, frozen=True):
    """A single slop violation with location context."""

    category: str
    phrase: str
    sentence_index: int


class SlopScore(BaseModel, frozen=True):
    """Slop detection score for a text section."""

    score: int
    rating: str
    violations: list[Violation]
    phrase_deductions: int
    pattern_deductions: int
```

- [ ] **Step 4: Run tests — should pass**

Run: `uv run pytest tests/unit/models/test_content_pipeline_models.py -v`

- [ ] **Step 5: Run full suite**

Run: `uv run pytest --tb=short -q`

- [ ] **Step 6: Commit**

```bash
git add src/models/content_pipeline.py tests/unit/models/test_content_pipeline_models.py
git commit -m "feat(content-006): add Violation and SlopScore models"
```

---

## Task 2: Slop Phrase Database + Pattern Rules

**Files:**
- Create: `src/agents/content/slop_phrases.py`
- Create: `src/agents/content/slop_patterns.py`

No dedicated tests — these are pure data constants. The scorer tests (Task 3) validate they work correctly.

- [ ] **Step 1: Create slop_phrases.py**

Create `src/agents/content/slop_phrases.py` with the full 200+ phrase list from slop-radar, organized into 8 categories. The file is a single `SLOP_PHRASES: dict[str, list[str]]` constant. Categories: `buzzwords`, `transitions`, `hedges`, `ai_openers`, `overblown`, `corporate`, `fluff`, `meta`.

Port the complete list from the slop-radar `phrases-en.json` file (available in the spec and in this plan's context). Organize by category — the original is a flat list, so categorize each phrase appropriately.

Key phrases to include (not exhaustive — port ALL 200+):

```python
"""Slop phrase database — 200+ AI writing signals.

Categorized phrases ported from slop-radar (MIT license).
Used by the slop scorer to detect AI-generated text patterns.
"""

SLOP_PHRASES: dict[str, list[str]] = {
    "buzzwords": [
        "delve", "delve into", "dive into", "dive deep", "deep dive",
        "leverage", "cutting-edge", "state-of-the-art", "robust",
        "seamless", "seamlessly", "holistic", "synergy", "synergize",
        "paradigm", "paradigm shift", "ecosystem", "harness", "unlock",
        "empower", "empowering", "streamline", "optimize", "foster",
        "curate", "curated", "bespoke", "tailored", "game-changer",
        "game-changing", "revolutionize", "revolutionary", "versatile",
        "innovative", "disrupt", "disruption", "disruptive",
        "catalyze", "orchestrate", "reimagine", "democratize",
        "operationalize", "incentivize", "contextualize", "strategize",
        "elevate", "amplify", "resonate", "ideate",
    ],
    "transitions": [
        "moreover", "furthermore", "in addition", "additionally",
        "in conclusion", "to summarize", "ultimately",
        "last but not least", "firstly", "secondly", "thirdly",
        "in this regard", "to that end", "with that being said",
        "that being said", "having said that", "with that in mind",
        "by the same token", "on the flip side",
    ],
    "hedges": [
        "essentially", "fundamentally", "it is worth noting",
        "it's worth noting", "it is important to note",
        "it's important to note", "interestingly", "indeed",
        "in other words", "that said", "needless to say",
        "arguably", "it could be argued", "one might say",
        "it bears mentioning", "it should be noted",
        "it goes without saying", "all things considered",
    ],
    "ai_openers": [
        "let me break this down", "let me explain",
        "let me walk you through", "here's the thing",
        "here's what you need to know", "here's the deal",
        "let's unpack",
    ],
    "overblown": [
        "unprecedented", "unparalleled", "transformative",
        "groundbreaking", "trailblazing", "pioneering",
        "remarkable", "exceptional", "noteworthy",
        "thought-provoking", "insightful", "profound",
        "meticulous", "meticulously", "intricate", "intricacies",
        "pivotal", "paramount", "indispensable", "imperative",
        "world-class", "best-in-class", "future-proof",
        "bleeding edge", "next-level",
    ],
    "corporate": [
        "stakeholder", "bandwidth", "low-hanging fruit",
        "move the needle", "north star", "value-add",
        "thought leadership", "pain point", "pain points",
        "value proposition", "end-to-end", "turnkey",
        "plug and play", "one-stop shop", "win-win",
        "drill down", "level up", "take it to the next level",
        "on the same page", "reach out", "touch base", "loop in",
        "circle back", "double down", "pivot",
        "actionable", "impactful", "scalable",
    ],
    "fluff": [
        "in today's world", "in today's fast-paced",
        "as we navigate", "navigate the complexities",
        "navigate the landscape", "ever-evolving", "ever-changing",
        "fast-paced", "rapidly evolving", "dynamic landscape",
        "shifting landscape", "in the realm of",
        "at the forefront", "pave the way", "shed light on",
        "at its core", "at the heart of",
        "in the grand scheme", "the crux of the matter",
        "on a broader scale", "for all intents and purposes",
        "in a nutshell", "to put it simply", "in essence",
        "nuanced", "nuanced approach", "myriad", "myriad of",
        "plethora", "a plethora of", "overarching",
        "multifaceted", "akin to",
    ],
    "meta": [
        "in this article", "in this post", "in this guide",
        "in this blog", "in this piece", "in this section",
        "in this tutorial", "in this overview", "in this essay",
        "comprehensive guide", "definitive guide",
        "ultimate guide", "step-by-step guide",
        "serves as a testament", "stands as a testament",
        "a testament to", "key takeaway", "key takeaways",
        "the takeaway", "wrapping up", "to wrap up",
        "in summary", "to sum up", "all in all",
        "without further ado", "food for thought",
    ],
}
```

- [ ] **Step 2: Create slop_patterns.py**

Create `src/agents/content/slop_patterns.py`:

```python
"""Structural pattern rules for AI text detection.

Regex patterns ported from slop-radar (MIT license).
Each pattern has a weight used for score deductions.
"""

from pydantic import BaseModel


class PatternRule(BaseModel, frozen=True):
    """A structural pattern that signals AI-generated text."""

    name: str
    pattern: str
    weight: int
    flags: str = "i"


STRUCTURAL_PATTERNS: list[PatternRule] = [
    PatternRule(
        name="em_dash",
        pattern=r"[\u2014\u2013]",
        weight=3,
    ),
    PatternRule(
        name="let_me_starter",
        pattern=r"^\s*let me \w+",
        weight=3,
        flags="im",
    ),
    PatternRule(
        name="heres_the_thing",
        pattern=r"here'?s (the thing|what|the deal|the kicker)",
        weight=3,
    ),
    PatternRule(
        name="binary_contrast",
        pattern=r"not (just|only|merely|simply) .{5,40}, but (also )?",
        weight=3,
    ),
    PatternRule(
        name="wh_starters",
        pattern=r"^\s*(what makes this|why this matters|why it matters|how this works|what this means)",
        weight=4,
        flags="im",
    ),
    PatternRule(
        name="bullet_overload",
        pattern=r"(^\s*[-*]\s.+\n){6,}",
        weight=4,
        flags="m",
    ),
    PatternRule(
        name="triple_adjective",
        pattern=r"\b\w+(?:ly)?\b,\s+\b\w+(?:ly)?\b,\s+(?:and\s+)?\b\w+(?:ly)?\b\s+\w+",
        weight=2,
    ),
    PatternRule(
        name="meta_reference",
        pattern=r"in this (article|post|guide|blog|piece|section|tutorial|overview|essay)",
        weight=3,
    ),
    PatternRule(
        name="passive_voice",
        pattern=r"\b(is|are|was|were|been|being)\s+\w+ed\b",
        weight=1,
    ),
    PatternRule(
        name="worth_noting",
        pattern=r"^\s*it('s|\s+is)\s+worth\s+(noting|mentioning|highlighting|pointing out)",
        weight=4,
        flags="im",
    ),
    PatternRule(
        name="colon_list_intro",
        pattern=r":\s*\n\s*[-*1]",
        weight=2,
        flags="m",
    ),
    PatternRule(
        name="emoji_header",
        pattern=r"^\s*[\U0001F300-\U0001FAD6]\s+\*\*",
        weight=5,
        flags="m",
    ),
    PatternRule(
        name="number_list_bold",
        pattern=r"^\s*\d+\.\s+\*\*.+\*\*",
        weight=2,
        flags="m",
    ),
    PatternRule(
        name="tldr_pattern",
        pattern=r"(tl;?dr|key takeaway|bottom line|in a nutshell)\s*:?\s*\n",
        weight=3,
        flags="im",
    ),
]
```

- [ ] **Step 3: Run full suite (no new tests yet, just verify no import errors)**

Run: `uv run pytest --tb=short -q`

- [ ] **Step 4: Commit**

```bash
git add src/agents/content/slop_phrases.py src/agents/content/slop_patterns.py
git commit -m "feat(content-006): add slop phrase database and structural pattern rules"
```

---

## Task 3: Slop Scorer

**Files:**
- Create: `src/agents/content/slop_scorer.py`
- Create: `tests/unit/agents/content/test_slop_scorer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/agents/content/test_slop_scorer.py`:

```python
"""Tests for slop scoring engine."""

from src.agents.content.slop_scorer import score_text
from src.models.content_pipeline import SlopScore


class TestScoreText:
    def test_clean_text_scores_high(self) -> None:
        text = (
            "Security researchers found that 40% of companies experienced "
            "a data breach in 2025. The team tested three different "
            "firewall configurations over six months. Results showed "
            "a 60% reduction in unauthorized access attempts. "
            "How did they achieve this?"
        )
        result = score_text(text)
        assert result.score >= 90
        assert result.rating == "HUMAN"

    def test_slop_heavy_text_scores_low(self) -> None:
        text = (
            "Let me delve into this transformative journey. "
            "Moreover, leveraging cutting-edge solutions is crucial. "
            "This holistic approach empowers stakeholders to unlock "
            "unprecedented synergy. Furthermore, it's worth noting "
            "that this innovative paradigm shift is game-changing."
        )
        result = score_text(text)
        assert result.score < 50
        assert result.rating in ("LIKELY_AI", "PURE_SLOP")
        assert len(result.violations) > 5

    def test_phrase_matching_case_insensitive(self) -> None:
        text = "We must LEVERAGE this INNOVATIVE approach."
        result = score_text(text)
        phrases = [v.phrase for v in result.violations]
        assert "leverage" in phrases
        assert "innovative" in phrases

    def test_phrase_matching_whole_word(self) -> None:
        text = "The optimization of this system is important."
        result = score_text(text)
        # "optimize" should NOT match inside "optimization"
        phrases = [v.phrase for v in result.violations if v.phrase == "optimize"]
        assert len(phrases) == 0

    def test_structural_pattern_em_dash(self) -> None:
        text = "This concept \u2014 which is important \u2014 matters."
        result = score_text(text)
        patterns = [v.phrase for v in result.violations if v.category == "pattern"]
        assert "em_dash" in patterns

    def test_question_bonus(self) -> None:
        # Base text with a minor slop phrase to bring score below 95
        base = "This robust system handles security monitoring effectively."
        with_q = base + " What does this mean for the industry?"
        score_no_q = score_text(base).score
        score_with_q = score_text(with_q).score
        # "robust" costs -2, so base ~ 98. With question bonus +5: 103 clamped to 100.
        # But base without question has no bonus: 98. With question: min(100, 98+5)=100.
        # Better assertion: just verify question text scores >= base text
        assert score_with_q >= score_no_q

    def test_sentence_variance_bonus(self) -> None:
        # Varied: short and long sentences mixed
        varied = "Security matters. The team discovered that implementing a comprehensive monitoring solution reduced incident response times by forty percent across all departments."
        # Monotonous: all similar length
        monotonous = "Security is important now. Companies need to act now. Teams should prepare for this. Everyone must be aware now."
        assert score_text(varied).score >= score_text(monotonous).score

    def test_score_clamped_0_100(self) -> None:
        # Extremely sloppy text
        slop = " ".join(["delve leverage innovative transformative"] * 20)
        result = score_text(slop)
        assert result.score >= 0
        assert result.score <= 100

    def test_repetitive_openers_detected(self) -> None:
        text = (
            "The system is secure. The team tested it. "
            "The results were positive. The data shows improvement. "
            "The conclusion is clear."
        )
        result = score_text(text)
        openers = [v for v in result.violations if v.category == "repetitive_opener"]
        assert len(openers) > 0

    def test_passive_voice_density_penalty(self) -> None:
        text = (
            "The system was designed by the team. "
            "Features were added by developers. "
            "Tests were written by engineers. "
            "Code was reviewed by peers."
        )
        result = score_text(text)
        assert result.pattern_deductions > 0
```

- [ ] **Step 2: Run tests — should fail**

Run: `uv run pytest tests/unit/agents/content/test_slop_scorer.py -v`

- [ ] **Step 3: Implement slop_scorer.py**

Create `src/agents/content/slop_scorer.py`:

```python
"""Slop scoring engine — detects AI writing patterns.

Pure functions, no LLM, no I/O. Scores text 0-100 based on
phrase hits, structural patterns, and writing quality signals.
Inspired by slop-radar (MIT license).
"""

import math
import re

import structlog

from src.agents.content.slop_patterns import STRUCTURAL_PATTERNS
from src.agents.content.slop_phrases import SLOP_PHRASES
from src.models.content_pipeline import SectionDraft, SlopScore, Violation

logger = structlog.get_logger()

_PHRASE_PENALTY = 2
_PASSIVE_DENSITY_THRESHOLD = 0.3
_PASSIVE_DENSITY_PENALTY = 10
_QUESTION_BONUS = 5
_VARIANCE_BONUS = 5
_VARIANCE_THRESHOLD = 4.0
_OPENER_THRESHOLD = 0.3
_OPENER_MIN_COUNT = 3
_OPENER_PENALTY = 3
_RE_FLAGS = {"i": re.IGNORECASE, "m": re.MULTILINE, "im": re.IGNORECASE | re.MULTILINE}


def score_text(text: str) -> SlopScore:
    """Score text for AI writing patterns. Returns 0-100."""
    sentences = _split_sentences(text)
    violations: list[Violation] = []
    violations.extend(_scan_phrases(text, sentences))
    pattern_deductions = _scan_patterns(text, violations)
    violations.extend(_check_repetitive_openers(sentences))
    phrase_deductions = sum(_PHRASE_PENALTY for v in violations if v.category != "pattern" and v.category != "repetitive_opener")
    opener_deductions = sum(_OPENER_PENALTY for v in violations if v.category == "repetitive_opener")
    passive_penalty = _check_passive_density(text, sentences)
    bonuses = _calculate_bonuses(text, sentences)
    raw = 100 - phrase_deductions - pattern_deductions - opener_deductions - passive_penalty + bonuses
    score = max(0, min(100, raw))
    return SlopScore(
        score=score,
        rating=_get_rating(score),
        violations=violations,
        phrase_deductions=phrase_deductions + opener_deductions,
        pattern_deductions=pattern_deductions + passive_penalty,
    )


def score_section(section: SectionDraft) -> SlopScore:
    """Score a section draft's body text."""
    return score_text(section.body_markdown)
```

Helper functions (each under 20 lines, max 3 params):

- `_split_sentences(text) -> list[str]` — split on `.!?`, strip, filter empty
- `_scan_phrases(text, sentences) -> list[Violation]` — iterate SLOP_PHRASES categories, match `\b{phrase}\b` case-insensitive, find sentence index for each hit
- `_scan_patterns(text, violations) -> int` — iterate STRUCTURAL_PATTERNS, `re.findall` with mapped flags, append to violations list, return total weighted deductions. Skip `passive_voice` pattern (handled separately by density check)
- `_check_passive_density(text, sentences) -> int` — count passive matches, if ratio > 0.3 return _PASSIVE_DENSITY_PENALTY else 0
- `_check_repetitive_openers(sentences) -> list[Violation]` — extract first word per sentence, count occurrences, flag words appearing > 30% (min 3)
- `_calculate_bonuses(text, sentences) -> int` — +5 for questions, +5 for varied sentence length (stddev > 4)
- `_get_rating(score) -> str` — thresholds: >= 90 HUMAN, >= 70 MOSTLY_CLEAN, >= 50 SUSPICIOUS, >= 30 LIKELY_AI, else PURE_SLOP

IMPORTANT: Keep each helper under 20 lines. The main `score_text` function orchestrates them.

- [ ] **Step 4: Run tests — should pass**

Run: `uv run pytest tests/unit/agents/content/test_slop_scorer.py -v`

- [ ] **Step 5: Run full suite**

Run: `uv run pytest --tb=short -q`

- [ ] **Step 6: Commit**

```bash
git add src/agents/content/slop_scorer.py tests/unit/agents/content/test_slop_scorer.py
git commit -m "feat(content-006): add slop scoring engine with phrase and pattern detection"
```

---

## Task 4: Mechanical Fixer & LLM Rewriter

**Files:**
- Create: `src/agents/content/humanizer.py`
- Create: `tests/unit/agents/content/test_humanizer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/agents/content/test_humanizer.py`:

```python
"""Tests for mechanical text fixes and LLM rewriting."""

import re
from unittest.mock import AsyncMock

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.content.humanizer import fix_mechanical, rewrite_section
from src.agents.content.slop_scorer import score_text
from src.models.content_pipeline import (
    CitationRef,
    SectionDraft,
    SlopScore,
    Violation,
)


def _make_section(text: str) -> SectionDraft:
    return SectionDraft(
        section_index=0,
        title="Test Section",
        body_markdown=text,
        word_count=len(text.split()),
        citations_used=[],
    )


def _make_score(score: int = 50) -> SlopScore:
    return SlopScore(
        score=score,
        rating="SUSPICIOUS",
        violations=[Violation(category="buzzwords", phrase="delve", sentence_index=0)],
        phrase_deductions=4,
        pattern_deductions=0,
    )


class TestFixMechanical:
    def test_replaces_em_dash_with_comma_before_lowercase(self) -> None:
        text = "This concept \u2014 which is important \u2014 matters."
        result = fix_mechanical(text)
        assert "\u2014" not in result
        assert "concept, which" in result

    def test_replaces_em_dash_with_period_before_uppercase(self) -> None:
        text = "The results were clear \u2014 Productivity increased."
        result = fix_mechanical(text)
        assert "\u2014" not in result
        assert "clear. Productivity" in result

    def test_replaces_en_dash(self) -> None:
        text = "The system \u2013 a new approach \u2013 worked well."
        result = fix_mechanical(text)
        assert "\u2013" not in result

    def test_normalizes_whitespace(self) -> None:
        text = "Word   word  \n\n\n  word."
        result = fix_mechanical(text)
        assert "   " not in result

    def test_preserves_citations(self) -> None:
        text = "This is important [1] \u2014 very important [2]."
        result = fix_mechanical(text)
        assert "[1]" in result
        assert "[2]" in result


class TestRewriteSection:
    async def test_returns_updated_section(self) -> None:
        section = _make_section("Let me delve into this transformative topic [1].")
        llm = FakeListChatModel(responses=[
            "This topic covers important ground [1]."
        ])
        result = await rewrite_section(section, _make_score(), llm)
        assert isinstance(result, SectionDraft)
        assert result.word_count > 0
        assert result.body_markdown != section.body_markdown

    async def test_preserves_citations(self) -> None:
        section = _make_section("The data shows [1] that leverage is key [2].")
        llm = FakeListChatModel(responses=[
            "The data shows [1] that this approach works [2]."
        ])
        result = await rewrite_section(section, _make_score(), llm)
        assert "[1]" in result.body_markdown
        assert "[2]" in result.body_markdown

    async def test_rejects_rewrite_if_citations_lost(self) -> None:
        section = _make_section("Important finding [1] and another [2].")
        llm = FakeListChatModel(responses=[
            "Important finding without any citations."
        ])
        result = await rewrite_section(section, _make_score(), llm)
        # Should keep original since citations were lost
        assert result.body_markdown == section.body_markdown

    async def test_single_attempt_no_retry(self) -> None:
        """LLM is called exactly once, even if rewrite still has slop."""
        section = _make_section("Let me delve into this transformative topic [1].")
        # Response still contains slop — but only one response provided
        llm = FakeListChatModel(responses=[
            "Let me explore this innovative concept [1]."
        ])
        result = await rewrite_section(section, _make_score(), llm)
        # Should return the (still sloppy) rewrite, not retry
        assert result.body_markdown == "Let me explore this innovative concept [1]."
```

- [ ] **Step 2: Run tests — should fail**

Run: `uv run pytest tests/unit/agents/content/test_humanizer.py -v`

- [ ] **Step 3: Implement humanizer.py**

Create `src/agents/content/humanizer.py`:

```python
"""Mechanical text fixes and LLM rewriting for humanization.

fix_mechanical() applies regex-based fixes (em-dash replacement,
whitespace normalization). rewrite_section() calls the LLM to
fix sections with high slop scores.
"""

import re

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from src.models.content_pipeline import SectionDraft, SlopScore

logger = structlog.get_logger()

_CITATION_PATTERN = re.compile(r"\[(\d+)\]")

_REWRITE_SYSTEM = (
    "You are an editor making AI-generated text sound natural. "
    "Rewrite the section to fix the listed issues. Keep all factual "
    "claims and [N] citations exactly as they are. Do not change the "
    "meaning. Only fix the writing style."
)


def fix_mechanical(text: str) -> str:
    """Apply regex-based text fixes. No LLM."""
    text = _replace_dashes(text)
    text = _normalize_whitespace(text)
    return text


async def rewrite_section(
    section: SectionDraft,
    slop_score: SlopScore,
    llm: BaseChatModel,
) -> SectionDraft:
    """Rewrite a section via LLM to fix slop violations."""
    original_citations = set(_CITATION_PATTERN.findall(section.body_markdown))
    rewritten = await _call_rewrite(section, slop_score, llm)
    if not _citations_preserved(rewritten, original_citations):
        logger.warning("humanize_citations_lost", section_index=section.section_index)
        return section
    return _build_rewritten_draft(section, rewritten)
```

Helper functions (each under 20 lines):

- `_replace_dashes(text) -> str` — regex to replace `—` and `–`. Pattern: `r"\s*[\u2014\u2013]\s*"`. Check char after dash: if lowercase → `, `. If uppercase or end → `. ` + capitalize.
- `_normalize_whitespace(text) -> str` — collapse multiple spaces, normalize newlines
- `_call_rewrite(section, score, llm) -> str` — build prompt with violations list, call LLM, return `str(response.content)`
- `_build_violations_text(score) -> str` — format violations as "Sentence N: category 'phrase'" for the prompt
- `_citations_preserved(text, original) -> bool` — check all original `[N]` refs still present
- `_build_rewritten_draft(section, text) -> SectionDraft` — create new SectionDraft with updated body and word count

- [ ] **Step 4: Run tests — should pass**

Run: `uv run pytest tests/unit/agents/content/test_humanizer.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/agents/content/humanizer.py tests/unit/agents/content/test_humanizer.py
git commit -m "feat(content-006): add mechanical text fixer and LLM section rewriter"
```

---

## Task 5: Humanize Node Factory

**Files:**
- Create: `src/agents/content/humanize_node.py`
- Create: `tests/unit/agents/content/test_humanize_node.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/agents/content/test_humanize_node.py`:

```python
"""Tests for the humanize pipeline node."""

from unittest.mock import AsyncMock

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.content.humanize_node import make_humanize_node
from src.models.content_pipeline import CitationRef, SectionDraft


def _make_drafts() -> list[SectionDraft]:
    return [
        SectionDraft(
            section_index=0,
            title="Clean Section",
            body_markdown="Security researchers found a 40% increase in breaches [1]. The team responded quickly.",
            word_count=12,
            citations_used=[CitationRef(index=1, source_url="https://a.com", source_title="A")],
        ),
        SectionDraft(
            section_index=1,
            title="Sloppy Section",
            body_markdown="Let me delve into this transformative journey. Moreover, leveraging cutting-edge solutions is crucial [1]. Furthermore, this holistic approach empowers stakeholders.",
            word_count=20,
            citations_used=[CitationRef(index=1, source_url="https://a.com", source_title="A")],
        ),
    ]


class TestHumanizeNode:
    async def test_rewrites_low_scoring_sections(self) -> None:
        llm = FakeListChatModel(responses=[
            "This approach focuses on practical solutions [1]. The team found concrete improvements."
        ])
        node = make_humanize_node(llm)
        state = {"section_drafts": _make_drafts(), "status": "draft_complete"}
        result = await node(state)
        drafts = result["section_drafts"]
        assert len(drafts) == 2
        # Sloppy section should have been rewritten
        assert "delve" not in drafts[1].body_markdown.lower() or drafts[1].body_markdown != _make_drafts()[1].body_markdown

    async def test_never_returns_failed_status(self) -> None:
        llm = FakeListChatModel(responses=[])  # will error
        node = make_humanize_node(llm)
        state = {"section_drafts": _make_drafts(), "status": "draft_complete"}
        result = await node(state)
        assert result.get("status") != "failed"
        assert "section_drafts" in result

    async def test_mechanical_fixes_applied_to_all(self) -> None:
        drafts = [
            SectionDraft(
                section_index=0, title="Dash Section",
                body_markdown="The results \u2014 which were good \u2014 improved.",
                word_count=7,
                citations_used=[],
            ),
        ]
        llm = FakeListChatModel(responses=[])
        node = make_humanize_node(llm)
        state = {"section_drafts": drafts, "status": "draft_complete"}
        result = await node(state)
        assert "\u2014" not in result["section_drafts"][0].body_markdown
```

- [ ] **Step 2: Run tests — should fail**

Run: `uv run pytest tests/unit/agents/content/test_humanize_node.py -v`

- [ ] **Step 3: Implement humanize_node.py**

Create `src/agents/content/humanize_node.py`:

```python
"""Humanize node factory for the content pipeline graph.

Applies mechanical fixes to all sections, then scores each.
Sections scoring < 70 get an LLM rewrite attempt.
Non-fatal — never sets status to failed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from langchain_core.language_models import BaseChatModel

from src.agents.content.humanizer import fix_mechanical, rewrite_section
from src.agents.content.slop_scorer import score_section
from src.models.content_pipeline import SectionDraft

if TYPE_CHECKING:
    from src.agents.content.pipeline import ContentState

logger = structlog.get_logger()

_REWRITE_THRESHOLD = 70


def make_humanize_node(llm: BaseChatModel) -> Any:
    """Factory: returns async node function for humanize step."""

    async def humanize_node(state: ContentState) -> dict[str, object]:
        try:
            return await _run_humanize(state, llm)
        except Exception as exc:
            logger.error("humanize_failed", error=str(exc))
            return {"section_drafts": state.get("section_drafts", [])}

    return humanize_node
```

The `_run_humanize(state, llm)` function:
1. **Guard**: if `state.get("status") == "failed"`, return `{"section_drafts": state.get("section_drafts", [])}` immediately (skip humanization on already-failed pipeline)
2. Coerce section_drafts from state
3. Apply `fix_mechanical` to each section
3. Score each with `score_section`
4. For sections < 70: `rewrite_section`, then `fix_mechanical` again
5. Log metrics
6. Return `{"section_drafts": updated}`

Keep `_run_humanize` under 20 lines by extracting `_humanize_section(section, llm)` helper.

- [ ] **Step 4: Run tests — should pass**

Run: `uv run pytest tests/unit/agents/content/test_humanize_node.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/agents/content/humanize_node.py tests/unit/agents/content/test_humanize_node.py
git commit -m "feat(content-006): add humanize node factory for content pipeline"
```

---

## Task 6: Pipeline Wiring + Prompt Engineering

**Files:**
- Modify: `src/agents/content/pipeline.py`
- Modify: `src/agents/content/outline_generator.py`
- Modify: `src/agents/content/section_drafter.py`
- Modify: `tests/unit/agents/content/test_pipeline.py`
- Create: `tests/unit/agents/content/test_prompt_updates.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/unit/agents/content/test_pipeline.py`:

```python
class TestContentPipelineWithHumanize:
    async def test_humanize_node_in_full_graph(self) -> None:
        """Full pipeline includes humanize node and produces section_drafts."""
        # Needs enough FakeLLM responses for: outline, queries, drafts, citations,
        # humanize rewrite (if triggered), SEO, discoverability
        # The exact response count depends on how many sections score < 70
        # Use clean draft text to avoid triggering rewrites
        responses = [
            _outline_json(),
            _queries_json(2),
            "Security researchers found a 40% increase [1].",  # clean section 0
            "The team tested three configurations [1].",       # clean section 1
            _seo_json(),
            _discoverability_json(),
        ]
        llm = FakeListChatModel(responses=responses)
        retriever = _mock_retriever()
        graph = build_content_graph(llm, retriever=retriever)
        result = await graph.ainvoke({
            "topic": _make_topic(),
            "research_plan": _make_plan(),
            "findings": _make_findings(),
            "session_id": uuid4(),
            "outline": None,
            "status": "outline_generating",
            "error": None,
        })
        assert result.get("section_drafts") is not None
        assert len(result["section_drafts"]) == 2
```

Create `tests/unit/agents/content/test_prompt_updates.py`:

```python
"""Tests for humanization style rules in generation prompts."""

from src.agents.content.outline_generator import _SYSTEM_PROMPT as OUTLINE_PROMPT
from src.agents.content.section_drafter import _SYSTEM_PROMPT as DRAFTER_PROMPT


class TestPromptStyleRules:
    def test_outline_prompt_has_em_dash_rule(self) -> None:
        assert "em-dash" in OUTLINE_PROMPT.lower() or "em dash" in OUTLINE_PROMPT.lower()

    def test_drafter_prompt_has_transition_rule(self) -> None:
        assert "moreover" in DRAFTER_PROMPT.lower() or "formal transition" in DRAFTER_PROMPT.lower()

    def test_drafter_prompt_has_buzzword_rule(self) -> None:
        assert "delve" in DRAFTER_PROMPT.lower() or "buzzword" in DRAFTER_PROMPT.lower()

    def test_drafter_prompt_has_tone_rule(self) -> None:
        assert "conversational" in DRAFTER_PROMPT.lower() or "natural" in DRAFTER_PROMPT.lower()
```

- [ ] **Step 2: Run tests — should fail**

Run: `uv run pytest tests/unit/agents/content/test_prompt_updates.py tests/unit/agents/content/test_pipeline.py::TestContentPipelineWithHumanize -v`

- [ ] **Step 3: Wire humanize node into pipeline.py**

Update `src/agents/content/pipeline.py`:

Add import:
```python
from src.agents.content.humanize_node import make_humanize_node
```

Add node:
```python
graph.add_node("humanize", make_humanize_node(llm))
```

Change edges — replace:
```python
graph.add_edge("manage_citations", "seo_optimize")
```
With:
```python
graph.add_edge("manage_citations", "humanize")
graph.add_edge("humanize", "seo_optimize")
```

- [ ] **Step 4: Update outline_generator.py prompt**

Append to `_SYSTEM_PROMPT` in `src/agents/content/outline_generator.py`:

```python
_SYSTEM_PROMPT = (
    "You are an expert content strategist. Generate a structured "
    "article outline from research findings. The outline should have "
    "4-8 sections with narrative flow: introduction, findings, "
    "analysis, and conclusion. "
    "Do not use em-dashes. Use periods or commas instead. "
    "Avoid formal transitions like moreover, furthermore, in conclusion. "
    "Write in a natural conversational tone. Vary sentence length. "
    "Be specific and concrete, not abstract. "
    "Respond with valid JSON only."
)
```

- [ ] **Step 5: Update section_drafter.py prompt**

Append to `_SYSTEM_PROMPT` in `src/agents/content/section_drafter.py`:

```python
_SYSTEM_PROMPT = (
    "You are an expert long-form writer. Draft a section of an article "
    "using the provided research context. Every factual claim must include "
    "an inline citation like [1], [2] referencing the numbered sources. "
    "Write in a clear, authoritative tone. Target approximately "
    "{target_word_count} words. "
    "Do not use em-dashes or en-dashes. Use periods or commas instead. "
    "Avoid words like delve, leverage, innovative, transformative, unprecedented. "
    "Skip transitions like moreover, furthermore, additionally. "
    "Vary sentence length and structure. "
    "Write as a knowledgeable human, not an AI assistant."
)
```

- [ ] **Step 6: Run tests — should pass**

Run: `uv run pytest tests/unit/agents/content/test_pipeline.py tests/unit/agents/content/test_prompt_updates.py -v`

- [ ] **Step 7: Run full suite**

Run: `uv run pytest --tb=short -q`

IMPORTANT: Existing pipeline tests use draft text like `"Draft section 0 [1]."` and `"Draft section 1 [1]."`. These are short, clean sentences with no slop phrases or structural patterns — they will score well above 70 (likely 95-100), so the humanize node will apply only mechanical fixes (no em-dashes to replace either) and will NOT trigger an LLM rewrite. No additional FakeLLM responses are needed for existing tests. The humanize node's early-return guard also skips processing if `status == "failed"`, so failure-path tests are unaffected. If any existing test breaks, the fix is to either add a clean rewrite response or update the draft text — but this should not be necessary.

- [ ] **Step 8: Commit**

```bash
git add src/agents/content/pipeline.py src/agents/content/outline_generator.py src/agents/content/section_drafter.py tests/unit/agents/content/test_pipeline.py tests/unit/agents/content/test_prompt_updates.py
git commit -m "feat(content-006): wire humanize node and update prompts with style rules"
```

---

## Task 7: Final Integration Test & Cleanup

**Files:**
- All modified files

- [ ] **Step 1: Run full test suite with coverage**

Run: `uv run pytest --cov=src --cov-report=term-missing --tb=short`

- [ ] **Step 2: Run linting**

Run: `uv run ruff check src/ && uv run ruff format --check src/`

- [ ] **Step 3: Run type checking**

Run: `uv run mypy src/`

- [ ] **Step 4: Format code**

Run: `uv run ruff format src/ tests/`

- [ ] **Step 5: Final commit if needed**

```bash
git add -u
git commit -m "chore(content-006): format, fix lint, update types"
```

- [ ] **Step 6: Update PROGRESS.md**

Change CONTENT-006 row to In Progress with branch and plan/spec links:

```
| CONTENT-006 | Content Humanization        | In Progress | `feature/CONTENT-006-content-humanization` | [plan](../docs/superpowers/plans/2026-03-20-content-006-content-humanization.md) | [spec](../docs/superpowers/specs/2026-03-20-content-006-content-humanization-design.md) |
```

```bash
git add project-management/PROGRESS.md
git commit -m "docs: update PROGRESS.md — CONTENT-006 in progress"
```
