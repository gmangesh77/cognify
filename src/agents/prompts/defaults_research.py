"""Research-pipeline default prompts (AUTHOR-012). Each `template` is the
literal that lived in the agent module before the registry existed."""

from src.agents.prompts.registry import PromptTemplate, register

register(
    PromptTemplate(
        key="plan_research.system",
        step="plan_research",
        description="Research planner: system role / topic + context",
        template=(  # verbatim from planner._SYSTEM_PROMPT
            "You are a research planning assistant. Given a topic, generate a "
            "research plan with 3-5 facets. Each facet should cover a distinct "
            "angle of the topic.\n\n"
            "For each facet, set source_type to one of:\n"
            '- "web": current events, industry news, practical guides\n'
            '- "academic": research papers, methodologies, empirical studies\n'
            '- "both": topics needing both web and scholarly sources\n\n'
            "Respond with valid JSON only."
        ),
        variables=frozenset(),
    ),
    PromptTemplate(
        key="plan_research.user",
        step="plan_research",
        description="Research planner: system role / topic + context",
        template=(  # verbatim from planner._USER_TEMPLATE
            "Plan research for this topic:\n"
            "Title: {title}\n"
            "Description: {description}\n"
            "Domain: {domain}\n"
            "{context_block}\n"
            'Return JSON: {{"facets": [{{"index": 0, "title": "...", '
            '"description": "...", "search_queries": ["..."], '
            '"source_type": "web|academic|both"}}], '
            '"reasoning": "..."}}'
        ),
        variables=frozenset({"title", "description", "domain", "context_block"}),
    ),
    PromptTemplate(
        key="evaluate_completeness.system",
        step="evaluate_completeness",
        description="Completeness evaluator: system role / findings per facet",
        template=(  # verbatim from evaluator._SYSTEM_PROMPT
            "You are a research completeness evaluator. Given a topic and "
            "research findings, determine if the findings are sufficient for "
            "a comprehensive article. Respond with valid JSON only."
        ),
        variables=frozenset(),
    ),
    PromptTemplate(
        key="evaluate_completeness.user",
        step="evaluate_completeness",
        description="Completeness evaluator: system role / findings per facet",
        template=(  # verbatim from evaluator._USER_TEMPLATE
            "Topic: {title} ({domain})\n\n"
            "Findings per facet:\n{findings_summary}\n\n"
            "Are these findings sufficient? Identify weak facets by index.\n"
            'Return JSON: {{"is_complete": bool, "weak_facets": [int], '
            '"reasoning": "..."}}'
        ),
        variables=frozenset({"title", "domain", "findings_summary"}),
    ),
    PromptTemplate(
        key="research_web_claims.system",
        step="research_web_claims",
        description="Web-search claim extraction: system role / search snippets",
        template=(  # verbatim from web_search._CLAIMS_SYSTEM
            "You are a research analyst. Extract key factual claims "
            "and a brief summary from search results. Respond with JSON only."
        ),
        variables=frozenset(),
    ),
    PromptTemplate(
        key="research_web_claims.user",
        step="research_web_claims",
        description="Web-search claim extraction: system role / search snippets",
        template=(  # verbatim from web_search._CLAIMS_TEMPLATE
            "Search results about '{title}':\n\n{snippets}\n\n"
            "Extract 3-5 key factual claims and a 2-3 sentence summary.\n"
            'Return JSON: {{"claims": ["..."], "summary": "..."}}'
        ),
        variables=frozenset({"title", "snippets"}),
    ),
    PromptTemplate(
        key="research_literature_claims.system",
        step="research_literature_claims",
        description="Literature-review claim extraction: system role / paper abstracts",
        template=(  # verbatim from literature_review._CLAIMS_SYSTEM
            "You are an academic research analyst. Extract key factual claims "
            "and a summary from paper abstracts. Focus on methodology, findings, "
            "and statistical results. Respond with JSON only."
        ),
        variables=frozenset(),
    ),
    PromptTemplate(
        key="research_literature_claims.user",
        step="research_literature_claims",
        description="Literature-review claim extraction: system role / paper abstracts",
        template=(  # verbatim from literature_review._CLAIMS_TEMPLATE
            "Paper abstracts about '{title}':\n\n{abstracts}\n\n"
            "Extract 3-5 key factual claims (cite as Author et al. (year)) "
            "and a 2-3 sentence summary of research contributions.\n"
            'Return JSON: {{"claims": ["..."], "summary": "..."}}'
        ),
        variables=frozenset({"title", "abstracts"}),
    ),
)
