"""Celery application for the Cognify worker (INFRA-007).

Started by the worker container as:
    celery -A src.tasks.celery_app worker --loglevel=info
"""

from __future__ import annotations

from celery import Celery

from src.config.settings import Settings


def make_celery(settings: Settings) -> Celery:
    """Build a Celery app from settings (broker/backend default to redis_url)."""
    broker = settings.celery_broker_url or settings.redis_url
    backend = settings.celery_result_backend or settings.redis_url
    app = Celery("cognify", broker=broker, backend=backend)
    app.conf.update(
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        task_track_started=True,
    )
    return app


# Module-level app for the `celery -A src.tasks.celery_app` CLI and for
# task registration (src.tasks.pipeline_tasks imports it). The worker
# process reads broker config from the environment via Settings().
celery_app = make_celery(Settings())

# Register tasks on import of the app module (celery CLI autodiscovers
# nothing by default; an explicit import keeps it obvious).
from src.tasks import pipeline_tasks  # noqa: E402,F401

__all__ = ["celery_app", "make_celery"]
