# Architecture

## What this is

Tahqeeq scores a piece of writing for the signals that distinguish reporting
from misinformation — sourcing, certainty, share pressure, structure — and shows
every reason behind the score.

The design constraint that shapes everything: **the user must be able to check
the answer.** A number with no explanation is just a second opinion you have to
take on faith, which is the problem this tool exists to solve.

---

## System diagram

```
                          ┌──────────────────────────┐
                          │   Browser (vanilla JS)   │
                          │  index.html / app.js     │
                          │  app.css — no build step │
                          └────────────┬─────────────┘
                                       │ fetch() + Bearer token
                                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                        FastAPI application                       │
│                                                                  │
│  middleware:  security headers  →  CORS  →  rate limiter         │
│                                                                  │
│  ┌────────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────┐  │
│  │ /api/auth  │  │ /api/analyze │  │ /api/fetch │  │ /api/    │  │
│  │ register   │  │ analyze-url  │  │  (SSRF     │  │ shared   │  │
│  │ login      │  │ analyses     │  │   guard)   │  │ (public) │  │
│  │ me         │  │ stats, share │  │            │  │          │  │
│  └─────┬──────┘  └──────┬───────┘  └─────┬──────┘  └────┬─────┘  │
│        │                │                │              │        │
│        │                ▼                │              │        │
│        │      ┌───────────────────┐      │              │        │
│        │      │  analysis engine  │      │              │        │
│        │      │  (pure functions) │      │              │        │
│        │      │                   │      │              │        │
│        │      │  text.py  ──► stats, sentences, markup   │        │
│        │      │  lexicon.py ─► word lists, patterns      │        │
│        │      │  signals.py ─► 11 signal functions       │        │
│        │      │  sources.py ─► domain prior              │        │
│        │      │  scoring.py ─► blend, verdict, report    │        │
│        │      └─────────┬─────────┘      │              │        │
│        │                │                │              │        │
│        ▼                ▼                ▼              ▼        │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │              SQLAlchemy 2.0 ORM  (models.py)             │    │
│  │   users  ·  analyses (report JSON)  ·  shared_reports    │    │
│  └──────────────────────────┬───────────────────────────────┘    │
└─────────────────────────────┼────────────────────────────────────┘
                              ▼
              ┌───────────────────────────────┐
              │  SQLite (default)             │
              │  PostgreSQL (docker-compose)  │
              └───────────────────────────────┘
```

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI | Async, Pydantic validation, OpenAPI for free |
| Validation | Pydantic v2 | Bounds live in the schema, so bad input never reaches the engine |
| ORM | SQLAlchemy 2.0 | Typed `Mapped[]` models, works on SQLite and Postgres unchanged |
| Auth | PyJWT + bcrypt | Direct, no passlib — it's unmaintained and breaks on bcrypt 4.x |
| Fetching | httpx + BeautifulSoup/lxml | Manual redirect handling, which the SSRF guard requires |
| Front end | Vanilla JS + one CSS file | No build step, no framework, no dependency tree to audit |
| Tests | pytest | 61 tests, no network |
| Lint | ruff | Check and format, both clean |

---

## Data flow: scoring a pasted article

```
1. POST /api/analyze  { text, headline?, url? }
2. Pydantic validates: 20 ≤ len(text) ≤ 60,000, url normalised
3. get_current_user resolves the Bearer token → User row
4. analyse(text, headline, url)  — pure, no I/O, no DB
     a. normalise()      collapse whitespace, strip zero-width chars
     b. strip_markup()   remove any HTML the user pasted
     c. stats()          word/sentence counts, caps ratio, punctuation density
     d. build SignalContext once, share it across all 11 signals
     e. run each signal function → Signal(id, weight, severity, applicable, evidence)
     f. drop inapplicable signals from the denominator
     g. weighted mean severity  →  raw score
     h. blend with the worst signal (65/35)  →  final score
     i. apply the domain prior if a URL was given
     j. cap at 98 — no automated check claims certainty
     k. map score → verdict band, attach notes
5. Persist: score, verdict, and the FULL report JSON
6. Return the report
```

Step 4 is a pure function. That's what makes the engine testable without a
database, a network, or a fixture — and it's why the test suite runs in under
four seconds.

---

## The scoring model

### Signals

Eleven functions, each returning a `Signal` with a fixed weight:

```
attribution 1.4 · conspiracy 1.3 · sensationalism 1.2 · share_pressure 1.2
headline 1.1 · certainty 1.0 · forward_markers 1.0 · anonymous_sourcing 0.9
quotes 0.8 · vague_quantities 0.7 · structure 0.6
```

Weights encode how diagnostic each signal is. Attribution is the strongest
single indicator of real reporting; structure is the weakest, because plenty of
legitimate writing is badly formatted.

### Three decisions that matter

**1. Inapplicable signals are excluded, not zeroed.**

A 30-word snippet can't be assessed for attribution. Scoring it 0 would read as
"no attribution problems" and inflate the result. Instead it's dropped from the
weighted mean and marked *not assessed* in the report.

**2. The mean is blended with the worst finding, 65/35.**

```
raw    = Σ(weight × severity) / Σ(weight)      over applicable signals
worst  = max(severity)                          over applicable signals
blend  = 0.65 × raw + 0.35 × worst
score  = 100 × (1 − blend)
```

A pure mean lets one damning signal be diluted by ten clean ones — a text whose
only flaw is "share this before they delete it" would still score in the 80s. A
pure maximum is equally wrong: one false positive would sink an honest article.
The blend keeps a single severe finding decisive without letting a single mild
one dominate.

**3. Confidence is separate from score.**

Confidence reflects how much text was available, not how sure the engine is
about the truth. Conflating the two is how a tool ends up confidently wrong
about a headline. Below `MIN_WORDS_FOR_CONFIDENCE` the report is marked
provisional.

### On source reputation

There is **no denylist of named outlets** in this codebase, and that's a
deliberate design decision rather than an omission.

Calling a specific publication a fake-news site is a factual claim this tool
cannot verify. Getting it wrong would be defamation with a database attached,
and it would make the score depend on editorial opinion rather than on the text.

Instead:

- A small allowlist of outlets with published editorial standards gets a modest
  positive prior.
- Everything else is judged on **structural** properties — free blog host, URL
  shortener, throwaway TLD — reported as observations, not verdicts.
- An unknown domain gets a **neutral** prior. Not knowing a domain is not
  evidence against it.

---

## Data model

```
users
  id (pk) · email (unique) · password_hash · display_name · created_at

analyses
  id (pk) · user_id (fk → users, cascade) · headline · source_url
  text_excerpt · text_chars
  score · confidence · verdict · verdict_label
  word_count · sentence_count · reading_seconds
  report (JSON)  ← the full frozen report
  created_at
  index (user_id, created_at)

shared_reports
  slug (pk) · analysis_id (fk → analyses, cascade) · report (JSON)
  created_at · views
```

**Why the report is stored as JSON.** The engine's weights will change. If the
history view re-ran the engine, yesterday's report would silently become a
different report. Storing the snapshot means the evidence a user saw is the
evidence they see later — and it makes the share link a true snapshot rather
than a live view.

**Why `shared_reports` copies the report.** So deleting an analysis kills its
public link. A foreign key with `ON DELETE CASCADE` does that in one statement.

---

## Security

### SSRF guard (`app/fetcher.py`)

The only code that makes an outbound request on a user's behalf, so it's the
only place that needs this.

- The hostname is **resolved**, and every returned address is checked against
  private, loopback, link-local, reserved and multicast ranges **before**
  connecting. Checking the string `"localhost"` is not enough — `127.0.0.1`,
  `0.0.0.0`, `[::1]` and a DNS record pointing at `169.254.169.254` all reach
  the same place.
- **Redirects are followed manually**, re-validating each hop. httpx's automatic
  redirect following would happily walk from a public URL to the cloud metadata
  service.
- URLs with embedded credentials are refused.
- Response bodies are capped at `FETCH_MAX_BYTES`.

### Other measures

| Concern | Handling |
|---|---|
| Password storage | bcrypt, cost 12, rejects >72 bytes rather than truncating |
| Token forgery | HS256, `typ` claim checked, `exp`/`sub`/`iat` required |
| Account enumeration | Identical 401 for wrong email and wrong password |
| IDOR | Ownership mismatch returns 404, not 403 |
| XSS | Front end uses `textContent` and DOM nodes, never `innerHTML` |
| Clickjacking | `X-Frame-Options: DENY` + `frame-ancestors 'none'` |
| Secret leakage | Env only; production refuses to start without a real key |
| Abuse | Sliding-window rate limits on auth and analysis |

---

## Scaling notes

Honest about what breaks first, in order:

**1. Rate limiting is per-process.** Behind N workers the effective limit is
N × the configured value. Fix: move `SlidingWindowLimiter` to Redis. It's one
class with one method.

**2. The engine is CPU-bound and runs in the request.** Fine to a few hundred
requests a minute. Beyond that, move scoring to a worker queue and return 202.
The engine is already a pure function, so it moves without changes.

**3. `create_all()` is not migrations.** Fine for one deploy, wrong for evolving
a schema. Alembic is the fix.

**4. SQLite writes serialize.** Fine for a single instance. Postgres is already
supported — set `DATABASE_URL`.

**5. The fetcher is synchronous.** A slow site holds a worker. Moving it to
`httpx.AsyncClient` is a contained change.

**6. No caching.** The same URL fetched twice does the work twice. A short-TTL
cache keyed on the URL would cut both latency and outbound traffic.

---

## Testing strategy

| File | Covers |
|---|---|
| `test_scoring.py` | Engine behaviour: separation, exclusion, the worst-signal blend, caveats |
| `test_text.py` | Sentence splitting around abbreviations, normalisation, stats |
| `test_fetcher.py` | SSRF guard — every bypass class |
| `test_api.py` | Status codes, auth boundaries, ownership, headers |

The scoring tests assert *behaviour that would be a bug if it changed* — that
clean text outscores misleading text by a wide margin, that a short snippet
doesn't get scored clean on attribution, that one damning signal can't be
averaged away. They don't assert exact scores, which would make every weight
tweak a test failure.

---

## Known limitations

- **Style, not facts.** A well-written lie with named sources scores well.
- **English only.** No Urdu or Roman-Urdu lexicons yet.
- **Gameable.** Anyone who reads the signal list can write around it.
- **No migrations, no worker queue, no cache, per-process rate limits.**
  Documented above rather than hidden.
