"""Phase 15A regressions: software/HTTP hardening, no scientific change.

* A1 -- ``/funnel`` ran a Monte Carlo per well at the requested ``samples`` and
  discarded every result: about 15 s of CPU for one GET at MAX_SAMPLES.
* A2 -- a ``NaN`` in the body produced a 422 whose echoed ``input`` could not
  be encoded as JSON, so the client received a plain-text 500.
* B1 -- a legacy input outside ``config.BOUNDS`` passed ``UserInputs`` and
  surfaced as an uncaught ``ConfigError``: another plain-text 500.
"""

from __future__ import annotations

import json

import pytest

from ccs_screen import api
from ccs_screen.config import BOUNDS
from ccs_screen.ingest import report as report_module
from ccs_screen.ingest.report import build_funnel, screen_well
from ccs_screen.ingest.scenario import BUILTIN_SCENARIOS

from test_ingest_pipeline import PO_WELLS, POZZI_STORICI, _write_xlsx

pytest.importorskip("openpyxl")
pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from ccs_screen import approved_model  # noqa: E402
from ccs_screen.web.app import create_app  # noqa: E402
from ccs_screen.web.settings import Settings  # noqa: E402

WELL = "SALUZZO|1"
APPROVED = {"area_m2": 8.0e7, "z_top": 1400.0, "z_base": 1527.0}
LEGACY = {"area_m2": 8.0e7, "thickness_m": 35.0}
LEGACY_SCENARIOS = ("sensitivity", "central", "conservative")
ENVELOPE = {"error", "type", "detail"}


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("hardening_data")
    _write_xlsx(d / "Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx")
    (d / "pozzi-storici.csv").write_bytes(POZZI_STORICI.encode("cp1252"))
    (d / "po_wells_clean.csv").write_bytes(PO_WELLS.encode("cp1252"))
    return d


@pytest.fixture(scope="module")
def client(data_dir):
    """Server exceptions become responses, as a real client would see them."""
    app = create_app(Settings(data_dir=str(data_dir)))
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _strict_json(response) -> dict:
    """Parse as strict JSON: NaN/Infinity tokens are an error, not a value."""
    def refuse(token: str):
        raise AssertionError(f"non-standard JSON token {token!r} in the response")
    return json.loads(response.text, parse_constant=refuse)


def _assert_json_error(response, status: int, type_: str) -> dict:
    assert response.status_code == status
    assert response.headers["content-type"].startswith("application/json")
    assert "Traceback" not in response.text
    payload = _strict_json(response)
    assert set(payload) == ENVELOPE
    assert payload["type"] == type_
    assert payload["error"]
    return payload


# -- A1: /funnel runs no Monte Carlo -----------------------------------------


@pytest.fixture
def monte_carlo_forbidden(monkeypatch):
    """Fail loudly if any capacity Monte Carlo runs while this is active."""
    def forbidden(*_args, **_kwargs):
        raise AssertionError("the funnel must not run a capacity Monte Carlo")
    monkeypatch.setattr(report_module, "run_capacity", forbidden)
    monkeypatch.setattr(report_module, "run_capacity_mc", forbidden)
    monkeypatch.setattr(approved_model, "run_capacity_mc", forbidden)


@pytest.mark.parametrize("scenario", ["literature-screening-v1", "none", *LEGACY_SCENARIOS])
def test_funnel_runs_no_monte_carlo_even_at_max_samples(client, monte_carlo_forbidden, scenario):
    response = client.get(f"/funnel?scenario={scenario}&samples={api.MAX_SAMPLES}")
    assert response.status_code == 200, response.text
    assert "p50" not in response.text


def test_python_funnel_with_user_inputs_runs_no_monte_carlo(data_dir, monte_carlo_forbidden):
    funnel = api.screening_funnel(scenario="sensitivity", user_inputs=LEGACY,
                                  data_dir=data_dir, samples=api.MAX_SAMPLES)
    assert funnel["screenable"] >= 1


@pytest.mark.parametrize("scenario", ["literature-screening-v1", "none", *LEGACY_SCENARIOS])
def test_funnel_result_does_not_depend_on_samples(client, scenario):
    low = client.get(f"/funnel?scenario={scenario}&samples={api.MIN_SAMPLES}").json()
    high = client.get(f"/funnel?scenario={scenario}&samples={api.MAX_SAMPLES}").json()
    assert low == high


@pytest.mark.parametrize("scenario", ["none", *LEGACY_SCENARIOS])
def test_funnel_counts_match_the_fully_screened_fleet(data_dir, scenario):
    """The MC-free funnel reports what screening every well would report."""
    records = list(api.load_records(data_dir))
    active = BUILTIN_SCENARIOS[scenario]
    screened = [screen_well(r, active, samples=5) for r in records]
    assert (build_funnel(records, active).to_dict()
            == build_funnel(records, active, screened).to_dict())


def test_funnel_response_contract_is_unchanged(client):
    legacy = client.get("/funnel?scenario=sensitivity").json()
    assert {"model_path", "validation_status", "interpretation", "required_user_inputs",
            "normalized", "with_temperature", "with_gross_thickness", "with_depth",
            "source_complete", "scenario_complete", "screenable", "blocked",
            "blocked_by_field", "scenario"} <= set(legacy)
    assert legacy["model_path"] == "LEGACY_NOT_VALIDATED"
    assert legacy["scenario_complete"] == legacy["screenable"] >= 1
    approved = client.get("/funnel").json()
    assert approved["model_path"] == "APPROVED_MODEL"
    assert approved["approved_results_computed"] == 0


def test_funnel_samples_is_still_range_checked(client):
    """Kept for compatibility: out-of-range values are still rejected."""
    _assert_json_error(client.get(f"/funnel?samples={api.MAX_SAMPLES + 1}"),
                       422, "RequestValidationError")


# -- A2: non-finite input is a structured 422, never a 500 --------------------


NON_FINITE = ["NaN", "Infinity", "-Infinity"]


def _raw_body(user_inputs: dict, scenario: str | None = None, **top: str) -> str:
    """A JSON body with raw tokens, since json.dumps would refuse to write NaN."""
    fields = [f'"{k}": {v}' for k, v in user_inputs.items()]
    parts = ['"user_inputs": {' + ", ".join(fields) + "}"]
    if scenario:
        parts.append(f'"scenario": "{scenario}"')
    parts += [f'"{k}": {v}' for k, v in top.items()]
    return "{" + ", ".join(parts) + "}"


def _cases(token: str) -> list[tuple[str, str, str]]:
    approved = {"area_m2": "8e7", "z_top": "1400", "z_base": "1527"}
    legacy = {"area_m2": "8e7", "thickness_m": "35"}
    ntg = ('{"low": %s, "high": 0.5, "net_criterion": "unspecified", '
           '"net_basis": "unknown"}' % token)
    return [
        ("screen", _raw_body({**approved, "area_m2": token}), "area_m2"),
        ("screen", _raw_body({**approved, "z_top": token}), "z_top"),
        ("screen", _raw_body({**approved, "z_base": token}), "z_base"),
        ("screen", _raw_body({**legacy, "area_m2": token}, "sensitivity"), "area_m2"),
        ("screen", _raw_body({**legacy, "thickness_m": token}, "sensitivity"), "thickness_m"),
        ("screen", _raw_body({**approved, "net_to_gross": ntg}), "low"),
        ("screen", _raw_body(approved, samples=token), "samples"),
        ("screen", _raw_body(approved, seed=token), "seed"),
        ("temperature", _raw_body({**legacy, "area_m2": token}, "sensitivity"), "area_m2"),
    ]


@pytest.mark.parametrize("token", NON_FINITE)
def test_non_finite_input_is_a_structured_422(client, token):
    for endpoint, body, field in _cases(token):
        response = client.post(f"/wells/{WELL}/{endpoint}", content=body,
                               headers={"content-type": "application/json"})
        payload = _assert_json_error(response, 422, "RequestValidationError")
        assert field in payload["error"], (endpoint, field, payload["error"])
        assert isinstance(payload["detail"], list) and payload["detail"]
        assert any(entry["loc"][-1] == field for entry in payload["detail"])


@pytest.mark.parametrize("token", NON_FINITE)
def test_rejected_non_finite_value_is_echoed_by_name(client, token):
    body = _raw_body({**APPROVED, "area_m2": token})
    response = client.post(f"/wells/{WELL}/screen", content=body,
                           headers={"content-type": "application/json"})
    entry = _assert_json_error(response, 422, "RequestValidationError")["detail"][0]
    assert entry["input"] == token


def test_validation_detail_keeps_fastapi_field_errors(client):
    """Clients that read detail[].loc / detail[].msg keep working."""
    response = client.post(f"/wells/{WELL}/screen",
                           json={"user_inputs": {**APPROVED, "porosity": 0.2}})
    payload = _assert_json_error(response, 422, "RequestValidationError")
    assert payload["detail"][0]["loc"] == ["body", "user_inputs", "porosity"]
    assert payload["detail"][0]["msg"]


def test_unexpected_error_is_a_json_500_without_internals(data_dir, monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("secret internal detail")
    monkeypatch.setattr(api, "screen_well", boom)
    with TestClient(create_app(Settings(data_dir=str(data_dir))),
                    raise_server_exceptions=False) as c:
        response = c.post(f"/wells/{WELL}/screen", json={"user_inputs": APPROVED})
    payload = _assert_json_error(response, 500, "InternalServerError")
    assert "secret internal detail" not in response.text
    assert payload["detail"] is None


def test_unexpected_error_is_not_swallowed(data_dir, monkeypatch):
    """The server still sees the exception after the client gets the envelope."""
    def boom(*_args, **_kwargs):
        raise RuntimeError("must propagate")
    monkeypatch.setattr(api, "screen_well", boom)
    with TestClient(create_app(Settings(data_dir=str(data_dir)))) as c:
        with pytest.raises(RuntimeError, match="must propagate"):
            c.post(f"/wells/{WELL}/screen", json={"user_inputs": APPROVED})


# -- B1: legacy inputs outside config.BOUNDS are blocked, never a 500 ----------


AREA_MAX = BOUNDS["area_m2"][1]
THICKNESS_MAX = BOUNDS["thickness_m"][1]
OUT_OF_BOUNDS = [
    ({"area_m2": 8.0e7, "thickness_m": 6000.0}, "thickness_m"),
    ({"area_m2": 8.0e7, "thickness_m": THICKNESS_MAX}, "thickness_m"),  # exclusive bound
    ({"area_m2": 1.0e13, "thickness_m": 35.0}, "area_m2"),
    ({"area_m2": AREA_MAX, "thickness_m": 35.0}, "area_m2"),  # exclusive bound
]


def _assert_blocked_on(payload: dict, field: str) -> None:
    assert payload["status"] == "blocked"
    assert payload["model_path"] == "LEGACY_NOT_VALIDATED"
    assert payload["validation_status"] == "NOT_VALIDATED"
    assert payload["reason"] == "missing_or_invalid_user_inputs"
    assert payload["scenario_based_capacity_mt"] is None
    assert payload["error"].startswith(f"{field}: must be <")


@pytest.mark.parametrize("scenario", LEGACY_SCENARIOS)
@pytest.mark.parametrize("user_inputs, field", OUT_OF_BOUNDS)
def test_out_of_bounds_legacy_input_is_blocked_over_http(client, scenario, user_inputs, field):
    response = client.post(f"/wells/{WELL}/screen",
                           json={"user_inputs": user_inputs, "scenario": scenario})
    assert response.status_code == 200
    assert "Traceback" not in response.text
    _assert_blocked_on(_strict_json(response), field)


@pytest.mark.parametrize("user_inputs, field", OUT_OF_BOUNDS)
def test_out_of_bounds_legacy_input_is_blocked_on_temperature(client, user_inputs, field):
    response = client.post(f"/wells/{WELL}/temperature",
                           json={"user_inputs": user_inputs, "scenario": "sensitivity"})
    assert response.status_code == 200
    _assert_blocked_on(_strict_json(response), field)


@pytest.mark.parametrize("user_inputs, field", OUT_OF_BOUNDS)
def test_out_of_bounds_python_funnel_is_an_api_error(data_dir, user_inputs, field):
    with pytest.raises(api.ApiError, match=f"^{field}: must be <"):
        api.screening_funnel(scenario="sensitivity", user_inputs=user_inputs, data_dir=data_dir)


@pytest.mark.parametrize("user_inputs, field", [
    ({"area_m2": 0.0, "thickness_m": 35.0}, "area_m2"),
    ({"area_m2": 8.0e7, "thickness_m": -1.0}, "thickness_m"),
])
def test_below_bound_legacy_input_is_blocked_in_the_python_api(data_dir, user_inputs, field):
    payload = api.screen_well(WELL, user_inputs=user_inputs, scenario="sensitivity",
                              data_dir=data_dir, samples=10)
    assert payload["status"] == "blocked"
    assert payload["error"].startswith(f"{field}: must be > 0")


def test_bounds_are_the_existing_config_bounds():
    """No new bound is introduced: UserInputs refuses exactly what config refuses."""
    api.UserInputs(area_m2=AREA_MAX * 0.999, thickness_m=THICKNESS_MAX * 0.999)
    with pytest.raises(api.ApiError):
        api.UserInputs(area_m2=AREA_MAX, thickness_m=35.0)
    with pytest.raises(api.ApiError):
        api.UserInputs(area_m2=8.0e7, thickness_m=THICKNESS_MAX)


def test_valid_legacy_input_near_the_bound_still_screens(client):
    response = client.post(f"/wells/{WELL}/screen", json={
        "user_inputs": {"area_m2": 8.0e7, "thickness_m": THICKNESS_MAX - 1},
        "scenario": "central", "samples": 10})
    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "screened"
    assert payload["scenario_based_capacity_mt"]["p50"] > 0


@pytest.mark.parametrize("scenario", LEGACY_SCENARIOS)
def test_valid_legacy_result_matches_the_python_api(client, data_dir, scenario):
    http = client.post(f"/wells/{WELL}/screen",
                       json={"user_inputs": LEGACY, "scenario": scenario, "samples": 200}).json()
    python = api.screen_well(WELL, user_inputs=LEGACY, scenario=scenario,
                             data_dir=data_dir, samples=200)
    assert http["status"] == "screened"
    assert http["scenario_based_capacity_mt"] == python["scenario_based_capacity_mt"]
