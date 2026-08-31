"""Content-pipeline default prompts, continued (AUTHOR-012).

Split out of `defaults_content.py` to stay under the 200-line file budget.
Imported for its registration side effect from `defaults_content.py`.
"""

from src.agents.prompts.registry import PromptTemplate, register

register(
    PromptTemplate(
        key="content_seo.system",
        step="content_seo",
        description="SEO metadata: system role + JSON shape.",
        template=(  # verbatim from seo_optimizer._SEO_SYSTEM
            "You are an SEO specialist. Generate SEO metadata for an article. "
            "Respond with valid JSON only: "
            '{"title": "50-60 char", "description": "150-160 char", '
            '"keywords": ["keyword1", "keyword2"]}'
        ),
        variables=frozenset(),
    ),
    PromptTemplate(
        key="content_seo.user",
        step="content_seo",
        description="SEO metadata: title + body excerpt.",
        template=(  # verbatim from seo_optimizer._SEO_USER
            "Generate SEO metadata for this article:\n\n"
            "Title: {title}\n"
            "Body (excerpt): {body_excerpt}\n\n"
            "Requirements: title 50-60 chars, description 150-160 chars, "
            "5-10 keywords. Return JSON only."
        ),
        variables=frozenset({"title", "body_excerpt"}),
    ),
    PromptTemplate(
        key="content_discover.system",
        step="content_discover",
        description="AI discoverability: summary + key claims system role.",
        template=(  # verbatim from seo_optimizer._DISCOVER_SYSTEM
            "You are a content analyst. Extract a concise summary (1-2 sentences, "
            "under 500 chars) and 3-5 key factual claims with citation references. "
            "Respond with valid JSON only: "
            '{"summary": "...", "key_claims": ["claim [1]", "claim [2]"]}'
        ),
        variables=frozenset(),
    ),
    PromptTemplate(
        key="content_discover.user",
        step="content_discover",
        description="AI discoverability: sections + citations.",
        template=(  # verbatim from seo_optimizer._DISCOVER_USER
            "Extract summary and key claims from this article:\n\n"
            "{sections_text}\n\n"
            "Citations available: {citations_text}\n"
            "Return JSON only."
        ),
        variables=frozenset({"sections_text", "citations_text"}),
    ),
    PromptTemplate(
        key="content_charts.prompt",
        step="content_charts",
        description="Chart proposals from section drafts (single-turn prompt).",
        template=(  # verbatim from chart_generator._PROMPT_TEMPLATE
            "You are a data visualization expert. "
            "Read the article sections below and propose 0-3 data charts.\n\n"
            "For each chart, provide:\n"
            '- chart_type: "bar", "line", or "pie"\n'
            "- title: chart title (max 120 chars)\n"
            "- x_labels: category labels or x-axis points\n"
            "- y_values: numeric values corresponding to each label\n"
            "- y_label: y-axis label\n"
            "- caption: one-sentence description for the article\n"
            "- source_section_index: which section (0-indexed) the data comes from\n\n"
            "Only propose charts where concrete numerical data exists. "
            "Return an empty array [] if no chartable data is found.\n\n"
            "Return ONLY a JSON array. No explanation.\n\n"
            "## Article Sections\n{sections_text}"
        ),
        variables=frozenset({"sections_text"}),
    ),
    PromptTemplate(
        key="content_diagrams.prompt",
        step="content_diagrams",
        description="Diagram proposals from section drafts (single-turn prompt).",
        template=(  # verbatim from diagram_generator._PROMPT_TEMPLATE
            "You are a technical diagram expert. Read the article sections below and "
            "decide which diagrams (if any) would make the prose clearer and more "
            "impactful. Draw diagrams ONLY when they clarify a concept the text "
            "already describes -- never force a diagram onto text that does not call "
            "for one.\n\n"
            "Supported types (pick the one that best fits the concept):\n"
            "- flowchart: decision trees, process flows, pipelines, branching logic\n"
            "- sequence: request/response and message exchanges between actors\n"
            "- class: data models, class hierarchies, component relationships\n"
            "- state: state machines, lifecycles, status transitions\n"
            "- er: entity-relationship / database schema\n"
            "- journey: step-by-step user journeys or experience maps\n\n"
            "For each diagram, provide:\n"
            "- diagram_type: one of the types listed above\n"
            "- title: concise diagram title (max 120 chars)\n"
            "- mermaid_syntax: valid Mermaid code for the chosen type\n"
            "- caption: one-sentence description for the article\n"
            "- source_section_index: the 0-indexed section this diagram illustrates. "
            "Use -1 for an article-level overview / high-level architecture diagram "
            "(it will render above the article body).\n\n"
            "Guidance on count: prefer 0 diagrams over a forced diagram. If the "
            "article warrants it, include a high-level overview (section_index = -1) "
            "plus a handful of per-section diagrams where they add genuine value. "
            "Do not exceed 5 total.\n\n"
            "Return ONLY a JSON array. Empty array [] if nothing is diagrammable. "
            "No prose, no markdown fences, no explanation.\n\n"
            "## Article Sections\n{sections_text}"
        ),
        variables=frozenset({"sections_text"}),
    ),
)
