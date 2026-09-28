# Ingestion: structured sources to ScreeningConfig

This document describes the ingestion layer in `src/ccs_screen/ingest/`, which
turns the structured Italian well sources into validated screening inputs.

Its governing rule:

> **Incomplete but honest beats complete-looking.**
> A field with no source is reported as missing and blocks `ScreeningConfig`
> construction until someone supplies a declared assumption for it.

A capacity number produced from an undocumented area is indistinguishable, on
the page, from one produced from a measured area. Keeping that difference
visible is the entire purpose of this layer.

## Data flow

```
structured sources          GEOTHOPICA xlsx, pozzi-storici.csv, po_wells_clean.csv
        |
        v
RawWellRecord               verbatim cell text + file/sheet/row, nothing coerced
        |
        v
NormalizedWellRecord        SI units, canonical well id, provenance per field
        |
        v
provenance + confidence     extracted / derived / assumed / missing, per field
        |
        v
completeness report         per-well: can this be screened, and if not why not
        |
        v
engineering assumptions     explicit, authored, dated, justified
        |
        v
ScreeningConfig             built ONLY when all six required inputs exist
```

## Usage

```bash
pip install -e ".[ingest]"

ccs-ingest --data-dir data                       # fleet completeness summary
ccs-ingest --data-dir data --well "SALUZZO|1"    # one well, in full
ccs-ingest --data-dir data --list-incomplete     # why each well is blocked
ccs-ingest --data-dir data --assumptions examples/pilot-assumptions.json \
           --emit-configs out/                   # write ScreeningConfigs
```

## Sources actually read

Only these files. The 11 GB scanned-PDF corpus is **not** touched: reconnaissance
established that the scans have no text layer and carry no reservoir properties,
only metadata already present in the CSVs.

| File | Sheet / table | Supplies |
| --- | --- | --- |
| `Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx` | `Anagrafica` | depth, ground elevation, operator, outcome |
| | `Temperature` | temperature vs depth **with method** -- the only temperature source |
| | `Lito-Stratigrafie` | gross chronostratigraphic intervals |
| `pozzi-storici.csv` | - | national registry: depth, year, operator, outcome |
| `po_wells_clean.csv` | - | cleaned Po-valley subset: WGS84 coordinates, depth |

All CSVs are **cp1252**, not UTF-8.

## What is extracted, derived, assumed and missing

| Field | Status | Detail |
| --- | --- | --- |
| `well_id` | **extracted** | canonical id from the source name |
| `depth_m` | **extracted** | total depth; datum usually unstated |
| coordinates | **extracted** | WGS84 (approximate, per the source column name) |
| `surface_elevation_m` | **extracted** | GEOTHOPICA `quota` |
| operator / year / outcome | **extracted** | |
| `temperature_k` | **derived** | best-ranked reservoir method near TD, converted from degC |
| `gross_thickness_m` | **derived** | bottom-top of the deepest logged unit |
| `net_storage_thickness_m` | **missing** | needs net-to-gross, which no source provides |
| `aquifer_thickness_m` | **missing** | no hydraulic-unit definition in any source |
| `porosity` | **missing** | logs record only qualitative type codes (PK/PI/PV/PC/PF) |
| `pressure_pa` | **missing** | no pressure data in any structured source |
| `area_m2` | **missing** | only administrative licence polygons exist |
| `storage_efficiency` | **missing** | engineering assumption by definition |

Four of the six `ScreeningConfig` requirements are therefore unavailable from
source data, and `thickness_m` is a fifth (see below). **No well in the pilot can
be screened without declared assumptions.** That is a finding, not a defect.

## The known data defects, handled explicitly

### Depth datum

AGIP composite logs state *"Tutte le profondita sono riferite al piano tavola
rotary"* -- depths run from the rotary table, which stood 120.00 m above sea
level at MALOSSA 15 and 238.7 m at CAVAGLIETTO 1. On a 900 m well that is a 27%
error if ignored.

`DepthMeasurement` carries a `DepthDatum`. Conversion to sub-sea depth requires
both a known datum *and* its elevation; otherwise `to_msl()` raises. The
structured sources do not state a datum, so `depth_msl_m` is reported **missing**
with that reason rather than passing along-hole depth off as sub-sea.

### Decimal separators

`120,00` and `313.20` appear in the same document family. `parse_number` applies
deterministic rules:

1. Both `.` and `,` present -> the **last** is the decimal separator.
2. One separator type, repeated -> thousands separator (`1.384.543` -> 1384543).
3. One separator, once:
   - exactly 3 trailing digits -> **ambiguous, raises** (`1.384` is either 1384
     or 1.384 and the source does not say which);
   - otherwise it is the decimal separator.

`~` and `circa` mark the result approximate rather than being discarded.

### Feet and metres

`to_metres` converts only an **explicitly labelled** unit. There is no magnitude
heuristic: 3000 could be metres or feet, and guessing wrong is a 900 m error.
Unlabelled values raise `UnitError`.

### Well-name normalization

Naive string matching linked 3 of 46 pilot wells to the national registry;
canonical matching links 40. Canonical form is `BASE|NUMBER|SUFFIX`, with the
suffix omitted when empty:

| Source spelling | Canonical |
| --- | --- |
| `SALUZZO 1`, `SALUZZO 001`, `saluzzo_001` | `SALUZZO|1` |
| `TRECATE 5D` | `TRECATE|5|D` |
| `NOVI LIGURE 2 BIS DIR` | `NOVI LIGURE|2|BIS DIR` |
| `S.BENIGNO CANAVESE 1`, `SAN BENIGNO CANAVESE 1` | `S BENIGNO CANAVESE|1` |

Saint prefixes collapse to a single `S` token rather than expanding to
SAN/SANT'/SANTA: expanding needs the following word's gender and initial, which
we cannot determine reliably, whereas collapsing is symmetric in both
directions. The original spelling is always kept on the record.

## Temperature provenance

Not one of the 452 temperature records in the pilot is a stabilised bottom-hole
measurement. Every value is extrapolated, unstabilised, or a surface air mean.
Methods are preserved, never collapsed:

| Method | Rank | Confidence |
| --- | --- | --- |
| `horner_corrected` | 0 | high |
| `extrapolated_fertl_wichmann` | 1 | medium |
| `extrapolated_squarci_taffi` | 2 | medium |
| `non_stabilized` | 3 | low |
| `raw` | 4 | low |
| `surface_air_mean` | never selectable | none |

Selection takes the best-ranked **reservoir** method within 85% of total depth,
so shallow modelled grid points (300/500/1000 m) cannot outrank a reading at TD.
A well whose only record is a surface air mean gets `temperature_k` **missing**,
because an annual air temperature is not a reservoir temperature.

This ingestion-time selection (the rank table and the 85% window) feeds the
legacy screening paths only, which are `NOT_VALIDATED` (Phase 14, owner decision
O2). The approved model never reads `temperature_k`: it selects one corrected
observation (Horner-corrected, Fertl-Wichmann or Squarci-Taffi) inside the
caller's storage interval, nearest the state point, with the Model Contract's
tie rules, no ranking and no 85% window, and excludes observations below the
recorded total depth (`ccs_screen.approved_model.select_temperature`). Each
`TemperatureObservation` carries a `depth_datum`, which ingestion leaves
`unknown` because no source states it; under the approved model an observation
qualifies only with an established ground-level reference.

Competing values at the same depth are recorded as a `Conflict`. This matters
quantitatively: choosing the unstabilised over the extrapolated value changes CO2
density -- and therefore capacity, which is linear in density -- by **6.4% to
15.0%** across the pilot wells.

## Thickness: three different quantities

| Kind | Available | Meaning |
| --- | --- | --- |
| `GROSS_STRATIGRAPHIC` | **yes** | bottom-top of a chronostratigraphic megaunit |
| `NET_STORAGE` | no | net pay inside the closure -- what `thickness_m` means |
| `AQUIFER_HYDRAULIC` | no | connected interval carrying pressure diffusion |

The sources give only gross intervals: 91-2,557 m across the pilot wells, against
the engine's representative net thickness of 25-55 m. Substituting one for the
other overstates capacity by **1.5x to 128x** depending on which pair you take
(a 91 m gross against 60 m net is only 1.5x; 2,557 m against 20 m is 128x), and
the result would look entirely plausible.

`gross_thickness_m` is therefore a separate field, and **no code path converts it
to `thickness_m`**. `ScreeningConfig.thickness_m` is left unrenamed for now; the
real gap is the absent net-to-gross ratio, not the field name.

The approved model (Phase 13 Model Contract) uses none of these three as an
input. Its thickness term is `h_g = z_base - z_top`, the gross thickness of a
storage-assessment interval the caller designates explicitly, in the same depth
coordinate and datum as `depth_m`; it is never inferred from total depth or
from the logged stratigraphic units. `thickness_m` remains the net-thickness
input of the `NOT_VALIDATED` legacy paths.

## Provenance model

Every normalized field is a `FieldValue` carrying `value`, `unit`, `provenance`,
`confidence`, `source`, `method`, `derivation`, `original_value` and any
`conflicts`. Invariants enforced at construction:

- a `MISSING` field cannot carry a value;
- a non-missing field must carry one;
- a `DERIVED` field must record how it was derived.

`Provenance` is one of `extracted`, `derived`, `spatial`, `assumed`,
`model_default`, `missing`. The transition `missing -> assumed` never happens
implicitly.

## Engineering assumptions

`Assumption` requires `parameter`, `value` (scalar or range), `author` and
`rationale`; `date`, `citation` and `confidence` are also carried. Construction
fails without an author or rationale.

Only these may be assumed: `area_m2`, `porosity`, `pressure_pa`,
`storage_efficiency`, `thickness_m`. Depth and temperature come from sources or
not at all -- assuming them would defeat the point of ingesting anything.

Assumptions **fill holes, never overwrite measurements**: where a derived
temperature exists, it wins.

See `examples/pilot-assumptions.json` for a worked set. Note that every entry
there is marked PLACEHOLDER: it exists to exercise the pipeline, not to describe
a real site.

## ScreeningConfig gate

`build_screening_config()` raises `IncompleteWellError` naming every missing
field. There are no fallback defaults. A well that cannot be screened stays
unscreened, and the completeness report says exactly why.

## Deliberately not built

PDF OCR, log digitisation, seismic interpretation, automated area estimation,
automatic porosity estimation, automatic pressure estimation. Each is a separate
milestone. In particular, **no amount of OCR unblocks area, porosity or
pressure** -- those are not in the scans either.

## Current blocker

`area_m2` is the one that matters most: capacity is linear in it, and the only
polygons in the dataset are expired mining licences (median 268 km2, max 21,138
km2) against a plausible closure of 50-150 km2. Well-to-concession joins succeed
for 29 of 1,556 wells. Resolving this needs a depth-structure map or
top-reservoir contour set -- the seismic *line geometry* is present in the KML,
but the *interpretation* is not.

---

# Scenarios: screening with auditable assumptions

Ingestion establishes that no pilot well can be screened from source data alone.
The scenario layer lets a well be screened anyway -- without ever letting an
assumption pass as a measurement.

```
NormalizedWellRecord + ScreeningScenario -> ScreeningConfig
                                         or IncompleteScreening
                                         -> engine -> WellScreeningReport
```

## The scenario model

`ScreeningScenario` carries `name`, `description`, `version`, `date`,
`rationale` and an optional `citation`, wrapping an `AssumptionSet` whose
entries each carry their own author, date, rationale and citation.

A scenario may supply only these five inputs:

```
area_m2   thickness_m   porosity   pressure_pa   storage_efficiency
```

**`temperature_k` is deliberately excluded.** It is the one required input the
sources actually provide, and letting a scenario override it would discard the
only reservoir measurement in the dataset. A well with no reservoir temperature
stays blocked under every scenario, including a fully specified one.

Values may be a scalar (`0.18`) or a range (`[0.12, 0.24]`), mapping directly
onto the existing `ScreeningConfig` prior representation. A scenario of scalars
is deterministic and collapses the Monte Carlo to P10 = P50 = P90.

## Precedence

Source-derived values always win. When a scenario supplies a parameter the
record already has, the assumption is ignored and the resolved input records
`"scenario assumption ignored (source data wins)"`. The reverse never happens:
assumptions fill holes only.

## Built-in scenarios

| Scenario | Shape | Evidence | Purpose |
| --- | --- | --- | --- |
| `none` | no assumptions | - | the honest baseline: what the data alone supports |
| `literature-screening-v1` | ranges | cited | the only scenario with a documented basis |
| `conservative` | point values, low side | **placeholder** | deterministic lower-bound check |
| `central` | point values, mid | **placeholder** | deterministic base case |
| `sensitivity` | ranges | **placeholder** | exercises uncertainty propagation |

Phase 14 (owner decision O2): everything `ccs-ingest` screens runs the legacy
scenario resolver documented here -- including `literature-screening-v1` and any
scenario or assumption JSON file -- and its output is labelled
`NOT_VALIDATED`. The placeholder descriptions say so. In the public Python and
HTTP API, `literature-screening-v1` instead runs the approved model (see
`README.md` and `docs/http-api.md`); the placeholders and JSON files remain
`NOT_VALIDATED` there too.

### literature-screening-v1

The one scenario whose values are traceable. See
[scenario-literature-review.md](scenario-literature-review.md) for the full
review, including what the literature does *not* support.

| Parameter | Value | Evidence class | Source |
| --- | --- | --- | --- |
| `storage_efficiency` | 0.01 - 0.04 | generic | CSLF-T-2008-04 (Bachu, 2008), P15-P85 for deep saline aquifers; a project-defined Uniform prior over those bounds (see scenario-literature-review.md) |
| `porosity` | 0.10 - 0.35 | regional | Donda et al. (2011) IJGGC 5(2) 327-335, Table 2, 13 Italian reservoirs |
| `pressure_pa` | derived | generic | P = rho*g*z from **source depth**, rho = 1020-1100 kg/m3 |
| `area_m2` | **not supplied** | unsupported | explicit user input; see area policy |
| `thickness_m` | **not supplied** | unsupported | explicit user input; see net-thickness policy |

Applied alone through the legacy resolver it screens **nothing**: every well
blocks on `area_m2` and `thickness_m`. That is the intended behaviour. `examples/` ships both the bare
scenario and a worked one that adds those two as clearly-labelled user inputs.

Nothing in it is site-specific. No value was measured in any pilot well.

### Input labels

Three labels, because two are not enough:

| Label | Meaning |
| --- | --- |
| `source` | extracted, or derived from this well's own data |
| `MODELLED` | computed from source data under a declared generic model (hydrostatic pressure from depth) |
| `ASSUMED` | supplied by a person through a scenario |

`MODELLED` exists so a pressure computed from a real depth under an assumed
hydrostatic gradient cannot be read as a measurement.

### Area and net-thickness policies

> Area is not inferred from administrative licence boundaries. `area_m2` is
> explicit scenario or user input.

> Net storage thickness is not derived from gross stratigraphic thickness.
> `thickness_m` is explicit scenario or user input.

Both statements are constants in the code (`AREA_POLICY_STATEMENT`,
`NET_THICKNESS_POLICY_STATEMENT`), appear in every scenario's JSON, and are
quoted back as the blocking reason when the parameter is missing.

**Every number in the three non-empty built-ins is a labelled PLACEHOLDER.**
They are the demo priors, carried over to exercise the machinery. They encode no
knowledge of any well, carry no citation, and their version is `0-placeholder`.
Replace them before presenting any result as a screening outcome. The spread a
`sensitivity` run produces is a property of the placeholders, not of the
subsurface.

## The screening report

`screen_well()` returns a `WellScreeningReport` that splits inputs into
source-derived and assumed, prints `ASSUMED` beside every assumed value, counts
the assumption flags, preserves the temperature method and provenance, lists the
temperatures *not* selected, keeps conflicts visible, and warns when no required
input is source-derived.

## Three distinct states

The funnel never collapses these:

| State | Meaning | Pilot |
| --- | --- | --- |
| source-complete | every required input came from the data | **0** |
| scenario-complete | a scenario supplied the rest | 45 |
| screenable | a config was built and run | 45 |

## Temperature-method comparison

No method is declared globally correct. `compare_temperature_methods()`
re-screens a well once per available reservoir method, varying only temperature,
and reports what each implies:

```
TRECATE|9|ST  (selected: extrapolated_fertl_wichmann)
  extrapolated_fertl_wichmann  452.15 K @ 6247.9 m   P50 = 5.93 Mt
  extrapolated_squarci_taffi   440.15 K @ 6000.0 m   P50 = 6.24 Mt
  non_stabilized               399.15 K @ 5510.0 m   P50 = 7.74 Mt
  -> P50 spread 1.81 Mt (30.5%) from temperature method alone
```

## CLI

The interface stays flat; screening is a mode of the same pipeline.

```bash
ccs-ingest --data-dir data                                     # completeness
ccs-ingest --data-dir data --screen --scenario sensitivity     # funnel
ccs-ingest --data-dir data --screen --scenario central --well "SALUZZO|1"
ccs-ingest --data-dir data --compare-temperature --well "TRECATE|9|ST"
```

`--assumptions` still works: a bare assumption set is wrapped into an ad-hoc
scenario rather than rejected.

Every screening mode (`--screen`, `--compare-temperature`, `--list-incomplete`,
`--emit-configs`, and any run under `--scenario` or `--assumptions`) prints a
`NOT_VALIDATED legacy output (owner decision O2)` header, and its JSON carries
`validation_status: "NOT_VALIDATED"`. Emitted config files stay strict
`ScreeningConfig` documents, so the label is reported on stdout and as
`emitted_configs_validation_status`. The plain completeness report produces no
capacity and carries no label.

## Calling from Python (future web API)

Every function returns a dataclass with `to_dict()`, and no CLI is involved:

```python
from ccs_screen.ingest import WellNormalizer, SENSITIVITY, screen_well, build_funnel

records = WellNormalizer("data").run()
reports = [screen_well(r, SENSITIVITY) for r in records]
payload = {
    "funnel": build_funnel(records, SENSITIVITY, reports).to_dict(),
    "wells": [r.to_dict() for r in reports],
}
```

`payload` is JSON-serialisable as-is, and every screening input in it carries an
`"assumed": true|false` flag.
