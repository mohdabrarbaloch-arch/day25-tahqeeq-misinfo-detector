"""Tests for the text utilities.

Sentence splitting is where naive implementations quietly break: "Dr. Smith"
becomes two sentences, and every downstream rate is then computed against the
wrong denominator.
"""

from __future__ import annotations

from app.analysis.text import normalise, paragraphs, sentences, stats, strip_markup, words


def test_normalise_collapses_whitespace() -> None:
    assert normalise("a   b\t\tc") == "a b c"


def test_normalise_strips_zero_width_characters() -> None:
    assert normalise("he\u200bllo") == "hello"


def test_normalise_handles_empty_input() -> None:
    assert normalise("") == ""


def test_strip_markup_removes_tags_and_entities() -> None:
    assert strip_markup("<p>a &amp; b</p>") == "a & b"


def test_sentences_splits_on_terminators() -> None:
    assert len(sentences("One. Two. Three.")) == 3


def test_sentences_keeps_abbreviations_intact() -> None:
    result = sentences("Dr. Smith arrived at 9am. He was late.")
    assert len(result) == 2
    assert result[0].startswith("Dr. Smith")


def test_sentences_keeps_initials_intact() -> None:
    result = sentences("J. Ahmad spoke briefly. The room was quiet.")
    assert len(result) == 2


def test_sentences_handles_empty_input() -> None:
    assert sentences("") == []


def test_paragraphs_split_on_blank_lines() -> None:
    assert len(paragraphs("One.\n\nTwo.\n\nThree.")) == 3


def test_words_extracts_tokens_and_numbers() -> None:
    tokens = words("In 2026 there were 45 cases.")
    assert "2026" in tokens
    assert "45" in tokens


def test_stats_counts_caps_and_punctuation() -> None:
    result = stats("SHOCKING news!!! Really?")
    assert result.caps == 1
    assert result.exclamations == 3
    assert result.questions == 1


def test_stats_on_empty_text_is_all_zero() -> None:
    result = stats("")
    assert result.total == 0
    assert result.caps_ratio == 0.0
    assert result.avg_sentence_words == 0.0
