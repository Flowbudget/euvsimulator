"""Regression guard: notebook 03 shows the Mack model the code implements.

Section 3 printed R = Rmax (1-M)^n / ((1-M)^n + M_th^n) + Rmin, but MackModel
implements R = Rmax (a+1)(1-M)^n / (a + (1-M)^n) + Rmin with
a = (n+1)/(n-1) (1-M_th)^n.  The cell then demonstrated threshold_development
(a binary cut, 1 = developed) under the colorbar label 'Resist remaining', and
the summary table listed threshold_development as the 'Mack model'.
notebooks/README.md also listed contents the notebooks do not have.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NB03 = ROOT / "notebooks" / "03_resist_chain.ipynb"


def _cells() -> list[dict]:
    return json.loads(NB03.read_text(encoding="utf-8"))["cells"]


def _src(cell: dict) -> str:
    return "".join(cell["source"])


def test_section3_formula_is_the_implemented_one() -> None:
    """The development section gives the enhanced Mack form with a(M_th)."""
    sec = next(_src(c) for c in _cells() if _src(c).startswith("## 3. Development"))
    flat = sec.replace(" ", "")
    assert "(M_{th})^n" not in flat, "notebook still shows M_th^n in the denominator"
    assert "(a+1)" in flat and "(1-M_{th})^n" in flat


def test_development_cell_uses_mackmodel_and_labels_correctly() -> None:
    """The cell demonstrates MackModel and labels threshold output 1 = developed."""
    code = [_src(c) for c in _cells() if c["cell_type"] == "code"]
    assert any("MackModel(" in s for s in code), "MackModel is never demonstrated"
    dev_cells = [s for s in code if "threshold_development(" in s]
    for s in dev_cells:
        assert 'label="Resist remaining"' not in s
        assert "developed" in s.lower()


def test_summary_table_names_the_development_model() -> None:
    summary = _src(_cells()[-1])
    row = next(line for line in summary.splitlines() if line.startswith("| Development"))
    assert "MackModel" in row, row


def test_notebooks_readme_lists_only_existing_contents() -> None:
    readme = (ROOT / "notebooks" / "README.md").read_text(encoding="utf-8")

    def section(name: str) -> str:
        return readme.split(f"### {name}", 1)[1].split("###", 1)[0]

    assert "1/√Dose" not in section("03_resist_chain.ipynb")
    assert "PNG export" not in section("04_process_window.ipynb")
    sec06 = section("06_mask3d.ipynb")
    assert "at High-NA" not in sec06
    assert "Absorber height & sidewall angle effects" not in sec06
