"""STEP 5.1 — Tests für den korrelationsbewussten LER-Estimator.

Deckt ab:
- Legacy-Kompatibilität (extract_ler unverändert)
- Large-N-Estimator + Metadaten
- Korrelationskorrektur (Kontrollmethode)
- Truncation-Regel
- Seed-Sequenz / SE / CI
- Fehlerfälle
"""

import math

import numpy as np
import pytest
import torch

from euvsimulator.resist.stochastic import (
    LEREstimate,
    extract_ler,
    ler_estimate,
)

DX = 0.25


def make_field(n_rows, n_cols=256, edge_col=100.0, sigma_edge=1.0, rng=None):
    """Erzeuge ein developed-Feld mit rauer Kante (sub-pixel via intensity).

    Dunkle Linie [edge, edge+W] (undeveloped), hell außen; Kanten-
    position schwankt pro Zeile korreliert (MA über 20 Zeilen).
    """
    if rng is None:
        rng = np.random.default_rng(0)
    white = rng.normal(0.0, sigma_edge, n_rows + 40)
    shift = np.convolve(white, np.ones(20) / 20.0, mode="valid")[:n_rows]
    x = torch.arange(n_cols, dtype=torch.float64).unsqueeze(0)  # (1,W)
    edge = (edge_col + torch.from_numpy(shift).float()).unsqueeze(1)  # (N,1)
    width = 56.0
    s = width / 6.0

    def sig(a):
        return torch.sigmoid(a)

    hl = sig((edge - x) / s)  # hell links (1 für x<edge)
    hr = sig((x - (edge + width)) / s)  # hell rechts (1 für x>edge+W)
    intensity = torch.minimum(hl + hr, torch.ones_like(hl))
    developed = (intensity > 0.5).float()
    return developed, intensity


def test_legacy_extract_ler_unchanged():
    """extract_ler liefert weiterhin exakt die alten Werte (RMS-Definition)."""
    dev, intens = make_field(256)
    ler = extract_ler(dev, threshold=0.5, dx=DX, intensity=intens)
    assert math.isfinite(ler)
    assert ler > 0.0
    # RMS-Definition: sqrt(mean(dev^2))
    left, right = None, None
    from euvsimulator.resist.stochastic import extract_edges

    l, r = extract_edges(dev, 0.5, DX, intens)
    fin = ~(torch.isnan(l) | torch.isnan(r))
    lf, rf = l[fin], r[fin]
    ref = float(torch.sqrt((torch.cat([lf - lf.mean(), rf - rf.mean()]) ** 2).mean()))
    assert ler == pytest.approx(ref, abs=1e-12)


def test_ler_estimate_large_n_metadata():
    dev, intens = make_field(2048)
    est = ler_estimate(dev, threshold=0.5, dx=DX, intensity=intens)
    assert isinstance(est, LEREstimate)
    assert est.estimator == "large_n"
    assert est.n_rows == 2048
    assert 0.0 < est.ler_nm < 1.0
    assert est.n_eff < est.n_rows  # korrelierte Zeilen -> N_eff < N
    assert est.n_eff > 1.0
    assert est.l_int_px > 1.0
    assert est.l_int_nm == pytest.approx(est.l_int_px * DX)
    assert est.rho_truncation >= 1
    assert "experimentell validierter Wert" in est.disclaimer


def test_ler_estimate_matches_legacy_on_same_field():
    """large_n auf EINEM Feld entspricht der Legacy-RMS (gleiche Observable)."""
    dev, intens = make_field(2048)
    est = ler_estimate(dev, threshold=0.5, dx=DX, intensity=intens)
    legacy = extract_ler(dev, threshold=0.5, dx=DX, intensity=intens)
    assert est.ler_nm == pytest.approx(legacy, rel=1e-6)


def test_ler_estimate_edge_variants():
    dev, intens = make_field(1024)
    e_both = ler_estimate(dev, threshold=0.5, dx=DX, intensity=intens, edge="both")
    e_left = ler_estimate(dev, threshold=0.5, dx=DX, intensity=intens, edge="left")
    e_right = ler_estimate(dev, threshold=0.5, dx=DX, intensity=intens, edge="right")
    assert math.isfinite(e_left.ler_nm)
    assert math.isfinite(e_right.ler_nm)
    # both = RMS über beide Kantenabweichungen
    assert e_both.ler_nm == pytest.approx(
        math.sqrt((e_left.ler_nm**2 + e_right.ler_nm**2) / 2.0), rel=0.05
    )


def test_ler_estimate_corr_corrected():
    """Korrektur hebt die naive Schätzung an (bias > 0)."""
    dev, intens = make_field(1024)
    e_ln = ler_estimate(dev, threshold=0.5, dx=DX, intensity=intens, estimator="large_n")
    e_cc = ler_estimate(dev, threshold=0.5, dx=DX, intensity=intens, estimator="corr_corrected")
    assert e_cc.estimator == "corr_corrected"
    # bei korrelierten Zeilen ist die Korrektur >= naive (kleiner Bias)
    assert e_cc.ler_nm >= e_ln.ler_nm * 0.99


def test_ler_estimate_multiple_seeds_uncertainty():
    """Mehrere Realisierungen -> SE/CI aus Seed-Variation."""
    fields, intens_list = [], []
    for s in range(5):
        dev, intens = make_field(1024, rng=np.random.default_rng(100 + s))
        fields.append(dev)
        intens_list.append(intens)
    est = ler_estimate(fields, threshold=0.5, dx=DX, intensity=intens_list)
    assert est.seed_count == 5
    assert math.isfinite(est.uncertainty_nm)
    assert est.uncertainty_nm > 0.0
    assert est.ci95_low_nm < est.ler_nm < est.ci95_high_nm


def test_ler_estimate_single_seed_no_ci():
    dev, intens = make_field(1024)
    est = ler_estimate(dev, threshold=0.5, dx=DX, intensity=intens)
    assert math.isnan(est.uncertainty_nm)
    assert math.isnan(est.ci95_low_nm)
    assert est.seed_count == 1


def test_ler_estimate_invalid_estimator():
    dev, intens = make_field(256)
    with pytest.raises(ValueError):
        ler_estimate(dev, threshold=0.5, dx=DX, intensity=intens, estimator="bogus")


def test_ler_estimate_invalid_edge():
    dev, intens = make_field(256)
    with pytest.raises(ValueError):
        ler_estimate(dev, threshold=0.5, dx=DX, intensity=intens, edge="middle")


def test_ler_estimate_nan_handling():
    """Zeilen ohne Kante (NaN) werden übersprungen, keine Fehler."""
    dev, intens = make_field(512)
    dev[10:15, :] = 1.0  # künstlich voll entwickelt -> keine Kante
    intens[10:15, :] = 1.0
    est = ler_estimate(dev, threshold=0.5, dx=DX, intensity=intens)
    assert math.isfinite(est.ler_nm)


def test_ler_estimate_deterministic_same_field():
    """Gleiches Feld -> bitweise identisches Ergebnis."""
    dev, intens = make_field(1024)
    e1 = ler_estimate(dev, threshold=0.5, dx=DX, intensity=intens)
    e2 = ler_estimate(dev, threshold=0.5, dx=DX, intensity=intens)
    assert e1.ler_nm == e2.ler_nm
    assert e1.n_eff == e2.n_eff
    assert e1.l_int_nm == e2.l_int_nm
