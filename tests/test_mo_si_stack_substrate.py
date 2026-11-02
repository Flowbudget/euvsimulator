"""Regression guard: mo_si_stack(substrate=...) changed only the description.

The substrate is not a layer of the stack; the TMM takes its index as a
separate n_substrate argument. mo_si_stack accepted a substrate symbol but
returned nothing derived from it, so substrate="Mo" and substrate="Si" gave
identical stacks and a caller had no way to get the index it names.
"""

import math

import pytest
import torch

from euvsimulator.materials import CXROTable
from euvsimulator.optics.multilayer import mo_si_stack
from euvsimulator.optics.tmm import reflectivity


@pytest.mark.parametrize("symbol", ["Si", "Mo"])
def test_stack_carries_the_substrate_index(symbol):
    """n_substrate is the CXRO index of the named substrate."""
    stack = mo_si_stack(n_bilayers=3, substrate=symbol)
    n, k = CXROTable().refractive_index(symbol, 91.84)
    assert stack.n_substrate is not None
    assert stack.n_substrate.dtype == torch.complex128
    assert complex(stack.n_substrate.item()) == complex(n, k)


def test_substrate_index_uses_the_stack_energy():
    """The substrate index is taken at the same photon energy as the layers."""
    stack = mo_si_stack(n_bilayers=3, energy_eV=95.0)
    n, k = CXROTable().refractive_index("Si", 95.0)
    assert complex(stack.n_substrate.item()) == complex(n, k)


def test_substrate_reaches_the_tmm_through_the_stack():
    """For a thin stack the substrate changes R; the stack now carries it."""
    wl = torch.tensor([13.5e-9], dtype=torch.float64)
    theta = torch.tensor(math.radians(6.0), dtype=torch.float64)
    refl = {}
    for symbol in ("Si", "Mo"):
        stack = mo_si_stack(n_bilayers=3, capping_layer=None, substrate=symbol)
        R, _ = reflectivity(
            stack.n_layers, stack.thicknesses, wl, theta, n_substrate=stack.n_substrate
        )
        refl[symbol] = float(R[0])
    assert abs(refl["Si"] - refl["Mo"]) > 1e-3


def test_unknown_substrate_is_rejected():
    """A symbol without CXRO data no longer passes silently into the label."""
    with pytest.raises(KeyError):
        mo_si_stack(n_bilayers=3, substrate="Xx")
