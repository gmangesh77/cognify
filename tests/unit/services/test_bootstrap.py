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
