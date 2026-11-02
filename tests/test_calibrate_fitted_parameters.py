"""Regression guard: ``euv calibrate`` fits only what reaches the model.

Before the fix ``pipeline_fn`` forwarded nine fixed keys and dropped every
other initial-params key (e.g. ``dill_B``), which Nelder-Mead still moved and
the CLI reported as fitted, with a confidence interval. With ``--bands`` the
base configuration omitted ``peb_acid_lifetime_s``, so the bands ran at the
default 7.54 s instead of the fitted lifetime.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import euvsimulator.calibrate.bands as bands_mod
import euvsimulator.pipeline as pipeline_mod
from euvsimulator.io.cli import app

TABLE = {4.0: 32.0, 4.5: 28.0, 5.0: 26.0, 5.5: 24.0}
# The resist parameters `euv calibrate` documents as fittable.
FITTABLE = (
    "dill_C",
    "peb_k",
    "peb_t_bake",
    "peb_sigma_diff",
    "peb_acid_lifetime_s",
    "mack_R_max",
    "mack_R_min",
    "mack_n",
    "mack_M_th",
)


def _write_fem(tmp_path):
    csv = tmp_path / "fem.csv"
    csv.write_text("dose,focus,cd_nm\n4.0,0.0,32.0\n4.5,0.0,28.0\n5.0,0.0,26.0\n5.5,0.0,24.0\n")
    return csv


def _invoke(tmp_path, initial: str, *extra: str):
    ip = tmp_path / "ip.yaml"
    ip.write_text(initial)
    return CliRunner().invoke(
        app,
        ["calibrate", str(_write_fem(tmp_path)), "-i", str(ip), "--bootstrap", "0", *extra],
    )


def test_unknown_initial_param_is_rejected_before_fitting(tmp_path, monkeypatch) -> None:
    seen = []

    def fake_run_simulation(cfg):
        seen.append(cfg)
        return SimpleNamespace(cd_nm=TABLE[cfg.dose_mj_cm2] - 0.5 * (cfg.peb_sigma_diff - 7.0))

    monkeypatch.setattr(pipeline_mod, "run_simulation", fake_run_simulation)
    # before the fix: exit 0 and "dill_B: 4.9xx" reported as fitted, while every
    # simulated configuration kept dill_B = 4.44
    result = _invoke(tmp_path, "peb_sigma_diff: 12.0\ndill_B: 4.0\n", "--maxiter", "20")
    assert result.exit_code == 1, result.output
    assert "dill_B" in result.output
    assert "peb_sigma_diff" in result.output  # the message lists what can be fitted
    assert seen == [], "no simulation may run with an unusable parameter"


@pytest.mark.parametrize("name", FITTABLE)
def test_every_fittable_key_reaches_the_simulation(tmp_path, monkeypatch, name) -> None:
    default = getattr(pipeline_mod.SimulationConfig(), name)
    start = 0.5 if name == "mack_M_th" else (default or 1.0) * 1.37  # inside DEFAULT_BOUNDS
    seen = []

    def fake_run_simulation(cfg):
        seen.append(cfg)
        return SimpleNamespace(cd_nm=TABLE[cfg.dose_mj_cm2])

    monkeypatch.setattr(pipeline_mod, "run_simulation", fake_run_simulation)
    result = _invoke(tmp_path, f"{name}: {start!r}\n", "--maxiter", "1")
    assert result.exit_code == 0, result.output
    assert seen
    assert getattr(seen[0], name) == pytest.approx(start), f"{name} never reached the model"


def test_bands_use_the_fitted_acid_lifetime(tmp_path, monkeypatch) -> None:
    def fake_run_simulation(cfg):
        lifetime = cfg.peb_acid_lifetime_s
        sigma = cfg.peb_sigma_diff
        return SimpleNamespace(
            cd_nm=TABLE[cfg.dose_mj_cm2] - 2.0 * (lifetime - 5.0) - 0.5 * (sigma - 7.0)
        )

    bases = []

    def spy_structural_bands(base, **kwargs):
        bases.append(dict(base))
        return {
            "dose_to_size_mj_cm2": {"analytical": 1.0, "reaction_diffusion": 1.1},
            "dose_to_size_band": [1.0, 1.1],
            "lwr_3sigma_nm_at_analytical_d2s": {"photon_shot_noise": 4.0},
            "lwr_3sigma_band": [4.0, 4.0],
        }

    monkeypatch.setattr(pipeline_mod, "run_simulation", fake_run_simulation)
    monkeypatch.setattr(bands_mod, "structural_bands", spy_structural_bands)
    out = tmp_path / "out.json"
    result = _invoke(
        tmp_path,
        "peb_acid_lifetime_s: 3.0\npeb_sigma_diff: 12.0\n",
        "--maxiter",
        "200",
        "--bands",
        "--period",
        "44",
        "--cd",
        "22",
        "--se-blur",
        "3",
        "-o",
        str(out),
    )
    assert result.exit_code == 0, result.output
    fitted = json.loads(out.read_text(encoding="utf-8"))["fit"]["fitted_params"]
    assert fitted["peb_acid_lifetime_s"] != pytest.approx(7.54, abs=0.5)
    assert len(bases) == 1
    base = bases[0]
    # before the fix: no peb_acid_lifetime_s in the base (the bands ran at 7.54 s)
    assert base["peb_acid_lifetime_s"] == pytest.approx(fitted["peb_acid_lifetime_s"])
    assert base["peb_sigma_diff"] == pytest.approx(fitted["peb_sigma_diff"])
    assert (base["period_nm"], base["line_width_nm"], base["se_blur_nm"]) == (44.0, 22.0, 3.0)
