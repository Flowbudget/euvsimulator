"""Regression guard: notebook 01 shows intensities on the pipeline's mJ/cm² scale.

The pipeline divides the thin-mask image by the clear-field reflectivity
before multiplying by the dose, so an open frame receives exactly the dose.
Notebook 01 multiplied by the dose only and labelled the result mJ/cm²: its
stored 'Max intensity: 11.645 mJ/cm²' is 0.647 (= |r_space|²) times the
pipeline's 17.9987.  It also said the orders come from RCWA, but the cells
use thin-mask Fourier coefficients.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from euvsimulator.pipeline import run_simulation

ROOT = Path(__file__).resolve().parent.parent
NB01 = ROOT / "notebooks" / "01_aerial_image.ipynb"


def _cells() -> list[dict]:
    return json.loads(NB01.read_text(encoding="utf-8"))["cells"]


def _stored_max_intensity() -> float:
    for cell in _cells():
        for out in cell.get("outputs", []):
            text = "".join(out.get("text", []))
            m = re.search(r"Max intensity: ([\d.]+) mJ/cm²", text)
            if m:
                return float(m.group(1))
    raise AssertionError("notebook 01 has no stored 'Max intensity' output")


def _notebook_config():
    """SimulationConfig as notebook 01 builds it (imports + configuration cell)."""
    ns: dict = {}
    code = [c for c in _cells() if c["cell_type"] == "code"]
    for cell in code:
        src = "".join(cell["source"])
        if "cfg = SimulationConfig(" in src:
            exec("from euvsimulator.pipeline import SimulationConfig\n" + src, ns)
            return ns["cfg"]
    raise AssertionError("notebook 01 has no configuration cell")


def test_notebook01_intensity_matches_pipeline_scale() -> None:
    """The stored maximum equals the pipeline's aerial maximum for the same config."""
    result = run_simulation(_notebook_config())
    assert _stored_max_intensity() == pytest.approx(float(result.aerial_image.max()), abs=1e-3)


def test_notebook01_does_not_claim_rcwa_orders() -> None:
    """Intro and notebooks/README.md describe the thin-mask orders the cells use."""
    intro = "".join(_cells()[0]["source"])
    assert "Mask → RCWA" not in intro
    assert "thin-mask" in intro.lower()
    readme = (ROOT / "notebooks" / "README.md").read_text(encoding="utf-8")
    sec01 = readme.split("### 01_aerial_image.ipynb", 1)[1].split("###", 1)[0]
    assert "diffraction orders (RCWA)" not in sec01
    assert "thin-mask" in sec01.lower()
