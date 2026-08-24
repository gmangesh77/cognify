"""Tests for src/services/usage.py — AUTHOR-005 pricing math."""

from datetime import UTC, datetime
from uuid import uuid4

from src.models.content import ImageAsset
from src.models.llm_call import LlmCall
from src.services.usage import (
    DEFAULT_LLM_PRICING,
    SessionUsage,
    compute_session_usage,
    effective_pricing,
    resolve_model_pricing,
)

_SESSION = uuid4()


def _call(
    op: str = "content_draft",
    model: str = "claude-sonnet-4-6",
    tokens: tuple[int | None, int | None] = (1000, 500),
) -> LlmCall:
    return LlmCall(
        session_id=_SESSION,
        call_name=op,
        model_name=model,
        input_tokens=tokens[0],
        output_tokens=tokens[1],
        started_at=datetime.now(UTC),
    )


def _visual(cost: float | None = 0.04, provider: str | None = "openai") -> ImageAsset:
    meta: dict[str, str | int | float | None] = {"spec_id": "s1"}
    if provider is not None:
        meta["provider"] = provider
    if cost is not None:
        meta["cost_usd"] = cost
    return ImageAsset(url="http://x/i.png", metadata=meta)


_PRICING = {"claude-sonnet": {"input_per_mtok": 3.0, "output_per_mtok": 15.0}}


class TestResolveModelPricing:
    def test_exact_match_wins(self) -> None:
        pricing = {"claude-sonnet-4-6": {"input_per_mtok": 9.0, "output_per_mtok": 9.0}}
        assert (
            resolve_model_pricing("claude-sonnet-4-6", pricing)
            == pricing["claude-sonnet-4-6"]
        )

    def test_longest_prefix_match(self) -> None:
        pricing = {
            "claude": {"input_per_mtok": 1.0, "output_per_mtok": 1.0},
            "claude-sonnet": {"input_per_mtok": 3.0, "output_per_mtok": 15.0},
        }
        assert (
            resolve_model_pricing("claude-sonnet-4-6", pricing)["input_per_mtok"] == 3.0
        )

    def test_unknown_model_returns_none(self) -> None:
        assert resolve_model_pricing("gpt-5", _PRICING) is None


class TestEffectivePricing:
    def test_overrides_merge_over_defaults(self) -> None:
        merged = effective_pricing(
            {"claude-sonnet": {"input_per_mtok": 1.0, "output_per_mtok": 2.0}}
        )
        assert merged["claude-sonnet"]["input_per_mtok"] == 1.0
        assert "claude-haiku" in merged

    def test_empty_overrides_yield_defaults(self) -> None:
        assert effective_pricing({}) == DEFAULT_LLM_PRICING


class TestComputeSessionUsage:
    def test_empty_inputs_zero_usage(self) -> None:
        usage = compute_session_usage([], [], _PRICING)
        assert usage == SessionUsage(0, 0, 0, 0, 0.0, ())

    def test_token_cost_hand_computed(self) -> None:
        # 1000 in @ $3/M + 500 out @ $15/M = 0.003 + 0.0075 = 0.0105
        usage = compute_session_usage([_call()], [], _PRICING)
        assert usage.llm_calls == 1
        assert usage.input_tokens == 1000
        assert usage.output_tokens == 500
        assert usage.cost_usd == 0.0105

    def test_none_tokens_counted_as_zero(self) -> None:
        usage = compute_session_usage([_call(tokens=(None, None))], [], _PRICING)
        assert usage.llm_calls == 1
        assert usage.input_tokens == 0
        assert usage.cost_usd == 0.0

    def test_unknown_model_costs_zero_but_counts(self) -> None:
        usage = compute_session_usage([_call(model="mystery")], [], _PRICING)
        assert usage.llm_calls == 1
        assert usage.input_tokens == 1000
        assert usage.cost_usd == 0.0

    def test_by_operation_groups_and_orders_by_cost(self) -> None:
        calls = [
            _call(op="content_draft"),
            _call(op="content_draft"),
            _call(op="section_regenerate", tokens=(100, 50)),
        ]
        usage = compute_session_usage(calls, [], _PRICING)
        ops = {o.op: o for o in usage.by_operation}
        assert ops["content_draft"].llm_calls == 2
        assert ops["content_draft"].input_tokens == 2000
        assert ops["section_regenerate"].cost_usd == 0.00105
        assert usage.by_operation[0].op == "content_draft"  # most expensive first

    def test_images_counted_and_costed_from_metadata(self) -> None:
        usage = compute_session_usage([], [_visual(0.04), _visual(0.001)], _PRICING)
        assert usage.images == 2
        assert usage.cost_usd == 0.041
        ops = {o.op: o for o in usage.by_operation}
        assert ops["images"].cost_usd == 0.041
        assert ops["images"].llm_calls == 0

    def test_mermaid_asset_free_but_counted(self) -> None:
        usage = compute_session_usage(
            [], [_visual(cost=None, provider="mermaid")], _PRICING
        )
        assert usage.images == 1
        assert usage.cost_usd == 0.0

    def test_total_is_tokens_plus_images(self) -> None:
        usage = compute_session_usage([_call()], [_visual(0.04)], _PRICING)
        assert usage.cost_usd == 0.0505

    def test_default_pricing_covers_sonnet_and_haiku(self) -> None:
        assert (
            resolve_model_pricing("claude-sonnet-4-6", DEFAULT_LLM_PRICING) is not None
        )
        assert (
            resolve_model_pricing("claude-haiku-4-5-20251001", DEFAULT_LLM_PRICING)
            is not None
        )
