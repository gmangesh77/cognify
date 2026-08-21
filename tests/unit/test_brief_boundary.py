"""ADR-003/004 invariant: publishing never imports the Brief input contract."""

from pathlib import Path

PUBLISHING = Path("src/services/publishing")


def test_publishing_does_not_import_brief() -> None:
    offenders = [
        p
        for p in PUBLISHING.rglob("*.py")
        if "models.brief" in p.read_text(encoding="utf-8")
    ]
    assert offenders == []
