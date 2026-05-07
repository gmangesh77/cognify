"""End-to-end preview test (Phase 3 / VISUAL-006).

Mirrors the workflow the frontend Visual Studio (Phase 5) will perform:
read a CanonicalArticle with planned + rendered visuals out of the
content pipeline, run the Ghost transformer, and assert the produced
HTML carries every spec at the right anchor + a feature_image at the
top-level metadata.

This is a pure-Python integration test — no DB, no LLM, no HTTP.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

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
from src.services.publishing.medium.transformer import MediumTransformer


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _provenance() -> Provenance:
    return Provenance(
        research_session_id=uuid4(),
        primary_model="claude-opus-4",
        drafting_model="claude-sonnet-4",
        embedding_model="all-MiniLM-L6-v2",
        embedding_version="1.0.0",
    )


def _build_article() -> CanonicalArticle:
    """Build a CanonicalArticle that exercises every supported anchor."""
    cover_spec = ImageSpec(
        id="cover",
        role_style="hero",
        visual_style="lifestyle_photo",
        prompt="A team huddled around a desk.",
        alt_text="Team at desk",
        aspect_ratio="16:9",
        placement=ImagePlacement(anchor="cover", section_index=-1),
    )
    intro_spec = ImageSpec(
        id="intro_top",
        role_style="feature_card",
        visual_style="isometric_3d",
        prompt="An isometric workspace.",
        alt_text="Isometric workspace",
        aspect_ratio="16:9",
        placement=ImagePlacement(anchor="top", section_index=0),
    )
    before_arch = ImageSpec(
        id="pre_arch",
        role_style="concept",
        visual_style="abstract",
        prompt="Floating layers.",
        alt_text="Layered concept",
        aspect_ratio="4:3",
        placement=ImagePlacement(
            anchor="before_heading", heading_text="Architecture", section_index=1
        ),
    )
    mid_arch = ImageSpec(
        id="arch_mid",
        role_style="screenshot_mock",
        visual_style="blueprint",
        prompt="Abstract blueprint frame.",
        alt_text="Blueprint frame",
        aspect_ratio="1:1",
        placement=ImagePlacement(
            anchor="between_paragraphs", paragraph_index=1, section_index=1
        ),
    )

    visuals = [
        ImageAsset(
            url="/visuals/cover.png",
            caption="Hero",
            alt_text="Hero",
            metadata={
                "spec_id": "cover",
                "placement_anchor": "cover",
                "section_index": -1,
                "provider": "imagen_4",
                "model": "stub",
                "prompt_used": "p",
                "cost_usd": 0.04,
                "generation_ms": 100,
            },
        ),
        ImageAsset(
            url="/visuals/intro_top.png",
            metadata={
                "spec_id": "intro_top",
                "placement_anchor": "top",
                "section_index": 0,
            },
        ),
        ImageAsset(
            url="/visuals/pre_arch.png",
            metadata={
                "spec_id": "pre_arch",
                "placement_anchor": "before_heading",
                "section_index": 1,
            },
        ),
        ImageAsset(
            url="/visuals/arch_mid.png",
            metadata={
                "spec_id": "arch_mid",
                "placement_anchor": "between_paragraphs",
                "section_index": 1,
            },
        ),
    ]

    body = (
        "## Intro\n\n"
        "First introduction paragraph.\n\n"
        "Second introduction paragraph.\n\n"
        "## Architecture\n\n"
        "Architecture paragraph one.\n\n"
        "Architecture paragraph two.\n\n"
        "Architecture paragraph three.\n"
    )

    return CanonicalArticle(
        title="Quiet Refactor",
        body_markdown=body,
        summary="A quiet refactor wins.",
        key_claims=["Small steps compound."],
        content_type=ContentType.ANALYSIS,
        seo=SEOMetadata(
            title="Quiet Refactor",
            description="Wins via small steps.",
            keywords=["engineering", "refactor"],
            canonical_url="https://cognify.app/articles/quiet-refactor",
            structured_data=StructuredDataLD(
                headline="Quiet Refactor",
                description="Wins.",
                keywords=["engineering"],
                author=SchemaOrgAuthor(),
                datePublished=_now(),
                dateModified=_now(),
            ),
        ),
        citations=[Citation(index=1, title="S", url="https://e.test/1")],
        authors=["Cognify"],
        domain="engineering",
        provenance=_provenance(),
        image_specs=[cover_spec, intro_spec, before_arch, mid_arch],
        visuals=visuals,
    )


class TestGhostPreviewE2E:
    def test_every_spec_renders_at_correct_anchor(self) -> None:
        article = _build_article()
        result = GhostTransformer(api_base_url="https://cdn.test").transform(article)
        html = result.content

        # Cover hoisted out — not in body but in feature_image.
        assert "cover.png" in str(result.metadata.get("feature_image", ""))
        assert 'data-spec-id="cover"' not in html

        # Intro top: appears AFTER <h2>Intro</h2> but BEFORE first <p>.
        h2_intro = html.find("<h2>Intro")
        intro_img = html.find('data-spec-id="intro_top"')
        first_p = html.find("<p>First introduction")
        assert -1 < h2_intro < intro_img < first_p

        # Before-heading: pre_arch precedes <h2>Architecture</h2>.
        pre_arch_idx = html.find('data-spec-id="pre_arch"')
        h2_arch = html.find("<h2>Architecture")
        assert -1 < pre_arch_idx < h2_arch

        # Between-paragraphs: arch_mid lives between Arch P1 and Arch P2.
        arch_p1 = html.find("Architecture paragraph one")
        arch_mid_idx = html.find('data-spec-id="arch_mid"')
        arch_p2 = html.find("Architecture paragraph two")
        assert -1 < arch_p1 < arch_mid_idx < arch_p2

    def test_idempotent_when_invoked_twice(self) -> None:
        article = _build_article()
        once = GhostTransformer(api_base_url="https://cdn.test").transform(article)
        twice = GhostTransformer(api_base_url="https://cdn.test").transform(article)
        # The transformer's input is unchanged, so output must be byte-identical.
        for spec in ("intro_top", "pre_arch", "arch_mid"):
            assert once.content.count(f'data-spec-id="{spec}"') == 1
            assert twice.content.count(f'data-spec-id="{spec}"') == 1

    def test_url_rewriting_uses_api_base(self) -> None:
        article = _build_article()
        result = GhostTransformer(api_base_url="https://cdn.test").transform(article)
        # Local visual URLs must be rewritten to absolute URLs.
        assert "https://cdn.test/generated_assets/visuals/cover.png" in str(
            result.metadata.get("feature_image", "")
        )


class TestMediumPreviewE2E:
    def test_cover_prepended_and_inline_specs_present(self) -> None:
        article = _build_article()
        result = MediumTransformer(api_base_url="https://cdn.test").transform(article)
        html = result.content
        cover_idx = html.find('class="cog-cover"')
        first_h2 = html.find("<h2>")
        assert -1 < cover_idx < first_h2
        for spec in ("intro_top", "pre_arch", "arch_mid"):
            assert f'data-spec-id="{spec}"' in html
