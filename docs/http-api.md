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
| GET | `/funnel` | approved model: depth-reference readiness; legacy scenario: completeness funnel (NOT_VALIDATED) |
| POST | `/wells/{well_id}/screen` | screen a well |
| POST | `/wells/{well_id}/temperature` | compare temperature methods (NOT_VALIDATED legacy diagnostic) |

Well ids contain a `|` (e.g. `SALUZZO|1`), so the routes use a `:path`
converter. `/wells/{id}/inputs` is registered before `/wells/{id}` so the
greedy converter does not swallow it.

## Two paths

| Scenario | Path | Inputs | Result |
| --- | --- | --- | --- |
| `literature-screening-v1` (default) | approved model (Phase 13 Model Contract) | `area_m2`, `z_top`, `z_base` | `status: "evaluated"`, both named water-level scenarios with statuses |
| `conservative`, `central`, `sensitivity`, `none` | legacy (owner decision O2) | `area_m2`, `thickness_m` | `status: "screened"`, `validation_status: "NOT_VALIDATED"` |

Every screening response carries `model_path` (`APPROVED_MODEL` or
`LEGACY_NOT_VALIDATED`). `GET /scenarios` reports each scenario's
`validation_status` (`APPROVED_MODEL` or `NOT_VALIDATED`) and
`required_user_inputs`, and `GET /wells/{id}/inputs` reports the inputs of the
path the requested scenario belongs to.

## Required inputs

On the approved model `area_m2`, `z_top` and `z_base` are **required, with no
defaults**. `z_top` and `z_base` bound the designated storage-assessment
interval, as depth below ground level in the same coordinate and datum as the
well's `depth_m` (`0 <= z_top < z_base`). The API derives `h_g = z_base -
z_top` and `z_state = (z_top + z_base) / 2`; there is no thickness input, and a
request carrying `thickness_m` is returned `blocked` with the reason.

On a legacy scenario `area_m2` and `thickness_m` are required, as before.

None of these has source data or a literature range, and none is ever inferred
from licence boundaries, concession polygons, administrative boundaries, well
spacing, a radius around a well, total depth, stratigraphic units or gross
stratigraphic thickness. `area_m2` is required by the request schema; the other
inputs depend on the scenario, so the API validates the combination and
returns `blocked` (200) naming what is missing or misplaced.

Request models use `extra="forbid"`, so an unrecognised field is rejected
rather than ignored. That is what stops `temperature_k` being slipped in as an
assumption: temperature is source-derived or the well stays blocked.

### Optional: `net_to_gross` (provenance only)

`user_inputs` may carry an optional `net_to_gross` block. On a legacy scenario
it declares the net-to-gross that `thickness_m` implies; on the approved model
it is `h_net / h_g` for the designated interval, a consistency/provenance check
only, reported in `net_to_gross_check` (with `0 < net_to_gross <= 1`,
`0 < h_net <= h_g` holds by construction). It is **recorded and reported only**:
it is not used in any calculation, never enters `screening_inputs`, is never an
assumption a scenario can supply, and is never inferred -- not from
`gross_thickness_m` and not from any record field. See
`docs/net-to-gross-semantics.md`.

```json
"net_to_gross": {
  "low": 0.30, "high": 0.55,                   // required, 0 < low <= high <= 1
  "net_criterion": "porosity_permeability",    // required when present
  "net_basis": "log_derived",                  // required when present
  "cutoff_note": "free text, <= 500 chars",    // optional
  "thickness_convention": "measured"           // optional: measured | tvd | tst
}
```

`net_criterion`: `porosity_permeability`, `porosity_only`, `permeability_only`,
`lithology_net_sand`, `flow_unit`, `unspecified`. `net_basis`: `log_derived`,
`core_derived`, `model_derived`, `analogue`, `assumed`, `unknown`. A block
without `net_criterion` and `net_basis`, with `low > high`, or with a bound
outside `(0, 1]` is rejected. Values outside CSLF's 0.25-0.75 are accepted.

On legacy paths the screen and temperature responses carry a `thickness_provenance` block with
`declared`, `net_to_gross_status` (`"declared"` or `"unknown -- not supplied by
the caller"`), the echoed `net_to_gross` (or `null`) and `used_in_calculation:
false`. When it is not declared, `interpretation.warnings` includes the advisory
`net_to_gross_not_declared`; a point value (`low == high`) earns
`net_to_gross_point_value`. The fleet funnel emits neither, and neither
applies to the approved model, where the gross-to-net reduction is represented
inside the storage efficiency by construction.

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

## Response contract: approved model

An evaluated approved response carries:

| Key | Content |
| --- | --- |
| `depth_reference` | the well's datum and whether it is established (only `ground_level` is usable) |
| `storage_interval` | `z_top_m`, `z_base_m`, and the derived `h_g_m`, `z_state_m` (`null` when the reference is not established) |
| `temperature_selection` | status, selected observation, eligible and excluded observations with reasons, diagnostics |
| `water_level_scenarios` | always `GROUND_REFERENCE` then `SEA_LEVEL_SENSITIVITY` |
| `systematic_effect` | baseline, the individual effect (`SEA_LEVEL_SENSITIVITY` vs `GROUND_REFERENCE`, a P50 difference only when both are `VALIDATED`), `multiplied_correction_factor: null` |
| `sampled_inputs` | porosity, brine density and storage efficiency priors with status, provenance and citations |
| `model_constants` | `P_atm`, `g`, EOS and envelope, conventions |

Each named scenario carries `validation_status`:

| Status | Meaning |
| --- | --- |
| `VALIDATED` | every realisation inside the validated EOS envelope; `capacity_mt` holds P10/P50/P90 |
| `OUTSIDE_VALIDATED_ENVELOPE` | at least one realisation outside 1-35 MPa (on `P_EOS`) or 280-400 K; `validated_percentiles: "BLOCKED"`, `capacity_mt: null`; `diagnostic_capacity_mt` may hold figures over every realisation, labelled `NOT_VALIDATED` |
| `UNAVAILABLE` | an input the contract requires is not available (depth reference, temperature, quota); no capacity |

plus `z_wl_m`, `z_state_m`, `pressure_eos_pa` (absolute, at the brine-density
bounds), `temperature_k`, `envelope` (counts per realisation;
`realisations_discarded: 0`) and `diagnostics` (`code`, `message`, detail).
Every ingested well currently has an `unknown` depth reference, so every real
well returns `UNAVAILABLE` with `DEPTH_REFERENCE_NOT_ESTABLISHED`.

The HTTP response model is a union discriminated by `model_path`, so neither
path acquires the other's fields; a test compares both HTTP payloads with the
Python ones key by key.

## Response contract: legacy scenarios

Legacy screening responses keep the disjoint partition -- each required input appears
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

They also carry `validation_status: "NOT_VALIDATED"` and the advisory
`not_validated_legacy_path` in `interpretation.warnings`.

On a successful legacy screen, the blocked-only fields (`reason`, `error`,
`missing_fields`, `missing_reasons`, `required_user_inputs`) serialise as
`null`. `scenario_based_capacity_mt` is always present -- `null` when blocked --
so a client reads the null rather than inferring it from absence.

### Percentiles and the uncertainty band

`p10`, `p50` and `p90` use the **statistical** convention: **P10 = low case,
P50 = median case, P90 = high case**. This is not the petroleum reserves
convention, in which P10 is the high case. Each reported capacity block (a
legacy `scenario_based_capacity_mt`, or an approved scenario's `capacity_mt`)
states this in `percentile_convention`. On the approved model the percentiles
are conditional on the declared model; they are not total accuracy and not
bounds on systematic bias.

The same block carries `uncertainty_band`: the P10-P90 interval is the model's
sampled uncertainty band -- P10 the lower and P90 the upper sampled case of the
Monte Carlo distribution. It does not necessarily contain systematic or model
bias. Systematic biases identified by the scientific validation audit lie
outside the Monte Carlo sampling uncertainty and may place the true value
outside the reported P10-P90 interval (audit Finding 12.5). The same statement
appears as the advisory `sampled_uncertainty_band_excludes_systematic_bias` in
`interpretation.warnings`. Both are disclosure only; no value is adjusted.

## Example: approved model

```bash
curl -s -X POST http://localhost:8000/wells/SALUZZO%7C1/screen \
  -H 'Content-Type: application/json' \
  -d '{"user_inputs": {"area_m2": 8.0e7, "z_top": 1400, "z_base": 1527}, "samples": 2000}'
```

```json
{
  "status": "evaluated",
  "model_path": "APPROVED_MODEL",
  "well_id": "SALUZZO|1",
  "depth_reference": {"depth_datum": "unknown", "status": "UNAVAILABLE", ...},
  "storage_interval": {"z_top_m": 1400.0, "z_base_m": 1527.0, "h_g_m": null,
                       "z_state_m": null, "status": "UNAVAILABLE", ...},
  "water_level_scenarios": [
    {"name": "GROUND_REFERENCE", "validation_status": "UNAVAILABLE",
     "validated_percentiles": "UNAVAILABLE", "capacity_mt": null,
     "diagnostics": [{"code": "DEPTH_REFERENCE_NOT_ESTABLISHED", ...}], ...},
    {"name": "SEA_LEVEL_SENSITIVITY", "validation_status": "UNAVAILABLE", ...}
  ],
  "systematic_effect": {"baseline": "GROUND_REFERENCE",
                        "multiplied_correction_factor": null, ...}
}
```

## Example: legacy scenario (NOT_VALIDATED)

```bash
curl -s -X POST http://localhost:8000/wells/SALUZZO%7C1/screen \
  -H 'Content-Type: application/json' \
  -d '{"user_inputs": {"area_m2": 8.0e7, "thickness_m": 35.0}, "scenario": "sensitivity", "samples": 2000}'
```

The response keeps the pre-contract shape below, with `model_path:
"LEGACY_NOT_VALIDATED"` and `validation_status: "NOT_VALIDATED"` added. (The
figures and the `pressure_pa` partition shown are those of the pre-contract
literature run, kept for illustration of the shape.)

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
       "invalidates_result": false, "correction_applied": false},
      {"code": "net_to_gross_not_declared", "severity": "advisory", ...},
      {"code": "sampled_uncertainty_band_excludes_systematic_bias",
       "severity": "advisory", ...}
    ]
  },
  "thickness_provenance": {"thickness_m": 35.0, "thickness_kind": "net_storage",
                           "declared": false, "net_to_gross": null,
                           "used_in_calculation": false, ...},
  "source_derived_inputs": ["temperature_k"],
  "modelled_inputs": ["pressure_pa"],
  "assumed_inputs": ["porosity", "storage_efficiency"],
  "user_supplied_inputs": ["area_m2", "thickness_m"],
  "scenario_based_capacity_mt": {
    "p10": 5.28, "p50": 11.24, "p90": 21.9,
    "percentile_convention": {"convention": "statistical", "p10": "low case -- ...",
                              "p50": "median case -- ...", "p90": "high case -- ..."},
    "uncertainty_band": {"code": "sampled_uncertainty_band_excludes_systematic_bias",
                         "includes_systematic_bias": false, "values_adjusted": false, ...}
  }
}
```
