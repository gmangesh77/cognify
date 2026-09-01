"""Request-scoped prompt overrides (AUTHOR-012).

Endpoints that call the LLM outside a pipeline run (section rewrite /
regenerate, SEO regenerate, humanize preview + stream, topic analyze) load
the current overrides once per request and bind them around the service
call with `bind_prompt_overrides`. Binding is explicit in the handler
(not a `yield` dependency) so StreamingResponse bodies, which run after
dependency teardown, can bind inside their generator.
"""

from __future__ import annotations

from collections.abc import Mapping

import structlog
from fastapi import Request

logger = structlog.get_logger()


async def load_prompt_overrides(request: Request) -> Mapping[str, str]:
    repo = getattr(request.app.state, "prompt_override_repo", None)
    if repo is None:
        return {}
    try:
        return dict(await repo.load_all())
    except Exception as exc:  # noqa: BLE001
        logger.warning("prompt_overrides_unavailable", error=str(exc))
        return {}
