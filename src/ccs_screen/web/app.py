"""FastAPI application over the screening API.

This module translates HTTP to :mod:`ccs_screen.api` and does nothing else. It
adds no science, no defaults, and no interpretation of its own -- the payloads
it returns are the Python API's dicts, passed through.

Concurrency
-----------
Every handler is a plain ``def``, not ``async def``. Screening is CPU-bound and
synchronous (up to ~0.33 s at MAX_SAMPLES), so FastAPI runs these in its
threadpool and the event loop keeps serving. An ``async def`` here would block
the loop for the duration of a Monte Carlo run and stall every other request.

Rate limiting
-------------
Always enforced: a request-body cap, and per-request computation bounds
(MAX_SAMPLES, at most MAX_TOTAL_SAMPLES realisations per assessment request).

Opt-in, for a public **single-process** deployment (both off by default):
``CCS_RATE_LIMIT_PER_MINUTE`` caps POST requests per client address, and
``CCS_MAX_CONCURRENT_EVALUATIONS`` caps simultaneous Monte Carlo runs (503
instead of queueing). Both are in-process state: with several workers or
instances each counts separately, so a scaled deployment needs limits at the
reverse proxy or API gateway (shared state such as Redis) instead. Behind a
proxy the client address is the forwarded one only when uvicorn trusts the
proxy (``--proxy-headers`` with ``FORWARDED_ALLOW_IPS``).
"""

from __future__ import annotations

import math
import threading
import time
from collections import OrderedDict, deque
from contextlib import asynccontextmanager, contextmanager
from typing import Any, AsyncIterator, Callable, Iterator

from fastapi import Body, FastAPI, Path, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from ccs_screen import api, assessment
from ccs_screen.ingest.scenario import BUILTIN_SCENARIOS
from ccs_screen.web.schemas import (
    AssessmentParseRequest,
    AssessmentRequest,
    EngineReadinessResponse,
    ErrorResponse,
    HealthResponse,
    ReadinessResponse,
    ScreenRequest,
    ScreenResponse,
    TemperatureRequest,
    TemperatureResponse,
    WellSummary,
)
from ccs_screen.web.settings import Settings

API_TITLE = "CCS screening API"
API_VERSION = "0.2.0"
API_DESCRIPTION = """
Scenario-based CO2 storage screening of **your own well or site data**
(`/assessments/*`, schema `ccs-assessment/1`), evaluated by the approved model
with no dataset on the server. Optionally, normalized existing well data
(`/wells/*`) when a dataset is configured. `/ready` is engine readiness;
`/ready/existing-data` is the optional dataset's readiness.

**Nothing this API returns is a site-specific storage estimate.** Every result
carries an `interpretation` block stating that it is a scenario-based screening
capacity, not a certified or proven resource.

**Approved model** (`literature-screening-v1`, the default): the owner-approved
Phase 13 Model Contract. The caller supplies `area_m2` and the
storage-assessment interval `z_top`, `z_base` (depth below ground level in the
well's `depth_m` datum); `h_g = z_base - z_top` is derived and `thickness_m` is
rejected. Both named water-level scenarios, `GROUND_REFERENCE` and
`SEA_LEVEL_SENSITIVITY`, are always evaluated, each with its own
`validation_status` (`VALIDATED`, `OUTSIDE_VALIDATED_ENVELOPE`, `UNAVAILABLE`)
and diagnostics. A well whose depth reference is not established returns
`UNAVAILABLE`.

**Legacy scenarios** (`conservative`, `central`, `sensitivity`, `none`) keep
their inputs (`area_m2`, `thickness_m`) and behaviour and are labelled
`validation_status: NOT_VALIDATED`, as is the temperature-method comparison.

None of the caller inputs has source data or a literature range. They are
**required, with no defaults**, and are never inferred from licence boundaries,
concession polygons, well spacing, a radius around a well, total depth,
stratigraphic units or gross stratigraphic thickness.

`GET /health` is liveness: it answers `200` with `status: "ok"` whenever the
process is serving, and reports `data_ready`. `GET /ready` is data readiness:
`200` when every required source loaded and at least one well was normalized,
otherwise `503` with the missing or unreadable sources and problems. A data
endpoint called while a required source is missing or unreadable answers `503`
(`DatasetNotReadyError`) with the failed sources in `detail`.

Error mapping: `400` for a rejected domain request (`ApiError`), `404` for an
unknown well, `413` for an oversized body, `503` when a required data source
is missing or unreadable, `422` for a schema violation
(unknown field, wrong type, out-of-range `samples`, a non-finite number such as
`NaN` or `Infinity`). Every error, including `422`, uses the envelope
`{error, type, detail}`; on a `422`, `detail` is the list of field errors.

Only built-in scenario names are accepted over HTTP; a filesystem path is not.

**Synthetic demo dataset.** When `CCS_DATA_DIR` points at the bundled demo
(`demo/data`), every well is fictional. `/health`, `/ready` and every data
response carry `dataset.synthetic: true`, well summaries carry `synthetic:
true`, and every interpretation block leads with the
`synthetic_demo_dataset` warning. Nothing from the demo describes a real site.
"""

_ERRORS: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Rejected request"},
    404: {"model": ErrorResponse, "description": "Unknown well"},
    503: {"model": ErrorResponse, "description": "Dataset not ready"},
}


class _BodyTooLarge(Exception):
    """Raised from the wrapped ``receive`` to stop the app reading further."""


class BodySizeLimitMiddleware:
    """Reject oversized request bodies without buffering them.

    A pure ASGI middleware. A declared Content-Length over the cap is refused
    before any body is read. Independently of the header, the bytes actually
    received are counted chunk by chunk as the application reads them: the
    moment the running total passes the cap, the 413 is sent and reading
    stops, so a chunked (or mis-declared) body is never consumed beyond
    ``max_bytes`` plus one chunk. Requests within the cap pass through
    untouched.
    """

    def __init__(self, app: Any, max_bytes: int,
                 path_limits: dict[str, int] | None = None) -> None:
        self.app = app
        self.default_max_bytes = max_bytes
        #: Larger caps for path prefixes that carry user data files.
        self.path_limits = dict(path_limits or {})

    def _limit_for(self, path: str) -> int:
        for prefix, limit in self.path_limits.items():
            if path.startswith(prefix):
                return limit
        return self.default_max_bytes

    def _too_large(self, limit: int) -> JSONResponse:
        return _error_response(413, "request body too large", "PayloadTooLarge",
                               f"limit is {limit} bytes")

    async def __call__(self, scope: dict[str, Any], receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self._limit_for(scope.get("path", ""))

        for name, value in scope.get("headers", ()):
            if name.lower() == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = -1
                if declared < 0:
                    await _error_response(400, "invalid Content-Length header",
                                          "ApiError")(scope, receive, send)
                    return
                if declared > limit:
                    await self._too_large(limit)(scope, receive, send)
                    return
                break

        received = 0
        rejected = False
        response_started = False

        async def guarded_send(message: dict[str, Any]) -> None:
            nonlocal response_started
            if rejected:
                # The 413 has been sent; drop whatever the app answers to
                # the aborted read (e.g. FastAPI's "error parsing the body").
                return
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        async def counting_receive() -> dict[str, Any]:
            nonlocal received, rejected
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    if not response_started:
                        rejected = True
                        await self._too_large(limit)(scope, receive, send)
                    raise _BodyTooLarge
            return message

        try:
            await self.app(scope, counting_receive, guarded_send)
        except _BodyTooLarge:
            if not rejected:
                raise


class RateLimitMiddleware:
    """At most ``per_minute`` POST requests per client address per rolling minute.

    Pure ASGI, in-process (see the module docstring). Reads (GET), CORS
    preflights and liveness/readiness are never limited. The refusal is a 429
    with ``Retry-After``. Memory is bounded: at most ``max_clients`` addresses
    are tracked, the least recently seen are forgotten first.
    """

    WINDOW_S = 60.0

    def __init__(self, app: Any, per_minute: int, max_clients: int = 10_000,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.app = app
        self.per_minute = per_minute
        self.max_clients = max_clients
        self.clock = clock
        self.hits: OrderedDict[str, deque[float]] = OrderedDict()

    async def __call__(self, scope: dict[str, Any], receive: Callable, send: Callable) -> None:
        if scope["type"] != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return
        client = (scope.get("client") or ("unknown", 0))[0]
        now = self.clock()
        window = self.hits.pop(client, None) or deque()
        while window and now - window[0] >= self.WINDOW_S:
            window.popleft()
        if len(window) >= self.per_minute:
            self.hits[client] = window
            retry = max(1, math.ceil(self.WINDOW_S - (now - window[0])))
            response = _error_response(
                429, f"too many requests: at most {self.per_minute} per minute per client",
                "RateLimited", f"retry after {retry} s")
            response.headers["Retry-After"] = str(retry)
            await response(scope, receive, send)
            return
        window.append(now)
        self.hits[client] = window  # most recently seen last
        while len(self.hits) > self.max_clients:
            self.hits.popitem(last=False)
        await self.app(scope, receive, send)


class _ServerBusy(Exception):
    """Raised when the evaluation concurrency cap is reached."""


def resolve_scenario_name(name: str) -> str:
    """Accept only a built-in scenario name over HTTP.

    ``ccs_screen.api`` also accepts a path to a scenario JSON file, which is
    right for the CLI and for Python callers. Exposing that to HTTP would let a
    request name any path on the server: even though the loader never returns
    file contents, it is an existence-and-parseability oracle, and on a host
    where an attacker can write a JSON file it becomes scenario injection.

    File-based scenarios remain available through the Python API and the CLI.

    Both alias keys (``central``) and canonical names (``central-placeholder``,
    as ``/scenarios`` reports them) are accepted; either resolves to an alias
    key, so ``load_scenario`` never sees anything that could be a path.
    """
    key = str(name).strip().lower()
    if key in BUILTIN_SCENARIOS:
        return key
    for alias, scenario in BUILTIN_SCENARIOS.items():
        if scenario.name.lower() == key:
            return alias
    accepted = sorted(set(BUILTIN_SCENARIOS) | {s.name for s in BUILTIN_SCENARIOS.values()})
    raise api.ApiError(
        f"unknown scenario {name!r}. Over HTTP only built-in scenarios are "
        f"accepted: {', '.join(accepted)}."
    )


def _error_response(status: int, error: str, type_: str,
                    detail: str | list[Any] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": error, "type": type_, "detail": detail},
    )


#: How a non-finite float is echoed back in an error, spelled as the JSON
#: extension (Python's json module) that let it into the request.
_NON_FINITE_NAMES = {"nan": "NaN", "inf": "Infinity", "-inf": "-Infinity"}


def _json_safe(value: Any) -> Any:
    """Make a validation-error echo encodable as strict JSON.

    A rejected ``NaN`` or ``Infinity`` is echoed in the error's ``input``; the
    response encoder refuses non-finite floats, which turned the 422 into a
    plain-text 500. They are echoed as their names instead. This touches the
    error report only -- the request was already rejected.
    """
    if isinstance(value, float) and not math.isfinite(value):
        return _NON_FINITE_NAMES[repr(value)]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application. A factory so tests can inject settings."""
    config = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # Warm the normalization cache so the first request does not pay for
        # reading a workbook and three CSVs. A missing data directory must not
        # stop the process starting; /ready surfaces it instead.
        if config.warm_cache_on_startup:
            # The engine self-check never raises for an expected failure; it
            # reports it at /ready. The optional existing dataset may be absent.
            assessment.engine_readiness()
            try:
                api.load_records(config.data_dir)
            except api.ApiError:
                pass
        yield

    app = FastAPI(
        lifespan=lifespan,
        title=API_TITLE,
        version=API_VERSION,
        description=API_DESCRIPTION,
        docs_url="/docs" if config.docs_enabled else None,
        redoc_url="/redoc" if config.docs_enabled else None,
    )
    app.state.settings = config

    # Body cap first so an oversized request is refused before CORS work.
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=config.max_body_bytes,
                       path_limits={"/assessments": config.max_assessment_body_bytes})
    # Added before CORS, so CORS wraps it and a browser can read the 429.
    if config.rate_limit_per_minute:
        app.add_middleware(RateLimitMiddleware, per_minute=config.rate_limit_per_minute)

    evaluation_slots = (threading.BoundedSemaphore(config.max_concurrent_evaluations)
                        if config.max_concurrent_evaluations else None)

    @contextmanager
    def evaluation_slot() -> Iterator[None]:
        """Hold one Monte Carlo slot, or refuse at once when all are taken."""
        if evaluation_slots is None:
            yield
            return
        if not evaluation_slots.acquire(blocking=False):
            raise _ServerBusy
        try:
            yield
        finally:
            evaluation_slots.release()

    if config.cors_enabled:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(config.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type"],
            # Lets the website read how long to wait after a 429 or busy 503.
            expose_headers=["Retry-After"],
            max_age=600,
        )

    # -- error mapping -------------------------------------------------------
    # UnknownWellError and DatasetNotReadyError subclass ApiError, so they are
    # registered first; Starlette dispatches on the most specific class.

    @app.exception_handler(api.DatasetNotReadyError)
    def _dataset_not_ready(request: Request, exc: api.DatasetNotReadyError) -> JSONResponse:
        failed = [s.to_dict() for s in exc.sources if s.required and not s.ok]
        return _error_response(503, str(exc), "DatasetNotReadyError", failed)

    @app.exception_handler(api.UnknownWellError)
    def _unknown_well(request: Request, exc: api.UnknownWellError) -> JSONResponse:
        return _error_response(404, str(exc), "UnknownWellError")

    @app.exception_handler(assessment.AssessmentError)
    def _assessment_error(request: Request, exc: assessment.AssessmentError) -> JSONResponse:
        # Field paths and messages only; nothing submitted is logged.
        return _error_response(422, str(exc), "AssessmentValidationError", exc.problems)

    @app.exception_handler(_ServerBusy)
    def _server_busy(request: Request, exc: _ServerBusy) -> JSONResponse:
        response = _error_response(
            503, "the server is busy with other calculations; try again shortly", "ServerBusy",
            f"at most {config.max_concurrent_evaluations} calculations run at once")
        response.headers["Retry-After"] = "5"
        return response

    @app.exception_handler(api.ApiError)
    def _api_error(request: Request, exc: api.ApiError) -> JSONResponse:
        return _error_response(400, str(exc), "ApiError")

    @app.exception_handler(RequestValidationError)
    def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Same envelope as every other error. ``detail`` stays the list of
        # field errors (loc, msg, type, input) that FastAPI returns by default,
        # so clients parsing it are unaffected.
        errors = _json_safe(jsonable_encoder(exc.errors()))
        first = errors[0] if errors else {}
        where = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
        message = f"{where}: {first.get('msg')}" if where else str(first.get("msg", "invalid"))
        return _error_response(422, f"request validation failed: {message}",
                               "RequestValidationError", errors)

    @app.exception_handler(Exception)
    def _unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Never send a traceback or exception text to the client. Starlette
        # re-raises the exception after this response, so the server still
        # logs it; nothing is swallowed.
        return _error_response(500, "internal server error", "InternalServerError")

    # -- endpoints -----------------------------------------------------------
    # All sync `def`: FastAPI runs them in a threadpool, keeping the event loop
    # free during CPU-bound Monte Carlo work.

    @app.get("/health", response_model=HealthResponse, tags=["meta"])
    def health() -> dict[str, Any]:
        """Liveness: 200 whenever the process is serving, even with no data.

        ``engine_ready`` summarizes ``/ready`` (user assessments can be
        evaluated); ``data_ready`` summarizes ``/ready/existing-data`` (the
        optional well dataset is usable).
        """
        readiness = api.data_readiness(config.data_dir)
        return {
            "status": "ok",
            "engine_ready": assessment.engine_readiness()["ready"],
            "data_ready": readiness["ready"],
            "dataset": readiness["dataset"],
            "wells_loaded": readiness["wells_loaded"],
            "data_dir": config.data_dir,
            "scenario_default": api.DEFAULT_SCENARIO,
            "limits": api.REQUEST_LIMITS,
        }

    @app.get("/ready", response_model=EngineReadinessResponse, tags=["meta"],
             responses={503: {"model": EngineReadinessResponse,
                              "description": "Engine not ready"}})
    def ready() -> JSONResponse:
        """Engine readiness: 200 when user-supplied assessments can be evaluated.

        Does not depend on the optional existing well dataset, which is
        reported under ``existing_data`` for information only.
        """
        engine = assessment.engine_readiness()
        existing = api.data_readiness(config.data_dir)
        body = {
            "status": "ready" if engine["ready"] else "not_ready",
            "engine": engine,
            "existing_data": {"ready": existing["ready"], "dataset": existing["dataset"],
                              "wells_loaded": existing["wells_loaded"],
                              "detail": "/ready/existing-data"},
        }
        return JSONResponse(status_code=200 if engine["ready"] else 503, content=body)

    @app.get("/ready/existing-data", response_model=ReadinessResponse, tags=["meta"],
             responses={503: {"model": ReadinessResponse, "description": "Data not ready"}})
    def ready_existing_data() -> JSONResponse:
        """Optional existing-data readiness: 200 when every required source
        loaded and at least one well was normalized; 503 with the problems
        otherwise. Only the /wells and /funnel endpoints need it.

        A missing optional source is listed in ``sources`` but is not a
        failure. Readiness concerns the software's inputs only: approved
        results can still be ``UNAVAILABLE`` for scientific reasons.
        """
        readiness = api.data_readiness(config.data_dir)
        body = {
            "status": "ready" if readiness["ready"] else "not_ready",
            "dataset": readiness["dataset"],
            "wells_loaded": readiness["wells_loaded"],
            "data_dir": config.data_dir,
            "sources": readiness["sources"],
            "problems": readiness["problems"],
        }
        return JSONResponse(status_code=200 if readiness["ready"] else 503, content=body)

    # -- user assessments -------------------------------------------------------

    @app.get("/assessments/contract", tags=["assessments"])
    def assessment_contract() -> dict[str, Any]:
        """The input schema: fields, units, conventions, methods and limits.

        ``deployment_limits`` reports this server's opt-in abuse controls
        (0 = off): POST requests per client per minute, simultaneous runs.
        """
        return {**assessment.input_contract(), "deployment_limits": {
            "post_requests_per_minute_per_client": config.rate_limit_per_minute,
            "concurrent_evaluations": config.max_concurrent_evaluations,
        }}

    @app.get("/assessments/examples", tags=["assessments"])
    def assessment_examples() -> dict[str, Any]:
        """The synthetic examples as a ccs-assessment/1 document (all fictional)."""
        return assessment.examples_document()

    @app.get("/assessments/files/{name}", tags=["assessments"], responses=_ERRORS)
    def assessment_file(name: str = Path(..., max_length=64)) -> Response:
        """Download a template or the synthetic examples (JSON or CSV)."""
        try:
            content = assessment.data_file(name)
        except KeyError:
            raise api.UnknownWellError(
                f"no file {name!r}; available: {', '.join(assessment.DATA_FILES)}") from None
        disposition = 'attachment; filename="' + name + '"'
        return Response(content=content, media_type=assessment.DATA_FILES[name],
                        headers={"Content-Disposition": disposition})

    @app.post("/assessments/parse", tags=["assessments"])
    def parse_assessments(request: AssessmentParseRequest = Body(...)) -> dict[str, Any]:
        """Parse an uploaded JSON or CSV file into an editable document.

        Nothing is evaluated. Problems carry field paths and, for CSV, row
        numbers. The content is treated as data only and is not stored.
        ``import_blocked`` marks a partial document that must not be
        evaluated; see ``assessment.parse_upload``.
        """
        return assessment.parse_upload(request.format, request.content)

    @app.post("/assessments/validate", tags=["assessments"])
    def validate_assessments(request: AssessmentRequest = Body(...)) -> dict[str, Any]:
        """Validate and normalize without evaluating."""
        normalized, problems = assessment.validate_document(request.document)
        return {"valid": not any(p["severity"] == "error" for p in problems),
                "problems": problems,
                "assessments": [a.inputs_dict() for a in normalized]}

    @app.post("/assessments/evaluate", tags=["assessments"],
              responses={422: {"model": ErrorResponse, "description": "Invalid input"}})
    def evaluate_assessments(request: AssessmentRequest = Body(...)) -> dict[str, Any]:
        """Validate, then evaluate every assessment with the approved model.

        The same engine path as /wells/{id}/screen. No well dataset is needed
        and nothing is stored. Input errors return 422 with every problem in
        ``detail``.
        """
        with evaluation_slot():
            return assessment.evaluate_document(request.document, samples=request.samples,
                                                seed=request.seed)

    # -- existing well data (optional) ------------------------------------------

    @app.get("/wells", response_model=list[WellSummary], tags=["wells"])
    def list_wells() -> list[dict[str, Any]]:
        """Every normalized well."""
        return api.list_wells(config.data_dir)

    @app.get("/wells/{well_id:path}/inputs", responses=_ERRORS, tags=["wells"])
    def well_inputs(
        well_id: str = Path(..., description="Canonical id, e.g. SALUZZO|1"),
        scenario: str = Query(api.DEFAULT_SCENARIO, max_length=200),
    ) -> dict[str, Any]:
        """What the caller must supply before this well can be screened."""
        return api.required_user_inputs(
            well_id, scenario=resolve_scenario_name(scenario), data_dir=config.data_dir
        )

    @app.get("/wells/{well_id:path}", responses=_ERRORS, tags=["wells"])
    def get_well(well_id: str = Path(..., description="Canonical id")) -> dict[str, Any]:
        """One well's normalized record with full field-level provenance."""
        return api.get_well(well_id, data_dir=config.data_dir)

    @app.post("/wells/{well_id:path}/screen", response_model=ScreenResponse,
              responses=_ERRORS, tags=["screening"])
    def screen(
        well_id: str = Path(..., description="Canonical id"),
        request: ScreenRequest = Body(...),
    ) -> dict[str, Any]:
        """Screen a well under a scenario plus caller-supplied inputs.

        The approved model returns ``status: "evaluated"`` with both named
        water-level scenarios and their statuses; a legacy scenario returns its
        NOT_VALIDATED result. A well that cannot be screened returns 200 with
        ``status: "blocked"`` and the reasons; that is an outcome, not an error.
        Only the inputs actually sent are passed on (``exclude_none``), so the
        API sees exactly what the caller supplied.
        """
        with evaluation_slot():
            return api.screen_well(
                well_id,
                user_inputs=request.user_inputs.model_dump(exclude_none=True),
                scenario=resolve_scenario_name(request.scenario),
                data_dir=config.data_dir,
                samples=request.samples,
                seed=request.seed,
            )

    @app.post("/wells/{well_id:path}/temperature", response_model=TemperatureResponse,
              responses=_ERRORS, tags=["screening"])
    def temperature(
        well_id: str = Path(..., description="Canonical id"),
        request: TemperatureRequest = Body(...),
    ) -> dict[str, Any]:
        """What each available temperature method implies for capacity.

        A NOT_VALIDATED legacy diagnostic; it takes the legacy inputs
        ``area_m2`` and ``thickness_m``.
        """
        with evaluation_slot():
            return api.compare_temperature_methods(
                well_id,
                user_inputs=request.user_inputs.model_dump(exclude_none=True),
                scenario=resolve_scenario_name(request.scenario),
                data_dir=config.data_dir,
                samples=request.samples,
                seed=request.seed,
            )

    @app.get("/scenarios", responses=_ERRORS, tags=["meta"])
    def scenarios() -> list[dict[str, Any]]:
        """Built-in scenarios with their evidence posture."""
        return api.list_scenarios()

    @app.get("/funnel", responses=_ERRORS, tags=["meta"])
    def funnel(
        scenario: str = Query(api.DEFAULT_SCENARIO, max_length=200),
        samples: int = Query(
            200, ge=api.MIN_SAMPLES, le=api.MAX_SAMPLES,
            description=("Accepted and range-checked for backwards compatibility only. "
                         "The funnel runs no Monte Carlo, so this has no effect."),
        ),
    ) -> dict[str, Any]:
        """Fleet-level counts, with the states kept distinct.

        No user inputs. Under the approved model this reports depth-reference
        readiness (an approved result needs a per-well interval); under a
        legacy scenario it is the NOT_VALIDATED completeness funnel. No
        capacity is computed on either path.
        """
        return api.screening_funnel(scenario=resolve_scenario_name(scenario),
                                    data_dir=config.data_dir, samples=samples)

    return app


app = create_app()
