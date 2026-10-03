"""Opt-in abuse controls for a public, single-process deployment.

``CCS_RATE_LIMIT_PER_MINUTE`` caps POST requests per client per minute and
``CCS_MAX_CONCURRENT_EVALUATIONS`` caps simultaneous Monte Carlo runs. Both
are off by default, so local use and the test suite are unaffected; a public
deployment turns them on (deploy/public-demo.env).
"""

from __future__ import annotations

import threading

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from ccs_screen import assessment as A  # noqa: E402
from ccs_screen.web.app import create_app  # noqa: E402
from ccs_screen.web.settings import Settings  # noqa: E402


def _doc() -> dict:
    return A.examples_document()


def _client(tmp_path, **settings) -> TestClient:
    return TestClient(create_app(Settings(data_dir=str(tmp_path / "none"), **settings)))


def test_limits_are_off_by_default(tmp_path):
    settings = Settings.from_env({})
    assert settings.rate_limit_per_minute == 0 and settings.max_concurrent_evaluations == 0
    with _client(tmp_path) as c:
        for _ in range(30):
            assert c.post("/assessments/validate", json={"document": _doc()}).status_code == 200


def test_settings_read_the_environment():
    s = Settings.from_env({"CCS_RATE_LIMIT_PER_MINUTE": "20", "CCS_MAX_CONCURRENT_EVALUATIONS": "2"})
    assert s.rate_limit_per_minute == 20 and s.max_concurrent_evaluations == 2
    for bad in ({"CCS_RATE_LIMIT_PER_MINUTE": "-1"}, {"CCS_MAX_CONCURRENT_EVALUATIONS": "-3"}):
        with pytest.raises(ValueError):
            Settings.from_env(bad)


def test_rate_limit_answers_429_with_retry_after(tmp_path):
    with _client(tmp_path, rate_limit_per_minute=3) as c:
        codes = [c.post("/assessments/validate", json={"document": _doc()}).status_code
                 for _ in range(4)]
        assert codes == [200, 200, 200, 429]
        refused = c.post("/assessments/evaluate", json={"document": _doc(), "samples": 10})
        assert refused.status_code == 429
        assert int(refused.headers["retry-after"]) >= 1
        body = refused.json()
        assert body["type"] == "RateLimited" and "per minute" in body["error"]
        # Reads, liveness and readiness are never rate limited.
        assert c.get("/ready").status_code == 200
        assert c.get("/health").status_code == 200
        assert c.get("/assessments/examples").status_code == 200


def test_rate_limit_is_per_client(tmp_path):
    with _client(tmp_path, rate_limit_per_minute=1) as c:
        first = {"x-forwarded-for": "ignored"}  # TestClient's peer address is what counts
        assert c.post("/assessments/validate", json={"document": _doc()}, headers=first).status_code == 200
        assert c.post("/assessments/validate", json={"document": _doc()}).status_code == 429
    limiter_app = create_app(Settings(data_dir=str(tmp_path / "none"), rate_limit_per_minute=1))
    with TestClient(limiter_app, client=("203.0.113.1", 1000)) as a, \
            TestClient(limiter_app, client=("203.0.113.2", 1000)) as b:
        assert a.post("/assessments/validate", json={"document": _doc()}).status_code == 200
        assert b.post("/assessments/validate", json={"document": _doc()}).status_code == 200
        assert a.post("/assessments/validate", json={"document": _doc()}).status_code == 429


def test_concurrency_cap_refuses_a_second_simultaneous_evaluation(tmp_path, monkeypatch):
    started, release = threading.Event(), threading.Event()
    real = A.evaluate_document

    def slow(*args, **kwargs):
        started.set()
        release.wait(10)
        return real(*args, **kwargs)

    monkeypatch.setattr(A, "evaluate_document", slow)
    with _client(tmp_path, max_concurrent_evaluations=1) as c:
        results: list[int] = []
        worker = threading.Thread(target=lambda: results.append(
            c.post("/assessments/evaluate", json={"document": _doc(), "samples": 10}).status_code))
        worker.start()
        assert started.wait(10)
        busy = c.post("/assessments/evaluate", json={"document": _doc(), "samples": 10})
        assert busy.status_code == 503
        assert busy.json()["type"] == "ServerBusy" and int(busy.headers["retry-after"]) >= 1
        # Cheap endpoints are not held back by a running evaluation.
        assert c.post("/assessments/validate", json={"document": _doc()}).status_code == 200
        release.set()
        worker.join(20)
        assert results == [200]
        assert c.post("/assessments/evaluate", json={"document": _doc(), "samples": 10}).status_code == 200


def test_limits_are_reported_in_the_contract(tmp_path):
    with _client(tmp_path, rate_limit_per_minute=12, max_concurrent_evaluations=2) as c:
        limits = c.get("/assessments/contract").json()["deployment_limits"]
    assert limits == {"post_requests_per_minute_per_client": 12, "concurrent_evaluations": 2}


def test_a_browser_on_the_allowed_origin_can_read_retry_after(tmp_path):
    origin = "https://imansgh.github.io"
    with _client(tmp_path, rate_limit_per_minute=1, cors_origins=(origin,)) as c:
        headers = {"Origin": origin}
        assert c.post("/assessments/validate", json={"document": _doc()}, headers=headers).status_code == 200
        refused = c.post("/assessments/validate", json={"document": _doc()}, headers=headers)
    assert refused.status_code == 429
    assert refused.headers["access-control-allow-origin"] == origin
    assert "retry-after" in refused.headers["access-control-expose-headers"].lower()
