# VISUAL-002: AI Illustration Generation — Design Spec

## Overview

Generate one hero image per article using OpenAI DALL-E 3, following the VISUAL-001 (chart generation) pattern. A provider-agnostic `ImageGenerator` protocol enables swapping to other providers (Stability AI, self-hosted SDXL) without changing pipeline code.

**Scope boundaries:**
- One hero image per article (not per-section)
- Local filesystem storage (S3 deferred to Epic 5 Publishing)
- OpenAI DALL-E 3 as default provider
- Best-effort: API failure skips illustration, pipeline continues
- No image post-processing (crop, resize, watermark)

## Acceptance Criteria (from BACKLOG.md)

1. Agent crafts descriptive prompt from article topic
2. ~~Stable Diffusion~~ DALL-E 3 generates illustration (1024x1024)
3. Image suitable for article header / cover
4. ~~Stored in S3~~ Stored locally with article reference (S3 deferred to Epic 5)

## Section 1: ImageGenerator Protocol & OpenAI Implementation

### Protocol

Define `ImageGenerator` protocol in `src/agents/content/illustration_generator.py`:

```python
class ImageGenerator(Protocol):
    async def generate(self, prompt: str, size: tuple[int, int]) -> bytes | None: ...
```

Returns raw image bytes on success, `None` on failure. Implementations should handle errors internally, but the node factory wraps all generator calls in try/except as the resilience guarantee (see Section 3).

### OpenAI Implementation

`OpenAIDalleGenerator` implements the protocol:

- Uses `openai.AsyncOpenAI` client with API key from settings
- Calls `client.images.generate(model="dall-e-3", prompt=prompt, size="1024x1024", response_format="b64_json")`
- Decodes base64 response to bytes
- On any error (auth, rate limit, timeout, invalid response): logs warning via structlog, returns `None`

### Settings

Add to `src/config/settings.py`:

```python
openai_api_key: str = ""
illustration_output_dir: str = "generated_assets/illustrations"
dalle_model: str = "dall-e-3"
illustration_timeout: float = 30.0
```

The `openai_api_key` is sourced from `COGNIFY_OPENAI_API_KEY` environment variable (per `env_prefix="COGNIFY_"`). Must never be logged (security checklist Section 3).

### Dependency

Add `openai` package to `pyproject.toml` dependencies. Add mypy override `[[tool.mypy.overrides]]` for `openai.*` module if needed (check if package ships `py.typed`).

**Files modified:**
- `src/agents/content/illustration_generator.py` (new) — protocol + OpenAI implementation
- `src/config/settings.py` — add 3 settings
- `pyproject.toml` — add `openai` dependency

## Section 2: Prompt Generation

### Function

`generate_illustration_prompt(topic: TopicInput, summary: str, llm: BaseChatModel) -> str | None`

Uses `TopicInput` (which has `title`, `description`, `domain`) to stay within the 3-param limit. The `summary` comes from the SEO step and is passed separately since it's not part of `TopicInput`.

- Sends a structured prompt to Claude asking it to write a DALL-E image generation prompt
- Prompt template stored as `_PROMPT_TEMPLATE` constant for visibility and testability
- System prompt instructions:
  - Create a professional, editorial-style illustration suitable for an article header
  - No text/words in the image
  - No photorealistic human faces
  - Clean composition, modern aesthetic
  - Relevant to the article's domain and topic
- Input: topic (title, description, domain) + summary (from SEO step)
- Output: a single descriptive prompt string (100-200 words)
- On LLM failure: log warning, return `None`

No `IllustrationSpec` model needed — unlike charts (structured specs with data arrays), illustrations just need a prompt string.

**Files modified:**
- `src/agents/content/illustration_generator.py` — add `generate_illustration_prompt()` function

## Section 3: Pipeline Integration

### Node Factory

`make_illustration_node(llm, generator, output_dir)` in `src/agents/content/nodes.py`:

1. Extract `topic` (`TopicInput`) from `state["topic"]`
2. Extract `summary` from `state.get("seo_result")` — if `seo_result` is `None`, fall back to `topic.description`
3. Call `generate_illustration_prompt(topic, summary, llm)` — get DALL-E prompt
4. If no prompt → preserve existing visuals and return
5. Call `generator.generate(prompt, (1024, 1024))` **wrapped in try/except** — the node owns error resilience, not the protocol
6. If no bytes → preserve existing visuals and return
7. Save bytes to `{output_dir}/{session_id}/hero.png` via `asyncio.to_thread`
8. Combine existing visuals with new illustration and return

### Pipeline Graph

Add `generate_illustrations` node after `generate_charts`, before `END`:

```
... → seo_optimize → generate_charts → generate_illustrations → END
```

### Visual Accumulation

**LangGraph TypedDict state uses replacement semantics** — returning `{"visuals": [...]}` replaces the key entirely. The illustration node must:
1. Read existing visuals: `existing = list(state.get("visuals", []))`
2. Append the new illustration `ImageAsset`
3. Return the combined list: `{"visuals": existing + [new_asset]}`

This ensures chart visuals from the previous node are preserved. If illustration generation fails, return `{"visuals": existing}` to preserve charts without adding anything.

### Pipeline Wiring

In `build_content_graph()` in `pipeline.py`:
- Check `settings.openai_api_key` — if empty, skip illustration node entirely (don't add to graph)
- If key is set: construct `OpenAIDalleGenerator(api_key=settings.openai_api_key, model=settings.dalle_model, timeout=settings.illustration_timeout)`
- Pass generator to `make_illustration_node(llm, generator, settings.illustration_output_dir)`
- Add node to graph after `generate_charts`

### Best-Effort Behavior

If `openai_api_key` is empty, the illustration node is not added to the graph at all. No pipeline crash. Article publishes without hero image. If key is set but API fails at runtime, the node catches the error, logs a warning, and returns existing visuals unchanged.

**Files modified:**
- `src/agents/content/nodes.py` — add `make_illustration_node()` factory
- `src/agents/content/pipeline.py` — construct generator, wire illustration node after charts

## Section 4: Testing Strategy

### Unit Tests — Prompt Generation

- Mock LLM returns descriptive prompt string → verify returned
- Mock LLM raises exception → returns `None`

### Unit Tests — OpenAIDalleGenerator

- Mock `openai.AsyncOpenAI` returns base64 image → verify bytes decoded
- Mock API error (rate limit, invalid key) → returns `None`
- Mock timeout → returns `None`

### Unit Tests — Illustration Node

- Full flow: mock LLM prompt + mock generator bytes → `ImageAsset` with correct fields (url, caption, alt_text, metadata)
- No summary in state → skips illustration
- Generator returns `None` → empty visuals
- Existing visuals from chart node preserved (accumulation works)

### Pipeline Integration

- Updated pipeline graph tests verify illustration node is wired after charts
- Existing pipeline tests pass without OpenAI key configured

### Backward Compatibility

- Generator is optional — no key = no illustration, pipeline continues
- Existing chart generation unaffected

**Test files:**
- `tests/unit/agents/content/test_illustration_generator.py` (new) — prompt gen + OpenAI generator tests
- `tests/unit/agents/content/test_illustration_node.py` (new) — node factory tests
- Existing pipeline tests — updated for new node

## File Change Summary

| File | Change Type | Description |
|------|------------|-------------|
| `src/agents/content/illustration_generator.py` | New | ImageGenerator protocol, OpenAIDalleGenerator, generate_illustration_prompt() |
| `src/config/settings.py` | Modified | Add openai_api_key, illustration_output_dir, dalle_model |
| `src/agents/content/nodes.py` | Modified | Add make_illustration_node() factory |
| `src/agents/content/pipeline.py` | Modified | Wire illustration node after charts |
| `pyproject.toml` | Modified | Add openai dependency |
| `tests/unit/agents/content/test_illustration_generator.py` | New | Prompt + generator unit tests |
| `tests/unit/agents/content/test_illustration_node.py` | New | Node factory tests |
