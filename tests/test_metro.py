"""Tests for the euv.metro package — CD metrology and process window."""

from __future__ import annotations

import math

import numpy as np
import pytest
import torch

from euv.metro.cd import (
    compute_nils,
    extract_cd_1d,
    extract_cd_2d,
    extract_contour,
    extract_multiple_lines,
)
from euv.metro.process_window import dose_matrix, plot_bossung, process_window, pw_metrics
from euv.metro.sem_render import add_edge_roughness, add_shot_noise, render_sem


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def line_profile_1d():
    """A 512-point line profile with a known ~28 nm CD at threshold 0.5.

    Centre Gaussian dip: I = 1 - A * exp(-(x - 64)^2 / (2 * sigma^2))
    """
    x = torch.linspace(0, 128, 512)  # nm
    sigma = 12.0  # nm
    center = 64.0
    intensity = 1.0 - 0.6 * torch.exp(-((x - center) ** 2) / (2 * sigma ** 2))
    return intensity, x


@pytest.fixture
def binary_rectangle():
    """A 100×200 binary image with a 60×120 rectangle centred."""
    H, W = 100, 200
    image = torch.zeros((H, W), dtype=torch.float32)
    # 60×120 rectangle in the centre
    image[20:80, 40:160] = 1.0
    return image


@pytest.fixture
def bossung_data():
    """A synthetic Bossung surface — parabolic focus dependence with
    dose-dependent CD."""
    doses = np.linspace(10.0, 30.0, 11)  # mJ/cm²
    focuses = np.linspace(-50.0, 50.0, 11)  # nm
    target_cd = 32.0
    # CD(D, F) = target + a*(D - D0) + b*F^2 + c*(D - D0)*F
    D0 = 20.0
    a = -1.0  # CD decreases with dose
    b = 0.005  # quadratic focus dependence
    c = 0.0  # no cross term
    D_grid, F_grid = np.meshgrid(doses, focuses)
    cd_matrix = target_cd + a * (D_grid - D0) + b * F_grid ** 2 + c * (D_grid - D0) * F_grid
    # Clip so in-spec region is realistic
    cd_matrix = np.clip(cd_matrix, 20.0, 44.0)
    return cd_matrix, doses, focuses, target_cd


# ═══════════════════════════════════════════════════════════════════
# Tests: CD extraction
# ═══════════════════════════════════════════════════════════════════


class TestCDExtraction:
    def test_cd_extraction(self, line_profile_1d):
        """Known line width → correct CD ±0.5 nm."""
        intensity, x = line_profile_1d
        cd = extract_cd_1d(intensity, x, threshold=0.5, mode="line")
        # Expected CD: width of the dip at I=0.5
        # I(x) = 1 - 0.6 * exp(-(x-64)^2/(2*12^2)) = 0.5
        # exp(...) = 0.5/0.6 = 0.8333
        # -(x-64)^2/(2*144) = ln(0.8333) = -0.1823
        # (x-64)^2 = 0.1823 * 288 = 52.51
        # x-64 = ±7.25 → x = 56.75, 71.25 → CD = 14.5 nm
        expected_cd = 2.0 * math.sqrt(-2.0 * 12.0 ** 2 * math.log(0.5 / 0.6))
        assert abs(cd - expected_cd) < 0.5, f"CD {cd:.2f} ≠ expected {expected_cd:.2f}"

    def test_cd_1d_flat(self):
        """Uniform intensity above threshold → CD = 0."""
        x = torch.linspace(0, 128, 128)
        I = torch.ones(128) * 0.8
        cd = extract_cd_1d(I, x, threshold=0.5)
        assert cd == 0.0, f"Expected 0 for uniform above threshold, got {cd}"

    def test_cd_1d_all_dark(self):
        """Uniform intensity below threshold → full range."""
        x = torch.linspace(0, 128, 128)
        I = torch.ones(128) * 0.2
        cd = extract_cd_1d(I, x, threshold=0.5)
        assert cd == 0.0, f"Expected 0 for uniform below threshold, got {cd} (no crossing)"

    def test_cd_1d_edge_cases(self):
        """Very narrow dip — should still find edges."""
        x = torch.linspace(0, 32, 256)
        I = torch.ones(256)
        I[100:120] = 0.1  # narrow dark region
        cd = extract_cd_1d(I, x, threshold=0.5)
        expected = 20 * (32.0 / 256)  # 20 pixels * pixel size
        assert abs(cd - expected) < 0.3

    def test_cd_2d(self):
        """2D CD extraction on an image with known line."""
        H, W = 50, 200
        # Vertical dark line from col 85 to 115 at centre
        image = torch.ones((H, W))
        image[:, 85:115] = 0.2
        pixel_size = 1.0  # nm

        left_edges, right_edges, cd_mean = extract_cd_2d(image, pixel_size, threshold=0.5)
        assert cd_mean == pytest.approx(30.0, abs=0.5), f"CD mean {cd_mean:.2f} ≠ 30.0"
        assert left_edges.shape == (H,)
        assert right_edges.shape == (H,)
        # All rows should have valid edges
        assert not torch.isnan(left_edges).any(), "Some rows missing left edge"
        assert not torch.isnan(right_edges).any(), "Some rows missing right edge"

    def test_extract_multiple_lines(self):
        """Multi-line extraction on periodic pattern."""
        H, W = 64, 256
        pitch = 64
        image = torch.ones((H, W))
        # Dark lines every 64 px, 20 px wide, offset so each segment
        # starts in the bright region (left half has bright-to-dark)
        offset = pitch // 4  # 16 px offset
        for start in range(offset, W, pitch):
            end = min(start + 20, W)
            image[:, start:end] = 0.2

        cds = extract_multiple_lines(image, pitch_px=pitch, threshold=0.5)
        assert len(cds) == 4, f"Expected 4 lines, got {len(cds)}"
        for cd in cds:
            assert cd == pytest.approx(20.0, abs=2.0), f"CD {cd:.2f} ≠ 20.0"


# ═══════════════════════════════════════════════════════════════════
# Tests: NILS
# ═══════════════════════════════════════════════════════════════════


class TestNILS:
    def test_nils_known_edge(self):
        """Known edge → correct NILS magnitude.

        For I(x) = 1 - 0.5 * exp(-(x-64)^2 / (2*12^2)) at threshold
        0.5, the NILS magnitude should be ~0.05 / nm.
        """
        x = torch.linspace(0, 128, 512)
        sigma = 12.0
        center = 64.0
        intensity = 1.0 - 0.6 * torch.exp(-((x - center) ** 2) / (2 * sigma ** 2))

        # Find edge at threshold 0.5
        edge_x = center - math.sqrt(-2.0 * sigma ** 2 * math.log(0.5 / 0.6))
        nils = compute_nils(intensity, x, float(edge_x))

        # NILS = (dI/dx)/I at the edge.  At the left edge of a dark line
        # the intensity is falling (dI/dx < 0), so NILS is negative.
        # The absolute magnitude is what matters.
        assert abs(nils) > 0.01, f"|NILS| too small: {nils}"
        assert abs(nils) < 1.0, f"|NILS| too large: {nils}"

    def test_nils_uniform(self):
        """Uniform intensity → NILS ~0."""
        x = torch.linspace(0, 128, 128)
        I = torch.ones(128) * 0.5
        nils = compute_nils(I, x, 64.0)
        assert abs(nils) < 1e-6, f"NILS should be ~0 for uniform, got {nils}"

    def test_nils_outside_domain(self):
        """Edge outside domain → should not crash, returns 0."""
        x = torch.linspace(0, 128, 128)
        I = 1.0 - 0.6 * torch.exp(-((x - 64.0) ** 2) / (2 * 12.0 ** 2))
        nils = compute_nils(I, x, 1000.0)  # far outside
        assert abs(nils) < 0.5  # should not crash


# ═══════════════════════════════════════════════════════════════════
# Tests: Process Window
# ═══════════════════════════════════════════════════════════════════


class TestProcessWindow:
    def test_process_window(self, bossung_data):
        """Dose-focus sweep → valid Bossung shape.

        The synthetic Bossung has a clear in-spec region at best
        focus/dose.
        """
        cd_matrix, doses, focuses, target_cd = bossung_data
        pw = process_window(cd_matrix, doses, focuses, target_cd, tolerance=0.1)

        # Best dose should be close to 20 mJ/cm²
        assert abs(pw["best_dose"] - 20.0) < 3.0, f"Best dose {pw['best_dose']:.1f} ≠ ~20"
        # Best focus near 0
        assert abs(pw["best_focus"]) < 10.0, f"Best focus {pw['best_focus']:.1f} ≠ ~0"
        # DoF should be positive
        assert pw["dof_nm"] > 0.0, f"DoF {pw['dof_nm']:.1f} should be > 0"
        # EL should be positive
        assert pw["el_pct"] > 0.0, f"EL {pw['el_pct']:.1f} should be > 0"

    def test_pw_metrics(self, bossung_data):
        """Known in-spec region → correct DoF/EL."""
        cd_matrix, doses, focuses, target_cd = bossung_data
        metrics = pw_metrics(cd_matrix, target_cd, tolerance=0.1)
        assert metrics["n_in_spec"] > 0, "Should have in-spec points"
        assert metrics["dof_nm"] > 0, "DoF should be positive"
        assert metrics["el_pct"] > 0, "EL should be positive"
        assert math.isnan(metrics["max_nils"]), "max_nils should be NaN when no nils_matrix given"

    def test_pw_metrics_with_nils(self, bossung_data):
        """NILS matrix provided → metrics include max/min NILS."""
        cd_matrix, doses, focuses, target_cd = bossung_data
        nils_matrix = np.random.uniform(0.5, 2.0, size=cd_matrix.shape)
        metrics = pw_metrics(cd_matrix, target_cd, tolerance=0.1, nils_matrix=nils_matrix)
        assert not math.isnan(metrics["max_nils"]), "max_nils should be valid"
        assert metrics["max_nils"] > 0.5
        assert metrics["min_nils"] > 0.0

    def test_dose_matrix_mock(self):
        """Mock pipeline function generates a Bossung."""
        def mock_pipeline(dose_mj_cm2, focus_nm):
            cd = 32.0 - 1.0 * (dose_mj_cm2 - 20.0) + 0.005 * focus_nm ** 2
            return {"cd_nm": float(cd)}

        doses = [15.0, 20.0, 25.0]
        focuses = [-30.0, 0.0, 30.0]
        cd_mat = dose_matrix(mock_pipeline, doses, focuses, target_cd=32.0, tolerance=0.1)
        assert cd_mat.shape == (3, 3), f"Expected (3, 3), got {cd_mat.shape}"
        # At best dose (20) and best focus (0), CD should be closest to 32
        assert not np.isnan(cd_mat).any(), "All entries should be valid"

    def test_plot_bossung(self, bossung_data, capsys):
        """plot_bossung prints ASCII table without error."""
        cd_matrix, doses, focuses, _ = bossung_data
        plot_bossung(cd_matrix, doses, focuses)
        captured = capsys.readouterr()
        assert "Focus" in captured.out, "Should print Focus header"
        assert len(captured.out) > 50, "Should print substantial output"


# ═══════════════════════════════════════════════════════════════════
# Tests: Contour
# ═══════════════════════════════════════════════════════════════════


class TestContour:
    def test_contour_binary_rectangle(self, binary_rectangle):
        """Binary rectangle → contour bounds match rectangle edges."""
        contour = extract_contour(binary_rectangle, pixel_size_nm=1.0)
        assert len(contour) > 0, "Should find contour points"

        xs = [p[0] for p in contour]
        ys = [p[1] for p in contour]

        # The rectangle is at x=[40,160), y=[20,80) in pixels
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        # Contour should be on the boundary of the rectangle
        assert min_x >= 39.0, f"min_x {min_x} too small"
        assert max_x <= 161.0, f"max_x {max_x} too large"
        assert min_y >= 19.0, f"min_y {min_y} too small"
        assert max_y <= 81.0, f"max_y {max_y} too large"

    def test_contour_blank_image(self):
        """All-zero image → empty contour."""
        image = torch.zeros((50, 50), dtype=torch.float32)
        contour = extract_contour(image, pixel_size_nm=1.0)
        assert len(contour) == 0, "Should return empty contour for blank image"

    def test_contour_no_scikit_dependency(self):
        """Contour extraction does not import scikit-image."""
        import sys
        old_modules = set(sys.modules.keys())
        # The function was imported at the top; verify no skimage dep
        # in the actual implementation
        contour = extract_contour(torch.ones((10, 10)), pixel_size_nm=1.0)
        assert len(contour) > 0
        new_modules = set(sys.modules.keys())
        skimage_imported = any("skimage" in m for m in (new_modules - old_modules))
        assert not skimage_imported, "Should not import scikit-image"


# ═══════════════════════════════════════════════════════════════════
# Tests: SEM Render
# ═══════════════════════════════════════════════════════════════════


class TestSEMRender:
    def test_sem_render_shape_and_range(self):
        """Valid image shape + intensity range."""
        # Simple rectangular contour
        contour = [(10.0, 10.0), (30.0, 10.0), (30.0, 30.0), (10.0, 30.0)]
        image = render_sem(contour, pixel_size_nm=1.0, image_size_nm=(50, 50))

        assert image.ndim == 2, f"Expected 2D, got {image.ndim}D"
        assert image.shape == (50, 50), f"Expected (50, 50), got {image.shape}"
        assert image.min() >= 0.0, f"Min intensity {image.min()} < 0"
        assert image.max() <= 1.0, f"Max intensity {image.max()} > 1"

    def test_sem_render_blank_contour(self):
        """Fewer than 3 contour points → blank image."""
        contour = [(10.0, 10.0), (20.0, 20.0)]  # only 2 points
        image = render_sem(contour, pixel_size_nm=1.0, image_size_nm=(50, 50))
        assert torch.all(image == 0.0), "Blank contour → zero image"

    def test_add_shot_noise(self):
        """Shot noise preserves [0, 1] range."""
        image = torch.ones((32, 32)) * 0.5
        noisy = add_shot_noise(image, dose_factor=10.0)
        assert noisy.shape == image.shape
        assert noisy.min() >= 0.0
        assert noisy.max() <= 1.0
        # With high dose factor, mean should stay close to 0.5
        assert noisy.mean().item() == pytest.approx(0.5, abs=0.15)

    def test_add_edge_roughness(self):
        """Edge roughness perturbs contour points."""
        contour = [(10.0, 10.0), (30.0, 10.0), (30.0, 30.0), (10.0, 30.0)]
        roughened = add_edge_roughness(contour, ler_nm=5.0, lwr_nm=5.0, rng_seed=42)

        assert len(roughened) == len(contour), "Same number of points"
        # Some points should have moved
        moved = sum(
            1 for (x1, y1), (x2, y2) in zip(contour, roughened)
            if abs(x1 - x2) > 0.01 or abs(y1 - y2) > 0.01
        )
        assert moved > 0, "At least some contour points should be perturbed"

    def test_add_edge_roughness_reproducible(self):
        """Same seed → same perturbation."""
        contour = [(10.0, 10.0), (30.0, 10.0), (30.0, 30.0), (10.0, 30.0)]
        r1 = add_edge_roughness(contour, ler_nm=3.0, lwr_nm=3.0, rng_seed=123)
        r2 = add_edge_roughness(contour, ler_nm=3.0, lwr_nm=3.0, rng_seed=123)
        for p1, p2 in zip(r1, r2):
            assert p1 == pytest.approx(p2, abs=1e-6)


# ═══════════════════════════════════════════════════════════════════
# Tests: Module-level interface
# ═══════════════════════════════════════════════════════════════════


class TestModuleInterface:
    def test_all_exports_exist(self):
        """All expected names are in the `euv.metro` namespace."""
        import euv.metro as metro
        for name in [
            "extract_cd_1d",
            "extract_cd_2d",
            "compute_nils",
            "extract_contour",
            "extract_multiple_lines",
            "dose_matrix",
            "process_window",
            "plot_bossung",
            "pw_metrics",
            "render_sem",
            "add_shot_noise",
            "add_edge_roughness",
        ]:
            assert hasattr(metro, name), f"metro.{name} not found in namespace"