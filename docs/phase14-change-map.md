# Phase 14 — Implementation / Test Change Map

**Phase 14 working document.** The plan below is implemented on this branch;
section 11 records the implementation-level details the plan left open.

| Item | Value |
| --- | --- |
| Branch | `phase14/model-contract-implementation` |
| Base | `417398ea6c10fa851cabfbed0efad3bd5610899a` |
| Frozen contract carried forward | cherry-pick of `bd1670db079239f9553c3defac8ac0b15d34329b` → `d3ac014`; blob identical; approved-text fingerprint `51346f529b48448e42c5515f65db82fb304913edd71a3cd2f060e75e1363cb2b` verified (on the LF text; the working copy is CRLF by checkout) |
| Contract | `docs/phase13-owner-decision-record.md` (authoritative: "Final Gap Closure", "O1 Decision and Owner-Approval Gate", "Owner Approval"). Not modified in Phase 14 |

## 0. Phase 14 owner decisions (O2, O3, O4)

**Terminology.** The approved model is not a single "approved scenario". It is
the Model Contract formulation, selected by the built-in parameter set
`literature-screening-v1`, with the common inputs `area_m2`, `z_top`, `z_base`.
Every approved evaluation produces both named deterministic water-level
scenarios, `GROUND_REFERENCE` and `SEA_LEVEL_SENSITIVITY`, each with its own
status and diagnostics; neither is chosen by the user as an alternative
formulation. Below, "approved model" means that path.

Recorded 2026-09-28. These are Phase 14 scope and implementation decisions by
the owner. They do not modify the frozen Phase 13 Model Contract.

### O2 — Non-literature / placeholder scenario paths: OPTION (a)

| Field | Content |
| --- | --- |
| Decision | Keep the existing non-literature scenario paths, and classify their outputs explicitly as **`NOT_VALIDATED`**. Applies to: the HTTP/API placeholder scenarios `conservative`, `central`, `sensitivity`; scenario/assumption JSON paths accepted by the Python API; scenario/assumption JSON paths accepted by `ccs-ingest`; `ccs-ingest --emit-configs` outputs |
| Rationale | These paths predate the approved contract and do not implement it (net-thickness placeholder or caller `thickness_m`, flat `pressure_pa`, demo E 0.02–0.07, ingestion-time temperature with the 0.85 filter and rank). The owner keeps them operational for compatibility/demo purposes without reclassifying them as validated |
| Implementation consequence | Two explicitly separated paths: **APPROVED MODEL** (`literature-screening-v1`, contract formulation) and **NOT_VALIDATED LEGACY/PLACEHOLDER SCENARIOS** (existing behaviour, unchanged arithmetic, labelled). Legacy outputs carry `validation_status = NOT_VALIDATED` and never the approved-model statuses. No legacy path is migrated to the approved formulation, and none is removed from the public API |
| Affected files | `src/ccs_screen/api.py` (path selection, labelling, per-scenario input spec); `src/ccs_screen/ingest/report.py` (legacy report labelled); `src/ccs_screen/ingest/cli.py` (screen, compare-temperature, emit-configs labelled); `src/ccs_screen/web/app.py`, `web/schemas.py` (`/scenarios` shows `validation_status`; screen responses carry it); `src/ccs_screen/ingest/scenario.py` (placeholder descriptions state `NOT_VALIDATED`) |
| Affected tests | `tests/test_scenario.py`, `tests/test_ingest_cli.py`, `tests/test_api.py`, `tests/test_web_api.py` (legacy-scenario sections: new label assertions; existing numeric expectations for legacy scenarios stay as they are) |
| Explicitly NOT implemented | No migration of legacy paths to the approved formulation; no removal of any legacy path or scenario; no envelope check, `P_atm`, interval or M3 temperature rule added to legacy paths; `ASSUMABLE` (`src/ccs_screen/ingest/assumptions.py:32`) unchanged; ingestion-time temperature derivation (`normalize.py:355–400`), `RESERVOIR_DEPTH_FRACTION` and `TEMPERATURE_METHOD_RANK` retained **for legacy paths only**, documented as not approved |
| O1 | Unchanged. O1 remains specific to `cli._screen` / `DEPLETED_GAS_ANALOG` |

**Consequences derived from O2 (applications of the recorded decision, not new
decisions):**

1. **Legacy inputs are preserved.** Legacy scenarios keep their existing
   caller inputs (`area_m2`, `thickness_m`, legacy net-thickness meaning),
   because O2 preserves their behaviour and forbids migrating them. The approved
   model takes `area_m2`, `z_top`, `z_base` and rejects `thickness_m`. The
   required-inputs endpoint reports the inputs of whichever path the scenario
   belongs to.
2. **Temperature-method comparison** (`api.compare_temperature_methods`,
   HTTP `/wells/{id}/temperature`, `ccs-ingest --compare-temperature`) runs on
   the legacy resolver and legacy temperature machinery, which O2 says must not
   be reclassified as validated. It is kept and labelled `NOT_VALIDATED`
   (diagnostic).
3. **`ccs-ingest --screen`** uses the legacy resolver for every scenario it
   accepts, so its screening output is labelled `NOT_VALIDATED`. (With
   `--scenario literature` it already returns blocked wells, because area and
   thickness are not supplied there.)

### O3 — Frontend scope: IN PHASE 14 SCOPE

| Field | Content |
| --- | --- |
| Decision | Frontend compatibility/update is in Phase 14 scope, limited to compatibility with the approved Model Contract |
| Rationale | The approved API input changes from `thickness_m` to `z_top`, `z_base` (`h_g = z_base − z_top`) and introduces named scenarios and statuses. The Next.js client still sends `thickness_m` and would break against the strict schema |
| Implementation consequence | The client renders the inputs the selected scenario requires (from the required-inputs endpoint): `area_m2`, `z_top`, `z_base` for the approved model (`literature-screening-v1`); `area_m2`, `thickness_m` for legacy scenarios (O2 consequence 1). Results show both named scenarios (`GROUND_REFERENCE` labelled as the project reference scenario, `SEA_LEVEL_SENSITIVITY`), each with its status (`VALIDATED`, `OUTSIDE_VALIDATED_ENVELOPE`, `UNAVAILABLE`) and diagnostics. Validated percentiles are shown only when the API marks them validated. Legacy results are badged `NOT_VALIDATED` |
| Affected files | `frontend/lib/types.ts`, `frontend/lib/api.ts`, `frontend/components/InputForm.tsx`, `InputCard.tsx`, `ScreeningWorkspace.tsx`, `ResultPanel.tsx`, `ProvenancePanel.tsx`, `TemperaturePanel.tsx`, `WellDetail.tsx`, `WarningsPanel.tsx` as needed |
| Affected tests | `frontend/tests/workspace.test.tsx`, `frontend/tests/fixtures.ts`, `frontend/tests/integration.test.ts` (inputs, response shapes, status rendering) |
| Explicitly NOT implemented | No frontend-side scientific default, calculation, conversion or assumption; no value invented when the API returns `UNAVAILABLE` or `NOT_VALIDATED` (the status and diagnostic are displayed instead); no change to styling beyond what the new fields require |

### O4 — Depth datum guard: IMPLEMENT

| Field | Content |
| --- | --- |
| Decision | If an explicitly established depth datum other than ground level is present and the approved contract provides no conversion to the required ground-reference coordinate, return the affected input/result as **`UNAVAILABLE`** with diagnostic **`UNSUPPORTED_DEPTH_DATUM`**. No implicit conversion, no assumed equivalence, no inferred offset |
| Rationale | The approved pressure/water-level formulation is defined in a ground-referenced depth coordinate; the contract specifies no datum conversion. This is a data-validity guard, not a scientific correction |
| Implementation consequence | Depth-reference check for the approved path: `ground_level` → usable; `unknown` → `UNAVAILABLE` (`DEPTH_REFERENCE_NOT_ESTABLISHED`, C2); `msl`, `rotary_table`, `kelly_bushing` → `UNAVAILABLE` (`UNSUPPORTED_DEPTH_DATUM`). Applies to `depth_m` (interval, pressure, TD exclusion) and to temperature-observation depths |
| Affected files | New approved-path module (see §2), `src/ccs_screen/ingest/records.py` (temperature-observation depth reference, default `unknown`) |
| Affected tests | New unit tests for each datum value and for mixed references between `depth_m` and temperature observations |
| Explicitly NOT implemented | No datum conversion logic (`DepthMeasurement.to_msl` is not used by the approved path) |

## 1. Consequence of the frozen contract on real data (not a decision)

Under C2 the depth reference must be formally established. Every ingested
well has `depth_datum = UNKNOWN` (`normalize.py:159, 162, 272, 274, 325`), and
temperature observations carry no depth reference. Implemented faithfully,
**every real well's approved screening returns UNAVAILABLE**
(`DEPTH_REFERENCE_NOT_ESTABLISHED`). This is the recorded consequence ("At
present this applies to every screened well"). Tests asserting real-well
approved capacity numbers migrate to asserting UNAVAILABLE with reasons; the
approved formulation's numerics are tested on synthetic records with an
established ground-level reference.

## 2. Core model and ingestion

| File | Current behaviour | Contract requirement | Planned change |
| --- | --- | --- | --- |
| **New** `src/ccs_screen/approved_model.py` (name indicative) | — | A1–A7, B1, M1–M4, R1, C1–C3, O4, F1 | Pure approved-path functions: interval validation and derivation (`h_g`, `z_state`); depth-reference check (C2, O4); pressure per named scenario `P_EOS = 101 325 + [ρ_lo, ρ_hi]·g·(z_state − z_wl)` with `z_wl = 0` (`GROUND_REFERENCE`) or `z_wl = quota` (`SEA_LEVEL_SENSITIVITY`); temperature selection (M3 + R1 + C3 + Horner-vs-FW guard + below-TD exclusion + in-interval + established reference); per-realisation envelope check on `P_EOS` and T (flag + block, no draw dropped); per-scenario result with status and diagnostics |
| `src/ccs_screen/capacity.py:6–24` | `M = A·thickness_m·φ·ρ·E` | `M = A·h_g·φ·ρ_CO2(P_EOS, T)·E` | Arithmetic unchanged; docstring states the approved thickness term is `h_g` |
| `src/ccs_screen/properties.py` | PR + constant Peneloux; justification "most Italian pilot reservoirs sit below 20 MPa" | E1, E2, C1 | Justification text corrected (premise not supported); envelope constants (1–35 MPa on `P_EOS`, 280–400 K) exposed. No density change |
| `src/ccs_screen/monte_carlo.py` | Percentiles over all draws | M4 | Arithmetic unchanged; the approved path evaluates the envelope over the same draws it passes to `run_capacity_mc` |
| `src/ccs_screen/ingest/scenario.py` | Legacy resolver (TD, gauge, ingestion temperature); `LITERATURE_UNSUPPORTED`; `NET_THICKNESS_POLICY_STATEMENT` | A1, M1, A6, O2 | Legacy resolver unchanged (O2). Literature scenario E rationale reworded per A6. New storage-interval policy statement for the approved path. Placeholder scenario descriptions state `NOT_VALIDATED` |
| `src/ccs_screen/ingest/normalize.py:64, 355–400` | 0.85 filter; FW over ST rank | S2, S3 (approved path); O2 (legacy kept) | Unchanged arithmetic; documented as legacy-only, not approved |
| `src/ccs_screen/ingest/provenance.py:65–76` | Rank table | S2 | Retained for legacy; docstring states it is not an accuracy ranking used by the approved model |
| `src/ccs_screen/ingest/records.py` | `TemperatureObservation` has no depth reference; `ThicknessKind` docstring says `thickness_m` means `NET_STORAGE` | C2, O4, A1 | Add `depth_datum` to `TemperatureObservation` (default `UNKNOWN`); docstring distinguishes approved `h_g` from legacy net thickness |
| `src/ccs_screen/ingest/report.py` | One scenario, one band | O2 | Legacy report labelled `NOT_VALIDATED` |
| `src/ccs_screen/pressure.py:14–18, 92–115` | `DEFAULT_FRACTURE_GRADIENT_PA_M = 15 000`, `DEFAULT_SAFETY_FACTOR = 0.9` | D1, rule B | Both constants and defaults removed; functions take explicit arguments (arithmetic only, no approval implied) |
| `src/ccs_screen/config.py:71–72, 125–126` | Fields default to 15 000 / 0.9 | D1 | Defaults removed (`None`); absent → injectivity outputs `UNAVAILABLE` |
| `src/ccs_screen/__init__.py` | Exports fracture helpers and defaults | Rule B | Default constants no longer exported |

## 3. Public API (`src/ccs_screen/api.py`)

| Area | Planned change |
| --- | --- |
| Input spec | Approved: `area_m2`, `z_top`, `z_base` (`0 ≤ z_top < z_base`, finite; depths in `depth_m`'s ground-level reference); `thickness_m` rejected. Legacy (O2): `area_m2`, `thickness_m` as today |
| `UserInputs` | Approved variant derives `h_g`, `z_state`; `net_to_gross` stays metadata-only; S12 check `0 < h_net ≤ h_g` where a net thickness is declared |
| `NET_TO_GROSS_*` texts | Approved path: ratio of a declared net thickness to `h_g`; never used in calculation. Legacy wording retained for legacy |
| `screen_well` | `literature-screening-v1` → approved model: both named scenarios, each with `validation_status` (`VALIDATED`, `OUTSIDE_VALIDATED_ENVELOPE`, `UNAVAILABLE`) and diagnostics; validated percentiles only when every draw is inside the envelope; `GROUND_REFERENCE` labelled baseline (project reference scenario); `SEA_LEVEL_SENSITIVITY` reported alongside (F1: baseline, individual effect, joint evaluation per scenario; no multiplied correction factors). Legacy scenario → existing behaviour plus `validation_status = NOT_VALIDATED` |
| `compare_temperature_methods` | O2 consequence 2: labelled `NOT_VALIDATED` diagnostic |
| `required_user_inputs`, `screening_funnel`, `list_wells`, `get_well`, `list_scenarios` | Report inputs/status per path; `list_scenarios` gains `validation_status` (`APPROVED_MODEL` / `NOT_VALIDATED`) |
| Interpretation texts | Net-thickness wording replaced for the approved path; S7 statement (percentiles conditional on the declared model, not total accuracy) |

## 4. CLI (`src/ccs_screen/cli.py`)

| Output | Planned change |
| --- | --- |
| Capacity P10/P50/P90/mean, surrogate metrics, `sensitivity_mt_per_sigma` | Labelled `NOT_VALIDATED` (O1); arithmetic unchanged |
| `fracture_pressure_pa`, `allowable_delta_p_pa`, `max_rate_m3_s`, `within_limit` | `UNAVAILABLE` when no gradient/safety factor is supplied (defaults removed). If the caller supplies both explicitly, reported as `NOT_VALIDATED` diagnostics (caller-supplied, not approved) |
| `planned_delta_p_pa`, `initial_pressure_pa` | `NOT_VALIDATED` diagnostics |
| `--fracture-gradient-pa-m`, `--safety-factor` | No default |

## 5. HTTP layer (`src/ccs_screen/web/`)

| Area | Planned change |
| --- | --- |
| `schemas.py` `UserInputsModel` | Accepts `area_m2`, `z_top`, `z_base`, `thickness_m` (all optional at schema level); the API validates the combination per scenario path and rejects mismatches |
| Response models | Named-scenario results with statuses and diagnostics; `validation_status` on legacy responses |
| `app.py` scenario resolution | Unchanged acceptance of built-in names (O2: not removed) |

## 6. Ingest CLI (`src/ccs_screen/ingest/cli.py`)

`--screen`, `--compare-temperature`, `--emit-configs`, `--scenario`,
`--assumptions`: behaviour unchanged; outputs labelled `NOT_VALIDATED` (O2).

## 7. Frontend (`frontend/`, O3)

As recorded under O3. Typecheck (`npm run typecheck`) and unit tests
(`npm test`) run as part of verification; the integration suite runs only if the
API and `data/` are available.

## 8. Tests

**Intentional changes (behaviour genuinely changed by the contract or by O2–O4):**

| Test file | Change | Basis |
| --- | --- | --- |
| `tests/test_capacity_audit.py:154–159` | Approved input is the interval, not net thickness | A1, M1 |
| `tests/test_provenance_audit.py:89–117` | Finding 9.1 characterisation: the contract changed to gross `h_g` (the test states it must then be replaced) | A1, A4 |
| `tests/test_ntg_disclosure.py` | Approved-path fixtures use the interval; the ratio refers to `h_g`; legacy wording kept for legacy | A7, M1, S12, O2 |
| `tests/test_cross_model_audit.py:172–244` | 12.4 characterisation replaced by joint-scenario methodology; product no longer asserted as a correction | F1–F3 |
| `tests/test_temperature_audit.py` | Rank/0.85 tests re-scoped to legacy; new approved-rule tests | S2, S3, M3, R1, O2 |
| `tests/test_pressure_audit.py` | Fracture tests no longer use a default; approved pressure `P_EOS` at `z_state` | D1, B1, M1 |
| `tests/test_injectivity.py`, `tests/test_injectivity_audit.py`, `tests/test_cli.py`, `tests/test_config.py`, `tests/test_dimensional_audit.py`, `tests/test_independent_calculation_audit.py` | Default constants removed; explicit gradient passed where arithmetic is tested; CLI labels | D1, rule B, O1 |
| `tests/test_percentile_disclosure.py:154–213` | Bit-exact baseline pinned to the **legacy** path (unchanged numbers, now labelled `NOT_VALIDATED`) or to UNAVAILABLE under the approved path | C2, O2 |
| `tests/test_real_data_audit.py`, `tests/test_api.py`, `tests/test_web_api.py`, `tests/test_literature_scenario.py`, `tests/test_scenario.py`, `tests/test_monte_carlo_audit.py`, `tests/test_ingest_cli.py` | Approved path: new inputs, named scenarios, UNAVAILABLE on real data; legacy path: labels only | M1, M2, M4, C2, O2 |
| `frontend/tests/*` | Inputs, response shapes, status rendering | O3 |

**Must remain unchanged:** `tests/test_capacity.py`, `tests/test_properties.py`,
`tests/test_properties_audit.py`, `tests/test_monte_carlo.py`,
`tests/test_surrogate.py`, `tests/test_sensitivity_audit.py`,
`tests/test_ingest_units.py`, `tests/test_ingest_identity.py`,
`tests/test_ingest_assumptions.py`, `tests/test_packaging.py`,
`tests/test_priors.py`, and legacy-path numeric expectations (O2).

**New tests:** interval validation/derivation; C2 and O4 statuses; `P_EOS` per
named scenario; M3+R1 rule order (in-interval, established reference, below-TD
exclusion incl. TRECATE 6099 m and 6247.9 m, nearest, shallower on equal
distance, same-method conflict → UNAVAILABLE + diagnostic, ST tie-break,
Horner-vs-FW guard, no interpolation); M4 per-realisation flag + block with no
draw dropped; F1 response shape; legacy `NOT_VALIDATED` labels; CLI
`UNAVAILABLE`/`NOT_VALIDATED`; absence of 15 000 / 0.9.

## 9. Documentation to update after implementation

`README.md`, `docs/http-api.md`, `docs/ingestion.md`,
`docs/scenario-literature-review.md`, `docs/net-to-gross-semantics.md`. The
frozen decision record is not modified.

## 10. Remaining owner/model-design decisions

None. Every row above follows from the frozen contract or from O2, O3 and O4.

## 11. Implementation notes (Phase 14)

Implementation-level details the plan did not fix. None changes the approved
formulation; each is either input hygiene, reporting, or the conservative
reading of an eligibility condition.

| Item | Implementation |
| --- | --- |
| Module | `src/ccs_screen/approved_model.py`; the API selects it only for the built-in `LITERATURE_SCREENING_V1` object (identity). Scenario JSON files, copies and derived scenarios run the legacy path |
| "Exactly the same" depth / distance / value (R1, C3) | Compared with an absolute tolerance of 1e-9 (floating-point hygiene only, so rounding in `(z_top + z_base)/2` cannot split a tie that is exact in real arithmetic) |
| Interval validity | Finite numbers, `0 <= z_top < z_base`; otherwise the request is `blocked`. No rule relates the interval to total depth |
| Interval bounds | `[z_top, z_base]` is closed: an observation exactly at a bound qualifies |
| Envelope bounds | Closed: 1-35 MPa on `P_EOS`, 280-400 K |
| Recorded total depth absent | The below-TD condition cannot be verified, so observations do not qualify (`TOTAL_DEPTH_NOT_RECORDED`) |
| Quota absent | `SEA_LEVEL_SENSITIVITY` is `UNAVAILABLE` (`SURFACE_ELEVATION_UNAVAILABLE`); `GROUND_REFERENCE` is still evaluated |
| Sampling | Porosity, brine density and E are drawn per realisation; `P_EOS` is computed from the drawn brine density. Both named scenarios use the same seed, so they share draws and differ only in `z_wl`. Stream order follows `UniformPriors.sample`, which makes the approved `GROUND_REFERENCE` equal the legacy arithmetic plus `P_atm` at the same state (tested) |
| Out-of-envelope diagnostics | Diagnostic percentiles over every realisation, labelled `NOT_VALIDATED`, computed only if every `P_EOS > 0`; otherwise `EOS_NOT_EVALUABLE`. Never shown in the UI |
| `z_state < z_wl` | Reported as `STATE_POINT_ABOVE_WATER_LEVEL`; the formula is applied as written |
| Individual effect (F1) | `P50(SEA_LEVEL_SENSITIVITY) - P50(GROUND_REFERENCE)`, reported only when both scenarios are `VALIDATED`; `multiplied_correction_factor` is always `null` |
| Approved funnel | Depth-reference readiness counts only; a fleet-level interval is refused (M1 requires a per-well interval) |
| HTTP | `POST /screen` responses are a union discriminated by `model_path` (`APPROVED_MODEL`, `LEGACY_NOT_VALIDATED`); the request passes only the fields actually sent |
| Legacy literature parameters | Reachable through the legacy resolver only via a scenario JSON file (Python API, `ccs-ingest`), e.g. `examples/literature-screening-v1.json`; the audited bit-exact baseline is pinned that way |
