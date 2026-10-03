# Command-line tool (`ccs-screen`)

The `ccs-screen` CLI runs the original demonstration capacity path: synthetic
depleted-gas priors, Monte Carlo P10/P50/P90, a linear sensitivity surrogate and
a Theis injectivity bound. **All of its output is `NOT_VALIDATED`**; the
approved model is served by the Python API and the HTTP API (see the
[README](../README.md) and [http-api.md](http-api.md)).

```bash
pip install -r requirements.txt
python scripts/run_demo.py          # no install needed
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

## Config files

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

## Percentile convention

`p10_mt` is the **10th percentile - the low case**. This is the statistical convention, not the petroleum convention where P10 is the high case. Read `p10 < p50 < p90` literally.

## Density accuracy

Peng-Robinson with a constant Peneloux volume shift, against Span-Wagner (1996) reference densities computed with CoolProp 8.0.0 (HEOS). An earlier version of this table had incorrect reference values; it was regenerated on 2026-10-02. The full envelope statistics are in [validation-evidence.md](validation-evidence.md). The shift is tuned for the dense-phase storage window; it over-corrects near the critical point, which is stated here rather than hidden.

| P (MPa) | T (K) | Phase | This code | Span-Wagner (CoolProp 8.0.0) | Error |
| --- | --- | --- | --- | --- | --- |
| 2 | 280 | vapour | 44.3 | 43.8 | +1.3% |
| 4 | 290 | vapour | 103.1 | 100.5 | +2.6% |
| 5 | 280 | liquid | 925.2 | 893.9 | +3.5% |
| 8 | 290 | liquid | 873.0 | 854.2 | +2.2% |
| 12 | 320 | dense | 601.5 | 632.2 | -4.9% |
| 15 | 333.15 | dense | 584.1 | 604.1 | -3.3% |
| 20 | 340 | dense | 677.9 | 679.7 | -0.3% |
| 30 | 350 | dense | 790.8 | 759.0 | +4.2% |

Below the saturation pressure the cubic has three roots; the code selects the phase by minimum fugacity rather than assuming the dense root. `tests/test_properties.py` pins this envelope.
