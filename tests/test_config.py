"""Tests for the ScreeningConfig input contract and the CLI's --config support.

The fixtures in ``tests/fixtures/`` stand in for what a future PDF/KML extractor
will emit, so the contract is pinned independently of any parser.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ccs_screen.cli import main
from ccs_screen.config import BOUNDS, REQUIRED_FIELDS, ConfigError, ScreeningConfig

FIXTURES = Path(__file__).parent / "fixtures"

VALID = FIXTURES / "well-valid.json"
INVALID_PRESSURE = FIXTURES / "well-invalid-pressure.json"
INVALID_TEMPERATURE = FIXTURES / "well-invalid-temperature.json"
MISSING_FIELD = FIXTURES / "well-missing-field.json"
MALFORMED = FIXTURES / "well-malformed.json"
DETERMINISTIC = FIXTURES / "well-deterministic.json"


def base_mapping(**overrides):
    """A minimal valid config, before applying overrides."""
    data = {
        "area_m2": 1.0e8,
        "thickness_m": 85.0,
        "porosity": 0.18,
        "pressure_pa": 12.5e6,
        "temperature_k": 358.15,
        "storage_efficiency": 0.04,
    }
    data.update(overrides)
    return data


# --------------------------------------------------------------------------
# Valid well
# --------------------------------------------------------------------------


def test_valid_well_fixture_loads_with_expected_values():
    config = ScreeningConfig.from_json_file(VALID)
    assert config.well_id == "WELL-001"
    assert config.area_m2 == (6.0e7, 1.2e8)
    assert config.porosity == (0.18, 0.18), "a scalar becomes a degenerate range"
    assert config.storage_efficiency == (0.02, 0.05)
    assert config.depth_m == 2450.0
    assert config.samples == 300


def test_unspecified_fields_fall_back_to_engine_defaults():
    config = ScreeningConfig.from_mapping(base_mapping())
    assert config.permeability_m2 == 8e-14
    assert config.radius_m == 500.0
    assert config.safety_factor == 0.9
    assert config.seed == 42
    assert config.well_id is None


def test_scalar_and_range_spellings_are_both_accepted():
    point = ScreeningConfig.from_mapping(base_mapping(porosity=0.18))
    span = ScreeningConfig.from_mapping(base_mapping(porosity=[0.12, 0.24]))
    assert point.porosity == (0.18, 0.18)
    assert span.porosity == (0.12, 0.24)


def test_all_point_values_are_reported_as_deterministic():
    assert ScreeningConfig.from_json_file(DETERMINISTIC).is_deterministic()
    assert not ScreeningConfig.from_json_file(VALID).is_deterministic()


def test_prior_ranges_covers_exactly_the_required_fields():
    config = ScreeningConfig.from_mapping(base_mapping())
    assert set(config.prior_ranges()) == set(REQUIRED_FIELDS)


def test_config_is_frozen():
    config = ScreeningConfig.from_mapping(base_mapping())
    with pytest.raises(Exception):
        config.porosity = (0.2, 0.3)  # type: ignore[misc]


# --------------------------------------------------------------------------
# Invalid pressure / temperature
# --------------------------------------------------------------------------


def test_invalid_pressure_fixture_is_rejected_with_a_named_reason():
    with pytest.raises(ConfigError) as excinfo:
        ScreeningConfig.from_json_file(INVALID_PRESSURE)
    problems = excinfo.value.problems
    assert any(p.startswith("pressure_pa:") for p in problems), problems
    assert any("Pa" in p for p in problems), "the unit belongs in the message"


def test_invalid_temperature_fixture_is_rejected_with_a_named_reason():
    with pytest.raises(ConfigError) as excinfo:
        ScreeningConfig.from_json_file(INVALID_TEMPERATURE)
    problems = excinfo.value.problems
    assert any(p.startswith("temperature_k:") for p in problems), problems
    assert any("K" in p for p in problems)


@pytest.mark.parametrize(
    "field,value",
    [
        ("porosity", 1.0),
        ("porosity", 1.5),
        ("porosity", 0.0),
        ("storage_efficiency", 1.0),
        ("pressure_pa", 0.0),
        ("pressure_pa", 5e8),
        ("temperature_k", -10.0),
        ("temperature_k", 5000.0),
        ("area_m2", 0.0),
        ("thickness_m", -1.0),
        ("depth_m", 99_000.0),
        ("safety_factor", 0.0),
        ("safety_factor", 1.5),
    ],
)
def test_physically_impossible_values_are_rejected(field, value):
    with pytest.raises(ConfigError) as excinfo:
        ScreeningConfig.from_mapping(base_mapping(**{field: value}))
    assert any(p.startswith(f"{field}:") for p in excinfo.value.problems)


def test_safety_factor_of_exactly_one_is_allowed():
    """The fracture-pressure ceiling is an inclusive upper bound."""
    assert ScreeningConfig.from_mapping(base_mapping(safety_factor=1.0)).safety_factor == 1.0


def test_inverted_range_is_rejected():
    with pytest.raises(ConfigError) as excinfo:
        ScreeningConfig.from_mapping(base_mapping(porosity=[0.30, 0.10]))
    assert any("low must be <= high" in p for p in excinfo.value.problems)


def test_equal_low_and_high_is_accepted():
    assert ScreeningConfig.from_mapping(base_mapping(porosity=[0.2, 0.2])).porosity == (0.2, 0.2)


@pytest.mark.parametrize("value", ["0.18", None, {"low": 1}, True, [0.1, 0.2, 0.3], []])
def test_non_numeric_and_malformed_values_are_rejected(value):
    with pytest.raises(ConfigError) as excinfo:
        ScreeningConfig.from_mapping(base_mapping(porosity=value))
    assert any(p.startswith("porosity:") for p in excinfo.value.problems)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_numbers_are_rejected(value):
    with pytest.raises(ConfigError):
        ScreeningConfig.from_mapping(base_mapping(porosity=value))


def test_every_bounded_field_has_a_unit_recorded():
    for name, (_, _, _, unit) in BOUNDS.items():
        assert unit, f"{name} has no unit"


# --------------------------------------------------------------------------
# Missing / unknown fields
# --------------------------------------------------------------------------


def test_missing_required_field_fixture_names_what_is_missing():
    with pytest.raises(ConfigError) as excinfo:
        ScreeningConfig.from_json_file(MISSING_FIELD)
    joined = " ".join(excinfo.value.problems)
    assert "missing required field(s)" in joined
    assert "pressure_pa" in joined
    assert "storage_efficiency" in joined


@pytest.mark.parametrize("omitted", REQUIRED_FIELDS)
def test_each_required_field_is_individually_enforced(omitted):
    data = base_mapping()
    del data[omitted]
    with pytest.raises(ConfigError) as excinfo:
        ScreeningConfig.from_mapping(data)
    assert omitted in " ".join(excinfo.value.problems)


def test_unknown_field_is_rejected_and_lists_known_fields():
    with pytest.raises(ConfigError) as excinfo:
        ScreeningConfig.from_mapping(base_mapping(porsity=0.18))
    joined = " ".join(excinfo.value.problems)
    assert "unknown field(s): porsity" in joined
    assert "porosity" in joined, "the known-field list helps catch the typo"


def test_all_problems_are_reported_in_a_single_pass():
    """An extractor should get a complete diagnosis, not one error per re-run."""
    data = {"porosity": 1.5, "pressure_pa": -1, "temperature_k": 0, "bogus": 1}
    with pytest.raises(ConfigError) as excinfo:
        ScreeningConfig.from_mapping(data)
    joined = " ".join(excinfo.value.problems)
    for expected in ("missing required field(s)", "porosity:", "pressure_pa:", "temperature_k:", "unknown field(s)"):
        assert expected in joined, f"{expected} missing from: {joined}"


def test_non_object_root_is_rejected():
    with pytest.raises(ConfigError):
        ScreeningConfig.from_mapping([1, 2, 3])  # type: ignore[arg-type]


def test_blank_well_id_is_rejected():
    with pytest.raises(ConfigError):
        ScreeningConfig.from_mapping(base_mapping(well_id="   "))


# --------------------------------------------------------------------------
# Malformed JSON / file errors
# --------------------------------------------------------------------------


def test_malformed_json_fixture_reports_line_and_column():
    with pytest.raises(ConfigError) as excinfo:
        ScreeningConfig.from_json_file(MALFORMED)
    message = excinfo.value.problems[0]
    assert "not valid JSON" in message
    assert "line" in message and "column" in message


def test_missing_config_file_is_reported_clearly(tmp_path):
    with pytest.raises(ConfigError) as excinfo:
        ScreeningConfig.from_json_file(tmp_path / "nope.json")
    assert "config file not found" in excinfo.value.problems[0]


def test_config_error_is_a_value_error():
    """The CLI's existing error path catches ValueError; this must ride on it."""
    assert issubclass(ConfigError, ValueError)


# --------------------------------------------------------------------------
# CLI: config loading, override, precedence
# --------------------------------------------------------------------------


def test_cli_loads_a_config_file(capsys):
    assert main(["--config", str(VALID), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["well_id"] == "WELL-001"
    assert report["n_samples"] == 300
    assert report["injectivity"]["fracture_pressure_pa"] == pytest.approx(2450.0 * 15_000.0)


def test_cli_flag_overrides_a_config_value(capsys):
    """Precedence: config file, then CLI flags on top."""
    main(["--config", str(VALID), "--json"])
    from_file = json.loads(capsys.readouterr().out)
    main(["--config", str(VALID), "--samples", "120", "--json"])
    overridden = json.loads(capsys.readouterr().out)
    assert from_file["n_samples"] == 300
    assert overridden["n_samples"] == 120


def test_cli_override_changes_the_physics_not_just_the_echo(capsys):
    main(["--config", str(VALID), "--json"])
    base = json.loads(capsys.readouterr().out)["capacity_mt"]["p50"]
    main(["--config", str(VALID), "--porosity", "0.30", "0.35", "--json"])
    richer = json.loads(capsys.readouterr().out)["capacity_mt"]["p50"]
    assert richer > base


def test_unoverridden_config_values_survive_an_override(capsys):
    """Overriding one field must not reset the others to engine defaults."""
    main(["--config", str(VALID), "--samples", "120", "--json"])
    report = json.loads(capsys.readouterr().out)
    assert report["injectivity"]["fracture_pressure_pa"] == pytest.approx(2450.0 * 15_000.0)
    assert report["well_id"] == "WELL-001"


def test_cli_rejects_an_override_that_is_physically_impossible(capsys):
    """A valid file plus a bad flag is still revalidated by the schema."""
    assert main(["--config", str(VALID), "--porosity", "1.2", "1.5"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "ccs-screen:" in captured.err


@pytest.mark.parametrize(
    "fixture,fragment",
    [
        (INVALID_PRESSURE, "pressure_pa"),
        (INVALID_TEMPERATURE, "temperature_k"),
        (MISSING_FIELD, "missing required field"),
        (MALFORMED, "not valid JSON"),
    ],
)
def test_cli_reports_bad_configs_on_stderr_with_exit_2(fixture, fragment, capsys):
    assert main(["--config", str(fixture)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("ccs-screen:")
    assert fragment in captured.err


def test_cli_reports_a_missing_config_file(capsys):
    assert main(["--config", "no-such-well.json"]) == 2
    assert "config file not found" in capsys.readouterr().err


def test_deterministic_config_collapses_the_distribution(capsys):
    assert main(["--config", str(DETERMINISTIC), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    cap = report["capacity_mt"]
    assert report["deterministic"] is True
    assert cap["p10"] == pytest.approx(cap["p50"]) == pytest.approx(cap["p90"])


def test_deterministic_run_is_flagged_in_text_output(capsys):
    main(["--config", str(DETERMINISTIC)])
    out = capsys.readouterr().out
    assert "P10 = P50 = P90" in out
    assert "WELL-POINT" in out


def test_constant_inputs_get_zero_sensitivity_not_numerical_noise(capsys):
    """A point-valued input has no influence and must rank as exactly zero.

    Its computed standard deviation is floating-point residue rather than zero,
    so an unguarded fit can report a constant as the strongest driver.
    """
    main(["--config", str(VALID), "--json"])
    ranked = json.loads(capsys.readouterr().out)["sensitivity_mt_per_sigma"]
    for constant in ("temperature_k", "pressure_pa", "thickness_m", "porosity"):
        assert ranked[constant] == 0.0, f"{constant} is constant but ranked {ranked[constant]}"
    assert ranked["area_m2"] != 0.0
    assert ranked["storage_efficiency"] != 0.0


def test_existing_flag_only_invocation_is_unaffected(capsys):
    """No --config: the original behaviour and defaults must be untouched."""
    assert main(["--samples", "100", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["well_id"] is None
    assert report["n_samples"] == 100
    assert report["injectivity"]["fracture_pressure_pa"] == pytest.approx(2000.0 * 15_000.0)


def test_round_trip_config_to_json_and_back(tmp_path):
    """What the schema accepts, it must accept again after a JSON round trip."""
    original = ScreeningConfig.from_json_file(VALID)
    payload = {name: list(value) for name, value in original.prior_ranges().items()}
    payload["well_id"] = original.well_id
    payload["depth_m"] = original.depth_m
    path = tmp_path / "round-trip.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert ScreeningConfig.from_json_file(path).prior_ranges() == original.prior_ranges()
