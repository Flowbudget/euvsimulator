"""Photon-to-acid multiplicity (plan stage C2b, log Fortsetzung 40).

The sampled chain (Poisson photons -> SE point-spread -> binomial PAG
conversion) is a compound Poisson process: the acid count in a block much
larger than the SE blur has Var/E = 1 + m with m the mean number of acids
per absorbed photon (1.0 for the defaults), and 1.0 when the photon noise
is switched off. This pins that the multiplicity is not missing.
"""

from __future__ import annotations

import pytest
import torch

from euvsimulator.pipeline import SimulationConfig, acids_per_absorbed_photon
from euvsimulator.resist.exposure import sample_pag_quencher_acid
from euvsimulator.resist.stochastic import photon_deposition_shot_noise


def _fano(noisy: bool, seed: int = 3) -> float:
    cfg = SimulationConfig()
    dx, dz, dose, n = 0.34, 1.0, 1.65, 768
    g = torch.Generator().manual_seed(seed)
    field = torch.full((n, n), dose, dtype=torch.float64)
    absorbed = (cfg.dill_A + cfg.dill_B) * 1e-3 * dz
    if noisy:
        field = photon_deposition_shot_noise(
            field,
            se_blur_nm=2.5,
            dx_nm=dx,
            photon_energy_eV=91.84,
            dose_to_energy_factor=6.241509074e15,
            absorption=absorbed,
            rng=g,
        )
    acid, _ = sample_pag_quencher_acid(
        field.unsqueeze(0),
        C=cfg.dill_C,
        pag_density=cfg.pag_density_per_nm3,
        quencher_density=0.0,
        dx=dx,
        dz=dz,
        rng=g,
    )
    counts = acid[0] * (cfg.pag_density_per_nm3 * dx * dx * dz)
    b = 64  # 21.8 nm blocks >> 2.5 nm PSF
    blocks = counts.reshape(n // b, b, n // b, b).sum(dim=(1, 3))
    return float(blocks.var() / blocks.mean())


def test_acid_count_is_compound_poisson_with_the_photon_multiplicity():
    m = acids_per_absorbed_photon(SimulationConfig())
    assert _fano(True) == pytest.approx(1.0 + m, abs=0.25)
    assert _fano(False) == pytest.approx(1.0, abs=0.15)
