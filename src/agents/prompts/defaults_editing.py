"""Editing / topic-analysis default prompts (AUTHOR-012). Each `template` is
the literal that lived in the service module before the registry existed."""

from src.agents.prompts.registry import PromptTemplate, register

register(
    PromptTemplate(
        key="section_rewrite.system",
        step="section_rewrite",
        description="Section prose rewriter: system role",
        template=(  # verbatim from section_rewriter._REWRITER_SYSTEM
            "You are a senior editor refining the prose of one section of an "
            "article. You receive the section's current markdown and a "
            "natural-language instruction. Return ONLY the refined markdown — "
            "no commentary, no fences, no headings the original did not "
            "already contain. Preserve every existing `[N]` citation marker "
            "verbatim, every `data-spec-id` attribute verbatim, and every "
            "second-level heading (`## …`) verbatim."
        ),
        variables=frozenset(),
    ),
    PromptTemplate(
        key="section_rewrite.tone.shorter",
        step="section_rewrite",
        description="Tone preset: shorter",
        template=(  # verbatim from section_rewriter.TONE_PRESETS["shorter"]
            "Make this paragraph noticeably shorter without losing any factual "
            "claim. Cut hedging phrases, drop adverbs, and tighten sentence "
            "structure. Aim for ~30% fewer words."
        ),
        variables=frozenset(),
    ),
    PromptTemplate(
        key="section_rewrite.tone.more_concrete",
        step="section_rewrite",
        description="Tone preset: more_concrete",
        template=(  # verbatim from section_rewriter.TONE_PRESETS["more_concrete"]
            "Make this paragraph more concrete. Replace vague phrasing with "
            "specific examples that are already implied by the surrounding "
            "context. Do not invent new statistics, names, or quotes."
        ),
        variables=frozenset(),
    ),
    PromptTemplate(
        key="section_rewrite.tone.more_conversational",
        step="section_rewrite",
        description="Tone preset: more_conversational",
        template=(  # verbatim from section_rewriter.TONE_PRESETS["more_conversational"]
            "Soften this paragraph into a more conversational register. Trim "
            "jargon to one or two key terms; favour short sentences. Keep "
            "every factual claim and citation marker exactly as written."
        ),
        variables=frozenset(),
    ),
    PromptTemplate(
        key="section_rewrite.tone.more_authoritative",
        step="section_rewrite",
        description="Tone preset: more_authoritative",
        template=(  # verbatim from section_rewriter.TONE_PRESETS["more_authoritative"]
            "Tighten this paragraph into a more authoritative register. Lead "
            "each sentence with the subject of the claim. Cut hedging "
            "language. Keep every factual claim and citation marker exactly "
            "as written."
        ),
        variables=frozenset(),
    ),
    PromptTemplate(
        key="topic_analyze.system",
        step="topic_analyze",
        description="Topic analyzer: system role",
        template=(  # verbatim from topic_analyzer._SYSTEM_PROMPT
            "You are an expert content strategist. Given a topic title, suggest "
            "metadata for article generation. Return valid JSON only."
        ),
        variables=frozenset(),
    ),
    PromptTemplate(
        key="topic_analyze.full",
        step="topic_analyze",
        description="Topic analyzer: full metadata analysis",
        template=(  # verbatim from topic_analyzer._FULL_ANALYSIS_TEMPLATE
            "Analyze this topic and suggest article metadata:\n\n"
            "Title: {title}\n\n"
            "{domains_section}"
            "Return JSON with these fields:\n"
            '- "description": 1-2 sentence description of the topic\n'
            '- "domain": best-fit domain for this topic\n'
            '- "keywords": 3-5 keywords for research\n'
            '- "target_audience": who should read this article\n'
            '- "content_tone": one of {valid_tones}\n'
            '- "preferred_angle": suggested editorial angle'
        ),
        variables=frozenset({"title", "domains_section", "valid_tones"}),
    ),
    PromptTemplate(
        key="topic_analyze.regenerate",
        step="topic_analyze",
        description="Topic analyzer: regenerate a single field",
        template=(  # verbatim from topic_analyzer._REGENERATE_TEMPLATE
            "Regenerate ONLY the '{field}' field for this topic.\n\n"
            "Title: {title}\n\n"
            "Current values (keep all except {field}):\n"
            "{current_json}\n\n"
            "Return the full JSON with only '{field}' changed."
        ),
        variables=frozenset({"field", "title", "current_json"}),
    ),
)
