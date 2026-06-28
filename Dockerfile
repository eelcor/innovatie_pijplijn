# --- Build stage ---
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock ./

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

# Create virtual environment and install dependencies
RUN uv venv .venv
RUN uv sync --frozen

# --- Runtime stage ---
FROM python:3.11-slim

WORKDIR /app

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY app/ ./app/

# Create data directories for SQLite and uploads
RUN mkdir -p /app/data/uploads && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    APP_PORT=8000 \
    APP_HOST=0.0.0.0

EXPOSE ${APP_PORT}

# Health check — uses /health endpoint (consistent with docker-compose)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${APP_PORT}/health')" || exit 1

# Run with uvicorn, reading host/port from environment
CMD ["sh", "-c", "uvicorn app.main:app --host ${APP_HOST} --port ${APP_PORT}"]
