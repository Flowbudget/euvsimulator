# =============================================================================
# euvsimulator — Multi-stage Docker build
# =============================================================================
# Stage 1: Builder — install all dependencies (including CPU-only PyTorch) and
#          the package from the local src/
# Stage 2: Runtime — copy the installed site-packages, serve via uvicorn
#
# arm64 hosts (Apple Silicon, Raspberry Pi): gdstk publishes Linux wheels for
# x86_64 only, so pip would build it from source, and python:3.11-slim has no
# C++ compiler.  Build the amd64 image there under emulation instead (Docker
# Desktop emulates amd64; on a plain Linux host register QEMU binfmt first):
#   docker build --platform linux/amd64 -t euvsimulator-api -f Dockerfile .
# =============================================================================

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build-system tools needed by the package
RUN pip install --no-cache-dir setuptools wheel

# Copy dependency metadata first (leverages Docker layer caching)
COPY pyproject.toml README.md ./

# CPU-only PyTorch (no CUDA runtime). --index-url replaces PyPI, and the
# PyTorch index hosts only torch and its own dependencies, so nothing else
# may be installed through it.
RUN pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    torch

# Remaining runtime dependencies from PyPI (torch is already satisfied)
RUN pip install --no-cache-dir \
    numpy scipy fastapi uvicorn pydantic httpx typer gdstk matplotlib

# pyproject.toml finds the package under src/ (packages.find where=["src"]),
# so src/ must be in this stage before the package is installed
COPY src/ ./src/

# Install the package itself from the local src/ (deps are already satisfied)
RUN pip install --no-cache-dir .

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy installed packages from the builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# No source copy here: the package, its data and the GUI's static files are
# installed in site-packages above, and /app/src would not be on sys.path

# The package reads its data from site-packages/euvsimulator/data, which is
# where docker-compose.yml mounts the host data

# Expose the FastAPI port
EXPOSE 8000

# Default command: serve the REST API
CMD ["uvicorn", "euvsimulator.api.main:app", "--host", "0.0.0.0", "--port", "8000"]