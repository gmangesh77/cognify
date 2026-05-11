"""Tests for the per-anchor markdown injector (Phase 3 / VISUAL-006).

`inject_visuals` walks an article's HTML body section by section and
folds each `ImageAsset` into the right place based on its planning
metadata (`spec_id`, `placement_anchor`, `section_index`, etc.). The
function is idempotent: running it twice with the same article never
duplicates an image.
"""

from __future__ import annotations

import re

from src.models.content import (
    CanonicalArticle,
    Citation,
    ContentType,
    ImageAsset,
    Provenance,
    SEOMetadata,
)
from src.models.visual import ImagePlacement, ImageSpec
from src.services.visuals.inject import (
    InjectionContext,
    inject_visuals,
    pick_cover_visual,
)


def _provenance() -> Provenance:
    from uuid import uuid4

    return Provenance(
        research_session_id=uuid4(),
        primary_model="claude-opus-4",
        drafting_model="claude-sonnet-4",
        embedding_model="all-MiniLM-L6-v2",
        embedding_version="1.0.0",
    )


def _spec(
    spec_id: str,
    *,
    role_style: str = "feature_card",
    anchor: str = "top",
    section_index: int = 0,
    visual_style: str | None = None,
    aspect_ratio: str = "16:9",
    heading_text: str | None = None,
    paragraph_index: int | None = None,
) -> ImageSpec:
    return ImageSpec(
        id=spec_id,
        role_style=role_style,  # type: ignore[arg-type]
        visual_style=visual_style,
        prompt="A subject scene.",
        alt_text=f"alt for {spec_id}",
        aspect_ratio=aspect_ratio,  # type: ignore[arg-type]
        placement=ImagePlacement(
            anchor=anchor,  # type: ignore[arg-type]
            heading_text=heading_text,
            paragraph_index=paragraph_index,
            section_index=section_index,
        ),
    )


def _asset(spec_id: str, *, url: str = "/visuals/img.png") -> ImageAsset:
    return ImageAsset(
        url=url,
        caption="Caption " + spec_id,
        alt_text="alt " + spec_id,
        metadata={
            "spec_id": spec_id,
            "role_style": "feature_card",
            "visual_style": "lifestyle_photo",
            "aspect_ratio": "16:9",
            "placement_anchor": "top",
            "section_index": 0,
            "provider": "gemini_flash",
            "model": "stub",
            "prompt_used": "p",
            "cost_usd": 0.0,
            "generation_ms": 1,
        },
    )


_DEFAULT_INTRO = (
    "<h2>Intro</h2>\n<p>First paragraph.</p>\n"
    "<p>Second paragraph.</p>\n<p>Third paragraph.</p>"
)
_DEFAULT_ARCH = "<h2>Architecture</h2>\n<p>Body of architecture.</p>"


def _article(
    *,
    body_html_sections: tuple[str, ...] = (_DEFAULT_INTRO, _DEFAULT_ARCH),
    image_specs: list[ImageSpec] | None = None,
    visuals: list[ImageAsset] | None = None,
) -> CanonicalArticle:
    body = "\n\n".join(body_html_sections)
    return CanonicalArticle(
        title="Quiet Refactor",
        body_markdown=body,
        summary="Small steps compound.",
        key_claims=["Small steps compound."],
        content_type=ContentType.ARTICLE,
        seo=SEOMetadata(title="Quiet Refactor", description="Wins via small steps."),
        citations=[Citation(index=1, title="Source", url="https://x.test/1")],
        authors=["Cognify"],
        domain="engineering",
        provenance=_provenance(),
        image_specs=image_specs or [],
        visuals=visuals or [],
    )


def _ctx(api_base: str = "https://cognify.test") -> InjectionContext:
    return InjectionContext(api_base_url=api_base)


def _img_count(html: str, spec_id: str) -> int:
    return len(re.findall(rf'data-spec-id="{re.escape(spec_id)}"', html))


class TestPickCoverVisual:
    def test_returns_visual_with_cover_anchor(self) -> None:
        cover_spec = _spec("cover", role_style="hero", anchor="cover", section_index=-1)
        section_spec = _spec("body", anchor="top", section_index=0)
        cover_visual = ImageAsset(
            url="/visuals/cover.png",
            metadata={
                "spec_id": "cover",
                "placement_anchor": "cover",
                "section_index": -1,
            },
        )
        section_visual = ImageAsset(
            url="/visuals/body.png",
            metadata={
                "spec_id": "body",
                "placement_anchor": "top",
                "section_index": 0,
            },
        )
        article = _article(
            image_specs=[cover_spec, section_spec],
            visuals=[section_visual, cover_visual],
        )
        picked = pick_cover_visual(article)
        assert picked is not None
        assert picked.metadata.get("spec_id") == "cover"

    def test_falls_back_to_legacy_hero_metadata(self) -> None:
        legacy = ImageAsset(
            url="/visuals/legacy.png",
            metadata={"type": "hero"},
        )
        article = _article(image_specs=[], visuals=[legacy])
        picked = pick_cover_visual(article)
        assert picked is legacy

    def test_recognises_role_style_hero_from_visual_studio_render(self) -> None:
        # Visual Studio renders emit `role_style: "hero"` (not `type: "hero"`)
        # and `section_index: -1`. They are not in `image_specs` because the
        # spec id is a generated `fallback_*` rather than a planned id, so the
        # spec_id lookup misses. The cover picker must still hoist them.
        chart = ImageAsset(
            url="/visuals/chart.png",
            metadata={"chart_type": "bar", "source_section": 5},
        )
        studio_hero = ImageAsset(
            url="/visuals/hero.png",
            metadata={
                "spec_id": "fallback_abc123",
                "role_style": "hero",
                "section_index": -1,
                "provider": "dalle_3",
            },
        )
        article = _article(image_specs=[], visuals=[chart, studio_hero])
        picked = pick_cover_visual(article)
        assert picked is studio_hero

    def test_returns_none_when_no_cover(self) -> None:
        section_spec = _spec("body", anchor="top", section_index=0)
        section_visual = ImageAsset(
            url="/visuals/body.png",
            metadata={"spec_id": "body", "placement_anchor": "top"},
        )
        article = _article(image_specs=[section_spec], visuals=[section_visual])
        assert pick_cover_visual(article) is None


class TestInjectAnchorTop:
    def test_top_prepends_image_to_section(self) -> None:
        spec = _spec("intro_top", anchor="top", section_index=0)
        asset = _asset("intro_top")
        article = _article(image_specs=[spec], visuals=[asset])

        result = inject_visuals(article, _ctx())
        # Image should appear inside section 0 before its first <p>.
        # Cover anchor isn't picked here so cover image is omitted.
        intro_section = result.split("<h2>Architecture</h2>")[0]
        first_p = intro_section.find("<p>First paragraph")
        first_img = intro_section.find('data-spec-id="intro_top"')
        assert first_img != -1
        assert first_img < first_p


class TestInjectAnchorBetweenParagraphs:
    def test_between_paragraphs_inserts_after_nth_paragraph(self) -> None:
        spec = _spec(
            "mid", anchor="between_paragraphs", paragraph_index=1, section_index=0
        )
        asset = _asset("mid")
        article = _article(image_specs=[spec], visuals=[asset])

        result = inject_visuals(article, _ctx())
        intro_section = result.split("<h2>Architecture</h2>")[0]
        # Image should sit between <p>First …</p> and <p>Second …</p>
        first_p_end = intro_section.find("</p>", intro_section.find("First paragraph"))
        img_idx = intro_section.find('data-spec-id="mid"')
        second_p_start = intro_section.find("<p>Second paragraph")
        assert first_p_end < img_idx < second_p_start


class TestInjectAnchorBeforeHeading:
    def test_before_heading_inserts_before_matching_h2(self) -> None:
        spec = _spec(
            "pre_arch",
            anchor="before_heading",
            heading_text="Architecture",
            section_index=1,
        )
        asset = _asset("pre_arch")
        article = _article(image_specs=[spec], visuals=[asset])

        result = inject_visuals(article, _ctx())
        img_idx = result.find('data-spec-id="pre_arch"')
        h2_idx = result.find("<h2>Architecture")
        assert img_idx != -1
        assert img_idx < h2_idx


class TestInjectAnchorBottomGrid:
    def test_bottom_grid_collects_into_one_div(self) -> None:
        s1 = _spec("g1", anchor="bottom_grid", section_index=0)
        s2 = _spec("g2", anchor="bottom_grid", section_index=0)
        article = _article(
            image_specs=[s1, s2],
            visuals=[_asset("g1"), _asset("g2")],
        )
        result = inject_visuals(article, _ctx())
        # Both spec IDs appear inside a single cog-grid container.
        grid_match = re.search(
            r'<div class="cog-grid">(.*?)</div>', result, flags=re.DOTALL
        )
        assert grid_match is not None
        block = grid_match.group(1)
        assert 'data-spec-id="g1"' in block
        assert 'data-spec-id="g2"' in block


class TestInjectAnchorBackground:
    def test_background_emits_marker_comment(self) -> None:
        spec = _spec("bg", anchor="background", section_index=0)
        article = _article(image_specs=[spec], visuals=[_asset("bg", url="/v/bg.png")])
        result = inject_visuals(article, _ctx())
        assert "<!-- bg-image:" in result
        assert "/v/bg.png" in result


class TestInjectAnchorColumnSplit:
    def test_column_split_wraps_section(self) -> None:
        spec = _spec("col", anchor="column_split", section_index=1)
        article = _article(
            image_specs=[spec],
            visuals=[_asset("col", url="/v/col.png")],
        )
        result = inject_visuals(article, _ctx())
        # The architecture section should be wrapped in cog-col-split.
        assert '<div class="cog-col-split">' in result
        assert 'data-spec-id="col"' in result


class TestInjectIdempotent:
    def test_double_injection_does_not_duplicate(self) -> None:
        spec = _spec("once", anchor="top", section_index=0)
        article = _article(image_specs=[spec], visuals=[_asset("once")])
        once = inject_visuals(article, _ctx())
        # A second pass over the result must not add another copy.
        # We simulate this by passing the already-injected HTML body back in.
        article2 = _article(
            image_specs=[spec],
            visuals=[_asset("once")],
            body_html_sections=(once,),
        )
        twice = inject_visuals(article2, _ctx())
        assert _img_count(twice, "once") == 1


class TestInjectIgnoresCover:
    def test_cover_visual_not_inlined(self) -> None:
        # Cover is owned by the transformer (feature_image), not inject.
        cover_spec = _spec("cover", role_style="hero", anchor="cover", section_index=-1)
        cover_visual = ImageAsset(
            url="/v/cover.png",
            metadata={
                "spec_id": "cover",
                "placement_anchor": "cover",
                "section_index": -1,
            },
        )
        article = _article(image_specs=[cover_spec], visuals=[cover_visual])
        result = inject_visuals(article, _ctx())
        assert 'data-spec-id="cover"' not in result


class TestInjectRewritesLocalPath:
    def test_local_path_becomes_api_base_url(self) -> None:
        spec = _spec("img", anchor="top", section_index=0)
        asset = ImageAsset(
            url="generated_assets/visuals/img.png",
            metadata={"spec_id": "img", "placement_anchor": "top"},
        )
        article = _article(image_specs=[spec], visuals=[asset])
        result = inject_visuals(article, _ctx(api_base="https://cdn.example"))
        assert "https://cdn.example/generated_assets/visuals/img.png" in result


class TestInjectFallsBackOnUnplannedVisuals:
    def test_legacy_visuals_without_spec_id_still_render_at_section_end(self) -> None:
        # Charts/diagrams from VISUAL-001/-003 don't have a spec_id but DO have
        # a source_section. Inject must place them at the end of that section
        # so the legacy charts/diagrams stay visible after the rewrite.
        legacy_chart = ImageAsset(
            url="/charts/x.png",
            caption="Bar chart",
            alt_text="Bar chart",
            metadata={"type": "chart", "source_section": 1},
        )
        article = _article(image_specs=[], visuals=[legacy_chart])
        result = inject_visuals(article, _ctx())
        # The chart should appear after <h2>Architecture</h2>.
        h2_idx = result.find("<h2>Architecture")
        img_idx = result.find("/charts/x.png")
        assert img_idx > h2_idx


class TestInjectMultiSpecOrdering:
    def test_multiple_specs_in_one_section_preserve_order(self) -> None:
        specs = [
            _spec("a", anchor="top", section_index=0),
            _spec(
                "b",
                anchor="between_paragraphs",
                paragraph_index=1,
                section_index=0,
            ),
        ]
        visuals = [_asset("a"), _asset("b")]
        article = _article(image_specs=specs, visuals=visuals)
        result = inject_visuals(article, _ctx())
        a_idx = result.find('data-spec-id="a"')
        b_idx = result.find('data-spec-id="b"')
        assert a_idx != -1 and b_idx != -1
        # `top` precedes `between_paragraphs`.
        assert a_idx < b_idx
