# Multi-stage production Dockerfile for QueryForge
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency definition
COPY pyproject.toml .

# Install dependencies into virtualenv
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir hatchling && \
    /opt/venv/bin/pip install --no-cache-dir \
        fastapi \
        uvicorn[standard] \
        pydantic \
        pydantic-settings \
        sqlalchemy[asyncio] \
        greenlet \
        asyncpg \
        aiosqlite \
        sqlglot \
        chromadb \
        httpx \
        pandas \
        python-dotenv \
        cryptography

# Runtime stage
FROM python:3.12-slim AS runner

WORKDIR /app

# Create non-root execution user and persistent storage directories
RUN groupadd -r queryforge && useradd -r -g queryforge queryforge && \
    mkdir -p /app/chroma_db && chown -R queryforge:queryforge /app

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source code
COPY --chown=queryforge:queryforge app /app/app
COPY --chown=queryforge:queryforge scripts /app/scripts
COPY --chown=queryforge:queryforge pyproject.toml /app/

# Set environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_PORT=8000

USER queryforge

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
