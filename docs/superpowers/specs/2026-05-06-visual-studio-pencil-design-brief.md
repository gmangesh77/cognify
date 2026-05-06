# Pencil Design Brief — Visual Studio Screens

> **For:** Next Claude Code session that picks up the design work in Pencil.
> **Why this exists:** The previous session diagnosed an MCP connection issue (Pencil MCP toggle was ON, but the CLI session's MCP binary had cached a startup failure because Pencil wasn't running yet at session launch). Solution: restart Claude Code, the fresh CLI session will connect to Pencil cleanly. This brief carries forward all alignment so the new session doesn't have to re-ask anything.

---

## Pre-flight check (do this first in the new session)

```text
mcp__pencil__get_editor_state(include_schema=false)
```

If it returns editor state → proceed. If it errors → make sure Pencil desktop is running BEFORE invoking the tool.

---

## Source-of-truth references (read these before designing)

1. **Implementation plan:** [`docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md`](../plans/2026-05-06-visual-generation-improvement-plan.md) — the *what* and *why*.
2. **Architecture review:** [`docs/architecture/COGNIFY_VS_IMPACTAI_REVIEW.md`](../../architecture/COGNIFY_VS_IMPACTAI_REVIEW.md) — context on why the visual stack needs an overhaul.
3. **Design system:** [`frontend/DESIGN.md`](../../../frontend/DESIGN.md) — Cognify's existing tokens, typography, spacing, components.
4. **ImpactAI image-gen reference (the bar to clear):** `D:\Workbench\gitlab\impactai\docs\image-generation.md` (branch `feat/content-hub`) — describes the existing competitor UX. Goal: deliver more refined.

---

## Scope (locked from prior session via AskUserQuestion)

- **Screens:** Full 9-screen set (8 visual-studio screens + Screen 9 added 2026-05-06 to close the per-section content-editing gap).
- **File treatment:** Add new pages alongside existing screens in `pencil_designs/cognify.pen`. Don't modify existing pages.
- **Aesthetic:** **Bolder, magazine-editorial feel** — Figma image-panel / Adobe Firefly-inspired. More whitespace than current Cognify dashboard, larger image-first hierarchy, image-as-canvas treatment. Stay anchored to DESIGN.md tokens (red `#DC2626`, warm slate neutrals, Space Grotesk + Inter, 4px grid, 12px radii) but spend whitespace and scale aggressively.

## Non-goals

- Do NOT modify existing cognify.pen pages.
- Do NOT change DESIGN.md tokens (extend, not redefine).
- Do NOT add wizard-style step sequencing — the studio docks into the existing article-detail flow.

---

## 8 screens to design (in order)

### Screen 1 — Article Detail with embedded Visual Studio panel  *(anchor screen)*

**Layout:** Existing article-detail screen on the left (~60% width), new right-docked Visual Studio panel (~40% width, ~480px wide). Panel can be collapsed.

**Visual Studio panel (top to bottom):**

- **Header band:** title "Visual Studio" (Space Grotesk semibold 20px), action buttons "Plan visuals", "Insert all into article" (Cognify primary red `#DC2626` for primary, ghost neutral for secondary). Cost badge at right.
- **Studio controls (bento grid, 3 cards):**
  - *Page art direction* — multiline textarea (placeholder: "e.g. soft natural light, slate palette, no people")
  - *Default visual style* — chip rail with all 12 styles from `visual_styles.py` catalogue (lifestyle_photo, isometric_3d, etc.); chips show small emoji + label
  - *Render quality* — segmented toggle Fast / Mid / Premium with per-tier cost label (e.g. "$0.001/img", "$0.01/img", "$0.04/img")
- **Spec list:** vertical scroll, one Spec Card per planned image (see Screen 2). Magazine-editorial: each card is wide and image-forward.

**Magazine-editorial cues:**

- Generous 32px vertical rhythm between Studio controls and spec list
- Page art direction textarea has a bigger-than-default placeholder (16px) — invites typing
- Cost badge uses subtle gradient pill (red → coral) instead of a flat chip

### Screen 2 — Spec Card (6 states)

Each spec card represents one planned image. Design 6 stacked variants on the page:

| State | Visual treatment |
|---|---|
| **idle** | Placeholder image area (16:9 grayed bento with thin dashed stroke + "Plan to generate" label), spec metadata (role · style · placement) below |
| **planning** | Subtle shimmer pulse on the image area with "Planning…" caption |
| **generating** | Indeterminate progress bar across image area + a 3-tier provider chip (Fast / Mid / Premium) at top-right showing which is rendering |
| **done** | Full image preview (rounded-md, soft shadow) + caption + chip rail of alternative styles + footer actions: Regenerate · Edit · Replace · Refine · Remove · Delete |
| **error** | Red-tinted top border, error message in error-light bg, retry button |
| **refining** | Image visible but slightly desaturated, refine input bar at bottom of card with mic/send icons |

**Spec Card anatomy (universal, all states):**

- Image bento (always 16:9 unless aspect_ratio overrides)
- Below: chip rail (top 3 suggested styles + current + page-default)
- Per-spec render-quality override chip (with `·override` tag when set)
- Refine input — only visible after first render (collapsed otherwise)
- Edit drawer trigger (icon button top-right)

### Screen 3 — Plan-Visuals Modal (entry point + variant picker)

**Two stages, designed as two pages or two states:**

1. **Planning state:** centered modal (max-w 720px), gradient red→coral header, animated dots, "Reading section, picking visuals…", small step list checking off ("Reading content", "Matching personas", "Picking styles", "Composing prompts").
2. **Variant picker:** modal expands to full-width grid (max-w 1280px). Each section shows a row of 3 variants (different visual styles applied to the same spec); user picks one per slot. Pickable variants get a red ring + check. Bottom action: "Apply N picked variants → render".

### Screen 4 — Edit Drawer

**Slides in from right side of a Spec Card** (full-height, 480px wide, soft drop shadow). Stacked form sections:

- Role style — segmented control or chip rail (hero, feature_card, concept, …)
- Visual style — chip rail (12 styles)
- Aspect ratio — segmented (16:9, 1:1, 4:3, 3:4, 4:5)
- Placement — anchor select (cover, top, before_heading, between_paragraphs, bottom_grid, background, column_split) + conditional fields (heading_text or paragraph_index)
- Alt text — single-line input with char count
- Prompt — multiline textarea (subject only) with hint text "Style is layered separately"
- Provider override — segmented Fast/Mid/Premium

Footer: "Save changes" (primary), "Reset to plan", "Cancel".

### Screen 5 — Saved Asset Gallery Modal

**Layout:** modal (max-w 1080px), magazine-grid layout.

- Header: "Your saved visuals" + filter chips (All, Hero, Inline, Cover, Quote-card, Stat-card) + sort dropdown (Most recent, Most reused, Least cost)
- Sidebar: filter facets — by article, by style token (`cognify_gallery:hero`, etc.), by provider, by date range
- Grid: 4-col masonry of saved images. Hover reveals: original article title, style token, render cost, "Use in current article" CTA
- Empty state: full-bleed illustration + "No saved visuals yet — every image you generate lands here for reuse"

### Screen 6 — Section HTML Refine Panel

**Layout:** full-width within Visual Studio panel (replaces spec list when open).

- Top: section heading (ghost back arrow → return to spec list)
- Middle: split view — *current HTML* (rendered iframe preview, left) and *proposed HTML* (rendered iframe preview, right) with diff highlights
- Bottom: "Apply with AI" textarea (large, magazine-style with placeholder rotating through suggestions: "make this more spacious", "add a 3-column grid", "use a trust strip", "switch to dark band CTA")
- Action row: "Generate refinement" (primary), "Reset to original", "Apply" (only enabled after generation, locked until user reviews diff)

### Screen 7 — Image Import Modal

**Layout:** modal (max-w 720px), 2 tabs.

- Tab A — **Upload from file:** big drop-zone with cloud-up icon, "Drag & drop or click to select", supported formats (png/jpg/webp), 10MB cap, MIME-sniff status row when file selected
- Tab B — **Fetch from URL:** URL input with paste-and-preview; on paste, show a status row: ✓ HTTPS, ✓ resolves to public IP, ✓ MIME allowed, ✓ size under cap (or red ✗ with explanation if any fails — SSRF guard feedback)
- Footer: "Import" (primary) — disabled until safety checks pass

### Screen 8 — Cost Badge / UsageBadge component

**Layout:** small floating component, 320px wide. Two density variants on the page:

1. **Compact (default):** total cost pill ("$0.043 this article") with subtle red→coral gradient
2. **Expanded (hover/click):** dropdown with provider breakdown — table with columns Provider · Model · Count · Subtotal, plus a "Reset / clear" link and a small sparkline of cost over time
3. **Limit warning state:** red tint when within 20% of per-user budget cap

### Screen 9 — Per-Section Context Toolbar  *(added 2026-05-06)*

**Why this screen exists:** Visual Studio gives editors fine control over images. This screen gives them the same depth of control over **prose** — closing the gap surfaced after Screens 1–8 were reviewed. Backed by `/api/v1/content/section-rewrite`, `/content/section-update`, `/content/paragraph-tone`, and `/content/section/{id}/history`.

**Layout:** full article-detail screen (1440 × ~1100). Article column on the left, Visual Studio panel collapsed-with-affordance on the right. The dominant content of *this* screen is a focused section in the article column with a floating context toolbar attached to it.

**Three sub-states stacked on the page:**

1. **Toolbar visible (hover/focus state):** When the editor hovers a section, a 3-action floating toolbar appears anchored to the section's top-right corner — small, pill-shaped, white surface with shadow:
   - *Edit text* (icon: `pen-line`) — toggles inline contenteditable mode for the section's prose
   - *Edit visual* (icon: `image`) — jumps to that section's Spec Card in the Visual Studio panel
   - *Refine layout* (icon: `layout-grid`) — opens Section HTML Refine panel (Screen 6) scoped to this section
   - History affordance: `history` icon button at the right side of the toolbar opens the Section History Drawer.

2. **Inline edit + AI rewrite popover:** A paragraph is selected (highlighted with subtle red underline / red selection background), and an AI popover floats below the selection:
   - Header: "Rewrite with AI" + selection word count + close X
   - Tone preset chip rail: `shorter`, `more concrete`, `more conversational`, `more authoritative` — single-click presets
   - Free-text instruction textarea with placeholder rotating: "make this more direct", "add a concrete example", "lead with the metric"
   - Footer: "Rewrite" primary CTA (red gradient), cost preview ("~$0.002")
   - Once the rewrite returns, the popover transforms into a **diff view**: word-level inserts (green highlight) and deletes (red strikethrough) on the original prose, with Accept / Reject / Try again actions. Reuses the same diff component used by humanization and HTML refine.

3. **Section History Drawer:** Slides in from right (480px wide). Shows a chronological list of section versions with: timestamp, source pill (`AI · shorter` / `manual` / `tone preset · concrete`), token cost, "Restore" button. The currently-active version is marked with a red bar.

**Magazine-editorial cues:**

- Toolbar uses bento-style icon buttons with text labels — not just bare icons. Reads as a deliberate surface, not a hover hack.
- Selection highlight uses `$primary-light` (rose tint) rather than the OS default blue — keeps the brand palette honest even during text manipulation.
- Diff view uses green for insertions and a desaturated red for deletions, never the warning red — preserves error red's meaning.
- Anchor-preservation indicator: a small `🔒 anchors preserved` badge on the popover footer, signals that image spec_id references and heading anchors will survive the rewrite.

**Interactions to hint at (not necessarily render):**

- Section header has a focus ring that matches the toolbar's anchor edge.
- When the popover is open, the rest of the article and the studio panel dim slightly (low-opacity overlay) — keeps focus on the active edit.
- Tone preset chips show a tiny "estimated word count delta" tooltip on hover (e.g., `shorter` → `−40 words`).

---

## How to operate Pencil via MCP (tool cheatsheet)

Top-level workflow:

1. `mcp__pencil__get_editor_state(include_schema=false)` — confirm cognify.pen is active; capture current selection / page list.
2. `mcp__pencil__get_guidelines(category="…")` — load Pencil's component patterns / spacing conventions if needed.
3. `mcp__pencil__batch_get(patterns=["…"])` — survey existing pages (Dashboard, Article View, Topic Discovery, Settings) to harvest tokens / reusable components from the canvas.
4. `mcp__pencil__batch_design(operations=[…])` — create new pages and elements. Use small-script syntax `foo=I("parent",{...})`, `baz=C("nodeid","parent",{...})`, etc. Cap at ~25 ops per call.
5. `mcp__pencil__find_empty_space_on_canvas()` — find a clean canvas region for each new page so they don't overlap existing pages.
6. `mcp__pencil__get_screenshot()` — visually verify each screen as you go.

**Crucial constraint:** `.pen` files are encrypted; only `batch_get` / `batch_design` can read or write them. Do NOT use Read/Edit/Write/Grep on `.pen` files.

---

## Recommended sequencing for the next session

1. Read this brief.
2. `mcp__pencil__get_editor_state` — verify connection, capture state.
3. Run `mcp__pencil__batch_get` to survey existing pages for tokens / components. Particularly the Article View page (~"Article V…" thumbnail in canvas) and Settings (~"Settings…" thumbnail).
4. Find empty canvas space below the existing pages.
5. Build Screen 1 first (Article Detail with Visual Studio panel) as the anchor — components built here (chip rail, spec card, cost badge) become reusable for screens 2-8.
6. Build Screen 2 (Spec Card states) using the Spec Card from Screen 1 — each state is a copy + variation.
7. Continue 3-8 in numerical order.
8. Final QA pass: take a screenshot of all 8 new pages and visually verify against DESIGN.md.

---

## Aesthetic guardrails (the "more refined than ImpactAI" bar)

ImpactAI's image studio is functional but visually flat (inline styles, sprinkled colour, basic chip rails, single-column layouts). To clear that bar:

- **Reserve red `#DC2626` for primary CTAs and active states only** — every other surface uses warm slate neutrals.
- **Bento-grid Studio header** (3 distinct cards: page direction, style, provider) instead of stacked rows.
- **Animated state transitions** on Spec Cards (idle→planning→generating→done) — at minimum a subtle shimmer / progress sweep.
- **Image-as-canvas** treatment in Spec Card "done" state — image dominates, controls are subordinate.
- **Cohesive typography ladder** Space Grotesk for everything heading-like, Inter for body. ImpactAI mixes weights inconsistently — Cognify's should feel deliberate.
- **Generous whitespace** — 32px vertical rhythm between Studio sections, 24px between Spec Cards. ImpactAI is denser; Cognify's chosen aesthetic ("magazine-editorial") explicitly trades density for breathing room.
- **Empty states designed** (not afterthoughts).
- **Cost transparency** — show per-tier cost inline on the Fast/Mid/Premium toggle. ImpactAI shows total but obscures per-tier.

---

## Acceptance check at end

For each of the 8 new pages:

- [ ] Uses tokens from DESIGN.md (no hex codes outside the documented palette except via documented gradients)
- [ ] Spacing on the 4px grid
- [ ] Typography uses Space Grotesk (headings) / Inter (body)
- [ ] Primary action uses `#DC2626`; no other red surfaces
- [ ] Empty / loading / error / hover states designed where applicable
- [ ] Components consistent across pages (chip rail looks identical on Screens 1 and 2 etc.)
- [ ] Magazine-editorial: each page has a clear focal point, generous whitespace, image-forward where applicable
- [ ] No drift from ImpactAI's anti-patterns (inline styles, sprinkled colour, dense single-column layouts)

When all 8 pages pass: take a single zoom-out screenshot of the canvas with all new pages visible, save it to `docs/superpowers/specs/visual-studio-designs-overview.png`, and report back.
