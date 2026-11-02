"""Regression guard: README's NXE1716 roughness bracket must use one reference value.

README said the NXE1716 roughness "is bracketed between 0.7x and 2.4x".  The
lower end was 4.8 nm divided by the SEM-biased 6.7 nm, the upper end 13 nm
divided by the bias-corrected 5.4 nm: two different bases.  docs/physics.md
§6 gives LWR 4.8-13 nm 3σ; the anchor JSON gives 6.7 nm (biased) and
5.1-5.7 nm (bias-corrected).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ANCHOR = ROOT / "src" / "euvsimulator" / "data" / "anchors" / "vesters2017_nxe1716.json"


def _physics_lwr_range() -> tuple[float, float]:
    """LWR range of the NXE1716 row in docs/physics.md §6."""
    text = (ROOT / "docs" / "physics.md").read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if line.startswith("| NXE1716"))
    m = re.search(r"LWR (\d+(?:\.\d+)?)[–-](\d+(?:\.\d+)?) nm 3σ", row)
    assert m, f"physics.md NXE1716 row has no LWR range: {row}"
    return float(m.group(1)), float(m.group(2))


def _readme_brackets() -> list[tuple[float, float]]:
    """All 'a×–b×' (or 'a× and b×') ratio pairs in README's NXE1716 sentence."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    para = " ".join(text.split("At the NXE1716 anchor", 1)[1].split("MET-2D", 1)[0].split())
    pairs = re.findall(r"(\d+(?:\.\d+)?)×\s*(?:–|-|and)\s*(\d+(?:\.\d+)?)×", para)
    return [(float(a), float(b)) for a, b in pairs]


def test_readme_nxe1716_bracket_has_one_basis() -> None:
    """Each README bracket is the physics.md range over one anchor value."""
    lo, hi = _physics_lwr_range()
    lwr = json.loads(ANCHOR.read_text(encoding="utf-8"))["patterning_thesis_table_4_2_B0"]
    biased = lwr["lwr_3sigma_nm_sem_biased"]
    u_lo, u_hi = lwr["lwr_unbiased_estimate_nm"]["range"]
    bases = {
        "SEM-biased": (lo / biased, hi / biased),
        "bias-corrected": (lo / u_hi, hi / u_lo),
    }
    pairs = _readme_brackets()
    assert pairs, "README gives no ratio bracket for the NXE1716 roughness"
    for a, b in pairs:
        ok = [
            name
            for name, (r_lo, r_hi) in bases.items()
            if a == pytest.approx(r_lo, abs=0.05) and b == pytest.approx(r_hi, abs=0.05)
        ]
        assert ok, f"README bracket {a}×–{b}× matches no single basis: {bases}"
