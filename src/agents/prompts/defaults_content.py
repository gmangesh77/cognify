"""Content-pipeline default prompts (AUTHOR-012)."""

from src.agents.prompts.registry import PromptTemplate, register

register(
    PromptTemplate(
        key="content_queries.system",
        step="content_queries",
        description="Retrieval-query generator: system role.",
        template=(
            "You are a research retrieval specialist. Respond with valid JSON only."
        ),
        variables=frozenset(),
    ),
    PromptTemplate(
        key="content_queries.user",
        step="content_queries",
        description="Retrieval-query generator: sections to query for.",
        template="Generate retrieval queries for each section:\n\n{sections_text}",
        variables=frozenset({"sections_text"}),
    ),
)
