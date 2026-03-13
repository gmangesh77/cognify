# Implementation Plan: DESIGN-001 — Design System Setup

**Ticket**: DESIGN-001
**Date**: 2026-03-13
**Spec**: [design-system-setup-design.md](../specs/2026-03-13-design-001-design-system-setup.md)
**Design file**: `C:\Users\mange\OneDrive\Documents\Workbench\pencil_designs\cognify.pen`

---

## Steps

### Step 1: Set all Pencil variables
- [x] Create color variables (brand, neutrals, semantic, surface/structure) via `set_variables`
- [x] Create typography variables (font-heading, font-body) via `set_variables`
- [x] Create spacing variables (space-1 through space-16) via `set_variables`
- [x] Create border radius variables (radius-sm, radius-md, radius-lg, radius-pill) via `set_variables`

### Step 2: Create Cognify logo component
- [x] Create a new reusable frame for the logo on the canvas
- [x] Design brain icon with amplification arcs using path/ellipse shapes
- [x] Add "Cognify" wordmark text using Space Grotesk 600
- [x] Make the component reusable (`reusable: true`)
- [x] Take screenshot to verify
- [x] Create compact (icon-only) variant

### Step 3: Visual verification
- [x] Verify variables are set correctly via `get_variables`
- [x] Screenshot the logo component to verify quality

### Step 4: Update progress tracking
- [x] Update PROGRESS.md: DESIGN-001 status to Done
- [x] Commit spec, plan, and design changes
