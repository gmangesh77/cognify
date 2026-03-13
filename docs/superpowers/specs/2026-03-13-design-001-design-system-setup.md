# Design Spec: DESIGN-001 — Design System Setup

**Ticket**: DESIGN-001
**Date**: 2026-03-13
**Status**: Approved
**Design file**: `pencil_designs/cognify.pen`

---

## 1. Overview

Establish a comprehensive design system as Pencil variables in `cognify.pen`, providing the foundation for all screens. The system defines colors, typography, spacing, elevation, and border radii — all as variables so every screen and component references tokens instead of hardcoded values.

**Aesthetic direction**: Refined, clean SaaS (Linear/Vercel-inspired). Warm slate neutrals, single red accent, Space Grotesk + Inter typography, subtle shadows and soft corner radii for depth.

---

## 2. Color Palette

### Brand Colors

| Variable Name | Value | Usage |
|---------------|-------|-------|
| `primary` | `#DC2626` | CTA buttons, active nav, logo accent, key highlights |
| `primary-hover` | `#B91C1C` | Button hover states |
| `primary-light` | `#FEF2F2` | Subtle red backgrounds (badges, alert bg) |
| `secondary` | `#1E293B` | Dark headings, sidebar active bg |
| `accent` | `#F97316` | Trending indicators, special callouts |

### Neutrals (warm slate scale)

| Variable Name | Value | Usage |
|---------------|-------|-------|
| `neutral-50` | `#F8FAFC` | Page background, subtle surfaces |
| `neutral-100` | `#F1F5F9` | Card hover, table header bg |
| `neutral-200` | `#E2E8F0` | Borders, dividers |
| `neutral-300` | `#CBD5E1` | Disabled states, subtle icons |
| `neutral-400` | `#94A3B8` | Placeholder text |
| `neutral-500` | `#64748B` | Secondary text, labels |
| `neutral-600` | `#475569` | Body text |
| `neutral-700` | `#334155` | Strong body text |
| `neutral-800` | `#1E293B` | Headings |
| `neutral-900` | `#0F172A` | Primary text, high emphasis |

### Semantic Colors

| Variable Name | Value | Usage |
|---------------|-------|-------|
| `success` | `#16A34A` | Live status, positive metrics |
| `success-light` | `#F0FDF4` | Success backgrounds |
| `warning` | `#D97706` | Scheduled, caution states |
| `warning-light` | `#FFFBEB` | Warning backgrounds |
| `error` | `#DC2626` | Failed, destructive actions |
| `error-light` | `#FEF2F2` | Error backgrounds |
| `info` | `#2563EB` | Info badges, links |
| `info-light` | `#EFF6FF` | Info backgrounds |

### Surface & Structure

| Variable Name | Value | Usage |
|---------------|-------|-------|
| `background` | `#FFFFFF` | Main page background |
| `surface` | `#FFFFFF` | Cards, panels |
| `surface-raised` | `#F8FAFC` | Sidebar, table headers |
| `border` | `#E2E8F0` | All borders and dividers |
| `border-strong` | `#CBD5E1` | Emphasized borders |

---

## 3. Typography

### Font Families

| Variable Name | Value | Usage |
|---------------|-------|-------|
| `font-heading` | `Space Grotesk` | Headings, metrics, nav, buttons, logo |
| `font-body` | `Inter` | Body text, descriptions, table content, labels |

### Type Scale

| Role | Font | Weight | Size | Letter Spacing | Line Height |
|------|------|--------|------|----------------|-------------|
| Page title (3xl) | Space Grotesk | 600 | 36px | -1 | 1.2 |
| Section heading (2xl) | Space Grotesk | 600 | 30px | -0.5 | 1.2 |
| Card title (xl) | Space Grotesk | 600 | 24px | -0.5 | 1.3 |
| Subsection (lg) | Space Grotesk | 500 | 20px | 0 | 1.4 |
| Nav/Label (md) | Space Grotesk | 500 | 16px | 0 | 1.5 |
| Body large | Inter | 400 | 16px | 0 | 1.5 |
| Body default | Inter | 400 | 14px | 0 | 1.5 |
| Body small | Inter | 400 | 13px | 0 | 1.5 |
| Caption/Badge (xs) | Inter | 500 | 12px | 0 | 1.5 |

---

## 4. Spacing Tokens (4px grid)

| Variable Name | Value | Usage |
|---------------|-------|-------|
| `space-1` | `4px` | Minimal gaps (icon-text tight) |
| `space-2` | `8px` | Small gaps (title + subtitle stacks) |
| `space-3` | `12px` | Navigation item gaps, button icon-text |
| `space-4` | `16px` | Form field gaps, medium spacing |
| `space-5` | `20px` | Card internal gaps, list sections |
| `space-6` | `24px` | Card padding, metric grid gap |
| `space-8` | `32px` | Section gaps, sidebar padding |
| `space-10` | `40px` | Page vertical padding |
| `space-12` | `48px` | Page horizontal padding, major section gap |
| `space-16` | `64px` | Hero-level spacing |

---

## 5. Border Radius

| Variable Name | Value | Usage |
|---------------|-------|-------|
| `radius-sm` | `4px` | Badges, small inputs, tags |
| `radius-md` | `8px` | Cards, buttons, inputs, dropdowns |
| `radius-lg` | `12px` | Modals, large containers, panels |
| `radius-pill` | `9999px` | Pills, filter chips, avatar circles |

---

## 6. Elevation (Shadows)

Shadows are applied via Pencil `effect` property on frames. Values encoded as shadow effects:

| Level | Offset | Blur | Spread | Color | Usage |
|-------|--------|------|--------|-------|-------|
| `shadow-sm` | (0, 1) | 2 | 0 | `#0000000D` (5%) | Buttons, inputs |
| `shadow-md` | (0, 4) | 6 | -1 | `#00000012` (7%) | Cards, dropdowns |
| `shadow-lg` | (0, 10) | 15 | -3 | `#0000001A` (10%) | Modals, popovers |

---

## 7. Cognify Logo / Brand Mark

**Concept**: Stylized brain with amplification arcs — a brain silhouette with 2-3 radiating signal arcs on the right side, communicating "intelligence amplifying outward."

- Brain shape: filled with `primary` (#DC2626)
- Signal arcs: `primary` at 80%, 50%, 25% opacity
- Wordmark "Cognify": Space Grotesk, 600 weight, `neutral-900`
- Compact variant: brain icon only (for collapsed sidebar, favicon)

---

## 8. Dark Mode Readiness

All colors are defined as Pencil variables. A future dark theme swaps values:

| Token | Light | Dark (future) |
|-------|-------|---------------|
| `background` | `#FFFFFF` | `#0F172A` |
| `surface` | `#FFFFFF` | `#1E293B` |
| `surface-raised` | `#F8FAFC` | `#334155` |
| `neutral-900` | `#0F172A` | `#F8FAFC` |
| `border` | `#E2E8F0` | `#334155` |

No dark mode implementation now — just variable-based architecture that supports it.

---

## 9. Acceptance Criteria Mapping

| Criteria | Section |
|----------|---------|
| Color palette with primary, secondary, accent, neutrals (50-900), semantic | Sections 2 |
| Typography scale: families, sizes (xs-3xl), weights, line heights | Section 3 |
| Spacing tokens: 4px grid (4, 8, 12, 16, 20, 24, 32, 40, 48, 64) | Section 4 |
| Border radii, shadows, elevation levels | Sections 5, 6 |
| Dark mode consideration (variable-based theming) | Section 8 |

---

## 10. Implementation Notes

- All values are created as Pencil variables via `set_variables` tool
- Color variables use `type: "color"`
- Spacing and radius variables use `type: "number"`
- Font family variables use `type: "string"`
- After setting variables, update existing wireframe screens to reference variables instead of hardcoded values (this is DESIGN-003 through DESIGN-008 scope, not this ticket)
- Logo is created as a reusable component on the canvas
