"""Tests for the scoring engine.

These are the tests that matter most: the engine is the product. They assert
behaviour that would be a real bug if it changed — separation between clean and
misleading text, the exclusion of inapplicable signals, and the fact that a
single damning signal cannot be averaged away.
"""

from __future__ import annotations

import pytest
from app.analysis.scoring import analyse

CLEAN = (
    "Pakistan's central bank held its policy rate at 11 percent on Monday, citing "
    "easing inflation.\n\n"
    "The State Bank of Pakistan said in a statement that inflation had slowed to 4.9 "
    'percent in October from 6.2 percent a month earlier. "We expect inflation to '
    'remain within the target range over the coming quarters," Governor Jameel Ahmad '
    "told reporters in Karachi.\n\n"
    "According to the bank's monetary policy report published on 10 November 2026, "
    "food prices rose 3.1 percent while core inflation held at 7.4 percent. Analysts "
    "at Topline Securities said the decision was widely expected.\n\n"
    "The next policy meeting is scheduled for 15 December 2026."
)

MISLEADING = (
    "SHOCKING!!! They don't want you to know the REAL truth about what happened in "
    "Karachi last night!!!\n\n"
    "A friend of a senior official has revealed that a MASSIVE cover-up is underway. "
    "Sources say that thousands of people were affected but the mainstream media "
    "won't report it. This is UNDENIABLE proof that the deep state is hiding "
    "everything from you.\n\n"
    "Experts say this is the biggest scandal in the country's history and nobody is "
    "talking about it. The government has completely destroyed the evidence. It is "
    "being reported that the real number is in the millions.\n\n"
    "SHARE THIS BEFORE THEY DELETE IT!!! Forward to everyone you know. Do your own "
    "research. Wake up before it's too late!"
)


def test_clean_report_scores_high() -> None:
    result = analyse(CLEAN, url="https://www.dawn.com/news/1234567")
    assert result.score >= 85, result.score
    assert result.verdict == "credible"


def test_misleading_text_scores_low() -> None:
    result = analyse(MISLEADING)
    assert result.score <= 30, result.score
    assert result.verdict in {"questionable", "unreliable"}


def test_clean_scores_above_misleading_by_a_wide_margin() -> None:
    clean = analyse(CLEAN, url="https://www.dawn.com/news/1234567")
    bad = analyse(MISLEADING)
    assert clean.score - bad.score >= 50


def test_every_signal_is_reported() -> None:
    result = analyse(MISLEADING)
    assert len(result.signals) == 11
    assert {s.id for s in result.signals} == {
        "sensationalism",
        "absolute_certainty",
        "attribution",
        "anonymous_sourcing",
        "vague_quantities",
        "clickbait_headline",
        "conspiracy_markers",
        "share_pressure",
        "forward_markers",
        "quote_integrity",
        "structure",
    }


def test_share_pressure_is_detected_with_evidence() -> None:
    result = analyse(MISLEADING)
    signal = next(s for s in result.signals if s.id == "share_pressure")
    assert signal.severity > 0.5
    assert signal.evidence
    assert any("share" in item.lower() for item in signal.evidence)


def test_conspiracy_framing_is_detected() -> None:
    result = analyse(MISLEADING)
    signal = next(s for s in result.signals if s.id == "conspiracy_markers")
    assert signal.severity >= 0.5


def test_short_text_skips_signals_instead_of_scoring_them_clean() -> None:
    """A 25-word snippet cannot be judged on attribution, so it must be excluded."""
    result = analyse("The council met on Tuesday to discuss the budget for next year.")
    attribution = next(s for s in result.signals if s.id == "attribution")
    assert attribution.applicable is False
    assert result.confidence < 0.8


def test_short_text_is_flagged_as_provisional() -> None:
    result = analyse("A short note about something that happened yesterday evening.")
    assert any("provisional" in note.lower() for note in result.notes)


def test_one_damning_signal_cannot_be_averaged_away() -> None:
    """Ten clean signals must not rescue a text that says 'share before they delete it'."""
    text = (
        "The ministry published its quarterly report on 12 November 2026. "
        'According to the report, spending rose 4.2 percent. "The figures are '
        'preliminary," said a spokesperson for the ministry. Analysts at a local '
        "firm said the number was in line with expectations. The report is available "
        "online. https://example.com/report "
        "SHARE THIS BEFORE THEY DELETE IT!!!"
    )
    result = analyse(text)
    assert result.score < 80, result.score


def test_score_is_never_a_hundred() -> None:
    """No automated style check should claim certainty."""
    result = analyse(CLEAN, url="https://www.reuters.com/world/example")
    assert result.score <= 98.0


def test_high_score_carries_an_explicit_caveat() -> None:
    result = analyse(CLEAN, url="https://www.dawn.com/news/1234567")
    assert any("not mean the claims are true" in note for note in result.notes)


def test_empty_text_is_rejected() -> None:
    with pytest.raises(ValueError):
        analyse("   ")


def test_confidence_rises_with_length() -> None:
    short = analyse("The committee met briefly on Monday morning to review the plan.")
    long = analyse(CLEAN, url="https://www.dawn.com/news/1234567")
    assert long.confidence > short.confidence


def test_known_outlet_raises_the_score() -> None:
    with_outlet = analyse(CLEAN, url="https://www.reuters.com/world/example")
    without = analyse(CLEAN)
    assert with_outlet.score >= without.score


def test_unknown_domain_is_not_punished_hard() -> None:
    """Not knowing a domain is not evidence against it."""
    result = analyse(CLEAN, url="https://some-unknown-outlet.com/story")
    assert result.score >= 80
    assert result.domain is not None
    assert result.domain.known is False


def test_shortener_is_flagged() -> None:
    result = analyse(CLEAN, url="https://bit.ly/abc123")
    assert result.domain is not None
    assert result.domain.is_shortener is True


def test_headline_is_taken_from_first_line_when_not_supplied() -> None:
    result = analyse(MISLEADING)
    assert result.headline.startswith("SHOCKING")


def test_explicit_headline_overrides_first_line() -> None:
    result = analyse(MISLEADING, headline="A measured headline")
    assert result.headline == "A measured headline"


def test_html_markup_is_stripped_before_analysis() -> None:
    result = analyse(f"<p>{CLEAN}</p><script>alert(1)</script>")
    assert "alert(1)" not in result.headline
    assert result.word_count > 50
