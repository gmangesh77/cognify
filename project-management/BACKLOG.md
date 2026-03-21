# Product Backlog: Cognify

## Backlog Prioritization
Ordered by business value and dependency. MoSCoW priority: **Must**, **Should**, **Could**, **Won't** (this release).

---

## Epic 0: Design System & UI/UX
**Goal**: Establish a consistent design system and finalize all screen designs in Pencil before frontend implementation.

**Design file**: `pencil_designs/cognify.pen` (Pencil Desktop)

### DESIGN-001: Design System Setup [Must] — DONE
**As a** developer, **I want** a design system with variables for colors, typography, and spacing, **so that** all screens share a consistent visual language.
- **Status**: Done (branch `feature/API-003-rbac-authorization`)
- **Plan**: [`docs/superpowers/plans/2026-03-13-design-001-design-system-setup.md`](../docs/superpowers/plans/2026-03-13-design-001-design-system-setup.md)
- **Spec**: [`docs/superpowers/specs/2026-03-13-design-001-design-system-setup.md`](../docs/superpowers/specs/2026-03-13-design-001-design-system-setup.md)
- **Acceptance Criteria**:
  - Color palette defined as Pencil variables: primary, secondary, accent, neutrals (50-900), semantic (success, warning, error, info)
  - Typography scale: font families, sizes (xs through 3xl), weights, line heights
  - Spacing tokens: 4px grid system (4, 8, 12, 16, 20, 24, 32, 40, 48, 64)
  - Border radii, shadows, and elevation levels defined
  - Dark mode consideration (variable-based theming)
- **Story Points**: 3
- **Blocks**: All DESIGN and DASH tickets

### DESIGN-002: Reusable Components [Must] — DONE
**As a** designer, **I want** reusable UI components in Pencil, **so that** screens are consistent and easy to update.
- **Status**: Done (branch `feature/API-003-rbac-authorization`)
- **Acceptance Criteria**:
  - Sidebar navigation component (with icons, active state, collapsed state)
  - Card component (metric card, topic card, article card variants)
  - Button component (primary, secondary, ghost, destructive; sm/md/lg sizes)
  - Badge/tag component (status badges: live, scheduled, failed, trending, new, rising)
  - Table component (header row, data row, sortable columns)
  - Form inputs (text field, dropdown, toggle, checkbox)
  - Modal/dialog component
  - Empty state component
- **Story Points**: 5
- **Blocks**: All DESIGN screen tickets

### DESIGN-003: Dashboard Screen — Final Design [Must] — DONE
**As a** user, **I want** a polished dashboard overview, **so that** I can monitor system activity at a glance.
- **Status**: Done (branch `feature/API-003-rbac-authorization`)
- **Acceptance Criteria**:
  - Modern metric cards with subtle shadows and trend indicators (up/down arrows with %)
  - Trending Topics list with clear visual hierarchy (score, title, source badges, time)
  - Recent Articles list with status chips and publish dates
  - Responsive grid layout with proper spacing
  - Uses design system components from DESIGN-001/002
- **Story Points**: 3
- **Blocks**: DASH-001

### DESIGN-004: Topic Discovery Screen — Final Design [Must] — DONE
**As a** user, **I want** a refined topic discovery screen, **so that** browsing and filtering topics is intuitive.
- **Status**: Done (branch `feature/API-003-rbac-authorization`)
- **Acceptance Criteria**:
  - Topic cards with depth (shadows, hover states) and clear badge hierarchy
  - Filter bar with source pills, time range selector, and domain switcher
  - Score visualization (progress bar or gauge, not just number)
  - "Generate Article" CTA with clear affordance
  - Empty state for when no topics match filters
- **Story Points**: 3
- **Blocks**: DASH-002

### DESIGN-005: Article View Screen — Final Design [Must] — DONE
**As a** user, **I want** a polished article preview, **so that** reviewing and publishing is a seamless experience.
- **Status**: Done (branch `feature/API-003-rbac-authorization`)
- **Acceptance Criteria**:
  - Clean article typography (headings, body, code blocks, blockquotes)
  - Agent workflow panel with step icons, durations, and status indicators
  - Sources section with clickable links and citation markers
  - Publish action bar with platform selection checkboxes
  - Inline chart/image rendering within article body
- **Story Points**: 3
- **Blocks**: DASH-003

### DESIGN-006: Research Sessions Screen — Final Design [Should] — DONE
**As a** user, **I want** a refined research hub, **so that** monitoring agent work is clear and informative.
- **Status**: Done (branch `feature/API-003-rbac-authorization`)
- **Acceptance Criteria**:
  - Session cards with multi-step progress indicators (not just a single bar)
  - Agent step breakdown within each session (expandable)
  - Knowledge base stats with visual gauges (storage, document count)
  - Data source connectors with live/disconnected status icons
  - "New Research" flow with topic selection
- **Story Points**: 3
- **Blocks**: DASH-004

### DESIGN-007: Publishing Screen — Final Design [Should] — DONE
**As a** publisher, **I want** a refined publishing dashboard, **so that** tracking publications across platforms is easy.
- **Status**: Done (branch `feature/API-003-rbac-authorization`)
- **Acceptance Criteria**:
  - Platform overview cards with connection status and article counts
  - Published articles table with sortable columns, status badges, and view counts
  - Retry action for failed publications
  - "Add Platform" flow with credential input
  - Scheduling UI for future publications
- **Story Points**: 3
- **Blocks**: PUBLISH-005

### DESIGN-008: Settings Screen — Final Design [Must] — DONE
**As an** admin, **I want** a well-organized settings screen, **so that** configuration is intuitive and supports multiple domains.
- **Status**: Done (branch `feature/API-003-rbac-authorization`)
- **Acceptance Criteria**:
  - **Multi-domain management**: domain list/switcher, add/edit/delete domains (not a single dropdown)
  - Per-domain config: trend sources, keywords, SEO settings, LLM preferences
  - General settings section with clear grouping and section dividers
  - API key management with masked values, status indicators, and rotate actions
  - LLM configuration with model dropdowns and token budget sliders
  - SEO defaults with toggle switches and descriptions
- **Story Points**: 5
- **Blocks**: DASH-005
- **Note**: Current design shows single "Domain Focus: Cybersecurity" — must be redesigned for multi-domain support per `DOMAIN_CONFIG` data model

### DESIGN-009: Login & Auth Screens [Must] — DONE
**As a** user, **I want** a polished login experience, **so that** authentication feels professional and secure.
- **Status**: Done (branch `feature/API-003-rbac-authorization`)
- **Acceptance Criteria**:
  - Login screen with email/password form, Cognify branding
  - Error states (invalid credentials, rate limited)
  - Loading/submitting state
  - Consistent with dashboard design language
- **Story Points**: 2
- **Blocks**: Frontend auth implementation

---

## Epic 1: Trend Discovery Engine
**Goal**: Automatically discover trending topics in a configured domain from multiple data sources.

### TREND-001: Google Trends Integration [Must] — DONE
**As a** content team member, **I want** the system to fetch trending topics from Google Trends API, **so that** I can identify rising search interest in my domain.
- **Status**: Done (branch `feature/TREND-001-google-trends-integration`)
- **Plan**: [`docs/superpowers/plans/2026-03-13-trend-001-google-trends-integration.md`](../docs/superpowers/plans/2026-03-13-trend-001-google-trends-integration.md)
- **Spec**: [`docs/superpowers/specs/2026-03-13-trend-001-google-trends-integration-design.md`](../docs/superpowers/specs/2026-03-13-trend-001-google-trends-integration-design.md)
- **Acceptance Criteria**:
  - System polls Google Trends API on configurable interval (default: 30 min)
  - Results filtered by configured domain keywords
  - Trend scores normalized to 0-100 scale
  - Results stored in database with source attribution
  - Graceful handling when API is unavailable (cached fallback)
- **Story Points**: 5

### TREND-002: Reddit Trend Source [Must] — DONE
**As a** content team member, **I want** trending Reddit posts monitored via PRAW, **so that** community-driven topics are captured.
- **Status**: Done (branch `feature/TREND-002-reddit-trend-source`)
- **Plan**: [`docs/superpowers/plans/2026-03-14-trend-002-reddit-trend-source.md`](../docs/superpowers/plans/2026-03-14-trend-002-reddit-trend-source.md)
- **Spec**: [`docs/superpowers/specs/2026-03-14-trend-002-reddit-trend-source-design.md`](../docs/superpowers/specs/2026-03-14-trend-002-reddit-trend-source-design.md)
- **Acceptance Criteria**:
  - Monitors configured subreddits (e.g., r/cybersecurity, r/programming)
  - Ranks by upvotes, comment velocity, and recency
  - Deduplicates cross-posted topics
  - Respects Reddit API rate limits
- **Story Points**: 5

### TREND-003: Hacker News Integration [Must] — DONE
**As a** content team member, **I want** Hacker News top stories tracked, **so that** tech community trends are captured.
- **Status**: Done (branch `feature/TREND-003-hackernews-integration`)
- **Plan**: [`docs/superpowers/plans/2026-03-13-trend-003-hackernews-integration.md`](../docs/superpowers/plans/2026-03-13-trend-003-hackernews-integration.md)
- **Spec**: [`docs/superpowers/specs/2026-03-13-trend-003-hackernews-integration-design.md`](../docs/superpowers/specs/2026-03-13-trend-003-hackernews-integration-design.md)
- **Acceptance Criteria**:
  - Fetches top/new/best stories via Algolia HN API
  - Filters by domain relevance
  - Scores by points and comment count
- **Story Points**: 3

### TREND-004: NewsAPI Integration [Should] — DONE
**As a** content team member, **I want** news headlines aggregated from NewsAPI, **so that** mainstream coverage is included.
- **Status**: Done (branch `feature/TREND-004-newsapi-integration`)
- **Plan**: [`docs/superpowers/plans/2026-03-15-trend-004-newsapi-integration.md`](../docs/superpowers/plans/2026-03-15-trend-004-newsapi-integration.md)
- **Spec**: [`docs/superpowers/specs/2026-03-15-trend-004-newsapi-integration-design.md`](../docs/superpowers/specs/2026-03-15-trend-004-newsapi-integration-design.md)
- **Acceptance Criteria**:
  - Fetches headlines by category and keyword
  - Deduplicates similar headlines across sources
  - Stores source metadata (publication, date, URL)
- **Story Points**: 3

### TREND-005: arXiv Paper Feed [Should] — DONE
**As a** researcher, **I want** recent arXiv papers in my domain tracked, **so that** academic trends are captured.
- **Status**: Done (branch `feature/TREND-005-arxiv-paper-feed`)
- **Plan**: [`docs/superpowers/plans/2026-03-15-trend-005-arxiv-paper-feed.md`](../docs/superpowers/plans/2026-03-15-trend-005-arxiv-paper-feed.md)
- **Spec**: [`docs/superpowers/specs/2026-03-15-trend-005-arxiv-paper-feed-design.md`](../docs/superpowers/specs/2026-03-15-trend-005-arxiv-paper-feed-design.md)
- **Acceptance Criteria**:
  - Monitors arXiv RSS/API for configured categories
  - Extracts title, abstract, authors, and categories
  - Ranks by recency and citation potential
- **Story Points**: 3

### TREND-006: Topic Ranking & Deduplication [Must] — DONE
**As a** user, **I want** topics ranked by composite score and deduplicated, **so that** I see the most relevant unique topics.
- **Status**: Done (branch `feature/TREND-006-topic-ranking-dedup`)
- **Plan**: [`docs/superpowers/plans/2026-03-13-trend-006-topic-ranking-dedup.md`](../docs/superpowers/plans/2026-03-13-trend-006-topic-ranking-dedup.md)
- **Spec**: [`docs/superpowers/specs/2026-03-13-trend-006-topic-ranking-dedup-design.md`](../docs/superpowers/specs/2026-03-13-trend-006-topic-ranking-dedup-design.md)
- **Acceptance Criteria**:
  - Composite scoring: relevance (0.4), recency (0.3), velocity (0.2), source diversity (0.1)
  - Semantic deduplication using embedding cosine similarity (threshold: 0.85)
  - Top N topics surfaced in dashboard (configurable N)
  - Domain keyword filtering applied before ranking
- **Story Points**: 8

---

## Epic 8: Architecture Foundation
**Goal**: Establish core contracts and patterns identified in the Architecture Modularity Review before building the research and content pipelines.

**Reference**: [`docs/architecture/ARCHITECTURE_MODULARITY_REVIEW.md`](../docs/architecture/ARCHITECTURE_MODULARITY_REVIEW.md)

### ARCH-001: CanonicalArticle Model & Content Contracts [Must] — DONE
**As a** developer, **I want** the CanonicalArticle Pydantic model and related content contracts defined, **so that** the research pipeline and publishing pipeline share a clear output/input boundary.
- **Status**: Done (branch `feature/ARCH-001-canonical-article-contracts`, PR #14)
- **Plan**: [`docs/superpowers/plans/2026-03-17-arch-001-canonical-article-contracts.md`](../docs/superpowers/plans/2026-03-17-arch-001-canonical-article-contracts.md)
- **Spec**: [`docs/superpowers/specs/2026-03-17-arch-001-canonical-article-contracts-design.md`](../docs/superpowers/specs/2026-03-17-arch-001-canonical-article-contracts-design.md)
- **Acceptance Criteria**:
  - `CanonicalArticle` Pydantic model defined in `src/models/` with fields: id, title, subtitle, body_markdown, summary, key_claims, content_type, seo (SEOMetadata), citations (list[Citation]), visuals (list[ImageAsset]), authors, domain, generated_at, provenance (Provenance), ai_generated
  - Supporting models: `SEOMetadata`, `Citation`, `ImageAsset`, `Provenance`
  - `Transformer` protocol defined: `transform(CanonicalArticle) -> PlatformPayload`
  - `Adapter` protocol defined: `publish(PlatformPayload, schedule_at) -> PublicationResult`
  - Unit tests validating model construction and serialization
  - No behavioral logic — pure model/contract definitions
- **Story Points**: 3
- **Blocks**: RESEARCH-001, CONTENT-001, PUBLISH-001

### ARCH-002: TrendSource Protocol & Registry [Should] — DONE
**As a** developer, **I want** a formal TrendSource protocol and source registry, **so that** trend sources are interchangeable and the router boilerplate is eliminated.
- **Status**: Done (branch `feature/ARCH-002-trendsource-protocol-registry`, PR #24)
- **Plan**: [`docs/superpowers/plans/2026-03-20-arch-002-trendsource-protocol-registry.md`](../docs/superpowers/plans/2026-03-20-arch-002-trendsource-protocol-registry.md)
- **Spec**: [`docs/superpowers/specs/2026-03-20-arch-002-trendsource-protocol-registry-design.md`](../docs/superpowers/specs/2026-03-20-arch-002-trendsource-protocol-registry-design.md)
- **Acceptance Criteria**:
  - `TrendSource` protocol: `source_name: str`, `fetch_and_normalize(config) -> list[RawTopic]`
  - `TrendFetchConfig` Pydantic model for unified fetch parameters
  - Source registry that discovers and manages active trend sources
  - Single registry-driven router endpoint replaces 5 copy-paste handlers
  - All 5 existing sources (HN, Google Trends, Reddit, NewsAPI, arXiv) implement the protocol
  - Existing tests continue to pass (no behavioral changes)
- **Story Points**: 5
- **Note**: Refactors existing code in `src/api/routers/trends.py` and `src/services/trends/`

---

## Epic 2: Multi-Agent Research Pipeline
**Goal**: Autonomously research a selected topic using parallel AI agents with RAG.

### RESEARCH-001: Agent Orchestrator (LangGraph) [Must] — DONE
**As a** system, **I want** an orchestrator that plans research and coordinates sub-agents, **so that** research is comprehensive and efficient.
- **Status**: Done (branch `feature/RESEARCH-001-agent-orchestrator`, PR #15)
- **Plan**: [`docs/superpowers/plans/2026-03-17-research-001-agent-orchestrator.md`](../docs/superpowers/plans/2026-03-17-research-001-agent-orchestrator.md)
- **Spec**: [`docs/superpowers/specs/2026-03-17-research-001-agent-orchestrator-design.md`](../docs/superpowers/specs/2026-03-17-research-001-agent-orchestrator-design.md)
- **Acceptance Criteria**:
  - Receives topic, generates research plan (3-5 facets)
  - Spawns research agents in parallel via Celery
  - Monitors agent progress with timeout (5 min per agent)
  - Evaluates completeness and triggers additional research if needed
  - State persisted in PostgreSQL for recovery
- **Story Points**: 13
- **Blocks**: RESEARCH-002, RESEARCH-003, RESEARCH-005, CONTENT-001

### RESEARCH-002: Web Search Agent [Must] — DONE
**As a** research agent, **I want** to search the web via SerpAPI, **so that** I can gather current information.
- **Status**: Done (branch `feature/RESEARCH-002-web-search-agent`, PR #16)
- **Plan**: [`docs/superpowers/plans/2026-03-17-research-002-web-search-agent.md`](../docs/superpowers/plans/2026-03-17-research-002-web-search-agent.md)
- **Spec**: [`docs/superpowers/specs/2026-03-17-research-002-web-search-agent-design.md`](../docs/superpowers/specs/2026-03-17-research-002-web-search-agent-design.md)
- **Acceptance Criteria**:
  - Executes search queries derived from research plan
  - Fetches and cleans top 10 results per query
  - Extracts relevant content, discards boilerplate
  - Stores findings with source URL and date
- **Story Points**: 8

### RESEARCH-003: RAG Pipeline (Milvus) [Must] — DONE
**As a** system, **I want** retrieved documents indexed in a vector database, **so that** agents can retrieve relevant context efficiently.
- **Status**: Done (branch `feature/RESEARCH-003-rag-pipeline`, PR #17)
- **Plan**: [`docs/superpowers/plans/2026-03-17-research-003-rag-pipeline.md`](../docs/superpowers/plans/2026-03-17-research-003-rag-pipeline.md)
- **Spec**: [`docs/superpowers/specs/2026-03-17-research-003-rag-pipeline-design.md`](../docs/superpowers/specs/2026-03-17-research-003-rag-pipeline-design.md)
- **Acceptance Criteria**:
  - Documents chunked (512 tokens, 50-token overlap)
  - Embedded via sentence-transformers (all-MiniLM-L6-v2)
  - Stored in Milvus with metadata (source, date, topic) — see [ADR-002](../docs/architecture/adrs/ADR-002-milvus-vector-database.md)
  - Top-k retrieval (k=5) by cosine similarity
  - Milvus Lite for local dev, Milvus standalone for production
  - Knowledge base stats tracked (doc count, embedding count, storage size)
- **Story Points**: 8

### RESEARCH-004: Literature Review Agent [Should] — DONE
**As a** research agent, **I want** to search arXiv and academic sources, **so that** articles include scholarly context.
- **Status**: Done (branch `feature/RESEARCH-004-literature-review-agent`, PR #29)
- **Plan**: [`docs/superpowers/plans/2026-03-21-research-004-literature-review-agent.md`](../docs/superpowers/plans/2026-03-21-research-004-literature-review-agent.md)
- **Spec**: [`docs/superpowers/specs/2026-03-21-research-004-literature-review-agent-design.md`](../docs/superpowers/specs/2026-03-21-research-004-literature-review-agent-design.md)
- **Acceptance Criteria**:
  - Searches arXiv API by topic keywords (via Semantic Scholar, which indexes all arXiv papers)
  - Extracts abstracts and key findings
  - Summarizes relevant papers with citations
- **Story Points**: 5

### RESEARCH-005: Research Session Tracking [Must]
**As a** user, **I want** to see the status and results of research sessions, **so that** I can monitor agent progress.
- **Acceptance Criteria**:
  - Dashboard shows session status (queued, in progress, complete, failed)
  - Each agent step logged with duration and result summary
  - Sources used count and embedding count displayed
  - Real-time status updates via WebSocket
- **Story Points**: 5

---

## Epic 3: Content Generation Pipeline
**Goal**: Generate high-quality, SEO-optimized, AI-discoverable long-form articles from research findings. Articles should be designed for both traditional search engines and LLM-based AI assistants (ChatGPT, Perplexity, Claude, Gemini) — structured for citation, grounded in sources, and machine-readable via JSON-LD and `llms.txt`.

### CONTENT-001: Article Outline Generation [Must] — DONE
**As a** writer agent, **I want** to generate a structured outline from research findings, **so that** articles have clear structure.
- **Status**: Done (branch `feature/CONTENT-001-article-outline`, PR #18)
- **Plan**: [`docs/superpowers/plans/2026-03-18-content-001-article-outline.md`](../docs/superpowers/plans/2026-03-18-content-001-article-outline.md)
- **Spec**: [`docs/superpowers/specs/2026-03-18-content-001-article-outline-design.md`](../docs/superpowers/specs/2026-03-18-content-001-article-outline-design.md)
- **Acceptance Criteria**:
  - LLM generates outline with 4-8 sections from research findings
  - Sections ordered for narrative flow (intro → findings → analysis → conclusion)
  - Each section has target word count and key points to cover
  - Outline reviewable before drafting proceeds
- **Story Points**: 5

### CONTENT-002: Section-by-Section Drafting with RAG [Must] — DONE
**As a** writer agent, **I want** to draft each section using relevant context from the knowledge base, **so that** content is grounded in research.
- **Status**: Done (branch `feature/CONTENT-002-section-drafting`, PR #19)
- **Plan**: [`docs/superpowers/plans/2026-03-19-content-002-section-drafting.md`](../docs/superpowers/plans/2026-03-19-content-002-section-drafting.md)
- **Spec**: [`docs/superpowers/specs/2026-03-19-content-002-section-drafting-design.md`](../docs/superpowers/specs/2026-03-19-content-002-section-drafting-design.md)
- **Acceptance Criteria**:
  - Each section drafted with top-k RAG context (k=5 relevant chunks)
  - All factual claims include inline citations
  - Word count targets met per section (200-500 words each)
  - Total article length ≥ 1500 words
- **Story Points**: 8

### CONTENT-003: SEO & AI Discoverability [Must] — DONE
**As a** content marketer, **I want** articles optimized for both search engines and AI assistants, **so that** they rank well in Google and are cited by ChatGPT, Perplexity, and other AI agents.
- **Status**: Done (branch `feature/CONTENT-003-seo-ai-discoverability`, PR #20)
- **Plan**: [`docs/superpowers/plans/2026-03-19-content-003-seo-ai-discoverability.md`](../docs/superpowers/plans/2026-03-19-content-003-seo-ai-discoverability.md)
- **Spec**: [`docs/superpowers/specs/2026-03-19-content-003-seo-ai-discoverability-design.md`](../docs/superpowers/specs/2026-03-19-content-003-seo-ai-discoverability-design.md)

#### Traditional SEO
- **Acceptance Criteria**:
  - Primary keyword in title, H1, first paragraph, meta description
  - Meta title 50-60 chars, meta description 150-160 chars
  - Keyword density 1-2% for primary keyword
  - Headings (H2, H3) contain secondary keywords
  - Readability score: Flesch-Kincaid grade 10-12

#### AI Discoverability
- **Acceptance Criteria**:
  - **Summary generation**: LLM synthesizes 1-2 sentence extractive summary from drafted content → populates `CanonicalArticle.summary` (used for `llms.txt`, OG descriptions, AI snippet extraction)
  - **Key claims extraction**: LLM extracts top 3-5 factual claims with citation indices from drafted sections → populates `CanonicalArticle.key_claims` (aids RAG retrieval by AI agents)
  - **JSON-LD Schema.org output**: Generate `Article` structured data (headline, author, datePublished, dateModified, citation array) as part of SEO metadata — stored in `CanonicalArticle.seo` or a new `structured_data` field
  - **Citation-optimized structure**: Prompt engineering produces question-shaped headings where appropriate ("What is X?" not just "X"), self-contained sections with direct answers near the top, and machine-readable author/date metadata
  - **AI disclosure**: `CanonicalArticle.ai_generated` flag drives disclosure rendering — generate disclosure text (e.g., "This article was generated by AI with human editorial oversight") stored alongside SEO metadata
  - **Provenance population**: Populate `CanonicalArticle.provenance` with actual model versions (primary_model, drafting_model, embedding_model, embedding_version) from runtime config

#### Implementation Notes
- Adds a new `seo_optimize` node to the content pipeline (runs after `validate_article`)
- The node calls the LLM to: generate summary, extract key_claims, produce SEO metadata, generate JSON-LD template
- Prompt engineering changes in outline_generator and section_drafter for citation-optimized structure
- See `docs/architecture/ARCHITECTURE_MODULARITY_REVIEW.md` Section 7 for full AI discoverability analysis
- **Story Points**: 8
- **Blocks**: CONTENT-005

### CONTENT-004: Citation Management [Must] — DONE
**As a** reader, **I want** all claims cited with source links, **so that** content is trustworthy.
- **Status**: Done (branch `feature/CONTENT-004-citation-management`, PR #21)
- **Plan**: [`docs/superpowers/plans/2026-03-19-content-004-citation-management.md`](../docs/superpowers/plans/2026-03-19-content-004-citation-management.md)
- **Spec**: [`docs/superpowers/specs/2026-03-19-content-004-citation-management-design.md`](../docs/superpowers/specs/2026-03-19-content-004-citation-management-design.md)
- **Acceptance Criteria**:
  - Every factual claim has an inline citation [1], [2], etc.
  - References section generated at article end with full source details (title, URL, authors, date)
  - CitationRef records from section drafting upgraded to full `Citation` models (populate authors, published_at from source metadata where available)
  - Links validated (no broken URLs) — async URL head check with timeout
  - Minimum 5 unique sources per article (hard gate, fail draft if unmet)
  - Duplicate citation indices merged (e.g., [1] in section 2 and [1] in section 4 pointing to different sources get renumbered globally)
- **Story Points**: 5
- **Blocks**: CONTENT-005

### CONTENT-005: CanonicalArticle Assembly [Must] — DONE
**As a** system, **I want** drafted sections assembled into a complete `CanonicalArticle`, **so that** the publishing pipeline has a single, validated, platform-neutral contract to consume.
- **Status**: Done (branch `feature/CONTENT-005-canonical-article-assembly`, PR #25)
- **Plan**: [`docs/superpowers/plans/2026-03-20-content-005-canonical-article-assembly.md`](../docs/superpowers/plans/2026-03-20-content-005-canonical-article-assembly.md)
- **Spec**: [`docs/superpowers/specs/2026-03-20-content-005-canonical-article-assembly-design.md`](../docs/superpowers/specs/2026-03-20-content-005-canonical-article-assembly-design.md)
- **Acceptance Criteria**:
  - **Article body assembly**: Concatenate section drafts into `body_markdown` with proper heading hierarchy (H2 per section title, H3 for subsections) and a references section at the end
  - **Field population**: All `CanonicalArticle` fields populated — title, subtitle, body_markdown, summary (from CONTENT-003), key_claims (from CONTENT-003), content_type, seo (from CONTENT-003), citations (from CONTENT-004), visuals (empty list until VISUAL-001+), authors, domain, generated_at, provenance (from CONTENT-003), ai_generated
  - **Validation**: Pydantic validation of the assembled `CanonicalArticle` — all required fields present, summary ≤ 500 chars, key_claims ≤ 10 items, citations ≥ 5 unique sources, body_markdown ≥ 1500 words
  - **ContentService method**: `finalize_article(draft_id)` assembles the CanonicalArticle (service-layer, not pipeline node — per design decision in spec)
  - **ContentService method**: `finalize_article(draft_id) -> CanonicalArticle` — runs the compile node, persists the CanonicalArticle, updates draft status to `COMPLETE`
  - **API endpoint**: `GET /api/v1/articles/{article_id}` returns the finalized `CanonicalArticle` (new `CanonicalArticleResponse` schema with summary, key_claims, provenance, ai_generated, seo, citations)
  - **Status transition**: `DRAFT_COMPLETE` → `COMPLETE` (final state in current pipeline; future tickets add publishing states)
- **Story Points**: 5
- **Depends on**: CONTENT-003 (SEO & AI Discoverability), CONTENT-004 (Citation Management), CONTENT-006 (Content Humanization)

### CONTENT-006: Content Humanization [Must] — DONE
**As a** reader, **I want** articles to read like they were written by a human, **so that** the content feels natural and trustworthy rather than obviously AI-generated.
- **Status**: Done (branch `feature/CONTENT-006-content-humanization`, PR #22)
- **Plan**: [`docs/superpowers/plans/2026-03-20-content-006-content-humanization.md`](../docs/superpowers/plans/2026-03-20-content-006-content-humanization.md)
- **Spec**: [`docs/superpowers/specs/2026-03-20-content-006-content-humanization-design.md`](../docs/superpowers/specs/2026-03-20-content-006-content-humanization-design.md)

#### Layer 1: Prevention (prompt engineering)
- **Acceptance Criteria**:
  - System prompts in `outline_generator.py` and `section_drafter.py` updated with explicit style rules
  - LLM instructed to avoid em-dashes (use periods or commas), formal transitions (moreover/furthermore/in conclusion/additionally), hedge words (essentially/basically/actually/certainly/generally), and buzzwords (delve/unpack/embark/innovative/vibrant/landscape/paradigm/leverage/synergy/holistic)
  - LLM instructed to use natural conversational tone — short sentences, active voice, concrete specifics over abstract generalities
  - LLM instructed to vary sentence length and structure (not every sentence follows the same pattern)

#### Layer 2: Correction (humanize node)
- **Acceptance Criteria**:
  - **New pipeline node**: `humanize` runs after `validate_article` and before `seo_optimize` in the content graph
  - **Mechanical fixes** (regex, no LLM): Replace em-dashes (—) with periods or commas, strip trailing hedge phrases, normalize whitespace
  - **Violation scanner**: Detect remaining formal transitions, hedge words, buzzwords, and repetitive sentence openers in drafted text — return `list[Violation]` with location and category
  - **LLM rewrite pass**: For sections with >3 violations, call LLM with the section text + specific violations to fix — "Rewrite this section to sound more natural: [violations list]". Single rewrite attempt per section (no retry loop)
  - **Metrics logging**: Log `humanization_complete` with violation_count, sections_rewritten, mechanical_fixes_applied per article
  - **Configurable**: Style rules defined as a data structure (not hardcoded in prompts), so new rules can be added without changing code. Default rules loaded from a `STYLE_RULES` constant.

#### Implementation Notes
- New file: `src/agents/content/humanizer.py` (~100 lines) — `scan_violations()`, `fix_mechanical()`, `humanize_section()`
- Style rules as frozen Pydantic model or dict constant — categories: em_dash, formal_transition, hedge_word, buzzword, repetitive_opener
- Tests: unit tests for each rule category, integration test for the pipeline node
- Does NOT change article meaning or remove citations — only style adjustments
- **Story Points**: 5
- **Blocks**: CONTENT-005

---

## Epic 4: Visual Asset Generation
**Goal**: Automatically create charts, diagrams, and illustrations for articles.

### VISUAL-001: Data Chart Generation [Must] — DONE
**As a** writer agent, **I want** charts generated from data in research findings, **so that** articles include data visualizations.
- **Status**: Done (branch `feature/VISUAL-001-data-chart-generation`, PR #30)
- **Plan**: [`docs/superpowers/plans/2026-03-21-visual-001-data-chart-generation.md`](../docs/superpowers/plans/2026-03-21-visual-001-data-chart-generation.md)
- **Spec**: [`docs/superpowers/specs/2026-03-21-visual-001-data-chart-generation-design.md`](../docs/superpowers/specs/2026-03-21-visual-001-data-chart-generation-design.md)
- **Acceptance Criteria**:
  - Generates bar, line, and pie charts via Matplotlib/Plotly
  - Chart title, axis labels, and legend auto-populated
  - Output as PNG with transparent background
  - Embedded in Markdown with caption
- **Story Points**: 5

### VISUAL-002: AI Illustration Generation [Should]
**As a** content team, **I want** AI-generated hero images for articles, **so that** articles have engaging visuals.
- **Acceptance Criteria**:
  - Agent crafts descriptive prompt from article topic
  - Stable Diffusion generates illustration (1024x1024)
  - Image suitable for article header / cover
  - Stored in S3 with article reference
- **Story Points**: 5

### VISUAL-003: Diagram Generation [Could]
**As a** writer agent, **I want** concept diagrams auto-generated, **so that** complex topics are visually explained.
- **Acceptance Criteria**:
  - Mermaid diagram syntax generated from article content
  - Rendered to PNG/SVG
  - Supports flowcharts and sequence diagrams
- **Story Points**: 3

---

## Epic 5: Multi-Platform Publishing
**Goal**: Publish articles to multiple platforms with correct formatting and metadata.

### PUBLISH-001: Ghost CMS Integration [Must]
**As a** publisher, **I want** articles published to Ghost via API, **so that** my blog is updated automatically.
- **Acceptance Criteria**:
  - Creates post via Ghost Admin API with title, content (HTML), tags, cover image
  - Handles draft vs. published status
  - Supports scheduling for future publication
  - Retry on failure with exponential backoff
- **Story Points**: 5

### PUBLISH-002: WordPress Integration [Should]
**As a** publisher, **I want** articles published to WordPress, **so that** I can reach my WordPress audience.
- **Acceptance Criteria**:
  - Creates post via WordPress REST API
  - Uploads featured image
  - Sets categories and tags
  - Handles authentication via Application Password
- **Story Points**: 5

### PUBLISH-003: Medium Integration [Could]
**As a** publisher, **I want** articles cross-posted to Medium, **so that** I expand reach.
- **Acceptance Criteria**:
  - Posts article via Medium API with proper formatting
  - Sets canonical URL to primary publication
  - Handles tags and publication assignment
- **Story Points**: 3

### PUBLISH-004: LinkedIn Integration [Could]
**As a** publisher, **I want** articles shared on LinkedIn, **so that** professional audience is reached.
- **Acceptance Criteria**:
  - Posts article to LinkedIn page via Marketing API
  - Includes title, excerpt, cover image, and link
  - OAuth2 authentication flow
- **Story Points**: 5

### PUBLISH-005: Publication Tracking [Must]
**As a** publisher, **I want** to see all publications and their status, **so that** I can track what's live.
- **Acceptance Criteria**:
  - Dashboard shows publications by platform with status (live, scheduled, failed)
  - View count tracking where platform API supports it
  - SEO score displayed per publication
  - Failed publications can be retried from dashboard
- **Story Points**: 5

---

## Epic 6: Dashboard & Configuration
**Goal**: Provide a web dashboard for monitoring, configuration, and manual control.

### DASH-001: Dashboard Overview [Must] — DONE
**As a** user, **I want** a dashboard showing key metrics, **so that** I can monitor system activity at a glance.
- **Status**: Done (branch `feature/DASH-001-dashboard-overview`, PR #12)
- **Plan**: [`docs/superpowers/plans/2026-03-15-dash-001-dashboard-overview.md`](../docs/superpowers/plans/2026-03-15-dash-001-dashboard-overview.md)
- **Spec**: [`docs/superpowers/specs/2026-03-15-dash-001-dashboard-overview-design.md`](../docs/superpowers/specs/2026-03-15-dash-001-dashboard-overview-design.md)
- **Acceptance Criteria**:
  - Metric cards: Topics Discovered, Articles Generated, Avg Research Time, Published count
  - Trending Topics list with scores and source badges
  - Recent Articles list with status indicators
  - Responsive layout (desktop-first)
- **Story Points**: 8

### DASH-002: Topic Discovery Screen [Must] — DONE
**As a** user, **I want** to browse and filter discovered topics, **so that** I can review and approve topics for research.
- **Status**: Done (branch `feature/DASH-002-topic-discovery-screen`, PR #23)
- **Plan**: [`docs/superpowers/plans/2026-03-20-dash-002-topic-discovery-screen.md`](../docs/superpowers/plans/2026-03-20-dash-002-topic-discovery-screen.md)
- **Spec**: [`docs/superpowers/specs/2026-03-20-dash-002-topic-discovery-screen-design.md`](../docs/superpowers/specs/2026-03-20-dash-002-topic-discovery-screen-design.md)
- **Acceptance Criteria**:
  - Grid of topic cards with trend badges (Trending, New, Rising, Steady)
  - Filter by source, time range, and domain
  - **Domain selector dropdown** (populated from configured domains in Settings) — user selects domain before scanning
  - "New Scan" button triggers scan for the selected domain only
  - "Generate Article" action button per topic
  - Shows trend score, description, and source tags
- **Story Points**: 5
- **Design update (2026-03-18)**: Domain selector added to filter bar in Pencil design. "New Scan" button removed from Dashboard (was ambiguous without domain context); scan is initiated only from Topic Discovery with a selected domain.

### DASH-003: Article View & Preview [Must] — DONE
**As a** user, **I want** to preview generated articles with agent workflow details, **so that** I can review before publishing.
- **Status**: Done (branch `feature/DASH-003-article-view-preview`, PR #27)
- **Plan**: [`docs/superpowers/plans/2026-03-21-dash-003-article-view-preview.md`](../docs/superpowers/plans/2026-03-21-dash-003-article-view-preview.md)
- **Spec**: [`docs/superpowers/specs/2026-03-21-dash-003-article-view-preview-design.md`](../docs/superpowers/specs/2026-03-21-dash-003-article-view-preview-design.md)
- **Acceptance Criteria**:
  - Full article preview with Markdown rendering
  - Side panel showing agent workflow steps with durations
  - Sources used section with links
  - Publish action with platform selection
- **Story Points**: 5

### DASH-004: Research Sessions Screen [Should] — DONE
**As a** user, **I want** to monitor active and past research sessions, **so that** I can track agent work.
- **Status**: Done (branch `feature/DASH-004-research-sessions-screen`, PR #28)
- **Plan**: [`docs/superpowers/plans/2026-03-21-dash-004-research-sessions-screen.md`](../docs/superpowers/plans/2026-03-21-dash-004-research-sessions-screen.md)
- **Spec**: [`docs/superpowers/specs/2026-03-21-dash-004-research-sessions-screen-design.md`](../docs/superpowers/specs/2026-03-21-dash-004-research-sessions-screen-design.md)
- **Acceptance Criteria**:
  - List of sessions with status (queued, in progress, complete)
  - Progress bars for active sessions
  - Knowledge base stats panel (documents, embeddings, storage)
  - Data source connectors with connection status
- **Story Points**: 5

### DASH-005: Settings & Configuration [Must] — DONE
**As an** admin, **I want** to configure domain focus, LLM models, API keys, and SEO defaults, **so that** the system is customizable.
- **Status**: Done (branch `feature/DASH-005-settings-configuration`, PR #26)
- **Plan**: [`docs/superpowers/plans/2026-03-21-dash-005-settings-configuration.md`](../docs/superpowers/plans/2026-03-21-dash-005-settings-configuration.md)
- **Spec**: [`docs/superpowers/specs/2026-03-20-dash-005-settings-configuration-design.md`](../docs/superpowers/specs/2026-03-20-dash-005-settings-configuration-design.md)
- **Acceptance Criteria**:
  - General settings: domain focus, article length target, content tone
  - LLM configuration: primary model, drafting model, image model
  - API key management: add, view status (masked), rotate
  - SEO defaults: toggleable options (meta tags, keyword optimization, cover images, citations, human review)
- **Story Points**: 8

---

## Epic 7: API & Authentication
**Goal**: RESTful API with JWT authentication and role-based access control.

### API-001: FastAPI Application Setup [Must] — DONE
**As a** developer, **I want** a FastAPI application with proper structure, **so that** we have a solid API foundation.
- **Status**: Done (branch `feature/API-001-fastapi-setup`)
- **Plan**: [`docs/superpowers/plans/2026-03-12-api-001-fastapi-setup.md`](../docs/superpowers/plans/2026-03-12-api-001-fastapi-setup.md)
- **Spec**: [`docs/superpowers/specs/2026-03-12-api-001-fastapi-setup-design.md`](../docs/superpowers/specs/2026-03-12-api-001-fastapi-setup-design.md)
- **Acceptance Criteria**:
  - FastAPI app with router organization by domain
  - Middleware: CORS, request ID, structured logging, rate limiting
  - Health endpoint: `/api/v1/health`
  - Auto-generated OpenAPI documentation at `/docs`
  - Pydantic settings for configuration
- **Story Points**: 5

### API-002: JWT Authentication [Must] — DONE
**As a** user, **I want** to authenticate with JWT tokens, **so that** my access is secure.
- **Status**: Done (branch `feature/API-002-jwt-authentication`)
- **Plan**: [`docs/superpowers/plans/2026-03-13-api-002-jwt-authentication.md`](../docs/superpowers/plans/2026-03-13-api-002-jwt-authentication.md)
- **Spec**: [`docs/superpowers/specs/2026-03-12-api-002-jwt-authentication-design.md`](../docs/superpowers/specs/2026-03-12-api-002-jwt-authentication-design.md)
- **Acceptance Criteria**:
  - Login endpoint returns access token (15min) + refresh token (7d)
  - RS256 algorithm, explicit validation
  - Refresh endpoint rotates tokens
  - Logout invalidates refresh token
- **Story Points**: 5

### API-003: RBAC Authorization [Must] — DONE
**As an** admin, **I want** role-based access control, **so that** different users have appropriate permissions.
- **Status**: Done (branch `feature/API-003-rbac-authorization`)
- **Plan**: [`docs/superpowers/plans/2026-03-13-api-003-rbac-authorization.md`](../docs/superpowers/plans/2026-03-13-api-003-rbac-authorization.md)
- **Spec**: [`docs/superpowers/specs/2026-03-13-api-003-rbac-authorization-design.md`](../docs/superpowers/specs/2026-03-13-api-003-rbac-authorization-design.md)
- **Acceptance Criteria**:
  - Roles: admin (full access), editor (read + write articles), viewer (read-only)
  - Permission checks enforced at route level via FastAPI dependencies
  - Admin-only routes: settings, API keys, platform management
- **Story Points**: 5

---

## Epic 9: Infrastructure & Integration
**Goal**: Replace in-memory stubs with real PostgreSQL persistence and wire frontend to backend APIs.

### INFRA-001: PostgreSQL Persistence Layer [Must]
**As a** developer, **I want** all in-memory repositories replaced with PostgreSQL-backed implementations, **so that** data survives server restarts and the system is production-ready.
- **Acceptance Criteria**:
  - SQLAlchemy models for: Topic, ResearchSession, AgentStep, ArticleDraft, CanonicalArticle
  - PostgreSQL-backed repository implementations replacing all `InMemory*Repository` classes
  - Alembic migrations for all tables
  - `TopicRepository` persists scanned topics from `/trends/fetch` + `/topics/rank` flow
  - `ResearchSessionRepository` persists sessions and agent steps
  - `ArticleDraftRepository` persists drafts through pipeline stages
  - `ArticleRepository` persists finalized CanonicalArticles
  - Replace `MemorySaver` with `PostgresSaver` in LangGraph orchestrator
  - **Cross-scan dedup**: Before persisting scanned topics, check existing topics in DB by semantic similarity (cosine threshold 0.85, reusing TREND-006 embedding logic). If match found, upsert — update `trend_score`, `velocity`, `discovered_at`. If no match, insert as new topic. Prevents duplicate topics across repeated scans of the same domain.
  - All existing tests continue to pass (in-memory repos used in test fixtures)
  - Docker Compose includes PostgreSQL 16 service for local dev
- **Story Points**: 13
- **Blocks**: INFRA-002

### INFRA-002: Frontend-Backend API Integration [Must]
**As a** user, **I want** all dashboard pages showing real data from the backend, **so that** the UI reflects actual system state.
- **Acceptance Criteria**:
  - Dashboard metrics (`/`) — aggregate real topic/article/session counts from backend
  - Article list (`/articles`) — calls backend `GET /articles` endpoint (new endpoint needed)
  - Article detail (`/articles/[id]`) — calls existing `GET /articles/{id}` instead of mock
  - Settings (`/settings`) — calls backend settings CRUD endpoints (new endpoints needed)
  - "Generate Article" button triggers real `POST /articles/generate` backend call
  - All frontend hooks updated: no mock data imports remain in production code
  - Mock data files retained for tests only
  - Auth enforced: unauthenticated users redirected to `/login`
- **Story Points**: 8
- **Depends on**: INFRA-001

---

## Backlog Summary

| Epic | Must | Should | Could | Total Stories | Total Points |
|------|------|--------|-------|--------------|-------------|
| Design System & UI/UX | 7 | 2 | 0 | 9 | 30 |
| Trend Discovery | 4 | 2 | 0 | 6 | 27 |
| Architecture Foundation | 1 | 1 | 0 | 2 | 8 |
| Research Pipeline | 4 | 1 | 0 | 5 | 39 |
| Content Generation | 6 | 0 | 0 | 6 | 36 |
| Visual Assets | 1 | 1 | 1 | 3 | 13 |
| Publishing | 2 | 1 | 2 | 5 | 23 |
| Dashboard & Config | 4 | 1 | 0 | 5 | 31 |
| API & Auth | 3 | 0 | 0 | 3 | 15 |
| Infrastructure & Integration | 2 | 0 | 0 | 2 | 21 |
| **Total** | **34** | **9** | **3** | **46** | **243** |
