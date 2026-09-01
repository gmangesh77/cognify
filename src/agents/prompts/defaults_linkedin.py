"""LinkedIn repurpose default prompts (AUTHOR-013, L-014).

Turns a CanonicalArticle into a standalone LinkedIn post: hook + 3 beats +
CTA + hashtags. Registered under the `linkedin_repurpose` step so an admin
can override the tone/structure without touching the repurpose service.
"""

from src.agents.prompts.registry import PromptTemplate, register

register(
    PromptTemplate(
        key="linkedin_repurpose.system",
        step="linkedin_repurpose",
        description="LinkedIn repurpose: system role",
        template=(
            "You are a senior social editor turning an article into a "
            "standalone LinkedIn post. Return JSON only, no markdown "
            "fences, no commentary, with this exact shape:\n"
            '{"hook": str, "beats": [str, str, str], "cta": str, '
            '"hashtags": [str]}\n\n'
            "Rules:\n"
            "- hook: one attention-grabbing opening line, at most 200 "
            "characters.\n"
            "- beats: exactly three, each 1-2 sentences, each expanding "
            "one concrete point from the article.\n"
            "- cta: one sentence that invites the reader to read the "
            "full article.\n"
            "- hashtags: 3-5 topical hashtags, lowercase words only, "
            "without the leading '#'.\n"
            "- No em-dashes. No 'In today's world' or similar generic "
            "openers. No emojis unless the article itself uses them.\n"
            "- Keep every fact, statistic, and claim exactly as stated "
            "in the article. Never invent a new number, name, or date."
        ),
        variables=frozenset(),
    ),
    PromptTemplate(
        key="linkedin_repurpose.user",
        step="linkedin_repurpose",
        description="LinkedIn repurpose: article context",
        template=(
            "Article title: {title}\n"
            "Summary: {summary}\n"
            "Key claims:\n{key_claims}\n"
            "{instruction}\n"
            "Return JSON only."
        ),
        variables=frozenset({"title", "summary", "key_claims", "instruction"}),
    ),
    PromptTemplate(
        key="linkedin_repurpose.shorter",
        step="linkedin_repurpose",
        description="LinkedIn repurpose: retry suffix when over the char limit",
        template=(
            "The previous draft was too long. Keep the total under 2,600 characters."
        ),
        variables=frozenset(),
    ),
)
