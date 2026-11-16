# Setup

Everything you need to get Tahqeeq running locally, plus the things that
usually go wrong.

---

## Requirements

- **Python 3.11 or newer.** The code uses `X | Y` type syntax and `datetime.UTC`,
  both of which need 3.10+; 3.11 is what it's tested on.
- **No database server needed.** SQLite is the default and the file is created
  on first run.
- Optional: **Docker** if you'd rather not install Python at all.

---

## Local install

```bash
git clone https://github.com/mohdabrarbaloch-arch/day25-tahqeeq-misinfo-detector.git
cd day25-tahqeeq-misinfo-detector

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -e ".[dev]"
```

### Configure

```bash
cp .env.example .env
```

Then generate a signing key and append it:

```bash
python -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(48))" >> .env
```

You can skip this in development — the app generates an ephemeral key — but
every restart will sign you out, which gets annoying fast.

### Seed and run

```bash
python -m app.seed
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>.

`python -m app.seed` creates the demo account and three sample reports so the
history view isn't empty on first look. It's idempotent — running it twice does
nothing the second time.

---

## Docker

```bash
echo "JWT_SECRET=$(python -c 'import secrets; print(secrets.token_urlsafe(48))')" > .env
docker compose up --build
```

The compose file refuses to start without `JWT_SECRET` — that's deliberate, not
a bug. It brings up PostgreSQL 16 and the app on port 8000.

To seed inside the container:

```bash
docker compose exec app python -m app.seed
```

---

## Running the tests

```bash
pytest                    # 61 tests, no network access required
pytest -v                 # per-test output
pytest tests/test_scoring.py   # just the engine
```

The suite sets its own environment before importing the app, so it never
touches your development database. It uses a throwaway SQLite file in a temp
directory.

## Lint and format

```bash
ruff check .
ruff format --check .
ruff format .             # apply
```

Both must pass cleanly. The config lives in `pyproject.toml`.

---

## Troubleshooting

**`RuntimeError: JWT_SECRET is not set.`**
You're running with `ENVIRONMENT=production` and no key. Either set one or drop
back to `ENVIRONMENT=development`. This is intentional — a production deploy
with a generated default key would silently invalidate every session on restart.

**`RuntimeError: JWT_SECRET must be at least 32 characters`**
Your key is too short for HS256 to be meaningful. Regenerate with the command
above.

**Every login returns 401 after a restart.**
You're in development with no `JWT_SECRET`, so a fresh ephemeral key is minted
per process. Set a real one in `.env`.

**`/docs` returns 404.**
Expected in production. The interactive docs are disabled there on purpose —
they're an information-disclosure surface you don't want on a public deploy.

**Fetching a URL fails with "That address is private or internal".**
The SSRF guard is working. It refuses loopback, private, link-local and
reserved addresses, and it re-checks every redirect hop. If you genuinely need
to fetch a local address in a test environment, set `ALLOW_PRIVATE_FETCH=true`
— and never in production.

**Fetching a real article fails with "not enough readable text".**
The page is probably paywalled, or it renders its body with JavaScript so the
HTML we receive is mostly empty. Paste the text instead.

**`lxml` fails to build.**
It needs `libxml2-dev` and `libxslt1-dev` (Debian/Ubuntu) or `libxml2` and
`libxslt` (macOS, via Homebrew). The Dockerfile installs these for you.

**Rate limit hit while testing.**
Raise `RATE_LIMIT_PER_MINUTE` and `ANALYZE_RATE_LIMIT_PER_MINUTE` in `.env`.
The test suite sets both to 10000 for exactly this reason.
