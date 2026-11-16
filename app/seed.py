"""Seed the demo account and a handful of real sample reports.

Run with: python -m app.seed

Idempotent: running it twice does not duplicate anything. The samples are
written to be genuinely instructive — one clean wire-style report, one
WhatsApp forward, one plausible-but-unsourced blog post — so a new user can see
the difference the signals actually make.
"""

from __future__ import annotations

import sys

from sqlalchemy import select

from app.analysis.scoring import analyse
from app.db import SessionLocal, init_db
from app.models import Analysis, User
from app.security import hash_password

DEMO_EMAIL = "demo@tahqeeq.app"
DEMO_PASSWORD = "tahqeeq-demo-2026"

SAMPLES: list[dict] = [
    {
        "headline": "State Bank holds policy rate at 11 percent as inflation eases",
        "url": "https://www.dawn.com/news/1234567",
        "text": (
            "Pakistan's central bank held its policy rate at 11 percent on Monday, "
            "citing easing inflation.\n\n"
            "The State Bank of Pakistan said in a statement that inflation had slowed "
            'to 4.9 percent in October from 6.2 percent a month earlier. "We expect '
            'inflation to remain within the target range over the coming quarters," '
            "Governor Jameel Ahmad told reporters in Karachi.\n\n"
            "According to the bank's monetary policy report published on 10 November "
            "2026, food prices rose 3.1 percent while core inflation held at 7.4 "
            "percent. Analysts at Topline Securities said the decision was widely "
            "expected.\n\n"
            "The next policy meeting is scheduled for 15 December 2026."
        ),
    },
    {
        "headline": "SHOCKING: They don't want you to know the REAL truth about Karachi",
        "url": None,
        "text": (
            "SHOCKING!!! They don't want you to know the REAL truth about what "
            "happened in Karachi last night!!!\n\n"
            "A friend of a senior official has revealed that a MASSIVE cover-up is "
            "underway. Sources say that thousands of people were affected but the "
            "mainstream media won't report it. This is UNDENIABLE proof that the deep "
            "state is hiding everything from you.\n\n"
            "Experts say this is the biggest scandal in the country's history and "
            "nobody is talking about it. The government has completely destroyed the "
            "evidence. It is being reported that the real number is in the millions.\n\n"
            "SHARE THIS BEFORE THEY DELETE IT!!! Forward to everyone you know. Do your "
            "own research. Wake up before it's too late!"
        ),
    },
    {
        "headline": "New study links city air quality to childhood asthma rates",
        "url": "https://example.blogspot.com/air-quality-asthma",
        "text": (
            "A new study has found a strong link between air quality and childhood "
            "asthma in large cities.\n\n"
            "Researchers looked at data from several hospitals over a period of years "
            "and concluded that children in more polluted areas were significantly "
            "more likely to be diagnosed. The findings were described as important by "
            "people familiar with the work.\n\n"
            "Many experts believe this could change how cities think about transport "
            "policy. It is being reported that thousands of families are affected "
            "every year.\n\n"
            "The study has not yet been published in a peer-reviewed journal."
        ),
    },
]


def seed() -> int:
    init_db()
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        if user is None:
            user = User(
                email=DEMO_EMAIL,
                password_hash=hash_password(DEMO_PASSWORD),
                display_name="Demo account",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"created demo user {DEMO_EMAIL}")
        else:
            print(f"demo user {DEMO_EMAIL} already exists")

        existing = db.scalar(select(Analysis).where(Analysis.user_id == user.id).limit(1))
        if existing is not None:
            print("sample reports already present, nothing to do")
            return 0

        for sample in SAMPLES:
            result = analyse(sample["text"], headline=sample["headline"], url=sample["url"])
            db.add(
                Analysis(
                    user_id=user.id,
                    headline=result.headline[:500],
                    source_url=sample["url"],
                    text_excerpt=sample["text"][:600],
                    text_chars=len(sample["text"]),
                    score=result.score,
                    confidence=result.confidence,
                    verdict=result.verdict,
                    verdict_label=result.verdict_label,
                    word_count=result.word_count,
                    sentence_count=result.sentence_count,
                    reading_seconds=result.reading_seconds,
                    report=result.to_dict(),
                )
            )
            print(f"  seeded: {result.score:5.1f}  {result.verdict:14s}  {result.headline[:60]}")

        db.commit()
        print(f"seeded {len(SAMPLES)} sample reports")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(seed())
