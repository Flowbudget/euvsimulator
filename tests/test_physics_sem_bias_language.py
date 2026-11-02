"""Regression guard: physics.md must not call SEM-biased upper bounds bias-corrected.

§5 said "the anchor data record bias-corrected estimates".  Only the NXE1716
anchor records one (lwr_unbiased_estimate_nm); the MET-2D anchor says
"no bias value published -> LER values are upper bounds".
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANCHORS = ROOT / "src" / "euvsimulator" / "data" / "anchors"
PHYSICS = ROOT / "docs" / "physics.md"


def _section(title: str) -> str:
    text = PHYSICS.read_text(encoding="utf-8")
    body = text.split(f"## {title}", 1)[1]
    return " ".join(body.split("\n## ", 1)[0].split())


def _has_unbiased_field(obj) -> bool:
    if isinstance(obj, dict):
        return any("unbiased" in k or _has_unbiased_field(v) for k, v in obj.items())
    if isinstance(obj, list):
        return any(_has_unbiased_field(v) for v in obj)
    return False


def test_met2d_anchor_has_no_bias_corrected_value() -> None:
    """Precondition: the MET-2D file records upper bounds only, NXE1716 an estimate."""
    met2d = json.loads((ANCHORS / "met2d_xp5271.json").read_text(encoding="utf-8"))
    nxe = json.loads((ANCHORS / "vesters2017_nxe1716.json").read_text(encoding="utf-8"))
    assert not _has_unbiased_field(met2d)
    assert "upper bounds" in json.dumps(met2d)
    assert _has_unbiased_field(nxe)


def test_roughness_section_distinguishes_the_anchors() -> None:
    """§5 says which anchor is bias-corrected and that MET-2D gives upper bounds."""
    sec = _section("5. Roughness metrics")
    assert "the anchor data record bias-corrected estimates" not in sec
    assert "MET-2D" in sec and "upper bound" in sec
    assert "NXE1716" in sec and "5.1–5.7" in sec
