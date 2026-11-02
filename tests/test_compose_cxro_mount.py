"""Regression guard: both compose files mount the CXRO data where the package reads it.

materials.DATA_DIR is <package>/data/cxro.  Both images install the package
into site-packages of python:3.11 and copy no source tree, so a mount at
/app/euvsimulator/data has no effect.  docker-compose.yml was corrected in
part 1 (code_77); docker-compose.cli.yml still mounted the dead path.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SITE_DATA = "/usr/local/lib/python3.11/site-packages/euvsimulator/data"


@pytest.mark.parametrize("name", ["docker-compose.yml", "docker-compose.cli.yml"])
def test_compose_data_volume_targets_site_packages(name: str) -> None:
    text = (ROOT / name).read_text(encoding="utf-8")
    mounts = re.findall(r"^\s*-\s*\./src/euvsimulator/data:(\S+)\s*$", text, re.MULTILINE)
    assert mounts == [SITE_DATA], f"{name}: data volume mounts {mounts}"


@pytest.mark.parametrize("name", ["Dockerfile", "Dockerfile.cli"])
def test_dockerfiles_do_not_create_the_dead_data_path(name: str) -> None:
    """No image prepares /app/euvsimulator/data, which nothing reads."""
    text = (ROOT / name).read_text(encoding="utf-8")
    assert "/app/euvsimulator/data" not in text
