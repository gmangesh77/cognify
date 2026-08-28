"""Bootstrap factory (INFRA-007) — worker-reusable service construction.

Construction must be lazy: repos store the session factory and never touch
the DB until first use, so these tests pass a sentinel factory.
"""

from src.config.settings import Settings
from src.services.bootstrap import PipelineServices, build_pipeline_services
from src.services.content import ContentService
from src.services.content.outline_gate import OutlineGateService


class _FakeSessionFactory:
    """Sentinel; Pg repositories only store it until first query."""


async def test_no_anthropic_key_builds_noop_research_and_llmless_content() -> None:
    settings = Settings(_env_file=None, anthropic_api_key="")
    ps = await build_pipeline_services(
        settings,
        _FakeSessionFactory(),  # type: ignore[arg-type]
    )
    assert isinstance(ps, PipelineServices)
    assert ps.settings is settings
    assert ps.research_service is not None
    assert isinstance(ps.content_service, ContentService)
    assert isinstance(ps.outline_gate, OutlineGateService)


async def test_repos_are_bound_to_the_given_session_factory() -> None:
    settings = Settings(_env_file=None, anthropic_api_key="")
    sf = _FakeSessionFactory()
    ps = await build_pipeline_services(settings, sf)  # type: ignore[arg-type]
    assert ps.llm_call_repo._sf is sf
    assert ps.step_repo is not None
    assert ps.article_repo is not None
    assert ps.content_repos.drafts is not None


# ---------------------------------------------------------------------------
# AUTHOR-010 — model tiering builder
# ---------------------------------------------------------------------------
import pytest  # noqa: E402
import structlog.testing  # noqa: E402

from src.services.bootstrap_builders import _build_llm, build_tiered_llm  # noqa: E402
from src.utils.tiered_llm import TieredChatModel  # noqa: E402
from src.utils.tracked_llm import TrackedChatModel  # noqa: E402


def _default_model() -> str:
    return Settings(_env_file=None).anthropic_model


class TestModelTiering:
    def test_setting_parses_json_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(
            "COGNIFY_LLM_MODEL_BY_STEP", '{"content_queries": "claude-haiku-4-5"}'
        )
        settings = Settings(_env_file=None)
        assert settings.llm_model_by_step == {"content_queries": "claude-haiku-4-5"}

    def test_empty_map_builds_plain_model(self) -> None:
        settings = Settings(_env_file=None, anthropic_api_key="k")
        llm = build_tiered_llm(settings)
        assert not isinstance(llm, TieredChatModel)
        assert llm.model == settings.anthropic_model

    def test_map_builds_tiered_model_sharing_instances(self) -> None:
        settings = Settings(
            _env_file=None,
            anthropic_api_key="k",
            llm_model_by_step={
                "content_queries": "claude-haiku-4-5",
                "content_validate": "claude-haiku-4-5",
                "content_draft": _default_model(),
            },
        )
        llm = build_tiered_llm(settings)
        assert isinstance(llm, TieredChatModel)
        assert llm.by_step["content_queries"] is llm.by_step["content_validate"]
        assert llm.by_step["content_draft"] is llm.default
        assert llm.default.model == settings.anthropic_model

    def test_unknown_step_is_warned_but_kept(self) -> None:
        settings = Settings(
            _env_file=None,
            anthropic_api_key="k",
            llm_model_by_step={"nope": "claude-haiku-4-5"},
        )
        with structlog.testing.capture_logs() as logs:
            llm = build_tiered_llm(settings)
        assert isinstance(llm, TieredChatModel) and "nope" in llm.by_step
        assert any(log["event"] == "llm_tiering_unknown_step" for log in logs)

    def test_build_llm_wraps_tiered_in_tracker(self) -> None:
        settings = Settings(
            _env_file=None,
            anthropic_api_key="k",
            llm_model_by_step={"content_queries": "claude-haiku-4-5"},
        )
        llm = _build_llm(settings, llm_call_repo=object())
        assert isinstance(llm, TrackedChatModel)
        assert isinstance(llm.inner, TieredChatModel)
