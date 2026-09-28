"""The scenario layer: assumptions that stay visibly assumptions.

Uses the same synthetic pilot dataset as test_ingest_pipeline.py so nothing here
depends on the git-ignored ``data/`` directory.
"""

from __future__ import annotations

import json

import pytest

from ccs_screen.config import REQUIRED_FIELDS, ScreeningConfig
from ccs_screen.ingest.assumptions import (
    Assumption,
    AssumptionError,
    AssumptionSet,
    Citation,
    EvidenceClass,
)
from ccs_screen.ingest.normalize import WellNormalizer
from ccs_screen.ingest.provenance import Provenance
from ccs_screen.ingest.report import (
    build_funnel,
    compare_temperature_methods,
    screen_well,
)
from ccs_screen.ingest.scenario import (
    BUILTIN_SCENARIOS,
    CENTRAL,
    CONSERVATIVE,
    NO_SCENARIO,
    SCENARIO_PARAMETERS,
    SENSITIVITY,
    SOURCE_ONLY_PARAMETERS,
    IncompleteScreening,
    ScreeningScenario,
    apply_scenario,
    load_scenario,
    resolve_inputs,
)

from test_ingest_pipeline import (  # reuse the synthetic pilot fixtures
    ANAGRAFICA,
    PO_WELLS,
    POZZI_STORICI,
    STRATIGRAPHY,
    TEMPERATURES,
    _write_xlsx,
)

openpyxl = pytest.importorskip("openpyxl")


@pytest.fixture(scope="module")
def pilot_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("scenario_data")
    _write_xlsx(d / "Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx")
    (d / "pozzi-storici.csv").write_bytes(POZZI_STORICI.encode("cp1252"))
    (d / "po_wells_clean.csv").write_bytes(PO_WELLS.encode("cp1252"))
    return d


@pytest.fixture(scope="module")
def records(pilot_dir):
    return {r.canonical_id: r for r in WellNormalizer(pilot_dir).run()}


def partial_scenario() -> ScreeningScenario:
    """Supplies only some of the missing inputs."""
    common = dict(author="Test Engineer", rationale="partial placeholder")
    return ScreeningScenario(
        name="partial", description="deliberately incomplete",
        assumptions=AssumptionSet(name="partial", assumptions=(
            Assumption(parameter="area_m2", value=1e8, **common),
            Assumption(parameter="porosity", value=0.18, **common),
        )),
    )


# -- scenario structure ------------------------------------------------------


def test_scenario_carries_its_paperwork():
    assert CENTRAL.name and CENTRAL.description and CENTRAL.version
    assert CENTRAL.date and CENTRAL.rationale
    for a in CENTRAL.assumptions:
        assert a.author and a.rationale and a.date


@pytest.mark.parametrize("scenario", [CONSERVATIVE, CENTRAL, SENSITIVITY])
def test_three_scenarios_cover_every_assumable_parameter(scenario):
    assert set(scenario.assumed_parameters) == set(SCENARIO_PARAMETERS)


@pytest.mark.parametrize("scenario", [CONSERVATIVE, CENTRAL, SENSITIVITY])
def test_builtin_values_are_labelled_placeholders(scenario):
    """No number here is authoritative and every one says so."""
    assert "placeholder" in scenario.name
    for a in scenario.assumptions:
        assert "PLACEHOLDER" in a.rationale
        # Machine-readable, so a client can reject these without reading prose.
        assert a.evidence_class is EvidenceClass.PLACEHOLDER
        assert not a.is_literature_derived, "a placeholder is not literature-derived"


def test_conservative_and_central_are_deterministic():
    assert CONSERVATIVE.is_deterministic
    assert CENTRAL.is_deterministic


def test_sensitivity_is_a_range_scenario():
    assert not SENSITIVITY.is_deterministic
    for a in SENSITIVITY.assumptions:
        assert isinstance(a.value, tuple)


def test_conservative_is_not_above_central():
    """Ordering sanity for the placeholders, not a scientific claim."""
    for parameter in SCENARIO_PARAMETERS:
        assert CONSERVATIVE.get(parameter).value <= CENTRAL.get(parameter).value


def test_no_scenario_assumes_nothing():
    assert NO_SCENARIO.assumed_parameters == ()


def test_scenario_cannot_assume_temperature():
    """Temperature is the one required input the sources supply."""
    assert "temperature_k" in SOURCE_ONLY_PARAMETERS
    with pytest.raises(AssumptionError):
        Assumption(parameter="temperature_k", value=350.0,
                   author="x", rationale="should be refused")


def test_scenario_requires_a_name_and_description():
    empty = AssumptionSet(name="e")
    with pytest.raises(AssumptionError):
        ScreeningScenario(name="", description="d", assumptions=empty)
    with pytest.raises(AssumptionError):
        ScreeningScenario(name="n", description="", assumptions=empty)


def test_builtin_lookup():
    for name in ("conservative", "central", "sensitivity", "none"):
        assert load_scenario(name) is BUILTIN_SCENARIOS[name]
    with pytest.raises(AssumptionError):
        load_scenario("no-such-scenario")


def test_scenario_round_trips_through_json(tmp_path):
    path = tmp_path / "scenario.json"
    path.write_text(json.dumps(SENSITIVITY.to_dict()), encoding="utf-8")
    loaded = ScreeningScenario.from_json_file(path)
    assert loaded.name == SENSITIVITY.name
    assert set(loaded.assumed_parameters) == set(SENSITIVITY.assumed_parameters)
    assert loaded.get("porosity").value == (0.12, 0.24)


def test_malformed_scenario_file_is_reported(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{oops", encoding="utf-8")
    with pytest.raises(AssumptionError):
        ScreeningScenario.from_json_file(path)


# -- application -------------------------------------------------------------


def test_source_data_plus_complete_scenario_builds_a_config(records):
    config = apply_scenario(records["SALUZZO|1"], SENSITIVITY)
    assert isinstance(config, ScreeningConfig)
    assert config.well_id == "SALUZZO|1"


def test_source_data_plus_incomplete_scenario_is_blocked(records):
    outcome = apply_scenario(records["SALUZZO|1"], partial_scenario())
    assert isinstance(outcome, IncompleteScreening)
    assert not outcome.screenable
    assert set(outcome.missing_fields) == {"thickness_m", "pressure_pa", "storage_efficiency"}
    assert all(reason for _, reason in outcome.reasons)


def test_no_scenario_leaves_every_assumable_field_missing(records):
    outcome = apply_scenario(records["SALUZZO|1"], NO_SCENARIO)
    assert isinstance(outcome, IncompleteScreening)
    assert set(outcome.missing_fields) == set(SCENARIO_PARAMETERS)


def test_assumptions_fill_only_the_missing_fields(records):
    resolved, missing = resolve_inputs(records["SALUZZO|1"], SENSITIVITY)
    assert not missing
    assumed = {n for n, i in resolved.items() if i.is_assumed}
    assert assumed == set(SCENARIO_PARAMETERS)
    assert resolved["temperature_k"].is_assumed is False


def test_source_data_takes_precedence_over_an_assumption(records):
    """A scenario cannot overwrite a derived temperature even if it tries."""
    config = apply_scenario(records["SALUZZO|1"], SENSITIVITY)
    assert config.temperature_k == (318.15, 318.15)
    resolved, _ = resolve_inputs(records["SALUZZO|1"], SENSITIVITY)
    assert resolved["temperature_k"].provenance is Provenance.DERIVED


def test_temperature_is_never_silently_overwritten(records):
    """Even a scenario built to target temperature cannot reach it."""
    with pytest.raises(AssumptionError):
        AssumptionSet.from_mapping({
            "name": "sneaky",
            "assumptions": [{"parameter": "temperature_k", "value": 400.0,
                             "author": "x", "rationale": "y"}],
        })


def test_missing_temperature_stays_blocking(records):
    """ASIGLIANO has only a surface air mean; no scenario can rescue it."""
    outcome = apply_scenario(records["ASIGLIANO|1"], SENSITIVITY)
    assert isinstance(outcome, IncompleteScreening)
    assert outcome.missing_fields == ("temperature_k",)
    reason = dict(outcome.reasons)["temperature_k"]
    assert "may not be supplied by a scenario" in reason


def test_incomplete_screening_describes_itself(records):
    outcome = apply_scenario(records["ASIGLIANO|1"], CENTRAL)
    text = outcome.describe()
    assert "ASIGLIANO|1" in text and "temperature_k" in text
    assert outcome.to_dict()["screenable"] is False


def test_deterministic_scenario_collapses_the_distribution(records):
    report = screen_well(records["SALUZZO|1"], CENTRAL, samples=200)
    assert report.result.deterministic
    r = report.result
    assert r.p10_mt == pytest.approx(r.p50_mt) == pytest.approx(r.p90_mt)


def test_uncertain_scenario_produces_a_spread(records):
    report = screen_well(records["SALUZZO|1"], SENSITIVITY, samples=400)
    assert not report.result.deterministic
    r = report.result
    assert r.p10_mt < r.p50_mt < r.p90_mt


def test_conservative_is_not_larger_than_central(records):
    low = screen_well(records["SALUZZO|1"], CONSERVATIVE, samples=200).result.p50_mt
    mid = screen_well(records["SALUZZO|1"], CENTRAL, samples=200).result.p50_mt
    assert low < mid


# -- report provenance -------------------------------------------------------


def test_report_separates_source_from_assumed(records):
    report = screen_well(records["SALUZZO|1"], SENSITIVITY, samples=200)
    assert [i.name for i in report.source_inputs] == ["temperature_k"]
    assert set(report.assumption_flags) == set(SCENARIO_PARAMETERS)
    assert not report.rests_entirely_on_assumptions


def test_every_required_input_appears_in_the_report(records):
    report = screen_well(records["SALUZZO|1"], SENSITIVITY, samples=200)
    assert {i.name for i in report.inputs} == set(REQUIRED_FIELDS)


def test_rendered_report_marks_assumed_inputs(records):
    text = screen_well(records["SALUZZO|1"], SENSITIVITY, samples=200).render()
    assert "ASSUMED" in text
    assert "assumed inputs" in text
    assert "source-derived inputs    : temperature_k" in text
    for parameter in SCENARIO_PARAMETERS:
        assert parameter in text


def test_report_preserves_temperature_provenance(records):
    report = screen_well(records["SALUZZO|1"], SENSITIVITY, samples=200)
    t = report.temperature
    assert t.method == "extrapolated_squarci_taffi"
    assert t.provenance is Provenance.DERIVED
    assert t.value_k == pytest.approx(318.15)
    assert t.alternatives, "the competing non-stabilized reading must stay visible"


def test_report_keeps_conflicts_visible(records):
    report = screen_well(records["SALUZZO|1"], SENSITIVITY, samples=200)
    joined = " ".join(report.conflicts)
    assert "depth_m" in joined and "temperature_k" in joined
    assert "conflicts" in report.render()


def test_report_json_is_serialisable_and_flags_assumptions(records):
    payload = screen_well(records["SALUZZO|1"], SENSITIVITY, samples=200).to_dict()
    json.dumps(payload)  # must not raise: the web API will do exactly this
    assert payload["assumed_inputs"] == list(payload["assumption_flags"])
    for name in SCENARIO_PARAMETERS:
        assert payload["screening_inputs"][name]["assumed"] is True
    assert payload["screening_inputs"]["temperature_k"]["assumed"] is False


def test_blocked_well_report_has_no_result(records):
    report = screen_well(records["ASIGLIANO|1"], SENSITIVITY, samples=200)
    assert report.screenable is False
    assert report.result is None
    assert "temperature_k" in report.missing_fields
    assert "screenable               : false" in report.render()


# -- funnel ------------------------------------------------------------------


def test_funnel_keeps_the_three_states_distinct(records):
    recs = list(records.values())
    reports = [screen_well(r, SENSITIVITY, samples=50) for r in recs]
    funnel = build_funnel(recs, SENSITIVITY, reports)
    assert funnel.normalized == len(recs)
    assert funnel.source_complete == 0, "nothing is screenable from source data alone"
    assert funnel.scenario_complete == funnel.screenable
    assert funnel.screenable == len(recs) - funnel.blocked_count
    assert funnel.blocked_by_field().get("temperature_k") == 1


def test_funnel_renders_the_distinct_states(records):
    recs = list(records.values())
    text = build_funnel(recs, SENSITIVITY, [screen_well(r, SENSITIVITY, samples=50) for r in recs]).render()
    assert "screenable from source data alone" in text
    assert "scenario-complete" in text


def test_no_scenario_funnel_screens_nothing(records):
    recs = list(records.values())
    reports = [screen_well(r, NO_SCENARIO, samples=50) for r in recs]
    funnel = build_funnel(recs, NO_SCENARIO, reports)
    assert funnel.screenable == 0
    assert funnel.blocked_count == len(recs)


# -- temperature comparison --------------------------------------------------


def test_temperature_methods_can_be_compared(records):
    comparison = compare_temperature_methods(records["SALUZZO|1"], SENSITIVITY, samples=200)
    assert comparison.selected_method == "extrapolated_squarci_taffi"
    methods = {v.method for v in comparison.variants}
    assert {"extrapolated_squarci_taffi", "non_stabilized"} <= methods


def test_temperature_choice_moves_capacity(records):
    """Method selection is a first-order uncertainty, not a detail."""
    comparison = compare_temperature_methods(records["SALUZZO|1"], SENSITIVITY, samples=400)
    assert comparison.p50_spread_mt is not None
    assert comparison.p50_spread_percent > 0


def test_comparison_does_not_declare_a_winner(records):
    """Every variant is reported; none is marked globally correct."""
    payload = compare_temperature_methods(records["SALUZZO|1"], SENSITIVITY, samples=200).to_dict()
    assert len(payload["variants"]) >= 2
    # Phase 14 (O2): the comparison is a legacy diagnostic and carries its label.
    assert set(payload) == {"well_id", "validation_status", "selected_method", "variants",
                            "p50_spread_mt", "p50_spread_percent"}
    assert payload["validation_status"] == "NOT_VALIDATED"
    assert all("correct" not in str(v) for v in payload["variants"])


def test_surface_air_only_well_has_nothing_to_compare(records):
    comparison = compare_temperature_methods(records["ASIGLIANO|1"], SENSITIVITY, samples=50)
    assert comparison.variants == ()
    assert comparison.p50_spread_mt is None


# -- Phase 14: owner decision O2 labels ---------------------------------------


@pytest.mark.parametrize("scenario", [CONSERVATIVE, CENTRAL, SENSITIVITY])
def test_placeholder_descriptions_state_not_validated(scenario):
    assert "NOT_VALIDATED" in scenario.description


def test_legacy_report_is_labelled_not_validated(records):
    report = screen_well(records["SALUZZO|1"], SENSITIVITY, samples=50)
    assert report.to_dict()["validation_status"] == "NOT_VALIDATED"
    assert "NOT_VALIDATED (legacy path, owner decision O2)" in report.render()


def test_legacy_funnel_is_labelled_not_validated(records):
    recs = list(records.values())
    funnel = build_funnel(recs, SENSITIVITY, [screen_well(r, SENSITIVITY, samples=20) for r in recs])
    assert funnel.to_dict()["validation_status"] == "NOT_VALIDATED"
    assert "NOT_VALIDATED (legacy path, owner decision O2)" in funnel.render()


def test_legacy_arithmetic_is_unchanged_by_the_labels(records):
    """O2: labels only. The legacy engine output equals a direct engine run."""
    from ccs_screen.monte_carlo import UniformPriors, run_capacity_mc

    report = screen_well(records["SALUZZO|1"], SENSITIVITY, samples=300, seed=4)
    config = apply_scenario(records["SALUZZO|1"], SENSITIVITY)
    direct = run_capacity_mc(UniformPriors(**config.prior_ranges()).sample(300, seed=4))
    assert (report.result.p10_mt, report.result.p50_mt, report.result.p90_mt) == (
        direct.p10_mt, direct.p50_mt, direct.p90_mt)
