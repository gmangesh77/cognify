"""Session/article usage roll-up (AUTHOR-005).

Pure math: ``llm_calls`` rows are priced by a model-prefix pricing map;
image cost comes from the real per-asset ``metadata.cost_usd`` recorded at
render time (see ``services/visuals/cost.py``) — never from settings, so
the badge always reflects what was actually charged.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.models.content import ImageAsset
from src.models.llm_call import LlmCall
from src.services.visuals.cost import aggregate_cost

DEFAULT_LLM_PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet": {"input_per_mtok": 3.0, "output_per_mtok": 15.0},
    "claude-haiku": {"input_per_mtok": 1.0, "output_per_mtok": 5.0},
    "claude-opus": {"input_per_mtok": 15.0, "output_per_mtok": 75.0},
}

_IMAGES_OP = "images"


@dataclass(frozen=True)
class OperationUsage:
    """Cost roll-up for one pipeline operation (``llm_calls.call_name``)."""

    op: str
    llm_calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float


@dataclass(frozen=True)
class SessionUsage:
    """Total usage for one research session."""

    llm_calls: int
    input_tokens: int
    output_tokens: int
    images: int
    cost_usd: float
    by_operation: tuple[OperationUsage, ...]


def resolve_model_pricing(
    model_name: str, pricing: dict[str, dict[str, float]]
) -> dict[str, float] | None:
    """Exact match first, then the longest key that prefixes ``model_name``."""
    if model_name in pricing:
        return pricing[model_name]
    matches = [key for key in pricing if model_name.startswith(key)]
    if not matches:
        return None
    return pricing[max(matches, key=len)]


def effective_pricing(
    overrides: dict[str, dict[str, float]],
) -> dict[str, dict[str, float]]:
    """``DEFAULT_LLM_PRICING`` with per-key overrides from settings."""
    return {**DEFAULT_LLM_PRICING, **overrides}


def _call_cost(call: LlmCall, pricing: dict[str, dict[str, float]]) -> float:
    rates = resolve_model_pricing(call.model_name, pricing)
    if rates is None:
        return 0.0
    input_usd = (call.input_tokens or 0) * rates.get("input_per_mtok", 0.0) / 1_000_000
    output_usd = (
        (call.output_tokens or 0) * rates.get("output_per_mtok", 0.0) / 1_000_000
    )
    return input_usd + output_usd


def _op_rollup(
    calls: list[LlmCall], pricing: dict[str, dict[str, float]]
) -> list[OperationUsage]:
    grouped: dict[str, list[LlmCall]] = {}
    for call in calls:
        grouped.setdefault(call.call_name, []).append(call)
    return [
        OperationUsage(
            op=op,
            llm_calls=len(group),
            input_tokens=sum(c.input_tokens or 0 for c in group),
            output_tokens=sum(c.output_tokens or 0 for c in group),
            cost_usd=round(sum(_call_cost(c, pricing) for c in group), 6),
        )
        for op, group in grouped.items()
    ]


def compute_session_usage(
    calls: list[LlmCall],
    visuals: list[ImageAsset],
    pricing: dict[str, dict[str, float]],
) -> SessionUsage:
    """Roll up token + image cost for one session. Pure — no I/O."""
    ops = _op_rollup(calls, pricing)
    # Legacy pre-VISUAL-005 assets carry no `provider` metadata and are
    # excluded from image_count/cost by aggregate_cost.
    image_cost = aggregate_cost(visuals)
    if image_cost.image_count > 0:
        ops.append(OperationUsage(_IMAGES_OP, 0, 0, 0, round(image_cost.total_usd, 6)))
    ops.sort(key=lambda o: o.cost_usd, reverse=True)
    return SessionUsage(
        llm_calls=len(calls),
        input_tokens=sum(c.input_tokens or 0 for c in calls),
        output_tokens=sum(c.output_tokens or 0 for c in calls),
        images=image_cost.image_count,
        cost_usd=round(sum(o.cost_usd for o in ops), 6),
        by_operation=tuple(ops),
    )


__all__ = [
    "DEFAULT_LLM_PRICING",
    "OperationUsage",
    "SessionUsage",
    "compute_session_usage",
    "effective_pricing",
    "resolve_model_pricing",
]
