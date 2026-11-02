"""Regression guard: the thin-mask amplitudes refer to one plane, the absorber top.

The thin mask combines the line reflectance a (absorber on the multilayer)
and the space reflectance b (bare multilayer) into c0 = a*eta + b*(1 - eta)
and c_m = (a - b) * sin(pi m eta) / (pi m). Until 2026-10 the two came from
TMM calls of two different stacks, so a referred to the absorber top and b
to the multilayer top, an absorber height lower. The space region missed the
vacuum round trip exp(2 i k d cos(theta0)) through the absorber height, and
arg(a/b) was off by 2 k d cos(6 deg) = 302.5 deg (mod 360) at d = 60 nm:
179.0 deg instead of -123.5 deg for the default Ta mask. The RCWA path, whose
grating layer has vacuum in the spaces, already referred both to the
absorber top.

The amplitudes are taken from the first aerial_from_orders call of
run_simulation; the spy stops the run there.
"""

import math

import pytest
import torch

import euvsimulator.pipeline as pipeline
from euvsimulator.constants import HC_EV_NM
from euvsimulator.materials import CXROTable
from euvsimulator.optics.multilayer import mo_si_stack
from euvsimulator.optics.tmm import reflectivity
from euvsimulator.pipeline import SimulationConfig, run_simulation

THETA0_DEG = 6.0  # chief-ray angle of run_simulation


class _StopError(Exception):
    """Raised by the spy once the orders are captured."""


def _first_orders(monkeypatch, cfg, *, image=False):
    """Orders (and optionally the raw image) of the first aerial_from_orders call."""
    real = pipeline.aerial_from_orders
    seen = {}

    def spy(amplitudes, order_tensor, **kw):
        seen["amp"] = amplitudes.detach().clone()
        seen["m"] = order_tensor.detach().clone()
        if image:
            seen["image"] = real(amplitudes, order_tensor, **kw)
        raise _StopError

    monkeypatch.setattr(pipeline, "aerial_from_orders", spy)
    with pytest.raises(_StopError):
        run_simulation(cfg)
    monkeypatch.setattr(pipeline, "aerial_from_orders", real)
    return seen


def _thin_mask_a_b(monkeypatch, cfg):
    """Line and space reflectances (a, b) recovered from c0 and c1."""
    seen = _first_orders(monkeypatch, cfg)
    amp, m = seen["amp"], seen["m"]
    eta = cfg.line_width_nm / cfg.period_nm
    c0 = complex(amp[m == 0][0])
    c1 = complex(amp[m == 1][0])
    a_minus_b = c1 * math.pi / math.sin(math.pi * eta)
    b = c0 - eta * a_minus_b
    return b + a_minus_b, b


def _vacuum_absorber(monkeypatch, symbol):
    """Make the pipeline's CXRO table return n = 1, k = 0 for ``symbol``."""

    class _Table(CXROTable):
        def refractive_index(self, sym, *args, **kwargs):
            if sym == symbol:
                return 1.0, 0.0
            return super().refractive_index(sym, *args, **kwargs)

    monkeypatch.setattr(pipeline, "CXROTable", _Table)


def _reference(cfg):
    """Independent reference: bare-ML r moved to the absorber top analytically.

    r_ml is the TMM reflectance of the bare multilayer at its own top; the
    space reflectance at the absorber top is r_ml * exp(2 i k d cos(theta0))
    with k = 2 pi / lambda in vacuum. r_abs is the TMM reflectance of the
    absorber-on-multilayer stack at the absorber top.
    """
    energy = HC_EV_NM / cfg.wavelength_nm
    table = CXROTable()
    ml = mo_si_stack(
        n_bilayers=cfg.ml_n_bilayers,
        d_mo_nm=cfg.ml_d_mo_nm,
        d_si_nm=cfg.ml_d_si_nm,
        gamma=cfg.ml_gamma,
        grading_linear_nm=cfg.ml_grading_linear_nm,
        grading_parabolic_nm=cfg.ml_grading_parabolic_nm,
        capping_layer=cfg.ml_capping if cfg.ml_capping != "none" else None,
        d_cap_nm=cfg.ml_capping_nm,
        energy_eV=energy,
    )
    n_si, k_si = table.refractive_index("Si", energy)
    n_sub = torch.tensor(complex(n_si, k_si), dtype=torch.complex128)
    wl = torch.tensor([cfg.wavelength_nm * 1e-9], dtype=torch.float64)
    th = torch.tensor(math.radians(THETA0_DEG), dtype=torch.float64)
    rough = cfg.ml_roughness_nm
    _, r_ml = reflectivity(
        ml.n_layers, ml.thicknesses, wl, th, n_substrate=n_sub, roughness_nm=rough
    )
    n_a, k_a = table.refractive_index(cfg.absorber_material, energy)
    d_m = cfg.absorber_height_nm * 1e-9
    _, r_abs = reflectivity(
        torch.cat([torch.tensor([complex(n_a, k_a)], dtype=torch.complex128), ml.n_layers]),
        torch.cat([torch.tensor([d_m], dtype=torch.float64), ml.thicknesses]),
        wl,
        th,
        n_substrate=n_sub,
        roughness_nm=rough,
    )
    k = 2.0 * math.pi / (cfg.wavelength_nm * 1e-9)
    shift = complex(math.cos(2 * k * d_m * math.cos(th)), math.sin(2 * k * d_m * math.cos(th)))
    r_ml = complex(r_ml[0])
    return complex(r_abs[0]), r_ml, r_ml * shift


def _wrapped(phi):
    return (phi + math.pi) % (2.0 * math.pi) - math.pi


CASES = {
    "default": {},
    "40nm": {"absorber_height_nm": 40.0},
    "rough_Ni": {"absorber_material": "Ni", "ml_roughness_nm": 0.5},
}


@pytest.mark.parametrize("kw", list(CASES.values()), ids=list(CASES))
def test_absorber_phase_is_taken_at_the_absorber_top(monkeypatch, kw):
    cfg = SimulationConfig(grid=64, device="cpu", **kw)
    a, b = _thin_mask_a_b(monkeypatch, cfg)
    r_abs, r_ml, r_ml_top = _reference(cfg)
    # arg(a/b) is the common-plane value ...
    got = math.atan2((a / b).imag, (a / b).real)
    want = math.atan2((r_abs / r_ml_top).imag, (r_abs / r_ml_top).real)
    assert abs(_wrapped(got - want)) < 1e-9, (math.degrees(got), math.degrees(want))
    # ... and both moduli are unchanged (|b| = |r_ML| keeps the dose scale).
    assert abs(a) == pytest.approx(abs(r_abs), rel=1e-12)
    assert abs(b) == pytest.approx(abs(r_ml), rel=1e-12)
    assert abs(b - r_ml_top) < 1e-12


def test_default_absorber_phase_value(monkeypatch):
    """Default Ta mask: arg(a/b) = -123.47 deg (179.0 deg before the fix)."""
    a, b = _thin_mask_a_b(monkeypatch, SimulationConfig(grid=64, device="cpu"))
    phi = math.degrees(math.atan2((a / b).imag, (a / b).real))
    assert phi == pytest.approx(-154.8305, abs=0.01)  # -123.47 before 2.3.0


def test_vacuum_absorber_is_no_absorber(monkeypatch):
    """A 60 nm vacuum 'absorber' is the open frame: a == b, no diffraction,
    a uniform image at the open-frame intensity. Before the fix a was the
    space reflectance moved by exp(2 i k d cos6) = 302.5 deg -- a phase grating.
    """
    cfg = SimulationConfig(grid=64, device="cpu")
    _vacuum_absorber(monkeypatch, cfg.absorber_material)
    a, b = _thin_mask_a_b(monkeypatch, cfg)
    assert abs(a - b) < 1e-12 * abs(b)
    seen = _first_orders(monkeypatch, cfg, image=True)
    amp, m = seen["amp"], seen["m"]
    assert float(amp[m != 0].abs().max()) < 1e-12
    open_frame = abs(b) ** 2
    image = seen["image"] / open_frame
    assert float((image - 1.0).abs().max()) < 1e-9


def test_thin_mask_space_amplitude_matches_rcwa_empty_grating(monkeypatch):
    """With a vacuum absorber the RCWA grating layer is plain vacuum, so its
    TE 0th order is the multilayer reflectance at the absorber top. The
    thin-mask b must be the same number.
    """
    kw = dict(grid=64, device="cpu", n_rcwa_orders=11)
    cfg = SimulationConfig(**kw)
    _vacuum_absorber(monkeypatch, cfg.absorber_material)
    _, b = _thin_mask_a_b(monkeypatch, cfg)
    rcwa = _first_orders(monkeypatch, SimulationConfig(use_rcwa=True, **kw))
    r0_rcwa = complex(rcwa["amp"][rcwa["m"] == 0][0])
    assert abs(b - r0_rcwa) < 1e-6 * abs(r0_rcwa), (b, r0_rcwa)
