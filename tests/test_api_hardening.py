"""Hardening the public API: scale disclosure, request bounds, cache safety.

These guard properties that only matter once the API is exposed: that the
basin-vs-closure mismatch travels with the result, that one request cannot
become seconds of CPU, and that a shared cache behaves under concurrency.
"""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from ccs_screen import api
from ccs_screen.config import REQUIRED_FIELDS

from test_ingest_pipeline import PO_WELLS, POZZI_STORICI, _write_xlsx

openpyxl = pytest.importorskip("openpyxl")

VALID = {"area_m2": 8.0e7, "thickness_m": 35.0}


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("harden_data")
    _write_xlsx(d / "Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx")
    (d / "pozzi-storici.csv").write_bytes(POZZI_STORICI.encode("cp1252"))
    (d / "po_wells_clean.csv").write_bytes(PO_WELLS.encode("cp1252"))
    return d


@pytest.fixture(autouse=True)
def _clean_cache():
    api.clear_cache()
    yield
    api.clear_cache()


def screen(data_dir, **kw):
    kw.setdefault("user_inputs", VALID)
    kw.setdefault("samples", 200)
    return api.screen_well("SALUZZO|1", data_dir=data_dir, **kw)


# -- 1. basin-vs-closure scale warning ---------------------------------------


def warnings_of(payload):
    return {w["code"]: w for w in payload["interpretation"]["warnings"]}


def test_scale_mismatch_warning_is_present_for_literature_scenario(data_dir):
    codes = warnings_of(screen(data_dir))
    assert "scale_mismatch_basin_vs_closure" in codes


def test_scale_mismatch_warning_wording(data_dir):
    warning = warnings_of(screen(data_dir))["scale_mismatch_basin_vs_closure"]
    assert warning["message"] == (
        "Literature-constrained porosity and storage-efficiency ranges are not "
        "site-specific closure-scale calibrations."
    )


def test_scale_mismatch_warning_names_the_affected_parameters(data_dir):
    warning = warnings_of(screen(data_dir))["scale_mismatch_basin_vs_closure"]
    assert set(warning["affects"]) == {"porosity", "storage_efficiency"}
    assert "CSLF" in warning["detail"]
    assert "Donda" in warning["detail"]
    assert "scenario-literature-review" in warning["reference"]


def test_warning_does_not_claim_the_result_is_invalid(data_dir):
    """Disclosure, not repudiation -- and no invented correction factor."""
    warning = warnings_of(screen(data_dir))["scale_mismatch_basin_vs_closure"]
    assert warning["invalidates_result"] is False
    assert warning["correction_applied"] is False
    assert warning["severity"] == "advisory"


def test_warning_does_not_change_the_numbers(data_dir):
    """The disclosure is metadata; capacity must be untouched by it."""
    result = screen(data_dir, samples=500)
    assert result["scenario_based_capacity_mt"]["p50"] > 0
    inputs = result["screening_inputs"]
    assert inputs["porosity"]["value"] == [0.10, 0.35]
    assert inputs["storage_efficiency"]["value"] == [0.01, 0.04]


def test_warning_travels_on_every_response_shape(data_dir):
    responses = [
        api.required_user_inputs("SALUZZO|1", data_dir=data_dir),
        screen(data_dir),
        api.compare_temperature_methods("SALUZZO|1", VALID, data_dir=data_dir, samples=50),
        api.screening_funnel(data_dir=data_dir, user_inputs=VALID, samples=20),
    ]
    for response in responses:
        assert "scale_mismatch_basin_vs_closure" in warnings_of(response)


def test_no_scale_warning_for_a_scenario_without_literature_values(data_dir):
    """A placeholder scenario has no literature framing to mismatch."""
    result = api.screen_well("SALUZZO|1", VALID, scenario="sensitivity",
                             data_dir=data_dir, samples=100)
    assert "scale_mismatch_basin_vs_closure" not in warnings_of(result)


def test_warnings_list_is_always_present_and_serialisable(data_dir):
    for scenario in ("literature-screening-v1", "sensitivity"):
        result = api.screen_well("SALUZZO|1", VALID, scenario=scenario,
                                 data_dir=data_dir, samples=50)
        assert isinstance(result["interpretation"]["warnings"], list)
        json.dumps(result)


def test_interpretation_warnings_do_not_leak_between_calls(data_dir):
    """The block is rebuilt per call; a shared mutable default would accumulate."""
    first = screen(data_dir)
    second = api.screen_well("SALUZZO|1", VALID, scenario="sensitivity",
                             data_dir=data_dir, samples=50)
    assert len(first["interpretation"]["warnings"]) == 1
    assert second["interpretation"]["warnings"] == []
    assert api.INTERPRETATION["warnings"] == [], "the module constant must stay empty"


# -- 2. sample bounds ---------------------------------------------------------


def test_published_limits():
    limits = api.REQUEST_LIMITS["samples"]
    assert limits["min"] == api.MIN_SAMPLES == 1
    assert limits["max"] == api.MAX_SAMPLES == 50_000
    assert limits["default"] == api.DEFAULT_SAMPLES == 2_000
    assert limits["clamped"] is False


@pytest.mark.parametrize("samples", [1, 100, 2_000, 49_999, 50_000])
def test_valid_sample_counts_are_accepted(samples):
    assert api.validate_samples(samples) == samples


@pytest.mark.parametrize(
    "samples,fragment",
    [
        (0, "must be >= 1"),
        (-1, "must be >= 1"),
        (-50_000, "must be >= 1"),
        (50_001, "must be <= 50000"),
        (10_000_000, "must be <= 50000"),
        (2.0, "expected an integer"),
        (2.5, "expected an integer"),
        ("2000", "expected an integer"),
        (None, "expected an integer"),
        ([2000], "expected an integer"),
    ],
)
def test_invalid_sample_counts_are_rejected(samples, fragment):
    with pytest.raises(api.ApiError) as excinfo:
        api.validate_samples(samples)
    assert fragment in str(excinfo.value)


@pytest.mark.parametrize("samples", [True, False])
def test_booleans_are_rejected_as_sample_counts(samples):
    """bool is an int subclass; True would otherwise mean one realisation."""
    with pytest.raises(api.ApiError) as excinfo:
        api.validate_samples(samples)
    assert "bool" in str(excinfo.value)


def test_excessive_sample_count_is_rejected_not_clamped(data_dir):
    with pytest.raises(api.ApiError) as excinfo:
        api.screen_well("SALUZZO|1", VALID, data_dir=data_dir, samples=10_000_000)
    assert "not clamped" in str(excinfo.value)


@pytest.mark.parametrize("bad", [0, -5, 2.5, True, "2000", 50_001])
def test_every_endpoint_validates_samples(data_dir, bad):
    with pytest.raises(api.ApiError):
        api.screen_well("SALUZZO|1", VALID, data_dir=data_dir, samples=bad)
    with pytest.raises(api.ApiError):
        api.compare_temperature_methods("SALUZZO|1", VALID, data_dir=data_dir, samples=bad)
    with pytest.raises(api.ApiError):
        api.screening_funnel(data_dir=data_dir, user_inputs=VALID, samples=bad)


def test_sample_count_is_honoured_exactly(data_dir):
    """Whatever is accepted is what runs -- no silent substitution."""
    for samples in (50, 777):
        result = screen(data_dir, samples=samples)
        assert result["scenario_based_capacity_mt"]["n_samples"] == samples


def test_maximum_is_accepted_end_to_end(data_dir):
    result = screen(data_dir, samples=api.MAX_SAMPLES)
    assert result["scenario_based_capacity_mt"]["n_samples"] == api.MAX_SAMPLES


# -- 3. cache safety ----------------------------------------------------------


def test_concurrent_cold_cache_normalizes_once(data_dir, monkeypatch):
    """A cold-cache burst must not multiply the most expensive operation."""
    api.clear_cache()
    calls = []
    original = api.WellNormalizer

    class CountingNormalizer(original):  # type: ignore[misc,valid-type]
        def run(self):
            calls.append(1)
            return super().run()

    monkeypatch.setattr(api, "WellNormalizer", CountingNormalizer)

    barrier = threading.Barrier(8)

    def load():
        barrier.wait()
        return api.load_records(data_dir)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = [f.result() for f in [pool.submit(load) for _ in range(8)]]

    assert len(calls) == 1, f"normalized {len(calls)} times under a concurrent burst"
    assert all(r is results[0] for r in results), "every caller must get the same tuple"


def test_concurrent_reads_are_consistent(data_dir):
    api.load_records(data_dir)

    def read():
        records = api.load_records(data_dir)
        return len(records), records[0].canonical_id

    with ThreadPoolExecutor(max_workers=16) as pool:
        observed = {f.result() for f in [pool.submit(read) for _ in range(64)]}
    assert len(observed) == 1, f"readers disagreed: {observed}"


def test_concurrent_screening_is_stable(data_dir):
    """Shared cached records must not be mutated by a screening run."""
    def run():
        result = api.screen_well("SALUZZO|1", VALID, data_dir=data_dir, samples=100)
        return round(result["scenario_based_capacity_mt"]["p50"], 6)

    with ThreadPoolExecutor(max_workers=8) as pool:
        values = {f.result() for f in [pool.submit(run) for _ in range(24)]}
    assert len(values) == 1, f"screening was not deterministic under threads: {values}"


def test_cache_survives_concurrent_clear(data_dir):
    """clear_cache under load must not corrupt or deadlock."""
    stop = threading.Event()

    def clearer():
        while not stop.is_set():
            api.clear_cache()

    thread = threading.Thread(target=clearer, daemon=True)
    thread.start()
    try:
        for _ in range(20):
            records = api.load_records(data_dir)
            assert len(records) >= 1
    finally:
        stop.set()
        thread.join(timeout=5)
    assert not thread.is_alive()


def test_refresh_rebuilds_rather_than_mutating(data_dir):
    first = api.load_records(data_dir)
    refreshed = api.load_records(data_dir, refresh=True)
    assert refreshed is not first
    assert len(refreshed) == len(first)


def test_missing_directory_still_raises_before_taking_the_lock():
    with pytest.raises(api.ApiError):
        api.load_records("no-such-directory")
    with pytest.raises(api.ApiError):
        api.load_records("no-such-directory")  # a failed load must not poison the cache


# -- 4. contract invariants still hold ---------------------------------------


def test_partition_remains_disjoint_and_complete(data_dir):
    result = screen(data_dir)
    buckets = {k: result[k] for k in api.INPUT_PARTITION_KEYS}
    flat = [n for names in buckets.values() for n in names]
    assert len(flat) == len(set(flat))
    assert set(flat) == set(REQUIRED_FIELDS)


def test_all_four_labels_survive_hardening(data_dir):
    labels = {i["label"] for i in screen(data_dir)["screening_inputs"].values()}
    assert labels == {"source", "MODELLED", "ASSUMED", "USER"}


def test_pressure_is_still_modelled_not_source(data_dir):
    pressure = screen(data_dir)["screening_inputs"]["pressure_pa"]
    assert pressure["label"] == "MODELLED"
    assert pressure["provenance"] == "derived"


def test_literature_ranges_are_unchanged(data_dir):
    inputs = screen(data_dir)["screening_inputs"]
    assert inputs["porosity"]["value"] == [0.10, 0.35]
    assert inputs["porosity"]["citation"]["year"] == 2011
    assert inputs["storage_efficiency"]["value"] == [0.01, 0.04]
    assert inputs["storage_efficiency"]["citation"]["year"] == 2008


def test_no_new_citations_were_introduced():
    """Only the two verified primaries, plus the non-literature markers."""
    from ccs_screen.ingest.scenario import BUILTIN_SCENARIOS
    from ccs_screen.ingest.assumptions import Citation, EvidenceClass

    years = set()
    for scenario in BUILTIN_SCENARIOS.values():
        for assumption in scenario.assumptions:
            if isinstance(assumption.citation, Citation) and assumption.is_literature_derived:
                years.add((assumption.citation.source.split()[0], assumption.citation.year))
    assert years == {("CSLF", 2008), ("Donda,", 2011)}


def test_area_and_thickness_still_have_no_defaults(data_dir):
    result = api.screen_well("SALUZZO|1", data_dir=data_dir)
    assert result["status"] == "blocked"
    assert result["scenario_based_capacity_mt"] is None


def test_temperature_still_cannot_be_supplied(data_dir):
    result = api.screen_well("SALUZZO|1", {**VALID, "temperature_k": 400.0},
                             data_dir=data_dir)
    assert result["status"] == "blocked"
