# HTTP API

FastAPI wrapper over `ccs_screen.api`. It translates HTTP to those calls and
does nothing else: no science, no defaults, no interpretation of its own.

```bash
pip install -e ".[ingest,web]"
uvicorn ccs_screen.web.app:app --reload
# interactive docs at /docs
```

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | liveness, well count, published limits |
| GET | `/wells` | every normalized well |
| GET | `/wells/{well_id}` | one well, full field-level provenance |
| GET | `/wells/{well_id}/inputs` | what the caller must supply |
| GET | `/scenarios` | built-in scenarios and their evidence posture |
| GET | `/funnel` | fleet completeness counts |
| POST | `/wells/{well_id}/screen` | screen a well |
| POST | `/wells/{well_id}/temperature` | compare temperature methods |

Well ids contain a `|` (e.g. `SALUZZO|1`), so the routes use a `:path`
converter. `/wells/{id}/inputs` is registered before `/wells/{id}` so the
greedy converter does not swallow it.

## Required inputs

`area_m2` and `thickness_m` are **required, with no defaults**. They have no
source data and no literature range, and are never inferred from licence
boundaries, concession polygons, administrative boundaries, well spacing, a
radius around a well, or gross stratigraphic thickness.

Request models use `extra="forbid"`, so an unrecognised field is rejected
rather than ignored. That is what stops `temperature_k` being slipped in as an
assumption: temperature is source-derived or the well stays blocked.

## Status codes

| Code | Meaning |
| --- | --- |
| 200 | Served. **Includes `status: "blocked"`** -- a well that cannot be screened is an outcome, not an error |
| 400 | `ApiError` -- a valid-shaped request the domain refuses (e.g. unknown scenario) |
| 404 | `UnknownWellError` |
| 413 | Request body over the configured cap |
| 422 | Schema violation: unknown field, wrong type, out-of-range `samples` |

`UnknownWellError` subclasses `ApiError`, so its handler is registered first.

Errors share one envelope:

```json
{"error": "no well with id 'NOPE|9'", "type": "UnknownWellError", "detail": null}
```

## Limits

| Parameter | Min | Max | Default |
| --- | --- | --- | --- |
| `samples` | 1 | 50,000 | 2,000 |
| request body | - | 16 KiB (`CCS_MAX_BODY_BYTES`) | - |

`samples` is a `StrictInt`: `"2000"` and `2.0` are rejected rather than
coerced, and out-of-range values are rejected rather than clamped. The bound is
published in the OpenAPI schema and in `/health`.

## Configuration

| Variable | Default | Notes |
| --- | --- | --- |
| `CCS_DATA_DIR` | `data` | source directory |
| `CCS_CORS_ORIGINS` | *(empty)* | comma-separated; **no wildcard default** |
| `CCS_MAX_BODY_BYTES` | `16384` | |
| `CCS_WARM_CACHE` | `1` | normalize at startup |
| `CCS_DOCS` | `1` | set `0` to disable `/docs` and `/redoc` |

CORS is **off** until origins are named. A public demo that reflects any
`Origin` is a footgun, so an unset variable never widens access:

```bash
CCS_CORS_ORIGINS=http://localhost:3000 uvicorn ccs_screen.web.app:app
```

## Concurrency

Every handler is a plain `def`, not `async def`. Screening is CPU-bound and
synchronous (~0.33 s at `MAX_SAMPLES`), so FastAPI runs them in its threadpool
and the event loop keeps serving. An `async def` here would block the loop for
the duration of a Monte Carlo run. A test asserts no route handler is a
coroutine function.

The normalization cache is shared and protected by a double-checked lock, so a
cold-cache burst normalizes once rather than once per worker.

## Rate limiting

**Not implemented, deliberately.** Doing it properly needs state shared across
workers (Redis or similar); an in-process counter would be wrong the moment a
second worker starts and would give a false sense of protection. Rate limiting
belongs at the reverse proxy or API gateway.

What *is* enforced in-process: the request-body cap, and `MAX_SAMPLES` bounding
CPU per request.

## Response contract

Screening responses keep the disjoint partition -- each required input appears
in exactly one bucket, and the four together cover all six:

`source_derived_inputs` - `modelled_inputs` - `assumed_inputs` -
`user_supplied_inputs`

Every entry in `screening_inputs` carries `value`, `unit`, `provenance`,
`evidence_class`, `assumed`, `label` and, where they exist, `rationale`,
`author`, `derivation` and a structured `citation`.

`response_model` is typed at the top level but keeps these entries as open
mappings on purpose: FastAPI filters responses against the declared model, so an
over-tight schema would *silently delete* provenance. A test compares the HTTP
payload against the Python one key by key to prove nothing is dropped.

On a successful screen, the blocked-only fields (`reason`, `error`,
`missing_fields`, `missing_reasons`, `required_user_inputs`) serialise as
`null`. `scenario_based_capacity_mt` is always present -- `null` when blocked --
so a client reads the null rather than inferring it from absence.

## Example

```bash
curl -s -X POST http://localhost:8000/wells/SALUZZO%7C1/screen \
  -H 'Content-Type: application/json' \
  -d '{"user_inputs": {"area_m2": 8.0e7, "thickness_m": 35.0}, "samples": 2000}'
```

```json
{
  "status": "screened",
  "well_id": "SALUZZO|1",
  "interpretation": {
    "type": "scenario_based_capacity",
    "site_specific": false,
    "certified": false,
    "proven_resource": false,
    "warnings": [
      {"code": "scale_mismatch_basin_vs_closure", "severity": "advisory",
       "invalidates_result": false, "correction_applied": false}
    ]
  },
  "source_derived_inputs": ["temperature_k"],
  "modelled_inputs": ["pressure_pa"],
  "assumed_inputs": ["porosity", "storage_efficiency"],
  "user_supplied_inputs": ["area_m2", "thickness_m"],
  "scenario_based_capacity_mt": {"p10": 5.28, "p50": 11.24, "p90": 21.9}
}
```
