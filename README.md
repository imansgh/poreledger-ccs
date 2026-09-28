# CCS screening starter

Screening-grade tools for **geologic CO2 storage**: Peng-Robinson density, CSLF volumetric capacity, Theis aquifer pressurization and injectivity, Monte Carlo P10/P50/P90, and a linear sensitivity surrogate.

This is not a full-physics reservoir simulator. It is a portfolio piece: physics-based Python a hiring manager can run in one command.

```bash
pip install -r requirements.txt
python scripts/run_demo.py          # no install needed
python -m pytest -q
```

Or install the package and use the CLI:

```bash
pip install -e .
ccs-screen --samples 2000 --porosity 0.10 0.20
ccs-screen --json | jq .capacity_mt
```

`python -m ccs_screen` runs the same CLI without relying on the console script.
Successful runs write only to stdout (so `--json` pipes cleanly); rejected inputs
write a `ccs-screen: ...` reason to stderr and exit 2.

**Every `ccs-screen` output is NOT_VALIDATED demo output.** The CLI capacity
path (synthetic depleted-gas priors, flat pressure prior, demo storage
efficiency) is outside the approved Model Contract (owner decision O1), and its
injectivity outputs are outside the approved scientific model. The fracture
gradient and safety factor have **no default**: without
`--fracture-gradient-pa-m` and `--safety-factor` the fracture-dependent outputs
are `UNAVAILABLE`; with them they are `NOT_VALIDATED`. The approved model is
served by the Python API and the HTTP API (see below).

## What it computes

| Piece | Use | Limit |
| --- | --- | --- |
| `co2_density_kg_m3` | Dense-phase rho(P,T) | Pure CO2, Peng-Robinson + Peneloux shift |
| `volumetric_storage_mass_kg` | M = A h phi rho E | Efficiency E is an input, not predicted |
| `theis_injection_delta_p_pa` | Far-field pressure bound | Single-phase brine analog; NOT_VALIDATED |
| `max_injection_rate_m3_s` | Rate that fits the pressure headroom | Exact inverse of the same Theis bound; NOT_VALIDATED |
| `allowable_delta_p_pa` | Headroom to the derated fracture pressure | Caller-supplied gradient and safety factor, no default; NOT_VALIDATED |
| `run_capacity_mc` | Uncertainty | Independent uniform priors |
| `fit_linear_surrogate` / `sensitivity` | Ranks which input moves capacity most | Linear in standardized features |

### Config files

A run can be driven by a JSON config instead of flags. This is the stable input
contract for the planned ingestion path:

```
PDF / KML -> extraction -> validated well record -> ScreeningConfig -> ccs_screen
```

```bash
ccs-screen --config well-001.json
ccs-screen --config well-001.json --samples 5000     # flags override the file
```

Complete example (`tests/fixtures/well-valid.json`):

```json
{
  "well_id": "WELL-001",
  "area_m2": [6.0e7, 1.2e8],
  "thickness_m": 85,
  "porosity": 0.18,
  "pressure_pa": 12500000,
  "temperature_k": 358.15,
  "storage_efficiency": [0.02, 0.05],
  "depth_m": 2450,
  "samples": 300
}
```

**Scalar or range.** Every capacity input accepts either a point value
(`0.18`) or an uncertainty range (`[0.12, 0.24]`). Extraction yields point
values; a config built entirely from them is a valid deterministic run, and the
report says so - `P10 = P50 = P90`, and constant inputs rank at exactly zero
sensitivity rather than at floating-point noise.

**Precedence.** Engine defaults, then the config file, then CLI flags. Only
flags you actually type override the file; the merged result is revalidated, so
an override cannot smuggle in an impossible value.

| Field | Unit | Required | Default |
| --- | --- | --- | --- |
| `well_id` | - | no | `null` |
| `area_m2` | m2 | **yes** | - |
| `thickness_m` | m | **yes** | - |
| `porosity` | - | **yes** | - |
| `pressure_pa` | Pa | **yes** | - |
| `temperature_k` | K | **yes** | - |
| `storage_efficiency` | - | **yes** | - |
| `depth_m` | m | no | 2000 |
| `permeability_m2` | m2 | no | 8e-14 |
| `aquifer_thickness_m` | m | no | 40 |
| `viscosity_pa_s` | Pa.s | no | 4.5e-4 |
| `radius_m` | m | no | 500 |
| `years` | yr | no | 10 |
| `aquifer_porosity` | - | no | 0.18 |
| `compressibility_1_pa` | 1/Pa | no | 1.2e-9 |
| `rate_m3_s` | m3/s | no | 0.08 |
| `fracture_gradient_pa_m` | Pa/m | no | none (outputs UNAVAILABLE) |
| `safety_factor` | - | no | none (outputs UNAVAILABLE) |
| `samples` | count | no | 2000 |
| `seed` | - | no | 42 |

Fractions are bounded to `0 < x < 1` (`safety_factor` allows exactly 1).
Validation reports **every** problem at once, with units, so an extractor gets a
complete diagnosis per well rather than one error per re-run:

```
$ ccs-screen --config broken.json
ccs-screen: missing required field(s): area_m2; porosity: must be < 1, got 1.5; pressure_pa: must be > 0 Pa, got -1
```

Bad input exits 2 with the reason on stderr and nothing on stdout.

### Percentile convention

`p10_mt` is the **10th percentile - the low case**. This is the statistical convention, not the petroleum convention where P10 is the high case. Read `p10 < p50 < p90` literally.

### Density accuracy

Peng-Robinson with a constant Peneloux volume shift, against Span-Wagner (NIST) reference densities. The shift is tuned for the dense-phase storage window; it over-corrects near the critical point, which is stated here rather than hidden.

| P (MPa) | T (K) | Phase | This code | Span-Wagner | Error |
| --- | --- | --- | --- | --- | --- |
| 2 | 280 | vapour | 44.3 | 43.6 | +1.6% |
| 4 | 290 | vapour | 103.1 | 101.6 | +1.4% |
| 5 | 280 | liquid | 925.2 | 883.6 | +4.7% |
| 8 | 290 | liquid | 873.0 | 796.6 | +9.6% |
| 12 | 320 | dense | 601.5 | 617.7 | -2.6% |
| 15 | 333 | dense | 584.1 | 604.3 | -3.3% |
| 20 | 340 | dense | 677.9 | 692.4 | -2.1% |
| 30 | 350 | dense | 790.8 | 829.8 | -4.7% |

Below the saturation pressure the cubic has three roots; the code selects the phase by minimum fugacity rather than assuming the dense root. `tests/test_properties.py` pins this envelope.

## Approved screening model (Phase 13 Model Contract)

The owner-approved Model Contract is recorded in
[docs/phase13-owner-decision-record.md](docs/phase13-owner-decision-record.md)
and implemented in `src/ccs_screen/approved_model.py`. It is selected by the
built-in parameter set `literature-screening-v1`, the API default.

```
M = A * h_g * phi * rho_CO2(P_EOS, T) * E
```

- **Inputs:** `area_m2` and the storage-assessment interval `z_top`, `z_base`
  (depth below ground level, in the well's `depth_m` datum). `h_g = z_base -
  z_top` and `z_state = (z_top + z_base) / 2` (a project model convention) are
  derived; there is no thickness input.
- **Pressure:** `P_EOS = 101325 Pa + rho_brine * g * (z_state - z_wl)`, absolute.
- **Water level:** two named deterministic scenarios, always both reported:
  `GROUND_REFERENCE` (`z_wl = 0`, the project reference scenario) and
  `SEA_LEVEL_SENSITIVITY` (`z_wl` = ground elevation above sea level). Neither
  is a measured formation head; water level is never sampled.
- **Temperature:** the nearest eligible corrected observation inside the
  interval (Horner-corrected, Fertl-Wichmann, Squarci-Taffi), with the
  contract's tie rules; no interpolation, no 0.85 filter; otherwise unavailable.
- **EOS envelope:** 1-35 MPa on `P_EOS` and 280-400 K, checked for every
  Monte Carlo realisation. If any realisation is outside, the scenario is
  `OUTSIDE_VALIDATED_ENVELOPE` and its validated percentiles are blocked; no
  realisation is discarded.
- **Depth reference:** only an established ground-level reference is usable.
  `unknown` gives `DEPTH_REFERENCE_NOT_ESTABLISHED`; any other datum gives
  `UNSUPPORTED_DEPTH_DATUM`. No datum conversion is applied. Every ingested
  well is currently `unknown`, so every real well's approved result is
  `UNAVAILABLE` -- the consequence the contract records.

Each named scenario carries `validation_status` (`VALIDATED`,
`OUTSIDE_VALIDATED_ENVELOPE` or `UNAVAILABLE`) and machine-readable
diagnostics. P10/P50/P90 are conditional on the declared model; they are not
total accuracy. The placeholder scenarios (`conservative`, `central`,
`sensitivity`, `none`), scenario JSON files and `ccs-ingest` screening keep
their behaviour and are labelled `NOT_VALIDATED`.

## Ingestion (Piemonte pilot)

Structured Italian well sources -> validated screening inputs, with provenance:

```bash
pip install -e ".[ingest]"
ccs-ingest --data-dir data                    # fleet completeness
ccs-ingest --data-dir data --well "SALUZZO|1" # one well, in full
```

Four of the six required inputs (`area_m2`, `porosity`, `pressure_pa`,
`storage_efficiency`) do not exist in any available source, and net
`thickness_m` is not derivable from the gross stratigraphy that does. No well
can be screened without explicitly declared engineering assumptions, and the
pipeline refuses to invent them.

Screening therefore runs under a named **scenario** that supplies those inputs
explicitly. Every report separates source-derived values from assumed ones:

```bash
ccs-ingest --data-dir data --screen --scenario sensitivity
ccs-ingest --data-dir data --screen --scenario central --well "SALUZZO|1"
ccs-ingest --data-dir data --compare-temperature --well "TRECATE|9|ST"
```

`literature-screening-v1` is the one scenario with a documented basis: storage
efficiency from CSLF-T-2008-04 (Bachu, 2008), porosity from Donda et al. (2011)
for Italian reservoirs, and a declared brine density. In the public API it runs
the approved model (above). Applied through `ccs-ingest`, which uses the legacy
scenario resolver, it supplies **neither area nor net thickness** and screens
nothing on its own. The other built-ins are labelled placeholders. Every
`ccs-ingest` screening, comparison and emitted config is `NOT_VALIDATED`.
`temperature_k` can never be supplied by a scenario. Nothing produced here is a
site-specific estimate; the correct term is **scenario-based capacity**.

See [docs/ingestion.md](docs/ingestion.md) and
[docs/scenario-literature-review.md](docs/scenario-literature-review.md).

## HTTP API

```bash
pip install -e ".[ingest,web]"
CCS_CORS_ORIGINS=http://localhost:3000 uvicorn ccs_screen.web.app:app --reload
```

```bash
curl -s -X POST 'http://localhost:8000/wells/SALUZZO%7C1/screen'   -H 'Content-Type: application/json'   -d '{"user_inputs": {"area_m2": 8.0e7, "z_top": 1400, "z_base": 1527}, "samples": 2000}'
```

On the approved model (the default) `area_m2`, `z_top` and `z_base` are
required with **no defaults**, and `thickness_m` is rejected. The response
carries both named water-level scenarios, each with its status and
diagnostics. Legacy scenarios (`scenario: "sensitivity"` and the other
placeholders) keep `area_m2` + `thickness_m` and are labelled `NOT_VALIDATED`.
Omitted inputs are rejected, never filled in. Every response carries an
`interpretation` block marking the number as scenario-based, not site-specific,
not certified. See [docs/http-api.md](docs/http-api.md).

## Web interface

A Next.js + TypeScript frontend that puts the provenance audit trail on screen
beside the number, not behind it.

**Backend** (terminal 1):

```bash
pip install -e ".[dev,web]"
CCS_CORS_ORIGINS=http://localhost:3000 uvicorn ccs_screen.web.app:app --reload
```

**Frontend** (terminal 2):

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

Configure the backend URL with `NEXT_PUBLIC_CCS_API_URL` (see
`frontend/.env.example`):

```
NEXT_PUBLIC_CCS_API_URL=http://127.0.0.1:8000
```

CORS is off in the backend until `CCS_CORS_ORIGINS` names an origin, so the
frontend cannot reach it until you set that variable.

The form asks for the inputs the selected scenario requires, all with **no
defaults**: storage area and the storage-assessment interval (`z_top`,
`z_base`) on the approved model; storage area and net reservoir thickness on a
`NOT_VALIDATED` legacy scenario. The UI computes nothing from them. An approved
result shows `GROUND_REFERENCE` and `SEA_LEVEL_SENSITIVITY` side by side, each
with its status and diagnostics; validated percentiles appear only when the API
reports them. Legacy results are badged `NOT_VALIDATED` and keep the four
provenance categories -- source-derived, modelled, literature-constrained, user
input -- each labelled in text, not colour alone.

This is a screening tool and a work in progress. It is not production-ready and
produces no certified or site-specific storage estimate.

## Deployment

Not deployed anywhere, and not production-hardened: there is **no
authentication and no rate limiting**. Treat what follows as the minimum a
deployment needs, not a claim that it is finished.

### Backend

```bash
pip install ".[ingest,web]"

CCS_DATA_DIR=/srv/ccs/data CCS_CORS_ORIGINS=https://your-frontend.example CCS_DOCS=0 uvicorn ccs_screen.web.app:app --host 0.0.0.0 --port 8000 --workers 4
```

| Variable | Default | Purpose |
| --- | --- | --- |
| `CCS_DATA_DIR` | `data` | directory holding the structured sources |
| `CCS_CORS_ORIGINS` | *(empty)* | comma-separated allowed origins; **no wildcard default** |
| `CCS_MAX_BODY_BYTES` | `16384` | JSON request body cap (413 above it) |
| `CCS_WARM_CACHE` | `1` | normalize at startup so the first request is not slow |
| `CCS_DOCS` | `1` | set `0` to disable `/docs` and `/redoc` |

See `.env.example`. No secrets are required.

**CORS is off until you name origins.** An unset `CCS_CORS_ORIGINS` blocks every
cross-origin browser request, so the frontend will not work until it is set to
the exact origin the frontend is served from.

**Rate limiting is not implemented** and should be handled by the reverse proxy
or API gateway. Doing it in-process would need state shared across workers; an
in-process counter would be wrong the moment a second worker started. What *is*
enforced in-process: the body cap, and `samples <= 50000` bounding CPU per
request.

### Frontend

`NEXT_PUBLIC_CCS_API_URL` is inlined at **build** time, not read at runtime, so
it must be set before `npm run build`:

```bash
cd frontend
npm ci
NEXT_PUBLIC_CCS_API_URL=https://your-backend.example npm run build
npm run start   # or serve the build output behind your own server
```

The browser calls that URL directly, so it must be reachable from the visitor's
machine and must appear in the backend's `CCS_CORS_ORIGINS`. A production build
made without the variable falls back to `http://127.0.0.1:8000` and shows a
visible warning in the UI rather than failing silently.

### Development

The commands under [Web interface](#web-interface) above are **development**
instructions: they bind to localhost, enable `/docs`, and use `--reload`.

## Next (on purpose left out)

Two-phase plume, residual/solubility trapping, caprock geomechanics, well integrity. Those are the follow-on if this repo stays the CCS public project.

## Repo layout

```
src/ccs_screen/    properties, capacity, pressure, monte_carlo, surrogate, config,
                   approved_model, api, cli
src/ccs_screen/web/      FastAPI app, Pydantic schemas, settings
frontend/          Next.js + TypeScript UI (app, components, lib, tests)
src/ccs_screen/ingest/   provenance, identity, units, records, sources,
                         normalize, completeness, assumptions,
                         scenario, report, cli
scripts/run_demo.py
tests/             538 tests + JSON fixtures, no network, no dependency on data/
```

CI (`.github/workflows/ci.yml`) runs the suite on Python 3.10, 3.11 and 3.12 on
every push and pull request. Each job installs from `pyproject.toml` into a clean
runner and checks the installed package is importable and runnable before testing,
so a module missing from the wheel fails CI rather than passing off the source tree.

`data/` is a local 11 GB mirror of public Italian well profiles (videpi.com) and is deliberately git-ignored.
