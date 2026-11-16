# API Reference

Base URL in development: `http://127.0.0.1:8000`

Interactive docs (development only): `/docs`

---

## Authentication

JWT bearer tokens. Send `Authorization: Bearer <token>` on every protected
endpoint.

Tokens are HS256, valid for `ACCESS_TOKEN_TTL_MINUTES` (default 7 days), and
carry `sub` (user id), `iat`, `exp` and `typ`. A token with the wrong `typ` is
rejected, so a token minted for another purpose can't be replayed here.

### `POST /api/auth/register`

Creates an account and returns a token immediately, so the client never needs a
second round trip to get the user in.

```json
{ "email": "you@example.com", "password": "at-least-10-chars", "display_name": "Optional" }
```

**201** — `{ access_token, token_type, expires_in, user }`
**409** — email already registered
**422** — password under 10 characters, or a known-common password

### `POST /api/auth/login`

```json
{ "email": "you@example.com", "password": "..." }
```

**200** — same shape as register
**401** — `"That email or password is incorrect."`

The message is deliberately identical for a wrong email and a wrong password.
Distinguishing them would let anyone enumerate which addresses have accounts.

### `GET /api/auth/me`

**200** — the current user. **401** if the token is missing, expired or invalid.

---

## Analysis

All of these require authentication.

### `POST /api/analyze`

Score pasted text.

```json
{ "text": "...", "headline": "optional", "url": "optional, for the source prior" }
```

`text` is 20–60,000 characters. `url` is optional and only used to look up the
publisher prior — it is not fetched.

**201** — a full report (see below)
**422** — text too short, blank, or a malformed URL

### `POST /api/fetch`

Fetch a URL and return its extracted text, without scoring it. Useful for
letting a user review what was pulled before committing to an analysis.

```json
{ "url": "https://example.com/article" }
```

**200** — `{ url, final_url, title, text, word_count, truncated }`
**400** — private/internal address, non-HTML content, or a bad URL
**422** — the page had too little readable text
**502** — the site returned 5xx or was unreachable
**504** — the site timed out

### `POST /api/analyze-url`

Fetch and score in one call. Same request body as `/api/fetch`, same error codes,
returns a full report on **201**.

### `GET /api/analyses`

Your history, newest first.

| Query | Default | Range |
|---|---|---|
| `limit` | 20 | 1–100 |
| `offset` | 0 | ≥ 0 |

**200** — `{ items: [...], total, limit, offset }`

### `GET /api/analyses/{id}`

**200** — the full report. **404** if it doesn't exist *or belongs to someone
else*.

That 404 is deliberate. A 403 would confirm the id exists, which leaks a little
information for no benefit.

### `DELETE /api/analyses/{id}`

**204** on success, **404** if not yours. Cascades to any share link.

### `POST /api/analyses/{id}/share`

Creates a public read-only link, or returns the existing one if you've already
shared that report.

**200** — `{ slug, url }` where `url` is `/r/<slug>`

### `GET /api/stats`

**200** — `{ total_analyses, average_score, by_verdict, last_7_days }`

---

## Public

### `GET /api/shared/{slug}`

No authentication. Returns the frozen report snapshot and increments a view
counter.

**200** — `{ slug, views, report }`
**404** — unknown slug

### `GET /api/health`

**200** — `{ status, version, environment }`

---

## The report object

```json
{
  "id": "a1b2c3d4e5f6...",
  "headline": "SHOCKING: They don't want you to know...",
  "source_url": null,
  "score": 23.7,
  "confidence": 0.72,
  "verdict": "unreliable",
  "verdict_label": "Reads like misinformation",
  "word_count": 97,
  "sentence_count": 8,
  "reading_seconds": 26,
  "created_at": "2026-11-17T04:12:33.918Z",
  "domain": null,
  "notes": [
    "A high score means no warning signs were found in the writing. It does not mean the claims are true — Tahqeeq reads style and sourcing, not facts."
  ],
  "signals": [
    {
      "id": "share_pressure",
      "label": "Share pressure",
      "weight": 1.2,
      "severity": 1.0,
      "applicable": true,
      "points_lost": 100.0,
      "explanation": "1 instruction(s) to share or forward. Journalism does not ask you to redistribute it before it is deleted.",
      "evidence": ["SHARE THIS BEFORE THEY DELETE IT"]
    }
  ]
}
```

### Field notes

- **`signals`** always contains all 11 signals, in a fixed order. Check
  `applicable` before using `severity` — an inapplicable signal has a severity of
  0 that means "not assessed", not "clean".
- **`points_lost`** is the actual deduction after weighting and the worst-signal
  blend. It's what you should sort by to find what mattered.
- **`evidence`** holds the exact matched phrases, capped at 8 per signal.
- **`domain`** is `null` when no URL was supplied. When present it carries
  `{ domain, known, label, prior, notes, is_shortener }`.
- **`notes`** carries the caveats. A high score always includes the "not a truth
  score" note.

---

## Errors

Every error is `{ "detail": "..." }` with a human-readable message. Validation
errors are flattened into a single string rather than pydantic's nested
structure, so the front end can display them directly.

| Status | Meaning |
|---|---|
| 400 | Bad request — malformed URL, private address, non-HTML content |
| 401 | Missing, expired or invalid token |
| 404 | Not found, or not yours |
| 409 | Conflict — email already registered |
| 422 | Validation failed |
| 429 | Rate limited — check the `Retry-After` header |
| 502 | Upstream site unreachable or returned 5xx |
| 504 | Upstream site timed out |

---

## Rate limits

Two sliding windows, per client IP:

- `RATE_LIMIT_PER_MINUTE` (default 60) on auth and analysis routes
- `ANALYZE_RATE_LIMIT_PER_MINUTE` (default 20) on the analysis router

A 429 includes `Retry-After` in seconds.

**These are per-process.** Behind multiple workers each keeps its own counter,
so the effective limit multiplies by the worker count. Redis is the fix; the
limiter is a single class in `app/deps.py`.

---

## Security headers

Every response carries:

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
Cross-Origin-Opener-Policy: same-origin
Content-Security-Policy: default-src 'self'; ...
```

In production, `Strict-Transport-Security` is added.
