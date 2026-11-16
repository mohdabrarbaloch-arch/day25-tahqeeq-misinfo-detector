"""Public shared reports. No auth: the slug is the capability."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import SharedReport

router = APIRouter(prefix="/api/shared", tags=["shared"])


@router.get("/{slug}")
def get_shared(slug: str, db: Session = Depends(get_db)) -> dict:
    row = db.get(SharedReport, slug)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    row.views += 1
    db.commit()
    return {"slug": row.slug, "views": row.views, "report": row.report}
