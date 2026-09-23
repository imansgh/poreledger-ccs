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
Deliberately not implemented. Doing it properly needs shared state across
workers (Redis or similar), and an in-process counter would be wrong the moment
a second worker starts -- it would give a false sense of protection. Rate
limiting belongs at the reverse proxy or API gateway. What *is* enforced here:
a request-body cap, and MAX_SAMPLES bounding CPU per request.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable

from fastapi import Body, FastAPI, Path, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ccs_screen import api
from ccs_screen.ingest.scenario import BUILTIN_SCENARIOS
from ccs_screen.web.schemas import (
    ErrorResponse,
    HealthResponse,
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
Scenario-based CO2 storage screening over normalized Italian well data.

**Nothing this API returns is a site-specific storage estimate.** Every result
carries an `interpretation` block stating that it is a scenario-based screening
capacity, not a certified or proven resource.

`area_m2` and `thickness_m` have no source data and no literature range. They
are **required caller inputs with no defaults**, and are never inferred from
licence boundaries, concession polygons, well spacing, a radius around a well,
or gross stratigraphic thickness.

Error mapping: `400` for a rejected domain request (`ApiError`), `404` for an
unknown well, `413` for an oversized body, `422` for a schema violation
(unknown field, wrong type, out-of-range `samples`).

Only built-in scenario names are accepted over HTTP; a filesystem path is not.
"""

_ERRORS: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Rejected request"},
    404: {"model": ErrorResponse, "description": "Unknown well"},
}


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized JSON bodies before they are parsed.

    Checks the declared Content-Length, and also counts bytes for chunked
    requests that declare no length -- otherwise the cap is trivially bypassed.
    """

    def __init__(self, app: Any, max_bytes: int) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: Callable) -> Any:
        declared = request.headers.get("content-length")
        if declared is not None:
            try:
                if int(declared) > self.max_bytes:
                    return _error_response(413, "request body too large", "PayloadTooLarge",
                                           f"limit is {self.max_bytes} bytes")
            except ValueError:
                return _error_response(400, "invalid Content-Length header", "ApiError")
        elif request.method in ("POST", "PUT", "PATCH"):
            body = await request.body()
            if len(body) > self.max_bytes:
                return _error_response(413, "request body too large", "PayloadTooLarge",
                                       f"limit is {self.max_bytes} bytes")
        return await call_next(request)


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
                    detail: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": error, "type": type_, "detail": detail},
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application. A factory so tests can inject settings."""
    config = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # Warm the normalization cache so the first request does not pay for
        # reading a workbook and three CSVs. A missing data directory must not
        # stop the process starting; /health surfaces it instead.
        if config.warm_cache_on_startup:
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
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=config.max_body_bytes)

    if config.cors_enabled:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(config.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type"],
            max_age=600,
        )

    # -- error mapping -------------------------------------------------------
    # UnknownWellError subclasses ApiError, so it must be registered first;
    # Starlette dispatches on the most specific registered class.

    @app.exception_handler(api.UnknownWellError)
    def _unknown_well(request: Request, exc: api.UnknownWellError) -> JSONResponse:
        return _error_response(404, str(exc), "UnknownWellError")

    @app.exception_handler(api.ApiError)
    def _api_error(request: Request, exc: api.ApiError) -> JSONResponse:
        return _error_response(400, str(exc), "ApiError")

    # -- endpoints -----------------------------------------------------------
    # All sync `def`: FastAPI runs them in a threadpool, keeping the event loop
    # free during CPU-bound Monte Carlo work.

    @app.get("/health", response_model=HealthResponse, tags=["meta"])
    def health() -> dict[str, Any]:
        """Liveness plus enough context to confirm the data actually loaded."""
        wells = api.load_records(config.data_dir)
        return {
            "status": "ok",
            "wells_loaded": len(wells),
            "data_dir": config.data_dir,
            "scenario_default": api.DEFAULT_SCENARIO,
            "limits": api.REQUEST_LIMITS,
        }

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

        A well that cannot be screened returns 200 with ``status: "blocked"``
        and the reasons; that is an outcome, not an error.
        """
        return api.screen_well(
            well_id,
            user_inputs=request.user_inputs.model_dump(),
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
        """What each available temperature method implies for capacity."""
        return api.compare_temperature_methods(
            well_id,
            user_inputs=request.user_inputs.model_dump(),
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
        samples: int = Query(200, ge=api.MIN_SAMPLES, le=api.MAX_SAMPLES),
    ) -> dict[str, Any]:
        """Fleet-level completeness counts, with the states kept distinct.

        No user inputs, so this reports what the data alone supports: zero
        screenable wells.
        """
        return api.screening_funnel(scenario=resolve_scenario_name(scenario),
                                    data_dir=config.data_dir, samples=samples)

    return app


app = create_app()
