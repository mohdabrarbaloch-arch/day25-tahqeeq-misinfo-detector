"""ORM models.

Three tables. `Analysis` stores the score and the full signal breakdown as JSON
so a report can be re-rendered years later without re-running the engine — and
so that changing the engine never silently rewrites history.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    analyses: Mapped[list[Analysis]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    headline: Mapped[str] = mapped_column(String(500), default="")
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    text_excerpt: Mapped[str] = mapped_column(Text, default="")
    text_chars: Mapped[int] = mapped_column(Integer, default=0)

    score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    verdict_label: Mapped[str] = mapped_column(String(120), default="")

    word_count: Mapped[int] = mapped_column(Integer, default=0)
    sentence_count: Mapped[int] = mapped_column(Integer, default=0)
    reading_seconds: Mapped[int] = mapped_column(Integer, default=0)

    # The full report, frozen at analysis time.
    report: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)

    user: Mapped[User] = relationship(back_populates="analyses")

    __table_args__ = (Index("ix_analyses_user_created", "user_id", "created_at"),)


class SharedReport(Base):
    """A public, read-only snapshot of one analysis.

    Sharing is opt-in and copies the report rather than pointing at the row, so
    deleting your analysis also kills the public link.
    """

    __tablename__ = "shared_reports"

    slug: Mapped[str] = mapped_column(String(24), primary_key=True)
    analysis_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("analyses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    views: Mapped[int] = mapped_column(Integer, default=0)
