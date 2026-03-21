# ── Stage 1: dependency installation ─────────────────────────────────────────
FROM python:3.12-slim AS builder

# Install uv
RUN pip install --no-cache-dir uv

WORKDIR /app

# Install system dependencies required by osmnx / libspatialindex
RUN apt-get update && apt-get install -y --no-install-recommends \
    libspatialindex-dev \
    libgeos-dev \
    libproj-dev \
    gdal-bin \
    libgdal-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifest and install all dependencies into a local venv
COPY pyproject.toml ./
RUN uv venv /app/.venv && \
    uv pip install --python /app/.venv/bin/python -e ".[dev]" --no-cache

# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Install runtime-only system libs (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libspatialindex-dev \
    libgeos-dev \
    libproj-dev \
    gdal-bin \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Bring the pre-built venv from the builder stage
COPY --from=builder /app/.venv /app/.venv

# Make venv binaries the default python / pip
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy application source
COPY . .

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
