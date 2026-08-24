"""Settings for task dispatch (INFRA-007)."""

import pytest

from src.config.settings import Settings


class TestDispatchSettings:
    def test_defaults_preserve_inprocess_behaviour(self) -> None:
        s = Settings(_env_file=None)
        assert s.task_dispatch == "inprocess"
        assert s.redis_url == "redis://localhost:6379/0"
        assert s.celery_broker_url == ""
        assert s.celery_result_backend == ""

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COGNIFY_TASK_DISPATCH", "celery")
        monkeypatch.setenv("COGNIFY_REDIS_URL", "redis://redis:6379/0")
        s = Settings(_env_file=None)
        assert s.task_dispatch == "celery"
        assert s.redis_url == "redis://redis:6379/0"
