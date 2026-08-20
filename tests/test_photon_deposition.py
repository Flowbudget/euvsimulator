"""Unit tests for photon_deposition_shot_noise — event-based shot noise.

Tests cover (Step 1 of STOCHASTIC_PHYSICS_DESIGN_AUDIT):
1. Statistical moments of the Poisson events (E[N]=lam, Var[N]=lam)
2. Unbiasedness of D_eff w.r.t. dose (many realisations)
3. Seed reproducibility
4. se_blur_nm = 0 handling (white noise, identity PSF)
5. dose = 0 (no NaN/Inf)
6. Spatial correlation increases for se_blur_nm > 0
7. Grid-resolution invariance of the relative noise statistics
"""

from __future__ import annotations

import math

import pytest
import torch

from euvsimulator.resist.stochastic import photon_deposition_shot_noise

E_PH = 91.84014696703977
F = 6.241509074e15


# ──────────────────────────────────────────────
# Fixtures / helpers
# ──────────────────────────────────────────────


def uniform_dose(shape=(64, 64), dose_val=20.0, device="cpu"):
    """Uniform dose map [mJ/cm²]."""
    return torch.full(shape, dose_val, dtype=torch.float64, device=device)


def photon_moments_from_d_eff(d_eff, dose, n_bar):
    """Recover Poisson moments from D_eff for se_blur=0 (white noise).

    With se_blur=0: D_eff = dose * N / N_bar, so
        E[D_eff/dose]         = E[N]/N_bar
        Var[D_eff/dose]*N_bar = Var[N]/N_bar   (== 1 for Poisson)
    """
    rel = d_eff / dose
    return rel.mean().item(), rel.var(unbiased=False).item() * n_bar


# ──────────────────────────────────────────────
# 1. Poisson moments
# ──────────────────────────────────────────────


class TestPoissonMoments:
    @pytest.mark.parametrize("dose_val", [5.0, 20.0, 80.0])
    def test_moments_recovered_from_white_noise(self, dose_val):
        """With se_blur=0, D_eff/dose = N/N_bar; recover E[N] and Var[N]."""
        dx_nm = 1.0
        dose = uniform_dose((32, 32), dose_val)
        voxel_area_cm2 = dx_nm * dx_nm * 1e-14
        n_bar = dose_val * voxel_area_cm2 * F / E_PH  # mean photons/voxel

        n_rep = 400
        e_acc = 0.0
        var_acc = 0.0
        for i in range(n_rep):
            d_eff = photon_deposition_shot_noise(
                dose, 0.0, dx_nm=dx_nm, photon_energy_eV=E_PH,
                dose_to_energy_factor=F, seed=i,
            )
            mean_rel, var_rel = photon_moments_from_d_eff(d_eff, dose, n_bar)
            e_acc += mean_rel
            var_acc += var_rel
        mean_E = e_acc / n_rep
        mean_Var = var_acc / n_rep

        # E[N]/N_bar should be ~1 (Poisson mean)
        assert abs(mean_E - 1.0) < 0.05, f"E[N]/Nbar={mean_E:.4f} != 1"
        # Var[N]/N_bar should be ~1 (Poisson variance)
        assert abs(mean_Var - 1.0) < 0.15, f"Var[N]/Nbar={mean_Var:.4f} != 1"


# ──────────────────────────────────────────────
# 2. Unbiasedness of D_eff
# ──────────────────────────────────────────────


class TestUnbiasedness:
    @pytest.mark.parametrize("se_blur_nm", [0.0, 2.0, 5.0])
    def test_d_eff_unbiased(self, se_blur_nm):
        """E[D_eff] = dose over many realisations (with and without PSF)."""
        dose = uniform_dose((64, 64), 20.0)
        n_rep = 60
        acc = torch.zeros_like(dose)
        for i in range(n_rep):
            acc += photon_deposition_shot_noise(
                dose, se_blur_nm, dx_nm=0.25, photon_energy_eV=E_PH,
                dose_to_energy_factor=F, seed=i,
            )
        mean = acc / n_rep
        # Global mean over all pixels & realisations: statistically solid
        # even for se_blur=0 (where per-pixel variance is huge at dx=0.25).
        global_mean = mean.mean().item()
        assert abs(global_mean - 20.0) / 20.0 < 0.01, (
            f"E[D_eff] global bias {(global_mean-20.0)/20.0:.4f} > 0.01 "
            f"for se_blur={se_blur_nm}"
        )

    def test_unbiased_with_spatial_pattern(self):
        """Unbiasedness also holds for a non-uniform dose map."""
        x = torch.linspace(-32, 32, 64)
        X, _ = torch.meshgrid(x, x, indexing="ij")
        dose = 20.0 * (0.5 + 0.5 * torch.cos(2 * torch.pi * X / 64.0))
        n_rep = 60
        acc = torch.zeros_like(dose)
        for i in range(n_rep):
            acc += photon_deposition_shot_noise(
                dose, 5.0, dx_nm=0.25, photon_energy_eV=E_PH,
                dose_to_energy_factor=F, seed=i,
            )
        mean = acc / n_rep
        # Global relative bias
        rel_err = ((mean - dose).abs() / dose.clamp(min=1e-9)).mean().item()
        # Per-pixel bias at 0.25 nm grid has large variance; use global
        global_bias = (mean - dose).abs().mean().item() / dose.mean().item()
        assert global_bias < 0.02, f"pattern global bias {global_bias:.4f} > 0.02"
        assert rel_err < 0.10, f"pattern per-pixel bias {rel_err:.4f} > 0.10"


# ──────────────────────────────────────────────
# 3. Seed reproducibility
# ──────────────────────────────────────────────


class TestSeedReproducibility:
    def test_same_seed_identical(self):
        """Same seed -> identical D_eff."""
        dose = uniform_dose((32, 32))
        d1 = photon_deposition_shot_noise(dose, 5.0, dx_nm=0.25, seed=42)
        d2 = photon_deposition_shot_noise(dose, 5.0, dx_nm=0.25, seed=42)
        assert torch.allclose(d1, d2)

    def test_different_seed_different(self):
        """Different seeds -> different realisations."""
        dose = uniform_dose((32, 32))
        d1 = photon_deposition_shot_noise(dose, 5.0, dx_nm=0.25, seed=1)
        d2 = photon_deposition_shot_noise(dose, 5.0, dx_nm=0.25, seed=2)
        assert not torch.allclose(d1, d2)

    def test_rng_overrides_seed(self):
        """Explicit rng takes precedence over seed."""
        dose = uniform_dose((32, 32))
        rng1 = torch.Generator().manual_seed(7)
        rng2 = torch.Generator().manual_seed(7)
        d1 = photon_deposition_shot_noise(dose, 5.0, dx_nm=0.25, seed=999, rng=rng1)
        d2 = photon_deposition_shot_noise(dose, 5.0, dx_nm=0.25, seed=999, rng=rng2)
        assert torch.allclose(d1, d2)


# ──────────────────────────────────────────────
# 4. se_blur_nm = 0
# ──────────────────────────────────────────────


class TestZeroBlur:
    def test_zero_blur_runs(self):
        """se_blur=0 must work and produce finite output."""
        dose = uniform_dose((32, 32))
        d_eff = photon_deposition_shot_noise(dose, 0.0, dx_nm=0.25, seed=1)
        assert torch.isfinite(d_eff).all()

    def test_zero_blur_matches_white_noise(self):
        """se_blur=0 => D_eff = dose * N/N_bar exactly."""
        dose = uniform_dose((32, 32), 20.0)
        dx_nm = 1.0
        n_bar = 20.0 * (dx_nm * dx_nm * 1e-14) * F / E_PH
        d_eff = photon_deposition_shot_noise(
            dose, 0.0, dx_nm=dx_nm, photon_energy_eV=E_PH,
            dose_to_energy_factor=F, seed=3,
        )
        # N = D_eff/dose * N_bar must be integer (Poisson draw)
        n_recovered = (d_eff / dose * n_bar).round()
        n_recovered2 = d_eff / dose * n_bar
        assert torch.allclose(n_recovered, n_recovered2, atol=1e-9)

    def test_negative_blur_treated_as_zero(self):
        """se_blur < 0 behaves like se_blur = 0 (no PSF)."""
        dose = uniform_dose((32, 32))
        d_neg = photon_deposition_shot_noise(dose, -3.0, dx_nm=0.25, seed=5)
        d_zero = photon_deposition_shot_noise(dose, 0.0, dx_nm=0.25, seed=5)
        assert torch.allclose(d_neg, d_zero)


# ──────────────────────────────────────────────
# 5. dose = 0 edge case
# ──────────────────────────────────────────────


class TestZeroDose:
    def test_zero_dose_no_nan(self):
        """dose=0 must not produce NaN/Inf."""
        dose = torch.zeros((32, 32), dtype=torch.float64)
        d_eff = photon_deposition_shot_noise(dose, 5.0, dx_nm=0.25, seed=1)
        assert not torch.isnan(d_eff).any()
        assert not torch.isinf(d_eff).any()

    def test_zero_dose_returns_zero(self):
        """dose=0 -> D_eff=0 (no photons -> no deposited energy)."""
        dose = torch.zeros((32, 32), dtype=torch.float64)
        d_eff = photon_deposition_shot_noise(dose, 5.0, dx_nm=0.25, seed=1)
        assert torch.allclose(d_eff, torch.zeros_like(dose), atol=1e-12)

    def test_mixed_zero_and_positive_dose(self):
        """Regions with dose=0 stay 0; positive regions stay finite."""
        dose = torch.zeros((64, 64), dtype=torch.float64)
        dose[16:48, 16:48] = 20.0
        d_eff = photon_deposition_shot_noise(dose, 5.0, dx_nm=0.25, seed=2)
        assert not torch.isnan(d_eff).any()
        assert not torch.isinf(d_eff).any()
        assert (d_eff[:8, :].abs() < 1e-9).all()  # zero-dose border stays ~0
        assert (d_eff[16:48, 16:48] > 0).all()  # exposed region positive


# ──────────────────────────────────────────────
# 6. Spatial correlation
# ──────────────────────────────────────────────


def lag1_autocorr_1d(x: torch.Tensor) -> float:
    """Lag-1 autocorrelation along the last axis (row)."""
    xc = x - x.mean()
    num = (xc[:-1] * xc[1:]).sum().item()
    den = (xc * xc).sum().item()
    return num / den if den > 0 else 0.0


class TestSpatialCorrelation:
    def test_correlation_increases_with_blur(self):
        """Lag-1 autocorrelation of the noise must grow with se_blur."""
        dose = uniform_dose((128, 128), 20.0)
        dx_nm = 0.25
        rel0 = (
            photon_deposition_shot_noise(dose, 0.0, dx_nm=dx_nm, seed=1) / dose
        )
        rel5 = (
            photon_deposition_shot_noise(dose, 5.0, dx_nm=dx_nm, seed=1) / dose
        )
        corr0 = lag1_autocorr_1d(rel0[64, :])
        corr5 = lag1_autocorr_1d(rel5[64, :])
        assert corr5 > corr0 + 0.5, (
            f"lag1: blur=0 -> {corr0:.4f}, blur=5 -> {corr5:.4f}"
        )
        assert corr5 > 0.5, f"blurred noise not correlated: {corr5:.4f}"

    def test_blur_zero_is_white(self):
        """se_blur=0 -> noise essentially uncorrelated (|lag1| small)."""
        dose = uniform_dose((128, 128), 200.0)  # high dose -> enough photons
        dx_nm = 0.25
        rel = photon_deposition_shot_noise(dose, 0.0, dx_nm=dx_nm, seed=2) / dose
        corr = lag1_autocorr_1d(rel[64, :])
        assert abs(corr) < 0.3, f"white noise lag1={corr:.4f} not ~0"


# ──────────────────────────────────────────────
# 7. Grid-resolution invariance
# ──────────────────────────────────────────────


class TestGridInvariance:
    def test_relative_noise_independent_of_grid(self):
        """Relative noise std(D_eff/dose) must not depend on the grid.

        Physical parameters (dose, se_blur, photon energy) are fixed;
        only the numerical resolution changes.  The voxel area must
        cancel out of the relative noise amplitude.
        """
        se_blur_nm = 5.0
        results = {}
        for grid, dx_nm in [(128, 0.5), (256, 0.25), (512, 0.125)]:
            dose = uniform_dose((grid, grid), 20.0)

            # Many realisations -> stable std estimate
            n_rep = 40
            rel_sq_acc = 0.0
            for i in range(n_rep):
                d_eff = photon_deposition_shot_noise(
                    dose, se_blur_nm, dx_nm=dx_nm, photon_energy_eV=E_PH,
                    dose_to_energy_factor=F, seed=i,
                )
                rel = d_eff / dose
                rel_sq_acc += (rel - rel.mean()).pow(2).mean().item()
            rel_std = math.sqrt(rel_sq_acc / n_rep)
            results[(grid, dx_nm)] = rel_std

        # All grid resolutions must give consistent relative noise
        vals = list(results.values())
        mean_v = sum(vals) / len(vals)
        for (grid, dx), v in results.items():
            assert abs(v - mean_v) / mean_v < 0.20, (
                f"grid={grid}, dx={dx}: rel_std={v:.4f} deviates from "
                f"mean {mean_v:.4f} by >20%"
            )


TestGridInvariance._results = {}
