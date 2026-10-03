# Scientific notes for the user-assessment workflow

The user-assessment workflow (2026-10-02) evaluates user data through the
unchanged approved engine: `ccs_screen.assessment` builds an in-memory record
and calls `api._screen_approved` -> `approved_model.evaluate_approved_model`,
the same path as every existing well. No formula, prior, temperature rule,
depth-reference guard, water-level scenario or envelope was changed.

Applying the contract to arbitrary user data raised questions the contract
does not answer explicitly. Each is recorded here with its evidence, kept
apart from implementation bugs. **None is a change to the Model Contract;
items marked "owner confirmation" are interpretations awaiting a recorded
owner decision.**

## Interpretations (owner confirmation requested)

### N1. Depths must be true vertical depth (TVD); MD is not evaluated

- **Evidence.** The contract's pressure is a hydrostatic column,
  `P_gauge = rho_brine * g * (z_state - z_wl)` with `z` "below ground"
  ([phase13-owner-decision-record.md](phase13-owner-decision-record.md),
  rows 7 and section M2, lines 238 and 468). A hydrostatic column height is a
  vertical distance. The contract says nothing about measured depth (MD) versus
  TVD, and no ingested source states it.
- **Implementation.** The assessment layer evaluates only assessments declared
  `TVD`. `MD` or `unknown` returns `UNAVAILABLE` for both named scenarios
  (`DEPTH_CONVENTION_NOT_TVD` / `DEPTH_CONVENTION_NOT_ESTABLISHED`) without
  calling the engine; temperature observations not in TVD are withheld from
  the engine with a notice. MD is never converted, relabelled or assumed equal
  to TVD.
- **Effect.** Can only withhold a result; it never produces one.
- **Inconsistency to resolve.** The existing-data path has no convention field
  and does not apply this gate. It is moot today (every real well is already
  `UNAVAILABLE` for its unknown datum), but the demo wells, which declare a
  ground-level datum, are evaluated without a stated convention.

### N2. A user's explicit ground-level declaration counts as "established" for that assessment

- **Evidence.** Contract C2/O4: only an "established ground-level reference" is
  usable; `unknown` gives `DEPTH_REFERENCE_NOT_ESTABLISHED`. For the ingested
  sources, "established" meant "stated by the source".
- **Implementation.** A user who selects `ground_level` has stated it. The
  result is computed, but every result records
  `depth_reference.basis = "user_declared"` and
  `independently_verified: false`, and carries a `user_declared_inputs`
  warning. The interface never describes the declaration as verified evidence.
- **Owner confirmation.** Whether a declaration by the submitter satisfies C2
  for published results.

## Clarifications (behaviour of the unchanged engine, made explicit)

- **N3. Total depth is required for an approved result.** M3 excludes
  observations deeper than the recorded total depth, and the engine excludes
  every observation (`TOTAL_DEPTH_NOT_RECORDED`) when no total depth is
  recorded. The schema therefore lists total depth as required for an
  approved estimate, and validation warns in advance when it is missing.
- **N4. Ground elevation must be above mean sea level.** `z_wl = quota` in
  `SEA_LEVEL_SENSITIVITY` is the ground elevation above sea level (M2). An
  elevation with an unknown reference is not passed to the engine, so only
  that scenario becomes `UNAVAILABLE`.
- **N5. Input bounds are physical-possibility checks, not priors.** Temperature
  0-1000 K, depth 0-15 000 m and area < 1e12 m2 reuse the existing screening
  config bounds (`config.BOUNDS`); elevation -1000..9000 m spans Earth's land
  surface. They reject impossible values only.
- **N6. Interval below total depth is allowed** with a notice: the contract
  does not require the interval to lie above total depth, only that a selected
  temperature does.

## Formula and conversion audit

Checked for this workflow (tests named in [validation-evidence.md](validation-evidence.md)):

| Item | Finding |
| --- | --- |
| `M = A h_g phi rho E`, units m2 x m x - x kg/m3 x - = kg, /1e9 = Mt | correct; independently re-implemented end to end |
| `P_EOS = 101 325 + rho_b g (z_state - z_wl)`, absolute Pa | correct; range checked against hand calculation from the contract's brine prior |
| `z_state = (z_top + z_base)/2`, `h_g = z_base - z_top` | correct (project convention S1) |
| Temperature degC/degF -> K, ft -> m, km2/ha/acre -> m2 | correct; exact factors, tested |
| Envelope check on absolute pressure and K | correct (existing tests) |
| Percentiles: P10 = 10th percentile = low case | correct (statistical convention, documented) |

**No formula error was found in the implementation.**

## Documentation error found and fixed

The density-accuracy table in the former README (moved to [cli.md](cli.md))
listed wrong Span-Wagner reference densities: e.g. 829.8 kg/m3 at 30 MPa /
350 K, where Span-Wagner (CoolProp 8.0.0) gives 759.0, which also flipped the
sign of the stated error. The code and the machine-verified test tables
(`tests/test_properties.py`, `tests/test_properties_audit.py`) were already
correct. The table was regenerated from CoolProp on 2026-10-02.
