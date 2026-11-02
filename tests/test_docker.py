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
    return path.read_text(encoding="utf-8")


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
    assert 'CMD ["uvicorn", "euvsimulator.api.main:app"' in content, (
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


# ── Build checks for both Dockerfiles (still no image is built) ──────────────


def _logical_lines(text: str) -> list[str]:
    """Instructions with backslash continuations joined; comments and blanks dropped."""
    lines: list[str] = []
    buf = ""
    for raw in text.splitlines():
        stripped = raw.strip()
        if not buf and (not stripped or stripped.startswith("#")):
            continue
        if stripped.endswith("\\"):
            buf += stripped[:-1].strip() + " "
            continue
        lines.append((buf + stripped).strip())
        buf = ""
    if buf:
        lines.append(buf.strip())
    return lines


def _pip_install(line: str) -> tuple[list[str], list[str]] | None:
    """Split a RUN pip install instruction into (options, packages)."""
    tokens = line.split()
    if tokens[:3] != ["RUN", "pip", "install"]:
        return None
    options: list[str] = []
    packages: list[str] = []
    rest = iter(tokens[3:])
    for tok in rest:
        if tok in ("-i", "--index-url", "--extra-index-url"):
            options.append(tok + "=" + next(rest, ""))
        elif tok.startswith("-"):
            options.append(tok)
        else:
            packages.append(tok)
    return options, packages


@pytest.mark.parametrize("name", list(DOCKERFILES))
def test_pytorch_cpu_index_serves_torch_only(name: str) -> None:
    """The CPU-only PyTorch index may be used for torch and nothing else.

    --index-url replaces PyPI, and download.pytorch.org/whl/cpu answers 403
    for scipy, fastapi, uvicorn, typer, gdstk, matplotlib and wheel.  Up to
    2.2.1 both images installed every dependency (and the package itself)
    through that index, so neither image could be built.
    """
    torch_from_cpu_index = False
    for line in _logical_lines(_read_dockerfile(name)):
        parsed = _pip_install(line)
        if parsed is None:
            continue
        options, packages = parsed
        if any("download.pytorch.org" in opt for opt in options):
            assert packages == ["torch"], f"{name}: PyTorch index used for {packages}"
            torch_from_cpu_index = True
        else:
            assert "torch" not in packages, f"{name}: torch installed from PyPI (CUDA build)"
    assert torch_from_cpu_index, f"{name}: torch is not installed from the CPU-only index"


@pytest.mark.parametrize("name", list(DOCKERFILES))
def test_builder_copies_src_before_pip_install(name: str) -> None:
    """The builder stage must copy src/ before installing the package.

    pyproject.toml uses packages.find where=["src"]; without src/ the build
    stops with "'src' does not exist or is not a directory".  Up to 2.2.1 the
    builder copied only pyproject.toml and README.md.
    """
    lines = _logical_lines(_read_dockerfile(name))
    froms = [i for i, line in enumerate(lines) if line.split()[0].upper() == "FROM"]
    assert len(froms) >= 2, f"{name}: expected a builder and a runtime stage"
    builder = lines[froms[0] : froms[1]]
    copy_src = [i for i, line in enumerate(builder) if line.split()[:2] == ["COPY", "src/"]]
    install_dot: list[int] = []
    for i, line in enumerate(builder):
        parsed = _pip_install(line)
        if parsed is not None and "." in parsed[1]:
            install_dot.append(i)
    assert copy_src, f"{name}: builder stage does not copy src/"
    assert install_dot, f"{name}: builder stage does not install the package (pip install .)"
    assert copy_src[0] < install_dot[0], f"{name}: src/ is copied after pip install ."


# ── docker-compose content checks ─────────────────────────────────────────────


def test_compose_api_port() -> None:
    """docker-compose.yml maps port 8000 on the host's loopback only.

    The API has no authentication; SECURITY.md asks to publish it only to
    trusted networks.  (Before 2026-09-25 the mapping was "8000:8000", i.e.
    all host interfaces, and this test pinned that.)
    """
    text = COMPOSE_FILES["docker-compose.yml"].read_text(encoding="utf-8")
    assert '"127.0.0.1:8000:8000"' in text, "docker-compose.yml must bind 127.0.0.1:8000"


def test_compose_api_volume() -> None:
    """The CXRO data volume targets the directory materials.py actually reads.

    materials.DATA_DIR is <package>/data/cxro; the package is installed into
    site-packages of the python:3.11 image (not /app, where the former mount
    pointed and had no effect).
    """
    text = COMPOSE_FILES["docker-compose.yml"].read_text(encoding="utf-8")
    assert (
        "./src/euvsimulator/data:/usr/local/lib/python3.11/site-packages/euvsimulator/data" in text
    )


def test_compose_api_restart() -> None:
    """docker-compose.yml must set restart: unless-stopped."""
    text = COMPOSE_FILES["docker-compose.yml"].read_text(encoding="utf-8")
    assert "unless-stopped" in text, "docker-compose.yml missing restart: unless-stopped"


def test_compose_cli_interactive() -> None:
    """docker-compose.cli.yml must set stdin_open and tty for -it mode."""
    text = COMPOSE_FILES["docker-compose.cli.yml"].read_text(encoding="utf-8")
    assert "stdin_open" in text, "docker-compose.cli.yml missing stdin_open"
    assert "tty:" in text, "docker-compose.cli.yml missing tty"


# ── .dockerignore content checks ──────────────────────────────────────────────


def test_dockerignore_entries() -> None:
    """.dockerignore must ignore common patterns."""
    text = DOCKERIGNORE.read_text(encoding="utf-8")
    required = [".git", "__pycache__", "tests", "*.ipynb", ".env"]
    for pattern in required:
        assert pattern in text, f".dockerignore missing required entry: {pattern}"
