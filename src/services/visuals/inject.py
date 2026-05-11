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

from src.models.content import CanonicalArticle, ImageAsset
from src.models.visual import ImageSpec

_H2_SPLIT_RE = re.compile(r"(<h2[^>]*>.*?</h2>)", flags=re.DOTALL | re.IGNORECASE)
_P_SPLIT_RE = re.compile(r"(<p[^>]*>.*?</p>)", flags=re.DOTALL | re.IGNORECASE)


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
        spec_id = meta.get("spec_id")
        if isinstance(spec_id, str) and spec_id in spec_by_id:
            section_index = spec_by_id[spec_id].placement.section_index
            planned.setdefault(section_index, []).append(asset)
        else:
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

    # Article-level legacy assets (source_section == -1) — prepend.
    for asset in legacy.get(-1, []):
        rendered = _legacy_figure_html(asset, ctx) + "\n" + rendered

    return rendered


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
        if para_index is None or para_index < 1:
            continue
        # paragraph_index is 1-based: =1 means "after the first paragraph",
        # placing the visual between p[0] and p[1].
        p_iter = list(_P_SPLIT_RE.finditer(out))
        anchor_para = para_index - 1
        if anchor_para >= len(p_iter):
            continue
        end = p_iter[anchor_para].end()
        snippet = "\n" + _img_html(asset, spec, ctx) + "\n"
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
    for asset in candidates:
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
