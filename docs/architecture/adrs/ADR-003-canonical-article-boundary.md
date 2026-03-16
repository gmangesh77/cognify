---

## status: "accepted"
date: 2026-03-17
decision-makers: ["Engineering Team"]
informed-by: "docs/architecture/ARCHITECTURE_MODULARITY_REVIEW.md"

# ADR-003: CanonicalArticle as the Content Pipeline Boundary

## Context and Problem Statement

Cognify's architecture has three major pipeline phases: trend discovery (inbound), content generation (orchestration), and publishing (outbound). The inbound phase already has a clean canonical model (`RawTopic`) — all 5 trend sources normalize to it, and the ranking service operates on it without knowing where data came from.

The content generation pipeline (Epics 2-4) and publishing pipeline (Epic 5) are about to be built. Without an explicit boundary between "the article is done" and "now format it for Ghost/WordPress/Medium," there is a risk that:

- Platform-specific formatting logic leaks into the Writer Agent or content generation code
- Each new publishing platform requires changes to the content engine
- SEO optimization becomes platform-coupled (Ghost meta tags differ from WordPress)
- AI discoverability concerns (JSON-LD, `llms.txt`, structured data) have no clear home
- The Writer Agent's output format becomes the de facto contract without deliberate design

## Decision Drivers

- **Separation of concerns**: Content intelligence (research, drafting, SEO) must be decoupled from content delivery (platform formatting, API transport)
- **Testability**: Platform transformers should be pure functions, fully unit-testable without I/O
- **Extensibility**: Adding a new publishing platform should require zero changes to the content engine
- **Consistency with inbound pattern**: The `RawTopic` canonical model works well — apply the same principle outbound
- **AI discoverability**: Structured data (JSON-LD), `llms.txt` summaries, and content provenance need a clear data source

## Considered Options

### Option A: No explicit boundary — Writer Agent outputs directly to Publishing Service
The Writer Agent produces platform-ready content. Each platform gets a different output path inside the Writer Agent.

**Rejected**: Couples content generation to publishing. Adding Substack means modifying the Writer Agent. Testing platform formatting requires mocking the entire generation pipeline.

### Option B: CanonicalArticle as the explicit boundary (Selected)
Define a `CanonicalArticle` Pydantic model that is the output contract of content generation and the input contract of all publishing. Everything upstream produces it. Everything downstream consumes it.

### Option C: Generic dict/JSON blob passed between stages
Use untyped dictionaries with schema validation at publish time.

**Rejected**: Loses compile-time safety, makes testing harder, and violates the project's Pydantic-first approach.

## Decision

**Option B: CanonicalArticle as the explicit boundary.**

The `CanonicalArticle` Pydantic model becomes the system's central contract between content generation and content delivery.

### Model Structure

```python
class CanonicalArticle(BaseModel):
    id: UUID
    title: str
    subtitle: str | None
    body_markdown: str
    summary: str                  # 1-2 sentence extractive summary
    key_claims: list[str]         # Top 3-5 factual claims with citation refs
    content_type: str             # "article", "how-to", "analysis", "report"
    seo: SEOMetadata              # Platform-neutral SEO defaults
    citations: list[Citation]
    visuals: list[ImageAsset]
    authors: list[str]
    domain: str
    generated_at: datetime
    provenance: Provenance        # Model versions, embedding versions
    ai_generated: bool = True     # AI disclosure flag
```

Supporting models: `SEOMetadata`, `Citation`, `ImageAsset`, `Provenance`.

### Boundary Rules

1. **Nothing upstream of CanonicalArticle knows about publishing platforms.** The Writer Agent, research agents, and SEO service operate on platform-neutral concepts.
2. **Nothing downstream of CanonicalArticle knows about content generation.** Platform transformers receive a fully formed article and produce platform-specific payloads.
3. **The only shared code** between content generation and publishing is the `CanonicalArticle` schema itself.

### AI Discoverability Support

The model includes fields specifically for AI agent consumption:
- `summary` — for `llms.txt` entries and AI snippet extraction
- `key_claims` — structured factual claims for RAG retrieval by AI agents
- `content_type` — maps to Schema.org `@type` for JSON-LD structured data
- `provenance` — model version tracking for reproducibility and AI Act compliance
- `ai_generated` — drives disclosure rendering per platform requirements

## Consequences

### Positive
- Clear contract between content generation and publishing — each can evolve independently
- Platform transformers are pure functions — trivially unit-testable
- Adding a new platform = new transformer + adapter, zero changes to content engine
- AI discoverability has a clear data source (CanonicalArticle fields → transformer → structured output)
- Consistent with the inbound pattern (RawTopic as canonical inbound model)

### Negative
- All content generation must produce a valid CanonicalArticle — no shortcuts for quick publishing
- Schema changes require coordination between content and publishing teams
- Slight overhead for simple publishing scenarios (the model has more fields than a basic blog post needs)

### Neutral
- SEO metadata in CanonicalArticle is platform-neutral defaults; platform transformers may override (e.g., Ghost meta tag length differs from Medium)

## Implementation

Tracked as **ARCH-001** in the backlog. Must be completed before RESEARCH-001 (Agent Orchestrator) begins, since the orchestrator's output contract is this model.
