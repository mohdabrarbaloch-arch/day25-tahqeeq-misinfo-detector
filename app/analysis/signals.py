"""The eleven signals, each one a small function with a stated weight.

Every signal returns a `Signal` carrying its own severity, the evidence that
produced it, and a plain-language explanation. Nothing here is a black box: if
the score says 34, the report can point at exactly which signals took the 66
points away and quote the words responsible.

Severity is always 0.0 (no problem found) to 1.0 (severe). A signal that cannot
be assessed on the given text returns `applicable=False` and is excluded from
the weighted average rather than being scored as clean — scoring a 20-word
snippet as "no attribution problems" would be a lie.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from app.analysis import lexicon as lex
from app.analysis.text import WordStats, clamp, per_100, sentences


@dataclass(frozen=True, slots=True)
class Signal:
    """One inspectable finding."""

    id: str
    label: str
    weight: float
    severity: float
    applicable: bool
    explanation: str
    evidence: list[str] = field(default_factory=list)

    @property
    def points_lost(self) -> float:
        """How many credibility points this signal is responsible for."""
        return round(self.severity * 100, 1)


@dataclass(frozen=True, slots=True)
class SignalContext:
    """Everything a signal might need, computed once."""

    text: str
    lower: str
    stats: WordStats
    headline: str
    body: str


def _hits(patterns: tuple[re.Pattern[str], ...], text: str) -> list[str]:
    """Return the matched substrings, de-duplicated, in order of appearance."""
    found: list[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        for match in pattern.finditer(text):
            snippet = match.group(0).strip()
            key = snippet.lower()
            if key and key not in seen:
                seen.add(key)
                found.append(snippet)
    return found


def _word_hits(vocabulary: frozenset[str], tokens: list[str]) -> list[str]:
    return [t for t in tokens if t.lower() in vocabulary]


# --- 1. sensationalism ------------------------------------------------------
def sensationalism(ctx: SignalContext) -> Signal:
    tokens = re.findall(r"[A-Za-z][A-Za-z'\u2019\-]*", ctx.text)
    hits = _word_hits(lex.SENSATIONAL, tokens)
    rate = per_100(len(hits), ctx.stats.total)
    # 3 alarm words per 100 words is already a lot for a news report.
    severity = clamp(
        rate / 3.0 * 0.65 + ctx.stats.caps_ratio * 2.0 + ctx.stats.exclam_per_100 / 4.0
    )
    return Signal(
        id="sensationalism",
        label="Sensational language",
        weight=1.2,
        severity=round(severity, 3),
        applicable=ctx.stats.total >= 20,
        explanation=(
            f"{len(hits)} alarm word(s) in {ctx.stats.total} words "
            f"({rate:.1f} per 100), {ctx.stats.caps_ratio:.1%} of words in capitals, "
            f"{ctx.stats.exclamations} exclamation mark(s)."
        ),
        evidence=sorted(set(hits))[:8],
    )


# --- 2. absolute certainty --------------------------------------------------
def absolute_certainty(ctx: SignalContext) -> Signal:
    tokens = re.findall(r"[A-Za-z][A-Za-z'\u2019\-]*", ctx.text)
    absolutes = _word_hits(lex.ABSOLUTES, tokens)
    hedges = _word_hits(lex.HEDGES, tokens)
    total = len(absolutes) + len(hedges)
    # With no certainty language at all there is nothing to penalise.
    severity = 0.0 if total == 0 else clamp(len(absolutes) / total * 1.15)
    return Signal(
        id="absolute_certainty",
        label="Claims stated as settled fact",
        weight=1.0,
        severity=round(severity, 3),
        applicable=ctx.stats.total >= 30,
        explanation=(
            f"{len(absolutes)} absolute claim word(s) against {len(hedges)} hedging word(s). "
            "Careful reporting hedges; confident-sounding text with no hedging is a warning sign."
        ),
        evidence=sorted(set(absolutes))[:8],
    )


# --- 3. attribution ---------------------------------------------------------
def attribution(ctx: SignalContext) -> Signal:
    named = _hits(lex.NAMED_SOURCE_PATTERNS, ctx.text)
    vague = _hits(lex.VAGUE_SOURCE_PATTERNS, ctx.lower)
    verbs = _word_hits(lex.ATTRIBUTION_VERBS, re.findall(r"[A-Za-z]+", ctx.text))

    if named:
        severity = clamp(0.12 - 0.02 * min(len(named), 4))
        verdict = "names a checkable source"
    elif vague:
        severity = 0.72
        verdict = "attributes only to unnamed sources"
    elif verbs:
        severity = 0.55
        verdict = "uses reporting verbs but never says who spoke"
    else:
        severity = 0.85
        verdict = "attributes nothing at all"

    return Signal(
        id="attribution",
        label="Source attribution",
        weight=1.4,
        severity=round(severity, 3),
        applicable=ctx.stats.total >= 40,
        explanation=(
            f"This text {verdict}: {len(named)} named attribution(s), "
            f"{len(vague)} vague one(s), {len(verbs)} reporting verb(s)."
        ),
        evidence=(named + vague)[:8],
    )


# --- 4. anonymous sourcing --------------------------------------------------
def anonymous_sourcing(ctx: SignalContext) -> Signal:
    hits = _hits(lex.ANONYMOUS_SOURCE_PATTERNS, ctx.lower)
    severity = clamp(len(hits) / 2.0)
    return Signal(
        id="anonymous_sourcing",
        label="Anonymous sourcing",
        weight=0.9,
        severity=round(severity, 3),
        applicable=ctx.stats.total >= 40,
        explanation=(
            f"{len(hits)} anonymous-source phrase(s) found. "
            "Anonymous sourcing is sometimes legitimate, but it cannot be checked by a reader."
        ),
        evidence=hits[:6],
    )


# --- 5. vague quantities ----------------------------------------------------
def vague_quantities(ctx: SignalContext) -> Signal:
    vague = _hits(lex.VAGUE_QUANTITY_PATTERNS, ctx.lower)
    precise = lex.PRECISE_QUANTITY.findall(ctx.text)
    total = len(vague) + len(precise)
    severity = clamp(len(vague) / total * 1.4) if total else 0.0
    return Signal(
        id="vague_quantities",
        label="Vague quantities",
        weight=0.7,
        severity=round(severity, 3),
        applicable=ctx.stats.total >= 40,
        explanation=(
            f"{len(vague)} vague quantity phrase(s) against {len(precise)} specific figure(s). "
            "Real events usually come with numbers someone can check."
        ),
        evidence=vague[:6],
    )


# --- 6. clickbait headline --------------------------------------------------
def clickbait_headline(ctx: SignalContext) -> Signal:
    if not ctx.headline:
        return Signal(
            id="clickbait_headline",
            label="Headline quality",
            weight=1.1,
            severity=0.0,
            applicable=False,
            explanation="No headline supplied, so headline quality was not assessed.",
        )

    hits = _hits(lex.CLICKBAIT_PATTERNS, ctx.headline)
    headline_words = {w.lower() for w in re.findall(r"[A-Za-z]{4,}", ctx.headline)}
    body_words = {w.lower() for w in re.findall(r"[A-Za-z]{4,}", ctx.body)}
    overlap = len(headline_words & body_words) / len(headline_words) if headline_words else 1.0
    mismatch = clamp((0.5 - overlap) * 2.0)
    severity = clamp(len(hits) * 0.5 + mismatch * 0.4)

    return Signal(
        id="clickbait_headline",
        label="Headline quality",
        weight=1.1,
        severity=round(severity, 3),
        applicable=True,
        explanation=(
            f"{len(hits)} clickbait pattern(s) in the headline; "
            f"{overlap:.0%} of its long words also appear in the body."
        ),
        evidence=hits[:5],
    )


# --- 7. conspiracy markers --------------------------------------------------
def conspiracy_markers(ctx: SignalContext) -> Signal:
    hits = _hits(lex.CONSPIRACY_PATTERNS, ctx.text)
    severity = clamp(len(hits) / 2.0)
    return Signal(
        id="conspiracy_markers",
        label="Conspiracy framing",
        weight=1.3,
        severity=round(severity, 3),
        applicable=ctx.stats.total >= 30,
        explanation=(
            f"{len(hits)} conspiracy-framing phrase(s). These are rhetorical moves that "
            "pre-empt doubt by claiming the evidence is being hidden."
        ),
        evidence=hits[:6],
    )


# --- 8. share pressure ------------------------------------------------------
def share_pressure(ctx: SignalContext) -> Signal:
    hits = _hits(lex.SHARE_PRESSURE_PATTERNS, ctx.text)
    severity = clamp(len(hits) / 1.5)
    return Signal(
        id="share_pressure",
        label="Share pressure",
        weight=1.2,
        severity=round(severity, 3),
        applicable=ctx.stats.total >= 20,
        explanation=(
            f"{len(hits)} instruction(s) to share or forward. "
            "Journalism does not ask you to redistribute it before it is deleted."
        ),
        evidence=hits[:6],
    )


# --- 9. forward markers -----------------------------------------------------
def forward_markers(ctx: SignalContext) -> Signal:
    hits = _hits(lex.FORWARD_PATTERNS, ctx.text)
    severity = clamp(len(hits) / 1.5)
    return Signal(
        id="forward_markers",
        label="Forwarded-message markers",
        weight=1.0,
        severity=round(severity, 3),
        applicable=True,
        explanation=(
            f"{len(hits)} marker(s) of a forwarded chain message. "
            "This is the shape of a WhatsApp forward, not of a published article."
        ),
        evidence=hits[:6],
    )


# --- 10. quote integrity ----------------------------------------------------
def quote_integrity(ctx: SignalContext) -> Signal:
    quotes = lex.QUOTE.findall(ctx.text)
    if not quotes:
        return Signal(
            id="quote_integrity",
            label="Quotation handling",
            weight=0.8,
            severity=0.35,
            applicable=ctx.stats.total >= 60,
            explanation=(
                "No direct quotations. Not a problem on its own — a short news brief "
                "often has none — but a long article with no quoted speech is unusual."
            ),
        )

    sents = sentences(ctx.text)
    attributed = 0
    for sentence in sents:
        if not lex.QUOTE.search(sentence):
            continue
        has_verb = any(v in sentence.lower() for v in lex.ATTRIBUTION_VERBS)
        has_named = any(p.search(sentence) for p in lex.NAMED_SOURCE_PATTERNS)
        if has_verb or has_named:
            attributed += 1

    ratio = attributed / len(quotes)
    severity = clamp(1.0 - ratio)
    return Signal(
        id="quote_integrity",
        label="Quotation handling",
        weight=0.8,
        severity=round(severity, 3),
        applicable=True,
        explanation=(
            f"{len(quotes)} direct quotation(s), {attributed} attached to a speaker. "
            "A quote with nobody behind it cannot be verified."
        ),
        evidence=[q[:90] for q in quotes[:3]],
    )


# --- 11. structure ----------------------------------------------------------
def structure(ctx: SignalContext) -> Signal:
    problems: list[str] = []
    severity = 0.0

    if ctx.stats.total < 80:
        severity += 0.2
        problems.append(f"only {ctx.stats.total} words")
    if ctx.stats.paragraph_count <= 1 and ctx.stats.total > 150:
        severity += 0.2
        problems.append("one undivided block of text")
    if not lex.BYLINE.search(ctx.text):
        severity += 0.1
        problems.append("no byline")
    if not lex.DATE_MARKER.search(ctx.text):
        severity += 0.15
        problems.append("no date")
    if not lex.URL.search(ctx.text):
        severity += 0.1
        problems.append("no link to a primary source")

    return Signal(
        id="structure",
        label="Article structure",
        weight=0.6,
        severity=round(clamp(severity), 3),
        applicable=True,
        explanation=(
            "Missing: " + ", ".join(problems) + "."
            if problems
            else "Has a byline, a date, a link and a normal paragraph structure."
        ),
        evidence=problems[:5],
    )


SIGNALS: tuple[Callable[[SignalContext], Signal], ...] = (
    sensationalism,
    absolute_certainty,
    attribution,
    anonymous_sourcing,
    vague_quantities,
    clickbait_headline,
    conspiracy_markers,
    share_pressure,
    forward_markers,
    quote_integrity,
    structure,
)


def run_all(ctx: SignalContext) -> list[Signal]:
    return [signal(ctx) for signal in SIGNALS]
