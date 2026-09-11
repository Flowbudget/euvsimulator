"""Parity between ``pipeline.SimulationConfig`` and the API field catalogue.

The GUI and the REST API expose the dataclass field by field; these tests
make sure the catalogue, the generated request model and the presets can
never silently drift from the dataclass.
"""

from __future__ import annotations

import dataclasses

import pytest

from euvsimulator.api.fields import (
    FIELDS,
    GROUPS,
    HEAD_FIELDS,
    PRESETS,
    PipelineOverrides,
    config_as_dict,
    field_catalogue,
    physics_errors,
    resolve_config,
)
from euvsimulator.pipeline import SimulationConfig

DATACLASS_FIELDS = [f.name for f in dataclasses.fields(SimulationConfig)]


def test_catalogue_names_equal_the_dataclass_fields() -> None:
    assert set(FIELDS) == set(DATACLASS_FIELDS), set(FIELDS) ^ set(DATACLASS_FIELDS)


def test_catalogue_rows_are_complete_and_grouped() -> None:
    for name, info in FIELDS.items():
        assert info["group"] in GROUPS, name
        assert info["label"].strip(), name
        assert len(info["help"]) >= 10, name
    assert set(HEAD_FIELDS) <= set(FIELDS)


def test_generated_request_model_mirrors_the_dataclass() -> None:
    assert list(PipelineOverrides.model_fields) == DATACLASS_FIELDS
    # every field optional: an empty body is valid and sets nothing
    assert PipelineOverrides().model_dump(exclude_unset=True) == {}
    # unknown names are rejected
    with pytest.raises(Exception):
        PipelineOverrides(no_such_field=1)


def test_field_catalogue_defaults_equal_the_dataclass_defaults() -> None:
    ref = SimulationConfig()
    rows = {r["name"]: r for r in field_catalogue()}
    assert list(rows) == DATACLASS_FIELDS
    for name in DATACLASS_FIELDS:
        assert rows[name]["default"] == getattr(ref, name), name
    assert rows["ler_passband_nm"]["type"] == "pair" and rows["ler_passband_nm"]["nullable"]
    assert rows["enable_stochastic"]["type"] == "bool"
    assert rows["illumination_shape"]["choices"]


@pytest.mark.parametrize("key", list(PRESETS))
def test_every_preset_builds_and_passes_the_physics_checks(key: str) -> None:
    cfg = PRESETS[key].factory()
    assert physics_errors(cfg) == []
    d = config_as_dict(cfg)
    assert set(d) == set(DATACLASS_FIELDS)


def test_resolve_config_applies_overrides_on_top_of_the_preset() -> None:
    cfg = resolve_config("nxe1716", {"grid": 64, "ler_passband_nm": [10.0, 100.0]})
    assert cfg.period_nm == 44.0 and cfg.grid == 64
    assert cfg.ler_passband_nm == (10.0, 100.0)
    with pytest.raises(KeyError):
        resolve_config("nope", {})


def test_physics_errors_catch_the_model_domains() -> None:
    # the dataclass's own __post_init__ rejects some values before physics_errors runs
    with pytest.raises(ValueError, match="mack_n"):
        resolve_config(None, {"mack_n": 1.0})
    with pytest.raises(ValueError, match="mack_M_th"):
        resolve_config(None, {"mack_M_th": 1.5})
    bad = resolve_config(
        None, {"na": 1.5, "absorber_taper_deg": 0.0, "sigma": 0.5, "sigma_inner": 0.6}
    )
    msgs = physics_errors(bad)
    assert any(m.startswith("na ") for m in msgs)
    assert any("absorber_taper_deg" in m for m in msgs)
    assert any("sigma_inner" in m for m in msgs)
    assert physics_errors(SimulationConfig()) == []


def test_unimplemented_mask_geometry_is_a_physics_error_not_a_crash() -> None:
    """The pipeline raises NotImplementedError for taper/undercut; the API must say so (422)."""
    msgs = physics_errors(resolve_config(None, {"absorber_taper_deg": 85.0}))
    assert any("not implemented" in m for m in msgs)
    msgs = physics_errors(resolve_config(None, {"mask_undercut_nm": 2.0}))
    assert any("not implemented" in m for m in msgs)
