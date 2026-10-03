# HTTP API

FastAPI wrapper over `ccs_screen.api` and `ccs_screen.assessment`. It
translates HTTP to those calls and does nothing else: no science, no defaults,
no interpretation of its own.

The primary workflow is **user assessments** (`/assessments/*`): your own well
or site data, evaluated by the approved model, with no dataset on the server.
The **existing-data** endpoints (`/wells`, `/funnel`) are optional and need a
dataset in `CCS_DATA_DIR`.

```bash
pip install -e ".[ingest,web]"
python scripts/serve.py --demo --cors-origin http://localhost:3000   # synthetic demo dataset
python scripts/serve.py --data-dir data                              # real sources
# interactive docs at /docs
```

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | liveness (always `200` while serving), `engine_ready`, `data_ready`, well count, published limits |
| GET | `/ready` | **engine readiness**: `200` when user assessments can be evaluated, whatever the dataset |
| GET | `/ready/existing-data` | optional dataset readiness: `200` when ready, `503` with the problems otherwise |
| GET | `/assessments/contract` | the input schema: fields, units, conventions, methods, limits |
| GET | `/assessments/examples` | the four synthetic examples (a `ccs-assessment/1` document) |
| GET | `/assessments/files/{name}` | download `assessment-template.{json,csv}` or `synthetic-examples.{json,csv}` |
| POST | `/assessments/parse` | parse an uploaded JSON or CSV file into an editable document; problems with row numbers; nothing evaluated |
| POST | `/assessments/validate` | validate and normalize a document; nothing evaluated |
| POST | `/assessments/evaluate` | validate, then evaluate every assessment with the approved model |
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
| 503 | `GET /ready`: the dataset is not ready. Any data endpoint: `DatasetNotReadyError`, a required source is missing or unreadable |
| 422 | Schema violation: unknown field, wrong type, out-of-range `samples`, a non-finite number (`NaN`, `Infinity`, `-Infinity`) |
| 500 | Unexpected server error; the body never carries a traceback |

`UnknownWellError` subclasses `ApiError`, so its handler is registered first.

Errors share one envelope:

```json
{"error": "no well with id 'NOPE|9'", "type": "UnknownWellError", "detail": null}
```

On a `422` (`"type": "RequestValidationError"`), `detail` is the list of field
errors (`loc`, `msg`, `type`, `input`); a rejected non-finite `input` is echoed
as `"NaN"`, `"Infinity"` or `"-Infinity"`.

On a legacy scenario, `area_m2` and `thickness_m` must also lie inside the
existing screening-config bounds (`ccs_screen.config.BOUNDS`); a value outside
them comes back `blocked` naming the bound.

`GET /funnel` runs no Monte Carlo on either path. Its `samples` parameter is
still accepted and range-checked for backwards compatibility, and has no effect.

## Limits

| Parameter | Min | Max | Default |
| --- | --- | --- | --- |
| `samples` | 1 | 50,000 | 2,000 |
| request body | - | 16 KiB (`CCS_MAX_BODY_BYTES`) | - |

`samples` is a `StrictInt`: `"2000"` and `2.0` are rejected rather than
coerced, and out-of-range values are rejected rather than clamped. The bound is
published in the OpenAPI schema and in `/health`.

The body cap is enforced on the bytes actually received, not only on the
declared `Content-Length`: a declared length over the cap is refused before
any byte is read, and a chunked (or under-declared) body is counted chunk by
chunk and abandoned the moment it passes the cap, so at most one chunk beyond
the cap is ever read. Keep a matching limit at the reverse proxy as well.

## Dataset and synthetic demo data

`/health`, `/ready` and every data response (`/wells/{id}`, `/wells/{id}/inputs`,
`/screen`, `/temperature`, `/funnel`) carry a `dataset` block:

```json
{"kind": "synthetic_demo", "synthetic": true,
 "name": "CCS screening synthetic demonstration dataset", "version": "1",
 "statement": "Every well, name, depth, datum, elevation and temperature in this file is fictional. ..."}
```

`kind` is `structured_sources` (real data, `synthetic: false`) or
`synthetic_demo`. Each `/wells` summary carries `synthetic` (boolean). When the
dataset is synthetic, every interpretation block's `warnings` starts with
`synthetic_demo_dataset` (`invalidates_result: true` for any real-world use).
A data directory is the demo only when it holds `ccs-synthetic-demo.json`; see
[demo/README.md](../demo/README.md). These are additive fields; no existing
field changed.

## User assessments

Request bodies for `validate` and `evaluate`:

```json
{"document": {"schema_version": "ccs-assessment/1", "assessments": [...]},
 "samples": 2000, "seed": 42}
```

`parse` takes `{"format": "csv" | "json", "content": "<file text>"}` and
returns `{document, preview_document, problems, valid, import_blocked}`.
`import_blocked` is true when the parser itself reported an error:
conflicting assessment-level cells across rows, an incomplete observation
row, a wrong row length, conflicting schema versions. What was parsed is then
partial (it keeps the first row's values and drops the bad rows), so
`document` is `null` and the partial data comes back as `preview_document`,
for display only. The preview carries a top-level `blocked_import` marker
(`format`, `reason`, and the parser `problems` with row numbers); `validate`
and `evaluate` reject any document carrying it with a single
`IMPORT_BLOCKED` problem (422 from `evaluate`), however the rest of it is
edited. Correct the file and parse it again. Validation problems of a
complete document never block: `document` is returned and can be corrected.
The marker prevents accidental evaluation of a partial import; it is not a
signature, and a caller who removes it has built a new document of their own. The schema, units, CSV layout and limits
are in [assessment-input-schema.md](assessment-input-schema.md).

`evaluate` returns `{schema_version, run, notices, assessments, summary_csv}`.
Each entry of `assessments` has `assessment_id`, `synthetic`, `data_origin`,
`model`, `run`, `outcome` (`overall_status`; `category` = `estimate`,
`partial_estimate`, `information_needed` or `outside_validated_range`;
per-scenario statuses with readable labels; `blocking_reasons`, each distinct
reason once with a plain `title`, `explanation`, `action`, the exact `code` and
`technical_message`, and the `scenarios` it affects; `main_reason` and
`next_action` for the first of them), `inputs` (normalized, with originals),
`provenance`, `result` (the engine's approved-model payload, identical in
shape to `/wells/{id}/screen` except that each observation in
`temperature_selection` also carries `input_index`, its position in the
submitted `temperature_observations`), `interpretation` and `limitations`.
In `summary_csv`, user text that a spreadsheet could evaluate as a formula is
prefixed with `'` (see [assessment-input-schema.md](assessment-input-schema.md)).
A number too large to represent (e.g. `1e400` written as an integer) is an
input error (`NOT_FINITE`), never a server error. Input
errors return **422** with `type: "AssessmentValidationError"` and every
problem (`path`, `row`, `code`, `message`, `severity`) in `detail`; notices
(inputs that will make a result `UNAVAILABLE`) never block.

Nothing submitted is stored or logged; see [data-handling.md](data-handling.md).
Requests under `/assessments` have their own body cap, 256 KiB by default
(`CCS_MAX_ASSESSMENT_BODY_BYTES`).

## Liveness and readiness

`GET /health` is **liveness**. It answers `200` with `status: "ok"` whenever
the process is serving -- including when the data directory is missing or
empty -- and adds `engine_ready`, `data_ready` (booleans) and `wells_loaded`.

`GET /ready` is **engine readiness** (changed in the user-assessment release;
it used to report dataset readiness, which moved to `/ready/existing-data`).
It evaluates the complete synthetic example once through the approved engine
and answers `200` when both named scenarios come back `VALIDATED`, otherwise
`503`. It does **not** depend on any well dataset; `existing_data` in the body
reports that for information only:

```json
{"status": "ready",
 "engine": {"ready": true, "check": "evaluates the synthetic example SYNTH ALPHA|1 ...",
            "problem": null, "schema_version": "ccs-assessment/1"},
 "existing_data": {"ready": false, "dataset": {...}, "wells_loaded": 0,
                   "detail": "/ready/existing-data"}}
```

`GET /ready/existing-data` is **optional dataset readiness** (the former
`/ready`):

```json
{"status": "ready", "wells_loaded": 46, "data_dir": "data",
 "sources": [{"source": "GEOTHOPICA:Anagrafica", "file": "Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx",
              "required": true, "status": "loaded", "detail": null}],
 "problems": []}
```

It is `200` when the data directory exists, every **required** source loaded,
and at least one well was normalized; otherwise `503` with `status:
"not_ready"` and the reasons in `problems`. Required sources are the three
GEOTHOPICA workbook sheets (`Anagrafica`, `Temperature`, `Lito-Stratigrafie`),
read with `openpyxl`. Each source's `status` is one of:

| `status` | Meaning |
| --- | --- |
| `loaded` | Read successfully |
| `missing` | The file, or the workbook sheet, is absent |
| `dependency_missing` | The reader dependency (`openpyxl`) is not installed |
| `conflict` | The synthetic demo manifest shares a directory with real source files; refused so the two are never combined |
| `unreadable` | Present but cannot be read: an inaccessible file (`OSError`), a corrupt or truncated ZIP container, a workbook missing its package parts, malformed workbook or sheet XML, or a sheet with no header row. `detail` names the file, the sheet and the underlying error, e.g. `cannot read Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx (Anagrafica): BadZipFile: File is not a zip file` | The registry CSVs (`pozzi-storici.csv`,
`po_wells_clean.csv`) only enrich wells the workbook defines and remain
**optional**: their absence is listed in `sources` but does not make the
dataset unready. Failed required sources are also logged as warnings, and
`ccs-ingest` prints them to stderr and reports `source_status` in its JSON.

When a required source is not `loaded`, nothing is cached: no records, and no
success. Data endpoints (`/wells`, `/wells/{id}`, `/screen`, `/funnel`, ...)
then answer `503` with the usual envelope, `type: "DatasetNotReadyError"`, and
the failed required sources as a list in `detail`. Each later request reads the
sources again, so a repaired dataset is picked up without a restart. Startup
cache warming treats the same failures as expected: the process still starts
and serves `/health` and `/ready`. Only those expected read and format
failures are translated; a programming error still surfaces as a `500` (and in
the server log), never as a dataset status.

Readiness concerns the software's inputs only. A ready dataset still returns
`UNAVAILABLE` approved-model results wherever the Model Contract requires it
(for example, a well whose depth reference is not established).

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

Always enforced in-process: the request-body cap, `MAX_SAMPLES` per request,
and at most 200 000 realisations per assessment request.

Opt-in, for a public **single-process** deployment (both off by default):

- `CCS_RATE_LIMIT_PER_MINUTE`: POST requests per client address per rolling
  minute. Over it: **429** `{"type": "RateLimited", ...}` with `Retry-After`.
- `CCS_MAX_CONCURRENT_EVALUATIONS`: Monte Carlo runs at once (assessment
  evaluation, well screening, temperature comparison). Over it: **503**
  `{"type": "ServerBusy", ...}` with `Retry-After`; requests are not queued.

`Retry-After` is exposed to the allowed CORS origins. `GET /assessments/contract`
reports the active values in `deployment_limits` (0 = off). The state is per
process: with several workers or instances, enforce limits at the reverse proxy
or API gateway instead (see [deployment.md](deployment.md)).

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
