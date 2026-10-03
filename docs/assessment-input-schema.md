# Assessment input schema (`ccs-assessment/1`)

The primary way to use this tool is to describe **your own** well or site and
run the approved screening model on it. This page is the contract for that
input, in JSON or CSV. The machine-readable summary is served at
`GET /assessments/contract`.

Templates and examples (also downloadable from the website and from
`GET /assessments/files/{name}`):

| File | What it is |
| --- | --- |
| [`assessment-template.json`](../src/ccs_screen/assessment_data/assessment-template.json) | Empty JSON template |
| [`assessment-template.csv`](../src/ccs_screen/assessment_data/assessment-template.csv) | Empty CSV template with comments |
| [`synthetic-examples.json`](../src/ccs_screen/assessment_data/synthetic-examples.json) | Four **fictional** examples, one per outcome |
| [`synthetic-examples.csv`](../src/ccs_screen/assessment_data/synthetic-examples.csv) | The same examples in CSV (generated from the JSON) |

## What the model needs

The approved Model Contract ([phase13-owner-decision-record.md](phase13-owner-decision-record.md))
computes `M = A * h_g * phi * rho_CO2(P_EOS, T) * E`. Porosity, storage
efficiency and brine density are the approved parameter set's literature or
project priors; **they cannot be overridden** in this workflow. You supply the
rest:

| Field | Required to submit | Required for an approved estimate | Used for |
| --- | --- | --- | --- |
| `id` | yes | - | your identifier, kept verbatim |
| `storage_area` | yes | yes | `A` |
| `storage_interval` (`top`, `base`) | yes | yes | `h_g = base - top`, `z_state = (top + base) / 2` |
| `depth_reference.datum` | yes | must be `ground_level` | depth reference guard (contract C2/O4) |
| `depth_reference.convention` | yes | must be `TVD` | the hydrostatic pressure term needs vertical depth (see below) |
| `total_depth` | no | yes | the temperature rule excludes observations below total depth, and excludes all of them when it is not recorded (M3) |
| `temperature_observations` | no | at least one eligible | the temperature rule (M3 + R1 + C3) |
| `surface_elevation` (reference `msl`) | no | for `SEA_LEVEL_SENSITIVITY` only | `z_wl` of the sea-level scenario |
| `name`, `notes`, `stratigraphy`, `source` on any value | no | - | context and provenance only; stratigraphy is never used by the model |

Anything missing is **reported, never filled in**. A document can be valid and
still produce `UNAVAILABLE`; validation returns *notices* that say in advance
which inputs will cause that and why.

## JSON

```json
{
  "schema_version": "ccs-assessment/1",
  "assessments": [
    {
      "id": "MY-SITE-1",
      "name": "optional display name",
      "storage_area": {"value": 20, "unit": "km2", "source": "optional"},
      "storage_interval": {"top": 1450, "base": 1550, "unit": "m"},
      "depth_reference": {"datum": "ground_level", "convention": "TVD", "source": "optional"},
      "surface_elevation": {"value": 240, "unit": "m", "reference": "msl"},
      "total_depth": {"value": 1650, "unit": "m"},
      "temperature_observations": [
        {"value": 58, "unit": "degC", "depth": 1500, "depth_unit": "m",
         "depth_datum": "ground_level", "depth_convention": "TVD",
         "method": "extrapolated_squarci_taffi", "source": "optional"}
      ],
      "stratigraphy": [{"top": 0, "base": 420, "unit": "m", "description": "optional"}],
      "notes": "optional"
    }
  ]
}
```

- `depth_reference` applies to the interval and the total depth; each
  temperature observation states its own datum and convention.
- `synthetic: true` (and an `example` object) mark fictional data. A document
  must not mix synthetic and non-synthetic assessments.
- Unknown fields are errors (they are named), as is any `schema_version` other
  than `ccs-assessment/1`.

## CSV

Comma-separated, UTF-8, `.` as the decimal separator. Lines starting with `#`
before the header are comments.

**One row per temperature observation. Rows with the same `assessment_id`
form one assessment**, in order of first appearance. Every column that does not
start with `obs_` is assessment-level and must be **identical on every row of
that assessment**; a difference is reported as `CONFLICTING_VALUE` with the
row number. A row whose `obs_*` value cells are empty contributes no
observation (an assessment without observations is one such row).

| Column | Required | Notes |
| --- | --- | --- |
| `schema_version` | yes | `1` |
| `assessment_id` | yes | groups rows |
| `area_value`, `area_unit` | yes | |
| `interval_top`, `interval_base`, `depth_unit` | yes | `depth_unit` also applies to `total_depth` |
| `depth_datum`, `depth_convention` | yes | |
| `assessment_name`, `synthetic`, `total_depth`, `notes` | no | `synthetic`: `true`/`false` |
| `surface_elevation`, `surface_elevation_unit`, `surface_elevation_reference` | no | |
| `area_source`, `interval_source`, `depth_reference_source`, `total_depth_source`, `surface_elevation_source` | no | free text |
| `obs_temperature`, `obs_temperature_unit`, `obs_depth`, `obs_depth_unit`, `obs_depth_datum`, `obs_depth_convention`, `obs_method` | per observation | all seven, or none |
| `obs_source` | no | |

Stratigraphy and example descriptions are JSON-only.

## Units and conventions

| Quantity | Units (exact factors) |
| --- | --- |
| Area | `m2`; `km2` = 1e6 m2; `ha` = 1e4 m2; `acre` = 4046.8564224 m2 |
| Depth, elevation | `m`; `ft` = 0.3048 m |
| Temperature | `K`; `degC`: K = degC + 273.15; `degF`: K = (degF - 32) x 5/9 + 273.15 |

| Setting | Accepted values | Usable by the approved model |
| --- | --- | --- |
| Depth datum | `ground_level`, `rotary_table`, `kelly_bushing`, `msl`, `unknown` | `ground_level` only. Others give `UNSUPPORTED_DEPTH_DATUM`, `unknown` gives `DEPTH_REFERENCE_NOT_ESTABLISHED`. **No datum conversion is applied.** |
| Depth convention | `TVD`, `MD`, `unknown` | `TVD` only. `MD` gives `DEPTH_CONVENTION_NOT_TVD` and `unknown` gives `DEPTH_CONVENTION_NOT_ESTABLISHED`; the model is not evaluated. **MD is never converted or relabelled.** |
| Elevation reference | `msl`, `unknown` | `msl`; `unknown` makes `SEA_LEVEL_SENSITIVITY` unavailable |
| Temperature method | `horner_corrected`, `extrapolated_fertl_wichmann`, `extrapolated_squarci_taffi` (eligible); `non_stabilized`, `raw`, `surface_air_mean`, `unknown` | eligible methods only, inside the interval, ground level, TVD, not below total depth |

**Declared, not verified.** Datums, conventions and every value are taken as
you declare them (`depth_reference.basis = "user_declared"`,
`independently_verified: false` in every result). The tool cannot check
them; a `VALIDATED` result is conditional on them.

## Validation and limits

Errors block evaluation and name the field (`path`) and, for CSV, the `row`.
They include: missing required values; non-numbers, `NaN` and infinities
(also rejected when parsing JSON); unsupported units or values; area <= 0 or
>= 1e12 m2; depths < 0 or deeper than 15 000 m; `top >= base`; temperatures
<= 0 K or >= 1000 K; elevation outside -1000..9000 m; text over 1000
characters; invalid or duplicate identifiers; mixed synthetic and real data;
unknown fields or columns; conflicting CSV rows.

| Limit | Value |
| --- | --- |
| Assessments per request | 50 |
| Temperature observations per assessment | 100 |
| Uploaded file | 200 000 bytes; 5 000 CSV rows |
| Request body on `/assessments/*` | 256 KiB (`CCS_MAX_ASSESSMENT_BODY_BYTES`) |
| Samples | 1-50 000 (default 2 000); seed 0..2^32-1 (default 42) |
| Total realisations per request | 200 000 (assessments x samples) |

## Results

Every result (`POST /assessments/evaluate`) carries the assessment id, the
normalized inputs with their original values and units, provenance
(user-supplied / model-derived / literature-constrained / project assumption),
model path, parameter set and contract, schema version, samples and seed, both
named water-level scenarios with status and diagnostics, an outcome summary
(overall status, main reason, next action), warnings and limitations, and the
synthetic origin when applicable. `summary_csv` is one row per assessment and
scenario: percentile columns are filled **only** for `VALIDATED`; an
`OUTSIDE_VALIDATED_ENVELOPE` diagnostic P50 has its own column,
`diagnostic_p50_mt_not_an_estimate`.

In the CSV summary, user text (`assessment_id`, `assessment_name`) that a
spreadsheet could read as a formula is prefixed with an apostrophe: text whose
first character, or first character after leading whitespace, is `=`, `+`,
`-`, `@`, tab, carriage return or line feed. A name `=1+1` is exported as
`'=1+1`. Numeric columns are never escaped, and the JSON result keeps the text
exactly as entered.

In `result.temperature_selection`, every selected, eligible and excluded
observation carries `input_index`: the position of the submitted observation
in `temperature_observations`. Use it to identify an observation; readings
with equal depth, temperature and method can differ in datum or source.

## Importing a file in the website

The website shows an imported file in an editable form but never repairs it
silently. A field you do not change is sent back exactly as it was in the
file: the schema version (supported or not), wrong types, fields the schema
does not define, and missing units or references. So the backend reports the
same problems on Calculate as on upload, until you correct them. A missing
unit is shown as an empty choice, never as a default, and an unsupported value
is shown as it is. Total depth keeps its own unit, independent of the
interval's. Fields the schema does not define are removed only when you press
"Remove unrecognised fields"; a missing `schema_version` is set only when you
press "Declare the file as ccs-assessment/1". An unsupported schema version
cannot be corrected in the website: no migration is defined. A file with no
list of assessments is not loaded, and your current inputs stay as they are.

A CSV file with row-level problems the form cannot represent (different
assessment-level values on rows of the same assessment, an incomplete
observation row, a row with the wrong number of cells) is shown as a preview
with its row numbers, but calculation is blocked for it: the preview holds
only part of what the file says. The block is enforced by the backend: the
preview carries a `blocked_import` marker, and validation and evaluation
reject any document carrying it (`IMPORT_BLOCKED`). Editing the preview, or
"Remove unrecognised fields", keeps the marker. Correct the file and upload
it again, or start a new assessment or load an example.

Uploaded content is parsed as data only; nothing in it is executed or
interpreted as an instruction. See [data-handling.md](data-handling.md).
