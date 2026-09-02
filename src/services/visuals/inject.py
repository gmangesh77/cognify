"""Per-anchor markdown/HTML injector (Phase 3 / VISUAL-006).

Walks an article's HTML body section by section and folds each
`ImageAsset` into the right place based on its planning metadata
(`spec_id`, `placement_anchor`, `section_index`, …). Mirrors impactai's
`injectBanners.ts`; the seven anchors are listed in plan §5.6.

Boundary invariants (ADR-005):
- Cover visuals are owned by the platform transformer (feature_image
  for Ghost; prepend-before-title for Medium/LinkedIn). Inject SKIPS
  them — the transformer that calls inject is responsible for the
  cover. `pick_cover_visual` is exposed as a sibling helper.
- Idempotent: a `data-spec-id` marker on every emitted `<img>` lets a
  second pass detect existing renderings and bail.
- Pure: no I/O, no LLM calls, no DB. Receives a CanonicalArticle and
  returns an HTML string; the caller is the transformer.
- Legacy fallback: visuals without a `spec_id` (Phase 1 charts and
  diagrams from VISUAL-001/-003) get appended to the end of their
  `source_section`, preserving existing publishing behaviour.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import get_args

import structlog
from pydantic import ValidationError

from src.models.content import CanonicalArticle, ImageAsset
from src.models.visual import (
    ImageAspectRatio,
    ImageRoleStyle,
    ImageSpec,
    PlacementAnchor,
)

logger = structlog.get_logger()

_H2_SPLIT_RE = re.compile(r"(<h2[^>]*>.*?</h2>)", flags=re.DOTALL | re.IGNORECASE)
_P_SPLIT_RE = re.compile(r"(<p[^>]*>.*?</p>)", flags=re.DOTALL | re.IGNORECASE)

# Anchors a spec reconstructed from persisted metadata may keep. `cover` is
# the transformer's job; `background` only emits a marker comment and
# `column_split` renders a single spec — both would make an already-paid-for
# image vanish from the published post, so they degrade to a visible figure
# at the section end (`between_paragraphs` without a paragraph hint).
_SYNTHESIZED_ANCHORS: frozenset[str] = frozenset(get_args(PlacementAnchor)) - {
    "cover",
    "background",
    "column_split",
}
_VALID_ROLE_STYLES: frozenset[str] = frozenset(get_args(ImageRoleStyle))
_VALID_ASPECTS: frozenset[str] = frozenset(get_args(ImageAspectRatio))


@dataclass(frozen=True)
class InjectionContext:
    """Context required to render asset URLs as platform-friendly absolute URLs."""

    api_base_url: str = "http://localhost:8000"


def pick_cover_visual(article: CanonicalArticle) -> ImageAsset | None:
    """Return the cover visual the platform transformer should hoist out.

    Order of preference:
    1. A rendered visual whose `metadata.placement_anchor == "cover"`.
    2. A rendered visual whose `metadata.role_style == "hero"` (Visual
       Studio attach-visual flow + planned hero specs).
    3. A rendered visual whose legacy `metadata.type == "hero"` (DALL-E
       hero from CONTENT-002 / VISUAL-002).
    4. None — let the caller decide whether to fall back to article.visuals[0].
    """
    for asset in article.visuals:
        anchor = (asset.metadata or {}).get("placement_anchor")
        if anchor == "cover":
            return asset
    for asset in article.visuals:
        if (asset.metadata or {}).get("role_style") == "hero":
            return asset
    for asset in article.visuals:
        if (asset.metadata or {}).get("type") == "hero":
            return asset
    return None


def inject_visuals(article: CanonicalArticle, ctx: InjectionContext) -> str:
    """Inject planned + legacy visuals into the article's HTML body.

    Returns the modified HTML. The article's `body_markdown` is treated as
    HTML if it already contains tags (test seeds), otherwise as markdown
    that the caller should have already converted. Preserves existing
    structure and is idempotent on re-run.
    """
    body = article.body_markdown
    sections = _split_into_sections(body)

    spec_by_id: dict[str, ImageSpec] = {s.id: s for s in article.image_specs}

    cover_visual = pick_cover_visual(article)

    # Bucket every rendered visual under the right section, skipping the
    # cover (the transformer hoists that out separately). Match by object
    # identity so heroes without a `spec_id` (legacy DALL-E heroes) are
    # also skipped, not just spec-id-tagged ones.
    planned: dict[int, list[ImageAsset]] = {}
    legacy: dict[int, list[ImageAsset]] = {}
    for asset in article.visuals:
        if cover_visual is not None and asset is cover_visual:
            continue
        meta = asset.metadata or {}
        if _is_unrendered_mermaid(asset):
            # mmdc failed at generation time: the asset's URL is the bare
            # object key with no PNG behind it. The dashboard still renders
            # it client-side from `mermaid_syntax`, but publishing an <img>
            # for it would ship a guaranteed 404 — skip it instead.
            logger.warning(
                "inject_skipped_unrendered_mermaid",
                spec_id=meta.get("spec_id"),
                url=asset.url,
            )
            continue
        spec_id = meta.get("spec_id")
        if isinstance(spec_id, str) and spec_id in spec_by_id:
            section_index = spec_by_id[spec_id].placement.section_index
            planned.setdefault(section_index, []).append(asset)
            continue
        # `image_specs` are not persisted on canonical_articles, so at
        # publish time the spec lookup is empty for every planner visual.
        # Reconstruct the placement from the asset's own metadata (which
        # the render node persists) — otherwise these visuals would fall
        # through to the legacy bucket and be prepended to the article.
        synthesized = _synthesize_spec_from_metadata(asset)
        if synthesized is not None:
            spec_by_id.setdefault(synthesized.id, synthesized)
            planned.setdefault(synthesized.placement.section_index, []).append(asset)
            continue
        # Legacy chart/diagram path: route by metadata.source_section.
        src_section = meta.get("source_section")
        if isinstance(src_section, int):
            legacy.setdefault(src_section, []).append(asset)
        else:
            legacy.setdefault(-1, []).append(asset)

    # Apply per-section injections in spec-anchor order.
    new_sections: list[str] = []
    for section_idx, section_html in enumerate(sections):
        section_html = _inject_before_heading_for(
            section_html, section_idx, planned, spec_by_id, ctx
        )
        section_html = _inject_top(section_html, section_idx, planned, spec_by_id, ctx)
        section_html = _inject_between_paragraphs(
            section_html, section_idx, planned, spec_by_id, ctx
        )
        section_html = _inject_bottom_grid(
            section_html, section_idx, planned, spec_by_id, ctx
        )
        section_html = _inject_background(
            section_html, section_idx, planned, spec_by_id, ctx
        )
        section_html = _inject_column_split(
            section_html, section_idx, planned, spec_by_id, ctx
        )
        # Append any legacy chart/diagram for this section to its end.
        for asset in legacy.get(section_idx, []):
            section_html = section_html + "\n" + _legacy_figure_html(asset, ctx)
        new_sections.append(section_html)

    rendered = "".join(new_sections)

    # Planner visuals whose section no longer exists in the body (sections
    # dropped/merged after rendering): keep them visible at the end rather
    # than losing a paid-for image, and say so.
    for section_idx in sorted(k for k in planned if k >= len(sections)):
        for asset in planned[section_idx]:
            spec = _spec_for_asset(asset, spec_by_id)
            if spec is None or _is_already_injected(rendered, spec.id):
                continue
            logger.warning(
                "inject_visual_section_out_of_range",
                spec_id=spec.id,
                section_index=section_idx,
                section_count=len(sections),
            )
            rendered = rendered + "\n" + _img_html(asset, spec, ctx)

    # Article-level legacy assets (source_section == -1) — prepend.
    for asset in legacy.get(-1, []):
        rendered = _legacy_figure_html(asset, ctx) + "\n" + rendered

    return rendered


def _is_unrendered_mermaid(asset: ImageAsset) -> bool:
    """True when a mermaid asset's URL is a bare object key (mmdc failed).

    A successful render stores a resolvable URL: absolute http(s), a
    `generated_assets/`-relative path, or a local filesystem path. The
    failure fallback keeps the raw storage key (e.g. `sessions/<id>/…`),
    which no static mount serves.
    """
    if (asset.metadata or {}).get("provider") != "mermaid":
        return False
    url = asset.url
    if url.startswith(("http://", "https://", "generated_assets/", "/")):
        return False
    # Windows-style absolute path (test/dev LocalDisk storage).
    return re.match(r"^[A-Za-z]:[\\/]", url) is None


def _synthesize_spec_from_metadata(asset: ImageAsset) -> ImageSpec | None:
    """Rebuild a minimal ImageSpec from a rendered asset's own metadata.

    The render node persists `spec_id`, `placement_anchor`, `section_index`
    (and, since VISUAL-013, `paragraph_index`/`heading_text`) on every
    planner visual. Only the placement fields matter for injection — the
    `prompt` is a placeholder because the image already exists.
    """
    meta = asset.metadata or {}
    spec_id = meta.get("spec_id")
    section_index = meta.get("section_index")
    if not isinstance(spec_id, str) or not spec_id:
        return None
    if not isinstance(section_index, int) or section_index < 0:
        return None
    anchor = meta.get("placement_anchor")
    if anchor not in _SYNTHESIZED_ANCHORS:
        # Missing/unknown/non-visible anchor: render at the section end,
        # mirroring the dashboard's placement.
        anchor = "between_paragraphs"
    paragraph_index = meta.get("paragraph_index")
    if not isinstance(paragraph_index, int) or paragraph_index < 1:
        paragraph_index = None
    heading_text = meta.get("heading_text")
    if not isinstance(heading_text, str) or not heading_text:
        heading_text = None
    role_style = meta.get("role_style")
    if role_style not in _VALID_ROLE_STYLES:
        role_style = "feature_card"
    aspect = meta.get("aspect_ratio")
    if aspect not in _VALID_ASPECTS:
        aspect = "16:9"
    visual_style = meta.get("visual_style")
    try:
        return ImageSpec.model_validate(
            {
                "id": spec_id,
                "role_style": role_style,
                "visual_style": visual_style if isinstance(visual_style, str) else None,
                "prompt": (asset.alt_text or asset.caption or "rendered visual")[:2000],
                "alt_text": asset.alt_text or "",
                "aspect_ratio": aspect,
                "placement": {
                    "anchor": anchor,
                    "heading_text": heading_text,
                    "paragraph_index": paragraph_index,
                    "section_index": section_index,
                },
            }
        )
    except ValidationError:
        return None


def _split_into_sections(body_html: str) -> list[str]:
    """Split HTML by `<h2>` so each section is one chunk."""
    parts = _H2_SPLIT_RE.split(body_html)
    if len(parts) == 1:
        return [body_html]
    sections: list[str] = []
    head = parts[0]
    if head.strip():
        sections.append(head)
    # Re-pair (heading, body) tuples. parts after the first match alternate
    # heading, body, heading, body…
    iterator = iter(parts[1:])
    while True:
        try:
            heading = next(iterator)
        except StopIteration:
            break
        try:
            content = next(iterator)
        except StopIteration:
            content = ""
        sections.append(heading + content)
    return sections


def _matching_specs(
    section_index: int,
    anchor: str,
    spec_by_id: dict[str, ImageSpec],
) -> list[ImageSpec]:
    return [
        spec
        for spec in spec_by_id.values()
        if spec.placement.section_index == section_index
        and spec.placement.anchor == anchor
    ]


def _spec_for_asset(
    asset: ImageAsset, spec_by_id: dict[str, ImageSpec]
) -> ImageSpec | None:
    spec_id = (asset.metadata or {}).get("spec_id")
    if isinstance(spec_id, str):
        return spec_by_id.get(spec_id)
    return None


def _img_html(asset: ImageAsset, spec: ImageSpec, ctx: InjectionContext) -> str:
    url = _asset_url(asset.url, ctx.api_base_url)
    alt = html.escape(asset.alt_text or spec.alt_text or "")
    caption = html.escape(asset.caption or "")
    figure = (
        f'<figure class="cog-figure" data-spec-id="{html.escape(spec.id)}">'
        f'<img src="{url}" alt="{alt}" '
        'style="max-width:100%;height:auto;" loading="lazy" />'
    )
    if caption:
        figure += f"<figcaption>{caption}</figcaption>"
    figure += "</figure>"
    return figure


def _legacy_figure_html(asset: ImageAsset, ctx: InjectionContext) -> str:
    url = _asset_url(asset.url, ctx.api_base_url)
    alt = html.escape(asset.alt_text or "")
    caption = html.escape(asset.caption or "")
    fig = (
        f'<figure class="cog-legacy-figure">'
        f'<img src="{url}" alt="{alt}" '
        'style="max-width:100%;height:auto;" loading="lazy" />'
    )
    if caption:
        fig += f"<figcaption>{caption}</figcaption>"
    fig += "</figure>"
    return fig


def _is_already_injected(html_str: str, spec_id: str) -> bool:
    return f'data-spec-id="{html.escape(spec_id)}"' in html_str


def _inject_top(
    section_html: str,
    section_index: int,
    planned: dict[int, list[ImageAsset]],
    spec_by_id: dict[str, ImageSpec],
    ctx: InjectionContext,
) -> str:
    specs = _matching_specs(section_index, "top", spec_by_id)
    if not specs:
        return section_html
    out = section_html
    for spec in specs:
        if _is_already_injected(out, spec.id):
            continue
        asset = _find_asset(spec, planned.get(section_index, []))
        if asset is None:
            continue
        snippet = _img_html(asset, spec, ctx) + "\n"
        # Insert AFTER the section heading if present, otherwise at the start.
        match = _H2_SPLIT_RE.search(out)
        if match:
            insert_at = match.end()
            out = out[:insert_at] + "\n" + snippet + out[insert_at:]
        else:
            out = snippet + out
    return out


def _inject_between_paragraphs(
    section_html: str,
    section_index: int,
    planned: dict[int, list[ImageAsset]],
    spec_by_id: dict[str, ImageSpec],
    ctx: InjectionContext,
) -> str:
    specs = _matching_specs(section_index, "between_paragraphs", spec_by_id)
    if not specs:
        return section_html
    out = section_html
    # Re-find paragraphs each time so positions stay valid after inserts.
    for spec in specs:
        if _is_already_injected(out, spec.id):
            continue
        asset = _find_asset(spec, planned.get(section_index, []))
        if asset is None:
            continue
        para_index = spec.placement.paragraph_index
        p_iter = list(_P_SPLIT_RE.finditer(out))
        snippet = "\n" + _img_html(asset, spec, ctx) + "\n"
        # paragraph_index is 1-based: =1 means "after the first paragraph",
        # placing the visual between p[0] and p[1].
        anchor_para = (para_index or 0) - 1
        if anchor_para < 0 or anchor_para >= len(p_iter):
            # No paragraph hint (specs reconstructed from persisted
            # metadata) or a hint past the section's paragraphs (planner
            # counted markdown blocks, or the section was shortened): append
            # at the section end, mirroring the dashboard, instead of
            # dropping the visual. Appending keeps article order for
            # multiple hint-less visuals in one section.
            out = out + snippet
            continue
        end = p_iter[anchor_para].end()
        out = out[:end] + snippet + out[end:]
    return out


def _inject_before_heading_for(
    section_html: str,
    section_index: int,
    planned: dict[int, list[ImageAsset]],
    spec_by_id: dict[str, ImageSpec],
    ctx: InjectionContext,
) -> str:
    specs = _matching_specs(section_index, "before_heading", spec_by_id)
    if not specs:
        return section_html
    out = section_html
    for spec in specs:
        if _is_already_injected(out, spec.id):
            continue
        asset = _find_asset(spec, planned.get(section_index, []))
        if asset is None:
            continue
        # Insert before the section's H2 (the one starting this section).
        match = _H2_SPLIT_RE.search(out)
        snippet = _img_html(asset, spec, ctx) + "\n"
        if match:
            out = out[: match.start()] + snippet + out[match.start() :]
        else:
            out = snippet + out
    return out


def _inject_bottom_grid(
    section_html: str,
    section_index: int,
    planned: dict[int, list[ImageAsset]],
    spec_by_id: dict[str, ImageSpec],
    ctx: InjectionContext,
) -> str:
    specs = _matching_specs(section_index, "bottom_grid", spec_by_id)
    if not specs:
        return section_html
    items: list[str] = []
    for spec in specs:
        if _is_already_injected(section_html, spec.id):
            continue
        asset = _find_asset(spec, planned.get(section_index, []))
        if asset is None:
            continue
        items.append(_img_html(asset, spec, ctx))
    if not items:
        return section_html
    grid = '\n<div class="cog-grid">' + "".join(items) + "</div>\n"
    return section_html + grid


def _inject_background(
    section_html: str,
    section_index: int,
    planned: dict[int, list[ImageAsset]],
    spec_by_id: dict[str, ImageSpec],
    ctx: InjectionContext,
) -> str:
    specs = _matching_specs(section_index, "background", spec_by_id)
    if not specs:
        return section_html
    out = section_html
    for spec in specs:
        url = _asset_url_for_spec(spec, planned, section_index, ctx)
        marker = f'<!-- bg-image:{url} spec-id="{spec.id}" -->\n'
        if marker.strip() in out:
            continue
        out = marker + out
    return out


def _inject_column_split(
    section_html: str,
    section_index: int,
    planned: dict[int, list[ImageAsset]],
    spec_by_id: dict[str, ImageSpec],
    ctx: InjectionContext,
) -> str:
    specs = _matching_specs(section_index, "column_split", spec_by_id)
    if not specs:
        return section_html
    spec = specs[0]
    if _is_already_injected(section_html, spec.id):
        return section_html
    asset = _find_asset(spec, planned.get(section_index, []))
    if asset is None:
        return section_html
    image_col = _img_html(asset, spec, ctx)
    return (
        '<div class="cog-col-split">'
        f'<div class="cog-col-text">{section_html}</div>'
        f'<div class="cog-col-image">{image_col}</div>'
        "</div>"
    )


def _find_asset(spec: ImageSpec, candidates: list[ImageAsset]) -> ImageAsset | None:
    # Latest render wins: Visual Studio regenerate + "Insert into article"
    # appends a second asset under the same spec id, and the newest one is
    # the one the editor accepted.
    for asset in reversed(candidates):
        if (asset.metadata or {}).get("spec_id") == spec.id:
            return asset
    return None


def _asset_url_for_spec(
    spec: ImageSpec,
    planned: dict[int, list[ImageAsset]],
    section_index: int,
    ctx: InjectionContext,
) -> str:
    asset = _find_asset(spec, planned.get(section_index, []))
    if asset is None:
        return ""
    return _asset_url(asset.url, ctx.api_base_url)


def _asset_url(path: str, api_base: str) -> str:
    """Convert a local file path to an HTTP URL served by the API."""
    if path.startswith(("http://", "https://")):
        return path
    normalized = path.replace("\\", "/")
    base = api_base.rstrip("/")
    if normalized.startswith("generated_assets/"):
        return f"{base}/{normalized}"
    return f"{base}/generated_assets/{normalized.lstrip('/')}"
