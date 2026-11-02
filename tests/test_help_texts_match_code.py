"""Regression guard: help texts and docstrings that contradicted the code.

(a) resist_threshold_norm is a fraction of the IMAGE mean at the 20 mJ/cm²
    reference dose (threshold = norm * mean(aerial) * 20 / dose), not of the
    clear-field mean.
(b) SimulationResult.aerial_image is the local dose in mJ/cm² (clear-field
    normalised image times dose_mj_cm2); the mask-level intensity is
    aerial_image / dose_mj_cm2 * clear_field_reflectivity.
(c) The --peb-k default 10.947 comes from the full-curve fit k*H0 = 0.2305 1/s
    (not k*H = 0.166, which gives 7.9); the peb_D comment's 3.3 nm²/s and
    9.4 nm blur are historical (now 4.2 nm²/s and 7.96 nm).
"""

from __future__ import annotations

import inspect
import math

import pytest
import typer

import euvsimulator.pipeline as pipeline
from euvsimulator.api.fields import field_catalogue
from euvsimulator.io.cli import app
from euvsimulator.pipeline import AERIAL_THRESHOLD_REFERENCE_DOSE_MJ_CM2, SimulationResult


def _flat(text: str) -> str:
    return " ".join(text.split())


def test_threshold_norm_help_names_the_image_mean():
    rows = {row["name"]: row for row in field_catalogue()}
    text = _flat(rows["resist_threshold_norm"]["help"])
    assert "clear-field mean" not in text
    assert "mean(aerial)" in text
    assert "20 / dose" in text
    assert AERIAL_THRESHOLD_REFERENCE_DOSE_MJ_CM2 == 20.0


def test_aerial_image_is_the_local_dose():
    """aerial_image scales with the dose; the docstring says so and gives the right recipe."""
    a = pipeline.run_simulation(grid=32, dose_mj_cm2=10.0)
    b = pipeline.run_simulation(grid=32, dose_mj_cm2=20.0)
    assert float((b.aerial_image - 2.0 * a.aerial_image).abs().max()) < 1e-12
    doc = _flat(SimulationResult.__doc__ or "")
    assert "mJ/cm²" in doc.split("resist_profile")[0]
    assert "aerial_image / dose_mj_cm2 * clear_field_reflectivity" in doc
    assert "``aerial_image * clear_field_reflectivity``" not in doc


def test_peb_k_help_cites_the_full_curve_fit():
    cmd = typer.main.get_command(app).commands["simulate"]  # type: ignore[attr-defined]
    help_text = _flat(next(p.help for p in cmd.params if p.name == "peb_k"))
    assert "0.2305" in help_text
    assert "0.166" not in help_text
    h0 = 1.0 - math.exp(-0.0152 * 1.4)  # relative acid at Yamamoto's 1.4 mJ/cm² flood
    assert 0.2305 / h0 == pytest.approx(pipeline.SimulationConfig().peb_k, rel=1e-3)
    assert 0.166 / h0 == pytest.approx(7.88, abs=0.01)  # the old text's value, not the default


def test_peb_d_comment_marks_the_old_values_as_historical():
    text = _flat(
        " ".join(
            line.strip().lstrip("#")
            for line in inspect.getsource(pipeline.SimulationConfig).splitlines()
        )
    )
    assert "peb_D default below (3.3 nm^2/s) is chosen" not in text
    assert "the default blur is sqrt(2·D·t_eff) = 9.4 nm" not in text
    assert "7.96 nm" in text
