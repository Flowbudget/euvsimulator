"""Verify Docker configuration files exist and have valid syntax.

These tests check file contents only — they do NOT build any images.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DOCKERFILES = {
    "Dockerfile": PROJECT_ROOT / "Dockerfile",
    "Dockerfile.cli": PROJECT_ROOT / "Dockerfile.cli",
}

COMPOSE_FILES = {
    "docker-compose.yml": PROJECT_ROOT / "docker-compose.yml",
    "docker-compose.cli.yml": PROJECT_ROOT / "docker-compose.cli.yml",
}

DOCKERIGNORE = PROJECT_ROOT / ".dockerignore"


# ── File existence ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name,path", list(DOCKERFILES.items()))
def test_dockerfile_exists(name: str, path: Path) -> None:
    """Each Dockerfile must exist and be non-empty."""
    assert path.is_file(), f"{name} not found at {path}"
    assert path.stat().st_size > 0, f"{name} is empty"


@pytest.mark.parametrize("name,path", list(COMPOSE_FILES.items()))
def test_compose_file_exists(name: str, path: Path) -> None:
    """Each docker-compose file must exist and be non-empty."""
    assert path.is_file(), f"{name} not found at {path}"
    assert path.stat().st_size > 0, f"{name} is empty"


def test_dockerignore_exists() -> None:
    """.dockerignore must exist and be non-empty."""
    assert DOCKERIGNORE.is_file(), f".dockerignore not found at {DOCKERIGNORE}"
    assert DOCKERIGNORE.stat().st_size > 0, ".dockerignore is empty"


# ── Dockerfile content checks ─────────────────────────────────────────────────


def _read_dockerfile(name: str) -> str:
    path = DOCKERFILES[name]
    return path.read_text()


def test_dockerfile_multi_stage() -> None:
    """Dockerfile must have at least two stages (builder + runtime)."""
    content = _read_dockerfile("Dockerfile")
    stages = re.findall(r"^FROM\s+\S+", content, re.MULTILINE)
    assert len(stages) >= 2, (
        f"Expected at least 2 FROM statements (builder + runtime), found {len(stages)}: {stages}"
    )


def test_dockerfile_python_311_slim() -> None:
    """All stages must use python:3.11-slim as the base image."""
    content = _read_dockerfile("Dockerfile")
    bases = re.findall(r"^FROM\s+(\S+)", content, re.MULTILINE)
    for base in bases:
        assert base == "python:3.11-slim", f"Stage uses {base!r} instead of python:3.11-slim"


def test_dockerfile_has_correct_cmd() -> None:
    """Dockerfile must end with the expected uvicorn CMD."""
    content = _read_dockerfile("Dockerfile")
    assert 'CMD ["uvicorn", "euv.api.main:app"' in content, (
        "Dockerfile missing or has wrong CMD for uvicorn"
    )


def test_dockerfile_installs_required_packages() -> None:
    """Dockerfile must install all required packages."""
    content = _read_dockerfile("Dockerfile")
    required = [
        "numpy",
        "scipy",
        "torch",
        "fastapi",
        "uvicorn",
        "pydantic",
        "httpx",
        "typer",
        "gdstk",
        "matplotlib",
    ]
    for pkg in required:
        assert pkg in content, f"Dockerfile does not reference required package: {pkg}"


def test_dockerfile_torch_cpu_index() -> None:
    """Dockerfile must use the CPU-only PyTorch index URL."""
    content = _read_dockerfile("Dockerfile")
    assert "download.pytorch.org/whl/cpu" in content, (
        "Dockerfile missing CPU-only PyTorch index URL"
    )


def test_dockerfile_exposes_port() -> None:
    """Dockerfile must expose port 8000."""
    content = _read_dockerfile("Dockerfile")
    assert "EXPOSE 8000" in content, "Dockerfile missing EXPOSE 8000"


# ── Dockerfile.cli content checks ─────────────────────────────────────────────


def test_cli_dockerfile_exists() -> None:
    """Dockerfile.cli must exist and be non-empty."""
    text = _read_dockerfile("Dockerfile.cli")
    assert len(text) > 0


def test_cli_dockerfile_python_311_slim() -> None:
    """Dockerfile.cli must use python:3.11-slim."""
    content = _read_dockerfile("Dockerfile.cli")
    bases = re.findall(r"^FROM\s+(\S+)", content, re.MULTILINE)
    for base in bases:
        assert base == "python:3.11-slim", f"CLI stage uses {base!r} instead of python:3.11-slim"


def test_cli_dockerfile_correct_cmd() -> None:
    """Dockerfile.cli CMD must show CLI help."""
    content = _read_dockerfile("Dockerfile.cli")
    assert 'CMD ["euv", "simulate", "--help"]' in content, "Dockerfile.cli missing or has wrong CMD"


def test_cli_dockerfile_no_uvicorn() -> None:
    """Dockerfile.cli must NOT install uvicorn (smaller image)."""
    content = _read_dockerfile("Dockerfile.cli")
    # uvicorn might appear in the pip install list, but it shouldn't be in the
    # explicit package list. Instead, check that all required CLI packages are
    # present and uvicorn is absent from the explicit install.
    # We allow it in comments or pip install lines only if it's not explicitly
    # listed as a standalone package.
    lines = content.splitlines()
    uvicorn_in_install = any(
        "uvicorn" in line and line.strip().startswith("RUN pip") for line in lines
    )
    assert not uvicorn_in_install, (
        "Dockerfile.cli should not install uvicorn — it's a CLI-only image"
    )


# ── docker-compose content checks ─────────────────────────────────────────────


def test_compose_api_port() -> None:
    """docker-compose.yml must map port 8000."""
    text = COMPOSE_FILES["docker-compose.yml"].read_text()
    assert '"8000:8000"' in text or "'8000:8000'" in text or "8000:8000" in text, (
        "docker-compose.yml missing port mapping 8000:8000"
    )


def test_compose_api_volume() -> None:
    """docker-compose.yml must have a volume for CXRO data."""
    text = COMPOSE_FILES["docker-compose.yml"].read_text()
    assert "euv/data" in text, "docker-compose.yml missing CXRO data volume mount"


def test_compose_api_restart() -> None:
    """docker-compose.yml must set restart: unless-stopped."""
    text = COMPOSE_FILES["docker-compose.yml"].read_text()
    assert "unless-stopped" in text, "docker-compose.yml missing restart: unless-stopped"


def test_compose_cli_interactive() -> None:
    """docker-compose.cli.yml must set stdin_open and tty for -it mode."""
    text = COMPOSE_FILES["docker-compose.cli.yml"].read_text()
    assert "stdin_open" in text, "docker-compose.cli.yml missing stdin_open"
    assert "tty:" in text, "docker-compose.cli.yml missing tty"


# ── .dockerignore content checks ──────────────────────────────────────────────


def test_dockerignore_entries() -> None:
    """.dockerignore must ignore common patterns."""
    text = DOCKERIGNORE.read_text()
    required = [".git", "__pycache__", "tests", "*.ipynb", ".env"]
    for pattern in required:
        assert pattern in text, f".dockerignore missing required entry: {pattern}"
