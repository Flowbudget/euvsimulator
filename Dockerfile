# =============================================================================
# OpEnUV — Multi-stage Docker build
# =============================================================================
# Stage 1: Builder — install all dependencies (including CPU-only PyTorch)
# Stage 2: Runtime — copy installed deps + source, serve via uvicorn
# =============================================================================

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build-system tools needed by the package
RUN pip install --no-cache-dir setuptools wheel

# Copy dependency metadata first (leverages Docker layer caching)
COPY pyproject.toml README.md ./

# Install all runtime dependencies including CPU-only PyTorch
# The --index-url ensures torch is CPU-only (no CUDA runtime)
RUN pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    numpy scipy torch fastapi uvicorn pydantic httpx typer gdstk matplotlib

# Install the package itself (deps are already satisfied, so this is fast)
RUN pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    .

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy installed packages from the builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source code
COPY src/ ./src/

# CXRO data directory (bind-mounted at runtime, but create the path)
RUN mkdir -p /app/euv/data

# Expose the FastAPI port
EXPOSE 8000

# Default command: serve the REST API
CMD ["uvicorn", "euv.api.main:app", "--host", "0.0.0.0", "--port", "8000"]