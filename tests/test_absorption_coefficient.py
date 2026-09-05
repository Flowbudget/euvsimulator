"""Dill B from first principles (2026-09-05).

The non-bleaching absorption coefficient of an organic EUV resist is fixed by
its composition and density through the CXRO f₂ scattering factors
(β = r_e λ²/2π · Σ N_i f₂,i, α = 4πβ/λ). The default resist (Yamamoto et al.
2011, Polymer A: PHS with 35 % acid-labile protection) therefore has a
computable B; the paper's Table-2 value of 1.06 µm⁻¹ lies below even
oxygen-free polystyrene and is not possible for a PHS-based film. Three
independent measurements (Sekiguchi 2011: 4.32/5.21 µm⁻¹ for MET-1K/2D;
Fallica 2016: 4–5 µm⁻¹; Kang 2010) agree with the computed range.
"""

from __future__ import annotations

import pytest

from euvsimulator.materials import linear_absorption_coefficient_per_um as alpha
from euvsimulator.pipeline import (
    DEFAULT_RESIST_COMPOSITION,
    DEFAULT_RESIST_DENSITY_G_CM3,
    SimulationConfig,
)

PHS = {"C": 8, "H": 8, "O": 1}
PMMA = {"C": 5, "H": 8, "O": 2}
PS = {"C": 8, "H": 8}


def test_pmma_matches_the_cxro_literature_value():
    # CXRO/Henke PMMA at 13.5 nm: ≈ 5 µm⁻¹ (attenuation length ≈ 0.2 µm)
    assert 4.6 < alpha(PMMA, 1.18) < 5.6


def test_phs_family_lies_at_four_per_micron():
    assert 3.8 < alpha(PHS, 1.15) < 4.3
    assert 4.2 < alpha(DEFAULT_RESIST_COMPOSITION, DEFAULT_RESIST_DENSITY_G_CM3) < 4.7


def test_oxygen_raises_absorption_and_polystyrene_is_the_floor():
    # every PHS-based composition absorbs more than oxygen-free polystyrene
    assert alpha(PS, 1.05) < alpha(PHS, 1.05) < alpha(PMMA, 1.05)
    # ... and even polystyrene is far above the 1.06 µm⁻¹ of Yamamoto's Table 2
    assert alpha(PS, 1.05) > 2.5


def test_linear_in_density_and_rejects_nonpositive_density():
    assert alpha(PHS, 2.0) == pytest.approx(2.0 * alpha(PHS, 1.0), rel=1e-12)
    with pytest.raises(ValueError):
        alpha(PHS, 0.0)


def test_default_dill_b_is_the_computed_value():
    """The pipeline default must stay tied to the derivation, not to a number."""
    cfg = SimulationConfig()
    assert cfg.dill_B == pytest.approx(
        alpha(DEFAULT_RESIST_COMPOSITION, DEFAULT_RESIST_DENSITY_G_CM3), abs=0.02
    )
