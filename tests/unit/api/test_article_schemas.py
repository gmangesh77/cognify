"""Tests for article API schema converters."""

from src.api.routers.canonical_articles import _to_image_response
from src.models.content import ImageAsset


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
