"""resist_model is validated in SimulationConfig (plan pipeline-1, step 1).

Until 2026-10 any string other than "full_chem" (e.g. "full-chem") silently
ran the aerial_threshold model and returned ler_nm = lwr_nm = 0.
"""

import pytest

from euvsimulator.pipeline import SimulationConfig


@pytest.mark.parametrize("bad", ["full-chem", "Full_Chem", "threshold", ""])
def test_unknown_resist_model_is_rejected(bad):
    with pytest.raises(ValueError, match="resist_model must be"):
        SimulationConfig(resist_model=bad)


@pytest.mark.parametrize("good", ["aerial_threshold", "full_chem"])
def test_known_resist_models_are_accepted(good):
    assert SimulationConfig(resist_model=good).resist_model == good
