"""`ccs-ingest` command-line contract.

Exercised against the synthetic pilot dataset, so these run anywhere.
"""

from __future__ import annotations

import json

import pytest

from ccs_screen.ingest.cli import build_parser, main, resolve_scenario
from ccs_screen.ingest.scenario import CENTRAL, NO_SCENARIO, SENSITIVITY

from test_ingest_pipeline import PO_WELLS, POZZI_STORICI, _write_xlsx

openpyxl = pytest.importorskip("openpyxl")


@pytest.fixture(scope="module")
def pilot_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("cli_data")
    _write_xlsx(d / "Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx")
    (d / "pozzi-storici.csv").write_bytes(POZZI_STORICI.encode("cp1252"))
    (d / "po_wells_clean.csv").write_bytes(PO_WELLS.encode("cp1252"))
    return d


def run(pilot_dir, *args):
    return main(["--data-dir", str(pilot_dir), *args])


# -- existing behaviour is preserved ----------------------------------------


def test_default_mode_still_reports_completeness(pilot_dir, capsys):
    assert run(pilot_dir) == 0
    assert "completeness report" in capsys.readouterr().out


def test_single_well_record(pilot_dir, capsys):
    assert run(pilot_dir, "--well", "SALUZZO|1") == 0
    assert "SALUZZO|1" in capsys.readouterr().out


# -- screening mode ----------------------------------------------------------


def test_screen_reports_the_funnel(pilot_dir, capsys):
    assert run(pilot_dir, "--screen", "--scenario", "sensitivity", "--samples", "50") == 0
    out = capsys.readouterr().out
    assert "screening funnel" in out
    assert "screenable from source data alone" in out


def test_screen_one_well_shows_the_full_report(pilot_dir, capsys):
    assert run(pilot_dir, "--screen", "--scenario", "central",
               "--well", "SALUZZO|1", "--samples", "50") == 0
    out = capsys.readouterr().out
    assert "ASSUMED" in out
    assert "source-derived inputs" in out
    assert "screening result" in out


def test_screen_json_is_machine_readable(pilot_dir, capsys):
    assert run(pilot_dir, "--screen", "--scenario", "sensitivity",
               "--samples", "50", "--json") == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["scenario"]["name"] == SENSITIVITY.name
    assert payload["funnel"]["source_complete"] == 0
    assert payload["funnel"]["screenable"] >= 1
    assert any(w["assumed_inputs"] for w in payload["wells"])


def test_scenario_metadata_reaches_the_json(pilot_dir, capsys):
    run(pilot_dir, "--screen", "--scenario", "central", "--samples", "50", "--json")
    scenario = json.loads(capsys.readouterr().out)["scenario"]
    for key in ("name", "description", "version", "date", "rationale", "assumptions"):
        assert key in scenario


def test_none_scenario_screens_nothing(pilot_dir, capsys):
    run(pilot_dir, "--screen", "--scenario", "none", "--samples", "50", "--json")
    assert json.loads(capsys.readouterr().out)["funnel"]["screenable"] == 0


# -- temperature comparison --------------------------------------------------


def test_compare_temperature_modes(pilot_dir, capsys):
    assert run(pilot_dir, "--compare-temperature", "--scenario", "sensitivity",
               "--well", "SALUZZO|1", "--samples", "100") == 0
    out = capsys.readouterr().out
    assert "Temperature-method comparison" in out
    assert "squarci" in out.lower()


# -- scenario resolution -----------------------------------------------------


def test_assumptions_flag_is_wrapped_into_a_scenario(pilot_dir, tmp_path, capsys):
    """The older --assumptions invocation keeps working through the new model."""
    path = tmp_path / "a.json"
    path.write_text(json.dumps({
        "name": "legacy",
        "assumptions": [{"parameter": "porosity", "value": 0.18,
                         "author": "x", "rationale": "legacy set"}],
    }), encoding="utf-8")
    scenario = resolve_scenario(build_parser().parse_args(["--assumptions", str(path)]))
    assert scenario.name == "legacy"
    assert scenario.assumed_parameters == ("porosity",)


def test_no_scenario_flag_defaults_to_source_data_only():
    assert resolve_scenario(build_parser().parse_args([])) is NO_SCENARIO


def test_builtin_scenario_by_name():
    assert resolve_scenario(build_parser().parse_args(["--scenario", "central"])) is CENTRAL


# -- error paths -------------------------------------------------------------


@pytest.mark.parametrize(
    "args,fragment",
    [
        (["--scenario", "no-such"], "unknown scenario"),
        (["--scenario", "central", "--assumptions", "x.json"], "not both"),
        (["--samples", "0", "--screen", "--scenario", "central"], "--samples"),
        (["--well", "NOT|A|WELL"], "no well with canonical id"),
    ],
)
def test_errors_exit_2_on_stderr(pilot_dir, capsys, args, fragment):
    assert run(pilot_dir, *args) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("ccs-ingest:")
    assert fragment in captured.err


def test_missing_data_dir_is_reported(capsys):
    assert main(["--data-dir", "no-such-dir"]) == 2
    assert "data directory not found" in capsys.readouterr().err


def test_emit_configs_writes_only_screenable_wells(pilot_dir, tmp_path, capsys):
    out_dir = tmp_path / "configs"
    assert run(pilot_dir, "--scenario", "central", "--emit-configs", str(out_dir)) == 0
    written = sorted(p.name for p in out_dir.glob("*.json"))
    assert written
    assert not any("ASIGLIANO" in n for n in written), "blocked well must not emit a config"
