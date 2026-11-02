"""Regression guard: resist islands, G0 coupling, Ru cap on Si.

B3.1  extract_edges takes the outermost resist pixels of a row, so resist
      detached from the line counts as line. residue_island_fraction reports
      the share of such rows (ler_metadata["island_row_fraction"]); the
      edges are unchanged.
B3.2  pag_density_per_nm3 (G0) scales the neutralisation k_Q*G0 but not the
      deprotection (peb_k is a fit for G0 = 0.2): a warning when G0 is
      changed and peb_k left at its default.
B3.3  The multilayer is Si-terminated: the Ru cap lies on Si. Until v2.2.1
      every bilayer was Mo then Si, so the cap lay on Mo.
"""

import math
import warnings

import pytest
import torch

from euvsimulator.optics.multilayer import mo_si_stack
from euvsimulator.optics.tmm import reflectivity
from euvsimulator.pipeline import SimulationConfig, run_simulation
from euvsimulator.resist.stochastic import extract_edges, residue_island_fraction

# ── B3.1 ────────────────────────────────────────────────────────────────


def _rows(*rows):
    """1 = developed, 0 = resist."""
    return torch.tensor(rows, dtype=torch.float64)


def test_island_fraction_counts_rows_with_detached_resist():
    dev = _rows(
        [1, 1, 0, 0, 0, 1, 1, 1],  # line only
        [1, 1, 0, 0, 0, 1, 0, 1],  # line + island in the space
        [1, 0, 0, 0, 0, 0, 1, 1],  # wider line, one segment
        [1, 1, 1, 1, 1, 1, 1, 1],  # no resist
    )
    assert residue_island_fraction(dev) == pytest.approx(0.25)


def test_island_fraction_treats_rows_as_periodic():
    # resist in the first and the last column is one segment across the boundary
    dev = _rows([0, 1, 1, 1, 1, 1, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0])
    assert residue_island_fraction(dev) == 0.0


def test_island_widens_the_extracted_line_and_fraction_flags_it():
    """The diagnostic marks exactly the rows whose width the island inflates."""
    clean = _rows([1, 1, 0, 0, 0, 1, 1, 1, 1, 1])
    island = _rows([1, 1, 0, 0, 0, 1, 1, 0, 1, 1])
    lc, rc = extract_edges(clean)
    li, ri = extract_edges(island)
    assert float(rc - lc) == 2.0
    assert float(ri - li) == 5.0  # the island at column 7 is counted as line
    assert residue_island_fraction(clean) == 0.0
    assert residue_island_fraction(island) == 1.0


def test_chain_reports_island_fraction():
    r = run_simulation(
        SimulationConfig(
            grid=64,
            device="cpu",
            resist_model="full_chem",
            enable_stochastic=True,
            stochastic_seed=3,
            stochastic_n_realisations=1,
        )
    )
    frac = r.ler_metadata["island_row_fraction"]
    assert 0.0 <= frac <= 1.0


# ── B3.2 ────────────────────────────────────────────────────────────────


def test_changed_g0_with_default_peb_k_warns():
    with pytest.warns(UserWarning, match="peb_k does not scale with G0"):
        SimulationConfig(pag_density_per_nm3=0.4)


@pytest.mark.parametrize(
    "kw",
    [
        {},  # default G0
        {"pag_density_per_nm3": 0.4, "peb_k": 2 * 10.947},  # explicit k for the new G0
        {"pag_density_per_nm3": 0.4, "peb_temperature_c": 110.0},  # k from the PEB fit
    ],
)
def test_no_g0_warning_when_peb_k_is_consistent_or_explicit(kw):
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        SimulationConfig(**kw)


# ── B3.3 ────────────────────────────────────────────────────────────────


def test_ru_cap_lies_on_si_and_mo_on_the_substrate():
    st = mo_si_stack(n_bilayers=40, capping_layer="Ru", d_cap_nm=2.5)
    assert st.symbols[:3] == ["Ru", "Si", "Mo"]
    assert st.symbols[-1] == "Mo"
    assert st.symbols.count("Mo") == st.symbols.count("Si") == 40


def test_ru_capped_stack_reflectivity_at_13p5_nm():
    """Si-terminated, 40 x (2.8 Mo / 4.1 Si) + 2.5 nm Ru at 6 deg, TE.

    Roughness-free TMM with the shipped CXRO tables, 50 bilayers: 0.7322 with
    the cap on Si, 0.6470 with the cap on Mo (the v2.2.1 order; measured
    2026-10-30).
    """
    st = mo_si_stack(n_bilayers=50, capping_layer="Ru", d_cap_nm=2.5)
    R, _ = reflectivity(
        st.n_layers,
        st.thicknesses,
        torch.tensor([13.5e-9], dtype=torch.float64),
        torch.tensor(math.radians(6.0), dtype=torch.float64),
        n_substrate=st.n_substrate,
    )
    assert float(R.flatten()[0]) == pytest.approx(0.732, abs=0.005)
