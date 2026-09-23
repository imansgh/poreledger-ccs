"""HTTP endpoint contract, via FastAPI's TestClient.

The HTTP layer must be a pure translation: the same payloads, the same
provenance, the same refusals. The most important test here is
``test_response_model_does_not_drop_provenance`` -- FastAPI filters responses
against the declared model, so an over-tight schema would silently delete the
audit trail while every other test still passed.
"""

from __future__ import annotations

import json

import pytest

from ccs_screen import api
from ccs_screen.config import REQUIRED_FIELDS

from test_ingest_pipeline import PO_WELLS, POZZI_STORICI, _write_xlsx

pytest.importorskip("openpyxl")
pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from ccs_screen.web.app import create_app  # noqa: E402
from ccs_screen.web.settings import Settings  # noqa: E402

VALID = {"area_m2": 8.0e7, "thickness_m": 35.0}
ORIGIN = "http://localhost:3000"


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("web_data")
    _write_xlsx(d / "Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx")
    (d / "pozzi-storici.csv").write_bytes(POZZI_STORICI.encode("cp1252"))
    (d / "po_wells_clean.csv").write_bytes(PO_WELLS.encode("cp1252"))
    return d


@pytest.fixture(scope="module")
def settings(data_dir):
    return Settings(data_dir=str(data_dir), cors_origins=(ORIGIN,))


@pytest.fixture(scope="module")
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


def screen_body(**kw):
    body = {"user_inputs": dict(VALID), "samples": 200}
    body.update(kw)
    return body


# -- health ------------------------------------------------------------------


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["wells_loaded"] >= 1
    assert payload["scenario_default"] == "literature-screening-v1"
    assert payload["limits"]["samples"]["max"] == api.MAX_SAMPLES


# -- wells -------------------------------------------------------------------


def test_list_wells(client):
    response = client.get("/wells")
    assert response.status_code == 200
    wells = response.json()
    assert any(w["well_id"] == "SALUZZO|1" for w in wells)
    entry = next(w for w in wells if w["well_id"] == "SALUZZO|1")
    assert entry["has_temperature"] is True
    assert entry["screenable_without_user_inputs"] is False


def test_get_well(client):
    response = client.get("/wells/SALUZZO|1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["canonical_id"] == "SALUZZO|1"
    assert payload["fields"]["temperature_k"]["provenance"] == "derived"
    assert payload["interpretation"]["site_specific"] is False


def test_unknown_well_returns_404(client):
    response = client.get("/wells/NO|SUCH|WELL")
    assert response.status_code == 404
    assert response.json()["type"] == "UnknownWellError"


def test_required_inputs_endpoint(client):
    response = client.get("/wells/SALUZZO|1/inputs")
    assert response.status_code == 200
    payload = response.json()
    fields = {f["field"] for f in payload["required"]}
    assert fields == {"area_m2", "thickness_m"}
    assert payload["can_be_screened_with_user_inputs"] is True


def test_inputs_route_is_not_swallowed_by_the_well_route(client):
    """`{well_id:path}` is greedy; /inputs must still resolve to its own route."""
    assert "required" in client.get("/wells/SALUZZO|1/inputs").json()
    assert "canonical_id" in client.get("/wells/SALUZZO|1").json()


def test_unknown_well_on_inputs_returns_404(client):
    assert client.get("/wells/NOPE|9/inputs").status_code == 404


# -- screening ---------------------------------------------------------------


def test_successful_screening(client):
    response = client.post("/wells/SALUZZO|1/screen", json=screen_body())
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "screened"
    capacity = payload["scenario_based_capacity_mt"]
    assert capacity["p10"] < capacity["p50"] < capacity["p90"]
    assert capacity["n_samples"] == 200


def test_blocked_screening_is_200_not_an_error(client):
    """A well that cannot be screened is an outcome, not a failure."""
    response = client.post("/wells/ASIGLIANO|1/screen", json=screen_body(samples=50))
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "blocked"
    assert payload["scenario_based_capacity_mt"] is None
    assert "temperature_k" in payload["missing_fields"]


def test_screening_unknown_well_returns_404(client):
    response = client.post("/wells/NOPE|9/screen", json=screen_body())
    assert response.status_code == 404


def test_user_inputs_drive_the_http_result(client):
    small = client.post("/wells/SALUZZO|1/screen", json=screen_body(
        user_inputs={"area_m2": 5e7, "thickness_m": 25.0})).json()
    large = client.post("/wells/SALUZZO|1/screen", json=screen_body(
        user_inputs={"area_m2": 1.5e8, "thickness_m": 55.0})).json()
    assert (large["scenario_based_capacity_mt"]["p50"]
            > small["scenario_based_capacity_mt"]["p50"])


# -- request validation ------------------------------------------------------


@pytest.mark.parametrize("missing", ["area_m2", "thickness_m"])
def test_missing_user_input_is_rejected(client, missing):
    body = screen_body()
    del body["user_inputs"][missing]
    response = client.post("/wells/SALUZZO|1/screen", json=body)
    assert response.status_code == 422
    assert missing in json.dumps(response.json())


def test_missing_user_inputs_object_is_rejected(client):
    assert client.post("/wells/SALUZZO|1/screen", json={"samples": 100}).status_code == 422


@pytest.mark.parametrize("bad", [0, -1, -5e7])
def test_non_positive_area_is_rejected(client, bad):
    response = client.post("/wells/SALUZZO|1/screen",
                           json=screen_body(user_inputs={"area_m2": bad, "thickness_m": 35.0}))
    assert response.status_code == 422


@pytest.mark.parametrize("bad", [0, -2.0])
def test_non_positive_thickness_is_rejected(client, bad):
    response = client.post("/wells/SALUZZO|1/screen",
                           json=screen_body(user_inputs={"area_m2": 8e7, "thickness_m": bad}))
    assert response.status_code == 422


@pytest.mark.parametrize("bad", ["large", None, [1], {"v": 1}])
def test_non_numeric_area_is_rejected(client, bad):
    response = client.post("/wells/SALUZZO|1/screen",
                           json=screen_body(user_inputs={"area_m2": bad, "thickness_m": 35.0}))
    assert response.status_code == 422


def test_unknown_field_in_user_inputs_is_rejected(client):
    """extra='forbid' -- an unrecognised field must not be silently ignored."""
    response = client.post("/wells/SALUZZO|1/screen", json=screen_body(
        user_inputs={**VALID, "porosity": 0.2}))
    assert response.status_code == 422
    assert "porosity" in json.dumps(response.json())


def test_temperature_cannot_be_supplied_as_a_user_assumption(client):
    """Temperature is source-derived or the well stays blocked."""
    response = client.post("/wells/SALUZZO|1/screen", json=screen_body(
        user_inputs={**VALID, "temperature_k": 400.0}))
    assert response.status_code == 422
    assert "temperature_k" in json.dumps(response.json())


def test_unknown_top_level_field_is_rejected(client):
    response = client.post("/wells/SALUZZO|1/screen", json=screen_body(nonsense=1))
    assert response.status_code == 422


# -- samples limit -----------------------------------------------------------


@pytest.mark.parametrize("samples", [1, 100, api.MAX_SAMPLES])
def test_valid_samples_accepted(client, samples):
    response = client.post("/wells/SALUZZO|1/screen", json=screen_body(samples=samples))
    assert response.status_code == 200
    assert response.json()["scenario_based_capacity_mt"]["n_samples"] == samples


@pytest.mark.parametrize("samples", [0, -1, api.MAX_SAMPLES + 1, 10_000_000, 2.5, "2000", None])
def test_invalid_samples_rejected(client, samples):
    response = client.post("/wells/SALUZZO|1/screen", json=screen_body(samples=samples))
    assert response.status_code == 422


def test_samples_limit_is_published_in_the_schema(client):
    schema = client.get("/openapi.json").json()
    screen_schema = schema["components"]["schemas"]["ScreenRequest"]["properties"]["samples"]
    assert screen_schema["maximum"] == api.MAX_SAMPLES
    assert screen_schema["minimum"] == api.MIN_SAMPLES


def test_funnel_samples_are_bounded(client):
    assert client.get(f"/funnel?samples={api.MAX_SAMPLES + 1}").status_code == 422
    assert client.get("/funnel?samples=0").status_code == 422


# -- provenance serialisation ------------------------------------------------


def test_response_model_does_not_drop_provenance(client, data_dir):
    """FastAPI filters responses; nothing from the Python payload may vanish."""
    api.clear_cache()
    http = client.post("/wells/SALUZZO|1/screen",
                       json=screen_body(samples=200, seed=42)).json()
    python = api.screen_well("SALUZZO|1", VALID, data_dir=str(data_dir),
                             samples=200, seed=42)

    def keys(d, prefix=""):
        out = set()
        for k, v in d.items():
            out.add(prefix + k)
            if isinstance(v, dict):
                out |= keys(v, prefix + k + ".")
        return out

    dropped = keys(python) - keys(http)
    assert not dropped, f"response_model dropped: {sorted(dropped)}"

    trimmed = {k: v for k, v in http.items() if k in python}
    assert json.dumps(trimmed, sort_keys=True) == json.dumps(python, sort_keys=True)


def test_partition_is_disjoint_over_http(client):
    payload = client.post("/wells/SALUZZO|1/screen", json=screen_body()).json()
    buckets = {k: payload[k] for k in api.INPUT_PARTITION_KEYS}
    flat = [n for names in buckets.values() for n in names]
    assert len(flat) == len(set(flat))
    assert set(flat) == set(REQUIRED_FIELDS)


def test_all_four_labels_survive_http(client):
    payload = client.post("/wells/SALUZZO|1/screen", json=screen_body()).json()
    labels = {i["label"] for i in payload["screening_inputs"].values()}
    assert labels == {"source", "MODELLED", "ASSUMED", "USER"}


def test_every_input_has_its_provenance_fields_over_http(client):
    payload = client.post("/wells/SALUZZO|1/screen", json=screen_body()).json()
    for name, entry in payload["screening_inputs"].items():
        for key in ("value", "unit", "evidence_class", "assumed", "provenance", "label"):
            assert key in entry, f"{name} lost {key}"


def test_citations_survive_http(client):
    inputs = client.post("/wells/SALUZZO|1/screen", json=screen_body()).json()["screening_inputs"]
    assert inputs["storage_efficiency"]["citation"]["year"] == 2008
    assert inputs["porosity"]["citation"]["year"] == 2011
    assert inputs["area_m2"]["citation"]["evidence_class"] == "user_input"


def test_blocked_response_keeps_the_null_capacity_key(client):
    """A client must be able to read the null, not infer it from absence."""
    payload = client.post("/wells/ASIGLIANO|1/screen", json=screen_body(samples=50)).json()
    assert "scenario_based_capacity_mt" in payload
    assert payload["scenario_based_capacity_mt"] is None


# -- interpretation metadata -------------------------------------------------


def test_interpretation_over_http(client):
    payload = client.post("/wells/SALUZZO|1/screen", json=screen_body()).json()
    interpretation = payload["interpretation"]
    assert interpretation["type"] == "scenario_based_capacity"
    assert interpretation["site_specific"] is False
    assert interpretation["certified"] is False
    assert interpretation["proven_resource"] is False


def test_scale_mismatch_warning_over_http(client):
    payload = client.post("/wells/SALUZZO|1/screen", json=screen_body()).json()
    codes = {w["code"] for w in payload["interpretation"]["warnings"]}
    assert "scale_mismatch_basin_vs_closure" in codes


def test_interpretation_on_every_endpoint(client):
    payloads = [
        client.get("/wells/SALUZZO|1").json(),
        client.get("/wells/SALUZZO|1/inputs").json(),
        client.get("/funnel?samples=20").json(),
        client.post("/wells/SALUZZO|1/screen", json=screen_body()).json(),
        client.post("/wells/SALUZZO|1/temperature",
                    json=screen_body(samples=50)).json(),
    ]
    for payload in payloads:
        assert payload["interpretation"]["type"] == "scenario_based_capacity"


# -- temperature comparison --------------------------------------------------


def test_temperature_comparison_endpoint(client):
    response = client.post("/wells/SALUZZO|1/temperature", json=screen_body(samples=100))
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "compared"
    assert payload["selected_method"] == "extrapolated_squarci_taffi"
    assert len(payload["variants"]) >= 2
    assert payload["p50_spread_percent"] > 0


def test_temperature_endpoint_requires_user_inputs(client):
    assert client.post("/wells/SALUZZO|1/temperature", json={"samples": 50}).status_code == 422


# -- scenarios and funnel ----------------------------------------------------


def test_scenarios_endpoint(client):
    response = client.get("/scenarios")
    assert response.status_code == 200
    names = {s["name"] for s in response.json()}
    assert "literature-screening-v1" in names


def test_funnel_endpoint_reports_zero_from_source_alone(client):
    payload = client.get("/funnel?samples=20").json()
    assert payload["source_complete"] == 0
    assert payload["screenable"] == 0


def test_unknown_scenario_maps_to_400(client):
    """A bad scenario is a domain refusal, not a schema violation."""
    response = client.get("/wells/SALUZZO|1/inputs?scenario=no-such-scenario")
    assert response.status_code == 400
    assert response.json()["type"] == "ApiError"


# -- CORS --------------------------------------------------------------------


def test_cors_allows_the_configured_origin(client):
    response = client.get("/wells", headers={"Origin": ORIGIN})
    assert response.headers.get("access-control-allow-origin") == ORIGIN


def test_cors_rejects_an_unconfigured_origin(client):
    response = client.get("/wells", headers={"Origin": "https://evil.example"})
    assert response.headers.get("access-control-allow-origin") != "https://evil.example"


def test_cors_preflight(client):
    response = client.options("/wells/SALUZZO|1/screen", headers={
        "Origin": ORIGIN,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin") == ORIGIN


def test_cors_is_off_by_default(data_dir):
    """An unset CCS_CORS_ORIGINS must not open the API to every origin."""
    settings = Settings.from_env({"CCS_DATA_DIR": str(data_dir)})
    assert settings.cors_origins == ()
    assert settings.cors_enabled is False
    with TestClient(create_app(settings)) as bare:
        response = bare.get("/wells", headers={"Origin": ORIGIN})
        assert response.headers.get("access-control-allow-origin") is None


def test_no_wildcard_origin_is_ever_configured(data_dir):
    settings = Settings.from_env({"CCS_DATA_DIR": str(data_dir)})
    assert "*" not in settings.cors_origins


# -- body size ---------------------------------------------------------------


def test_oversized_body_is_rejected(data_dir):
    settings = Settings(data_dir=str(data_dir), max_body_bytes=512)
    with TestClient(create_app(settings)) as small:
        payload = screen_body()
        payload["user_inputs"] = dict(VALID)
        blob = {"user_inputs": dict(VALID), "samples": 100, "pad": "x" * 4096}
        response = small.post("/wells/SALUZZO|1/screen", json=blob)
        assert response.status_code == 413
        assert response.json()["type"] == "PayloadTooLarge"


def test_normal_body_passes_the_size_check(client):
    assert client.post("/wells/SALUZZO|1/screen", json=screen_body()).status_code == 200


# -- error mapping -----------------------------------------------------------


def test_error_envelope_shape(client):
    payload = client.get("/wells/NOPE|9").json()
    assert set(payload) == {"error", "type", "detail"}
    assert payload["error"]


def test_error_mapping_table(client):
    """404 for an unknown well, 400 for a domain refusal, 422 for schema."""
    assert client.get("/wells/NOPE|9").status_code == 404
    assert client.get("/wells/SALUZZO|1/inputs?scenario=nope").status_code == 400
    assert client.post("/wells/SALUZZO|1/screen", json={"samples": 10}).status_code == 422


def test_endpoints_are_sync_so_they_run_in_the_threadpool():
    """An async handler would block the event loop during a Monte Carlo run."""
    import inspect

    from ccs_screen.web import app as app_module

    application = app_module.create_app(Settings(data_dir="data"))
    for route in application.routes:
        endpoint = getattr(route, "endpoint", None)
        if endpoint is None or not getattr(route, "methods", None):
            continue
        if route.path.startswith(("/openapi", "/docs", "/redoc")):
            continue
        assert not inspect.iscoroutinefunction(endpoint), (
            f"{route.path} is async and would block the event loop"
        )


# -- scenario is not a filesystem path ---------------------------------------


@pytest.mark.parametrize(
    "scenario",
    [
        "examples/literature-screening-v1.json",
        "/etc/passwd",
        "../pyproject.toml",
        "..\pyproject.toml",
        "C:\Windows\win.ini",
        "./README.md",
    ],
)
def test_scenario_path_is_rejected_over_http(client, scenario):
    """A path is not a scenario name.

    ``ccs_screen.api`` accepts a scenario file path, which is right for the CLI.
    Over HTTP it would be an existence-and-parseability oracle for arbitrary
    server paths, so the web layer accepts built-in names only.
    """
    response = client.get("/wells/SALUZZO|1/inputs", params={"scenario": scenario})
    assert response.status_code == 400
    assert response.json()["type"] == "ApiError"
    assert "built-in" in response.json()["error"]


def test_scenario_path_is_rejected_on_screen(client):
    response = client.post(
        "/wells/SALUZZO|1/screen",
        json={"user_inputs": {"area_m2": 8e7, "thickness_m": 35.0},
              "scenario": "examples/literature-screening-v1.json", "samples": 50},
    )
    assert response.status_code == 400


def test_builtin_scenario_names_still_work(client):
    for name in ("literature-screening-v1", "central", "sensitivity", "none"):
        response = client.get("/wells/SALUZZO|1/inputs", params={"scenario": name})
        assert response.status_code == 200, name


def test_well_id_is_never_a_filesystem_path(client):
    """The well id is matched against canonical ids, never opened as a path.

    Traversal probes end as 404 either from the route not matching (the client
    normalises the path) or from the id lookup failing. What matters is that no
    probe returns content.
    """
    for probe in ("../../../etc/passwd", "..%2F..%2Fpyproject.toml", "./README.md",
                  "C:\Windows\win.ini"):
        response = client.get(f"/wells/{probe}")
        assert response.status_code == 404, probe
        body = response.json()
        if "type" in body:
            assert body["type"] == "UnknownWellError", probe
        assert "root:" not in response.text
        assert "[project]" not in response.text
