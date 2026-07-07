"""Tests for the Hopkins/TCC aerial image module."""

from __future__ import annotations

import pytest
import torch

from euv.aerial.hopkins import (
    compare_hopkins_abbe,
    compute_tcc,
    hopkins_aerial,
    tcc_soc_decomposition,
)
from euv.aerial.pupil import circular_pupil, pupil_grid
from euv.aerial.source import conventional, dipole_x

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def G() -> int:
    """Default grid size for tests."""
    return 24


@pytest.fixture
def na() -> float:
    return 0.33


@pytest.fixture
def sigma() -> float:
    return 0.8


@pytest.fixture
def source(G: int, sigma: float) -> torch.Tensor:
    return conventional(G, sigma=sigma)


@pytest.fixture
def pupil(G: int, na: float) -> torch.Tensor:
    return circular_pupil(G, na=na)


@pytest.fixture
def fx_fy(G: int, na: float):
    """Return (fx, fy, _) from pupil_grid."""
    return pupil_grid(G, na=na)


@pytest.fixture
def thin_mask(G: int) -> torch.Tensor:
    """A simple thin-mask: centred dark line on bright background.

    This produces a diffraction spectrum that a partially coherent
    system can image correctly — a good reference for comparing
    Hopkins vs. Abbe.
    """
    mask = torch.ones(G, G, dtype=torch.float64)
    # Dark line in the centre (3 pixels wide)
    half = G // 2
    mask[half - 1 : half + 2, :] = 0.0
    return mask


# ── TCC symmetry ──────────────────────────────────────────────────────


class TestTccSymmetry:
    """Verify that the TCC matrix is Hermitian (conjugate symmetric)."""

    def test_hermitian_property(self, G: int, na: float, source: torch.Tensor, pupil: torch.Tensor):
        tcc = compute_tcc(source, pupil, na=na, grid=G)
        # TCC should equal its conjugate transpose
        diff = tcc - tcc.mH
        max_violation = diff.abs().max().item()
        assert max_violation < 1e-10, f"TCC is not Hermitian (max violation = {max_violation:.2e})"

    def test_diagonal_real(self, G: int, na: float, source: torch.Tensor, pupil: torch.Tensor):
        tcc = compute_tcc(source, pupil, na=na, grid=G)
        diag = tcc.diag()
        # Diagonal of a Hermitian matrix must be real
        imag_part = diag.imag.abs().max().item()
        assert imag_part < 1e-12, f"TCC diagonal has imaginary part = {imag_part:.2e}"

    def test_small_grid_hermitian(self):
        """Test on a very small grid (faster)."""
        G = 16
        src = conventional(G, sigma=0.8)
        pup = circular_pupil(G, na=0.33)
        tcc = compute_tcc(src, pup, na=0.33, grid=G)
        diff = tcc - tcc.mH
        assert diff.abs().max().item() < 1e-10


# ── SOCS decomposition ────────────────────────────────────────────────


class TestTccDecomposition:
    """Verify the SOCS kernel properties."""

    def test_kernels_orthonormal(
        self, G: int, na: float, source: torch.Tensor, pupil: torch.Tensor
    ):
        tcc = compute_tcc(source, pupil, na=na, grid=G)
        n_kernels = min(16, G * G)
        kernels = tcc_soc_decomposition(tcc, n_kernels=n_kernels)

        # Each kernel is (G, G); flatten to (n_kernels, G²)
        flat = kernels.reshape(n_kernels, -1)  # (N, G²)

        # Inner product: <Φ_i, Φ_j> should be λ_i * δ_ij
        # For the weighted kernels, inner = sum(conj(Φ_i) * Φ_j) = λ_i * δ_ij
        # Since kernels = sqrt(λ) * Φ, the inner product:
        # Σ conj(k_i) * k_j = sqrt(λ_i*λ_j) * Σ conj(Φ_i) * Φ_j
        #                    = sqrt(λ_i*λ_j) * δ_ij

        # Check that different kernels are approximately orthogonal
        for i in range(min(8, n_kernels)):
            for j in range(i + 1, min(8, n_kernels)):
                inner = (flat[i].conj() * flat[j]).sum().abs().item()
                assert (
                    inner < 1e-8
                ), f"SOCS kernels {i} and {j} not orthogonal (inner = {inner:.2e})"

    def test_kernel_shape(self, G: int, na: float, source: torch.Tensor, pupil: torch.Tensor):
        tcc = compute_tcc(source, pupil, na=na, grid=G)
        n_kernels = 8
        kernels = tcc_soc_decomposition(tcc, n_kernels=n_kernels)
        assert kernels.shape == (
            n_kernels,
            G,
            G,
        ), f"Expected ({n_kernels}, {G}, {G}), got {kernels.shape}"

    def test_dtype_complex128(self, G: int, na: float, source: torch.Tensor, pupil: torch.Tensor):
        tcc = compute_tcc(source, pupil, na=na, grid=G)
        kernels = tcc_soc_decomposition(tcc, n_kernels=4)
        assert kernels.dtype == torch.complex128

    def test_eigenvalues_positive(
        self, G: int, na: float, source: torch.Tensor, pupil: torch.Tensor
    ):
        tcc = compute_tcc(source, pupil, na=na, grid=G)
        n_kernels = 16
        kernels = tcc_soc_decomposition(tcc, n_kernels=n_kernels)
        # The norm (sum of |kernel|²) should be positive for all kernels
        norms = (kernels.abs() ** 2).reshape(n_kernels, -1).sum(dim=1)
        assert (norms > 0).all(), "Some SOCS kernels have zero norm"


# ── Hopkins vs Abbe comparison ────────────────────────────────────────


class TestHopkinsAerial:
    """Compare Hopkins/TCC imaging with the Abbe reference."""

    def test_hopkins_aerial_matches_abbe(
        self,
        G: int,
        na: float,
        source: torch.Tensor,
        pupil: torch.Tensor,
        thin_mask: torch.Tensor,
        fx_fy,
    ):
        """For thin-mask, Hopkins ≈ Abbe within ~1%."""
        fx, fy, _ = fx_fy

        result = compare_hopkins_abbe(thin_mask, source, pupil, fx, fy, na=na, grid=G)

        # Both images should have plausible shape
        assert result["hopkins_aerial"].shape == (G, G)
        assert result["abbe_aerial"].shape == (G, G)

        # Relative error should be small (< 2% with SOCS truncation to 64 kernels)
        rel_err = result["relative_error"]
        assert rel_err < 0.02, f"Hopkins/Abbe relative error too large: {rel_err:.4f} (> 2%)"

        # MAE should be reasonable
        mae = result["mae"]
        assert mae < 0.005, f"MAE too large: {mae:.6f}"

    def test_nonnegative_intensity(
        self,
        G: int,
        na: float,
        source: torch.Tensor,
        pupil: torch.Tensor,
        thin_mask: torch.Tensor,
        fx_fy,
    ):
        """Aerial image intensities must be non-negative."""
        fx, fy, _ = fx_fy
        result = compare_hopkins_abbe(thin_mask, source, pupil, fx, fy, na=na, grid=G)
        assert (result["hopkins_aerial"] >= -1e-12).all()
        assert (result["abbe_aerial"] >= -1e-12).all()


# ── Direct hopkins_aerial API ─────────────────────────────────────────


class TestDirectHopkinsAerial:
    """Test the hopkins_aerial function directly."""

    def test_basic_call(self, G: int, na: float, source: torch.Tensor, pupil: torch.Tensor):
        tcc = compute_tcc(source, pupil, na=na, grid=G)
        n_kernels = 8
        kernels = tcc_soc_decomposition(tcc, n_kernels=n_kernels)

        mask = torch.ones(G, G, dtype=torch.float64)
        mask_fft = torch.fft.fft2(mask)

        aerial = hopkins_aerial(mask_fft, kernels)
        assert aerial.shape == (G, G)
        assert aerial.dtype == torch.float64
        assert (aerial >= -1e-12).all()


# ── Dipole illumination ───────────────────────────────────────────────


class TestDipoleIllumination:
    """Test that Hopkins/TCC works correctly with dipole source."""

    @pytest.fixture
    def dipole_src(self, G: int) -> torch.Tensor:
        return dipole_x(G, sigma=0.15, sigma_out=0.7, separation=0.55)

    def test_dipole_tcc(self, G: int, na: float, pupil: torch.Tensor, dipole_src):
        tcc = compute_tcc(dipole_src, pupil, na=na, grid=G)
        # TCC should be Hermitian
        diff = tcc - tcc.mH
        assert diff.abs().max().item() < 1e-10

    def test_dipole_aerial(
        self,
        G: int,
        na: float,
        pupil: torch.Tensor,
        dipole_src,
        thin_mask: torch.Tensor,
        fx_fy,
    ):
        fx, fy, _ = fx_fy
        result = compare_hopkins_abbe(thin_mask, dipole_src, pupil, fx, fy, na=na, grid=G)

        # With dipole the SOCS truncation may give larger errors, but should still
        # be reasonable
        assert result["hopkins_aerial"].shape == (G, G)
        assert result["abbe_aerial"].shape == (G, G)
        assert (result["hopkins_aerial"] >= -1e-12).all()
        assert (result["abbe_aerial"] >= -1e-12).all()

        # For dipole, relative error < 5% with 64 kernels
        rel_err = result["relative_error"]
        assert rel_err < 0.05, f"Dipole Hopkins/Abbe relative error too large: {rel_err:.4f} (> 5%)"


# ── Kernel shape ──────────────────────────────────────────────────────


class TestSocKernelShape:
    """Verify SOCS kernel shapes."""

    def test_kernel_count(self, G: int, na: float, source: torch.Tensor, pupil: torch.Tensor):
        tcc = compute_tcc(source, pupil, na=na, grid=G)
        # Test multiple kernel counts from the same TCC
        for n in [1, 4, 16, 48]:
            kernels = tcc_soc_decomposition(tcc, n_kernels=n)
            expected = min(n, G * G)
            assert kernels.shape[0] == expected, f"Requested {n} kernels, got {kernels.shape[0]}"
            assert kernels.shape[1:] == (G, G)

    def test_more_kernels_than_rank(
        self, G: int, na: float, source: torch.Tensor, pupil: torch.Tensor
    ):
        """Requesting more kernels than the TCC rank should clamp gracefully."""
        tcc = compute_tcc(source, pupil, na=na, grid=G)
        n_kernels = G * G + 100  # more than possible
        kernels = tcc_soc_decomposition(tcc, n_kernels=n_kernels)
        assert kernels.shape[0] <= G * G
        assert kernels.shape[1:] == (G, G)


# ── Speed note ────────────────────────────────────────────────────────


class TestHopkinsSpeed:
    """Note on speed characteristics.

    For a single mask, Abbe is competitive.  For large iteration counts
    (thousands of masks in an OPC loop), the TCC is pre-computed once and
    each mask images in O(N² log N) vs. Abbe's O(N_src × N² log N).
    """

    def test_tcc_precompute_then_fast(
        self, G: int, na: float, source: torch.Tensor, pupil: torch.Tensor
    ):
        """Verify the two-phase workflow: precompute TCC, then image many masks.

        This is a functional test, not a benchmark — it verifies that
        the precomputation pattern works correctly.
        """
        # Phase 1: Precompute TCC and kernels once
        tcc = compute_tcc(source, pupil, na=na, grid=G)
        n_kernels = 16
        kernels = tcc_soc_decomposition(tcc, n_kernels=n_kernels)

        # Phase 2: Image several masks using the same kernels
        masks = []
        for i in range(3):
            m = torch.ones(G, G, dtype=torch.float64)
            half = G // 2
            offset = i - 1
            center = half + offset
            m[center - 1 : center + 2, :] = 0.0
            masks.append(m)

        for m in masks:
            m_fft = torch.fft.fft2(m)
            aerial = hopkins_aerial(m_fft, kernels)
            assert aerial.shape == (G, G)
            assert (aerial >= -1e-12).all()

    def test_hopkins_faster_comment(self):
        """Documentation: for large iteration counts Hopkins is faster.

        The TCC is precomputed once (O(G⁶) naive / O(G⁴) optimised)
        and then each mask is imaged in O(N × G² log G) via SOCS,
        where N << G² is the number of retained kernels.

        Abbe images each mask in O(N_src × G² log G) where N_src is
        the number of illuminated source points — typically O(G²).

        For N_masks > (G² / N), Hopkins wins.
        """
        pass  # This is a documentation/test marker


# ── Edge cases ────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_source(self, G: int, na: float, pupil: torch.Tensor):
        """Zero source → zero TCC."""
        src = torch.zeros(G, G, dtype=torch.float64)
        tcc = compute_tcc(src, pupil, na=na, grid=G)
        expected = G * G
        assert tcc.shape == (expected, expected)
        assert tcc.abs().max().item() == 0.0

    def test_uniform_mask(
        self, G: int, na: float, source: torch.Tensor, pupil: torch.Tensor, fx_fy
    ):
        """Uniform mask → constant aerial image."""
        fx, fy, _ = fx_fy
        mask = torch.ones(G, G, dtype=torch.float64)
        result = compare_hopkins_abbe(mask, source, pupil, fx, fy, na=na, grid=G)
        # The aerial should be nearly constant
        hop_img = result["hopkins_aerial"]
        std = hop_img.std().item()
        assert std < 0.01, f"Uniform mask aerial not constant (std = {std:.4f})"
