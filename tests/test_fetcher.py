"""Tests for the SSRF guard.

This is the security-critical part of the app: it is the only code that makes an
outbound request on a user's behalf. Each test here corresponds to a real way
that guard gets bypassed in the wild.
"""

from __future__ import annotations

import pytest
from app.fetcher import FetchError, validate_url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/",
        "http://localhost:8000/",
        "http://0.0.0.0/",
        "http://[::1]/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/",
        "http://192.168.1.1/",
        "http://172.16.0.1/",
    ],
)
def test_private_and_internal_addresses_are_refused(url: str) -> None:
    with pytest.raises(FetchError):
        validate_url(url)


def test_non_http_schemes_are_refused() -> None:
    with pytest.raises(FetchError):
        validate_url("file:///etc/passwd")


def test_embedded_credentials_are_refused() -> None:
    with pytest.raises(FetchError):
        validate_url("https://user:pass@example.com/")


def test_empty_url_is_refused() -> None:
    with pytest.raises(FetchError):
        validate_url("   ")


def test_bare_hostname_gets_https() -> None:
    assert validate_url("example.com").startswith("https://")


def test_public_url_is_accepted() -> None:
    assert validate_url("https://example.com/article") == "https://example.com/article"
