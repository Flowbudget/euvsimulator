"""run_simulation builds the Mo/Si multilayer at the photon energy of cfg.wavelength_nm."""

from __future__ import annotations

import math

import pytest
import torch

from euvsimulator.constants import HC_EV_NM
from euvsimulator.materials import CXROTable
from euvsimulator.optics.multilayer import mo_si_stack
from euvsimulator.optics.tmm import reflectivity
from euvsimulator.pipeline import SimulationConfig, run_simulation


def _bare_mirror_r_te(cfg: SimulationConfig) -> float:
    """TE clear-field reflectivity at 6 deg with every n,k at hc/wavelength."""
    energy_eV = HC_EV_NM / cfg.wavelength_nm
    n_si, k_si = CXROTable().refractive_index("Si", energy_eV)
    stack = mo_si_stack(
        n_bilayers=cfg.ml_n_bilayers,
        d_mo_nm=cfg.ml_d_mo_nm,
        d_si_nm=cfg.ml_d_si_nm,
        gamma=cfg.ml_gamma,
        grading_linear_nm=cfg.ml_grading_linear_nm,
        grading_parabolic_nm=cfg.ml_grading_parabolic_nm,
        capping_layer=cfg.ml_capping if cfg.ml_capping != "none" else None,
        d_cap_nm=cfg.ml_capping_nm,
        energy_eV=energy_eV,
    )
    _, r = reflectivity(
        stack.n_layers,
        stack.thicknesses,
        torch.tensor([cfg.wavelength_nm * 1e-9], dtype=torch.float64),
        torch.tensor(math.radians(6.0), dtype=torch.float64),
        n_substrate=torch.tensor(complex(n_si, k_si), dtype=torch.complex128),
        roughness_nm=cfg.ml_roughness_nm,
    )
    return float((abs(r[0]) ** 2).real)


@pytest.mark.parametrize("wavelength_nm", [13.0, 13.5, 14.0])
def test_clear_field_reflectivity_uses_wavelength_energy(wavelength_nm):
    cfg = SimulationConfig(device="cpu", grid=64, wavelength_nm=wavelength_nm)
    r = run_simulation(cfg)
    assert r.clear_field_reflectivity == pytest.approx(_bare_mirror_r_te(cfg), rel=1e-9)


def test_clear_field_reflectivity_at_13nm():
    # Measured 2026-10-02: with the Mo/Si/Ru n,k fixed at 91.84 eV the
    # pipeline gave 0.3562 at 13.0 nm; at hc/13.0 nm it is 0.1508.
    r = run_simulation(SimulationConfig(device="cpu", grid=64, wavelength_nm=13.0))
    assert r.clear_field_reflectivity == pytest.approx(0.217002, abs=1e-4)  # 0.150771 before 2.3.0
