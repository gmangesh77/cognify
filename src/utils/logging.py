import logging
from collections.abc import MutableMapping
from typing import Any

import structlog

SENSITIVE_KEYS: frozenset[str] = frozenset(
    {"password", "token", "secret", "api_key", "authorization", "encrypted_key"}
)

_REDACTED = "***REDACTED***"


def _filter_sensitive(
    logger: Any,
    method: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Redact sensitive fields from log event dicts before emission."""
    for key in SENSITIVE_KEYS:
        if key in event_dict:
            event_dict[key] = _REDACTED
    return event_dict


def setup_logging(debug: bool = False) -> None:
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        _filter_sensitive,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if debug:
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if debug else logging.INFO
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
