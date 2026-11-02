"""Regression guard: Docker build on arm64 hosts and stale comments.

These tests read files only; they do NOT build any image.

gdstk publishes Linux wheels for x86_64 only (see uv.lock), so on an arm64
host pip falls back to the sdist, which needs a C++ toolchain that
python:3.11-slim lacks.  Until the Dockerfiles install one for non-amd64
builds, each Dockerfile must tell the reader how to build there.
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


def _gdstk_wheels() -> list[str]:
    """Wheel file names that uv.lock records for gdstk."""
    text = (PROJECT_ROOT / "uv.lock").read_text(encoding="utf-8")
    blocks = text.split("[[package]]")
    gdstk = [b for b in blocks if re.search(r'^name = "gdstk"$', b, re.MULTILINE)]
    assert len(gdstk) == 1, "uv.lock: expected exactly one gdstk package entry"
    return re.findall(r"gdstk-[^\"/]+\.whl", gdstk[0])


def _stages(text: str) -> list[str]:
    """Split a Dockerfile into its stages (text from one FROM to the next)."""
    parts = re.split(r"^(?=FROM\s)", text, flags=re.MULTILINE)
    return [p for p in parts if p.startswith("FROM")]


def test_gdstk_has_no_linux_aarch64_wheel() -> None:
    """Precondition of the arm64 checks below: no Linux aarch64 wheel for gdstk.

    If a future gdstk ships one, this test fails and the arm64 note in the
    Dockerfiles can go.
    """
    wheels = _gdstk_wheels()
    assert wheels, "uv.lock lists no gdstk wheels"
    assert any("x86_64" in w and "linux" in w for w in wheels)
    assert not any("linux" in w and "aarch64" in w for w in wheels)


@pytest.mark.parametrize("name", list(DOCKERFILES))
def test_arm64_build_path_documented(name: str) -> None:
    """An arm64 host must find a working build path in the Dockerfile.

    Either the builder stage installs a C++ toolchain on non-amd64
    architectures (dpkg --print-architecture), or the file documents the
    amd64 emulation route (docker build --platform linux/amd64).
    """
    text = DOCKERFILES[name].read_text(encoding="utf-8")
    builder = _stages(text)[0]
    arch_gated_toolchain = "dpkg --print-architecture" in builder and "g++" in builder
    documented_emulation = "--platform linux/amd64" in text
    assert arch_gated_toolchain or documented_emulation, (
        f"{name}: gdstk has no Linux aarch64 wheel, and neither a non-amd64 C++ toolchain "
        "nor the --platform linux/amd64 route is given"
    )


@pytest.mark.parametrize("name", list(DOCKERFILES))
def test_comments_match_instructions(name: str) -> None:
    """Comments must not describe steps the Dockerfile no longer performs.

    Since Dockerfile-1/-2 the runtime stage copies no source tree, and the
    package is installed from the local src/ (not from PyPI).
    """
    text = DOCKERFILES[name].read_text(encoding="utf-8")
    stages = _stages(text)
    runtime = stages[-1]
    assert not re.search(r"^COPY\s+src/", runtime, re.MULTILINE)
    header = text.split("FROM", 1)[0]
    stage2 = [line for line in header.splitlines() if "Stage 2" in line]
    for line in stage2:
        assert "source" not in line, f"{name}: header says stage 2 copies source: {line!r}"
    lines = stages[0].splitlines()
    for i, line in enumerate(lines):
        if re.match(r"RUN pip install .*\s\.$", line.strip()):
            j = i - 1
            while j >= 0 and lines[j].lstrip().startswith("#"):
                assert "PyPI" not in lines[j], (
                    f"{name}: comment says the package comes from PyPI: {lines[j]!r}"
                )
                j -= 1
