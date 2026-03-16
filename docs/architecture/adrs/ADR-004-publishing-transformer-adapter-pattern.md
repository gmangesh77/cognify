---

## status: "accepted"
date: 2026-03-17
decision-makers: ["Engineering Team"]
informed-by: "docs/architecture/ARCHITECTURE_MODULARITY_REVIEW.md"
depends-on: "ADR-003 (CanonicalArticle boundary)"

# ADR-004: Centralized Publishing Service with Transformer/Adapter Pattern

## Context and Problem Statement

Cognify will publish articles to multiple platforms (Ghost, WordPress, Medium, LinkedIn — Epic 5). Each platform has different API protocols, content formats, authentication methods, and metadata requirements.

The architecture must support:
- Adding new platforms without modifying existing code
- Platform-specific content formatting (Markdown → Ghost HTML, → WordPress blocks, → Medium markdown)
- Cross-cutting concerns: retry with backoff, scheduling, credential management, rate limiting, publication tracking
- AI discoverability output: JSON-LD structured data, `robots.txt` AI crawler policies, `llms.txt` auto-generation

## Decision Drivers

- **Separation of transformation from transport**: Content formatting is a pure function; API delivery involves I/O, retries, auth. These should be separate.
- **Testability**: Transformers must be unit-testable without mocking APIs. Adapters tested with integration tests.
- **DRY**: Cross-cutting concerns (retry, scheduling, credentials, analytics) should not be duplicated per platform.
- **Extensibility**: Adding Substack should be 2 files (transformer + adapter) and a registry entry.

## Considered Options

### Option A: Independent Celery subscribers per platform
Each platform gets its own Celery task that subscribes to `article.generated` events independently. Full pub-sub decoupling.

**Rejected**: Duplicates cross-cutting concerns across every subscriber (retry logic, scheduling, credential management, rate limiting, publication analytics). Risks inconsistent behavior. The BizTalk Message Box pattern that inspired this works at enterprise integration scale with thousands of message types — Cognify has one: articles.

### Option B: Centralized Publishing Service with Transformer/Adapter pairs (Selected)
A single Publishing Service owns all cross-cutting concerns and delegates platform-specific work to transformer/adapter pairs.

### Option C: Monolithic Publishing Service
One service handles everything — formatting, API calls, retries — per platform in a single module.

**Rejected**: Mixes pure transformation logic with I/O, making transformers untestable without API mocks. Platform modules grow into the most complex, fragile files in the system.

## Decision

**Option B: Centralized Publishing Service with Transformer/Adapter pairs.**

### Architecture

```
PublishingService (cross-cutting: retry, schedule, credentials, tracking)
       |
       ├── GhostTransformer    → GhostAdapter    → Ghost Admin API
       ├── WordPressTransformer → WordPressAdapter → WP REST API
       ├── MediumTransformer   → MediumAdapter    → Medium API
       └── LinkedInTransformer → LinkedInAdapter  → LinkedIn Marketing API
```

### Component Responsibilities

| Component | Type | Responsibility |
|-----------|------|----------------|
| **PublishingService** | Orchestrator | Scheduling, credential management, retry/backoff, rate limiting, publication state tracking, `llms.txt` regeneration |
| **Transformer** | Pure function | `CanonicalArticle → PlatformPayload`. Renders HTML, JSON-LD, platform meta tags, AI disclosure. No I/O. |
| **Adapter** | I/O handler | `PlatformPayload → External API`. Authentication, HTTP calls, error mapping, DLQ. |

### Protocols

```python
class Transformer(Protocol):
    def transform(self, article: CanonicalArticle) -> PlatformPayload: ...

class Adapter(Protocol):
    async def publish(
        self, payload: PlatformPayload, schedule_at: datetime | None
    ) -> PublicationResult: ...
```

### File Structure

```
src/services/publishing/
    service.py              # PublishingService (cross-cutting orchestrator)
    protocols.py            # Transformer, Adapter, PlatformPayload protocols
    ghost/
        transformer.py      # CanonicalArticle → GhostPayload (HTML, tags, JSON-LD)
        adapter.py          # GhostPayload → Ghost Admin API
    wordpress/
        transformer.py      # CanonicalArticle → WordPressPayload (blocks, categories)
        adapter.py          # WordPressPayload → WP REST API
    medium/
        transformer.py
        adapter.py
    linkedin/
        transformer.py
        adapter.py
```

### Adding a New Platform

1. Create `src/services/publishing/<platform>/transformer.py` (pure function, unit tests)
2. Create `src/services/publishing/<platform>/adapter.py` (I/O, integration tests)
3. Register in PublishingService
4. Zero changes to orchestrator, content engine, or existing platforms

## Consequences

### Positive
- Transformers are pure functions — trivially unit-testable, no API mocking needed
- Cross-cutting concerns centralized — consistent retry, scheduling, and tracking behavior
- New platform = 2 files + registration, zero changes elsewhere
- AI discoverability (JSON-LD, `llms.txt` regeneration) fits naturally in the transformer and post-publish hooks

### Negative
- PublishingService is a coordination point — must be designed to not become a god object
- Platform-specific error handling must be surfaced through a common interface (may lose nuance)

### Neutral
- Celery tasks still used for background execution — the Publishing Service dispatches via Celery, but owns the orchestration logic

## Implementation

Platform protocols defined as part of **ARCH-001**. Individual platform implementations tracked as **PUBLISH-001** through **PUBLISH-004** in the backlog.
