# Custom Topic Entry with Smart Auto-Fill

**Date**: 2026-03-30
**Status**: Draft
**Branch**: `feature/custom-topic-entry`

---

## 1. Problem

Users can only generate articles from topics discovered via automated trend scanning (5 sources). There is no way to enter a custom topic. Additionally, per-article customization of audience, tone, and angle is missing — these are only configurable as global settings applied uniformly to all articles.

## 2. Solution Overview

Add a "Create Topic" button on the Topics page that opens a two-step modal:

1. User enters a topic title → clicks "Analyze" → single LLM call auto-fills description, domain, keywords, target audience, tone, and preferred angle.
2. User reviews/tweaks any field (with per-field "Regenerate" buttons) → creates the topic and optionally triggers article generation.

Per-article parameters (audience, tone, angle) are also added to the existing "Generate Article" modal for scanned topics, so all articles benefit from customization.

## 3. Data Flow

```
User enters title
  → POST /api/v1/topics/analyze (LLM → suggested fields)
  → User tweaks fields
  → POST /api/v1/topics (creates TopicRow with source="manual")
  → POST /api/v1/research/sessions (session with audience/tone/angle overrides)
  → Existing pipeline runs with per-article parameters
```

## 4. API Design

### 4.1 Topic Analysis

**Endpoint**: `POST /api/v1/topics/analyze`
**Auth**: editor+

**Request**:
```json
{
  "title": "Zero Trust Architecture in Cloud-Native Applications",
  "regenerate_field": null
}
```

When `regenerate_field` is set (e.g., `"keywords"`), the request also includes the current values of all other fields so the LLM keeps them stable and only regenerates the specified field:

```json
{
  "title": "Zero Trust Architecture in Cloud-Native Applications",
  "regenerate_field": "keywords",
  "current_values": {
    "description": "An exploration of zero trust...",
    "domain": "cybersecurity",
    "keywords": ["zero trust", "cloud-native"],
    "target_audience": "Security engineers",
    "content_tone": "technical-authoritative",
    "preferred_angle": "Implementation guide"
  }
}
```

**Response** (`TopicAnalysis` schema):
```json
{
  "description": "An exploration of zero trust security principles applied to cloud-native environments, covering microsegmentation, identity-based access, and continuous verification.",
  "domain": "cybersecurity",
  "keywords": ["zero trust", "cloud-native", "microsegmentation", "identity-based access"],
  "target_audience": "Security engineers and cloud architects",
  "content_tone": "technical-authoritative",
  "preferred_angle": "Practical implementation guide with real-world case studies"
}
```

**Implementation**:
- Single Claude Sonnet call with structured JSON output.
- Prompt includes the list of configured domains (from settings) so the LLM picks from existing domains or suggests a new one.
- For regenerate requests: prompt instructs "keep all fields as provided, regenerate only {field}".
- `content_tone` values: `technical-authoritative`, `conversational`, `educational`, `analytical`, `news-reporting`. LLM picks from this set.

### 4.2 Manual Topic Creation

**Endpoint**: `POST /api/v1/topics`
**Auth**: editor+

**Request** (`ManualTopicCreate` schema):
```json
{
  "title": "Zero Trust Architecture in Cloud-Native Applications",
  "description": "An exploration of zero trust security principles...",
  "domain": "cybersecurity",
  "keywords": ["zero trust", "cloud-native", "microsegmentation"]
}
```

**Response**: Existing `PersistedTopic` schema, with:
- `source` = `"manual"`
- `trend_score` = `0.0`
- `composite_score` = `null`
- `velocity` = `0.0`
- `discovered_at` = current timestamp

**Deduplication**: Uses the same embedding similarity check as `TopicPersistenceService` (threshold 0.85). Response uses `ManualTopicResult` schema:
```json
{
  "topic": { "id": "uuid", "title": "...", ... },
  "is_duplicate": false,
  "duplicate_of": null
}
```
When a similar topic exists:
```json
{
  "topic": { "id": "uuid-of-existing", "title": "Existing similar topic", ... },
  "is_duplicate": true,
  "duplicate_of": "uuid-of-existing-topic"
}
```
The frontend shows a confirmation: "A similar topic already exists: {title}. Use the existing topic instead?" If the user confirms, they proceed with the existing topic. If they decline, a second call with `force_create: true` bypasses dedup.

**No new DB columns on `topics` table** — uses existing fields: `title`, `description`, `domain`, `domain_keywords` (for keywords), `source`.

### 4.3 Research Session Extension

**Extended endpoint**: `POST /api/v1/research/sessions`
**Auth**: editor+

**New request body** (existing `topic_id` + new optional fields):
```json
{
  "topic_id": "uuid",
  "target_audience": "Security engineers and cloud architects",
  "content_tone": "technical-authoritative",
  "preferred_angle": "Practical implementation guide with real-world case studies"
}
```

All three new fields are optional. When omitted, the pipeline falls back to global settings.

## 5. Database Changes

### 5.1 Migration: Add per-article params to `research_sessions`

Three new nullable columns on `research_sessions`:

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `target_audience` | `String(500)` | Yes | `null` |
| `content_tone` | `String(100)` | Yes | `null` |
| `preferred_angle` | `String(500)` | Yes | `null` |

No changes to the `topics` table.

## 6. Content Pipeline Changes

### 6.1 State Extension

`ContentPipelineState` (LangGraph state dict) gets three new optional fields:
- `target_audience: str | None`
- `content_tone: str | None`
- `preferred_angle: str | None`

### 6.2 Parameter Loading

`ContentService` populates these from the research session when invoking the pipeline.

**Fallback chain**: session override → global settings → `None` (omitted from prompt).

### 6.3 Affected Nodes

| Node | Uses | How |
|------|------|-----|
| `make_outline_node` | audience, angle | Prompt includes "Write for {audience}" and "Take the angle: {angle}" — shapes section structure and depth |
| `make_queries_node` | audience | Tailors retrieval queries to audience knowledge level |
| `make_draft_node` | audience, tone | Prompt includes tone instruction and audience context — affects vocabulary, depth, examples |
| `make_humanize_node` | tone | Already reads tone; changes from global-only to session-first |
| `make_seo_node` | audience | SEO keywords tuned to what the target audience searches for |

Each node's prompt template gets conditional sections. If a param is `None`, the section is omitted (preserving current behavior).

## 7. Frontend Changes

### 7.1 Create Topic Modal

**Entry point**: "Create Topic" button on the Topics page, alongside the existing "Scan Topics" button.

**State 1 — Input**:
- Large text input for topic title (auto-focus)
- "Analyze" button (primary, disabled until title has 3+ characters)
- Loading state: skeleton shimmer on fields below while LLM processes

**State 2 — Review & Customize**:
After analysis completes, fields appear below the title:
- **Description** — textarea, auto-filled, editable, with regenerate icon button
- **Domain** — dropdown (from configured domains), auto-selected, with regenerate icon button. If LLM suggests an unconfigured domain, show with "new domain" indicator
- **Keywords** — tag/chip input, auto-filled, user can add/remove, with regenerate icon button
- **Target Audience** — text input, auto-filled, with regenerate icon button
- **Content Tone** — dropdown (`technical-authoritative`, `conversational`, `educational`, `analytical`, `news-reporting`), auto-selected, with regenerate icon button
- **Preferred Angle** — text input, auto-filled, with regenerate icon button

**Footer actions**:
- "Create Topic" (secondary) — saves topic only, returns to topics list
- "Create & Generate Article" (primary) — saves topic + starts research session with per-article params

**Styling**: Per DESIGN.md — `rounded-lg` modal, `font-heading` for labels, `neutral-200` borders, `primary` red for CTA, regenerate icons `neutral-400` with `hover:neutral-600`.

### 7.2 Extended Generate Article Modal

The existing `GenerateArticleModal` (for scanned topics) gets a "Customize Article" expandable section, **collapsed by default**:
- **Target Audience** — text input, pre-filled from global settings
- **Content Tone** — dropdown, pre-filled from global settings
- **Preferred Angle** — text input, empty by default

These pass to `POST /research/sessions` as per-article overrides. If untouched, global defaults apply.

### 7.3 Topic List Changes

Manual topics display with a "Manual" badge (using existing badge pattern) alongside the source indicator. All other topic card behavior is unchanged.

## 8. API Functions & Hooks

### 8.1 New API Functions (`frontend/src/lib/api/`)

- `analyzeTopic(title, regenerateField?, currentValues?)` → `TopicAnalysis`
- `createManualTopic(data)` → `{ topic: PersistedTopic, duplicate_of?: string }`

### 8.2 New/Modified Hooks (`frontend/src/hooks/`)

- `useTopicAnalysis()` — manages analyze call, loading state, regenerate-per-field
- Modified `useGenerateArticle()` — passes per-article params to session creation

## 9. Testing Strategy

### 9.1 Backend Unit Tests
- Topic analysis endpoint — mock LLM, verify structured JSON with all fields
- Per-field regenerate — verify only specified field changes
- Manual topic creation — verify dedup check, `source="manual"`, correct defaults
- Research session with per-article params — verify storage and retrieval
- Content pipeline nodes — verify prompts include audience/tone/angle when present, omit when `None`
- Fallback chain — session override → global settings → default

### 9.2 Backend Integration Tests
- Full flow: analyze → create topic → create session with params → verify params reach pipeline state
- Dedup: create manual topic, create similar one, verify match detection

### 9.3 Frontend Tests
- Create Topic modal: renders, analyze button disabled until 3+ chars, fields populate after mock analyze response, regenerate triggers call for single field
- Generate Article modal: customization section collapsed by default, expands, fields pre-fill from globals
- Manual topics display with "Manual" source badge

### 9.4 FakeLLM Responses
- `/topics/analyze` — structured JSON with all 6 fields
- Per-field regenerate — single field response
- Existing full-pipeline responses (L-007) unchanged

## 10. Out of Scope

- Auto-fill keywords when adding a new domain in Settings (separate ticket)
- Bulk manual topic creation
- Topic templates or presets
- Saving per-article param presets for reuse
