# Synthetic demonstration dataset (existing-data section)

The primary workflow uses your own data and needs none of this. The same four
fictional wells are also offered as **assessment examples** in the user
workflow (`src/ccs_screen/assessment_data/synthetic-examples.json`); a test
keeps the two in agreement (`tests/test_assessment.py::test_examples_agree_with_the_demo_well_dataset`).

`data/ccs-synthetic-demo.json` is a small, deterministic, **entirely fictional**
dataset distributed with the repository so the API and website run from a fresh
clone. It is not derived from any real well, and nothing computed from it
describes a real site.

## What it contains

Four wells, each built to exercise one outcome of the unchanged approved model:

| Well | Declared depth datum | Temperature data | Approved-model outcome |
| --- | --- | --- | --- |
| `SYNTH ALPHA\|1` | ground level | Squarci-Taffi at 1500 m (plus an ineligible non-stabilized reading and a surface air mean) | `VALIDATED` for an interval around 1500 m |
| `SYNTH BETA\|1` | unknown | Squarci-Taffi at 1450 m | `UNAVAILABLE` -- `DEPTH_REFERENCE_NOT_ESTABLISHED` |
| `SYNTH GAMMA\|1` | ground level | Squarci-Taffi at 3500 m, 142 degC | `OUTSIDE_VALIDATED_ENVELOPE` |
| `SYNTH DELTA\|1` | ground level | non-stabilized only | `UNAVAILABLE` -- no eligible temperature |

The datums, depths, elevations and temperatures are *inputs* chosen to show the
model's rules; they do not change the rules. The same Model Contract, priors,
eligible temperature methods and guards apply to these wells as to real ones.

## How it is kept separate and labelled

- A data directory is the demo **only** when it contains
  `ccs-synthetic-demo.json`. The manifest must declare
  `"dataset_kind": "synthetic_demo"` and `"synthetic": true`, and every well
  name must start with `SYNTH`, or it is rejected.
- A directory holding both the manifest and real source files is refused
  (`/ready/existing-data` reports the dataset conflict; `/ready` checks engine readiness), so demo and real data are never combined.
- A missing or broken real dataset never falls back to the demo.
- Every API response from the demo carries `dataset.synthetic: true` and leads
  its warnings with `synthetic_demo_dataset`; every well summary carries
  `synthetic: true`; every field value carries a `SYNTHETIC` note and cites the
  manifest as its source. The website shows a non-dismissible banner.

Field values read from the manifest have provenance `extracted` (read from the
demo file) with confidence `low`; the `SYNTHETIC` note and the `dataset` block,
not the provenance enum, carry the fact that the file itself is fictional.

## Example requests

`requests/` holds request bodies for `POST /wells/{id}/screen`:

| File | Well | Expected |
| --- | --- | --- |
| `approved-validated.json` | `SYNTH ALPHA\|1` | `VALIDATED` / `VALIDATED` |
| `approved-unavailable.json` | `SYNTH BETA\|1` | `UNAVAILABLE` / `UNAVAILABLE` |
| `approved-outside-envelope.json` | `SYNTH GAMMA\|1` | `OUTSIDE_VALIDATED_ENVELOPE` x2 |
| `legacy-not-validated.json` | `SYNTH ALPHA\|1` | `NOT_VALIDATED` |

`python scripts/run_public_demo.py` runs all four without a server. The
expectations are pinned by `tests/test_demo_dataset.py` and
`frontend/tests/demo.integration.test.ts`.

## Changing the demo

Keep it small and fictional. Any new well must start with `SYNTH`, and its
purpose should be one clearly explained model outcome. Update the tables above
and the tests in the same change.

## Release status

These are local synthetic examples, not an already-hosted demo. Version 0.2.0
publication status and the separate Lovable portfolio preview are tracked in
[the main README](../README.md) and [the publication guide](../docs/public-release.md).
