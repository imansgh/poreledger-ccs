"""Phase 15a software hardening: regressions for REVIEW-2026-10-01.

One section per confirmed finding:

1. the request-body cap consumed a whole chunked body before answering 413;
4. ``NaN`` passed the ``value <= 0`` guards of the public numerical functions;
5. ``E1(u)`` underflow made ``max_injection_rate_m3_s`` divide by zero;
6. R2 was 1.0 for a constant target even when every prediction was wrong;
7. fractional ``samples`` / ``seed`` were silently truncated;

plus data readiness: a missing required source or reader dependency was
swallowed by ``WellNormalizer.run`` and ``/health`` said ``ok`` with no wells.

Findings 2 and 3 are frontend races, covered in ``frontend/tests``.
"""

from __future__ import annotations

import asyncio
import json
import math
import sys

import numpy as np
import pytest

from ccs_screen import api
from ccs_screen.capacity import volumetric_storage_mass_kg
from ccs_screen.cli import main as cli_main
from ccs_screen.config import ConfigError, ScreeningConfig
from ccs_screen.ingest.normalize import WellNormalizer
from ccs_screen.monte_carlo import CapacitySample, UniformPriors
from ccs_screen.pressure import (
    TheisDomainError,
    allowable_delta_p_pa,
    fracture_pressure_pa,
    max_injection_rate_m3_s,
    theis_injection_delta_p_pa,
    theis_transmissivity,
)
from ccs_screen.properties import co2_density_kg_m3
from ccs_screen.surrogate import evaluate, fit_linear_surrogate

from test_ingest_pipeline import PO_WELLS, POZZI_STORICI, _write_xlsx

NAN = float("nan")
INF = float("inf")
NON_FINITE = (NAN, INF, -INF)

CAPACITY = dict(area_m2=8e7, thickness_m=35.0, porosity=0.2,
                co2_density_kg_m3=600.0, storage_efficiency=0.02)
AQUIFER = dict(permeability_m2=8e-14, thickness_m=40.0, viscosity_pa_s=4.5e-4,
               time_s=3.15e8, radius_m=500.0, porosity=0.18, compressibility_1_pa=1.2e-9)
#: The review's reproduction: u is so large that E1(u) underflows to 0.0.
UNDERFLOW = dict(AQUIFER, permeability_m2=1e-20, time_s=1.0, radius_m=100_000.0)


# -- 1. streaming body cap ---------------------------------------------------


def _scope(method: str, path: str, headers: list[tuple[bytes, bytes]]) -> dict:
    return {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
        "query_string": b"", "root_path": "", "headers": headers,
        "client": ("127.0.0.1", 1234), "server": ("testserver", 80),
    }


def _drive(app, scope: dict, chunks: list[bytes]) -> tuple[list[dict], int]:
    """Run one ASGI request; return the sent messages and body bytes consumed."""
    sent: list[dict] = []
    consumed = 0
    queue = list(chunks)

    async def receive() -> dict:
        nonlocal consumed
        if not queue:
            return {"type": "http.request", "body": b"", "more_body": False}
        chunk = queue.pop(0)
        consumed += len(chunk)
        return {"type": "http.request", "body": chunk, "more_body": bool(queue)}

    async def send(message: dict) -> None:
        sent.append(message)

    asyncio.run(app(scope, receive, send))
    return sent, consumed


def _status_and_json(sent: list[dict]) -> tuple[int, dict]:
    starts = [m for m in sent if m["type"] == "http.response.start"]
    assert len(starts) == 1, f"exactly one response expected, got {sent}"
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return starts[0]["status"], json.loads(body)


def _body_reading_app():
    """A downstream app that reads the whole body, as a JSON endpoint does."""
    seen = {"bytes": 0, "completed": False}

    async def app(scope, receive, send):
        while True:
            message = await receive()
            seen["bytes"] += len(message.get("body", b""))
            if not message.get("more_body"):
                break
        seen["completed"] = True
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    return app, seen


def test_chunked_body_stops_being_read_once_the_cap_is_passed():
    """The review's reproduction: 1,000,000 bytes against a 100-byte cap."""
    from ccs_screen.web.app import BodySizeLimitMiddleware

    downstream, seen = _body_reading_app()
    middleware = BodySizeLimitMiddleware(downstream, max_bytes=100)
    chunks = [b"x" * 100] * 10_000  # 1,000,000 bytes, no Content-Length
    sent, consumed = _drive(middleware, _scope("POST", "/x", []), chunks)

    status, payload = _status_and_json(sent)
    assert status == 413
    assert payload == {"error": "request body too large", "type": "PayloadTooLarge",
                       "detail": "limit is 100 bytes"}
    # One chunk past the cap is the most that may be read: 200 of 1,000,000.
    assert consumed == 200
    assert seen["completed"] is False


def test_received_bytes_are_checked_even_when_content_length_understates_them():
    from ccs_screen.web.app import BodySizeLimitMiddleware

    downstream, _ = _body_reading_app()
    middleware = BodySizeLimitMiddleware(downstream, max_bytes=100)
    scope = _scope("POST", "/x", [(b"content-length", b"50")])
    sent, consumed = _drive(middleware, scope, [b"x" * 60] * 100)
    assert _status_and_json(sent)[0] == 413
    assert consumed == 120


def test_declared_oversize_is_refused_before_any_byte_is_read():
    from ccs_screen.web.app import BodySizeLimitMiddleware

    downstream, _ = _body_reading_app()
    middleware = BodySizeLimitMiddleware(downstream, max_bytes=100)
    scope = _scope("POST", "/x", [(b"content-length", b"1000000")])
    sent, consumed = _drive(middleware, scope, [b"x" * 100] * 10_000)
    assert _status_and_json(sent)[0] == 413
    assert consumed == 0


@pytest.mark.parametrize("value", [b"abc", b"-5"])
def test_invalid_content_length_is_a_400_envelope(value):
    from ccs_screen.web.app import BodySizeLimitMiddleware

    downstream, _ = _body_reading_app()
    middleware = BodySizeLimitMiddleware(downstream, max_bytes=100)
    sent, consumed = _drive(middleware, _scope("POST", "/x", [(b"content-length", value)]),
                            [b"{}"])
    status, payload = _status_and_json(sent)
    assert (status, payload["type"], consumed) == (400, "ApiError", 0)


def test_small_body_passes_through_unchanged():
    from ccs_screen.web.app import BodySizeLimitMiddleware

    downstream, seen = _body_reading_app()
    middleware = BodySizeLimitMiddleware(downstream, max_bytes=100)
    sent, consumed = _drive(middleware, _scope("POST", "/x", []), [b"x" * 40, b"y" * 60])
    assert _status_and_json(sent)[0] == 200
    assert consumed == 100 and seen["bytes"] == 100 and seen["completed"]


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("hardening_data")
    _write_xlsx(d / "Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx")
    (d / "pozzi-storici.csv").write_bytes(POZZI_STORICI.encode("cp1252"))
    (d / "po_wells_clean.csv").write_bytes(PO_WELLS.encode("cp1252"))
    return d


def _web():
    pytest.importorskip("fastapi")
    pytest.importorskip("openpyxl")
    from ccs_screen.web.app import create_app
    from ccs_screen.web.settings import Settings
    return create_app, Settings


def test_full_app_answers_413_envelope_for_an_endless_chunked_body(data_dir):
    """Through FastAPI: its body-parse error for the aborted read is suppressed,
    so the client sees the 413 envelope only, and the stream is abandoned."""
    create_app, Settings = _web()
    app = create_app(Settings(data_dir=str(data_dir), max_body_bytes=100,
                              warm_cache_on_startup=False))
    scope = _scope("POST", "/wells/SALUZZO|1/screen", [(b"content-type", b"application/json")])
    sent, consumed = _drive(app, scope, [b" " * 100] * 10_000)
    status, payload = _status_and_json(sent)
    assert status == 413 and payload["type"] == "PayloadTooLarge"
    assert set(payload) == {"error", "type", "detail"}
    assert consumed == 200


def test_full_app_serves_a_chunked_body_within_the_cap(data_dir):
    create_app, Settings = _web()
    app = create_app(Settings(data_dir=str(data_dir), warm_cache_on_startup=False))
    body = json.dumps({"user_inputs": {"area_m2": 8e7, "z_top": 1400.0, "z_base": 1527.0},
                       "samples": 50}).encode()
    scope = _scope("POST", "/wells/SALUZZO|1/screen", [(b"content-type", b"application/json")])
    sent, consumed = _drive(app, scope, [body[:20], body[20:]])
    status, payload = _status_and_json(sent)
    assert status == 200 and payload["status"] == "evaluated"
    assert consumed == len(body)


# -- 4. non-finite inputs to the public numerical functions ------------------


def test_volumetric_mass_rejects_the_reviews_nan():
    with pytest.raises(ValueError, match="area_m2 must be finite"):
        volumetric_storage_mass_kg(NAN, 35, 0.2, 600, 0.02)


@pytest.mark.parametrize("name", list(CAPACITY))
@pytest.mark.parametrize("bad", NON_FINITE)
def test_volumetric_mass_rejects_every_non_finite_argument(name, bad):
    with pytest.raises(ValueError, match=f"{name} must be finite"):
        volumetric_storage_mass_kg(**{**CAPACITY, name: bad})


def test_volumetric_mass_rejects_overflow_and_non_numbers():
    with pytest.raises(ValueError, match="not a finite positive number"):
        volumetric_storage_mass_kg(**{**CAPACITY, "area_m2": 1e300, "thickness_m": 1e300})
    with pytest.raises(TypeError):
        volumetric_storage_mass_kg(**{**CAPACITY, "area_m2": True})


def test_volumetric_mass_is_unchanged_for_valid_inputs():
    expected = 8e7 * 35.0 * 0.2 * 600.0 * 0.02
    assert volumetric_storage_mass_kg(**CAPACITY) == expected
    assert volumetric_storage_mass_kg(**{**CAPACITY, "area_m2": np.float64(8e7)}) == expected


@pytest.mark.parametrize("name", list(AQUIFER))
@pytest.mark.parametrize("bad", NON_FINITE)
def test_theis_functions_reject_every_non_finite_argument(name, bad):
    with pytest.raises(ValueError, match=f"{name} must be finite"):
        theis_injection_delta_p_pa(rate_m3_s=0.08, **{**AQUIFER, name: bad})
    with pytest.raises(ValueError, match=f"{name} must be finite"):
        max_injection_rate_m3_s(allowable_delta_p_pa=1e6, **{**AQUIFER, name: bad})


@pytest.mark.parametrize("bad", NON_FINITE)
def test_pressure_helpers_reject_non_finite_inputs(bad):
    with pytest.raises(ValueError, match="must be finite"):
        theis_injection_delta_p_pa(rate_m3_s=bad, **AQUIFER)
    with pytest.raises(ValueError, match="must be finite"):
        max_injection_rate_m3_s(allowable_delta_p_pa=bad, **AQUIFER)
    with pytest.raises(ValueError, match="must be finite"):
        fracture_pressure_pa(bad, 15_000.0)
    with pytest.raises(ValueError, match="must be finite"):
        allowable_delta_p_pa(bad, 2000.0, 15_000.0, 0.9)
    with pytest.raises(ValueError):
        allowable_delta_p_pa(15e6, 2000.0, 15_000.0, bad)


def test_intermediate_overflow_is_a_domain_error_not_inf():
    with pytest.raises(TheisDomainError, match="transmissivity"):
        theis_transmissivity(1e300, 1e300, 1e-300)
    with pytest.raises(TheisDomainError, match="fracture pressure"):
        fracture_pressure_pa(1e300, 1e300)


def test_theis_values_are_unchanged_for_valid_inputs():
    from scipy.special import exp1

    t = 8e-14 * 40.0 / 4.5e-4
    u = (500.0**2 * 0.18 * 1.2e-9 * 40.0) / (4 * t * 3.15e8)
    unit_dp = (1.0 / (4 * math.pi * t)) * float(exp1(u))
    assert theis_injection_delta_p_pa(rate_m3_s=1.0, **AQUIFER) == unit_dp
    assert max_injection_rate_m3_s(allowable_delta_p_pa=1e6, **AQUIFER) == 1e6 / unit_dp


@pytest.mark.parametrize("bad", NON_FINITE)
def test_eos_and_priors_reject_non_finite_inputs(bad):
    with pytest.raises(ValueError, match="must be finite"):
        co2_density_kg_m3(bad, 330.0)
    with pytest.raises(ValueError, match="must be finite"):
        co2_density_kg_m3(15e6, bad)
    ranges = dict(area_m2=(1e7, 1e8), thickness_m=(10.0, 50.0), porosity=(0.1, 0.2),
                  pressure_pa=(10e6, 20e6), temperature_k=(320.0, 360.0),
                  storage_efficiency=(0.01, 0.04))
    with pytest.raises(ValueError, match="must be finite"):
        UniformPriors(**{**ranges, "porosity": (0.1, bad)})


# -- 5. Theis underflow ------------------------------------------------------


def test_underflowed_theis_response_is_a_domain_error_not_zero_division():
    """The review's reproduction; it raised ZeroDivisionError."""
    assert theis_injection_delta_p_pa(rate_m3_s=1.0, **UNDERFLOW) == 0.0
    with pytest.raises(TheisDomainError, match="underflows to zero") as excinfo:
        max_injection_rate_m3_s(allowable_delta_p_pa=1e6, **UNDERFLOW)
    assert isinstance(excinfo.value, ValueError)


def test_cli_reports_underflowed_max_rate_as_unavailable(capsys):
    argv = ["--samples", "50", "--json", "--permeability-m2", "1e-20",
            "--radius-m", "100000", "--years", str(1 / (365.25 * 24 * 3600)),
            "--fracture-gradient-pa-m", "15000", "--safety-factor", "0.9"]
    assert cli_main(argv) == 0
    injectivity = json.loads(capsys.readouterr().out)["injectivity"]
    assert injectivity["max_rate_m3_s"] is None
    assert injectivity["output_status"]["max_rate_m3_s"] == "UNAVAILABLE"
    assert "underflows to zero" in injectivity["unavailable_reasons"]["max_rate_m3_s"]
    assert injectivity["validation_status"] == "NOT_VALIDATED"

    assert cli_main([arg for arg in argv if arg != "--json"]) == 0
    assert "max rate UNAVAILABLE" in capsys.readouterr().out


# -- 6. R2 on a constant target ----------------------------------------------


def _samples(n: int, vary: bool = True) -> list[CapacitySample]:
    rng = np.random.default_rng(0)
    return [CapacitySample(area_m2=float(rng.uniform(1e7, 1e8)) if vary else 5e7,
                           thickness_m=30.0, porosity=0.2, pressure_pa=15e6,
                           temperature_k=330.0, storage_efficiency=0.02) for _ in range(n)]


def test_wrong_prediction_of_a_constant_target_is_not_a_perfect_r2():
    """The review's reproduction: target 2 Mt, prediction 12 Mt."""
    samples = _samples(20)
    model = fit_linear_surrogate(samples, np.full(20, 12.0))
    metrics = evaluate(model, samples, np.full(20, 2.0))
    assert metrics.rmse_mt == pytest.approx(10.0)
    assert metrics.mae_mt == pytest.approx(10.0)
    assert metrics.r2 == 0.0


def test_exact_prediction_of_a_constant_target_keeps_r2_one():
    samples = _samples(20)
    model = fit_linear_surrogate(samples, np.full(20, 2.0))
    assert evaluate(model, samples, np.full(20, 2.0)).r2 == 1.0
    big = np.full(20, 358.15e3)
    assert evaluate(fit_linear_surrogate(samples, big), samples, big).r2 == 1.0


def test_r2_for_a_varying_target_is_the_usual_definition():
    samples = _samples(50)
    y = np.array([s.area_m2 for s in samples]) / 1e7 + np.linspace(0, 1, 50)
    model = fit_linear_surrogate(samples, y)
    metrics = evaluate(model, samples, y)
    from ccs_screen.surrogate import predict_samples
    residual = predict_samples(model, samples) - y
    expected = 1.0 - np.sum(residual**2) / np.sum((y - y.mean()) ** 2)
    assert metrics.r2 == pytest.approx(expected)
    assert 0.0 < metrics.r2 < 1.0


# -- 7. run controls ---------------------------------------------------------


REQUIRED = dict(area_m2=8e7, thickness_m=35.0, porosity=0.2, pressure_pa=15e6,
                temperature_k=330.0, storage_efficiency=0.02)


def test_fractional_samples_and_seed_are_rejected_not_truncated():
    """The review's reproduction: 2.9 and 4.7 became 2 and 4."""
    with pytest.raises(ConfigError) as excinfo:
        ScreeningConfig.from_mapping({**REQUIRED, "samples": 2.9, "seed": 4.7})
    problems = excinfo.value.problems
    assert "samples: must be a whole number, got 2.9" in problems
    assert "seed: must be a whole number, got 4.7" in problems


@pytest.mark.parametrize("field, value, message", [
    ("samples", 2.9, "samples: must be a whole number"),
    ("seed", 4.7, "seed: must be a whole number"),
    ("seed", -1, "seed: must be >= 0"),
    ("seed", True, "seed: expected a number"),
    ("seed", NAN, "seed: must be a finite number"),
    ("samples", 0, "samples: must be > 0"),
])
def test_direct_construction_validates_run_controls_like_the_mapping(field, value, message):
    for build in (lambda: ScreeningConfig(**REQUIRED_RANGES, **{field: value}),
                  lambda: ScreeningConfig.from_mapping({**REQUIRED, field: value})):
        with pytest.raises(ConfigError, match=message):
            build()


REQUIRED_RANGES = {name: (value, value) for name, value in REQUIRED.items()}


def test_integer_run_controls_are_preserved():
    config = ScreeningConfig.from_mapping({**REQUIRED, "samples": 300, "seed": 7})
    assert (config.samples, config.seed) == (300, 7)
    # JSON spells 1000 as 1e3 or 1000.0: the same integer, kept as an int.
    config = ScreeningConfig.from_mapping({**REQUIRED, "samples": 1e3, "seed": 2.0})
    assert (config.samples, config.seed) == (1000, 2)
    assert isinstance(config.samples, int) and isinstance(config.seed, int)
    direct = ScreeningConfig(**REQUIRED_RANGES, samples=500.0, seed=2**40)
    assert (direct.samples, direct.seed) == (500, 2**40)
    assert isinstance(direct.samples, int)
    assert ScreeningConfig(**REQUIRED_RANGES).seed == 42


# -- data readiness ----------------------------------------------------------


def test_normalizer_reports_missing_required_sources(tmp_path):
    normalizer = WellNormalizer(tmp_path)
    assert normalizer.run() == []
    status = {s.source: s for s in normalizer.source_status}
    assert len(status) == 5
    assert all(s.status == "missing" for s in status.values())
    assert {s.source for s in normalizer.missing_required_sources} == {
        "GEOTHOPICA:Anagrafica", "GEOTHOPICA:Temperature", "GEOTHOPICA:Lito-Stratigrafie"}
    assert status["po_wells"].required is False


def test_optional_sources_may_be_absent(tmp_path):
    pytest.importorskip("openpyxl")
    _write_xlsx(tmp_path / "Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx")
    normalizer = WellNormalizer(tmp_path)
    assert normalizer.run()
    assert normalizer.missing_required_sources == ()
    optional = {s.source: s.status for s in normalizer.source_status if not s.required}
    assert optional == {"pozzi-storici": "missing", "po_wells": "missing"}
    readiness = api.data_readiness(tmp_path)
    assert readiness["ready"] is True and readiness["problems"] == []


def test_missing_reader_dependency_is_reported(tmp_path, monkeypatch, caplog):
    pytest.importorskip("openpyxl")
    _write_xlsx(tmp_path / "Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx")
    monkeypatch.setitem(sys.modules, "openpyxl", None)  # import now raises ImportError
    with caplog.at_level("WARNING", logger="ccs_screen.ingest.normalize"):
        normalizer = WellNormalizer(tmp_path)
        assert normalizer.run() == []
    assert {s.status for s in normalizer.missing_required_sources} == {"dependency_missing"}
    assert "openpyxl" in normalizer.missing_required_sources[0].detail
    assert "required source GEOTHOPICA:Anagrafica not loaded" in caplog.text


def test_health_is_liveness_and_ready_reports_an_empty_dataset(tmp_path):
    create_app, Settings = _web()
    from fastapi.testclient import TestClient

    api.clear_cache()
    with TestClient(create_app(Settings(data_dir=str(tmp_path)))) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        assert health.json()["data_ready"] is False
        assert health.json()["wells_loaded"] == 0

        ready = client.get("/ready/existing-data")
        assert ready.status_code == 503
        payload = ready.json()
        assert payload["status"] == "not_ready"
        assert any("GEOTHOPICA:Anagrafica" in p for p in payload["problems"])
        assert {s["status"] for s in payload["sources"] if s["required"]} == {"missing"}


def test_health_stays_live_when_the_data_directory_is_missing(tmp_path):
    create_app, Settings = _web()
    from fastapi.testclient import TestClient

    with TestClient(create_app(Settings(data_dir=str(tmp_path / "absent")))) as client:
        health = client.get("/health")
        assert health.status_code == 200 and health.json()["data_ready"] is False
        ready = client.get("/ready/existing-data")
        assert ready.status_code == 503
        assert "data directory not found" in ready.json()["problems"][0]


def test_ready_for_a_complete_dataset(data_dir):
    create_app, Settings = _web()
    from fastapi.testclient import TestClient

    with TestClient(create_app(Settings(data_dir=str(data_dir)))) as client:
        ready = client.get("/ready/existing-data")
        assert ready.status_code == 200
        payload = ready.json()
        assert payload["status"] == "ready" and payload["problems"] == []
        assert payload["wells_loaded"] >= 1
        assert {s["status"] for s in payload["sources"]} == {"loaded"}
        assert client.get("/health").json()["data_ready"] is True


def test_integration_fixture_is_a_ready_dataset_with_the_wells_ci_exercises(tmp_path):
    """``scripts/make_integration_fixture.py`` backs the frontend integration
    suite in CI; it must stay ready and keep the properties that suite checks."""
    pytest.importorskip("openpyxl")
    import importlib.util
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / "scripts" / "make_integration_fixture.py"
    spec = importlib.util.spec_from_file_location("make_integration_fixture", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.write_fixture(tmp_path)

    readiness = api.data_readiness(tmp_path)
    assert readiness["ready"] is True
    assert {s["status"] for s in readiness["sources"]} == {"loaded"}
    records = {r.canonical_id: r for r in api.load_records(tmp_path)}
    assert set(records) == {"SALUZZO|1", "CRESCENTINO|1"}
    assert records["SALUZZO|1"].temperature_k.is_present
    assert not records["CRESCENTINO|1"].temperature_k.is_present
    # Like the real sources: no datum stated, so the approved model stays UNAVAILABLE.
    assert all(r.depth_datum.value == "unknown" for r in records.values())
