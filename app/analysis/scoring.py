"""The scoring engine: turn eleven signals into one number you can argue with.

The score is a weighted average of signal severities, inverted so 100 is clean.
Three decisions are worth explaining because they are where a naive version of
this tool goes wrong:

1. **Inapplicable signals are excluded, not zeroed.** A 30-word snippet cannot
   be assessed for attribution, so scoring it 0 ("no attribution problems")
   would inflate its credibility. It is dropped from the denominator instead.

2. **The worst signal sets a ceiling.** A weighted average lets one catastrophic
   finding be diluted by ten clean ones — a text with "share this before they
   delete it" and nothing else wrong would still score in the 80s. So the final
   score is capped at `100 - worst_severity * 55`, which means a single severe
   finding can never be averaged away.

3. **Short texts get a confidence penalty, not a score penalty.** The score
   reflects what the signals found; the confidence reflects how much text they
   had to work with. Conflating the two is how tools end up confidently wrong
   about a headline.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.analysis import sources
from app.analysis.signals import Signal, SignalContext, run_all
from app.analysis.text import clamp, normalise, stats, strip_markup

VERDICTS = (
    (85.0, "credible", "Reads like standard reporting"),
    (65.0, "mostly-credible", "Mostly sound, with some weak spots"),
    (45.0, "mixed", "Mixed signals — check the primary source"),
    (25.0, "questionable", "Several strong warning signs"),
    (0.0, "unreliable", "Reads like misinformation"),
)


def _verdict(score: float) -> tuple[str, str]:
    for threshold, key, label in VERDICTS:
        if score >= threshold:
            return key, label
    return "unreliable", "Reads like misinformation"


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    score: float
    confidence: float
    verdict: str
    verdict_label: str
    signals: list[Signal]
    domain: sources.DomainAssessment | None
    word_count: int
    sentence_count: int
    reading_seconds: int
    headline: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "confidence": self.confidence,
            "verdict": self.verdict,
            "verdict_label": self.verdict_label,
            "word_count": self.word_count,
            "sentence_count": self.sentence_count,
            "reading_seconds": self.reading_seconds,
            "headline": self.headline,
            "notes": self.notes,
            "domain": (
                {
                    "domain": self.domain.domain,
                    "known": self.domain.known,
                    "label": self.domain.label,
                    "prior": self.domain.prior,
                    "notes": self.domain.notes,
                }
                if self.domain
                else None
            ),
            "signals": [
                {
                    "id": s.id,
                    "label": s.label,
                    "weight": s.weight,
                    "severity": s.severity,
                    "applicable": s.applicable,
                    "points_lost": s.points_lost,
                    "explanation": s.explanation,
                    "evidence": s.evidence,
                }
                for s in self.signals
            ],
        }


def _split_headline(text: str, headline: str | None) -> tuple[str, str]:
    """Return (headline, body). If none was supplied, use the first line."""
    if headline and headline.strip():
        return normalise(headline), text
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if len(lines) > 1 and len(lines[0]) <= 200:
        return lines[0], "\n".join(lines[1:])
    return "", text


def analyse(
    text: str,
    *,
    headline: str | None = None,
    url: str | None = None,
    min_words: int = 40,
) -> AnalysisResult:
    """Score a piece of text. Pure function: no I/O, no clock, no randomness."""
    cleaned = strip_markup(text or "")
    if not cleaned:
        raise ValueError("Text is empty after cleaning.")

    head, body = _split_headline(cleaned, headline)
    word_stats = stats(cleaned)
    ctx = SignalContext(
        text=cleaned,
        lower=cleaned.lower(),
        stats=word_stats,
        headline=head,
        body=body,
    )
    signals = run_all(ctx)

    applicable = [s for s in signals if s.applicable]
    if not applicable:
        raise ValueError("Text is too short to assess.")

    total_weight = sum(s.weight for s in applicable)
    weighted_severity = sum(s.severity * s.weight for s in applicable) / total_weight
    worst = max(s.severity for s in applicable)

    # Blend the average with the worst finding. A pure average lets one damning
    # signal be diluted by ten clean ones — a text whose only flaw is "share this
    # before they delete it" would still score in the 80s. A pure maximum is
    # equally wrong: one false positive would sink an honest article. So the
    # average describes the overall texture and the worst describes the single
    # most damning thing, weighted 65/35.
    combined = 0.65 * weighted_severity + 0.35 * worst
    score = round(clamp(100.0 * (1.0 - combined), 0.0, 100.0), 1)

    # Domain prior nudges the score, but only by a few points either way.
    domain = sources.assess(url)
    if domain is not None:
        score = round(clamp(score + (domain.prior - 0.6) * 10.0, 0.0, 100.0), 1)

    # No automated style check should ever claim certainty. 98 is the ceiling.
    score = min(score, 98.0)

    # Confidence is about how much evidence there was, not how bad it looked.
    length_factor = clamp(word_stats.total / max(min_words, 1))
    coverage = len(applicable) / len(signals)
    confidence = round(clamp(0.35 + 0.5 * length_factor + 0.15 * coverage), 2)

    verdict, verdict_label = _verdict(score)

    notes: list[str] = []
    notes.append(
        "A high score means no warning signs were found in the writing. It does not "
        "mean the claims are true — Tahqeeq reads style and sourcing, not facts."
    )
    if word_stats.total < min_words:
        notes.append(
            f"Only {word_stats.total} words were supplied. Signals that need a full "
            f"article were skipped, so treat this score as provisional."
        )
    if not head:
        notes.append("No headline was supplied, so headline quality was not assessed.")
    if domain is None:
        notes.append("No source URL was supplied, so the publisher was not assessed.")

    return AnalysisResult(
        score=score,
        confidence=confidence,
        verdict=verdict,
        verdict_label=verdict_label,
        signals=signals,
        domain=domain,
        word_count=word_stats.total,
        sentence_count=word_stats.sentence_count,
        reading_seconds=max(1, round(word_stats.total / 3.5)),
        headline=head,
        notes=notes,
    )
