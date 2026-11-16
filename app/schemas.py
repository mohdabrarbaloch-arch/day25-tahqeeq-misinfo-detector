"""Request and response schemas.

Validation lives here so the API rejects bad input before it reaches the engine.
Every bound is deliberate: the text cap stops a 50 MB paste from pinning a
worker, and the URL cap stops a 100 KB query string from reaching the fetcher.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(default="", max_length=80)

    @field_validator("password")
    @classmethod
    def _not_obvious(cls, value: str) -> str:
        if value.lower() in {"password12", "1234567890", "qwertyuiop", "password123"}:
            raise ValueError("That password is too common. Pick something else.")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserOut


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=20, max_length=60_000)
    headline: str | None = Field(default=None, max_length=500)
    url: str | None = Field(default=None, max_length=2048)

    @field_validator("text")
    @classmethod
    def _has_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text cannot be blank.")
        return value

    @field_validator("url")
    @classmethod
    def _looks_like_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        candidate = value.strip()
        if not candidate.startswith(("http://", "https://")):
            candidate = f"https://{candidate}"
        if "." not in candidate.split("//", 1)[-1]:
            raise ValueError("That does not look like a URL.")
        return candidate


class FetchRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)

    @field_validator("url")
    @classmethod
    def _normalise(cls, value: str) -> str:
        candidate = value.strip()
        if not candidate.startswith(("http://", "https://")):
            candidate = f"https://{candidate}"
        return candidate


class FetchResponse(BaseModel):
    url: str
    final_url: str
    title: str
    text: str
    word_count: int
    truncated: bool


class SignalOut(BaseModel):
    id: str
    label: str
    weight: float
    severity: float
    applicable: bool
    points_lost: float
    explanation: str
    evidence: list[str]


class DomainOut(BaseModel):
    domain: str
    known: bool
    label: str
    prior: float
    notes: list[str]


class AnalysisOut(BaseModel):
    id: str
    headline: str
    source_url: str | None
    score: float
    confidence: float
    verdict: str
    verdict_label: str
    word_count: int
    sentence_count: int
    reading_seconds: int
    created_at: datetime
    signals: list[SignalOut]
    domain: DomainOut | None = None
    notes: list[str] = []


class AnalysisSummary(BaseModel):
    id: str
    headline: str
    source_url: str | None
    score: float
    verdict: str
    verdict_label: str
    word_count: int
    created_at: datetime


class AnalysisList(BaseModel):
    items: list[AnalysisSummary]
    total: int
    limit: int
    offset: int


class ShareResponse(BaseModel):
    slug: str
    url: str


class StatsOut(BaseModel):
    total_analyses: int
    average_score: float
    by_verdict: dict[str, int]
    last_7_days: int
