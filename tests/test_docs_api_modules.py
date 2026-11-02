"""docs/api/modules.rst must name modules of the euvsimulator package that exist in src/."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES_RST = ROOT / "docs" / "api" / "modules.rst"
SRC = ROOT / "src"

_AUTOMODULE = re.compile(r"^\.\. automodule:: (\S+)\s*$", re.MULTILINE)


def _targets() -> list[str]:
    return _AUTOMODULE.findall(MODULES_RST.read_text(encoding="utf-8"))


def test_modules_rst_keeps_all_automodule_directives() -> None:
    assert len(_targets()) >= 26


def test_every_automodule_target_is_in_the_euvsimulator_package() -> None:
    bad = [t for t in _targets() if t != "euvsimulator" and not t.startswith("euvsimulator.")]
    assert bad == []


def test_every_automodule_target_has_a_source_file() -> None:
    missing = []
    for target in _targets():
        base = SRC.joinpath(*target.split("."))
        if not (base.with_suffix(".py").is_file() or (base / "__init__.py").is_file()):
            missing.append(target)
    assert missing == []


def test_section_underlines_are_at_least_as_long_as_their_titles() -> None:
    lines = MODULES_RST.read_text(encoding="utf-8").splitlines()
    short = []
    for title, underline in zip(lines, lines[1:]):
        is_underline = underline != "" and set(underline) <= {"-", "="}
        if is_underline and title.strip() and len(underline) < len(title):
            short.append(title)
    assert short == []
