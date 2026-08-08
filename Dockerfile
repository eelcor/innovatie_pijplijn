# =============================================================================
# Innovatiepijplijn — Dockerfile
# Multi-stage build met uv voor snelle dependency installatie
# =============================================================================

# --- Stage 1: Builder ---
FROM python:3.11-slim AS builder

WORKDIR /app

# Installeer build dependencies (gcc nodig voor sommige Python packages)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Kopieer dependency files eerst voor beter Docker layer caching
COPY pyproject.toml uv.lock ./

# Installeer uv en sync dependencies
RUN pip install --no-cache-dir uv
RUN uv venv .venv
RUN uv sync --frozen --no-dev

# --- Stage 2: Runtime ---
FROM python:3.11-slim

WORKDIR /app

# Creëer non-root gebruiker voor security
RUN groupadd -r appuser && \
    useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Kopieer virtual environment van builder stage
COPY --from=builder /app/.venv /app/.venv

# Kopieer applicatie code
COPY app/ ./app/

# Creëer data directories voor SQLite, uploads en backups
RUN mkdir -p /app/data/uploads /app/data/backups && \
    chown -R appuser:appuser /app

# Schakel over naar non-root gebruiker
USER appuser

# Environment variabelen
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    APP_PORT=8000 \
    APP_HOST=0.0.0.0

EXPOSE ${APP_PORT}

# Health check via /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${APP_PORT}/health')" || exit 1

# Start de applicatie via uvicorn
CMD ["sh", "-c", "uvicorn app.main:app --host ${APP_HOST} --port ${APP_PORT}"]
