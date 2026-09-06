"""Photon-to-acid multiplicity (plan stage C2b, log Fortsetzung 40).

The sampled chain (Poisson photons -> SE point-spread -> binomial PAG
conversion) is a compound Poisson process: the acid count in a block much
larger than the SE blur has Var/E = 1 + m with m the mean number of acids
per absorbed photon (1.0 for the defaults). Finite blocks cut the acid
cluster of a photon at their borders, which lowers the block Fano factor by
a term ~ sigma/b; the limit b -> infinity is taken by a linear fit in 1/b.
Without photon noise the count is binomial, Fano ~ 1.
"""

from __future__ import annotations

import numpy as np
import pytest
import torch

from euvsimulator.pipeline import SimulationConfig, acids_per_absorbed_photon
from euvsimulator.resist.exposure import sample_pag_quencher_acid
from euvsimulator.resist.stochastic import photon_deposition_shot_noise

N, DX, DZ, DOSE = 1536, 0.34, 45.0, 1.65
BLOCKS = (24, 32, 48, 64, 96, 128)


def _acid_counts(seed: int, noisy: bool) -> torch.Tensor:
    cfg = SimulationConfig()
    g = torch.Generator().manual_seed(seed)
    field = torch.full((N, N), DOSE, dtype=torch.float64)
    if noisy:
        field = photon_deposition_shot_noise(
            field,
            se_blur_nm=2.5,
            dx_nm=DX,
            photon_energy_eV=91.84,
            dose_to_energy_factor=6.241509074e15,
            absorption=(cfg.dill_A + cfg.dill_B) * 1e-3 * DZ,
            rng=g,
        )
    acid, _ = sample_pag_quencher_acid(
        field.unsqueeze(0),
        C=cfg.dill_C,
        pag_density=cfg.pag_density_per_nm3,
        quencher_density=0.0,
        dx=DX,
        dz=DZ,
        rng=g,
    )
    return acid[0] * (cfg.pag_density_per_nm3 * DX * DX * DZ)


def _fano(counts: torch.Tensor, b: int) -> float:
    m = N // b * b
    blocks = counts[:m, :m].reshape(N // b, b, N // b, b).sum(dim=(1, 3))
    return float(blocks.var() / blocks.mean())


def test_acid_count_is_compound_poisson_with_the_photon_multiplicity():
    m_exp = acids_per_absorbed_photon(SimulationConfig())
    fano = np.mean([[_fano(_acid_counts(s, True), b) for b in BLOCKS] for s in (3, 4, 5)], axis=0)
    assert np.all(np.diff(fano) > -0.15)  # rises with block size (border effect shrinks)
    inv_b = 1.0 / np.array(BLOCKS, dtype=float)
    intercept, slope = np.linalg.lstsq(np.vstack([np.ones_like(inv_b), inv_b]).T, fano, rcond=None)[
        0
    ]
    assert slope < 0
    assert intercept == pytest.approx(1.0 + m_exp, abs=0.25), (intercept, fano)


def test_without_photon_noise_the_count_is_binomial():
    assert _fano(_acid_counts(4, False), 64) == pytest.approx(1.0, abs=0.15)
