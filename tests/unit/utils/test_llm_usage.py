"""extract_usage — promoted from section_rewriter so drafter + rewriter share it."""

from langchain_core.messages import AIMessage

from src.utils.llm_usage import extract_usage


def test_reads_usage_metadata() -> None:
    msg = AIMessage(
        content="x",
        usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    )
    assert extract_usage(msg) == {"input": 10, "output": 5}


def test_falls_back_to_response_metadata_usage() -> None:
    msg = AIMessage(
        content="x",
        response_metadata={"usage": {"prompt_tokens": 7, "completion_tokens": 3}},
    )
    assert extract_usage(msg) == {"input": 7, "output": 3}


def test_unknown_shape_yields_nones() -> None:
    assert extract_usage(object()) == {"input": None, "output": None}
