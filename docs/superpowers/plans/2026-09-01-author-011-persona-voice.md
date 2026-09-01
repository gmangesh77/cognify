# AUTHOR-011 Persona Voice Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Author/brand voice personas built from pasted writing samples — stdlib stylometric fingerprint → confidence-gated prompt block + few-shot → per-section voice score → one targeted fix pass — with a Settings Personas tab and a Voice-match chip on the article.

**Architecture:** New pure package `src/services/persona/` (fingerprint, scoring, few_shot, prompt_block, voice_context), `personas` + `persona_samples` tables + repo, `/personas` API, `voice_persona_id` plumbed brief → session → `ContentState`, two flagged graph nodes (`score_voice` pure, `fix_voice_deviations` LLM) after `humanize`, voice fields persisted on `canonical_articles`, frontend Personas tab + Voice select + chip. Feature flag `COGNIFY_ENABLE_VOICE_ENGINE` (default false) keeps the default pipeline byte-identical.

**Tech Stack:** Python 3.12 / FastAPI / LangGraph / SQLAlchemy async + Alembic / pydantic v2 / numpy (existing) / pytest-asyncio; Next.js 15 / React 19 / TanStack Query / Vitest.

**Spec:** `docs/superpowers/specs/2026-09-01-author-011-persona-voice-design.md` (binding). Deviation from spec §4.4 approved here: ONE registry key `voice.dim_line` with the per-dimension labels in code (instead of 13 `voice.dim.<name>` keys) — 5 registry keys total: `voice.block_intro`, `voice.dim_line`, `voice.samples_intro`, `voice.fix.system`, `voice.fix.user`. Deviation from §4.1: 13 dims (the spec listed 12 and named 13 — `first_person_rate` is the 13th).

## Global Constraints

- Functions < 20 lines, files < 200 lines, max 3 positional params (bundle with frozen dataclasses / keyword-only), no `Any`, named exports; L-001 `model_dump(mode="json")` for JSONB; L-002 `parse_llm_json` for LLM JSON (the fix node returns plain text, not JSON); L-014 prompts are registry keys (`render_prompt`), never module constants; route decorator OUTERMOST, `@limiter.limit` innermost.
- TDD per task: failing test → run → implement → run → commit. Backend tests: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest …` (a set key hangs app import on Milvus). Frontend: `cd frontend && npx vitest run …`; `frontend/src/file-size-budget.test.ts` enforces ≤ 200 lines under `src/app` + `src/components`.
- **Byte-identical default pipeline**: with `COGNIFY_ENABLE_VOICE_ENGINE=false` (default) the graph node set and every prompt are unchanged; with the flag on but no persona on the session, both nodes return `{}`.
- Existing `audience_persona` (8 keys, image style) is untouched; the voice persona is a separate `voice_persona_id: UUID | None` everywhere.
- Branch `feature/AUTHOR-011-persona-voice` in worktree `.claude/worktrees/author-011-voice`; **local only — never push**. Conventional commits ending with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_01MxA5LxaxT1si7an6Pu5wG2`.
- Settings: `enable_voice_engine: bool = False`, `voice_fix_threshold: int = 70` (env `COGNIFY_ENABLE_VOICE_ENGINE`, `COGNIFY_VOICE_FIX_THRESHOLD`). Constants: `MIN_SAMPLES = 5`, `MIN_SAMPLE_WORDS = 150`, `CONFIDENCE_FULL_N = 8`, `MIN_CONFIDENCE = 0.5`, `DEVIATION_Z = 1.5`, `SHORT_SECTION_WORDS = 60`, `FEW_SHOT_K = 3`, `EXCERPT_WORDS = 120`.
- Tracked step names `content_score_voice`, `content_fix_voice` (added to `KNOWN_LLM_STEPS`).
- Migration id `f3b8d1c6a2e4`, `down_revision = "e2a7c4d9b1f3"` (verify with `uv run alembic heads` first).

---

## File structure

| File | Responsibility |
|---|---|
| `src/models/persona.py` | `Persona`, `PersonaCreate`, `PersonaUpdate`, `PersonaSample`, `SampleCreate`, `DimStat`, `VoiceFingerprint`, `DimScore`, `VoiceDeviation`, `VoiceScore` |
| `src/services/persona/__init__.py` | re-exports |
| `src/services/persona/fingerprint.py` | `text_features`, `build_fingerprint`, `InsufficientSamples`, `DIMENSIONS`, `DIM_LABELS` |
| `src/services/persona/scoring.py` | `score_text`, `score_sections`, `band_for` |
| `src/services/persona/few_shot.py` | `pick_samples`, `excerpt` |
| `src/services/persona/prompt_block.py` | `build_voice_block` |
| `src/services/persona/voice_context.py` | `build_voice_state` (persona → state dict) |
| `src/agents/prompts/defaults_voice.py` | the 5 `voice.*` registry keys |
| `src/db/tables_personas.py`, `src/db/persona_repository.py`, `alembic/versions/f3b8d1c6a2e4_add_personas.py` | storage |
| `src/api/schemas/personas.py`, `src/api/routers/personas.py` | API |
| `src/agents/content/voice_nodes.py` | `make_score_voice_node`, `make_fix_voice_node`, `make_voice_router` |
| `frontend/src/types/persona.ts`, `lib/api/personas.ts`, `hooks/use-personas.ts` | client API |
| `frontend/src/components/settings/personas-settings.tsx`, `personas-list.tsx`, `persona-editor.tsx`, `persona-samples.tsx` | Settings tab |
| `frontend/src/components/topics/voice-select.tsx`, `frontend/src/components/articles/voice-match-chip.tsx` | selection + chip |

---

### Task 1: Settings flag, persona models, stdlib fingerprint

**Files:**
- Modify: `src/config/settings.py` (after `require_outline_approval`, line 208)
- Create: `src/models/persona.py`, `src/services/persona/__init__.py`, `src/services/persona/fingerprint.py`
- Test: `tests/unit/services/persona/__init__.py` (empty), `tests/unit/services/persona/test_fingerprint.py`

**Interfaces:**
- Produces: `Settings.enable_voice_engine: bool = False`, `Settings.voice_fix_threshold: int = 70`; models listed in the file table; `text_features(text: str) -> dict[str, float]` (13 keys = `DIMENSIONS`); `build_fingerprint(samples: list[str]) -> VoiceFingerprint` raising `InsufficientSamples`; `DIM_LABELS: dict[str, str]`; constants `MIN_SAMPLES`, `MIN_SAMPLE_WORDS`, `CONFIDENCE_FULL_N`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/services/persona/test_fingerprint.py
"""AUTHOR-011 — stdlib stylometric fingerprint."""

from __future__ import annotations

import pytest

from src.services.persona.fingerprint import (
    CONFIDENCE_FULL_N,
    DIMENSIONS,
    MIN_SAMPLES,
    InsufficientSamples,
    build_fingerprint,
    text_features,
)

SHORT = "We ship small. It works. Teams win."  # 3 sentences, 8 words
LONG_SENTENCES = (
    "When a platform team decides to rebuild its deployment pipeline from scratch "
    "without first measuring where the current one actually loses time, the result "
    "is usually a beautiful system that solves yesterday's problem. "
    "Measurement before architecture is not glamorous, but it is the only way to "
    "know whether the rebuild was worth the quarter it consumed."
)


def _sample(seed: int, words: int = 160) -> str:
    base = [
        "I think the honest answer is that we don't know yet.",
        "Small steps compound; big rewrites stall.",
        "Perhaps the team could try it for a week?",
        "Clearly the data supports a slower rollout.",
    ]
    out: list[str] = []
    i = seed
    while sum(len(s.split()) for s in out) < words:
        out.append(base[i % len(base)])
        i += 1
    return "\n\n".join(" ".join(out[j : j + 3]) for j in range(0, len(out), 3))


class TestTextFeatures:
    def test_returns_every_dimension(self) -> None:
        feats = text_features(SHORT)
        assert set(feats) == set(DIMENSIONS)

    def test_sentence_length_mean_and_std(self) -> None:
        feats = text_features(SHORT)
        assert feats["sentence_len_mean"] == pytest.approx(8 / 3, abs=0.01)
        assert feats["sentence_len_std"] > 0

    def test_longer_sentences_raise_fk_grade(self) -> None:
        assert text_features(LONG_SENTENCES)["fk_grade"] > text_features(SHORT)["fk_grade"]

    def test_contractions_hedges_boosters_first_person(self) -> None:
        feats = text_features("I don't think so. Perhaps we'll see. Clearly I'm right.")
        assert feats["contraction_rate"] > 0
        assert feats["hedge_rate"] > 0
        assert feats["booster_rate"] > 0
        assert feats["first_person_rate"] > 0

    def test_punctuation_per_1k_words(self) -> None:
        feats = text_features("One, two; three — four? Five.")
        assert feats["punct_comma_per_1k"] == pytest.approx(200.0)
        assert feats["punct_semicolon_per_1k"] == pytest.approx(200.0)
        assert feats["punct_dash_per_1k"] == pytest.approx(200.0)
        assert feats["punct_question_per_1k"] == pytest.approx(200.0)

    def test_markdown_structure_is_ignored(self) -> None:
        md = "## Heading\n\n```python\nx = 1; y = 2; z = 3\n```\n\nPlain prose here. More prose."
        feats = text_features(md)
        assert feats["punct_semicolon_per_1k"] == 0.0

    def test_empty_text_is_all_zero(self) -> None:
        assert all(v == 0.0 for v in text_features("").values())


class TestBuildFingerprint:
    def test_requires_min_samples_of_min_words(self) -> None:
        with pytest.raises(InsufficientSamples):
            build_fingerprint([_sample(i) for i in range(MIN_SAMPLES - 1)])
        with pytest.raises(InsufficientSamples):
            build_fingerprint([SHORT] * MIN_SAMPLES)

    def test_fingerprint_has_stats_per_dimension(self) -> None:
        fp = build_fingerprint([_sample(i) for i in range(MIN_SAMPLES)])
        assert fp.sample_count == MIN_SAMPLES
        assert set(fp.dims) == set(DIMENSIONS)
        stat = fp.dims["sentence_len_mean"]
        assert stat.mean > 0 and stat.stddev >= 0 and 0 <= stat.confidence <= 1

    def test_confidence_grows_with_sample_count(self) -> None:
        few = build_fingerprint([_sample(i) for i in range(MIN_SAMPLES)])
        many = build_fingerprint([_sample(i) for i in range(CONFIDENCE_FULL_N)])
        assert many.dims["sentence_len_mean"].confidence > few.dims["sentence_len_mean"].confidence

    def test_confidence_falls_with_spread(self) -> None:
        tight = build_fingerprint([_sample(0)] * MIN_SAMPLES)
        wild = build_fingerprint([_sample(i) for i in range(MIN_SAMPLES - 1)] + [LONG_SENTENCES * 12])
        assert tight.dims["sentence_len_mean"].confidence >= wild.dims["sentence_len_mean"].confidence
```

- [ ] **Step 2: Run to verify it fails**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/services/persona/test_fingerprint.py -q`
Expected: FAIL — `ModuleNotFoundError: src.services.persona`

- [ ] **Step 3: Implement**

`src/config/settings.py` — after line 208 (`require_outline_approval: bool = False`):
```python
    # Persona voice engine (AUTHOR-011). Off by default: with False the
    # score_voice / fix_voice_deviations nodes are not added to the graph.
    enable_voice_engine: bool = False
    voice_fix_threshold: int = 70  # sections scoring below get ONE fix pass
```

```python
# src/models/persona.py
"""Persona voice engine models (AUTHOR-011)."""

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

VoiceBand = Literal["match", "close", "off_voice"]


class DimStat(BaseModel, frozen=True):
    mean: float
    stddev: float
    confidence: float = Field(ge=0.0, le=1.0)


class VoiceFingerprint(BaseModel, frozen=True):
    dims: dict[str, DimStat]
    sample_count: int


class DimScore(BaseModel, frozen=True):
    value: float
    z: float
    confidence: float


class VoiceDeviation(BaseModel, frozen=True):
    dim: str
    observed: float
    target: float
    message: str


class VoiceScore(BaseModel, frozen=True):
    score: int = Field(ge=0, le=100)
    band: VoiceBand
    per_dim: dict[str, DimScore]
    deviations: list[VoiceDeviation]


class PersonaSample(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    persona_id: UUID
    text: str
    word_count: int
    embedding: list[float] | None = None
    created_at: datetime


class SampleCreate(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)


class PersonaCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class PersonaUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class Persona(BaseModel):
    id: UUID
    owner_id: str
    name: str
    description: str | None
    fingerprint: VoiceFingerprint | None
    sample_count: int
    created_at: datetime
    updated_at: datetime
```

```python
# src/services/persona/__init__.py
"""Persona voice engine (AUTHOR-011): fingerprint → block → score → fix."""

from src.services.persona.fingerprint import (
    DIM_LABELS,
    DIMENSIONS,
    InsufficientSamples,
    build_fingerprint,
    text_features,
)

__all__ = [
    "DIMENSIONS",
    "DIM_LABELS",
    "InsufficientSamples",
    "build_fingerprint",
    "text_features",
]
```

```python
# src/services/persona/fingerprint.py
"""Stylometric fingerprint — stdlib only (spec §4.1)."""

from __future__ import annotations

import re
import statistics

from src.models.persona import DimStat, VoiceFingerprint
from src.utils.markdown_structure import (
    extract_humanizable_text,
    humanizable_blocks,
    parse_markdown_blocks,
)

MIN_SAMPLES = 5
MIN_SAMPLE_WORDS = 150
CONFIDENCE_FULL_N = 8
_TTR_WINDOW = 500

DIMENSIONS: tuple[str, ...] = (
    "sentence_len_mean", "sentence_len_std", "fk_grade", "ttr",
    "contraction_rate", "hedge_rate", "booster_rate",
    "punct_comma_per_1k", "punct_semicolon_per_1k", "punct_dash_per_1k",
    "punct_question_per_1k", "paragraph_len_mean", "first_person_rate",
)
DIM_LABELS: dict[str, str] = {
    "sentence_len_mean": "average sentence length (words)",
    "sentence_len_std": "sentence length variation",
    "fk_grade": "reading grade level",
    "ttr": "vocabulary variety (type-token ratio)",
    "contraction_rate": "contractions per 100 words",
    "hedge_rate": "hedging words per 100 words",
    "booster_rate": "booster words per 100 words",
    "punct_comma_per_1k": "commas per 1,000 words",
    "punct_semicolon_per_1k": "semicolons per 1,000 words",
    "punct_dash_per_1k": "dashes per 1,000 words",
    "punct_question_per_1k": "questions per 1,000 words",
    "paragraph_len_mean": "average paragraph length (words)",
    "first_person_rate": "first-person words per 100 words",
}

_HEDGES = frozenset("maybe perhaps possibly likely probably seems appears might could somewhat arguably generally often sometimes tends suggest suggests".split())
_BOOSTERS = frozenset("clearly obviously certainly definitely absolutely always never undoubtedly must essential critical crucial extremely highly truly".split())
_FIRST_PERSON = frozenset("i i'm i've i'd i'll me my mine we we're we've we'd our ours us".split())
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z']*")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_CONTRACTION_RE = re.compile(r"\b\w+'(?:t|s|re|ve|ll|d|m)\b", re.IGNORECASE)
_DASH_RE = re.compile(r"[\u2014\u2013]|(?<=\s)-(?=\s)|--")


class InsufficientSamples(ValueError):
    """Fewer than MIN_SAMPLES samples of MIN_SAMPLE_WORDS words."""


def _prose(text: str) -> str:
    blocks = parse_markdown_blocks(text)
    parts = [extract_humanizable_text(b) or "" for _, b in humanizable_blocks(blocks)]
    prose = "\n\n".join(p for p in parts if p.strip())
    return prose if prose.strip() else text


def _syllables(word: str) -> int:
    groups = re.findall(r"[aeiouy]+", word.lower())
    count = len(groups)
    if word.lower().endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


def _sentences(prose: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_RE.split(prose.strip()) if s.strip()]


def _per(count: int, n: int, unit: int) -> float:
    return (count / n) * unit if n else 0.0


def _sentence_stats(sentences: list[str]) -> tuple[float, float]:
    lengths = [len(_WORD_RE.findall(s)) for s in sentences]
    if not lengths:
        return 0.0, 0.0
    return statistics.fmean(lengths), statistics.pstdev(lengths)


def _fk_grade(words: list[str], sentences: list[str]) -> float:
    if not words or not sentences:
        return 0.0
    syllables = sum(_syllables(w) for w in words)
    return 0.39 * (len(words) / len(sentences)) + 11.8 * (syllables / len(words)) - 15.59


def _ttr(words: list[str]) -> float:
    window = [w.lower() for w in words[:_TTR_WINDOW]]
    return len(set(window)) / len(window) if window else 0.0


def _paragraph_len_mean(prose: str) -> float:
    paras = [p for p in re.split(r"\n\s*\n", prose) if p.strip()]
    if not paras:
        return 0.0
    return statistics.fmean(len(_WORD_RE.findall(p)) for p in paras)


def text_features(text: str) -> dict[str, float]:
    """All DIMENSIONS for one text (zeros for empty input)."""
    prose = _prose(text)
    words = _WORD_RE.findall(prose)
    lowered = [w.lower() for w in words]
    sentences = _sentences(prose)
    n = len(words)
    mean_len, std_len = _sentence_stats(sentences)
    return {
        "sentence_len_mean": mean_len,
        "sentence_len_std": std_len,
        "fk_grade": max(_fk_grade(words, sentences), 0.0),
        "ttr": _ttr(words),
        "contraction_rate": _per(len(_CONTRACTION_RE.findall(prose)), n, 100),
        "hedge_rate": _per(sum(w in _HEDGES for w in lowered), n, 100),
        "booster_rate": _per(sum(w in _BOOSTERS for w in lowered), n, 100),
        "punct_comma_per_1k": _per(prose.count(","), n, 1000),
        "punct_semicolon_per_1k": _per(prose.count(";"), n, 1000),
        "punct_dash_per_1k": _per(len(_DASH_RE.findall(prose)), n, 1000),
        "punct_question_per_1k": _per(prose.count("?"), n, 1000),
        "paragraph_len_mean": _paragraph_len_mean(prose),
        "first_person_rate": _per(sum(w in _FIRST_PERSON for w in lowered), n, 100),
    }


def _dim_stat(values: list[float], n: int) -> DimStat:
    mean = statistics.fmean(values)
    stddev = statistics.pstdev(values)
    cv = stddev / abs(mean) if mean else (0.0 if stddev == 0 else 1.0)
    confidence = min(1.0, n / CONFIDENCE_FULL_N) * (1.0 - min(1.0, cv))
    return DimStat(mean=mean, stddev=stddev, confidence=round(confidence, 4))


def build_fingerprint(samples: list[str]) -> VoiceFingerprint:
    """Per-dimension {mean, stddev, confidence} over the valid samples."""
    valid = [s for s in samples if len(_WORD_RE.findall(s)) >= MIN_SAMPLE_WORDS]
    if len(valid) < MIN_SAMPLES:
        msg = f"need {MIN_SAMPLES} samples of {MIN_SAMPLE_WORDS}+ words, have {len(valid)}"
        raise InsufficientSamples(msg)
    feats = [text_features(s) for s in valid]
    dims = {name: _dim_stat([f[name] for f in feats], len(valid)) for name in DIMENSIONS}
    return VoiceFingerprint(dims=dims, sample_count=len(valid))
```

If `fingerprint.py` exceeds 200 lines, move `DIM_LABELS` + the word sets into `src/services/persona/lexicon.py` and import them.

- [ ] **Step 4: Run to verify it passes**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/services/persona -q` → all pass. Then `uv run ruff check src/services/persona src/models/persona.py tests/unit/services/persona && uv run ruff format src/services/persona src/models/persona.py tests/unit/services/persona` and `uv run mypy src/services/persona src/models/persona.py --ignore-missing-imports` (0 errors).

- [ ] **Step 5: Commit**

```bash
git add src/config/settings.py src/models/persona.py src/services/persona tests/unit/services/persona
git commit -m "feat(persona): voice engine flag, persona models, stdlib stylometric fingerprint (AUTHOR-011)"
```

---

### Task 2: Voice scoring

**Files:**
- Create: `src/services/persona/scoring.py`
- Modify: `src/services/persona/__init__.py` (export)
- Test: `tests/unit/services/persona/test_scoring.py`

**Interfaces:**
- Produces: `score_text(text: str, fp: VoiceFingerprint) -> VoiceScore`; `band_for(score: int) -> VoiceBand` (`>=80 match`, `>=60 close`, else `off_voice`); `score_sections(sections: list[SectionDraft], fp) -> tuple[dict[str, int], int | None]` — per-section scores keyed by `str(section_index)` (JSON-friendly) and the word-weighted article mean over sections with ≥ `SHORT_SECTION_WORDS` words (`None` when none qualify). Constants `MIN_CONFIDENCE = 0.5`, `DEVIATION_Z = 1.5`, `SHORT_SECTION_WORDS = 60`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/services/persona/test_scoring.py
"""AUTHOR-011 — z-score voice matching."""

from __future__ import annotations

from src.models.content_pipeline import SectionDraft
from src.models.persona import DimStat, VoiceFingerprint
from src.services.persona.fingerprint import DIMENSIONS, text_features
from src.services.persona.scoring import (
    MIN_CONFIDENCE,
    band_for,
    score_sections,
    score_text,
)

TEXT = "We ship small. It works. Teams win. Perhaps we'll try it again tomorrow."


def _fp(overrides: dict[str, DimStat] | None = None, confidence: float = 1.0) -> VoiceFingerprint:
    feats = text_features(TEXT)
    dims = {
        name: DimStat(mean=feats[name], stddev=max(0.5, abs(feats[name]) * 0.2), confidence=confidence)
        for name in DIMENSIONS
    }
    dims.update(overrides or {})
    return VoiceFingerprint(dims=dims, sample_count=8)


class TestScoreText:
    def test_text_matching_its_own_fingerprint_scores_100(self) -> None:
        result = score_text(TEXT, _fp())
        assert result.score == 100 and result.band == "match"
        assert result.deviations == []

    def test_far_off_dimension_lowers_score_and_names_deviation(self) -> None:
        fp = _fp({"sentence_len_mean": DimStat(mean=40.0, stddev=2.0, confidence=1.0)})
        result = score_text(TEXT, fp)
        assert result.score < 100
        dev = next(d for d in result.deviations if d.dim == "sentence_len_mean")
        assert "average sentence length" in dev.message and "40" in dev.message
        assert result.per_dim["sentence_len_mean"].z < -1.5

    def test_low_confidence_dimensions_are_ignored(self) -> None:
        fp = _fp({"sentence_len_mean": DimStat(mean=40.0, stddev=2.0, confidence=MIN_CONFIDENCE - 0.1)})
        assert score_text(TEXT, fp).score == 100

    def test_penalty_is_capped_at_three_sigma(self) -> None:
        fp3 = _fp({"ttr": DimStat(mean=5.0, stddev=1.0, confidence=1.0)})
        fp9 = _fp({"ttr": DimStat(mean=50.0, stddev=1.0, confidence=1.0)})
        assert score_text(TEXT, fp3).score == score_text(TEXT, fp9).score

    def test_no_confident_dimensions_scores_100(self) -> None:
        assert score_text(TEXT, _fp(confidence=0.0)).score == 100


class TestBands:
    def test_bands(self) -> None:
        assert band_for(80) == "match" and band_for(79) == "close"
        assert band_for(60) == "close" and band_for(59) == "off_voice"


class TestScoreSections:
    def test_short_sections_excluded_from_article_mean(self) -> None:
        long_body = " ".join(["We ship small."] * 30)  # 90 words
        sections = [
            SectionDraft(section_index=0, title="a", body_markdown="Tiny.", word_count=1, citations_used=[]),
            SectionDraft(section_index=1, title="b", body_markdown=long_body, word_count=90, citations_used=[]),
        ]
        by_section, overall = score_sections(sections, _fp())
        assert set(by_section) == {"0", "1"}
        assert overall == by_section["1"]

    def test_all_short_gives_none(self) -> None:
        sections = [SectionDraft(section_index=0, title="a", body_markdown="Tiny.", word_count=1, citations_used=[])]
        assert score_sections(sections, _fp())[1] is None
```

- [ ] **Step 2: Run to verify it fails** — `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/services/persona/test_scoring.py -q` → `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# src/services/persona/scoring.py
"""Voice-match scoring (spec §4.2): confidence-weighted capped z-scores."""

from __future__ import annotations

from src.models.content_pipeline import SectionDraft
from src.models.persona import (
    DimScore,
    DimStat,
    VoiceBand,
    VoiceDeviation,
    VoiceFingerprint,
    VoiceScore,
)
from src.services.persona.fingerprint import DIM_LABELS, text_features

MIN_CONFIDENCE = 0.5
DEVIATION_Z = 1.5
SHORT_SECTION_WORDS = 60
_Z_CAP = 3.0


def band_for(score: int) -> VoiceBand:
    if score >= 80:
        return "match"
    if score >= 60:
        return "close"
    return "off_voice"


def _denominator(stat: DimStat) -> float:
    return max(stat.stddev, 0.1 * abs(stat.mean), 0.25)


def _message(dim: str, observed: float, stat: DimStat) -> str:
    label = DIM_LABELS.get(dim, dim)
    return f"{label} is {observed:.1f}; target {stat.mean:.1f} ± {stat.stddev:.1f}"


def _dim_score(dim: str, observed: float, stat: DimStat) -> tuple[DimScore, VoiceDeviation | None]:
    z = (observed - stat.mean) / _denominator(stat)
    score = DimScore(value=observed, z=z, confidence=stat.confidence)
    if abs(z) <= DEVIATION_Z:
        return score, None
    return score, VoiceDeviation(dim=dim, observed=observed, target=stat.mean, message=_message(dim, observed, stat))


def score_text(text: str, fp: VoiceFingerprint) -> VoiceScore:
    """0–100 match of `text` against `fp` over its confident dimensions."""
    feats = text_features(text)
    per_dim: dict[str, DimScore] = {}
    deviations: list[VoiceDeviation] = []
    weighted = total = 0.0
    for dim, stat in fp.dims.items():
        if stat.confidence < MIN_CONFIDENCE or dim not in feats:
            continue
        score, deviation = _dim_score(dim, feats[dim], stat)
        per_dim[dim] = score
        weighted += stat.confidence * min(abs(score.z), _Z_CAP) / _Z_CAP
        total += stat.confidence
        if deviation is not None:
            deviations.append(deviation)
    final = 100 if total == 0 else round(100 * (1 - weighted / total))
    deviations.sort(key=lambda d: -abs(per_dim[d.dim].z))
    return VoiceScore(score=final, band=band_for(final), per_dim=per_dim, deviations=deviations)


def score_sections(
    sections: list[SectionDraft], fp: VoiceFingerprint
) -> tuple[dict[str, int], int | None]:
    """Per-section scores + word-weighted mean over non-short sections."""
    by_section = {str(s.section_index): score_text(s.body_markdown, fp).score for s in sections}
    weighted = [(by_section[str(s.section_index)], s.word_count) for s in sections if s.word_count >= SHORT_SECTION_WORDS]
    if not weighted:
        return by_section, None
    total_words = sum(w for _, w in weighted)
    return by_section, round(sum(score * w for score, w in weighted) / total_words)
```

Add `score_text`, `score_sections`, `band_for` to `src/services/persona/__init__.py` exports.

- [ ] **Step 4: Run** — `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/services/persona -q`; ruff/mypy on the package.
- [ ] **Step 5: Commit** — `git commit -m "feat(persona): confidence-weighted voice scoring + bands (AUTHOR-011)"`

---

### Task 3: Few-shot picker, voice prompt block, registry keys

**Files:**
- Create: `src/services/persona/few_shot.py`, `src/services/persona/prompt_block.py`, `src/agents/prompts/defaults_voice.py`
- Modify: `src/agents/prompts/__init__.py` (import `defaults_voice` beside the other defaults modules), `src/services/persona/__init__.py`
- Test: `tests/unit/services/persona/test_few_shot.py`, `tests/unit/services/persona/test_prompt_block.py`

**Interfaces:**
- `EmbedFn = Callable[[list[str]], list[list[float]] | None]`
- `pick_samples(query: str, samples: list[PersonaSample], embed: EmbedFn, *, k: int = FEW_SHOT_K) -> PickResult` where `PickResult(chosen: list[PersonaSample], new_embeddings: dict[UUID, list[float]])` — `new_embeddings` are samples that lacked a stored embedding and were embedded during this call (the caller persists them). Cold model (`embed` returns `None`) → the `k` longest samples, `new_embeddings` empty.
- `excerpt(text: str, max_words: int = EXCERPT_WORDS) -> str` — trimmed at a sentence boundary.
- `build_voice_block(fp: VoiceFingerprint, samples: list[PersonaSample]) -> str`.
- Registry keys (step `voice`): `voice.block_intro` (no vars), `voice.dim_line` (`label, target, low, high`), `voice.samples_intro` (no vars), `voice.fix.system` (no vars), `voice.fix.user` (`voice_block, deviations, section_text`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/services/persona/test_few_shot.py
"""AUTHOR-011 — few-shot sample selection by cosine, cold fallback."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from src.models.persona import PersonaSample
from src.services.persona.few_shot import EXCERPT_WORDS, excerpt, pick_samples

_PID = uuid4()


def _sample(text: str, embedding: list[float] | None = None) -> PersonaSample:
    return PersonaSample(persona_id=_PID, text=text, word_count=len(text.split()), embedding=embedding, created_at=datetime.now(UTC))


def _embed_axis(texts: list[str]) -> list[list[float]]:
    # deterministic: "kube" → x axis, "market" → y axis
    return [[1.0, 0.0] if "kube" in t else [0.0, 1.0] for t in texts]


class TestPickSamples:
    def test_picks_by_cosine_and_embeds_missing(self) -> None:
        s_kube = _sample("kube pods and nodes " * 5)
        s_mkt = _sample("market campaign funnel " * 5, embedding=[0.0, 1.0])
        result = pick_samples("kube networking", [s_mkt, s_kube], _embed_axis, k=1)
        assert [s.id for s in result.chosen] == [s_kube.id]
        assert set(result.new_embeddings) == {s_kube.id}

    def test_cold_model_falls_back_to_longest(self) -> None:
        short = _sample("a b c")
        long_ = _sample("w " * 50)
        result = pick_samples("anything", [short, long_], lambda _t: None, k=1)
        assert [s.id for s in result.chosen] == [long_.id]
        assert result.new_embeddings == {}

    def test_k_bounds_result(self) -> None:
        samples = [_sample(f"kube {i} " * 5) for i in range(5)]
        assert len(pick_samples("kube", samples, _embed_axis, k=3).chosen) == 3


class TestExcerpt:
    def test_trims_at_sentence_boundary(self) -> None:
        text = " ".join(f"Sentence number {i} here." for i in range(60))
        out = excerpt(text)
        assert len(out.split()) <= EXCERPT_WORDS
        assert out.endswith(".")

    def test_short_text_unchanged(self) -> None:
        assert excerpt("Short one. Two.") == "Short one. Two."
```

```python
# tests/unit/services/persona/test_prompt_block.py
"""AUTHOR-011 — confidence-gated voice block + registry keys."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from src.agents.prompts import DEFAULT_PROMPTS, bind_prompt_overrides
from src.models.persona import DimStat, PersonaSample, VoiceFingerprint
from src.services.persona.fingerprint import DIMENSIONS
from src.services.persona.prompt_block import build_voice_block


def _fp(conf_len: float, conf_hedge: float) -> VoiceFingerprint:
    dims = {name: DimStat(mean=1.0, stddev=0.1, confidence=0.0) for name in DIMENSIONS}
    dims["sentence_len_mean"] = DimStat(mean=17.0, stddev=4.0, confidence=conf_len)
    dims["hedge_rate"] = DimStat(mean=2.0, stddev=0.5, confidence=conf_hedge)
    return VoiceFingerprint(dims=dims, sample_count=6)


def _sample(text: str) -> PersonaSample:
    return PersonaSample(persona_id=uuid4(), text=text, word_count=len(text.split()), created_at=datetime.now(UTC))


class TestBuildVoiceBlock:
    def test_only_confident_dimensions_are_listed(self) -> None:
        block = build_voice_block(_fp(0.9, 0.2), [])
        assert "average sentence length" in block and "17.0" in block
        assert "hedging" not in block

    def test_targets_carry_low_and_high(self) -> None:
        block = build_voice_block(_fp(0.9, 0.9), [])
        assert "13.0" in block and "21.0" in block  # 17 ± 4

    def test_samples_are_appended_as_excerpts(self) -> None:
        block = build_voice_block(_fp(0.9, 0.9), [_sample("Sample prose here. It reads well.")])
        assert "Sample 1" in block and "Sample prose here." in block

    def test_registry_override_changes_intro(self) -> None:
        with bind_prompt_overrides({"voice.block_intro": "VOICE-OVERRIDE"}):
            assert build_voice_block(_fp(0.9, 0.9), []).startswith("VOICE-OVERRIDE")

    def test_keys_registered(self) -> None:
        for key in ("voice.block_intro", "voice.dim_line", "voice.samples_intro", "voice.fix.system", "voice.fix.user"):
            assert key in DEFAULT_PROMPTS
        assert DEFAULT_PROMPTS["voice.fix.user"].variables == frozenset({"voice_block", "deviations", "section_text"})
```

- [ ] **Step 2: Run to verify it fails** — both files: `ModuleNotFoundError` / `KeyError`.

- [ ] **Step 3: Implement**

```python
# src/agents/prompts/defaults_voice.py
"""Persona voice prompts (AUTHOR-011). Editable in Settings → Prompts."""

from src.agents.prompts.registry import PromptTemplate, register

register(
    PromptTemplate(
        key="voice.block_intro", step="voice",
        description="Voice block: heading that introduces the measured targets.",
        template=(
            "Voice. Write in this author's measured voice. Treat each line as a "
            "target, not a hard rule; keep every factual claim and citation marker:"
        ),
        variables=frozenset(),
    ),
    PromptTemplate(
        key="voice.dim_line", step="voice",
        description="Voice block: one line per confident dimension.",
        template="{label}: aim for about {target} (typical range {low}–{high}).",
        variables=frozenset({"label", "target", "low", "high"}),
    ),
    PromptTemplate(
        key="voice.samples_intro", step="voice",
        description="Voice block: introduces the few-shot excerpts.",
        template="Match the register of these excerpts from the same author:",
        variables=frozenset(),
    ),
    PromptTemplate(
        key="voice.fix.system", step="voice",
        description="Voice fix pass: system role for rewriting one off-voice section.",
        template=(
            "You are an editor aligning one article section to a specific author's "
            "voice. Rewrite the prose so the named deviations are corrected. Keep "
            "every factual claim, every [N] citation marker, and every heading "
            "exactly as written. If the input contains the sentinel `<<<BLOCK>>>` "
            "between chunks, preserve every sentinel verbatim and rewrite each chunk "
            "in place — the output must contain exactly the same number of "
            "sentinels. Return plain markdown only — no commentary, no fences."
        ),
        variables=frozenset(),
    ),
    PromptTemplate(
        key="voice.fix.user", step="voice",
        description="Voice fix pass: voice block + deviations + the section prose.",
        template=(
            "{voice_block}\n\nDeviations to correct:\n{deviations}\n\n"
            "Section text:\n{section_text}"
        ),
        variables=frozenset({"voice_block", "deviations", "section_text"}),
    ),
)
```
In `src/agents/prompts/__init__.py` add `defaults_voice` to the side-effect import list.

```python
# src/services/persona/few_shot.py
"""Few-shot sample selection — in-process cosine (spec §4.3)."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import UUID

import numpy as np

from src.models.persona import PersonaSample

FEW_SHOT_K = 3
EXCERPT_WORDS = 120
EmbedFn = Callable[[list[str]], list[list[float]] | None]
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class PickResult:
    chosen: list[PersonaSample]
    new_embeddings: dict[UUID, list[float]] = field(default_factory=dict)


def excerpt(text: str, max_words: int = EXCERPT_WORDS) -> str:
    """First sentences of `text` up to `max_words`, never mid-sentence."""
    out: list[str] = []
    count = 0
    for sentence in _SENTENCE_RE.split(text.strip()):
        words = len(sentence.split())
        if out and count + words > max_words:
            break
        out.append(sentence)
        count += words
    return " ".join(out)


def _longest(samples: list[PersonaSample], k: int) -> PickResult:
    ordered = sorted(samples, key=lambda s: s.word_count, reverse=True)
    return PickResult(chosen=ordered[:k])


def _ensure_embeddings(
    samples: list[PersonaSample], embed: EmbedFn
) -> tuple[dict[UUID, list[float]], dict[UUID, list[float]]] | None:
    missing = [s for s in samples if s.embedding is None]
    fresh = embed([s.text for s in missing]) if missing else []
    if fresh is None:
        return None
    new = {s.id: vec for s, vec in zip(missing, fresh, strict=True)}
    known = {s.id: s.embedding for s in samples if s.embedding is not None}
    return {**known, **new}, new


def pick_samples(
    query: str, samples: list[PersonaSample], embed: EmbedFn, *, k: int = FEW_SHOT_K
) -> PickResult:
    """Top-`k` samples by cosine to `query`; longest-`k` when the model is cold."""
    if not samples:
        return PickResult(chosen=[])
    query_vec = embed([query])
    ensured = _ensure_embeddings(samples, embed)
    if query_vec is None or ensured is None:
        return _longest(samples, k)
    vectors, new = ensured
    q = np.array(query_vec[0])
    scored = sorted(samples, key=lambda s: -float(np.dot(q, np.array(vectors[s.id]))))
    return PickResult(chosen=scored[:k], new_embeddings=new)
```
(Embeddings from `EmbeddingService.embed` are L2-normalised, so the dot product is the cosine.)

```python
# src/services/persona/prompt_block.py
"""Confidence-gated voice block for the drafter / fixer (spec §4.4)."""

from __future__ import annotations

from src.agents.prompts import render_prompt
from src.models.persona import DimStat, PersonaSample, VoiceFingerprint
from src.services.persona.few_shot import excerpt
from src.services.persona.fingerprint import DIM_LABELS
from src.services.persona.scoring import MIN_CONFIDENCE


def _dim_line(dim: str, stat: DimStat) -> str:
    return "- " + render_prompt(
        "voice.dim_line",
        label=DIM_LABELS.get(dim, dim),
        target=f"{stat.mean:.1f}",
        low=f"{max(stat.mean - stat.stddev, 0.0):.1f}",
        high=f"{stat.mean + stat.stddev:.1f}",
    )


def build_voice_block(fp: VoiceFingerprint, samples: list[PersonaSample]) -> str:
    """Intro + one line per confident dimension + few-shot excerpts."""
    lines = [render_prompt("voice.block_intro")]
    lines += [_dim_line(d, s) for d, s in fp.dims.items() if s.confidence >= MIN_CONFIDENCE]
    if samples:
        lines.append("")
        lines.append(render_prompt("voice.samples_intro"))
        for i, sample in enumerate(samples, 1):
            lines.append(f"Sample {i}:\n{excerpt(sample.text)}")
    return "\n".join(lines)
```
Export `pick_samples`, `PickResult`, `excerpt`, `build_voice_block` from `src/services/persona/__init__.py`.

- [ ] **Step 4: Run** — `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/services/persona tests/unit/agents/prompts -q` (the registry self-validation test now covers the 5 new keys); ruff + mypy on the touched modules.
- [ ] **Step 5: Commit** — `git commit -m "feat(persona): few-shot cosine picker, voice prompt block, voice.* registry keys (AUTHOR-011)"`

---

### Task 4: Tables, migration, repositories

**Files:**
- Create: `src/db/tables_personas.py`, `src/db/persona_repository.py`, `alembic/versions/f3b8d1c6a2e4_add_personas.py`
- Modify: `src/db/tables.py` (import `PersonaRow, PersonaSampleRow` beside `PromptOverrideRow`), `src/db/tables_briefs.py` (add `voice_persona_id`), `src/db/tables.py` `ResearchSessionRow` (add `voice_persona_id` after `audience_persona`, line 109) and `CanonicalArticleRow` (add the five columns after `authors`, line 218)
- Test: `tests/unit/db/test_persona_repository.py`, `tests/integration/db/test_pg_personas.py`

**Interfaces:**
- `PersonaRepository` Protocol: `create(owner_id: str, data: PersonaCreate) -> Persona`; `get(persona_id: UUID) -> Persona | None`; `list() -> list[Persona]`; `update(persona_id, data: PersonaUpdate) -> Persona | None`; `delete(persona_id) -> bool`; `add_sample(persona_id, data: SampleCreate) -> PersonaSample` (computes `word_count`); `delete_sample(persona_id, sample_id) -> bool`; `list_samples(persona_id) -> list[PersonaSample]`; `set_fingerprint(persona_id, fp: VoiceFingerprint | None) -> Persona | None` (also updates `sample_count`); `set_sample_embedding(sample_id, vec: list[float]) -> None`. `PgPersonaRepository(sf)`, `InMemoryPersonaRepository()`.
- Row columns (new): `research_sessions.voice_persona_id uuid null FK personas ON DELETE SET NULL`, `briefs.voice_persona_id` (same), `canonical_articles.voice_persona_id` (same) + `voice_match_score float null` + `voice_scores_by_section jsonb null` + `few_shot_sample_ids jsonb not null default '[]'` + `audience_persona varchar(100) null`.

- [ ] **Step 1: Write the failing unit test** (in-memory; the PG test mirrors it)

```python
# tests/unit/db/test_persona_repository.py
"""AUTHOR-011 — persona repository contract (in-memory twin)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.db.persona_repository import InMemoryPersonaRepository
from src.models.persona import DimStat, PersonaCreate, PersonaUpdate, SampleCreate, VoiceFingerprint


def _fp() -> VoiceFingerprint:
    return VoiceFingerprint(dims={"ttr": DimStat(mean=0.5, stddev=0.1, confidence=0.7)}, sample_count=5)


@pytest.mark.asyncio
class TestInMemoryPersonaRepository:
    async def test_crud_round_trip(self) -> None:
        repo = InMemoryPersonaRepository()
        p = await repo.create("user-1", PersonaCreate(name="Ada", description="d"))
        assert p.fingerprint is None and p.sample_count == 0
        assert (await repo.get(p.id)) == p
        assert [x.id for x in await repo.list()] == [p.id]
        updated = await repo.update(p.id, PersonaUpdate(name="Ada L."))
        assert updated is not None and updated.name == "Ada L."
        assert await repo.delete(p.id) is True
        assert await repo.get(p.id) is None and await repo.delete(p.id) is False

    async def test_samples_and_fingerprint(self) -> None:
        repo = InMemoryPersonaRepository()
        p = await repo.create("user-1", PersonaCreate(name="Ada"))
        s = await repo.add_sample(p.id, SampleCreate(text="one two three"))
        assert s.word_count == 3 and s.embedding is None
        assert [x.id for x in await repo.list_samples(p.id)] == [s.id]
        await repo.set_sample_embedding(s.id, [0.1, 0.2])
        assert (await repo.list_samples(p.id))[0].embedding == [0.1, 0.2]
        with_fp = await repo.set_fingerprint(p.id, _fp())
        assert with_fp is not None and with_fp.fingerprint == _fp() and with_fp.sample_count == 1
        assert await repo.delete_sample(p.id, s.id) is True
        assert await repo.list_samples(p.id) == []

    async def test_unknown_persona(self) -> None:
        repo = InMemoryPersonaRepository()
        assert await repo.update(uuid4(), PersonaUpdate(name="x")) is None
        assert await repo.set_fingerprint(uuid4(), _fp()) is None
```

- [ ] **Step 2: Run to verify it fails** — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# src/db/tables_personas.py
"""SQLAlchemy tables for voice personas + writing samples (AUTHOR-011).

Own module — `src/db/tables.py` is over the 200-line budget; imported from
there so `Base.metadata` is complete for Alembic and `create_all`.
"""

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin, UUIDMixin


class PersonaRow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "personas"

    owner_id: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    fingerprint: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)


class PersonaSampleRow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "persona_samples"

    persona_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
        index=True,
    )
    text: Mapped[str] = mapped_column(Text)
    word_count: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list | None] = mapped_column(JSONB, nullable=True)
```

`src/db/tables.py`: add `from src.db.tables_personas import PersonaRow, PersonaSampleRow  # noqa: F401` next to the `PromptOverrideRow` import; in `ResearchSessionRow` after `audience_persona` (line 109):
```python
    # AUTHOR-011 — measured voice persona (separate from audience_persona).
    voice_persona_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("personas.id", ondelete="SET NULL"), nullable=True
    )
```
in `CanonicalArticleRow` after `authors` (line 218):
```python
    # AUTHOR-011 — voice engine outputs (+ the audience_persona column the
    # model has carried since VISUAL-005 without ever being persisted).
    audience_persona: Mapped[str | None] = mapped_column(String(100), nullable=True)
    voice_persona_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("personas.id", ondelete="SET NULL"), nullable=True
    )
    voice_match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    voice_scores_by_section: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    few_shot_sample_ids: Mapped[list] = mapped_column(JSONB, default=list)
```
`src/db/tables_briefs.py`: add `voice_persona_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("personas.id", ondelete="SET NULL"), nullable=True)` (import `uuid`, `ForeignKey`, `PG_UUID`). Because `tables_briefs.py` now references `personas`, import `tables_personas` BEFORE `tables_briefs` in `tables.py` so the FK target is registered first.

```python
# src/db/persona_repository.py
"""Repositories for personas + samples (AUTHOR-011)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.tables_personas import PersonaRow, PersonaSampleRow
from src.models.persona import (
    Persona, PersonaCreate, PersonaSample, PersonaUpdate, SampleCreate, VoiceFingerprint,
)

logger = structlog.get_logger()


class PersonaRepository(Protocol):
    async def create(self, owner_id: str, data: PersonaCreate) -> Persona: ...
    async def get(self, persona_id: UUID) -> Persona | None: ...
    async def list(self) -> list[Persona]: ...
    async def update(self, persona_id: UUID, data: PersonaUpdate) -> Persona | None: ...
    async def delete(self, persona_id: UUID) -> bool: ...
    async def add_sample(self, persona_id: UUID, data: SampleCreate) -> PersonaSample: ...
    async def delete_sample(self, persona_id: UUID, sample_id: UUID) -> bool: ...
    async def list_samples(self, persona_id: UUID) -> list[PersonaSample]: ...
    async def set_fingerprint(self, persona_id: UUID, fp: VoiceFingerprint | None) -> Persona | None: ...
    async def set_sample_embedding(self, sample_id: UUID, vec: list[float]) -> None: ...


def _word_count(text: str) -> int:
    return len(text.split())


def row_to_persona(row: PersonaRow) -> Persona:
    fp = VoiceFingerprint.model_validate(row.fingerprint) if row.fingerprint else None
    return Persona(
        id=row.id, owner_id=row.owner_id, name=row.name, description=row.description,
        fingerprint=fp, sample_count=row.sample_count, created_at=row.created_at, updated_at=row.updated_at,
    )


def row_to_sample(row: PersonaSampleRow) -> PersonaSample:
    return PersonaSample(
        id=row.id, persona_id=row.persona_id, text=row.text, word_count=row.word_count,
        embedding=list(row.embedding) if row.embedding else None, created_at=row.created_at,
    )
```
Then `PgPersonaRepository` (each method `async with self._sf() as db:`; `update` applies `data.model_dump(exclude_none=True)` via `setattr`; `delete` returns `bool(result.rowcount)`; `add_sample` inserts with `word_count=_word_count(data.text)`; `delete_sample` filters on both ids; `set_fingerprint` writes `fp.model_dump(mode="json")` (L-001) or `None` and recounts samples with `select(func.count())`; `set_sample_embedding` assigns `list(vec)`) and `InMemoryPersonaRepository` (two dicts, same semantics, `sample_count` = number of samples for that persona). If the file passes 200 lines, put the in-memory twin in `src/db/persona_repository_memory.py` and re-export it.

Migration (chain off `e2a7c4d9b1f3`; check with `uv run alembic heads`):
```python
"""add personas + persona_samples, voice_persona_id on sessions/briefs/articles, voice fields on articles

Revision ID: f3b8d1c6a2e4
Revises: e2a7c4d9b1f3
Create Date: 2026-09-01 12:00:00.000000

AUTHOR-011 — persona voice engine.
"""
```
`upgrade()`: create `personas` (id uuid PK, created_at/updated_at timestamptz default now(), owner_id varchar(100) not null, name varchar(200) not null, description text, fingerprint jsonb, sample_count int not null default 0) + index `ix_personas_owner_id`; create `persona_samples` (id, timestamps, persona_id uuid not null FK personas ON DELETE CASCADE, text text not null, word_count int not null, embedding jsonb) + index `ix_persona_samples_persona_id`; `op.add_column` on `research_sessions`, `briefs`, `canonical_articles` for `voice_persona_id` with `op.create_foreign_key("fk_<table>_voice_persona_id", …, ondelete="SET NULL")`; `canonical_articles` also `audience_persona varchar(100)`, `voice_match_score float`, `voice_scores_by_section jsonb`, `few_shot_sample_ids jsonb not null server_default '[]'`. `downgrade()` reverses in exact reverse order (drop FKs before columns, samples table before personas).

Integration test `tests/integration/db/test_pg_personas.py` (same fixture shape as `test_pg_prompt_overrides.py`; cleans `DELETE FROM personas WHERE owner_id = 'it-user'` — samples cascade): create → add 2 samples → `set_sample_embedding` → `set_fingerprint` → `list_samples` shows the embedding → `delete` persona → `list_samples` empty (cascade).

- [ ] **Step 4: Run** — unit test → 3 passed; `COGNIFY_DATABASE_URL=postgresql+asyncpg://cognify:cognify@localhost:5432/cognify uv run alembic upgrade head` → `f3b8d1c6a2e4`; then `downgrade -1` + `upgrade head`; integration test `-m integration` → 1 passed; full unit suite; ruff/mypy on new modules. **Do not run the migration against anything but the local Docker DB.**
- [ ] **Step 5: Commit** — `git commit -m "feat(persona): personas + persona_samples tables, migration f3b8d1c6a2e4, voice columns, Pg + in-memory repos (AUTHOR-011)"`

---

### Task 5: `/personas` API + app wiring

**Files:**
- Create: `src/api/schemas/personas.py`, `src/api/routers/personas.py`
- Modify: `src/api/main.py` (router include after `prompts_router`; `app.state.persona_repo = PgPersonaRepository(sf)` next to `prompt_override_repo` in the DB branch, `InMemoryPersonaRepository()` in `create_app`; pass `_get_or_create_embedding_service(app)` to the router via `app.state.embedding_service` — already set), `src/services/bootstrap.py` (`PipelineServices.persona_repo`)
- Test: `tests/unit/api/test_personas_endpoints.py`

**Interfaces:**
- Routes exactly as spec §6. Response models: `PersonaSummary {id, name, description, sample_count, ready: bool, updated_at}`, `PersonaDetail = PersonaSummary + {fingerprint: VoiceFingerprint | None, samples: [SampleView {id, word_count, preview (first 300 chars), created_at}]}`, `ScoreRequest {text}`, `VoiceScore` (from models). `SampleCreate` 422 when `word_count < MIN_SAMPLE_WORDS` → `detail={"violations": [f"sample needs at least {MIN_SAMPLE_WORDS} words (has N)"]}` (same shape as prompts). `POST /personas/{id}/score` → 409 `CognifyError(code="persona_not_ready")` when no fingerprint.
- After `add_sample` / `delete_sample`: recompute `build_fingerprint([s.text for s in samples])` → `set_fingerprint(fp)`; on `InsufficientSamples` → `set_fingerprint(None)`. After `add_sample`, embed with `request.app.state.embedding_service.try_embed([text])` if present and warm; store via `set_sample_embedding` (skip silently when cold — the few-shot picker embeds lazily).

- [ ] **Step 1: Write the failing tests** — using `auth_app` + `make_auth_header` from `tests/unit/api/conftest.py`, set `auth_app.state.persona_repo = InMemoryPersonaRepository()` and `auth_app.state.embedding_service = MagicMock(try_embed=lambda texts: None)`:
  - viewer can `GET /personas` (200, empty list); viewer `POST` → 403; editor `POST {name}` → 201 with `ready=false`.
  - `POST /personas/{id}/samples` with 20 words → 422 with the violation message; with 5 samples of ≥150 words (build a 160-word string) → after the 5th, `GET /personas/{id}` shows `ready=true`, `fingerprint.sample_count == 5`, `samples[0].preview` ≤ 300 chars.
  - `DELETE /personas/{id}/samples/{sid}` on one of five → `ready=false` (fingerprint null).
  - `POST /personas/{id}/score {text}` → 409 before ready, 200 with `score`/`band`/`deviations` after.
  - unknown persona → 404 on GET/PATCH/DELETE/samples/score; `PATCH` renames; `DELETE` → 204; 31st `GET /personas` → 429.

- [ ] **Step 2: Run to verify it fails.**
- [ ] **Step 3: Implement** — router helpers `_repo(request)` (503 when absent), `_get_or_404`, `_recompute_fingerprint(repo, persona_id)`, `_maybe_embed(request, sample)`; keep every handler < 20 lines by delegating to `src/services/persona/service.py::PersonaService` if the router grows past 200 lines (create it then; it wraps the repo + fingerprint recompute + embedding). Wire `main.py` (both branches) and `bootstrap.py`.
- [ ] **Step 4: Run** — `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/api/test_personas_endpoints.py tests/unit/api -q`; full unit suite; ruff; mypy on new files.
- [ ] **Step 5: Commit** — `git commit -m "feat(persona): /personas CRUD, samples, fingerprint recompute, score preview + wiring (AUTHOR-011)"`

---

### Task 6: `voice_persona_id` plumbing (brief → session → state)

**Files:**
- Modify: `src/models/brief.py` (`BriefFields.voice_persona_id: UUID | None = None`, `BriefUpdate.voice_persona_id: UUID | None = None`), `src/db/brief_repository.py` (`_row_fields` adds `voice_persona_id=row.voice_persona_id`; `brief_create_to_row` unchanged — `model_dump(mode="json")` gives a str uuid; SQLAlchemy `PG_UUID(as_uuid=True)` accepts it — verify in the test, else convert), `src/api/schemas/research.py` (`CreateResearchSessionRequest.voice_persona_id: UUID | None = None`; `ResearchSessionResponse.voice_persona_id: UUID | None = None`), `src/models/session_params.py` (`voice_persona_id: UUID | None = None`; `from_brief` copies it), `src/api/routers/research_params.py` (`_INLINE_FIELDS` += `"voice_persona_id"`; `inline_brief_create` passes `voice_persona_id=body.voice_persona_id`), `src/models/research_db.py` (`ResearchSession.voice_persona_id: UUID | None = None`), `src/db/repositories.py` (`PgResearchSessionRepository.create/update/_to_model` map it — lines 91, 138, 216), `src/services/research.py` (wherever `SessionParams` fields are copied onto the session in `start_session` — grep `audience_persona=` and add the sibling), `src/api/routers/research.py` (session response mapping — grep `content_type=` in the response builder and add `voice_persona_id`), `src/services/content/graph_state.py` (`"voice_persona_id": session.voice_persona_id`), `src/agents/content/pipeline.py` (`ContentState.voice_persona_id: NotRequired[UUID | None]`)
- Test: extend `tests/unit/api/test_research_params.py` (or the file that tests `resolve_session_params` — `grep -rl resolve_session_params tests`) with: inline value overrides brief; brief value used when inline is None; `inline_brief_create` carries it. Extend the graph-state test (`grep -rl build_initial_state tests/unit`) with `voice_persona_id` present in the state. Extend the PG session repo integration test if one exists (`tests/integration/db/test_pg_repositories.py`) with a round trip of the new column — set `voice_persona_id=None` unless a persona row exists (FK).

- [ ] **Step 1: Write the failing tests** (as listed) → **Step 2: Run** (AttributeError/KeyError) → **Step 3: Implement** the edits above → **Step 4: Run** `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/api tests/unit/services tests/unit/agents/content -q` + full suite → **Step 5: Commit** `git commit -m "feat(persona): voice_persona_id through brief, session request, session row and ContentState (AUTHOR-011)"`

---

### Task 7: Voice fields on `CanonicalArticle`, persistence, API response

**Files:**
- Modify: `src/models/content.py` (after `audience_persona`, line 132: `voice_persona_id: UUID | None = None`, `voice_match_score: int | None = None`, `voice_scores_by_section: dict[str, int] | None = None`, `few_shot_sample_ids: list[UUID] = Field(default_factory=list)`), `src/db/repositories.py` (`PgArticleRepository.create` adds `audience_persona=article.audience_persona, voice_persona_id=…, voice_match_score=…, voice_scores_by_section=dict(...) or None, few_shot_sample_ids=[str(i) for i in article.few_shot_sample_ids]`; `_to_model` reads them back with `UUID(x)` for the id list), `src/services/content/persist.py` (`_apply_voice(article, result)` → `article.model_copy(update={...})` for the four voice keys when present in `result`, called after `build_article`), the `CanonicalArticleResponse` schema (`grep -rn "class CanonicalArticleResponse" src/api/schemas`) + `_to_canonical_response` in `src/api/routers/canonical_articles.py:157` (add the five fields)
- Test: `tests/unit/db/test_article_repository_voice.py` (in-memory round trip keeps the fields — InMemory stores the model, trivially true, so assert on the PG mapping instead: unit-test `PgArticleRepository._to_model` with a fake row object carrying the new attributes, including `few_shot_sample_ids` as strings → UUIDs), `tests/unit/services/content/test_persist_voice.py` (`persist_pipeline_result` with `result["voice_match_score"]=88`, `voice_scores_by_section={"0": 88}`, `few_shot_sample_ids=[uuid]`, `voice_persona_id=uuid` → stored article carries them; without them → `None`/`[]`), extend `tests/unit/api/test_canonical_articles*.py` response test with the new fields; `tests/integration/db/test_pg_repositories.py` — add one article round trip asserting `audience_persona` and the voice fields survive (this is the gap fix).

- [ ] Steps 1–5 as above; commit `git commit -m "feat(persona): persist voice_persona_id/score/sections/few-shot ids (+ audience_persona) on canonical_articles (AUTHOR-011)"`

---

### Task 8: Graph nodes — `score_voice`, `fix_voice_deviations`, flagged wiring

**Files:**
- Create: `src/agents/content/voice_nodes.py`
- Modify: `src/agents/content/pipeline.py` (`ContentState` += `voice_fingerprint: NotRequired[VoiceFingerprint | None]`, `voice_block: NotRequired[str | None]`, `few_shot_sample_ids: NotRequired[list[UUID]]`, `voice_scores_by_section: NotRequired[dict[str, int]]`, `voice_match_score: NotRequired[int | None]`; `build_content_graph` wiring; `_extract_output` branch `if "voice_match_score" in result: return {"voice_match_score": result["voice_match_score"]}` placed BEFORE the `section_drafts` branch), `src/utils/tiered_llm.py` (`KNOWN_LLM_STEPS` += `content_score_voice`, `content_fix_voice`), `src/config/settings.py` comment listing step names (line ~118)
- Test: `tests/unit/agents/content/test_voice_nodes.py`, extend `tests/unit/agents/content/test_pipeline.py` with node-set assertions

**Interfaces:**
- `make_score_voice_node() -> node`: returns `{}` when `state.get("voice_fingerprint")` is falsy or status failed; else `{"voice_scores_by_section": by_section, "voice_match_score": overall}` via `score_sections`.
- `make_fix_voice_node(llm, threshold: int) -> node`: for each section whose score `< threshold` (and `word_count >= SHORT_SECTION_WORDS`): build the prose payload with the humanizer's sentinel helpers (`from src.agents.content.humanizer import _payload_for_llm, _slot_back` — internal reuse inside the same package; add both names to humanizer's `__all__` as `payload_for_llm`/`slot_back` aliases so the import is public), render `voice.fix.system` + `voice.fix.user` (`deviations` = "- " joined messages from `score_text(...).deviations[:5]`, `section_text` = payload), ONE `llm.ainvoke`, `strip_fences`, slot back, `reassemble`, verify citations preserved (`re.findall(r"\[\d+\]")` set ⊆), re-score, keep the higher-scoring body; return updated `section_drafts` + recomputed scores. Never raises (log `voice_fix_failed`, keep original).
- `make_voice_router(threshold) -> Callable[[ContentState], str]`: `"fix_voice_deviations"` if any section score `< threshold` else `"seo_optimize"`.
- Wiring in `build_content_graph` (replace `graph.add_edge("humanize", "seo_optimize")`):
```python
    voice_enabled = bool(settings and settings.enable_voice_engine)
    if voice_enabled:
        assert settings is not None  # noqa: S101
        graph.add_node("score_voice", _wrap_node("score_voice", make_score_voice_node(), deps))
        graph.add_node(
            "fix_voice_deviations",
            _wrap_node("fix_voice", make_fix_voice_node(llm, settings.voice_fix_threshold), deps),
        )
        graph.add_edge("humanize", "score_voice")
        graph.add_conditional_edges(
            "score_voice",
            make_voice_router(settings.voice_fix_threshold),
            {"fix_voice_deviations": "fix_voice_deviations", "seo_optimize": "seo_optimize"},
        )
        graph.add_edge("fix_voice_deviations", "seo_optimize")
    else:
        graph.add_edge("humanize", "seo_optimize")
```
  (extract this into `_wire_voice(graph, llm, settings, deps)` to keep `build_content_graph` under 20 added lines.)

- [ ] **Step 1: Write the failing tests**
  - `test_voice_nodes.py` with `FakeListChatModel`: score node no-op without fingerprint; scores sections and computes overall; fix node rewrites ONLY sections below threshold (assert `llm` called once for one weak section among three) and skips when all above; keeps the original when the rewrite drops a `[1]` citation; keeps the original when the rewrite scores lower; router picks `fix_voice_deviations` only when a score is below threshold; `_extract_output` returns `voice_match_score`.
  - `test_pipeline.py`: `build_content_graph(llm, None, Settings(_env_file=None, enable_voice_engine=False, enable_image_planner=False))` node set has no `score_voice`; with `enable_voice_engine=True` it has both nodes; with the flag on and a state lacking `voice_fingerprint`, a FakeLLM full run (existing helper `_full_pipeline_responses()`) still completes and `voice_match_score` is absent.
- [ ] Steps 2–5; commit `git commit -m "feat(persona): score_voice + fix_voice_deviations nodes, flagged graph wiring, step names (AUTHOR-011)"`

---

### Task 9: Voice context into the run + drafter injection

**Files:**
- Create: `src/services/persona/voice_context.py`
- Modify: `src/services/content_repositories.py` (`ContentDeps` += `persona_repo: PersonaRepository | None = None`, `embedding_service: EmbeddingService | None = None` — import under `TYPE_CHECKING`), `src/services/content/__init__.py` (`generate_full_article`: after `build_initial_state` → `state.update(await self._voice_state(session, topic))`; new method `_voice_state` delegating to `build_voice_state`), `src/services/content/outline_gate.py` (`_prepare_run` does the same via `self._content._voice_state`), `src/agents/content/section_drafter.py` (`DraftingContext.voice_block: str | None = None`), `src/agents/content/section_prompt.py` (`build_system_prompt`: `if ctx.voice_block: system += "\n\n" + ctx.voice_block`), `src/agents/content/nodes.py` (`_make_draft_ctx` passes `voice_block=deps.state.get("voice_block")`), `src/api/main.py` + `src/services/bootstrap.py` (`ContentDeps(..., persona_repo=…, embedding_service=…)` at every construction site — grep `ContentDeps(`)
- Test: `tests/unit/services/persona/test_voice_context.py`, extend `tests/unit/agents/content/test_section_prompt.py` (voice block appended to the system prompt; absent when `None`)

**Interfaces:**
- `build_voice_state(repo: PersonaRepository | None, embed: EmbedFn | None, ctx: VoiceContextInput) -> dict[str, object]` where `VoiceContextInput(voice_persona_id: UUID | None, query: str)` (query = topic title + description). Returns `{}` when no id / no repo / persona missing / no fingerprint; else `{"voice_fingerprint": fp, "voice_block": block, "few_shot_sample_ids": [ids]}` and persists any `new_embeddings` via `repo.set_sample_embedding`. `ContentService._voice_state(session, topic)` builds the input and passes `self._deps.embedding_service.try_embed` (or `None`).

- [ ] Steps 1–5 (tests: returns `{}` in each degraded case; happy path with the in-memory repo + a fake embed persists new embeddings and produces a block containing the persona's confident dims; `generate_full_article` seeds `voice_block` when the session has a persona — use the existing ContentService FakeLLM test fixture and assert the drafter's system prompt contains "Voice."); commit `git commit -m "feat(persona): resolve persona into the run state; drafter system prompt carries the voice block (AUTHOR-011)"`

---

### Task 10: Frontend — types, API, hook, Settings → Personas tab

**Files:**
- Create: `frontend/src/types/persona.ts`, `frontend/src/lib/api/personas.ts` (+ `.test.ts`), `frontend/src/hooks/use-personas.ts` (+ `.test.tsx`), `frontend/src/components/settings/personas-settings.tsx`, `personas-list.tsx`, `persona-editor.tsx`, `persona-samples.tsx` (+ tests for each component)
- Modify: `frontend/src/types/settings.ts` (`"personas"`), `frontend/src/components/settings/settings-nav.tsx` (`{ key: "personas", label: "Personas", icon: Mic }` after `prompts`; update `settings-nav.test.tsx` count), `frontend/src/app/(dashboard)/settings/page.tsx` (`{activeTab === "personas" && <PersonasSettings />}`)

**Interfaces:**
- `PersonaSummary`, `PersonaDetail`, `VoiceFingerprint`, `VoiceScore` TS mirrors (snake_case).
- `listPersonas()`, `getPersona(id)`, `createPersona({name, description})`, `updatePersona(id, patch)`, `deletePersona(id)`, `addSample(id, text)`, `deleteSample(id, sid)`, `scorePersona(id, text)`, `extractPersonaViolations(err)` (same 422 shape as prompts).
- `usePersonas()` → `{personas, isLoading, error, create, update, remove}`; `usePersona(id | null)` → `{persona, isLoading, addSample, removeSample, isMutating}`; both invalidate `["personas"]` / `["personas", id]`.
- `PersonasList({personas, selectedId, onSelect, onCreate})` (name, `sample_count`, Ready/`needs N more` badge), `PersonaEditor({persona, canEdit, onSave})` (name/description + fingerprint card: one row per dim with label, mean ± std, a confidence bar `w-[{confidence*100}%]` via inline width class is NOT allowed — use Tailwind arbitrary width classes computed from 5 buckets `w-1/5 … w-full`), `PersonaSamples({persona, canEdit, violations, onAdd, onRemove})` (textarea with live word count vs 150, list with delete). Editing gated by `currentRole() !== "viewer"` (editors may edit personas).

- [ ] Steps 1–5 (Vitest RED → implement → whole suite + eslint + tsc at the 13-error baseline → commit `feat(frontend): Personas settings tab — list, editor with fingerprint card, samples (AUTHOR-011)`)

---

### Task 11: Frontend — Voice select in the Generate modal, Voice-match chip

**Files:**
- Create: `frontend/src/components/topics/voice-select.tsx` (+ test), `frontend/src/components/articles/voice-match-chip.tsx` (+ test)
- Modify: `frontend/src/types/api.ts` (`ArticleParams.voice_persona_id?: string`), `frontend/src/types/brief.ts` (`voice_persona_id?: string | null`), `frontend/src/components/topics/use-generate-modal-state.ts` (`voicePersonaId` state; `applyBrief` sets it from `b.voice_persona_id ?? null`; `buildParams` emits `voice_persona_id: voicePersonaId ?? undefined`; `resetState` clears), `frontend/src/components/topics/generate-article-modal.tsx` (`<VoiceSelect value={gen.voicePersonaId} onChange={gen.setVoicePersonaId} />` after `DiagramModeSelect`), `frontend/src/lib/api/articles.ts` (`ArticleResponse` += the five fields), `frontend/src/hooks/use-article.ts` (`toDetail` maps `voicePersonaId`, `voiceMatchScore`, `voiceScoresBySection`, `fewShotSampleIds`), `frontend/src/types/articles.ts` (`ArticleDetail` += those), `frontend/src/components/articles/article-sidebar.tsx` (a "Voice match" card between Metadata and Usage, rendered only when `article.voiceMatchScore != null`)
- `VoiceSelect` uses `usePersonas()` and lists only `ready` personas (`None` first). `VoiceMatchChip({score, bySection})`: pill (`bg-success-light text-success` ≥80, `bg-warning-light text-warning` ≥60, `bg-error-light text-error` otherwise) showing `Voice match 82`, click → `role="dialog"` popover listing `Section N — score` rows (same anatomy as `UsageBadge`).

- [ ] Steps 1–5 (tests: select renders only ready personas and emits the id; modal state includes `voice_persona_id` in `buildParams` when set and omits it otherwise; chip band classes + popover rows; sidebar renders the chip only with a score); commit `feat(frontend): Voice select in Generate modal + Voice-match chip on the article (AUTHOR-011)`

---

### Task 12: Gates + live smoke

- [ ] Backend: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/ -q`; `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/`; `uv run mypy src/ --ignore-missing-imports | tail -1` (≤ 116 baseline; 0 in new files). Frontend: `cd frontend && npx vitest run && npx eslint src --max-warnings=5 && npx tsc --noEmit | tail -3` (13-error baseline).
- [ ] Live smoke (branch API in-process on :8010 with `--env-file D:/Workbench/github/cognify/.env` plus `COGNIFY_ENABLE_VOICE_ENGINE=true`; Docker DB already migrated to `f3b8d1c6a2e4` by Task 4; branch frontend on :3100 with `NEXT_PUBLIC_API_BASE_URL=http://localhost:8010/api/v1` from PowerShell, `.next` wiped first; CORS override if needed as in AUTHOR-012):
  1. Settings → Personas: create "Smoke voice"; paste 5 samples of ≥150 words in a distinctive voice (short sentences, many questions, first person — write them into files under the scratchpad first); the card flips to Ready and shows 13 dims with confidence bars; `POST /personas/{id}/score` with an off-voice paragraph → `off_voice`.
  2. Generate a short article from the modal with Voice = "Smoke voice" → session completes; `llm_calls` for the session has `content_fix_voice` rows only for sections whose pre-fix score was below 70 (compare with the `agent_steps` output for `content_score_voice`); article page shows the Voice-match chip with per-section popover; `GET /articles/{id}` carries `voice_persona_id`, `voice_match_score`, `few_shot_sample_ids` (non-empty).
  3. Generate once more with Voice = None → no `content_score_voice` step, no chip. Flag off (restart API without the env) → graph unchanged (assert via a quick `build_content_graph` node-set check in `uv run python -c`).
  4. Record session ids, scores, and `content_fix_voice` counts in the report; stop both servers.

---

### Task 13: Docs (no PR — local branch)

- [ ] `PROGRESS.md`: AUTHOR-011 row → `Done (2026-09-0X, local branch feature/AUTHOR-011-persona-voice — NOT pushed; migration f3b8d1c6a2e4)`; RESUME block item with design decisions, modules, endpoints, flag defaults, tests, smoke record, follow-ups (URL crawl, per-user personas, Milvus store, persona for the regenerate endpoint, re-score existing articles, `voice.dim.*` per-dimension keys if admins ask). `BACKLOG.md` row + summary (Epic 11 16/17 done; remaining AUTHOR-013 5 SP + PUBLISH-002 5 SP; velocity + 13 SP). `CLAUDE.md` Epic 11 sentence + Next action. `docs/LEARNINGS.md` **L-015**: "Model fields are not columns — `CanonicalArticle.audience_persona` silently round-tripped to `None` for three tickets; every new model field needs a column + `create()` + `_to_model()` + a PG round-trip test". Plan checkboxes ticked. Commit `docs(AUTHOR-011): status, L-015, plan ticked`.

---

## Self-review

- **Spec coverage:** §3 data model → Task 4 (+ Task 7 article columns); §4.1 fingerprint → Task 1; §4.2 scoring → Task 2; §4.3 few-shot + §4.4 block/keys → Task 3; §4.5 nodes/router/flag/step names → Task 8, draft-time injection + state seeding → Task 9; §5 plumbing → Task 6; §6 API → Task 5; §7 frontend → Tasks 10–11; §8 tests/smoke → per task + Task 12; §9 non-goals respected. Deviations (5 keys instead of 13+; 13 dims) stated in the header.
- **Placeholders:** Tasks 4–7 and 9–11 describe edits by exact file/line and interface rather than full listings where the code is a mechanical mirror of an existing pattern named in the same task (briefs repo, prompts router/tab, UsageBadge); every test in those tasks is enumerated with its assertions.
- **Type consistency:** `VoiceFingerprint.dims: dict[str, DimStat]`, `score_sections -> (dict[str,int], int|None)`, state keys `voice_fingerprint / voice_block / few_shot_sample_ids / voice_scores_by_section / voice_match_score` are the same names in Tasks 7, 8, 9; `PersonaRepository` method names match between Tasks 4, 5, 9; `EmbedFn` matches `EmbeddingService.try_embed`'s signature; frontend field names mirror the API's snake_case in Tasks 10–11.
