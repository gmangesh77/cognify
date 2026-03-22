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

Returns raw image bytes on success, `None` on failure. All implementations must handle errors internally and never raise.

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
```

### Dependency

Add `openai` package to `pyproject.toml` dependencies.

**Files modified:**
- `src/agents/content/illustration_generator.py` (new) — protocol + OpenAI implementation
- `src/config/settings.py` — add 3 settings
- `pyproject.toml` — add `openai` dependency

## Section 2: Prompt Generation

### Function

`generate_illustration_prompt(title: str, summary: str, domain: str, llm: BaseChatModel) -> str | None`

- Sends a structured prompt to Claude asking it to write a DALL-E image generation prompt
- System prompt instructions:
  - Create a professional, editorial-style illustration suitable for an article header
  - No text/words in the image
  - No photorealistic human faces
  - Clean composition, modern aesthetic
  - Relevant to the article's domain and topic
- Input: article title, summary (from SEO step), domain (e.g., "cybersecurity")
- Output: a single descriptive prompt string (100-200 words)
- On LLM failure: log warning, return `None`

No `IllustrationSpec` model needed — unlike charts (structured specs with data arrays), illustrations just need a prompt string.

**Files modified:**
- `src/agents/content/illustration_generator.py` — add `generate_illustration_prompt()` function

## Section 3: Pipeline Integration

### Node Factory

`make_illustration_node(llm, generator, output_dir)` in `src/agents/content/nodes.py`:

1. Extract `title`, `summary`, `domain` from `ContentState` (via `topic` and `seo_metadata`)
2. Call `generate_illustration_prompt(title, summary, domain, llm)` — get DALL-E prompt
3. If no prompt → return `{"visuals": []}` (skip gracefully)
4. Call `generator.generate(prompt, (1024, 1024))` — get image bytes
5. If no bytes → return `{"visuals": []}` (skip gracefully)
6. Save bytes to `{output_dir}/{session_id}/hero.png` via `asyncio.to_thread`
7. Return `{"visuals": [ImageAsset(url=path, caption=title, alt_text=prompt, metadata={"generator": "dall-e-3", "type": "hero"})]}`

### Pipeline Graph

Add `generate_illustrations` node after `generate_charts`, before `END`:

```
... → seo_optimize → generate_charts → generate_illustrations → END
```

### Visual Accumulation

The illustration node appends to visuals already produced by the chart node. The node reads existing `state.get("visuals", [])` and returns the combined list (existing charts + new illustration).

### Best-Effort Behavior

If `openai_api_key` is empty, the generator is not created and the node is either skipped or returns empty visuals. No pipeline crash. Article publishes without hero image.

**Files modified:**
- `src/agents/content/nodes.py` — add `make_illustration_node()` factory
- `src/agents/content/pipeline.py` — add illustration node to graph, wire after charts

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
