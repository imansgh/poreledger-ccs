# Validation evidence

What has been checked, against what, and what it does **not** show. The
checks below concern the software's calculations. They do not validate any
storage estimate, input data or site.

Three different things are kept apart:

| | Meaning | Evidence |
| --- | --- | --- |
| **Calculation implemented and checked** | the code computes the contract's equations correctly | independent re-implementations and reference values (below) |
| **Model validity** | the model's validation conditions hold for given inputs | the per-result `validation_status` (`VALIDATED`, `OUTSIDE_VALIDATED_ENVELOPE`, `UNAVAILABLE`) |
| **Input-data quality** | the inputs are correct for the real site | **not assessed by this tool**; inputs are as declared |

## 1. Independent re-implementation of the chain

`tests/test_independent_calculation_audit.py` re-implements Peng-Robinson with
the Peneloux shift, hydrostatic pressure, the exponential integral and the
capacity equation from the published equations using only `math`. An AST test
enforces that this block never references `ccs_screen`. Phase 11 measured a
worst relative difference of 1.6e-16 (one ulp) against production.
Runs in every CI job.

## 2. CO2 density against Span & Wagner (1996)

Reference: Span & Wagner (1996) equation of state, evaluated with CoolProp
8.0.0 (HEOS backend). Component: `properties.co2_density_kg_m3`
(Peng-Robinson + constant Peneloux shift).

Measured on 2026-10-02 over the **approved validated envelope**, a 35 x 25
grid, 1-35 MPa (absolute) x 280-400 K, 875 points; error = (code - reference)
/ reference:

| Metric | Value |
| --- | --- |
| Mean absolute error | 3.80 % |
| Median absolute error | 2.54 % |
| 95th percentile | 11.23 % |
| Maximum | 13.58 % (35 MPa, 280 K: 1188.8 vs 1046.6 kg/m3) |
| Sub-window 10-35 MPa x 300-400 K | mean 3.26 %, max 11.84 % |

These figures describe the density component inside the envelope only. They
are not the accuracy of a capacity estimate, which also depends on the area,
interval, porosity, efficiency and temperature inputs and on model structure.

Tests: `tests/test_properties_audit.py::test_error_over_the_whole_validated_envelope_against_span_wagner`
(live CoolProp grid; asserts max < 14 %, mean < 4 %, p95 < 12 %), plus fixed
CoolProp-verified reference tables in `tests/test_properties.py` and
`tests/test_properties_audit.py` that need no extra dependency.

**CI:** the `reference-checks` job installs CoolProp and runs these with
`CCS_REQUIRE_REFERENCE_TESTS=1`, which turns a missing CoolProp into a test
failure, so the live comparison cannot pass by being skipped.

## 3. User-assessment path, end to end

`tests/test_assessment.py`:

- **Independent Monte Carlo.** A separate Monte Carlo (100 000 draws, its own
  RNG stream) built from the contract's priors (porosity U(0.10, 0.35), E
  U(0.01, 0.04), brine density U(1020, 1100) kg/m3) and the independent
  Peng-Robinson implementation reproduces the engine's P10/P50/P90 for a user
  assessment within 2-3 % (sampling error), for both named scenarios.
- **Hydrostatics.** Reported P_EOS ranges equal `101325 + rho_b g (z_state -
  z_wl)` computed by hand at the brine-density bounds, for `z_wl = 0` and
  `z_wl` = elevation.
- **Unit conversions.** Exact factors checked; an assessment entered in feet,
  acres and degF gives the same capacity as its metric twin (rel. 1e-9).
- **Shared engine.** A user assessment and the demo well with the same inputs
  produce identical scenario results.
- **Reproducibility.** Same seed, same result; different seed, different draws.
- **Boundaries.** MD, unknown convention, every non-ground datum, missing
  total depth, missing elevation, no or ineligible temperatures, and the
  outside-envelope example each produce the documented status, never a
  reportable estimate.

## 4. Existing approved-model tests

`tests/test_approved_model.py` (temperature selection and tie rules, envelope
checks on absolute pressure, state point above the water level,
reproducibility), `tests/test_temperature_audit.py`,
`tests/test_dimensional_audit.py`, `tests/test_pressure_audit.py`,
`tests/test_monte_carlo_audit.py` and `tests/test_percentile_disclosure.py`
continue to apply unchanged; the user path calls the same functions.

## Limits of this evidence

- Agreement with Span & Wagner within the stated error does not make
  Peng-Robinson exact; outside 1-35 MPa / 280-400 K results are
  `OUTSIDE_VALIDATED_ENVELOPE` by design.
- The priors are literature-constrained or project assumptions; no test can
  show they fit a particular site.
- Synthetic examples demonstrate behaviour, not real-world accuracy.
- No real-site benchmark of capacity exists in this repository.
