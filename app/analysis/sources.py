"""Domain reputation, judged on structure rather than on opinion.

There is no denylist of named outlets anywhere in this file, and that is a
deliberate design decision. Calling a specific publication a fake-news site is
a factual claim Tahqeeq cannot verify, and getting it wrong would be defamation
with a database attached. So the tool does two things instead:

  1. It recognises a small allowlist of outlets with published editorial
     standards, and gives them a modest prior.
  2. For everything else it looks at *structural* properties — is this a free
     blog host, a URL shortener, a throwaway TLD — and reports them as
     observations, not verdicts.

An unknown domain gets a neutral prior and is judged on its text alone. That is
the honest position: not knowing a domain is not evidence against it.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from app.analysis import lexicon as lex


@dataclass(frozen=True, slots=True)
class DomainAssessment:
    domain: str
    known: bool
    prior: float
    notes: list[str]
    is_shortener: bool

    @property
    def label(self) -> str:
        if self.is_shortener:
            return "URL shortener"
        if self.known:
            return "Recognised outlet"
        return "Unrecognised domain"


def _registrable(host: str) -> str:
    """Best-effort registrable domain without pulling in a public-suffix list.

    Handles the two-level suffixes that actually matter for this project
    (co.uk, com.pk, com.au, co.in) and falls back to the last two labels.
    """
    host = host.lower().strip(".")
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    two_level = {"co", "com", "net", "org", "gov", "edu", "ac"}
    if parts[-2] in two_level and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def assess(url: str | None) -> DomainAssessment | None:
    if not url:
        return None
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    if not host:
        return None

    domain = _registrable(host)
    notes: list[str] = []

    if domain in lex.URL_SHORTENERS:
        return DomainAssessment(
            domain=domain,
            known=False,
            prior=0.45,
            notes=["The link is shortened, so the real publisher is hidden until it is opened."],
            is_shortener=True,
        )

    if domain in lex.HIGH_TRUST_DOMAINS:
        return DomainAssessment(
            domain=domain,
            known=True,
            prior=0.95,
            notes=["This domain is on the recognised-outlet list."],
            is_shortener=False,
        )

    prior = 0.6
    for pattern in lex.FREE_HOST_PATTERNS:
        if pattern.search(host):
            prior = 0.5
            notes.append(
                "Hosted on a free publishing platform, which has no editorial review "
                "before publication."
            )
            break

    tld = domain.rsplit(".", 1)[-1]
    if tld in lex.LOW_SIGNAL_TLDS:
        prior = min(prior, 0.45)
        notes.append(f"The .{tld} top-level domain is cheap and commonly used for throwaway sites.")

    if not notes:
        notes.append(
            "This domain is not on the recognised-outlet list. That is not evidence "
            "against it — it is simply unknown, so the text was judged on its own merits."
        )

    return DomainAssessment(
        domain=domain, known=False, prior=prior, notes=notes, is_shortener=False
    )
