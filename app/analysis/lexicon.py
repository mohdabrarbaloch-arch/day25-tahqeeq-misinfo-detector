"""The word lists every signal is built on.

These are the actual domain knowledge in the project, so they are kept in one
place, commented, and easy to argue with. Each list is deliberately narrow: a
word only belongs here if its presence in a news article is genuinely
diagnostic, not merely informal. "Huge" is not on the sensationalism list;
"bombshell" is.
"""

from __future__ import annotations

import re

# --- 1. sensationalism ------------------------------------------------------
# Words that sell a feeling rather than report a fact.
SENSATIONAL = frozenset(
    {
        "shocking",
        "shock",
        "bombshell",
        "explosive",
        "devastating",
        "terrifying",
        "horrifying",
        "outrage",
        "outrageous",
        "fury",
        "furious",
        "slam",
        "slams",
        "slammed",
        "destroy",
        "destroys",
        "destroyed",
        "obliterate",
        "obliterated",
        "humiliate",
        "humiliated",
        "epic",
        "insane",
        "unbelievable",
        "jaw-dropping",
        "miracle",
        "miraculous",
        "secret",
        "secrets",
        "exposed",
        "busted",
        "caught",
        "scandal",
        "scandalous",
        "disgusting",
        "sickening",
        "horrendous",
        "catastrophic",
        "apocalyptic",
        "nightmare",
        "chaos",
        "meltdown",
        "slaughter",
        "carnage",
        "stunning",
        "astonishing",
        "staggering",
        "mind-blowing",
        "unprecedented",
    }
)

# --- 2. absolute certainty --------------------------------------------------
# Claims stated as settled fact, with no room for being wrong.
ABSOLUTES = frozenset(
    {
        "proves",
        "proven",
        "proof",
        "undeniable",
        "undeniably",
        "indisputable",
        "indisputably",
        "definitely",
        "certainly",
        "absolutely",
        "guaranteed",
        "always",
        "never",
        "everyone",
        "nobody",
        "obviously",
        "clearly",
        "unquestionably",
        "irrefutable",
        "fact",
        "100%",
    }
)

# Language that admits uncertainty. Its presence is a *good* sign.
HEDGES = frozenset(
    {
        "reportedly",
        "allegedly",
        "apparently",
        "seemingly",
        "possibly",
        "probably",
        "likely",
        "unlikely",
        "may",
        "might",
        "could",
        "would",
        "suggests",
        "suggested",
        "appears",
        "appeared",
        "preliminary",
        "initial",
        "estimate",
        "estimated",
        "roughly",
        "approximately",
        "about",
        "around",
        "unconfirmed",
        "uncertain",
        "disputed",
        "contested",
        "claimed",
        "claims",
        "according",
    }
)

# --- 3. attribution ---------------------------------------------------------
# Verbs and phrases that attach a claim to a named, checkable source.
ATTRIBUTION_VERBS = frozenset(
    {
        "said",
        "says",
        "told",
        "stated",
        "announced",
        "confirmed",
        "declared",
        "added",
        "explained",
        "noted",
        "wrote",
        "reported",
        "testified",
        "argued",
        "warned",
        "acknowledged",
        "admitted",
        "denied",
        "insisted",
        "claimed",
    }
)

NAMED_SOURCE_PATTERNS = (
    re.compile(r"according to (?:the )?[A-Z][\w.&'-]*(?:\s+[A-Z][\w.&'-]*){0,4}"),
    re.compile(r"(?:a|the) (?:spokes(?:person|man|woman)|statement|report|study|paper)\b"),
    re.compile(r"(?:researchers|scientists|officials|analysts|investigators) at [A-Z]"),
    re.compile(r"published in (?:the )?[A-Z][\w.&'-]*"),
    re.compile(r"[A-Z][a-z]+ (?:University|Institute|Ministry|Department|Agency|Commission)"),
)

# Attribution that points at nobody in particular.
VAGUE_SOURCE_PATTERNS = (
    re.compile(r"sources? (?:say|said|close to|familiar|indicate|suggest)"),
    re.compile(r"people (?:familiar|close to|in the know)"),
    re.compile(r"(?:experts|critics|analysts|observers|many|some) (?:say|says|believe|agree|warn)"),
    re.compile(r"it (?:is|has been) (?:reported|said|claimed|rumou?red)"),
    re.compile(r"word (?:on the street|is)"),
    re.compile(r"reportedly\b"),
)

# --- 4. anonymous sourcing --------------------------------------------------
ANONYMOUS_SOURCE_PATTERNS = (
    re.compile(r"a (?:friend|relative|neighbour|neighbor|colleague) of (?:the|his|her|a)"),
    re.compile(r"(?:an? )?(?:insider|whistleblower|source) (?:who|that) (?:asked|spoke)"),
    re.compile(r"(?:on|under) condition of anonymity"),
    re.compile(r"(?:a|an) anonymous (?:source|official|person)"),
    re.compile(r"someone (?:who|close to) (?:knows|the)"),
)

# --- 5. vague quantities ----------------------------------------------------
VAGUE_QUANTITY_PATTERNS = (
    re.compile(r"\b(?:thousands|millions|billions|hundreds|dozens|countless|numerous)\b"),
    re.compile(r"\b(?:a )?(?:huge|massive|enormous|staggering) (?:number|amount|sum)\b"),
    re.compile(r"\b(?:many|several|a lot of) (?:people|thousands|hundreds)\b"),
)

# A specific figure: 1,500 / 45% / 2.5 billion / 12 people.
PRECISE_QUANTITY = re.compile(
    r"\b\d[\d,]*(?:\.\d+)?\s*(?:%|percent|per cent|million|billion|trillion|thousand|lakh|crore)?\b"
)

# --- 6. clickbait headlines -------------------------------------------------
CLICKBAIT_PATTERNS = (
    re.compile(r"^you (?:won't|wont|will not) believe", re.I),
    re.compile(r"^this is (?:why|what)", re.I),
    re.compile(r"^the reason (?:why|behind)", re.I),
    re.compile(r"(?:what|here's what) happened (?:next|when)", re.I),
    re.compile(r"(?:will|'ll) blow your mind", re.I),
    re.compile(r"nobody (?:expected|saw this)", re.I),
    re.compile(r"goes viral|breaks the internet", re.I),
    re.compile(r"^breaking[:!]", re.I),
    re.compile(r"(?:shocking|stunning|insane) (?:video|moment|truth|reason)", re.I),
    re.compile(r"you need to (?:see|know) this", re.I),
)

# --- 7. conspiracy markers --------------------------------------------------
CONSPIRACY_PATTERNS = (
    re.compile(r"they don'?t want you to know", re.I),
    re.compile(r"(?:mainstream|lamestream) media (?:won'?t|will not|is hiding|ignores)", re.I),
    re.compile(r"\bwake up\b", re.I),
    re.compile(r"\bsheeple\b", re.I),
    re.compile(r"\bcover[- ]?up\b", re.I),
    re.compile(r"hidden agenda", re.I),
    re.compile(r"\b(?:big pharma|deep state|new world order|globalist)\b", re.I),
    re.compile(r"false flag", re.I),
    re.compile(r"crisis actor", re.I),
    re.compile(r"do your own research", re.I),
    re.compile(r"(?:banned|censored|suppressed|silenced) (?:by|from)", re.I),
    re.compile(r"the (?:real|actual) truth", re.I),
    re.compile(r"what they'?re (?:hiding|not telling)", re.I),
)

# --- 8. share pressure ------------------------------------------------------
SHARE_PRESSURE_PATTERNS = (
    re.compile(r"share (?:this|it|before|with)", re.I),
    re.compile(r"forward (?:this|to|it)", re.I),
    re.compile(r"tell everyone", re.I),
    re.compile(r"spread the word", re.I),
    re.compile(r"before (?:it'?s|they) (?:deleted|removed|take it down)", re.I),
    re.compile(r"copy and paste", re.I),
    re.compile(r"send (?:this )?to (?:\d+|ten|10|all)", re.I),
    re.compile(r"don'?t (?:let|allow) them (?:delete|remove|hide)", re.I),
)

# --- 9. forward markers -----------------------------------------------------
# The single most diagnostic thing for a WhatsApp forward, which is the real
# distribution channel for most misinformation in Pakistan.
FORWARD_PATTERNS = (
    re.compile(r"^\s*(?:fw|fwd|forwarded)\s*:", re.I | re.M),
    re.compile(r"^\s*forwarded (?:as received|message)", re.I | re.M),
    re.compile(r"as received\b", re.I),
    re.compile(r"please (?:forward|share) (?:to|with) (?:all|everyone|your)", re.I),
    re.compile(r"viral (?:message|forward|whatsapp)", re.I),
    re.compile(r"^\s*breaking\s*:", re.I | re.M),
)

# --- 10. quote handling -----------------------------------------------------
QUOTE = re.compile(r"[\"\u201c]([^\"\u201d]{12,400})[\"\u201d]")

# --- 11. structure ----------------------------------------------------------
BYLINE = re.compile(r"\b(?:by|written by|reported by)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?", re.I)
DATE_MARKER = re.compile(
    r"\b(?:\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4}"
    r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{4}"
    r"|\d{4}-\d{2}-\d{2})\b",
    re.I,
)
URL = re.compile(r"https?://[^\s<>\"']+", re.I)

# --- source reputation ------------------------------------------------------
# An allowlist only. There is deliberately no denylist of named outlets: calling
# a specific publication fake is a factual claim this tool cannot verify, and
# getting it wrong would be defamation. Unknown domains get a neutral prior and
# are judged on their text alone.
HIGH_TRUST_DOMAINS = frozenset(
    {
        "reuters.com",
        "apnews.com",
        "afp.com",
        "bbc.com",
        "bbc.co.uk",
        "dawn.com",
        "tribune.com.pk",
        "thenews.com.pk",
        "nation.com.pk",
        "nature.com",
        "science.org",
        "sciencedirect.com",
        "thelancet.com",
        "nejm.org",
        "who.int",
        "un.org",
        "worldbank.org",
        "imf.org",
        "nasa.gov",
        "nih.gov",
        "cdc.gov",
        "europa.eu",
        "ft.com",
        "wsj.com",
        "bloomberg.com",
        "economist.com",
    }
)

# Structural hints that a domain is not a newsroom. These are properties, not
# accusations: a blogspot subdomain is not automatically wrong, it just has no
# editorial process behind it.
LOW_SIGNAL_TLDS = frozenset({"xyz", "top", "click", "buzz", "loan", "work", "gq", "tk"})
FREE_HOST_PATTERNS = (
    re.compile(r"(?:^|\.)blogspot\.", re.I),
    re.compile(r"(?:^|\.)wordpress\.com$", re.I),
    re.compile(r"(?:^|\.)weebly\.com$", re.I),
    re.compile(r"(?:^|\.)wixsite\.com$", re.I),
    re.compile(r"(?:^|\.)medium\.com$", re.I),
    re.compile(r"(?:^|\.)substack\.com$", re.I),
)
URL_SHORTENERS = frozenset(
    {"bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly", "is.gd", "buff.ly", "cutt.ly"}
)
