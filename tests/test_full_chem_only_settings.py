"""Regression guard: full_chem-only settings under the default aerial_threshold model.

The default resist model thresholds the aerial image with resist_threshold_norm
alone (pipeline._cd_via_aerial_threshold). The SE blur, the Dill, PEB, Mack,
film and development parameters and the stochastic settings act only with
resist_model='full_chem'. Until 2026-10 the CLI help (--se-blur,
--resist-preset), the field help and the GUI presented them as active for the
default model.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from euvsimulator.api.fields import field_catalogue
from euvsimulator.io.cli import app
from euvsimulator.pipeline import SimulationConfig, run_simulation

APP_JS = (
    Path(__file__).resolve().parent.parent / "src" / "euvsimulator" / "api" / "static" / "app.js"
)

# A valid non-default value for every full_chem-only field (aerial_threshold).
PERTURBED = {
    "dill_A": 0.5,
    "dill_B": 5.0,
    "dill_C": 0.03,
    "se_blur_nm": 7.0,
    "resist_thickness_nm": 80.0,
    "peb_model": "reaction_diffusion",
    "peb_temperature_c": 90.0,
    "peb_t_bake": 90.0,
    "peb_k": 2.0,
    "peb_acid_lifetime_s": 3.0,
    "peb_D": 8.0,
    "peb_sigma_diff": 5.0,
    "peb_k_trap_per_s": 0.1,
    "peb_D_quencher": 2.0,
    "pag_density_per_nm3": 0.3,
    "quencher_density_per_nm3": 0.05,
    "acid_base_quench_rate_nm3_per_s": 5.0,
    "mack_R_max": 100.0,
    "mack_R_min": 0.2,
    "mack_n": 5.0,
    "mack_M_th": 0.5,
    "develop_time_s": 60.0,
    "development_model": "column",
    "stochastic_n_realisations": 3,
    "stochastic_seed": 7,
    "stochastic_ler_grid_y": 128,
    "stochastic_ler_estimator": "legacy",
    "ler_passband_nm": (10.0, 100.0),
    "exposure_stochasticity": True,
    "development_stochasticity": True,
    "blocked_site_density_per_nm3": 2.0,
    "dissolution_cell_nm": 2.0,
    "n_develop_layers": 11,
}


def _flagged() -> set[str]:
    return {row["name"] for row in field_catalogue() if row["full_chem_only"]}


def test_catalogue_flags_and_help_name_the_full_chem_only_fields():
    rows = {row["name"]: row for row in field_catalogue()}
    flagged = _flagged()
    assert set(PERTURBED) | {"enable_stochastic"} == flagged
    for name in flagged:
        assert "full_chem only" in rows[name]["help"], name
    for name in ("dose_mj_cm2", "resist_model", "resist_threshold_norm", "na", "grid"):
        assert not rows[name]["full_chem_only"], name


def test_flagged_fields_have_no_effect_with_aerial_threshold():
    """The flag set is exactly right: perturbing every flagged field changes nothing."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # peb_sigma_diff with reaction_diffusion warns
        ref = run_simulation(SimulationConfig(grid=32))
        alt = run_simulation(SimulationConfig(grid=32, **PERTURBED))
    assert alt.cd_nm == ref.cd_nm
    assert alt.nils_value == ref.nils_value
    assert bool((alt.aerial_image == ref.aerial_image).all())
    # the one flagged field that is not inert is rejected outright
    with pytest.raises(ValueError, match="requires resist_model='full_chem'"):
        SimulationConfig(enable_stochastic=True)


def _option_help(command: str, param: str) -> str:
    cmd = typer.main.get_command(app).commands[command]  # type: ignore[attr-defined]
    return next(p.help for p in cmd.params if p.name == param)


@pytest.mark.parametrize(
    ("command", "param"),
    [("simulate", "se_blur"), ("simulate", "resist_preset"), ("process-window", "se_blur")],
)
def test_cli_help_says_full_chem_only(command, param):
    text = " ".join(_option_help(command, param).split())
    assert "full_chem only" in text
    assert "no effect with the default aerial_threshold model" in text


def test_simulate_warns_about_full_chem_options_with_aerial_threshold():
    runner = CliRunner()
    r = runner.invoke(app, ["simulate", "--grid", "32", "--se-blur", "5", "--mack-n", "5"])
    assert r.exit_code == 0, r.output
    assert "only act with --resist-model full_chem" in r.output
    assert "--se-blur" in r.output and "--mack-n" in r.output
    quiet = runner.invoke(app, ["simulate", "--grid", "32"])
    assert quiet.exit_code == 0, quiet.output
    assert "only act with --resist-model full_chem" not in quiet.output


def test_process_window_warns_about_se_blur_with_aerial_threshold(tmp_path):
    args = ["process-window", "--grid", "32", "--dose-steps", "2", "--focus-steps", "2"]
    r = CliRunner().invoke(app, [*args, "--se-blur", "5", "--output", str(tmp_path / "pw.json")])
    assert r.exit_code == 0, r.output
    assert "only act with --resist-model full_chem" in r.output


def test_gui_hides_full_chem_only_fields_for_aerial_threshold():
    js = APP_JS.read_text(encoding="utf-8")
    body = js[js.index("function updateVisibility") :]
    body = body[: body.index("\n  }\n")]
    assert "full_chem_only" in body
    assert "aerial_threshold" in body
