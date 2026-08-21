"""AUTHOR-004 boundary guards: regenerate path is graph-free and publishing-free."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGEN_FILES = [
    ROOT / "src/agents/content/section_prompt.py",
    ROOT / "src/services/content/section_history_contracts.py",
    ROOT / "src/services/content/section_regenerate.py",
    ROOT / "src/services/content/section_regenerate_models.py",
    ROOT / "src/services/content/section_regenerate_text.py",
    ROOT / "src/api/routers/content_shared.py",
    ROOT / "src/api/routers/content_regenerate.py",
]


def test_regenerate_modules_exist() -> None:
    missing = [p for p in REGEN_FILES if not p.exists()]
    assert missing == []


def test_regenerate_modules_do_not_import_langgraph_or_nodes() -> None:
    for path in REGEN_FILES:
        text = path.read_text(encoding="utf-8")
        assert "langgraph" not in text, path
        assert "agents.content.nodes" not in text, path
        assert "agents.content.pipeline" not in text, path
        assert "build_content_graph" not in text, path


def test_regenerate_modules_do_not_import_publishing() -> None:
    for path in REGEN_FILES:
        assert "services.publishing" not in path.read_text(encoding="utf-8"), path
