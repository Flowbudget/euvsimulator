"""Regression guard: no numpy.trapezoid calls while pyproject allows NumPy 1.x.

numpy.trapezoid exists only from NumPy 2.0, but pyproject.toml declares
numpy>=1.24. The library switched to scipy.integrate.trapezoid; a test that
still called np.trapezoid raised AttributeError on NumPy 1.x. CI runs
NumPy 2 and cannot see that, so this test scans the code instead.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CALL = re.compile(r"\b(?:np|numpy)\.trapezoid\s*\(")


def test_no_numpy_trapezoid_calls_in_code_tests_or_notebooks():
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    bound = re.search(r'"numpy>=(\d+)', pyproject)
    if bound is not None and int(bound.group(1)) >= 2:
        pytest.skip("pyproject requires NumPy >= 2, numpy.trapezoid is available")
    files = [
        *(REPO / "src").rglob("*.py"),
        *(REPO / "tests").rglob("*.py"),
        *(REPO / "scripts").rglob("*.py"),
        *(REPO / "notebooks").glob("*.ipynb"),
    ]
    hits = [
        f"{path.relative_to(REPO)}:{lineno}"
        for path in files
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if CALL.search(line)
    ]
    assert hits == [], f"numpy.trapezoid needs NumPy >= 2.0; use scipy.integrate.trapezoid: {hits}"
