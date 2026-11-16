"""Analysis endpoints: score text, fetch-and-score a URL, list history.

The engine is a pure function, so the route's only job is to validate, persist
and shape the response. Every stored analysis keeps the full report JSON, which
is what makes the history view able to show the original evidence even after the
engine's weights change.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analysis.scoring import analyse
from app.db import get_db
from app.deps import get_current_user
from app.fetcher import FetchError, fetch_article
from app.models import Analysis, SharedReport, User
from app.schemas import (
    AnalysisList,
    AnalysisOut,
    AnalysisSummary,
    AnalyzeRequest,
    FetchRequest,
    FetchResponse,
    ShareResponse,
    StatsOut,
)

router = APIRouter(prefix="/api", tags=["analysis"])

EXCERPT_CHARS = 600


def _to_out(row: Analysis) -> AnalysisOut:
    report = row.report or {}
    return AnalysisOut(
        id=row.id,
        headline=row.headline,
        source_url=row.source_url,
        score=row.score,
        confidence=row.confidence,
        verdict=row.verdict,
        verdict_label=row.verdict_label,
        word_count=row.word_count,
        sentence_count=row.sentence_count,
        reading_seconds=row.reading_seconds,
        created_at=row.created_at,
        signals=report.get("signals", []),
        domain=report.get("domain"),
        notes=report.get("notes", []),
    )


def _persist(
    db: Session,
    user: User,
    *,
    text: str,
    headline: str,
    url: str | None,
) -> Analysis:
    result = analyse(text, headline=headline or None, url=url)
    payload = result.to_dict()

    row = Analysis(
        user_id=user.id,
        headline=result.headline[:500],
        source_url=url,
        text_excerpt=text[:EXCERPT_CHARS],
        text_chars=len(text),
        score=result.score,
        confidence=result.confidence,
        verdict=result.verdict,
        verdict_label=result.verdict_label,
        word_count=result.word_count,
        sentence_count=result.sentence_count,
        reading_seconds=result.reading_seconds,
        report=payload,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/analyze", response_model=AnalysisOut, status_code=status.HTTP_201_CREATED)
def analyze_text(
    payload: AnalyzeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AnalysisOut:
    try:
        row = _persist(
            db, user, text=payload.text, headline=payload.headline or "", url=payload.url
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return _to_out(row)


@router.post("/fetch", response_model=FetchResponse)
def fetch_url(
    payload: FetchRequest,
    _user: User = Depends(get_current_user),
) -> FetchResponse:
    """Fetch a URL and return its text so the user can review it before scoring."""
    try:
        article = fetch_article(payload.url)
    except FetchError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return FetchResponse(
        url=article.url,
        final_url=article.final_url,
        title=article.title,
        text=article.text,
        word_count=article.word_count,
        truncated=article.truncated,
    )


@router.post("/analyze-url", response_model=AnalysisOut, status_code=status.HTTP_201_CREATED)
def analyze_url(
    payload: FetchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AnalysisOut:
    """Fetch a URL and score it in one call."""
    try:
        article = fetch_article(payload.url)
    except FetchError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    try:
        row = _persist(
            db,
            user,
            text=article.text,
            headline=article.title,
            url=article.final_url,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return _to_out(row)


@router.get("/analyses", response_model=AnalysisList)
def list_analyses(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AnalysisList:
    total = db.scalar(select(func.count()).select_from(Analysis).where(Analysis.user_id == user.id))
    rows = db.scalars(
        select(Analysis)
        .where(Analysis.user_id == user.id)
        .order_by(Analysis.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return AnalysisList(
        items=[
            AnalysisSummary(
                id=row.id,
                headline=row.headline,
                source_url=row.source_url,
                score=row.score,
                verdict=row.verdict,
                verdict_label=row.verdict_label,
                word_count=row.word_count,
                created_at=row.created_at,
            )
            for row in rows
        ],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get("/analyses/{analysis_id}", response_model=AnalysisOut)
def get_analysis(
    analysis_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AnalysisOut:
    row = db.get(Analysis, analysis_id)
    # Someone else's analysis returns 404, not 403: a 403 would confirm the id
    # exists, which is a small but real information leak.
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found.")
    return _to_out(row)


@router.delete("/analyses/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis(
    analysis_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    row = db.get(Analysis, analysis_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found.")
    db.delete(row)
    db.commit()


@router.post("/analyses/{analysis_id}/share", response_model=ShareResponse)
def share_analysis(
    analysis_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ShareResponse:
    row = db.get(Analysis, analysis_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found.")

    existing = db.scalar(select(SharedReport).where(SharedReport.analysis_id == row.id))
    if existing is not None:
        return ShareResponse(slug=existing.slug, url=f"/r/{existing.slug}")

    slug = secrets.token_urlsafe(9)
    db.add(SharedReport(slug=slug, analysis_id=row.id, report=row.report or {}))
    db.commit()
    return ShareResponse(slug=slug, url=f"/r/{slug}")


@router.get("/stats", response_model=StatsOut)
def stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StatsOut:
    total = db.scalar(select(func.count()).select_from(Analysis).where(Analysis.user_id == user.id))
    average = db.scalar(select(func.avg(Analysis.score)).where(Analysis.user_id == user.id))

    by_verdict: dict[str, int] = {}
    for verdict, count in db.execute(
        select(Analysis.verdict, func.count())
        .where(Analysis.user_id == user.id)
        .group_by(Analysis.verdict)
    ).all():
        by_verdict[verdict] = count

    week_ago = datetime.now(UTC) - timedelta(days=7)
    recent = db.scalar(
        select(func.count())
        .select_from(Analysis)
        .where(Analysis.user_id == user.id, Analysis.created_at >= week_ago)
    )

    return StatsOut(
        total_analyses=total or 0,
        average_score=round(float(average), 1) if average is not None else 0.0,
        by_verdict=by_verdict,
        last_7_days=recent or 0,
    )
