"""absorber_taper_deg / mask_undercut_nm are refused on BOTH mask paths
(plan pipeline-1, step 4).

Until 2026-10 the NotImplementedError sat inside the use_rcwa branch, so the
default thin-mask path accepted any taper or undercut without effect.
"""

import pytest

from euvsimulator.pipeline import SimulationConfig, run_simulation


@pytest.mark.parametrize("kw", [{"absorber_taper_deg": 88.0}, {"mask_undercut_nm": 2.0}])
def test_taper_and_undercut_are_rejected_on_the_thin_mask_path(kw):
    cfg = SimulationConfig(grid=64, device="cpu", **kw)
    assert cfg.use_rcwa is False
    with pytest.raises(NotImplementedError, match="absorber_taper_deg / mask_undercut_nm"):
        run_simulation(cfg)


def test_taper_is_still_rejected_on_the_rcwa_path():
    cfg = SimulationConfig(use_rcwa=True, absorber_taper_deg=88.0, grid=64, device="cpu")
    with pytest.raises(NotImplementedError, match="absorber_taper_deg / mask_undercut_nm"):
        run_simulation(cfg)


def test_default_taper_and_undercut_still_run():
    r = run_simulation(SimulationConfig(grid=64, device="cpu"))
    assert r.cd_nm > 0
