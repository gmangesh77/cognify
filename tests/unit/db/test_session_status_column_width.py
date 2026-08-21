"""Regression: every session status must fit `research_sessions.status`.

AUTHOR-002 introduced `awaiting_outline_review` (23 chars) while the column was
VARCHAR(20); unit tests run on `create_all` against SQLite, which does not
enforce lengths, so the gate only failed live against Postgres.
"""

from src.db.tables import ResearchSessionRow

KNOWN_SESSION_STATUSES = (
    "planning",
    "in_progress",
    "researching",
    "evaluating",
    "complete",
    "failed",
    "awaiting_outline_review",
    "generating_article",
    "article_complete",
    "article_failed",
    "cancelled",
)


def test_all_known_statuses_fit_the_column() -> None:
    length = ResearchSessionRow.__table__.c.status.type.length
    assert length is not None
    too_long = [s for s in KNOWN_SESSION_STATUSES if len(s) > length]
    assert too_long == [], f"status column is VARCHAR({length}); too long: {too_long}"
