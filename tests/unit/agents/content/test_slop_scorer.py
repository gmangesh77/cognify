"""Tests for slop scoring engine."""

from src.agents.content.slop_scorer import score_text
from src.models.content_pipeline import SlopScore


class TestScoreText:
    def test_clean_text_scores_high(self) -> None:
        text = (
            "Security researchers found that 40% of companies experienced "
            "a data breach in 2025. The team tested three different "
            "firewall configurations over six months. Results showed "
            "a 60% reduction in unauthorized access attempts. "
            "How did they achieve this?"
        )
        result = score_text(text)
        assert result.score >= 90
        assert result.rating == "HUMAN"

    def test_slop_heavy_text_scores_low(self) -> None:
        text = (
            "Let me delve into this transformative journey. "
            "Moreover, leverage cutting-edge solutions is crucial. "
            "This holistic approach empowers stakeholders to unlock "
            "unprecedented synergy. Furthermore, it's worth noting "
            "that this innovative paradigm shift is game-changing. "
            "In today's fast-paced landscape, we must harness "
            "robust and seamless best practices to streamline "
            "this groundbreaking ecosystem."
        )
        result = score_text(text)
        assert result.score < 50
        assert result.rating in ("LIKELY_AI", "PURE_SLOP")
        assert len(result.violations) > 5

    def test_phrase_matching_case_insensitive(self) -> None:
        text = "We must LEVERAGE this INNOVATIVE approach."
        result = score_text(text)
        phrases = [v.phrase for v in result.violations]
        assert "leverage" in phrases
        assert "innovative" in phrases

    def test_phrase_matching_whole_word(self) -> None:
        text = "The optimization of this system is important."
        result = score_text(text)
        # "optimize" should NOT match inside "optimization"
        phrases = [v.phrase for v in result.violations if v.phrase == "optimize"]
        assert len(phrases) == 0

    def test_structural_pattern_em_dash(self) -> None:
        text = "This concept \u2014 which is important \u2014 matters."
        result = score_text(text)
        patterns = [v.phrase for v in result.violations if v.category == "pattern"]
        assert "em_dash" in patterns

    def test_question_bonus(self) -> None:
        # Base text with a minor slop phrase to bring score below 95
        base = "This robust system handles security monitoring effectively."
        with_q = base + " What does this mean for the industry?"
        score_no_q = score_text(base).score
        score_with_q = score_text(with_q).score
        assert score_with_q >= score_no_q

    def test_sentence_variance_bonus(self) -> None:
        varied = "Security matters. The team discovered that implementing a comprehensive monitoring solution reduced incident response times by forty percent across all departments."
        monotonous = "Security is important now. Companies need to act now. Teams should prepare for this. Everyone must be aware now."
        assert score_text(varied).score >= score_text(monotonous).score

    def test_score_clamped_0_100(self) -> None:
        slop = " ".join(["delve leverage innovative transformative"] * 20)
        result = score_text(slop)
        assert result.score >= 0
        assert result.score <= 100

    def test_repetitive_openers_detected(self) -> None:
        text = (
            "The system is secure. The team tested it. "
            "The results were positive. The data shows improvement. "
            "The conclusion is clear."
        )
        result = score_text(text)
        openers = [v for v in result.violations if v.category == "repetitive_opener"]
        assert len(openers) > 0

    def test_passive_voice_density_penalty(self) -> None:
        text = (
            "The system was designed by the team. "
            "Features were added by developers. "
            "Tests were written by engineers. "
            "Code was reviewed by peers."
        )
        result = score_text(text)
        assert result.pattern_deductions > 0
