"""CSV export positions follow the aerial-image sampling x_i = -P/2 + i*P/n."""

from euvsimulator.api.main import _job_csv


def test_csv_positions_use_pitch_period_over_n():
    r = {
        "preset": "test",
        "config": {"period_nm": 64.0},
        "results": [],
        "raw": {"aerial_profile_nm": [1.0, 2.0, 3.0, 4.0], "resist_profile": [0, 0, 1, 1]},
    }
    lines = _job_csv("simulate", r).splitlines()
    assert lines[1] == "position_nm,local_dose_mj_cm2,developed"
    xs = [float(line.split(",")[0]) for line in lines[2:]]
    assert xs == [-32.0, -16.0, 0.0, 16.0]
