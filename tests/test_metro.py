"""Tests for the euv.metro package — CD metrology and process window."""

from __future__ import annotations

import math

import numpy as np
import pytest
import torch

from euvsimulator.metro.cd import (
    compute_nils,
    extract_cd_1d,
    extract_cd_2d,
    extract_contour,
    extract_multiple_lines,
)
from euvsimulator.metro.process_window import dose_matrix, plot_bossung, process_window, pw_metrics
from euvsimulator.metro.sem_render import add_edge_roughness, add_shot_noise, render_sem

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
    intensity = 1.0 - 0.6 * torch.exp(-((x - center) ** 2) / (2 * sigma**2))
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
    dose-dependent CD.
    """
    doses = np.linspace(10.0, 30.0, 11)  # mJ/cm²
    focuses = np.linspace(-50.0, 50.0, 11)  # nm
    target_cd = 32.0
    # CD(D, F) = target + a*(D - D0) + b*F^2 + c*(D - D0)*F
    D0 = 20.0
    a = -1.0  # CD decreases with dose
    b = 0.005  # quadratic focus dependence
    c = 0.0  # no cross term
    D_grid, F_grid = np.meshgrid(doses, focuses)
    cd_matrix = target_cd + a * (D_grid - D0) + b * F_grid**2 + c * (D_grid - D0) * F_grid
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
        expected_cd = 2.0 * math.sqrt(-2.0 * 12.0**2 * math.log(0.5 / 0.6))
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

    def test_cd_1d_profile_starting_inside_line(self):
        """A line cut by the left border is skipped, not paired with the next line.

        Pitch 64 nm, dx 0.25 nm, 20 nm lines centred near x = 0, 64 and 128.
        Before the fix the result was 44.0 nm, the width of the space.
        """
        x = torch.arange(512, dtype=torch.float32) * 0.25
        intensity = torch.ones(512)
        intensity[0:40] = 0.2
        intensity[216:296] = 0.2
        intensity[472:512] = 0.2
        cd = extract_cd_1d(intensity, x, threshold=0.6, mode="line")
        assert cd == pytest.approx(20.0, abs=1e-4)
        # The first complete space (between the cut line and the next line)
        cd_space = extract_cd_1d(intensity, x, threshold=0.6, mode="space")
        assert cd_space == pytest.approx(44.0, abs=1e-4)

    def test_cd_1d_space_profile_starting_inside_space(self):
        """Mirror case: mode='space' on a profile that starts bright.

        Before the fix the result was 44.0 nm, the width of the line.
        """
        x = torch.arange(512, dtype=torch.float32) * 0.25
        intensity = torch.full((512,), 0.2)
        intensity[0:40] = 1.0
        intensity[216:296] = 1.0
        intensity[472:512] = 1.0
        cd = extract_cd_1d(intensity, x, threshold=0.6, mode="space")
        assert cd == pytest.approx(20.0, abs=1e-4)

    def test_cd_2d_rows_starting_inside_line(self):
        """extract_cd_2d: left edge left of right edge, CD of the complete line.

        Before the fix: left 53.875 nm, right 9.875 nm, cd_mean 44.0 nm.
        """
        row = torch.ones(512)
        row[0:40] = 0.2
        row[216:296] = 0.2
        row[472:512] = 0.2
        image = row.unsqueeze(0).repeat(4, 1)
        left, right, cd_mean = extract_cd_2d(image, 0.25, threshold=0.6)
        assert torch.allclose(left, torch.full((4,), 53.875))
        assert torch.allclose(right, torch.full((4,), 73.875))
        assert cd_mean == pytest.approx(20.0, abs=1e-4)

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

    def test_extract_multiple_lines_lines_on_stripe_edges(self):
        """Lines centred on multiples of the pitch: every complete line is measured.

        Pitch 40 px, 12 px lines centred at x = 0, 40, 80, 120 and 160 in a
        160 px row; the lines at x = 0 and x = 160 are cut by the border.
        Before the fix the result was [28, 28, 28, 28] px, the spaces.
        """
        W = 160
        image = torch.ones((8, W))
        for centre in range(0, W + 1, 40):
            lo = max(centre - 6, 0)
            hi = min(centre + 6, W)
            image[:, lo:hi] = 0.2
        cds = extract_multiple_lines(image, pitch_px=40, threshold=0.6)
        assert cds.tolist() == pytest.approx([12.0, 12.0, 12.0], abs=1e-4)

    def test_extract_multiple_lines_rejects_bad_pitch(self):
        """pitch_px below 1 raises ValueError."""
        with pytest.raises(ValueError):
            extract_multiple_lines(torch.ones((4, 16)), pitch_px=0)

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
        intensity = 1.0 - 0.6 * torch.exp(-((x - center) ** 2) / (2 * sigma**2))

        # Find edge at threshold 0.5
        edge_x = center - math.sqrt(-2.0 * sigma**2 * math.log(0.5 / 0.6))
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

    def test_nils_with_cd_is_mack_nils(self):
        """With cd_nm the result is CD * |dI/dx| / I (Mack), not the 1/nm log-slope.

        I = 0.5 + 0.5 cos(2 pi (x - 64) / 64): at x = 48 and x = 80 the exact
        log-slope magnitude is pi / 32 = 0.0982 1/nm, so NILS(CD 32 nm) = pi.
        The 1 nm central difference gives 0.09802 1/nm and NILS 3.1365.
        """
        x = torch.linspace(0, 128, 1281)
        intensity = 0.5 + 0.5 * torch.cos(2 * math.pi * (x - 64) / 64)
        # Default output unchanged: signed log-slope in 1/nm
        assert compute_nils(intensity, x, 48.0) == pytest.approx(0.09802, abs=1e-4)
        assert compute_nils(intensity, x, 80.0) == pytest.approx(-0.09802, abs=1e-4)
        for edge in (48.0, 80.0):
            nils = compute_nils(intensity, x, edge, cd_nm=32.0)
            assert nils == pytest.approx(math.pi, abs=0.01)

    def test_nils_rejects_non_positive_cd(self):
        """cd_nm <= 0 raises ValueError."""
        x = torch.linspace(0, 128, 129)
        intensity = torch.ones(129)
        with pytest.raises(ValueError):
            compute_nils(intensity, x, 64.0, cd_nm=0.0)

    def test_ils_near_domain_end_uses_one_sided_step(self):
        """Near the ends the step stays inside the profile; outside it returns 0.

        I = 1 + 0.01 x on [0, 10]: the exact log-slope at x = 0.5 is
        0.01 / 1.005 = 0.0099502 1/nm.  Before the fix: 0.0074627 (the
        clamped sample lowered the slope by 25 %) and 0.0030 at x = -0.4.
        """
        x = torch.linspace(0, 10, 101)
        intensity = 1.0 + 0.01 * x
        assert compute_nils(intensity, x, 0.5) == pytest.approx(0.01 / 1.005, abs=1e-6)
        assert compute_nils(intensity, x, 9.5) == pytest.approx(0.01 / 1.095, abs=1e-6)
        assert compute_nils(intensity, x, -0.4) == 0.0
        assert compute_nils(intensity, x, 10.4) == 0.0

    def test_nils_outside_domain(self):
        """Edge outside domain → should not crash, returns 0."""
        x = torch.linspace(0, 128, 128)
        I = 1.0 - 0.6 * torch.exp(-((x - 64.0) ** 2) / (2 * 12.0**2))
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
        metrics = pw_metrics(cd_matrix, target_cd, tolerance=0.1, doses=doses, focuses=focuses)
        assert metrics["n_in_spec"] > 0, "Should have in-spec points"
        assert metrics["dof_nm"] > 0, "DoF should be positive"
        assert metrics["el_pct"] > 0, "EL should be positive"
        assert metrics["dof_steps"] > 0 and metrics["el_steps"] > 0
        assert math.isnan(metrics["max_nils"]), "max_nils should be NaN when no nils_matrix given"
        # Hand-computed for CD = 32 - (D - 20) + 0.005 F², spec ±3.2 nm: the
        # CD-exact candidates tie; (F -20, D 22) has the largest contiguous
        # window: F -30..30 (60 nm) and D 20..24 (4/22 = 18.18 %).
        assert metrics["dof_nm"] == pytest.approx(60.0)
        assert metrics["el_pct"] == pytest.approx(400.0 / 22.0)
        # process_window() fixes best focus on the central dose column
        # (F 0, D 20): F -20..20 and D 18..22.  A different definition, so
        # the two functions need not agree.
        pw = process_window(cd_matrix, doses, focuses, target_cd, tolerance=0.1)
        assert pw["dof_nm"] == pytest.approx(40.0)
        assert pw["el_pct"] == pytest.approx(20.0)
        # Without the grids only step counts are available
        bare = pw_metrics(cd_matrix, target_cd, tolerance=0.1)
        assert math.isnan(bare["dof_nm"]) and math.isnan(bare["el_pct"])
        assert bare["dof_steps"] == metrics["dof_steps"]

    def test_window_does_not_bridge_an_out_of_spec_gap(self):
        """In-spec at F = -40 and +40 but not at 0: DoF is not 80 nm."""
        focuses = [-40.0, -20.0, 0.0, 20.0, 40.0]
        doses = [19.0, 20.0, 21.0]
        cd = np.full((5, 3), 32.0)
        cd[1:4, :] = 40.0  # F = -20, 0, 20 out of spec at every dose
        m = pw_metrics(cd, 32.0, 0.1, doses=doses, focuses=focuses)
        assert m["dof_steps"] == 0 and math.isnan(m["dof_nm"])
        pw = process_window(cd, doses, focuses, 32.0, tolerance=0.1)
        assert pw["dof_nm"] == 0.0

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
            cd = 32.0 - 1.0 * (dose_mj_cm2 - 20.0) + 0.005 * focus_nm**2
            return {"cd_nm": float(cd)}

        doses = [15.0, 20.0, 25.0]
        focuses = [-30.0, 0.0, 30.0]
        cd_mat = dose_matrix(mock_pipeline, doses, focuses, target_cd=32.0, tolerance=0.1)
        assert cd_mat.shape == (3, 3), f"Expected (3, 3), got {cd_mat.shape}"
        # At best dose (20) and best focus (0), CD should be closest to 32
        assert not np.isnan(cd_mat).any(), "All entries should be valid"

    def test_dose_matrix_accepts_any_parameter_names(self):
        """The callback is called positionally, so (dose, focus) works as well."""

        def fn(dose, focus):
            return {"cd_nm": 32.0 - (dose - 20.0) + 0.005 * focus**2}

        cd_mat = dose_matrix(fn, [15.0, 20.0], [-30.0, 0.0, 30.0])
        assert cd_mat.shape == (3, 2) and not np.isnan(cd_mat).any()

    def test_dose_matrix_does_not_hide_errors(self):
        """A failing callback raises instead of silently filling the matrix with NaN."""

        def broken(dose, focus):
            raise RuntimeError("simulation failed")

        with pytest.raises(RuntimeError):
            dose_matrix(broken, [20.0], [0.0])

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

    def test_contour_round_trip_is_exact(self):
        """extract_contour -> render_sem (no blur, no noise) gives the mask back.

        Before the fix a 31 x 20 px rectangle came back as 30 x 19 px
        (570 of 620 px) and an L shape had IoU 0.40.
        """
        rect = torch.zeros((60, 60))
        rect[10:41, 20:40] = 1.0
        ell = torch.zeros((60, 60))
        ell[10:50, 10:20] = 1.0
        ell[40:50, 10:50] = 1.0
        u_shape = torch.zeros((50, 50))
        u_shape[10:40, 10:16] = 1.0
        u_shape[10:40, 34:40] = 1.0
        u_shape[34:40, 10:40] = 1.0
        full = torch.ones((10, 10))
        for mask in (rect, ell, u_shape, full):
            H, W = mask.shape
            contour = extract_contour(mask, pixel_size_nm=1.0)
            image = render_sem(
                contour,
                pixel_size_nm=1.0,
                image_size_nm=(W, H),
                blur_sigma_nm=0.0,
                noise_sigma=0.0,
            )
            assert torch.equal(image > 0.5, mask > 0.5)

    def test_contour_is_ordered_unit_steps(self):
        """Neighbouring points, including last -> first, are one pixel apart."""
        ell = torch.zeros((30, 30))
        ell[5:25, 5:10] = 1.0
        ell[20:25, 5:25] = 1.0
        contour = extract_contour(ell, pixel_size_nm=2.0)
        assert len(contour) == 80  # perimeter of the 20 x 20 px L in pixel edges
        assert contour[0] == (9.0, 9.0)  # top-left corner of pixel (5, 5)
        for k in range(len(contour)):
            x0, y0 = contour[k - 1]
            x1, y1 = contour[k]
            assert abs(x1 - x0) + abs(y1 - y0) == 2.0
            assert x1 == x0 or y1 == y0

    def test_contour_first_feature_only(self):
        """Only the outer boundary of the first feature in row-major order is traced."""
        two = torch.zeros((80, 80))
        two[10:70, 10:30] = 1.0
        two[10:70, 50:70] = 1.0
        contour = extract_contour(two, pixel_size_nm=1.0)
        xs = [p[0] for p in contour]
        ys = [p[1] for p in contour]
        assert (min(xs), max(xs), min(ys), max(ys)) == (9.5, 29.5, 9.5, 69.5)
        assert len(contour) == 160
        ring = torch.zeros((40, 40))
        ring[10:30, 10:30] = 1.0
        ring[15:25, 15:25] = 0.0
        contour = extract_contour(ring, pixel_size_nm=1.0)
        assert len(contour) == 80  # outer square only, the hole is ignored

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
            1
            for (x1, y1), (x2, y2) in zip(contour, roughened)
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

    @staticmethod
    def _line_contour(n=2000, width=32.0, length=1000.0, angle_deg=0.0):
        """Closed contour of a straight line: right edge upward, left edge downward."""
        ys = [length * i / (n - 1) for i in range(n)]
        pts = [(width / 2, y) for y in ys] + [(-width / 2, y) for y in reversed(ys)]
        c = math.cos(math.radians(angle_deg))
        s = math.sin(math.radians(angle_deg))
        return [(c * x - s * y, s * x + c * y) for x, y in pts]

    @pytest.mark.parametrize("angle_deg", [0.0, 30.0])
    @pytest.mark.parametrize(
        "ler, lwr", [(2.0, 2.0), (2.0, 0.0), (2.0, 2.0 * math.sqrt(2.0)), (2.0, 4.0)]
    )
    def test_add_edge_roughness_sets_ler_and_lwr(self, ler, lwr, angle_deg):
        """On a straight line the edge std is ler_nm and the width std is lwr_nm."""
        n = 2000
        contour = self._line_contour(n=n, angle_deg=angle_deg)
        rough = add_edge_roughness(contour, ler_nm=ler, lwr_nm=lwr, rng_seed=7)
        d = torch.tensor(rough, dtype=torch.float64) - torch.tensor(contour, dtype=torch.float64)
        a = math.radians(angle_deg)
        across = d[:, 0] * math.cos(a) + d[:, 1] * math.sin(a)  # shift across the line
        k = 5  # skip the corner points, whose normals are diagonal
        right = across[k : n - k]
        left = torch.flip(across[n:], dims=[0])[k : n - k]
        assert right.std().item() == pytest.approx(ler, rel=0.06)
        assert left.std().item() == pytest.approx(ler, rel=0.06)
        width_std = (right - left).std().item()
        if lwr == 0.0:
            assert width_std < 1e-3
        else:
            assert width_std == pytest.approx(lwr, rel=0.06)

    def test_add_edge_roughness_rejects_impossible_values(self):
        """lwr_nm above 2 * ler_nm and negative values raise ValueError."""
        contour = [(10.0, 10.0), (30.0, 10.0), (30.0, 30.0), (10.0, 30.0)]
        with pytest.raises(ValueError):
            add_edge_roughness(contour, ler_nm=0.0, lwr_nm=2.0)
        with pytest.raises(ValueError):
            add_edge_roughness(contour, ler_nm=2.0, lwr_nm=4.5)
        with pytest.raises(ValueError):
            add_edge_roughness(contour, ler_nm=-1.0, lwr_nm=0.0)

    def test_add_edge_roughness_keeps_global_rng(self):
        """A seed must not reset or advance the global torch RNG."""
        contour = [(10.0, 10.0), (30.0, 10.0), (30.0, 30.0), (10.0, 30.0)]
        torch.manual_seed(0)
        state = torch.get_rng_state().clone()
        add_edge_roughness(contour, ler_nm=2.0, lwr_nm=2.0, rng_seed=5)
        assert torch.equal(state, torch.get_rng_state())


# ═══════════════════════════════════════════════════════════════════
# Tests: Module-level interface
# ═══════════════════════════════════════════════════════════════════


class TestModuleInterface:
    def test_all_exports_exist(self):
        """All expected names are in the `euvsimulator.metro` namespace."""
        import euvsimulator.metro as metro

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
