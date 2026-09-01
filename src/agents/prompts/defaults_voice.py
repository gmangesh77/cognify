"""Persona voice prompts (AUTHOR-011). Editable in Settings → Prompts."""

from src.agents.prompts.registry import PromptTemplate, register

register(
    PromptTemplate(
        key="voice.block_intro",
        step="voice",
        description="Voice block: heading that introduces the measured targets.",
        template=(
            "Voice. Write in this author's measured voice. Treat each line as a "
            "target, not a hard rule; keep every factual claim and citation marker:"
        ),
        variables=frozenset(),
    ),
    PromptTemplate(
        key="voice.dim_line",
        step="voice",
        description="Voice block: one line per confident dimension.",
        template="{label}: aim for about {target} (typical range {low}–{high}).",
        variables=frozenset({"label", "target", "low", "high"}),
    ),
    PromptTemplate(
        key="voice.samples_intro",
        step="voice",
        description="Voice block: introduces the few-shot excerpts.",
        template="Match the register of these excerpts from the same author:",
        variables=frozenset(),
    ),
    PromptTemplate(
        key="voice.fix.system",
        step="voice",
        description="Voice fix pass: system role for rewriting one off-voice section.",
        template=(
            "You are an editor aligning one article section to a specific author's "
            "voice. Rewrite the prose so the named deviations are corrected. Keep "
            "every factual claim, every [N] citation marker, and every heading "
            "exactly as written. If the input contains the sentinel `<<<BLOCK>>>` "
            "between chunks, preserve every sentinel verbatim and rewrite each chunk "
            "in place — the output must contain exactly the same number of "
            "sentinels. Return plain markdown only — no commentary, no fences."
        ),
        variables=frozenset(),
    ),
    PromptTemplate(
        key="voice.fix.user",
        step="voice",
        description="Voice fix pass: voice block + deviations + the section prose.",
        template=(
            "{voice_block}\n\nDeviations to correct:\n{deviations}\n\n"
            "Section text:\n{section_text}"
        ),
        variables=frozenset({"voice_block", "deviations", "section_text"}),
    ),
)
