"""Application settings, loaded from the environment only.

Nothing here has a secret default. If JWT_SECRET is missing the app refuses to
start in production mode rather than quietly signing tokens with a guessable
string.
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- core -------------------------------------------------------------
    app_name: str = "Tahqeeq"
    environment: str = Field(default="development", description="development | production")
    debug: bool = False

    # --- security ---------------------------------------------------------
    jwt_secret: str = Field(default="", description="HS256 signing key. Required in production.")
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60 * 24 * 7
    bcrypt_rounds: int = 12

    # --- database ---------------------------------------------------------
    database_url: str = "sqlite:///./tahqeeq.db"

    # --- http -------------------------------------------------------------
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"
    rate_limit_per_minute: int = 60
    analyze_rate_limit_per_minute: int = 20

    # --- url fetching -----------------------------------------------------
    fetch_timeout_seconds: float = 12.0
    fetch_max_bytes: int = 3_000_000
    fetch_user_agent: str = (
        "Mozilla/5.0 (compatible; TahqeeqBot/1.0; +https://github.com/mohdabrarbaloch-arch)"
    )
    allow_private_fetch: bool = Field(
        default=False,
        description="Allow fetching private/loopback addresses. Off by default (SSRF guard).",
    )

    # --- analysis ---------------------------------------------------------
    min_words_for_confidence: int = 40
    max_text_chars: int = 60_000

    @field_validator("environment")
    @classmethod
    def _known_environment(cls, value: str) -> str:
        allowed = {"development", "production", "test"}
        normalised = value.strip().lower()
        if normalised not in allowed:
            raise ValueError(f"environment must be one of {sorted(allowed)}")
        return normalised

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def resolved_jwt_secret(self) -> str:
        """Return the signing key, generating an ephemeral one outside production.

        In production a missing key is a hard failure: an ephemeral key would
        invalidate every session on restart and, worse, tempt someone into
        shipping a default.

        The generated key is cached on the instance. Without that cache every
        call returns a *different* random string, so a token would be signed
        with one key and verified with another and every login would fail with
        a 401 — which is exactly the bug this comment exists to prevent.
        """
        if self.jwt_secret:
            if self.is_production and len(self.jwt_secret) < 32:
                raise RuntimeError(
                    "JWT_SECRET must be at least 32 characters in production. "
                    "Generate one with: "
                    'python -c "import secrets; print(secrets.token_urlsafe(48))"'
                )
            return self.jwt_secret
        if self.is_production:
            raise RuntimeError(
                "JWT_SECRET is not set. Refusing to start in production. "
                'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        cached = self.__dict__.get("_ephemeral_secret")
        if cached is None:
            cached = secrets.token_urlsafe(48)
            object.__setattr__(self, "_ephemeral_secret", cached)
        return cached


@lru_cache
def get_settings() -> Settings:
    return Settings()
