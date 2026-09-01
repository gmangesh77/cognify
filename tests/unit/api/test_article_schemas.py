"""Tests for article API schema converters."""

from datetime import UTC, datetime
from uuid import uuid4

from src.api.routers.canonical_articles import (
    _to_canonical_response,
    _to_image_response,
)
from src.models.content import (
    CanonicalArticle,
    ContentType,
    ImageAsset,
    Provenance,
    SEOMetadata,
)


class TestToImageResponse:
    def test_maps_basic_fields(self) -> None:
        asset = ImageAsset(
            url="/assets/diagram_1.png",
            caption="Auth flow overview.",
            alt_text="Auth Flow",
        )
        response = _to_image_response(asset)
        assert response.url == "/assets/diagram_1.png"
        assert response.caption == "Auth flow overview."
        assert response.alt_text == "Auth Flow"

    def test_preserves_mermaid_syntax_metadata(self) -> None:
        asset = ImageAsset(
            url="/assets/diagram_1.png",
            caption="Auth flow.",
            alt_text="Auth Flow",
            metadata={
                "diagram_type": "flowchart",
                "source_section": 0,
                "mermaid_syntax": "graph TD\n    A[Start] --> B[End]",
            },
        )
        response = _to_image_response(asset)
        assert response.metadata is not None
        assert response.metadata["diagram_type"] == "flowchart"
        assert response.metadata["source_section"] == 0
        assert (
            response.metadata["mermaid_syntax"] == "graph TD\n    A[Start] --> B[End]"
        )

    def test_empty_metadata_becomes_none(self) -> None:
        asset = ImageAsset(
            url="/assets/chart.png",
            caption="Chart",
            alt_text="Chart",
        )
        response = _to_image_response(asset)
        assert response.metadata is None

    def test_overview_section_index_preserved(self) -> None:
        asset = ImageAsset(
            url="/assets/overview.png",
            caption="System overview.",
            alt_text="System",
            metadata={
                "diagram_type": "flowchart",
                "source_section": -1,
                "mermaid_syntax": "graph LR\n    UI --> API --> DB",
            },
        )
        response = _to_image_response(asset)
        assert response.metadata is not None
        assert response.metadata["source_section"] == -1

    def test_relative_url_absolutified_when_api_base_given(self) -> None:
        asset = ImageAsset(
            url="generated_assets/charts/abc/img.png",
            caption="Chart",
            alt_text="Chart",
        )
        response = _to_image_response(asset, api_base_url="http://localhost:8000")
        assert (
            response.url == "http://localhost:8000/generated_assets/charts/abc/img.png"
        )

    def test_already_absolute_url_passes_through(self) -> None:
        asset = ImageAsset(
            url="https://cdn.example.com/img.png",
            caption="Hosted",
            alt_text="Hosted",
        )
        response = _to_image_response(asset, api_base_url="http://localhost:8000")
        assert response.url == "https://cdn.example.com/img.png"

    def test_omitting_api_base_preserves_url(self) -> None:
        """Backwards-compat: callers that don't pass api_base_url get raw URL."""
        asset = ImageAsset(
            url="generated_assets/charts/abc/img.png",
            caption="Chart",
            alt_text="Chart",
        )
        response = _to_image_response(asset)
        assert response.url == "generated_assets/charts/abc/img.png"


def _make_article(**overrides: object) -> CanonicalArticle:
    defaults: dict[str, object] = dict(
        title="Title",
        body_markdown="## Intro\n\nBody.\n",
        summary="Summary.",
        content_type=ContentType.ARTICLE,
        seo=SEOMetadata(title="T", description="D"),
        authors=["Cognify"],
        domain="cybersecurity",
        generated_at=datetime.now(UTC),
        provenance=Provenance(
            research_session_id=uuid4(),
            primary_model="claude-opus-4-5",
            drafting_model="claude-sonnet-4-5",
            embedding_model="all-MiniLM-L6-v2",
            embedding_version="1.0.0",
        ),
    )
    defaults.update(overrides)
    return CanonicalArticle(**defaults)


class TestToCanonicalResponseVoiceFields:
    """AUTHOR-011: audience_persona + voice fields must reach the API response."""

    def test_defaults_when_absent(self) -> None:
        article = _make_article()
        response = _to_canonical_response(article)
        assert response.audience_persona is None
        assert response.voice_persona_id is None
        assert response.voice_match_score is None
        assert response.voice_scores_by_section is None
        assert response.few_shot_sample_ids == []

    def test_maps_populated_voice_fields(self) -> None:
        persona_id = uuid4()
        sample_id = uuid4()
        article = _make_article(
            audience_persona="general_business",
            voice_persona_id=persona_id,
            voice_match_score=88,
            voice_scores_by_section={"0": 88},
            few_shot_sample_ids=[sample_id],
        )
        response = _to_canonical_response(article)
        assert response.audience_persona == "general_business"
        assert response.voice_persona_id == persona_id
        assert response.voice_match_score == 88
        assert response.voice_scores_by_section == {"0": 88}
        assert response.few_shot_sample_ids == [sample_id]
