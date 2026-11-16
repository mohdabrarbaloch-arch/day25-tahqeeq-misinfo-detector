"""Fetch an article from a URL, safely.

This is the only place in the app that makes an outbound request, so it is the
only place that needs an SSRF guard. The guard resolves the hostname and checks
every returned address against the private ranges *before* connecting — checking
the string "localhost" is not enough, because `127.0.0.1`, `0.0.0.0`, `[::1]`
and a DNS record pointing at 169.254.169.254 all reach the same place.

Redirects are followed manually so each hop is re-validated. httpx's automatic
redirect following would happily walk from a public URL to the metadata service.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import get_settings

settings = get_settings()

MAX_REDIRECTS = 4

# Tags whose text is never article content.
_STRIP_TAGS = (
    "script",
    "style",
    "noscript",
    "iframe",
    "svg",
    "form",
    "nav",
    "footer",
    "header",
    "aside",
    "button",
    "select",
    "textarea",
)

# Containers that usually hold the article body, best first.
_CONTENT_SELECTORS = (
    "article",
    "[role=main]",
    "main",
    ".article-body",
    ".article__body",
    ".story-body",
    ".post-content",
    ".entry-content",
    "#content",
)


class FetchError(Exception):
    """A fetch that failed for a reason worth telling the user about."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class FetchedArticle:
    url: str
    final_url: str
    title: str
    text: str
    truncated: bool

    @property
    def word_count(self) -> int:
        return len(self.text.split())


def _is_public_address(host: str) -> bool:
    """True if every address the host resolves to is publicly routable."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise FetchError(f"Could not resolve {host}.", 400) from exc

    if not infos:
        raise FetchError(f"Could not resolve {host}.", 400)

    for info in infos:
        raw = info[4][0]
        try:
            address = ipaddress.ip_address(raw)
        except ValueError:
            return False
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        ):
            return False
    return True


def validate_url(url: str) -> str:
    """Normalise and vet a URL. Raises FetchError if it is not fetchable."""
    candidate = url.strip()
    if not candidate:
        raise FetchError("No URL was supplied.", 400)
    if not candidate.startswith(("http://", "https://")):
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"}:
        raise FetchError("Only http and https URLs can be fetched.", 400)
    if not parsed.hostname:
        raise FetchError("That URL has no hostname.", 400)
    if parsed.username or parsed.password:
        raise FetchError("URLs with embedded credentials are not fetched.", 400)

    if not settings.allow_private_fetch and not _is_public_address(parsed.hostname):
        raise FetchError(
            "That address is private or internal, so it will not be fetched. "
            "Tahqeeq only reads public web pages.",
            400,
        )
    return candidate


def _extract(html: str) -> tuple[str, str]:
    """Return (title, body text) from raw HTML."""
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(list(_STRIP_TAGS)):
        tag.decompose()

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    if not title:
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            title = str(og["content"]).strip()

    container = None
    for selector in _CONTENT_SELECTORS:
        found = soup.select_one(selector)
        if found and len(found.get_text(strip=True)) > 200:
            container = found
            break
    if container is None:
        container = soup.body or soup

    blocks: list[str] = []
    for element in container.find_all(["p", "h1", "h2", "h3", "li", "blockquote"]):
        text = element.get_text(" ", strip=True)
        if len(text) >= 25:
            blocks.append(text)

    if not blocks:
        blocks = [container.get_text(" ", strip=True)]

    body = "\n\n".join(blocks)
    return title, body


def fetch_article(url: str) -> FetchedArticle:
    """Fetch and extract an article. Raises FetchError on any failure."""
    current = validate_url(url)
    original = current

    headers = {
        "User-Agent": settings.fetch_user_agent,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    with httpx.Client(
        timeout=settings.fetch_timeout_seconds,
        follow_redirects=False,
        headers=headers,
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            try:
                response = client.get(current)
            except httpx.TimeoutException as exc:
                raise FetchError("That site took too long to respond.", 504) from exc
            except httpx.HTTPError as exc:
                raise FetchError(f"Could not reach that site: {exc}", 502) from exc

            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise FetchError("That site redirected without saying where.", 502)
                current = validate_url(str(httpx.URL(current).join(location)))
                continue

            if response.status_code >= 400:
                raise FetchError(
                    f"That page returned HTTP {response.status_code}.",
                    502 if response.status_code >= 500 else 400,
                )

            content_type = response.headers.get("content-type", "").lower()
            if "html" not in content_type and "xml" not in content_type:
                raise FetchError(f"That URL is {content_type or 'not HTML'}, not a web page.", 400)

            raw = response.content[: settings.fetch_max_bytes]
            truncated = len(response.content) > settings.fetch_max_bytes
            break
        else:
            raise FetchError("That URL redirected too many times.", 400)

    encoding = response.encoding or "utf-8"
    try:
        html = raw.decode(encoding, errors="replace")
    except LookupError:
        html = raw.decode("utf-8", errors="replace")

    title, body = _extract(html)
    if len(body.split()) < 20:
        raise FetchError(
            "That page did not contain enough readable text. It may be paywalled, "
            "JavaScript-rendered, or not an article.",
            422,
        )

    return FetchedArticle(
        url=original,
        final_url=current,
        title=title[:500],
        text=body[: settings.max_text_chars],
        truncated=truncated or len(body) > settings.max_text_chars,
    )
