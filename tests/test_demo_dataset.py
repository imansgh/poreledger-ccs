"""The public synthetic demo dataset (``demo/data``).

Pins three things:

* the demo runs from repository files alone and reaches every validation
  status through the unchanged model -- VALIDATED, OUTSIDE_VALIDATED_ENVELOPE,
  UNAVAILABLE on the approved path and NOT_VALIDATED on the legacy path;
* synthetic provenance is never lost: every response says ``synthetic`` and
  leads with the ``synthetic_demo_dataset`` warning, every field value carries
  the SYNTHETIC note, and every well id is visibly fictional;
* demo and real data never mix, and real data never falls back to the demo.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from ccs_screen import api
from ccs_screen.ingest.demo import (
    DEMO_MANIFEST,
    SYNTHETIC_NOTE,
    DemoDatasetError,
    load_demo_dataset,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "demo" / "data"
REQUESTS = ROOT / "demo" / "requests"
WELLS = ("SYNTH ALPHA|1", "SYNTH BETA|1", "SYNTH DELTA|1", "SYNTH GAMMA|1")


@pytest.fixture(autouse=True)
def _fresh_cache():
    api.clear_cache()
    yield
    api.clear_cache()


def _screen(well: str, request_file: str) -> dict:
    body = json.loads((REQUESTS / request_file).read_text(encoding="utf-8"))
    return api.screen_well(well, user_inputs=body["user_inputs"], scenario=body["scenario"],
                           data_dir=DEMO_DIR, samples=body["samples"], seed=body["seed"])


def _statuses(result: dict) -> dict[str, str]:
    return {s["name"]: s["validation_status"] for s in result["water_level_scenarios"]}


def _codes(result: dict) -> set[str]:
    return {d["code"] for s in result["water_level_scenarios"] for d in s["diagnostics"]}


# -- the dataset ---------------------------------------------------------------


def test_demo_dataset_is_ready_and_declares_itself_synthetic():
    readiness = api.data_readiness(DEMO_DIR)
    assert readiness["ready"] is True and readiness["wells_loaded"] == 4
    assert readiness["dataset"]["kind"] == "synthetic_demo"
    assert readiness["dataset"]["synthetic"] is True
    assert "fictional" in readiness["dataset"]["statement"]
    assert [s["status"] for s in readiness["sources"]] == ["loaded"]


def test_demo_is_small_and_ships_only_fictional_wells():
    assert (DEMO_DIR / DEMO_MANIFEST).stat().st_size < 20_000
    assert sorted(p.name for p in DEMO_DIR.iterdir()) == [DEMO_MANIFEST]
    wells = api.list_wells(DEMO_DIR)
    assert tuple(w["well_id"] for w in wells) == WELLS
    assert all(w["well_id"].startswith("SYNTH ") and w["synthetic"] for w in wells)


def test_every_demo_field_value_is_labelled_synthetic():
    for well in WELLS:
        detail = api.get_well(well, data_dir=DEMO_DIR)
        assert detail["sources"] == [DEMO_MANIFEST]
        present = {name: f for name, f in detail["fields"].items() if f["provenance"] != "missing"}
        assert present, well
        for name, value in present.items():
            if value["provenance"] == "extracted":
                assert SYNTHETIC_NOTE in value.get("notes", []), (well, name)
                assert value["source"].startswith(DEMO_MANIFEST), (well, name)
            # Derived values point back at a synthetic source, never a real file.
            assert DEMO_MANIFEST in value.get("source", DEMO_MANIFEST), (well, name)


# -- every status through the unchanged model ---------------------------------


def test_established_synthetic_inputs_give_validated():
    result = _screen("SYNTH ALPHA|1", "approved-validated.json")
    assert result["status"] == "evaluated" and result["model_path"] == "APPROVED_MODEL"
    assert _statuses(result) == {"GROUND_REFERENCE": "VALIDATED",
                                 "SEA_LEVEL_SENSITIVITY": "VALIDATED"}
    for scenario in result["water_level_scenarios"]:
        capacity = scenario["capacity_mt"]
        assert 0 < capacity["p10"] < capacity["p50"] < capacity["p90"]
    temperature = result["temperature_selection"]
    assert temperature["selected_observation"]["method"] == "extrapolated_squarci_taffi"
    # The non-stabilized reading at the same depth is excluded by the M3 rule.
    excluded = {o["method"]: o["reasons"] for o in temperature["excluded_observations"]}
    assert "METHOD_NOT_ELIGIBLE" in excluded["non_stabilized"]


def test_unknown_datum_gives_unavailable_like_real_wells():
    result = _screen("SYNTH BETA|1", "approved-unavailable.json")
    assert set(_statuses(result).values()) == {"UNAVAILABLE"}
    assert "DEPTH_REFERENCE_NOT_ESTABLISHED" in _codes(result)
    assert all(s["capacity_mt"] is None for s in result["water_level_scenarios"])


def test_hot_deep_well_is_outside_the_validated_envelope():
    result = _screen("SYNTH GAMMA|1", "approved-outside-envelope.json")
    assert set(_statuses(result).values()) == {"OUTSIDE_VALIDATED_ENVELOPE"}
    assert all(s["capacity_mt"] is None for s in result["water_level_scenarios"])
    assert all(s["diagnostic_capacity_mt"] is not None for s in result["water_level_scenarios"])


def test_no_eligible_temperature_gives_unavailable():
    result = api.screen_well("SYNTH DELTA|1",
                             {"area_m2": 2e7, "z_top": 1900, "z_base": 2000},
                             data_dir=DEMO_DIR, samples=200)
    assert set(_statuses(result).values()) == {"UNAVAILABLE"}
    assert "TEMPERATURE_UNAVAILABLE" in _codes(result)


def test_legacy_scenario_on_demo_is_not_validated():
    result = _screen("SYNTH ALPHA|1", "legacy-not-validated.json")
    assert result["status"] == "screened"
    assert result["validation_status"] == "NOT_VALIDATED"


def test_demo_results_are_deterministic():
    first = _screen("SYNTH ALPHA|1", "approved-validated.json")
    api.clear_cache()
    second = _screen("SYNTH ALPHA|1", "approved-validated.json")
    assert first["water_level_scenarios"] == second["water_level_scenarios"]


# -- synthetic provenance on every response ------------------------------------


def _assert_synthetic(payload: dict) -> None:
    assert payload["dataset"]["synthetic"] is True
    assert payload["dataset"]["kind"] == "synthetic_demo"
    warnings = payload["interpretation"]["warnings"]
    assert warnings[0]["code"] == "synthetic_demo_dataset"
    assert warnings[0]["invalidates_result"] is True


def test_every_data_response_carries_the_synthetic_label():
    _assert_synthetic(api.get_well("SYNTH ALPHA|1", data_dir=DEMO_DIR))
    _assert_synthetic(api.required_user_inputs("SYNTH ALPHA|1", data_dir=DEMO_DIR))
    _assert_synthetic(api.required_user_inputs("SYNTH ALPHA|1", scenario="sensitivity",
                                               data_dir=DEMO_DIR))
    _assert_synthetic(_screen("SYNTH ALPHA|1", "approved-validated.json"))
    _assert_synthetic(_screen("SYNTH BETA|1", "approved-unavailable.json"))
    _assert_synthetic(_screen("SYNTH ALPHA|1", "legacy-not-validated.json"))
    # A blocked request is labelled too.
    _assert_synthetic(api.screen_well("SYNTH ALPHA|1", {"area_m2": 2e7}, data_dir=DEMO_DIR))
    _assert_synthetic(api.screening_funnel(data_dir=DEMO_DIR))
    _assert_synthetic(api.screening_funnel(scenario="sensitivity", data_dir=DEMO_DIR))
    _assert_synthetic(api.compare_temperature_methods(
        "SYNTH ALPHA|1", {"area_m2": 2e7, "thickness_m": 30}, scenario="sensitivity",
        data_dir=DEMO_DIR, samples=100))


def test_real_sources_are_not_labelled_synthetic(tmp_path):
    pytest.importorskip("openpyxl")
    from test_ingest_pipeline import _write_xlsx

    _write_xlsx(tmp_path / "Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx")
    detail = api.get_well("SALUZZO|1", data_dir=tmp_path)
    assert detail["dataset"] == {**detail["dataset"], "kind": "structured_sources",
                                 "synthetic": False}
    assert all(w["code"] != "synthetic_demo_dataset"
               for w in detail["interpretation"]["warnings"])
    assert all(w["synthetic"] is False for w in api.list_wells(tmp_path))


# -- separation from real data --------------------------------------------------


def _copy_demo(tmp_path: Path) -> Path:
    target = tmp_path / "demo"
    shutil.copytree(DEMO_DIR, target)
    return target


def test_demo_manifest_beside_real_sources_is_refused(tmp_path):
    mixed = _copy_demo(tmp_path)
    (mixed / "pozzi-storici.csv").write_text("x;y;z\n", encoding="cp1252")
    readiness = api.data_readiness(mixed)
    assert readiness["ready"] is False
    assert readiness["dataset"]["synthetic"] is True
    assert readiness["sources"][0]["status"] == "conflict"
    with pytest.raises(api.DatasetNotReadyError, match="separate"):
        api.list_wells(mixed)


def test_missing_real_data_never_falls_back_to_the_demo(tmp_path):
    readiness = api.data_readiness(tmp_path / "data")
    assert readiness["ready"] is False
    assert readiness["dataset"]["synthetic"] is False
    empty = tmp_path / "empty"
    empty.mkdir()
    readiness = api.data_readiness(empty)
    assert readiness["ready"] is False and readiness["dataset"]["synthetic"] is False


@pytest.mark.parametrize("mutate, message", [
    (lambda m: m.update(synthetic=False), "synthetic"),
    (lambda m: m.update(dataset_kind="real"), "dataset_kind"),
    (lambda m: m["wells"][0].update(name="REAL WELL 1"), "must start with 'SYNTH '"),
    (lambda m: m["wells"][0]["temperatures"][0].update(method="guess"), "unknown method"),
    (lambda m: m["wells"][0].update(depth_datum="sea_floor"), "depth_datum"),
    (lambda m: m["wells"][0].update(porosity=0.2), "unknown field"),
    (lambda m: m["wells"][0].update(depth_m=float("nan")), "finite"),
    (lambda m: m["wells"].append(dict(m["wells"][0])), "duplicate"),
])
def test_malformed_manifest_is_rejected_and_reported(tmp_path, mutate, message):
    demo = _copy_demo(tmp_path)
    manifest = json.loads((demo / DEMO_MANIFEST).read_text(encoding="utf-8"))
    mutate(manifest)
    (demo / DEMO_MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(DemoDatasetError, match=message):
        load_demo_dataset(demo)
    readiness = api.data_readiness(demo)
    assert readiness["ready"] is False
    assert readiness["sources"][0]["status"] == "unreadable"
    assert readiness["problems"][0].startswith("required source synthetic-demo unreadable")


def test_corrupt_manifest_is_not_ready(tmp_path):
    demo = _copy_demo(tmp_path)
    (demo / DEMO_MANIFEST).write_text("{not json", encoding="utf-8")
    readiness = api.data_readiness(demo)
    assert readiness["ready"] is False and "not valid JSON" in readiness["problems"][0]


# -- HTTP ----------------------------------------------------------------------


def test_http_reports_the_demo_dataset():
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from ccs_screen.web.app import create_app
    from ccs_screen.web.settings import Settings

    with TestClient(create_app(Settings(data_dir=str(DEMO_DIR)))) as client:
        health = client.get("/health").json()
        assert health["data_ready"] is True and health["dataset"]["synthetic"] is True
        ready = client.get("/ready/existing-data")
        assert ready.status_code == 200 and ready.json()["dataset"]["kind"] == "synthetic_demo"
        wells = client.get("/wells").json()
        assert all(w["synthetic"] for w in wells)
        body = json.loads((REQUESTS / "approved-validated.json").read_text(encoding="utf-8"))
        result = client.post("/wells/SYNTH ALPHA|1/screen", json=body).json()
        _assert_synthetic(result)
        assert _statuses(result)["GROUND_REFERENCE"] == "VALIDATED"


def test_demo_dataset_is_not_git_ignored_but_real_data_is():
    """The demo must be committable; the real data/ dump must never be.

    A bare ``data/`` ignore pattern also matched ``demo/data`` and would have
    kept the demo out of every clone.
    """
    import subprocess

    def ignored(path: str) -> bool | None:
        try:
            result = subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT,
                                    capture_output=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return {0: True, 1: False}.get(result.returncode)

    demo = ignored(f"demo/data/{DEMO_MANIFEST}")
    if demo is None:
        pytest.skip("git is not available or this is not a git checkout")
    assert demo is False
    assert ignored("data/Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx") is True
