"""peb_sigma_diff together with peb_model="reaction_diffusion" warns
(plan pipeline-1, step 3).

The concurrent PDE has no single blur and ignores peb_sigma_diff; until
2026-10 this happened silently (MET-2D preset: 10.1 nm measured blur
replaced by sqrt(2 * 4.2 * 90) = 27.5 nm from peb_D and peb_t_bake).
"""

import warnings

import pytest

from euvsimulator.pipeline import SimulationConfig
from euvsimulator.presets import met2d_config


def test_sigma_diff_with_reaction_diffusion_warns():
    with pytest.warns(UserWarning, match="is ignored with peb_model='reaction_diffusion'"):
        SimulationConfig(peb_model="reaction_diffusion", peb_sigma_diff=10.0)


def test_no_warning_without_an_effective_sigma_or_with_the_analytical_model():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        SimulationConfig(peb_model="reaction_diffusion")
        SimulationConfig(peb_model="reaction_diffusion", peb_sigma_diff=0.0)
        SimulationConfig(peb_model="analytical", peb_sigma_diff=10.0)


def test_met2d_preset_with_reaction_diffusion_warns():
    with pytest.warns(UserWarning, match="is ignored with peb_model='reaction_diffusion'"):
        met2d_config(peb_model="reaction_diffusion")
