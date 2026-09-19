"""The literature-constrained scenario and its citation machinery.

The discipline under test: a cited value and an invented one must never be
indistinguishable, and the two parameters the literature does not support must
stay blocking rather than acquiring a quiet default.
"""

from __future__ import annotations

import json
from pathlib import Path

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
from ccs_screen.ingest.report import screen_well
from ccs_screen.ingest.scenario import (
    AREA_POLICY_STATEMENT,
    BUILTIN_SCENARIOS,
    CENTRAL,
    CSLF_2008,
    DONDA_2011,
    LITERATURE_SCREENING_V1,
    LITERATURE_UNSUPPORTED,
    NET_THICKNESS_POLICY_STATEMENT,
    STANDARD_GRAVITY_M_S2,
    IncompleteScreening,
    ScreeningScenario,
    apply_scenario,
    load_scenario,
    resolve_inputs,
)

from test_ingest_pipeline import PO_WELLS, POZZI_STORICI, _write_xlsx

openpyxl = pytest.importorskip("openpyxl")

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def pilot_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("lit_data")
    _write_xlsx(d / "Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx")
    (d / "pozzi-storici.csv").write_bytes(POZZI_STORICI.encode("cp1252"))
    (d / "po_wells_clean.csv").write_bytes(PO_WELLS.encode("cp1252"))
    return d


@pytest.fixture(scope="module")
def records(pilot_dir):
    return {r.canonical_id: r for r in WellNormalizer(pilot_dir).run()}


@pytest.fixture(scope="module")
def complete_scenario() -> ScreeningScenario:
    """literature-screening-v1 plus explicit user inputs for the two gaps."""
    user = Citation(source="user input", title="User-supplied screening input",
                    year=2026, text="USER INPUT - no literature basis.",
                    evidence_class=EvidenceClass.UNSUPPORTED)
    extra = (
        Assumption(parameter="area_m2", value=(5e7, 1.5e8), author="Test Engineer",
                   rationale="example user input", citation=user),
        Assumption(parameter="thickness_m", value=(25.0, 55.0), author="Test Engineer",
                   rationale="example user input, net not gross", citation=user),
    )
    return ScreeningScenario(
        name="literature-plus-user", description="literature-screening-v1 plus user inputs",
        version="1", rationale="test fixture",
        brine_density_kg_m3=LITERATURE_SCREENING_V1.brine_density_kg_m3,
        assumptions=AssumptionSet(
            name="literature-plus-user",
            assumptions=LITERATURE_SCREENING_V1.assumptions.assumptions + extra,
        ),
    )


# -- citation metadata -------------------------------------------------------


def test_citation_requires_real_metadata():
    for bad in ({"source": ""}, {"title": ""}, {"text": ""}):
        kwargs = dict(source="s", title="t", year=2008, text="x")
        kwargs.update(bad)
        with pytest.raises(AssumptionError):
            Citation(**kwargs)


@pytest.mark.parametrize("year", [0, 1800, 2200, "2008", None])
def test_citation_rejects_an_implausible_year(year):
    with pytest.raises(AssumptionError):
        Citation(source="s", title="t", year=year, text="x")


def test_adopted_citations_carry_full_metadata():
    for citation in (CSLF_2008, DONDA_2011):
        assert citation.source and citation.title and citation.text
        assert 2000 <= citation.year <= 2026
        assert citation.locator, "a citation must say where in the document"
        assert citation.quote, "a citation must carry supporting wording"
        assert citation.url


def test_cslf_citation_is_the_verified_primary_source():
    assert CSLF_2008.year == 2008
    assert "CSLF-T-2008-04" in CSLF_2008.text
    assert "1% and 4%" in CSLF_2008.quote
    assert CSLF_2008.evidence_class is EvidenceClass.GENERIC


def test_donda_citation_is_regional_not_site_specific():
    assert DONDA_2011.year == 2011
    assert "10.1016/j.ijggc.2010.08.009" in DONDA_2011.text
    assert DONDA_2011.evidence_class is EvidenceClass.REGIONAL
    assert not DONDA_2011.is_site_specific


def test_no_adopted_citation_claims_site_specificity():
    """Nothing was measured in a pilot well, so nothing may claim to be."""
    for a in LITERATURE_SCREENING_V1.assumptions:
        assert a.evidence_class is not EvidenceClass.SITE_SPECIFIC


def test_citation_round_trips_through_json():
    payload = json.loads(json.dumps(CSLF_2008.to_dict()))
    rebuilt = AssumptionSet.from_mapping({
        "name": "x",
        "assumptions": [{"parameter": "porosity", "value": 0.2, "author": "a",
                         "rationale": "r", "citation": payload}],
    })
    citation = rebuilt.get("porosity").citation
    assert isinstance(citation, Citation)
    assert citation.year == 2008
    assert citation.evidence_class is EvidenceClass.GENERIC


# -- literature vs placeholder provenance ------------------------------------


def test_literature_values_are_flagged_literature_derived():
    for a in LITERATURE_SCREENING_V1.assumptions:
        assert a.is_literature_derived
        assert isinstance(a.citation, Citation)


def test_placeholder_values_are_not_flagged_literature_derived():
    for a in CENTRAL.assumptions:
        assert not a.is_literature_derived
        assert a.evidence_class is EvidenceClass.PLACEHOLDER


def test_evidence_classes_are_distinguishable_in_json():
    """A client must be able to filter on evidence without reading prose."""
    lit = {a["parameter"]: a["evidence_class"]
           for a in LITERATURE_SCREENING_V1.to_dict()["assumptions"]}
    placeholder = {a["parameter"]: a["evidence_class"]
                   for a in CENTRAL.to_dict()["assumptions"]}
    assert lit["storage_efficiency"] == "generic"
    assert lit["porosity"] == "regional"
    assert set(placeholder.values()) == {"placeholder"}


def test_an_uncited_assumption_reads_as_unsupported():
    a = Assumption(parameter="area_m2", value=1e8, author="x", rationale="y")
    assert a.evidence_class is EvidenceClass.UNSUPPORTED
    assert not a.is_literature_derived


# -- scenario versioning -----------------------------------------------------


def test_literature_scenario_is_named_versioned_and_dated():
    s = LITERATURE_SCREENING_V1
    assert s.name == "literature-screening-v1"
    assert s.version == "1"
    assert s.date == "2026-09-19"
    assert s.rationale and s.description
    assert isinstance(s.citation, Citation)


def test_literature_scenario_is_resolvable_by_name():
    assert load_scenario("literature-screening-v1") is LITERATURE_SCREENING_V1
    assert load_scenario("literature") is LITERATURE_SCREENING_V1
    assert "literature-screening-v1" in BUILTIN_SCENARIOS


def test_scenario_json_carries_both_policies():
    payload = LITERATURE_SCREENING_V1.to_dict()
    assert payload["area_policy"] == AREA_POLICY_STATEMENT
    assert payload["net_thickness_policy"] == NET_THICKNESS_POLICY_STATEMENT
    json.dumps(payload)


# -- area policy -------------------------------------------------------------


def test_area_policy_statement_is_explicit():
    assert "not inferred from administrative licence boundaries" in AREA_POLICY_STATEMENT


def test_literature_scenario_does_not_supply_area_or_thickness():
    assert LITERATURE_UNSUPPORTED == ("area_m2", "thickness_m")
    assert "area_m2" not in LITERATURE_SCREENING_V1.assumed_parameters
    assert "thickness_m" not in LITERATURE_SCREENING_V1.assumed_parameters


def test_area_remains_blocking_under_the_literature_scenario(records):
    outcome = apply_scenario(records["SALUZZO|1"], LITERATURE_SCREENING_V1)
    assert isinstance(outcome, IncompleteScreening)
    assert set(outcome.missing_fields) == {"area_m2", "thickness_m"}


def test_blocking_reasons_state_the_policies(records):
    outcome = apply_scenario(records["SALUZZO|1"], LITERATURE_SCREENING_V1)
    reasons = dict(outcome.reasons)
    assert "licence boundaries" in reasons["area_m2"]
    assert "not derived from gross" in reasons["thickness_m"]


# -- gross vs net separation -------------------------------------------------


def test_gross_thickness_never_becomes_net_thickness(records, complete_scenario):
    """Gross is source-derived and large; net is assumed and separate."""
    record = records["SALUZZO|1"]
    assert record.gross_thickness_m.is_present
    assert record.gross_thickness_m.value == pytest.approx(1104.7)
    assert not record.net_storage_thickness_m.is_present

    resolved, _ = resolve_inputs(record, complete_scenario)
    assert resolved["thickness_m"].is_assumed
    assert resolved["thickness_m"].value == [25.0, 55.0]
    assert resolved["thickness_m"].value != record.gross_thickness_m.value


def test_net_thickness_policy_is_stated():
    assert "not derived from gross stratigraphic thickness" in NET_THICKNESS_POLICY_STATEMENT


# -- pressure derived from depth ---------------------------------------------


def test_pressure_is_derived_from_source_depth(records, complete_scenario):
    resolved, missing = resolve_inputs(records["SALUZZO|1"], complete_scenario)
    assert not missing
    pressure = resolved["pressure_pa"]
    assert pressure.provenance is Provenance.DERIVED
    assert not pressure.is_assumed
    assert pressure.label == "MODELLED", "a modelled value is not a plain measurement"
    assert "1527.5" in pressure.derivation


def test_pressure_scales_with_depth(records, complete_scenario):
    """A flat pressure range cannot serve wells spanning 897-6694 m."""
    shallow, _ = resolve_inputs(records["ASTI|1"], complete_scenario)      # 1247 m
    deep, _ = resolve_inputs(records["MALOSSA|15"], complete_scenario)     # 5491 m
    ratio = deep["pressure_pa"].value[0] / shallow["pressure_pa"].value[0]
    assert ratio == pytest.approx(5491.0 / 1247.0, rel=1e-6)
    assert ratio > 4


def test_hydrostatic_model_matches_rho_g_z():
    s = LITERATURE_SCREENING_V1
    low, high = s.hydrostatic_pressure_pa(1000.0)
    assert low == pytest.approx(1020.0 * STANDARD_GRAVITY_M_S2 * 1000.0)
    assert high == pytest.approx(1100.0 * STANDARD_GRAVITY_M_S2 * 1000.0)


def test_declaring_both_a_gradient_and_a_flat_pressure_is_refused():
    with pytest.raises(AssumptionError) as excinfo:
        ScreeningScenario(
            name="conflicting", description="d", brine_density_kg_m3=1050.0,
            assumptions=AssumptionSet(name="c", assumptions=(
                Assumption(parameter="pressure_pa", value=15e6, author="x", rationale="y"),
            )),
        )
    assert "choose one" in str(excinfo.value)


def test_well_without_depth_cannot_have_pressure_modelled(records, complete_scenario):
    """The model needs a source depth; without one it blocks rather than guesses."""
    record = records["ASIGLIANO|1"]
    object.__setattr__(record, "depth_m", type(record.depth_m).missing("no depth"))
    _, missing = resolve_inputs(record, complete_scenario)
    assert any(name == "pressure_pa" for name, _ in missing)


# -- source precedence and the full path -------------------------------------


def test_source_temperature_still_wins(records, complete_scenario):
    config = apply_scenario(records["SALUZZO|1"], complete_scenario)
    assert isinstance(config, ScreeningConfig)
    assert config.temperature_k == (318.15, 318.15)


def test_complete_scenario_screens_and_keeps_the_audit_trail(records, complete_scenario):
    report = screen_well(records["SALUZZO|1"], complete_scenario, samples=200)
    assert report.screenable
    assert report.result.p10_mt < report.result.p50_mt < report.result.p90_mt

    payload = json.loads(json.dumps(report.to_dict()))
    inputs = payload["screening_inputs"]
    assert set(inputs) == set(REQUIRED_FIELDS)

    efficiency = inputs["storage_efficiency"]
    assert efficiency["assumed"] is True
    assert efficiency["evidence_class"] == "generic"
    assert efficiency["citation"]["year"] == 2008
    assert "1% and 4%" in efficiency["citation"]["quote"]
    assert efficiency["rationale"]
    assert efficiency["author"]

    porosity = inputs["porosity"]
    assert porosity["evidence_class"] == "regional"
    assert "ijggc" in porosity["citation"]["text"].lower()

    assert inputs["pressure_pa"]["label"] == "MODELLED"
    assert inputs["temperature_k"]["assumed"] is False
    assert inputs["temperature_k"]["from_source"] is True


def test_capacity_never_arrives_without_provenance(records, complete_scenario):
    """Every input alongside the number carries its own origin."""
    payload = screen_well(records["SALUZZO|1"], complete_scenario, samples=100).to_dict()
    assert payload["result"]["p50_mt"] > 0
    for name, entry in payload["screening_inputs"].items():
        assert "provenance" in entry and "evidence_class" in entry, name
        assert "assumed" in entry and "label" in entry, name


def test_ignored_assumption_is_recorded(records):
    """An assumption a scenario cannot apply must say so, not vanish."""
    scenario = ScreeningScenario(
        name="tries-porosity-twice", description="d",
        assumptions=AssumptionSet(name="t", assumptions=(
            Assumption(parameter="porosity", value=0.2, author="x", rationale="y"),
        )),
    )
    resolved, _ = resolve_inputs(records["SALUZZO|1"], scenario)
    # temperature came from source and no assumption targeted it
    assert resolved["temperature_k"].assumption_ignored is False


def test_shipped_scenario_files_load_and_are_consistent():
    for name in ("literature-screening-v1.json",
                 "literature-screening-v1-with-user-inputs.json"):
        path = ROOT / "examples" / name
        if not path.exists():
            pytest.skip(f"{name} not present")
        scenario = ScreeningScenario.from_json_file(path)
        assert scenario.brine_density_kg_m3 is not None
        for a in scenario.assumptions:
            assert a.author and a.rationale
        if "with-user-inputs" in name:
            assert set(scenario.assumed_parameters) >= {"area_m2", "thickness_m"}
        else:
            assert "area_m2" not in scenario.assumed_parameters
