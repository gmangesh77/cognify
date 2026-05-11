"""Multi-anchor transformer tests (Phase 3 / VISUAL-006).

End-to-end checks that Ghost, Medium, and LinkedIn transformers all
respect the per-anchor placement contract from `inject_visuals` and
`pick_cover_visual`. Single source of truth for "does this transformer
respect the new boundary?"
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.models.content import (
    CanonicalArticle,
    Citation,
    ContentType,
    ImageAsset,
    Provenance,
    SchemaOrgAuthor,
    SEOMetadata,
    StructuredDataLD,
)
from src.models.visual import ImagePlacement, ImageSpec
from src.services.publishing.ghost.transformer import GhostTransformer
from src.services.publishing.linkedin.transformer import LinkedInTransformer
from src.services.publishing.medium.transformer import MediumTransformer


def _provenance() -> Provenance:
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
    paragraph_index: int | None = None,
    heading_text: str | None = None,
) -> ImageSpec:
    return ImageSpec(
        id=spec_id,
        role_style=role_style,  # type: ignore[arg-type]
        prompt="Subject scene.",
        alt_text=f"alt for {spec_id}",
        aspect_ratio="16:9",
        placement=ImagePlacement(
            anchor=anchor,  # type: ignore[arg-type]
            heading_text=heading_text,
            paragraph_index=paragraph_index,
            section_index=section_index,
        ),
    )


def _asset(
    spec_id: str,
    *,
    url: str | None = None,
    anchor: str = "top",
    section_index: int = 0,
) -> ImageAsset:
    return ImageAsset(
        url=url or f"/visuals/{spec_id}.png",
        caption=f"Caption {spec_id}",
        alt_text=f"alt {spec_id}",
        metadata={
            "spec_id": spec_id,
            "role_style": "feature_card",
            "visual_style": "lifestyle_photo",
            "aspect_ratio": "16:9",
            "placement_anchor": anchor,
            "section_index": section_index,
            "provider": "gemini_flash",
            "model": "stub",
            "prompt_used": "p",
            "cost_usd": 0.0,
            "generation_ms": 1,
        },
    )


@pytest.fixture
def multi_anchor_article() -> CanonicalArticle:
    """Article with cover + section-top + between-paragraphs + bottom-grid."""
    cover_spec = _spec("cover", role_style="hero", anchor="cover", section_index=-1)
    intro_top = _spec("intro_top", anchor="top", section_index=0)
    arch_mid = _spec(
        "arch_mid", anchor="between_paragraphs", paragraph_index=1, section_index=1
    )
    grid_a = _spec("grid_a", anchor="bottom_grid", section_index=1)
    grid_b = _spec("grid_b", anchor="bottom_grid", section_index=1)

    cover_visual = _asset("cover", anchor="cover", section_index=-1)
    intro_visual = _asset("intro_top", anchor="top", section_index=0)
    mid_visual = _asset("arch_mid", anchor="between_paragraphs", section_index=1)
    grid_a_visual = _asset("grid_a", anchor="bottom_grid", section_index=1)
    grid_b_visual = _asset("grid_b", anchor="bottom_grid", section_index=1)

    now = datetime.now(UTC).isoformat()
    return CanonicalArticle(
        title="Multi Anchor Test",
        body_markdown=(
            "## Intro\n\n"
            "First paragraph here.\n\n"
            "Second paragraph here.\n\n"
            "## Architecture\n\n"
            "Arch para one.\n\n"
            "Arch para two.\n\n"
            "Arch para three.\n"
        ),
        summary="Article testing multi-anchor visual injection.",
        key_claims=["Multi-anchor works."],
        content_type=ContentType.ANALYSIS,
        seo=SEOMetadata(
            title="Multi Anchor",
            description="A multi-anchor visual integration test.",
            keywords=["test", "anchor"],
            canonical_url="https://cognify.app/articles/multi-anchor",
            structured_data=StructuredDataLD(
                headline="Multi Anchor",
                description="Multi-anchor test.",
                keywords=["test"],
                author=SchemaOrgAuthor(),
                datePublished=now,
                dateModified=now,
            ),
        ),
        citations=[Citation(index=1, title="S", url="https://e.test/1")],
        authors=["Cognify"],
        domain="engineering",
        provenance=_provenance(),
        image_specs=[cover_spec, intro_top, arch_mid, grid_a, grid_b],
        visuals=[
            cover_visual,
            intro_visual,
            mid_visual,
            grid_a_visual,
            grid_b_visual,
        ],
    )


class TestGhostMultiAnchor:
    def test_cover_lifted_to_feature_image(
        self, multi_anchor_article: CanonicalArticle
    ) -> None:
        result = GhostTransformer().transform(multi_anchor_article)
        assert "feature_image" in result.metadata
        assert "cover.png" in str(result.metadata["feature_image"])

    def test_cover_not_inlined_in_body(
        self, multi_anchor_article: CanonicalArticle
    ) -> None:
        result = GhostTransformer().transform(multi_anchor_article)
        assert 'data-spec-id="cover"' not in result.content

    def test_section_top_visual_present(
        self, multi_anchor_article: CanonicalArticle
    ) -> None:
        result = GhostTransformer().transform(multi_anchor_article)
        assert 'data-spec-id="intro_top"' in result.content

    def test_between_paragraphs_visual_present(
        self, multi_anchor_article: CanonicalArticle
    ) -> None:
        result = GhostTransformer().transform(multi_anchor_article)
        assert 'data-spec-id="arch_mid"' in result.content

    def test_bottom_grid_visuals_collected(
        self, multi_anchor_article: CanonicalArticle
    ) -> None:
        result = GhostTransformer().transform(multi_anchor_article)
        assert '<div class="cog-grid">' in result.content
        assert 'data-spec-id="grid_a"' in result.content
        assert 'data-spec-id="grid_b"' in result.content


class TestMediumMultiAnchor:
    def test_cover_prepended_to_html(
        self, multi_anchor_article: CanonicalArticle
    ) -> None:
        result = MediumTransformer().transform(multi_anchor_article)
        # Cover figure should appear before any <h2>.
        cover_idx = result.content.find('class="cog-cover"')
        h2_idx = result.content.find("<h2>")
        assert cover_idx != -1 and h2_idx != -1
        assert cover_idx < h2_idx

    def test_cover_image_url_in_metadata(
        self, multi_anchor_article: CanonicalArticle
    ) -> None:
        result = MediumTransformer().transform(multi_anchor_article)
        assert "cover_image" in result.metadata
        assert "cover.png" in str(result.metadata["cover_image"])

    def test_section_visuals_present(
        self, multi_anchor_article: CanonicalArticle
    ) -> None:
        result = MediumTransformer().transform(multi_anchor_article)
        assert 'data-spec-id="intro_top"' in result.content
        assert 'data-spec-id="arch_mid"' in result.content


class TestLinkedInMultiAnchor:
    def test_cover_image_url_surfaced_in_metadata(
        self, multi_anchor_article: CanonicalArticle
    ) -> None:
        result = LinkedInTransformer().transform(multi_anchor_article)
        assert "cover_image_url" in result.metadata
        assert "cover.png" in str(result.metadata["cover_image_url"])

    def test_cover_alt_text_surfaced_in_metadata(
        self, multi_anchor_article: CanonicalArticle
    ) -> None:
        result = LinkedInTransformer().transform(multi_anchor_article)
        assert result.metadata.get("cover_image_alt") == "alt cover"

    def test_commentary_remains_text_only(
        self, multi_anchor_article: CanonicalArticle
    ) -> None:
        result = LinkedInTransformer().transform(multi_anchor_article)
        # No HTML img tags or data-spec-id markers should leak into commentary.
        assert "<img" not in result.content
        assert "data-spec-id" not in result.content


@pytest.fixture
def legacy_chart_plus_studio_hero_article() -> CanonicalArticle:
    """Article with a legacy chart and a Visual Studio-rendered hero.

    Mirrors the production state where:
      - the content pipeline produced a chart (no `spec_id`, `source_section=1`)
      - the user later attached a hero via Visual Studio's `attach_visual`
        endpoint (`spec_id = "fallback_*"`, `role_style = "hero"`,
        `section_index = -1`).
    Neither asset has a matching entry in `image_specs`.
    """
    now = datetime.now(UTC).isoformat()
    chart = ImageAsset(
        url="generated_assets/charts/run/abc.png",
        caption="Workflow chart caption.",
        alt_text="Workflow chart",
        metadata={"chart_type": "bar", "source_section": 1},
    )
    studio_hero = ImageAsset(
        url="http://localhost:8000/generated_assets/visuals/renders/hero.png",
        caption="Hero cover.",
        alt_text="",
        metadata={
            "spec_id": "fallback_abc123",
            "role_style": "hero",
            "section_index": -1,
            "provider": "dalle_3",
            "model": "dall-e-3",
        },
    )
    return CanonicalArticle(
        title="Hero plus chart",
        body_markdown=(
            "## Intro\n\n"
            "First paragraph.\n\n"
            "## Outlook\n\n"
            "Closing paragraph with the chart anchor.\n"
        ),
        summary="Article with a Visual Studio hero attached after the fact.",
        key_claims=["The hero is the cover."],
        content_type=ContentType.ANALYSIS,
        seo=SEOMetadata(
            title="Hero plus chart",
            description="Tests hero/chart hoisting.",
            keywords=["hero", "chart"],
            canonical_url="https://cognify.app/articles/hero-plus-chart",
            structured_data=StructuredDataLD(
                headline="Hero plus chart",
                description="Tests hero/chart hoisting.",
                keywords=["hero"],
                author=SchemaOrgAuthor(),
                datePublished=now,
                dateModified=now,
            ),
        ),
        citations=[Citation(index=1, title="S", url="https://e.test/1")],
        authors=["Cognify"],
        domain="engineering",
        provenance=_provenance(),
        image_specs=[],
        visuals=[chart, studio_hero],
    )


class TestVisualStudioHeroHoisting:
    """Regression suite for the user-reported duplicate-hero bug.

    Before the fix:
      - `pick_cover_visual` only recognised `metadata.type == "hero"`, so the
        Visual Studio hero (which uses `role_style: "hero"`) was missed.
      - The cover fell back to `visuals[0]` (the chart), and the actual hero
        — having no matching `image_spec` — was injected into the body as an
        article-level legacy figure (prepended).
      - Result on Ghost: chart used as `feature_image`, hero duplicated in body.
    """

    def test_hero_lifted_to_feature_image(
        self, legacy_chart_plus_studio_hero_article: CanonicalArticle
    ) -> None:
        result = GhostTransformer().transform(
            legacy_chart_plus_studio_hero_article
        )
        assert "feature_image" in result.metadata
        assert "hero.png" in str(result.metadata["feature_image"])
        assert "charts/run/abc.png" not in str(result.metadata["feature_image"])

    def test_hero_not_duplicated_in_body(
        self, legacy_chart_plus_studio_hero_article: CanonicalArticle
    ) -> None:
        result = GhostTransformer().transform(
            legacy_chart_plus_studio_hero_article
        )
        # The hero is hoisted as feature_image; it must NOT appear in the body.
        assert "hero.png" not in result.content

    def test_chart_still_renders_inline(
        self, legacy_chart_plus_studio_hero_article: CanonicalArticle
    ) -> None:
        result = GhostTransformer().transform(
            legacy_chart_plus_studio_hero_article
        )
        # The chart legacy figure is anchored to section 1, so it must remain
        # in the body even when a hero exists.
        assert "charts/run/abc.png" in result.content


class TestGhostIdempotence:
    def test_double_transform_does_not_duplicate_spec_renders(
        self, multi_anchor_article: CanonicalArticle
    ) -> None:
        once = GhostTransformer().transform(multi_anchor_article)
        # Re-running on the same article must produce the same content count.
        twice = GhostTransformer().transform(multi_anchor_article)
        for spec_id in ("intro_top", "arch_mid", "grid_a"):
            assert once.content.count(f'data-spec-id="{spec_id}"') == 1
            assert twice.content.count(f'data-spec-id="{spec_id}"') == 1
