# CONTENT-006: Content Humanization — Design Spec

> **Ticket**: CONTENT-006
> **Date**: 2026-03-20
> **Status**: Design approved
> **Depends on**: CONTENT-002 (section drafting)
> **Blocks**: CONTENT-005 (CanonicalArticle assembly)

---

## 1. Overview

Two-layer humanization: prompt engineering at generation time (Layer 1 prevention) plus a `humanize` pipeline node with mechanical regex fixes and LLM rewrite for flagged sections (Layer 2 correction). Uses a slop detection system inspired by slop-radar (200+ phrase database, 14 structural patterns, scoring engine) — all baked into Python constants with zero external dependencies.

### Acceptance Criteria (from BACKLOG.md)

#### Layer 1: Prevention (prompt engineering)
- System prompts in `outline_generator.py` and `section_drafter.py` updated with explicit style rules
- LLM instructed to avoid em-dashes, formal transitions, hedge words, buzzwords
- LLM instructed to use natural conversational tone, vary sentence length, be specific not abstract

#### Layer 2: Correction (humanize node)
- New `humanize` pipeline node after `validate_article`, before `manage_citations`
- Mechanical fixes: replace all em-dashes/en-dashes with periods or commas, strip hedge phrases
- Slop scoring: detect phrase hits and structural patterns, score 0-100
- LLM rewrite for sections scoring < 70 (single attempt, no retry loop)
- Metrics logging: violation count, sections rewritten, mechanical fixes applied
- Style rules as hardcoded Python constants (option A)

### Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Style rules location | Hardcoded Python constants | Editorial concern, not deployment config. Easy to update and test |
| Em-dash rule | Zero tolerance — replace ALL | No human uses special characters not on standard keyboards |
| Rewrite threshold | Score < 70 (SUSPICIOUS) | High standard for our own generated content |
| Rewrite retry | Single attempt only | Avoids infinite loops; mechanical fixes catch remaining issues |
| Humanize node failure mode | Non-fatal | Worst case is mechanical fixes only; never blocks the pipeline |
| Slop database source | slop-radar (MIT), ported to Python | 200+ curated phrases, 14 patterns, battle-tested. Zero dependency |

---

## 2. Data Structures

### Phrase database: `src/agents/content/slop_phrases.py` (~80 lines)

Categorized phrase lists ported from slop-radar's 200+ English phrases:

```python
SLOP_PHRASES: dict[str, list[str]] = {
    "buzzwords": [
        "delve", "leverage", "cutting-edge", "robust", "seamless", "holistic",
        "synergy", "paradigm", "ecosystem", "harness", "unlock", "empower",
        "streamline", "optimize", "foster", "curated", "bespoke", "tailored",
        "game-changer", "game-changing", "state-of-the-art", "revolutionize",
        "versatile", "innovative", ...
    ],
    "transitions": [
        "moreover", "furthermore", "additionally", "in conclusion",
        "to summarize", "firstly", "secondly", "thirdly", "in this regard",
        "to that end", "with that being said", "last but not least", ...
    ],
    "hedges": [
        "essentially", "fundamentally", "it's worth noting",
        "it is important to note", "interestingly", "indeed",
        "needless to say", "arguably", "it could be argued", ...
    ],
    "ai_openers": [
        "let me break this down", "let me explain", "let me walk you through",
        "here's the thing", "here's what you need to know", "here's the deal", ...
    ],
    "overblown": [
        "unprecedented", "transformative", "revolutionary", "groundbreaking",
        "remarkable", "exceptional", "unparalleled", "trailblazing",
        "pioneering", "thought-provoking", "insightful", "profound", ...
    ],
    "corporate": [
        "stakeholder", "bandwidth", "low-hanging fruit", "move the needle",
        "north star", "value-add", "best-in-class", "next-level",
        "thought leadership", "pain point", "value proposition", ...
    ],
    "fluff": [
        "in today's world", "in today's fast-paced", "as we navigate",
        "ever-evolving", "ever-changing", "dynamic landscape",
        "shifting landscape", "rapidly evolving", "fast-paced", ...
    ],
    "meta": [
        "in this article", "in this guide", "in this post",
        "comprehensive guide", "definitive guide", "ultimate guide",
        "step-by-step guide", ...
    ],
}
```

Full list: ~200 phrases across 8 categories.

### Structural patterns: `src/agents/content/slop_patterns.py` (~60 lines)

```python
class PatternRule(BaseModel, frozen=True):
    """Structural pattern that signals AI-generated text."""
    name: str
    pattern: str
    weight: int
    flags: str = "i"  # maps to Python re flags: "i"=IGNORECASE, "m"=MULTILINE, "im"=both

STRUCTURAL_PATTERNS: list[PatternRule] = [
    PatternRule(name="em_dash", pattern=r"[\u2014\u2013]", weight=3),
    PatternRule(name="let_me_starter", pattern=r"^\s*let me \w+", weight=3, flags="im"),
    PatternRule(name="heres_the_thing", pattern=r"here'?s (the thing|what|the deal|the kicker)", weight=3),
    PatternRule(name="binary_contrast", pattern=r"not (just|only|merely|simply) .{5,40}, but (also )?", weight=3),
    PatternRule(name="wh_starters", pattern=r"^\s*(what makes this|why this matters|why it matters|how this works|what this means)", weight=4, flags="im"),
    PatternRule(name="bullet_overload", pattern=r"(^\s*[-*]\s.+\n){6,}", weight=4, flags="m"),
    PatternRule(name="triple_adjective", pattern=r"\b\w+(?:ly)?\b,\s+\b\w+(?:ly)?\b,\s+(?:and\s+)?\b\w+(?:ly)?\b\s+\w+", weight=2),
    PatternRule(name="meta_reference", pattern=r"in this (article|post|guide|blog|piece|section|tutorial|overview|essay)", weight=3),
    PatternRule(name="passive_voice", pattern=r"\b(is|are|was|were|been|being)\s+\w+ed\b", weight=1),
    PatternRule(name="worth_noting", pattern=r"^\s*it('s|\s+is)\s+worth\s+(noting|mentioning|highlighting|pointing out)", weight=4, flags="im"),
    PatternRule(name="colon_list_intro", pattern=r":\s*\n\s*[-*1]", weight=2, flags="m"),
    PatternRule(name="emoji_header", pattern=r"^\s*[\U0001F300-\U0001FAD6]\s+\*\*", weight=5, flags="m"),
    PatternRule(name="number_list_bold", pattern=r"^\s*\d+\.\s+\*\*.+\*\*", weight=2, flags="m"),
    PatternRule(name="tldr_pattern", pattern=r"(tl;?dr|key takeaway|bottom line|in a nutshell)\s*:?\s*\n", weight=3, flags="im"),
]
```

### Repetitive sentence opener detection

Not a regex pattern — handled as a separate check in `score_text()`:
- Split text into sentences
- Extract the first word of each sentence
- If any word appears as opener for > 30% of sentences (minimum 3 occurrences), deduct -3 per repeated opener beyond 2
- Common offenders: "The", "This", "It", "These", "However"

```python
def _check_repetitive_openers(sentences: list[str]) -> list[Violation]:
    """Flag words that start > 30% of sentences."""
    ...
```
```

---

## 3. Scoring Engine

### New file: `src/agents/content/slop_scorer.py` (~80 lines)

Pure functions, no LLM, no I/O.

**`score_text(text: str) -> SlopScore`**:
- Start at 100
- Scan for phrase matches: `-2 per hit` (case-insensitive whole-word `\b` matching)
- Scan for structural patterns: `-weight per match`
- Passive voice density: `-10 if passive matches > 30% of sentence count`
- Bonus: `+5 if text contains `?`` (questions signal natural writing)
- Bonus: `+5 if sentence length stddev > 4` (varied rhythm)
- Clamp 0-100

**Return models (in `src/models/content_pipeline.py`):**

```python
class Violation(BaseModel, frozen=True):
    """A single slop violation with location context."""
    category: str       # buzzwords, transitions, hedges, ai_openers, etc.
    phrase: str          # matched phrase or pattern name
    sentence_index: int  # which sentence (0-based)

class SlopScore(BaseModel, frozen=True):
    score: int
    rating: str  # HUMAN / MOSTLY_CLEAN / SUSPICIOUS / LIKELY_AI / PURE_SLOP
    violations: list[Violation]
    phrase_deductions: int
    pattern_deductions: int
```

The `Violation` model provides location (sentence index) and category for each hit. The LLM rewrite prompt uses this to show specific violations: `"Sentence 3: buzzword 'delve'. Sentence 7: transition 'moreover'."`

Rating thresholds: >= 90 HUMAN, >= 70 MOSTLY_CLEAN, >= 50 SUSPICIOUS, >= 30 LIKELY_AI, < 30 PURE_SLOP.

**`score_section(section: SectionDraft) -> SlopScore`** — convenience wrapper.

---

## 4. Mechanical Fixer & LLM Rewriter

### New file: `src/agents/content/humanizer.py` (~100 lines)

**`fix_mechanical(text: str) -> str`** — regex, no LLM:
- Replace all em-dashes `—` and en-dashes `–`:
  - If followed by lowercase word → comma: `"concept — which"` → `"concept, which"`
  - If followed by uppercase or end of clause → period + capitalize: `"clear — The"` → `"clear. The"`
- Strip trailing hedge phrases
- Normalize multiple spaces/newlines

**`rewrite_section(section, score, llm) -> SectionDraft`** — LLM rewrite for sections scoring < 70:

System prompt:
> You are an editor making AI-generated text sound natural. Rewrite the section to fix these specific issues. Keep all factual claims and [N] citations exactly as they are. Do not change the meaning. Only fix the writing style.

User prompt includes:
- The section text
- Specific violations: `"Phrases found: delve, leverage, moreover. Patterns: binary_contrast, let_me_starter"`
- Target: "Remove these phrases, vary sentence structure, use conversational tone"

Returns new `SectionDraft` with updated `body_markdown` and recalculated `word_count`. Post-rewrite: verify all `[N]` references still exist. If citations lost, reject rewrite and keep original.

**Single attempt only** — no retry loop. If rewrite still scores < 70, accept and log warning.

---

## 5. Pipeline Integration

### Node placement

```
... → validate_article → manage_citations → humanize → seo_optimize → END
```

Humanize runs after citation management (global renumbering already complete) and before SEO optimization. This is safer — the humanizer operates on finalized `[N]` references and only needs to verify it doesn't drop them, rather than dealing with pre-renumbered local references.

### Node: `make_humanize_node(llm)` factory

New file `src/agents/content/humanize_node.py` (~60 lines):

1. Read `section_drafts` from state
2. Run `fix_mechanical()` on each section
3. Score each section with `score_text()`
4. For sections scoring < 70: call `rewrite_section(section, score, llm)`
5. Run `fix_mechanical()` again on rewritten sections (catch LLM-introduced slop)
6. Return `{"section_drafts": updated_drafts}`

**Non-fatal** — on exception, log error and return original `section_drafts` unchanged. Never sets `status: "failed"`.

### Graph wiring in `pipeline.py`

```python
graph.add_node("humanize", make_humanize_node(llm))
graph.add_edge("manage_citations", "humanize")
graph.add_edge("humanize", "seo_optimize")
```

Replaces `manage_citations → seo_optimize` edge.

### Prompt engineering (Layer 1)

Update `_SYSTEM_PROMPT` in `outline_generator.py` to append:
> Do not use em-dashes. Use periods or commas instead. Avoid formal transitions like moreover, furthermore, in conclusion. Write in a natural conversational tone. Vary sentence length. Be specific and concrete, not abstract.

Update `_SYSTEM_PROMPT` in `section_drafter.py` to append:
> Do not use em-dashes or en-dashes. Use periods or commas instead. Avoid words like delve, leverage, innovative, transformative, unprecedented. Skip transitions like moreover, furthermore, additionally. Vary sentence length and structure. Write as a knowledgeable human, not an AI assistant.

---

## 6. Error Handling & Logging

### Error scenarios

| Error | Handling | Pipeline impact |
|---|---|---|
| Mechanical fix regex error | Log warning, return original text | None |
| LLM rewrite fails | Log warning, keep mechanically-fixed version | None |
| Rewritten section loses citations | Reject rewrite, keep pre-rewrite version | None |
| Rewritten section still < 70 | Accept it, log warning | None |

The humanize node is **non-fatal** — never sets `status: "failed"`. Worst case: article passes through with only mechanical fixes.

### Structured logging

```python
logger.info("humanize_started", section_count=N)
logger.info("humanize_section_scored", section_index=i, score=S, rating=R)
logger.info("humanize_mechanical_fixes", section_index=i, em_dashes_replaced=N)
logger.info("humanize_rewrite_triggered", section_index=i, score=S, phrase_hits=[...])
logger.info("humanize_rewrite_complete", section_index=i, old_score=S1, new_score=S2)
logger.warning("humanize_rewrite_still_low", section_index=i, score=S)
logger.warning("humanize_citations_lost", section_index=i, missing=[N])
logger.info("humanize_complete", sections_rewritten=N, sections_mechanical_only=M)
```

---

## 7. Testing Strategy

### Unit tests (~20 tests)

**`test_slop_scorer.py`** (~8 tests):
- Clean text scores > 90
- Buzzword-heavy text scores < 50
- Phrase matching is case-insensitive and whole-word
- Structural patterns detected (em-dash, let-me-starter, binary-contrast)
- Question bonus applied (+5)
- Sentence variance bonus applied (+5)
- Passive voice density deduction at > 30%
- Score clamped 0-100

**`test_humanizer.py`** (~7 tests):
- `fix_mechanical` replaces em-dashes with commas (lowercase follows)
- `fix_mechanical` replaces em-dashes with periods (uppercase follows)
- `fix_mechanical` handles en-dashes too
- `rewrite_section` returns updated SectionDraft with new word count
- Rewrite preserves citation references
- Rewrite rejected if citations lost (original kept)
- Single rewrite attempt, no retry

**`test_humanize_node.py`** (~3 tests):
- Sections below 70 get rewritten, above 70 get mechanical fixes only
- Node never returns failed status (returns original on error)
- Pipeline with humanize node produces updated section_drafts

**`test_prompt_updates.py`** (~2 tests):
- Outline generator prompt contains "Do not use em-dashes"
- Section drafter prompt contains "Avoid formal transitions"

**Total: ~20 new tests.**

---

## 8. File Impact Summary

| File | Action | Est. Lines |
|---|---|---|
| `src/agents/content/slop_phrases.py` | **New** — 200+ phrases in 8 categories | ~140 |
| `src/agents/content/slop_patterns.py` | **New** — PatternRule model + 14 patterns | ~60 |
| `src/agents/content/slop_scorer.py` | **New** — score_text(), score_section(), rating logic | ~80 |
| `src/agents/content/humanizer.py` | **New** — fix_mechanical(), rewrite_section() | ~100 |
| `src/agents/content/humanize_node.py` | **New** — make_humanize_node() factory | ~60 |
| `src/models/content_pipeline.py` | Modify — add SlopScore model | +10 |
| `src/agents/content/pipeline.py` | Modify — add humanize node, update edges | +5 |
| `src/agents/content/outline_generator.py` | Modify — append style rules to system prompt | +5 |
| `src/agents/content/section_drafter.py` | Modify — append style rules to system prompt | +5 |
| Tests (5 files) | New + extend | ~250 |
| **Total** | | ~715 |

---

## 9. Out of Scope

- **Multi-language support** — English only (slop-radar has German, but we don't need it)
- **Fuzzy matching** — slop-radar supports fuzzy phrase matching; we use exact whole-word matching (simpler, sufficient)
- **User-configurable rules** — rules are hardcoded constants, not settings/config files
- **Scoring persistence** — slop scores are logged but not stored on ArticleDraft (can be added later)
- **Full slop-radar integration** — we port the data and algorithm, not the library
