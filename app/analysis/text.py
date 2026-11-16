"""Text normalisation and the small amount of linguistics this project needs.

Deliberately dependency-free: no spaCy, no nltk downloads. Every signal in
Tahqeeq is lexical or structural, so a tokeniser and a sentence splitter are
enough — and keeping them here means the whole analysis runs offline in
milliseconds with no model to fetch.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff\u2060"), None)
_WS = re.compile(r"[ \t\u00a0]+")
_MULTI_NL = re.compile(r"\n{3,}")
_TAG = re.compile(r"<[^>]{1,200}>")

# Tokens that end in a period but do not end a sentence.
_ABBREV = frozenset(
    {
        "mr",
        "mrs",
        "ms",
        "dr",
        "prof",
        "sr",
        "jr",
        "st",
        "vs",
        "etc",
        "inc",
        "ltd",
        "co",
        "corp",
        "gov",
        "sen",
        "rep",
        "gen",
        "col",
        "capt",
        "lt",
        "no",
        "vol",
        "fig",
        "approx",
        "dept",
        "univ",
        "est",
        "jan",
        "feb",
        "mar",
        "apr",
        "jun",
        "jul",
        "aug",
        "sep",
        "sept",
        "oct",
        "nov",
        "dec",
        "mon",
        "tue",
        "wed",
        "thu",
        "fri",
        "sat",
        "sun",
    }
)

_WORD = re.compile(r"[A-Za-z][A-Za-z'\u2019\-]*|\d+(?:[.,]\d+)*")
_SENT_END = re.compile(r"(?<=[.!?])[\"'\u201d\u2019)\]]*\s+")
_ABBREV_TAIL = re.compile(r"([A-Za-z]+)\.$")


def normalise(text: str) -> str:
    """Unicode-normalise, strip zero-width characters, collapse whitespace."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text).translate(_ZERO_WIDTH)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WS.sub(" ", text)
    text = _MULTI_NL.sub("\n\n", text)
    return text.strip()


def strip_markup(text: str) -> str:
    """Remove HTML tags and decode the handful of entities that matter here."""
    text = _TAG.sub(" ", text)
    for entity, char in (
        ("&nbsp;", " "),
        ("&amp;", "&"),
        ("&lt;", "<"),
        ("&gt;", ">"),
        ("&quot;", '"'),
        ("&#39;", "'"),
    ):
        text = text.replace(entity, char)
    return normalise(text)


def words(text: str) -> list[str]:
    """Word and number tokens, in order."""
    return _WORD.findall(normalise(text))


def paragraphs(text: str) -> list[str]:
    return [p.strip() for p in normalise(text).split("\n\n") if p.strip()]


def _ends_with_abbreviation(chunk: str) -> bool:
    match = _ABBREV_TAIL.search(chunk)
    if not match:
        return False
    token = match.group(1)
    if token.lower() in _ABBREV:
        return True
    # A single capital letter is an initial: "J. Smith said".
    return len(token) == 1 and token.isupper()


def sentences(text: str) -> list[str]:
    """Split into sentences, keeping abbreviations and initials intact."""
    text = normalise(text)
    if not text:
        return []
    out: list[str] = []
    buffer = ""
    for chunk in _SENT_END.split(text):
        candidate = f"{buffer} {chunk}".strip() if buffer else chunk.strip()
        if not candidate:
            continue
        if _ends_with_abbreviation(candidate):
            buffer = candidate
            continue
        out.append(candidate)
        buffer = ""
    if buffer:
        out.append(buffer)
    return [s for s in out if s]


@dataclass(frozen=True, slots=True)
class WordStats:
    """Counts every signal needs, computed once per analysis."""

    total: int
    unique: int
    caps: int
    exclamations: int
    questions: int
    sentence_count: int
    paragraph_count: int
    avg_sentence_words: float
    caps_ratio: float
    exclam_per_100: float


def stats(text: str) -> WordStats:
    tokens = words(text)
    total = len(tokens)
    caps = sum(1 for t in tokens if len(t) >= 2 and t.isupper() and t.isalpha())
    sents = sentences(text)
    paras = paragraphs(text)
    normalised = normalise(text)
    exclamations = normalised.count("!")
    questions = normalised.count("?")
    return WordStats(
        total=total,
        unique=len({t.lower() for t in tokens}),
        caps=caps,
        exclamations=exclamations,
        questions=questions,
        sentence_count=len(sents),
        paragraph_count=len(paras),
        avg_sentence_words=round(total / len(sents), 2) if sents else 0.0,
        caps_ratio=round(caps / total, 4) if total else 0.0,
        exclam_per_100=round(exclamations * 100 / total, 2) if total else 0.0,
    )


def per_100(count: int, total: int) -> float:
    """Rate per 100 words — the only fair way to compare texts of different lengths."""
    if total <= 0:
        return 0.0
    return count * 100.0 / total


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))
