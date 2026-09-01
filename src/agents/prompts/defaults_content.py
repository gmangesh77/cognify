"""Content-pipeline default prompts (AUTHOR-012). Each `template` is the
literal that lived in the generator module before the registry existed."""

from src.agents.prompts.registry import PromptTemplate, register

register(
    PromptTemplate(
        key="content_outline.system",
        step="content_outline",
        description="Outline generator: content-strategist system role + style rules.",
        template=(  # verbatim from outline_generator._SYSTEM_PROMPT
            "You are an expert content strategist. Generate a structured "
            "article outline from research findings. The outline should have "
            "sections with narrative flow: introduction, findings, "
            "analysis, and conclusion. Follow the section count and word "
            "budgets given in the requirements. "
            "Do not use em-dashes. Use periods or commas instead. "
            "Avoid formal transitions like moreover, furthermore, in conclusion. "
            "Write in a natural conversational tone. Vary sentence length. "
            "Be specific and concrete, not abstract. "
            "Respond with valid JSON only."
        ),
        variables=frozenset(),
    ),
    PromptTemplate(
        key="content_outline.user",
        step="content_outline",
        description="Outline generator: topic, findings, sizing requirements, schema.",
        template=(  # verbatim from outline_generator._USER_TEMPLATE
            "Generate an article outline for this topic:\n\n"
            "Title: {title}\n"
            "Description: {description}\n"
            "Domain: {domain}\n\n"
            "Research findings:\n{findings_summary}\n\n"
            "{requirements}\n"
            "Return JSON: {schema_hint}"
        ),
        variables=frozenset(
            {
                "title",
                "description",
                "domain",
                "findings_summary",
                "requirements",
                "schema_hint",
            }
        ),
    ),
    PromptTemplate(
        key="content_queries.system",
        step="content_queries",
        description="Retrieval-query generator: system role.",
        template=(  # verbatim from query_generator._SYSTEM_PROMPT
            "You are a research retrieval specialist. Given an article outline, "
            "generate 1-2 focused search queries per section for finding relevant "
            "passages in a knowledge base. Queries should be semantic and specific. "
            "Respond with valid JSON only."
        ),
        variables=frozenset(),
    ),
    PromptTemplate(
        key="content_queries.user",
        step="content_queries",
        description="Retrieval-query generator: sections + JSON shape.",
        template=(  # verbatim from query_generator._USER_TEMPLATE
            "Generate retrieval queries for each section:\n\n"
            "{sections_text}\n\n"
            "Return JSON array: "
            '[{{"section_index": 0, "queries": ["query1", "query2"]}}]'
        ),
        variables=frozenset({"sections_text"}),
    ),
    PromptTemplate(
        key="content_draft.system",
        step="content_draft",
        description=(
            "Section drafter: base system prompt "
            "(audience/tone lines are appended in code)."
        ),
        template=(  # verbatim from section_prompt.SYSTEM_PROMPT
            "You are an expert long-form writer. Draft a section of an article "
            "using the provided research context. Every factual claim must include "
            "an inline citation like [1], [2] referencing the numbered sources. "
            "Write in a clear, authoritative tone. Target approximately "
            "{target_word_count} words. "
            "Do not use em-dashes or en-dashes. Use periods or commas instead. "
            "Avoid words like delve, leverage, innovative, transformative, unprecedented. "  # noqa: E501
            "Skip transitions like moreover, furthermore, additionally. "
            "Vary sentence length and structure. "
            "Write in a natural voice as a knowledgeable human, not an AI assistant."
        ),
        variables=frozenset({"target_word_count"}),
    ),
    PromptTemplate(
        key="content_humanize.system",
        step="content_humanize",
        description="Humanizer rewrite pass: system role (sentinel contract).",
        template=(  # verbatim from humanizer._REWRITE_SYSTEM
            "You are an editor making AI-generated text sound natural. "
            "Rewrite the section to fix the listed issues. Keep all factual "
            "claims and [N] citations exactly as they are. Do not change the "
            "meaning. Only fix the writing style. "
            "If the input contains the sentinel `<<<BLOCK>>>` between chunks, "
            "preserve every sentinel verbatim and rewrite each chunk in place "
            "— the rewrite must contain exactly the same number of sentinels "
            "as the input."
        ),
        variables=frozenset(),
    ),
)
