"""Shared anti-AI style constants for content generation prompts.

Derived from slop_phrases.py categories. Used by section_drafter,
outline_generator, humanizer, and seo_optimizer to prevent and
correct AI-sounding writing patterns.
"""

TONE_INSTRUCTIONS = (
    "WRITING STYLE RULES (mandatory):\n"
    "- Write short, direct sentences. Mix in occasional questions.\n"
    "- Vary sentence length between 5 and 25 words.\n"
    "- Use active voice. Be concrete: cite numbers, dates, tool names.\n"
    "- No em-dashes or en-dashes. Use commas or periods instead.\n"
    "- Never start three or more sentences with the same word.\n"
    "- Sound like a knowledgeable journalist, not an AI assistant."
)

ANTI_SLOP_RULES = (
    "FORBIDDEN PHRASES — do not use any of these or similar words:\n"
    "- Buzzwords: delve, leverage, cutting-edge, robust, seamless, "
    "holistic, innovative, transformative, streamline, harness, "
    "unlock, empower, synergy, paradigm, ecosystem, game-changer, "
    "and similar inflated tech jargon.\n"
    "- Transitions: moreover, furthermore, additionally, in conclusion, "
    "to summarize, ultimately, firstly, secondly, that being said, "
    "and similar formal connectors. Just start the next sentence.\n"
    "- Hedges: essentially, fundamentally, it is worth noting, "
    "interestingly, indeed, needless to say, arguably, it should be "
    "noted, and similar filler qualifiers.\n"
    "- Overblown adjectives: unprecedented, unparalleled, remarkable, "
    "groundbreaking, pivotal, paramount, impactful, mission-critical, "
    "and similar exaggeration.\n"
    "- Corporate jargon: stakeholder, bandwidth, low-hanging fruit, "
    "move the needle, pain point, value proposition, best practices, "
    "and similar business-speak.\n"
    "- Fluff: in today's world, ever-evolving, dynamic landscape, "
    "at the forefront, pave the way, when it comes to, myriad, "
    "plethora, multifaceted, nuanced, and similar padding.\n"
    "- Meta-references: in this article, key takeaway, comprehensive "
    "guide, to wrap up, in summary, and similar self-referential text.\n"
    "- AI openers: let me explain, here's the thing, let's unpack, "
    "and similar conversational AI starters."
)

STYLE_EXAMPLES = (
    "EXAMPLES of bad vs good writing:\n"
    "BAD: \"It is worth noting that this transformative approach "
    "leverages cutting-edge technology to deliver a seamless "
    "experience for stakeholders.\"\n"
    "GOOD: \"This approach uses recent NLP models and cut response "
    "times by 40% in Q3 2025 testing.\"\n\n"
    "BAD: \"Moreover, the unprecedented paradigm shift underscores "
    "the need for a holistic, end-to-end solution.\"\n"
    "GOOD: \"The shift from on-premise to cloud hosting forced three "
    "teams to rewrite their deployment scripts in two weeks.\""
)
