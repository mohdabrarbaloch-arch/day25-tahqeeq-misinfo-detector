FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# lxml needs libxml2/libxslt at build time; curl is for the healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential libxml2-dev libxslt1-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Dependencies first so the layer caches across code changes.
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir .

# Drop the build toolchain from the runtime image.
RUN apt-get purge -y --auto-remove build-essential libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Run as a non-root user. A container that can write to its own code is a
# container that can be turned into a webshell.
RUN useradd --create-home --uid 10001 tahqeeq \
    && mkdir -p /data \
    && chown -R tahqeeq:tahqeeq /app /data
USER tahqeeq

ENV DATABASE_URL=sqlite:////data/tahqeeq.db \
    ENVIRONMENT=production \
    PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 2 --proxy-headers --forwarded-allow-ips='*'"]
