"""Phase 10 audit regression tests: real-data end-to-end validation.

These run against the live ``data/`` directory, which is deliberately not in
git. The whole module skips when it is absent, so CI stays green without it --
but when the data is present these are the only tests in the suite that exercise
the real ingestion path from spreadsheet to megatonnes.

Two findings here were only reachable with real data: a temperature observation
160.9 m below its well's recorded total depth, and the per-well magnitude of the
depth-datum bias, which turned out to be narrower than Phase 4 estimated.

See ``docs/scientific-validation-audit.md``, Phase 10.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ccs_screen.ingest.records import DepthDatum
from ccs_screen.ingest.scenario import STANDARD_GRAVITY_M_S2
from ccs_screen.properties import co2_density_kg_m3

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
REQUIRED_SOURCES = (
    "Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx",
    "pozzi-storici.csv",
    "po_wells_clean.csv",
)

pytestmark = pytest.mark.skipif(
    not all((DATA_DIR / name).is_file() for name in REQUIRED_SOURCES),
    reason="real source data not present; this module needs the local data/ directory",
)

#: The wells the audit brief named.
AUDIT_WELLS = [
    "SALUZZO|1", "TRECATE|9|ST", "DESANA|1", "ASTI|1",
    "MALOSSA|15", "CRESCENTINO|1", "ASIGLIANO|1",
]

#: Wells with every required input, so they produce a capacity.
SCREENABLE = ["SALUZZO|1", "TRECATE|9|ST", "DESANA|1", "ASTI|1", "MALOSSA|15"]

USER_INPUTS = {"area_m2": 8.0e7, "thickness_m": 35.0}


@pytest.fixture(scope="module")
def records():
    from ccs_screen.api import load_records

    return {r.identity.canonical: r for r in load_records(str(DATA_DIR))}


@pytest.fixture(scope="module")
def screened():
    from ccs_screen.api import screen_well

    return {
        well: screen_well(well, user_inputs=USER_INPUTS, data_dir=str(DATA_DIR))
        for well in AUDIT_WELLS
    }


# -- identity and ingestion --------------------------------------------------


@pytest.mark.parametrize("well", AUDIT_WELLS)
def test_every_audited_well_is_in_the_corpus(records, well):
    assert well in records


def test_sidetrack_suffix_survives_canonicalisation(records):
    assert records["TRECATE|9|ST"].identity.original == "TRECATE 9ST"


# -- blocking ----------------------------------------------------------------


def test_well_without_temperature_is_blocked_on_temperature(screened):
    """Temperature is the one required input no scenario may supply."""
    result = screened["CRESCENTINO|1"]
    assert result["scenario_based_capacity_mt"] is None
    assert result["missing_fields"] == ["temperature_k"]


def test_well_without_depth_is_blocked_on_pressure(screened):
    """Pressure is derived from depth, so no depth means no pressure."""
    result = screened["ASIGLIANO|1"]
    assert result["scenario_based_capacity_mt"] is None
    assert result["missing_fields"] == ["pressure_pa"]


def test_omitting_user_inputs_returns_the_other_blocked_shape():
    """Two distinct blocked payloads exist; a client must handle both."""
    from ccs_screen.api import screen_well

    result = screen_well("SALUZZO|1", user_inputs=None, data_dir=str(DATA_DIR))
    assert result["status"] == "blocked"
    assert {f["field"] for f in result["required_user_inputs"]} == {"area_m2", "thickness_m"}
    assert "missing_fields" not in result, "the two blocked shapes must stay distinct"


# -- label partition ---------------------------------------------------------


@pytest.mark.parametrize("well", SCREENABLE)
def test_labels_partition_the_inputs_disjointly(screened, well):
    result = screened[well]
    groups = [
        result["source_derived_inputs"], result["modelled_inputs"],
        result["assumed_inputs"], result["user_supplied_inputs"],
    ]
    flat = [name for group in groups for name in group]
    assert len(flat) == len(set(flat)), "a parameter appears under two labels"
    assert set(flat) == {
        "temperature_k", "pressure_pa", "porosity",
        "storage_efficiency", "area_m2", "thickness_m",
    }


@pytest.mark.parametrize("well", SCREENABLE)
def test_pressure_is_modelled_and_temperature_is_source_derived(screened, well):
    result = screened[well]
    assert result["modelled_inputs"] == ["pressure_pa"]
    assert result["source_derived_inputs"] == ["temperature_k"]
    assert sorted(result["user_supplied_inputs"]) == ["area_m2", "thickness_m"]


# -- independent recomputation -----------------------------------------------


@pytest.mark.parametrize("well", SCREENABLE)
def test_midpoint_recomputation_has_the_expected_ratio_to_the_median(screened, well):
    """Audit measured a ratio of exactly 1.128 for all five wells.

    The median of a product of uniforms sits below the product of their
    midpoints by a factor set only by the varying priors' shapes -- which are
    identical across wells. A well-specific deviation would mean something
    well-specific is leaking into the Monte Carlo beyond the state point.
    """
    result = screened[well]
    inputs = result["screening_inputs"]

    def midpoint(name):
        value = inputs[name]["value"]
        return (value[0] + value[1]) / 2 if isinstance(value, list) else value

    density = co2_density_kg_m3(midpoint("pressure_pa"), midpoint("temperature_k"))
    recomputed_mt = (
        midpoint("area_m2") * midpoint("thickness_m") * midpoint("porosity")
        * density * midpoint("storage_efficiency") / 1e9
    )
    assert recomputed_mt / result["scenario_based_capacity_mt"]["p50"] == pytest.approx(
        1.128, abs=0.01
    )


@pytest.mark.parametrize("well", SCREENABLE)
def test_percentiles_are_ordered_and_positive(screened, well):
    capacity = screened[well]["scenario_based_capacity_mt"]
    assert 0 < capacity["p10"] < capacity["p50"] < capacity["p90"]
    assert capacity["mean"] > capacity["p50"], "a product distribution is right-skewed"


def test_repeat_calls_are_bit_identical():
    from ccs_screen.api import screen_well

    first = screen_well("SALUZZO|1", user_inputs=USER_INPUTS, data_dir=str(DATA_DIR))
    second = screen_well("SALUZZO|1", user_inputs=USER_INPUTS, data_dir=str(DATA_DIR))
    assert first["scenario_based_capacity_mt"] == second["scenario_based_capacity_mt"]


# -- Finding 10.1: temperature observation below total depth -----------------


def test_trecate_has_a_temperature_observation_below_its_total_depth(records):
    """CHARACTERISATION, Finding 10.1.

    The selected temperature comes from 6 247.9 m in a well whose recorded total
    depth is 6 087.0 m -- 160.9 m deeper than the hole. Depth and temperature
    come from different sheets of the same workbook and are never compared.

    When a containment check is added, this test must be replaced.
    """
    record = records["TRECATE|9|ST"]
    total_depth = record.depth_m.value
    deepest_observation = max(t.depth_m for t in record.temperatures)

    assert total_depth == pytest.approx(6087.0)
    assert deepest_observation == pytest.approx(6247.9)
    assert deepest_observation - total_depth == pytest.approx(160.9, abs=0.1)


@pytest.mark.parametrize("well", ["SALUZZO|1", "DESANA|1", "ASTI|1", "MALOSSA|15"])
def test_other_wells_select_a_temperature_effectively_at_total_depth(records, well):
    """Discharges most of Phase 6 Finding 6.5 on real data.

    That finding worried the 0.85 filter could select a temperature up to 15%
    shallower than TD. In practice it lands at 0.981-0.998 of TD.
    """
    record = records[well]
    selected = [
        t.depth_m for t in record.temperatures
        if t.temperature_k == record.temperature_k.value
    ]
    assert 0.97 <= selected[0] / record.depth_m.value <= 1.0


# -- Finding 10.2: the datum bias --------------------------------------------


@pytest.mark.parametrize("well", AUDIT_WELLS)
def test_datum_is_unknown_but_elevation_is_already_ingested(records, well):
    """Finding 10.2, the operative discovery.

    The elevation needed to correct the depth is present for every well. Only
    the datum label is missing, which is what makes the correction impossible
    today rather than any absence of data.
    """
    record = records[well]
    assert record.depth_datum is DepthDatum.UNKNOWN
    assert not record.depth_msl_m.is_present
    assert record.surface_elevation_m.is_present


def test_saluzzo_is_the_worst_datum_bias_in_the_sample(records):
    """CHARACTERISATION, Finding 10.2: +15.59% on capacity.

    Real-data range across the sample is +1.10% to +15.59%, which supersedes the
    8-36% Phase 4 estimated from illustrative depths.
    """
    record = records["SALUZZO|1"]
    total_depth = record.depth_m.value
    elevation = float(record.surface_elevation_m.value)
    brine_density = 1060.0

    raw = brine_density * STANDARD_GRAVITY_M_S2 * total_depth
    corrected = brine_density * STANDARD_GRAVITY_M_S2 * (total_depth - elevation)
    assert (raw - corrected) / corrected == pytest.approx(0.2546, abs=0.005)

    temperature = record.temperature_k.value
    density_bias = (
        co2_density_kg_m3(raw, temperature) - co2_density_kg_m3(corrected, temperature)
    ) / co2_density_kg_m3(corrected, temperature)
    assert density_bias == pytest.approx(0.1559, abs=0.005)


def test_the_datum_bias_shrinks_with_depth(records):
    """It is an absolute offset against a growing column, so shallow wells suffer."""
    def bias(well):
        record = records[well]
        elevation = float(record.surface_elevation_m.value)
        return elevation / (record.depth_m.value - elevation)

    assert bias("SALUZZO|1") > bias("ASTI|1") > bias("DESANA|1") > bias("MALOSSA|15")


# -- Finding 10.3 and 10.4: conflicts and gross/net --------------------------


@pytest.mark.parametrize("well", SCREENABLE)
def test_depth_disagreements_between_sources_stay_below_a_quarter_percent(records, well):
    """Negligible next to the datum bias, and each is recorded with its locator."""
    record = records[well]
    depth_conflicts = [c for c in record.conflicts if c.field_name == "depth_m"]
    for conflict in depth_conflicts:
        for alternative, _ in conflict.alternatives:
            assert abs(alternative - record.depth_m.value) / record.depth_m.value < 0.0025


@pytest.mark.parametrize("well", SCREENABLE)
def test_depth_conflicts_name_the_rejected_source(records, well):
    for conflict in (c for c in records[well].conflicts if c.field_name == "depth_m"):
        joined = " ".join(str(a) for a in conflict.alternatives)
        assert ".csv" in joined or ".xlsx" in joined


@pytest.mark.parametrize("well", AUDIT_WELLS)
def test_gross_thickness_never_becomes_the_modelled_thickness(screened, records, well):
    """Finding 10.4: the substitution would have been 10x to 32x on real data."""
    result = screened[well]
    inputs = result.get("screening_inputs", {})
    assert inputs["thickness_m"]["value"] == USER_INPUTS["thickness_m"]
    assert inputs["thickness_m"]["label"] == "USER"

    gross = records[well].gross_thickness_m
    if gross.is_present:
        assert gross.value / inputs["thickness_m"]["value"] > 5.0


# -- Finding 10.5: the disclosure fix on live data ---------------------------


@pytest.mark.parametrize(
    "well,expected_span_m", [("SALUZZO|1", 0), ("ASTI|1", 0), ("TRECATE|9|ST", 738)]
)
def test_temperature_conflicts_report_the_depth_span(records, well, expected_span_m):
    """The Phase 6 disclosure fix, verified on live data.

    SALUZZO and ASTI disagree at the same depth -- genuine method disagreement.
    TRECATE's 53 K spans 738 m, so most of it is the geothermal gradient.
    """
    conflicts = [c for c in records[well].conflicts if c.field_name == "temperature_k"]
    assert conflicts, f"{well} should record a temperature conflict"
    note = conflicts[0].note
    assert f"across {expected_span_m} m of depth" in note
    assert "geothermal gradient" in note


# -- disclosure present on every result --------------------------------------


@pytest.mark.parametrize("well", AUDIT_WELLS)
def test_every_result_declares_itself_uncertified(screened, well):
    interpretation = screened[well]["interpretation"]
    assert interpretation["site_specific"] is False
    assert interpretation["certified"] is False
    assert interpretation["proven_resource"] is False


@pytest.mark.parametrize("well", SCREENABLE)
def test_every_screened_result_carries_the_scale_mismatch_warning(screened, well):
    warnings = screened[well]["interpretation"]["warnings"]
    assert any(w["code"] == "scale_mismatch_basin_vs_closure" for w in warnings)
