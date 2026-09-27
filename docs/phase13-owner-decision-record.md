# Phase 13 — Owner Decision Record

**Model & Formulation Resolution. Documentation only.**

> **Reading guide.** This record is append-only: later sections supersede
> earlier ones where they say so. The authoritative Model Contract and freeze
> status are in the **last** section, "O1 Decision and Owner-Approval Gate",
> read together with "Final Gap Closure", which it amends. Earlier status
> tables and gate results are kept for traceability only.

This record converts the owner decisions taken on the Phase 13 Master Scientific
Decision Register into a decision record, a Model Contract approval candidate
and a Phase 14 entry checklist.

- No source code, test, API/schema, CLI, numerical default, equation or
  distribution was changed.
- The Scientific Validation Audit (Phases 1–12,
  `docs/scientific-validation-audit.md`) is closed and is not reopened here.
- The frozen Finding 3.1 evidence phase is not reopened.
- No NTG value, gross interval, formation pressure, water level or fracture
  gradient is introduced.

---

## 1. Verified Base

| Item | Value |
| --- | --- |
| Integrated base branch | `eyo/ccs-screening-starter` |
| Integrated commit | `417398ea6c10fa851cabfbed0efad3bd5610899a` (verified against `origin`) |
| Working branch for this record | `phase13/owner-decision-record`, created from the integrated commit |
| Research branch (evidence only; not the base) | `research/finding-3.1-4.2-evidence` @ `70c95d0663fb5df77aea2ce3b3d9f031e7571d22` |
| Hash note | A previously quoted hash containing `…cabfbedef0ad3bd…` does not exist in the repository. The integrated commit is `…cabfbed0efad3bd…`. |

**Source of truth.** The Phase 13 Master Scientific Decision Register and Draft
Model Contract (session report, 2026-09-27), `docs/scientific-validation-audit.md`,
the NETL (2008) *Carbon Sequestration Atlas II*, Appendix B ("Atlas II"), and
CSLF-T-2008-04, both verified in the Finding 3.1 evidence phase.

---

## 2. Decision Status Legend

Every statement below carries one epistemic label and, where it is a decision,
one decision status.

**Epistemic labels**

| Label | Meaning |
| --- | --- |
| **ESTABLISHED** | Supported directly by a primary source or by the repository |
| **INFERRED** | Follows from established facts; not stated by a source |
| **OWNER / MODEL-DESIGN** | A choice made by the project owner. Not a scientific finding |
| **DEFERRED** | Deliberately postponed, with the reason stated |
| **EVIDENCE-BLOCKED** | Cannot be decided numerically without evidence the project does not hold |

**Decision / contract statuses**

| Status | Meaning |
| --- | --- |
| **DECIDED** | Owner decision recorded in this document |
| **PROVISIONAL** | Current behaviour retained; not re-decided in Phase 13 |
| **DEFERRED** | Postponed by the owner; must be decided before the dependent Phase 14 work |
| **EVIDENCE-BLOCKED** | Requires evidence before any numerical implementation |
| **PHASE-14 IMPLEMENTATION** | Decided; implementation belongs to Phase 14 |

---

## 3. Finding 3.1 — Thickness / NTG / E

### Established evidence (frozen; not re-opened)

- **ESTABLISHED.** DOE/NETL's saline equation is `GCO2 = At hg φtot ρ E`, with
  `hg` = "Gross thickness of saline formations for which CO2 storage is assessed
  within the basin or region defined by A" (Atlas II p. 121).
- **ESTABLISHED.** DOE's saline E is
  `Esaline = (An/At)(hn/hg)(φe/φtot) EA EI Eg Ed`; `hn/hg` is labelled
  "Net to gross thickness", 0.25–0.75, "Fraction of total geologic unit that
  meets minimum porosity and permeability requirements for injection"; E must
  include the gross-to-net term because gross thickness is used
  (Atlas II pp. 128–129).
- **ESTABLISHED.** DOE's 0.01–0.04 is an averaged and rounded P15–P85 range from
  Monte Carlo cases; "No rigor was given to selection of the distribution"
  (Atlas II p. 129).
- **ESTABLISHED.** DOE does not establish dividing saline E by NTG (Atlas II;
  the only term removal described is for coal, p. 131).
- **ESTABLISHED.** Current `thickness_m` is a caller-supplied net thickness
  (`src/ccs_screen/api.py:95–105`; `src/ccs_screen/web/schemas.py:80–86`); the
  repository has no normative definition of "net"; `net_to_gross` is metadata
  only (`api.py:409–413`); E ~ Uniform(0.01, 0.04)
  (`src/ccs_screen/ingest/scenario.py:594–595`; `src/ccs_screen/monte_carlo.py:55`).
- **NOT ESTABLISHED.** That current `thickness_m` equals DOE `hn`, or that a
  caller's NTG is the same concept as DOE `hn/hg`. The double-counting claim of
  audit Finding 9.1 is therefore **conditional**.

### Decisions

| ID | Status | Exact decision | Evidence basis | NOT established | Scientific consequence | Implementation consequence | Dependency | Phase 14 action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **A1** | DECIDED (OWNER / MODEL-DESIGN) | `thickness_m` represents the **gross storage-assessment thickness `h_g` of the designated storage-assessment interval**. It is NOT net pay, NOT net reservoir thickness, NOT effective thickness. Capacity: `M = A · h_g · φ · ρ_CO2(P,T) · E` | Atlas II p. 121 (`hg`) | That any existing field value is `h_g` | The gross-to-net reduction is supplied once, by E | Contract change (see A7) | A2, A7, S12, 4.3 | Change `thickness_m` semantics |
| **A2** | DECIDED; per-well values DEFERRED | `h_g` refers to a **designated storage-assessment interval** for each well. The interval is **not** automatically TD. Per-well top/base values are **not** invented in Phase 13; their provenance/rule is established in the implementation/data stage | Audit Finding 4.3 (no storage interval designated) | Any per-well top/base | Defines the interval to which `h_g`, the state point (S1) and the P/T state (S4) refer | Requires an interval representation | **Finding 4.3 / S1**, S4 | Establish designation rule and provenance before use (see §14, M1) |
| **A3** | DECIDED | A project `net_to_gross` value is **not** automatically identified with DOE `hn/hg`. No unsupported Piemonte NTG value is introduced | Evidence phase: equivalence not established | Equivalence; any Piemonte NTG | No NTG enters capacity | None beyond S12 | S12 | Keep NTG out of the capacity equation |
| **A4** | DECIDED | The gross-to-net reduction lives **inside the aggregate E**. Approved: `M = A · h_g · φ · ρ_CO2(P,T) · E`. **Not approved:** `h_net × E`. **Not approved as DOE-supported:** `h_g × (E / NTG)` | Atlas II pp. 121, 128–129 | — | Removes the conditional double count by construction | Equation form unchanged; input meaning changes | A1, A5 | Implement via A7 |
| **A5** | DECIDED | E remains the **aggregate** storage-efficiency term, with the gross-to-net component represented inside E | Atlas II pp. 128–129 | — | E is not decomposed | None | A4 | None beyond documentation |
| **A6** | DECIDED (OWNER / MODEL-DESIGN) | Retain **Uniform(0.01, 0.04)** as a project prior bounded by the DOE-derived P15–P85 range. Documentation must state: *"The Uniform distribution is a project-defined prior over the DOE-derived P15–P85 bounds. It is not claimed to reproduce the DOE probability distribution."* | **ESTABLISHED:** DOE reports P15–P85, not a Uniform (Atlas II p. 129) | That Uniform(0.01, 0.04) reproduces DOE's distribution (it does not: its P15/P50/P85 are 0.0145/0.025/0.0355) | E band is a project prior, not DOE's distribution | Documentation and provenance text | S6, S7 | Update E provenance wording |
| **A7** | DECIDED; PHASE-14 IMPLEMENTATION | `thickness_m` changes from net-thickness to **gross storage-assessment thickness `h_g`** | A1 | — | — | API/schema, validation, tests, characterisation tests, documentation | A1, A2, S12 | Implement contract change |

---

## 4. Finding 4.1 — Pressure Convention

- **ESTABLISHED.** Hydrostatic pressure (`scenario.py:130`) and fracture pressure
  (`src/ccs_screen/pressure.py:97`) are both zero at the depth reference; no
  `P_atm` term exists; Peng–Robinson uses absolute pressure; the model passes a
  gauge-by-construction value (audit Finding 4.1 revision, line 874 onward). The
  cited regional methodology uses 1 atm at the surface (audit Finding 9.7).

| ID | Status | Exact decision | Evidence basis | NOT established | Scientific consequence | Implementation consequence | Dependency | Phase 14 action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **B1** | DECIDED; PHASE-14 IMPLEMENTATION | The EOS receives **absolute** pressure: `P_EOS = P_gauge + P_atm`. Gauge pressure is not retained as the approved EOS input | Audit Finding 4.1 revision §2 | — | Evidence-derived effect sizes (not forecasts): P50 capacity **+0.09% to +0.57%** on the five screened wells; density up to **+2.53%** across the 44-well corpus | EOS input, baseline tests | 4.2 (joint pressure state), 11.1, 12.4 | Add `P_atm` at the EOS input |
| **B2** | DEFERRED | Fracture/headroom pressure convention | Gradient convention undocumented (audit Finding 4.1 revision §3; Finding 4.5) | The fracture gradient's gauge/absolute convention | — | None in Phase 13 | 4.5 (D1) | None until a fracture model is approved |

---

## 5. Finding 4.2 — Formation Head

- **ESTABLISHED.** Operator depth datum (rotary table) and elevations are
  documented for SALUZZO|1, DESANA|1, ASTI|1, MALOSSA|15; workbook `depth_m`
  equals RT TD minus RT height; TRECATE|9|ST is not establishable (audit
  Finding 4.2 / 10.2 revision §1, line 3964 onward; research branch
  `docs/finding-4.2-datum-provenance.md`).
- **ESTABLISHED.** The current code places the brine column's zero at `z`'s
  reference surface (ground for four wells); no water-level variable exists
  (revision §2, line 3996 onward).
- **ESTABLISHED.** The repository contains **no stabilised static water level
  and no stabilised water-bearing formation pressure** for any of the five wells
  (revision §4). Finding 10.2's +1.10% to +15.59% is a **sensitivity**, not a
  measured bias (revision §3).
- **ESTABLISHED.** Formation head (RU5) and Finding 4.2 are the same unknown;
  their effects must not be multiplied (audit lines ~1630–1632). Malossa-field
  pressures are **analogue** evidence only.

| ID | Status | Exact decision | Evidence basis | NOT established | Scientific consequence | Implementation consequence | Dependency | Phase 14 action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **C1** | DECIDED (OWNER / MODEL-DESIGN); bounds DEFERRED | Represent water-level / formation-head uncertainty as an **explicit scenario parameter**, not as an undocumented ground-level assumption. This is a **scenario treatment**, not a claim that any range (for example ground to sea level) is a measured probability distribution. Scenario bounds must be explicitly documented and never presented as measured site data | Revision §§2–4 | The water level at any well | Pressure, CO2 density, capacity and EOS-envelope status become scenario-dependent | Scenario parameter in pressure | B1, S1, S4, 11.1, 12.4 | Implement once bounds and treatment are defined (§14, M2) |
| **C2** | EVIDENCE-BLOCKED | **No per-well hydraulic correction.** No numerical transfer of MALOSSA analogue pressure to screened wells without a separately approved transfer methodology | Revision §5 | Any per-well head | — | None | C1 | None until evidence exists |

**Evidence required before any per-well numerical correction** (audit revision
§5, line 4070 onward), per well, never transferred between wells:
stabilised static formation pressure **or** static water level; measurement
depth; depth datum; pressure datum; gauge/absolute convention; fluid
identification (interval and wellbore column).

---

## 6. Finding 4.5 — Fracture Gradient

- **ESTABLISHED.** `DEFAULT_FRACTURE_GRADIENT_PA_M = 15 000` and
  `DEFAULT_SAFETY_FACTOR = 0.9` have no documented source; no screened well has a
  leak-off or fracture test; no-loss mud bounds at SALUZZO|1, ASTI|1, DESANA|1
  are at or below 15 000 Pa/m; MALOSSA|15 sustained about 20.1 kPa/m with
  partial losses (audit Finding 4.5 revision, line 1272 onward).

| ID | Status | Exact decision | Evidence basis | NOT established | Scientific consequence | Implementation consequence | Dependency | Phase 14 action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **D1** | DECIDED; PHASE-14 IMPLEMENTATION | **Remove** the uncited constant fracture-gradient criterion from the approved scientific model scope. 15 000 Pa/m and SF = 0.9 are **not** an approved, scientifically validated fracture model. They may remain documented historically as existing implementation behaviour | Finding 4.5 revision | Any validated fracture model | Injectivity/headroom leaves the approved scientific scope | CLI headroom and rate ceiling (Findings 5.1, 5.2, 12.1) | B2, 5.x, 12.1 | Decide CLI treatment within Phase 14 |
| **D2** | EVIDENCE-BLOCKED | No well-specific fracture gradient may be invented | Finding 4.5 revision | Any well-specific gradient | — | None | D1 | None until evidence exists |

---

## 7. Finding 11.1 — Peneloux / EOS Envelope

- **ESTABLISHED (audit observations, computed under the pre-Phase-13 state
  definition: gauge pressure, ground-level head, TD state point).**
  14/45 pilot wells are below 20 MPa; 15/44 corpus wells exceed 35 MPa;
  13/44 exceed 400 K; with the shift on, departures from Span–Wagner above
  35 MPa are about **+3.8% to +8.8%** (audit Finding 11.1 revision, line 4395
  onward).
- **ESTABLISHED.** The stated justification "most Italian pilot reservoirs sit
  below 20 MPa" (`properties.py`) is **not supported** by the pilot population.

| ID | Status | Exact decision | Evidence basis | NOT established | Scientific consequence | Implementation consequence | Dependency | Phase 14 action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **E1** | DECIDED | **Keep** Peng–Robinson + constant Peneloux shift. **Declare and enforce** the validated operating envelope: **pressure 1–35 MPa, temperature 280–400 K.** Outside it: no silent extrapolation; the result is **flagged as outside the validated envelope**. The EOS is not replaced | Phase 1 validation envelope; Finding 11.1 revision | Reference-EOS uncertainty above 30 MPa | Out-of-envelope results are disclosed, not presented as validated | Envelope check and flagging/blocking behaviour | B1, C1, S1, S4, temperature (S2–S5, S11) | Implement envelope check |
| **E2** | DECIDED | Correct the Peneloux justification: the "most … below 20 MPa" premise is not supported | Finding 11.1 revision item 1 | — | Documentation | `properties.py` docstring/comment | — | Correct the justification text |

---

## 8. Finding 12.4 — Combined Methodology

- **ESTABLISHED.** The audit's combined factor is a **conditional scenario
  product** (3.1 × 4.1 × 4.2 × 11.1), conditional on a sea-level water level, and
  is "not an estimate of true/reported" (audit line 4683). The characterisation
  helper `combined_factor` excludes 11.1 (`tests/test_cross_model_audit.py:173`)
  and uses the generic NTG range (`tests/test_cross_model_audit.py:45`).

| ID | Status | Exact decision | Evidence basis | NOT established | Scientific consequence | Implementation consequence | Dependency | Phase 14 action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **F1** | DECIDED; PHASE-14 IMPLEMENTATION | Do **not** use the multiplicative product as an estimate of true or reported capacity correction. Approved methodology: **single joint scenario evaluation.** Pressure-state terms (4.1, 4.2/RU5, relevant EOS state) share one coherent state; 3.1 uses the approved gross-thickness formulation; 11.1 is evaluated within the same P/T state. Report (1) baseline, (2) individual systematic effects, (3) joint scenario. Never report `3.1 × 4.1 × 4.2 × 11.1` as a true correction factor | Audit line 4683; RU5 | Any "true" capacity | The joint scenario is a scenario result, not a correction | Reporting; characterisation tests | A, B1, C1, E1, S7 | Implement joint-scenario reporting; update characterisation tests |
| **F2** | DECIDED | The existing product may remain in historical audit material as a **conditional sensitivity/scenario product**, never relabelled as an estimate of true capacity | Audit line 4683 | — | — | None | F1 | None |
| **F3** | PHASE-14 IMPLEMENTATION | The unresolved Copilot comment on PR #4 (`tests/test_cross_model_audit.py:173`, wording at lines 188–219) is a documentation/test-consistency item | PR #4 review | — | — | Test wording | F1 | Reconcile characterisation wording with F1 |

---

## 9. Secondary Decisions

All entries are **OWNER / MODEL-DESIGN** decisions, not newly discovered facts.

| ID | Finding | Status | Exact decision | Evidence basis | NOT established | Consequence | Dependency | Phase 14 action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **S1** | 4.3 | DECIDED | The state point belongs to the designated storage interval, not automatically TD. **PROJECT MODEL CONVENTION** (not a physical law): `z_state = (z_top + z_base) / 2` | Finding 4.3 (state point is TD; no interval designated) | Any per-well `z_top`, `z_base` | P, T and EOS evaluated at `z_state` | A2 | Implement once interval provenance exists (M1) |
| **S2** | 6.3 | DECIDED | No scientific ranking of Fertl–Wichmann over Squarci–Taffi (or the reverse) is claimed without independent evidence. Method selection must be deterministic and provenance-based | Finding 6.3 | A justified ranking | Current rank order loses its scientific status | S3, S4 | Define the deterministic rule (M3) |
| **S3** | 6.4 | DECIDED | The 0.85 reservoir-depth filter is **not** an established physical threshold and is not presented as validated. Phase 14 removes it from the approved formulation unless an evidence-backed basis is supplied | Finding 6.4 | A physical basis for 0.85 | Temperature selection needs a replacement rule | S4 | Remove; define replacement (M3) |
| **S4** | 6.5 | DECIDED | Pressure and temperature use a **common, explicitly documented state-point depth and datum**. No silent datum conversion | Findings 6.5, 12.3 | — | T must refer to `z_state` | S1 | Define how T is obtained at `z_state` (M3) |
| **S5** | 6.6 | DECIDED | Uncorrected BHT is **not** an approved temperature observation when no defensible corrected value exists. If none exists: **temperature = unavailable** (no silent substitution) | Finding 6.6 (up to 18.6% bias) | Which corrections are "defensible" per well | Some wells may become unscreenable | S2, S4 | Implement unavailable-temperature behaviour |
| **S6** | 7.1 | DECIDED | Only variables with an explicitly defined uncertainty distribution and a justified role vary in Monte Carlo. Constants and deterministic conventions are not converted into artificial priors | Finding 7.1 | — | Which priors vary becomes a documented choice | A6, C1 | Apply to prior set |
| **S7** | 7.2 | DECIDED | P10/P50/P90 represent statistical/model uncertainty **conditional on the declared model**. They are not total accuracy and not bounds on systematic bias. Systematic effects are reported separately | Findings 7.2, 12.5 | — | Output semantics fixed | F1 | Update output disclosures |
| **S8** | 7.3 | DEFERRED | CLI demo independent P/T sampling | Finding 7.3 (CLI only) | — | — | — | Phase 14 |
| **S9** | 8.2 | DECIDED | Constant inputs are not ranked as influential sensitivity variables; they remain documented model assumptions | Finding 8.2 | — | Sensitivity output semantics | S6 | Update sensitivity reporting |
| **S10** | 9.8 | DECIDED | Every externally sourced empirical constant or assumption requires provenance/citation. Owner-selected conventions are labelled **PROJECT ASSUMPTIONS**, not literature facts | Finding 9.8 | Citations for currently uncited constants | Provenance contract | — | Apply provenance labels |
| **S11** | 10.1 | DECIDED | The TRECATE\|9\|ST corrected observations below the recorded TD (6087 m), at **6099 m and 6247.9 m**, are **not** used in the approved temperature path while the depth/datum inconsistency is unresolved | Finding 10.1 | Resolution of the inconsistency | TRECATE temperature may become unavailable (S5) | S5 | Exclude the observation |
| **S12** | 12.2 | DECIDED | Thickness relationships are explicitly validated. Where both exist: `0 < h_net ≤ h_g`; `NTG = h_net / h_g` may be used as a **consistency/provenance check only**, never as a second capacity correction | Finding 12.2 | — | Validation rule | A1, A3 | Implement relational validation |

---

## 10. Final Model Contract

**Approval candidate. Not approved by this document.**

| # | Item | Contract content | Status |
| --- | --- | --- | --- |
| 1 | Model purpose | Scenario-based volumetric screening; not a site-specific estimate (existing API interpretation block) | PROVISIONAL |
| 2 | Area | Caller-supplied structural closure area; required; never inferred from licences (`api.py:81–94`). DOE's E includes a basin-scale area term (`An/At`); the scale mismatch is disclosed (`api.py:108–134`) but not resolved in Phase 13 | PROVISIONAL |
| 3 | Thickness | `thickness_m` = gross storage-assessment thickness `h_g` of the designated interval (A1, A7) | DECIDED |
| 4 | Storage interval | Designated storage-assessment interval; not automatically TD (A2). Designation rule and source/provenance of `z_top`, `z_base` not yet defined (M1) | DEFERRED |
| 5 | NTG | No NTG in capacity; no Piemonte NTG value; `NTG = h_net/h_g` as consistency check only (A3, S12) | DECIDED |
| 6 | Porosity | Uniform(0.10, 0.35), Donda et al. (2011); read as total porosity by the audit (Finding 9.2) | PROVISIONAL |
| 7 | Pressure | Absolute EOS input: `P_EOS = P_atm + P_gauge`, with `P_gauge = ρ_brine · g · (z_state − z_wl)`, where `z_wl` is the scenario water-level depth (B1, C1, S1) | DECIDED |
| 8 | Water level / formation head | Explicit scenario parameter (C1). Scenario bounds and treatment (discrete scenarios vs sampled) not yet defined (M2). Per-well correction evidence-blocked (C2) | DEFERRED |
| 9 | State-point depth | `z_state = (z_top + z_base)/2`, PROJECT MODEL CONVENTION (S1); depends on row 4 | DECIDED |
| 10 | Temperature | Deterministic, provenance-based selection (S2); no 0.85 filter (S3); common state point and datum with pressure (S4); uncorrected BHT excluded, else unavailable (S5); TRECATE below-TD observation excluded (S11). The rule for obtaining T at `z_state` and the deterministic method-selection rule are not yet defined (M3) | DEFERRED |
| 11 | CO2 EOS | Peng–Robinson + constant Peneloux shift, retained; justification corrected (E1, E2) | DECIDED |
| 12 | EOS operating envelope | 1–35 MPa, 280–400 K; no silent extrapolation; out-of-envelope results flagged (E1). Flag-only vs blocking not yet specified (M4) | PHASE-14 IMPLEMENTATION |
| 13 | Brine density | Uniform(1020, 1100) kg/m³ | PROVISIONAL |
| 14 | Storage efficiency E | Aggregate DOE-style E containing the gross-to-net term (A4, A5) | DECIDED |
| 15 | E statistical interpretation | Uniform(0.01, 0.04) is a project-defined prior over DOE's P15–P85 bounds; not DOE's distribution (A6) | DECIDED |
| 16 | Monte Carlo distributions | Only variables with an explicit distribution and justified role vary (S6). E: DECIDED (A6). Porosity and brine density: current priors retained | PROVISIONAL |
| 17 | Dependency structure | P and T share one state point and datum (S4); pressure-state terms form one joint scenario (F1) | DECIDED |
| 18 | Output percentiles | P10/P50/P90 on the statistical convention; conditional on the declared model; not total accuracy (S7) | DECIDED |
| 19 | Systematic-effect reporting | Reported separately from the Monte Carlo band (S7, F1) | DECIDED |
| 20 | Combined methodology | Single joint scenario; report baseline, individual effects, joint scenario; never a product as a true correction (F1, F2) | PHASE-14 IMPLEMENTATION |
| 21 | Fracture/injectivity scope | Uncited constant fracture criterion removed from approved scope (D1); well-specific gradient evidence-blocked (D2); headroom convention deferred (B2) | PHASE-14 IMPLEMENTATION |
| 22 | Provenance | Citations required for external constants; owner conventions labelled PROJECT ASSUMPTIONS (S10) | DECIDED |
| 23 | Known limitations | §13 of this record | DECIDED |
| 24 | Deferred items | §§11–12 of this record | DEFERRED |

---

## 11. Evidence-Blocked Items

| Item | Required evidence | Status |
| --- | --- | --- |
| Per-well formation-head (water-level) correction (C2) | Per well: stabilised static formation pressure or static water level; measurement depth; depth datum; pressure datum; gauge/absolute; fluid identification | EVIDENCE-BLOCKED |
| Transfer of MALOSSA analogue pressure (C2) | A separately approved transfer methodology, plus the above | EVIDENCE-BLOCKED |
| Well-specific fracture gradient (D2) | Leak-off or fracture test per well | EVIDENCE-BLOCKED |
| Any numerical Piemonte NTG (A3) | Not needed by the approved formulation; any value would need its own evidence | EVIDENCE-BLOCKED |

---

## 12. Phase 14 Deferred Implementation

None of the following is implemented in Phase 13.

- API/schema change of `thickness_m` semantics to `h_g` (A7), with validation,
  tests, characterisation tests and documentation.
- Storage-interval representation and `z_state` (A2, S1), once M1 is defined.
- Absolute EOS pressure input (B1).
- Water-level scenario implementation (C1), once M2 is defined.
- EOS envelope enforcement and flagging (E1), once M4 is defined; Peneloux
  justification correction (E2).
- Temperature-path changes (S2–S5, S11), once M3 is defined.
- Monte Carlo prior set (S6), output and sensitivity disclosures (S7, S9),
  provenance labelling (S10), relational thickness validation (S12).
- Joint-scenario reporting (F1) and characterisation-test updates (F3).
- CLI fracture/injectivity treatment (D1, B2).
- Findings **5.1, 5.2, 7.3, 12.1**.

---

## 13. Scientific Limitations

- E is a generic North American aggregate; its gross-to-net component is not a
  Piemonte value.
- The E prior is project-defined over DOE's P15–P85 bounds and does not
  reproduce DOE's distribution.
- DOE's E contains a basin-scale area term; the project applies it with a
  closure-scale area (disclosed, not resolved).
- No well has a measured formation head; pressure is a declared scenario, not a
  measurement.
- No well has a measured fracture gradient; injectivity is outside the approved
  scientific scope.
- The EOS is validated only within 1–35 MPa and 280–400 K; the reference-EOS
  uncertainty above 30 MPa is not quantified.
- No stabilised bottom-hole temperature exists in the data; approved-path
  temperatures may be unavailable for some wells.
- The CO2 stream is modelled as pure CO2.
- P10/P50/P90 exclude systematic effects by definition.
- The Finding 11.1 envelope counts were computed under the pre-Phase-13 state
  definition (gauge pressure, ground-level head, TD state point); they are audit
  observations, not a forecast of counts under the approved contract.

---

## 14. Phase 14 Entry Conditions

### Definitions still required before implementation (owner decisions)

These are not evidence gaps. Each changes equations or inputs, so an
implementer cannot choose them without making a scientific decision.

| ID | Missing definition | Affects |
| --- | --- | --- |
| **M1** | Designation rule and source/provenance of the storage-assessment interval (`z_top`, `z_base`, hence `h_g` and `z_state`), including its depth convention and datum | Rows 3, 4, 7, 9, 10 |
| **M2** | Water-level scenario bounds and their treatment (discrete named scenarios vs a sampled parameter) | Rows 7, 8, 12, 16, 20 |
| **M3** | Rule for obtaining temperature at `z_state`, and the deterministic method-selection rule that replaces the ranking and the 0.85 filter | Rows 10, 12 |
| **M4** | Out-of-envelope behaviour: flag-only, or flag and block | Rows 12, 20 |

### Formulation freeze gate

| # | Question | Answer |
| --- | --- | --- |
| 1 | Is the capacity equation defined? | **YES** — `M = A · h_g · φ · ρ_CO2(P_EOS, T) · E` |
| 2 | Is thickness semantics defined? | **YES** — A1 |
| 3 | Is the storage interval policy defined? | **NO** — the principle is decided (A2, S1), but the designation rule and source of `z_top`/`z_base` are not (M1) |
| 4 | Is pressure convention defined? | **YES** — B1 (absolute at the EOS); fracture convention deferred with fracture outside the approved scope (B2, D1) |
| 5 | Is formation-head policy defined? | **NO** — the scenario treatment is decided (C1), but its bounds and discrete-vs-sampled treatment are not (M2) |
| 6 | Is EOS and operating envelope defined? | **YES** — E1; the flag-vs-block behaviour is open (M4) |
| 7 | Is E interpretation defined? | **YES** — A5, A6 |
| 8 | Is uncertainty treatment defined? | **YES** — S6, S7; porosity and brine density priors retained as PROVISIONAL |
| 9 | Is combined methodology defined? | **YES** — F1; its scenario inputs depend on M2 |
| 10 | Are evidence-blocked items explicitly isolated? | **YES** — §11 |
| 11 | Are Phase 14 implementation items explicitly isolated? | **YES** — §12 |
| 12 | Can implementation start without making a new scientific decision? | **NO** — M1, M2, M3 and M4 must be decided first |

**Result:**

NOT READY FOR MODEL CONTRACT APPROVAL

### Checklist to enter Phase 14

1. Owner decisions M1–M4 recorded in this document.
2. Every Model Contract row DECIDED, PROVISIONAL (accepted as such),
   DEFERRED with reason, EVIDENCE-BLOCKED or PHASE-14 IMPLEMENTATION.
3. Explicit owner approval of the Model Contract.
4. Formulation freeze: equations, input contract, distributions and outputs
   fixed in writing.
5. A written list of baseline and characterisation tests expected to change
   (including `tests/test_capacity_audit.py:154–159`,
   `tests/test_provenance_audit.py:107–117`, `tests/test_ntg_disclosure.py`,
   `tests/test_cross_model_audit.py`).
6. Phase 14 branches from `417398ea6c10fa851cabfbed0efad3bd5610899a` (or its
   approved successor), never from `research/finding-3.1-4.2-evidence`.

---

## Final Decision Gate — M1–M4

*Added 2026-09-28. Documentation only. Sections 1–14 above are unchanged; this
section supersedes their M1–M4 entries and the §14 freeze result. Nothing here
is an owner choice: each item is analysed to the point where the owner can
choose. No top/base value, water level, temperature correction or envelope
behaviour has been adopted.*

**Data inspected (read-only).** GEOTHOPICA workbook
`data/Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx`, sheets `Lito-Stratigrafie`
(178 rows; columns `nome, nomeunita1, nomeunita2, top, bottom, litologia, rango,
da età relativa, a età relativa`), `Temperature` (452 rows; `profondità,
temperatura, tempo circolazione, tempo stop, tipo di misura`) and `Anagrafica`
(46 rows); ingestion in `src/ccs_screen/ingest/normalize.py:219–248` (intervals)
and `:355–400` (temperature); method rank in
`src/ccs_screen/ingest/provenance.py:55–86`.

### M1 — Storage-assessment interval

**1. Current state.** `thickness_m` is caller-supplied; no interval is
designated; the state point is TD (Finding 4.3). Ingestion stores each
`Lito-Stratigrafie` row as a `StratigraphicInterval(top_m, bottom_m, lithology,
age)`, documented as "one chronostratigraphic unit as logged, in metres
along-hole" (`src/ccs_screen/ingest/records.py:99–110`). `gross_thickness_m` is
the bottom-top of the deepest logged unit (`normalize.py:336–351`). Decisions
A1, A2 and S1 require `h_g` and `z_state = (z_top + z_base)/2` from a
designated interval that is not automatically TD.

**2. Decision question.** By what rule, and from what source, are `z_top` and
`z_base` of each well's storage-assessment interval obtained?

**3. Evidence already established.**
- The workbook holds, per well, 3–7 chronostratigraphic/lithological
  **megaunits** with top/bottom, a qualitative lithology string, an age and, for
  some wells, a formation name and `rango`. Screened wells: SALUZZO 1, three
  units, the deepest 422.8–1527.5 m `CIOTTOLI E SABBIE`; DESANA 1, four, deepest
  2126.4–3224.9 m; ASTI 1, three, deepest 370–1250 m; MALOSSA 15, seven named
  formations, deepest 5136–5491 m `MAIOLICA, ROSSO AMMONITICO`; TRECATE 9ST,
  four, deepest 5468–6087 m.
- **No field designates a reservoir, storage or seal interval.** Lithology is
  qualitative (for example `SABBIE E ARGILLE`); no porosity, permeability,
  salinity or seal attribute exists in the workbook.
- DOE defines a saline formation assessed for storage as "a porous and permeable
  body of rock containing water with total dissolved solids (TDS) greater than
  10,000 parts per million (ppm)", which "can include more than one named
  geologic formation or be defined as only part of a formation", with a caprock
  and depth exceeding 800 m (Atlas II p. 120).
- **The depth reference of the tops is not uniform across sheets.** Tops are
  along-hole (`records.py:100`). For ASTI 1 the deepest `Lito-Stratigrafie`
  bottom (1250.0 m) equals the rotary-table TD, while the `Anagrafica` depth
  (1247.0 m) is RT − 3.0 m; the workbook does not use one reference across
  sheets (research branch `docs/finding-4.2-datum-provenance.md` §4).
  TRECATE|9|ST's datum is not establishable.
- Operator composite logs (`data/PDF/`) carry finer formation tops and
  descriptions for some wells (for example SALUZZO 1: Molare Formation from
  598.0 m RT), documented on the research branch. None designates a storage
  interval.

**4. Evidence NOT established.** Which unit, or part of a unit, at any screened
well meets DOE's storage definition (porous and permeable, TDS > 10,000 ppm,
caprock); any per-well reservoir or seal pick; a single depth reference for
`Lito-Stratigrafie`.

**5. Options.**

| Option | Scientific meaning | Data requirement | Effect on `h_g` | Effect on `z_state` | Effect on P and T | Implementation consequence |
| --- | --- | --- | --- | --- | --- | --- |
| **M1-A** Deterministic rule over existing units (for example "the logged unit containing TD") | A **project convention** that a whole megaunit is the assessed formation. Existing data cannot show that the unit is porous, permeable, saline and sealed | Existing workbook units; a declared depth reference per sheet | Whole-unit thickness (hundreds of metres) | Unit midpoint | Evaluated at the unit midpoint | Rule in ingestion; depth-reference reconciliation |
| **M1-B** Continue using TD | State point at TD; no interval | None | Undefined | TD | As today | None. **Inconsistent with recorded decisions A2 and S1** |
| **M1-C** Explicit per-well `z_top`/`z_base` inputs with declared provenance | The interval is a **caller designation**, as area and thickness are today | Caller supplies interval, depth reference and provenance; no project default | `z_base − z_top` (or a supplied `h_g` checked against it) | Midpoint of the supplied interval | Evaluated at that midpoint | API/schema inputs, validation (S12), provenance |
| **M1-D** `h_g` unavailable where no defensible interval exists | No capacity without a designated interval | None | Unavailable | Unavailable | Not evaluated | Blocking behaviour; combinable with M1-A or M1-C |

**6. Scientific consequence.** M1-A produces numbers without inventing values,
but asserts by convention that a chronostratigraphic megaunit is the storage
formation. That is a geological claim the data do not support: the audited
megaunits are 355–1105 m thick. M1-C places the geological judgement with the
caller, where `area_m2` and `thickness_m` already sit, and keeps the project
from inventing it. M1-D prevents unsupported output. M1-B contradicts A2 and S1.

**7. Implementation consequence.** M1-A: ingestion rule plus depth-reference
reconciliation. M1-C: new required inputs, schema, validation and provenance.
M1-D: blocked status and reasons. In every case `z_state` feeds pressure,
temperature (M3) and the envelope check (M4).

**8. Recommended contract wording** (for the owner to adopt or amend; not
adopted here):
- *If M1-C, with M1-D:* "The storage-assessment interval is designated per well
  by the caller as `z_top` and `z_base`, with a declared depth reference and
  provenance. `h_g = z_base − z_top` in that reference. No interval is inferred
  from chronostratigraphic units or TD. Where no interval is supplied, `h_g` and
  capacity are unavailable."
- *If M1-A:* "The storage-assessment interval is, by project convention, [rule].
  This convention does not establish that the interval meets DOE's storage
  criteria (Atlas II p. 120)."

**9. Status:** **READY FOR OWNER DECISION.** A geologically justified per-well
interval pick, as opposed to a convention or a caller designation, is
**EVIDENCE-BLOCKED**: it would need per-well reservoir-quality, salinity and
seal evidence that the project does not hold.

### M2 — Water-level scenario

**1. Current state.** `P = ρ_brine · g · z` with `z` below ground, so the water
level is implicitly at ground (Finding 4.2 / 10.2 revision §2). Decision C1
makes the head an explicit scenario parameter.

**2. Decision question.** Which water-level scenario or scenarios does the model
define, and are they deterministic scenarios or a sampled parameter?

**3. Evidence already established.**
- Ground elevation `quota` exists for every well; for four wells `depth_m` is
  below ground (revision §1). A sea-level water level corresponds to
  `P_gauge = ρ_brine · g · (z_state − quota)`, which is the Finding 10.2 shift
  (revision §3).
- Finding 10.2's +1.10% to +15.59% is the capacity **sensitivity** to moving the
  water level from ground to sea level; its direction as an error is not
  established.
- **No stabilised water-bearing pressure or static water level exists** for any
  screened well (revision §4). Malossa-field pressures (about 102.6–106.5 MPa
  at the MALOSSA|15-equivalent depth) are analogue evidence, and whether to
  transfer them is an owner methodology decision (RU5, audit ~1610–1640).
- The RU5 pressure multiplier `k` (sensitivity S-2) is explicitly "not an
  evidence-based pressure estimate".

**4. Evidence NOT established.** The head at any well; that ground and sea level
**bound** the true head (the head could lie above ground or below sea level, or
be overpressured as the Malossa analogue suggests); any probability
distribution over head.

**5–6. Options and consequences.**

| Option | Uncertainty or sensitivity? | Enters Monte Carlo? | Joint P/T effect | Scenario or distribution? | Bounds supported by evidence? |
| --- | --- | --- | --- | --- | --- |
| **M2-A** Named deterministic scenarios: `ground` (`z_wl = 0`) and `sea-level` (`z_wl = quota`) | Sensitivity | No; each scenario is a separate Monte Carlo run | Pressure changes per scenario; temperature unchanged (point value); EOS density and envelope status per scenario | Scenario bracket | The scenario **definitions** are computable from `quota`; they are **not** bounds on the true head |
| **M2-B** Continuous sampled head | Uncertainty | Yes | As A, sampled | Probability distribution | **No**: no distribution is evidenced, and it conflicts with S6 |
| **M2-C** Ground-level baseline plus an explicit sea-level alternative | Sensitivity | No | As A | Baseline plus scenario | As A; designating ground as "baseline" is a convention, not evidence |
| **M2-D** No hydraulic scenario until evidence exists | — | — | — | — | Conflicts with recorded decision C1 |

**7. Implementation consequence.** M2-A or M2-C: a scenario parameter in the
pressure path, one Monte Carlo run per scenario, a per-scenario envelope check
(M4) and joint-scenario reporting (F1). M2-B: a new prior, which the evidence
does not support. M2-D: none. For TRECATE|9|ST the sea-level scenario needs its
depth reference, which is not establishable.

**8. Recommended contract wording** (not adopted):
"Water level is a declared scenario parameter. Two named deterministic scenarios
are defined: `ground` (`z_wl = 0`) and `sea-level` (`z_wl = quota`). They form
a **scenario bracket for sensitivity**, not bounds on the true formation head
and not a probability distribution; the head is not sampled in Monte Carlo.
[If M2-C: the `ground` scenario is the reporting baseline by convention.] No
analogue or overpressure scenario is defined without an approved transfer
methodology."

**9. Status:** **READY FOR OWNER DECISION** between M2-A and M2-C. M2-B is
unsupported and M2-D contradicts C1. The per-well head remains
**EVIDENCE-BLOCKED** (C2).

### M3 — Temperature selection rule

**1. Current state.** `_derive_temperature` keeps non-surface observations,
restricts them to `depth ≥ 0.85 × deepest`, and picks the best rank
(`HORNER 0`, `FERTL_WICHMANN 1`, `SQUARCI_TAFFI 2`, `NON_STABILIZED 3`,
`RAW 4`, `UNKNOWN 5`; `SURFACE_AIR 99` excluded), breaking ties by greater
depth, with no depth correction (`normalize.py:355–400`;
`provenance.py:68–76`). Decisions S2, S3, S4, S5 and S11 remove the scientific
status of the FW/ST order, remove the 0.85 filter, tie temperature to
`z_state`, exclude uncorrected BHT and exclude the TRECATE below-TD observation.

**2. Decision question.** Which deterministic rule selects the temperature at
the approved state point `z_state`?

**3. Evidence already established.**
- Screened-well temperature records (workbook `Temperature`):
  - **no Horner-corrected value** at any screened well;
  - Squarci–Taffi values at every screened well, mostly at round depths (300,
    500, 1000 m and so on) and at the BHT depth;
  - Fertl–Wichmann values only at MALOSSA 15 (4745, 5387 m) and TRECATE 9ST
    (5510, 6099, 6247.9 m);
  - non-stabilised BHTs at every well.
- The audit found ranks 0 (Horner), 3 (non-stabilised), 5 (unknown) and 99
  (surface air) "defensible on general grounds", and the Fertl–Wichmann over
  Squarci–Taffi order **unjustified**; no methodological comparison of the two
  was located (audit Finding 6.3, ~2344–2376).
- TRECATE|9|ST has TD 6087.0 m. Observations exist at **6099 m** (FW 168 °C;
  non-stabilised 165 °C) and at **6247.9 m** (FW 179 °C; non-stabilised
  161 °C). **Both depths lie below TD.** Finding 10.1 flags only 6247.9 m
  (audit ~3862–3875).

**4. Evidence NOT established.** Which of FW or ST is more accurate; any
temperature exactly at `z_state` (observations are at discrete depths); the
geothermal gradient between observations.

**5–6. Options and consequences.**

| Option | Exact rule | Multiple observations | Outside the interval | Uncorrected BHT | TRECATE | Envelope consequence |
| --- | --- | --- | --- | --- | --- | --- |
| **M3-A** Nearest corrected observation to `z_state` within the interval | Among corrected observations (Horner, FW, ST) inside `[z_top, z_base]`, take the one nearest `z_state` | Nearest wins; an FW/ST tie at equal distance needs a declared tie-break | Not used | Excluded (S5) | Below-TD observations excluded | Temperature fixed per well; envelope checked at that value |
| **M3-B** Applicability hierarchy without an accuracy ranking | Class 1: Horner. Class 2: empirical corrections (FW, ST), **unranked**. Non-stabilised, raw, unknown and surface-air values are never selected. Within a class, M3-A's proximity rule; remaining FW/ST ties need a declared neutral rule | As M3-A, plus the class order | As M3-A | Excluded | As M3-A | As M3-A |
| **M3-C** Corrected observation required within the interval, otherwise unavailable | As M3-A or M3-B, but if no corrected observation lies in `[z_top, z_base]`, temperature is **unavailable** | As chosen | Not used; no extrapolation | Excluded | As M3-A | Wells without an in-interval corrected temperature are not screened |
| **M3-D** Keep the current rank only where its basis is documented | Ranks 0, 3, 5 and 99 have a documented general basis; **FW over ST does not** | — | — | — | — | Cannot be kept as it stands under S2 |
| **M3-E** Interpolate between bracketing corrected observations (a convention) | Linear interpolation in depth between the nearest corrected observations above and below `z_state`, same method only; no extrapolation | The bracketing pair | Allowed only as bracketing endpoints | Excluded | Below-TD excluded | Temperature at `z_state` by convention |

Declared neutral FW/ST tie-break candidates (the owner chooses one; none is an
accuracy claim):
- **(i)** report both, and treat temperature as a **named temperature scenario
  pair**;
- **(ii)** temperature unavailable when FW and ST disagree at equal proximity;
- **(iii)** a provenance preference, such as the project's regional-over-generic
  `EvidenceClass` order (audit Finding 6.3 notes that Squarci–Taffi belongs to
  the Italian/GEOTHOPICA lineage). This is a provenance rule, not an accuracy
  ranking, and must be labelled as such.

**7. Implementation consequence.** Replace the 0.85 filter and rank ordering in
`_derive_temperature`; add interval-aware selection, unavailable-temperature
blocking and the below-TD exclusion rule. M3-E adds an interpolation step, which
is a declared convention, not a correction.

**8. Recommended contract wording** (not adopted):
"Temperature at `z_state` is taken from corrected observations only
(Horner-corrected, Fertl–Wichmann, Squarci–Taffi). Non-stabilised, raw, unknown
and surface-air values are never selected. [Selection: M3-A nearest, or M3-E
bracketing interpolation] within `[z_top, z_base]`. Fertl–Wichmann and
Squarci–Taffi are not ranked by accuracy; where they conflict, [tie-break (i),
(ii) or (iii)]. Observations deeper than the recorded TD are excluded. If no
corrected observation satisfies the rule, temperature is unavailable. No
empirical correction is introduced."

**9. Status:** **READY FOR OWNER DECISION.** It can be resolved as a project rule
without new evidence, but cannot be applied until M1 is decided.

### M4 — EOS-envelope behaviour

**1. Current state.** No envelope check exists. Decision E1 declares the
validated envelope as 1–35 MPa and 280–400 K, with no silent extrapolation and
out-of-envelope results flagged.

**2. Decision question.** What happens when a state point, or a Monte Carlo draw,
falls outside the envelope?

**3. Evidence already established.**
- The envelope is the Phase 1 **validation** range, not a boundary of physical
  impossibility: Span & Wagner is valid from the triple point to 1100 K at
  pressures up to 800 MPa (audit Finding 11.1 revision, "Reference
  uncertainty").
- Outside the envelope the model **extrapolates**, with shift-on departures of
  about +3.8% to +8.8% above 35 MPa.
- Pressure varies between draws (brine density 1020–1100 kg/m³) and between M2
  scenarios; temperature is a point value.
- *Conditional observation:* if the designated interval were the deepest logged
  unit, every corrected temperature in that unit at MALOSSA 15 (FW 143 °C,
  416 K, at 5387 m) and TRECATE 9ST (FW 156 °C, 429 K; ST 167 °C, 440 K)
  exceeds 400 K.

**4. Evidence NOT established.** The density error outside the envelope beyond
the Span–Wagner comparison; the reference-EOS uncertainty above 30 MPa.

**5–6. Options and consequences.**

| Option | Scientific meaning | Extrapolation? | P10/P50/P90 | Sample count | Selection bias | Deterministic outputs |
| --- | --- | --- | --- | --- | --- | --- |
| **M4-A** Flag only | Result reported and marked as outside the validated envelope | Yes, disclosed | Unchanged | Unchanged | None | Flag carried; value reported |
| **M4-B** Flag and block | No capacity reported outside the envelope | Prevented | None reported | — | None | Blocked, with the reason |
| **M4-C** Flag and drop out-of-envelope draws | Statistics conditional on the in-envelope subset | Partly prevented | Truncated distribution | Variable | **Yes**: out-of-envelope draws are not physically impossible, so dropping them biases the percentiles | Deterministic runs become all-or-nothing |
| **M4-D** Informational only | Envelope documented but not acted on | Yes, silent at result level | Unchanged | Unchanged | None | No flag. **Contradicts recorded decision E1** |

Where the check is evaluated also needs a declared rule:
- **(a)** at each M2 scenario's deterministic state point (central brine
  density);
- **(b)** per draw, reporting the fraction of draws outside the envelope;
- **(c)** flagging or blocking if any draw is outside.

**7. Implementation consequence.** M4-A or M4-B: an envelope check with a flag or
blocked status per scenario; M4-B adds reasons. M4-C: sample filtering and a
variable sample count. In every case: disclosure text, and per-scenario status
through M2.

**8. Recommended contract wording** (not adopted):
"The EOS is validated only for 1–35 MPa and 280–400 K. This is a validation
boundary, not a physical limit. The envelope is checked at [rule (a), (b) or
(c)]. Outside it, [M4-A: the result is reported and flagged 'outside validated
EOS envelope — extrapolated' / M4-B: capacity is not reported and the result is
blocked with that reason]. Monte Carlo draws are never silently removed."

**9. Status:** **READY FOR OWNER DECISION.** M4-A and M4-B are consistent with E1;
M4-C introduces selection bias and must be disclosed if chosen; M4-D contradicts
E1.

### Cross-dependency check

| Chain | Check | Result |
| --- | --- | --- |
| M1 → `z_state` → pressure → temperature → envelope | `z_state` exists only once M1 is chosen; M3 and M4 are evaluated at it | **Blocking dependency on M1** |
| M2 → pressure → EOS state → 11.1 | Per-scenario pressure changes density and envelope status; no sampling under M2-A or M2-C | Consistent with C1, S6, F1 |
| M3 → temperature → envelope | Temperature is a point value per well; the below-TD exclusion changes TRECATE's candidates | Consistent with S2–S5 and S11; **S11 scope question** (6099 m) |
| M4 → Monte Carlo semantics | M4-A and M4-B preserve the meaning of the percentiles; M4-C changes it | Consistent with S7 under M4-A or M4-B |
| Finding 3.1 | `h_g` comes from M1; E unchanged | Consistent with A1–A6 |
| Finding 4.1 | `P_atm` added in each scenario | Consistent with B1 |
| Finding 4.2 / RU5 | Named scenarios, not a bound or a distribution; no analogue transfer | Consistent with C1 and C2 |
| Finding 4.3 | Interval designated (M1); midpoint state point (S1) | Consistent |
| Findings 6.3–6.6 | No FW/ST accuracy claim; no 0.85 filter; common depth; no uncorrected BHT | Consistent with S2–S5 |
| Findings 7.1–7.2 | Head not sampled; percentiles conditional; systematic effects separate | Consistent with S6 and S7 |
| Finding 10.1 | Below-TD exclusion | Consistent; scope to be confirmed (6099 m) |
| Finding 11.1 | Envelope enforced per M4; the audit's counts are pre-Phase-13 observations | Consistent with E1 |
| Finding 12.4 | Joint scenario = one M2 scenario with its own P, T and EOS state | Consistent with F1 |

### MODEL CONTRACT FREEZE STATUS

The four statuses requested (DECIDED, PROVISIONAL, EVIDENCE-BLOCKED,
PHASE-14 IMPLEMENTATION) cannot honestly label rows whose defining choice still
belongs to the owner. Those rows are marked **PENDING OWNER DECISION (Mx)**
rather than being forced into DECIDED.

| # | Item | Status |
| --- | --- | --- |
| 1 | Model purpose | PROVISIONAL |
| 2 | Area | PROVISIONAL |
| 3 | Thickness (`h_g` semantics) | DECIDED |
| 4 | Storage interval | **PENDING OWNER DECISION (M1)**; a geological pick is EVIDENCE-BLOCKED |
| 5 | NTG | DECIDED |
| 6 | Porosity | PROVISIONAL |
| 7 | Pressure (`P_EOS = P_atm + ρ_brine · g · (z_state − z_wl)`) | DECIDED (form); depends on M1 and M2 |
| 8 | Water level / formation head | **PENDING OWNER DECISION (M2)**; per-well head is EVIDENCE-BLOCKED |
| 9 | State-point depth (midpoint convention) | DECIDED; depends on M1 |
| 10 | Temperature | **PENDING OWNER DECISION (M3)** |
| 11 | CO2 EOS | DECIDED |
| 12 | EOS operating envelope | **PENDING OWNER DECISION (M4)**; then PHASE-14 IMPLEMENTATION |
| 13 | Brine density | PROVISIONAL |
| 14 | Storage efficiency E | DECIDED |
| 15 | E statistical interpretation | DECIDED |
| 16 | Monte Carlo distributions | PROVISIONAL |
| 17 | Dependency structure | DECIDED |
| 18 | Output percentiles | DECIDED |
| 19 | Systematic-effect reporting | DECIDED |
| 20 | Combined methodology | PHASE-14 IMPLEMENTATION |
| 21 | Fracture/injectivity scope | PHASE-14 IMPLEMENTATION; well-specific gradient EVIDENCE-BLOCKED |
| 22 | Provenance | DECIDED |
| 23 | Known limitations | DECIDED |
| 24 | Deferred items | PHASE-14 IMPLEMENTATION |

No row is "NOT YET DEFINED".

| # | Question | Answer |
| --- | --- | --- |
| 1 | Is the capacity equation fixed? | **YES** |
| 2 | Is `h_g` defined? | **YES** (semantics, A1); its values depend on M1 |
| 3 | Is the storage interval policy defined? | **NO**: M1 pending |
| 4 | Is pressure convention fixed? | **YES** (B1) |
| 5 | Is water-level treatment defined? | **NO**: M2 pending |
| 6 | Is state-point depth defined? | **YES** (S1 convention); depends on M1 |
| 7 | Is temperature selection defined? | **NO**: M3 pending |
| 8 | Is EOS and its envelope defined? | **NO**: the EOS and envelope bounds are, but out-of-envelope behaviour (M4) is pending |
| 9 | Is E interpretation fixed? | **YES** (A6) |
| 10 | Is Monte Carlo treatment fixed? | **YES** (S6, A6; porosity and brine-density priors PROVISIONAL) |
| 11 | Is 12.4 methodology fixed? | **YES** (F1) |
| 12 | Are all evidence-blocked items explicitly isolated? | **YES** (§11; geological interval pick; per-well head; fracture gradient) |
| 13 | Can Phase 14 implement without making a new scientific decision? | **NO**: M1–M4 are owner choices |

**Result:**

NOT READY FOR MODEL CONTRACT APPROVAL

### Owner choices required to close the gate

1. **M1:** M1-A (with the rule declared), M1-C, and/or M1-D; plus the depth
   reference for `z_top` and `z_base`.
2. **M2:** M2-A or M2-C (and, if M2-C, the baseline scenario).
3. **M3:** the selection form (M3-A, M3-B, M3-C and/or M3-E), the FW/ST
   tie-break ((i), (ii) or (iii)), and confirmation that S11 covers **all**
   observations deeper than the recorded TD (TRECATE 9ST: 6099 m and 6247.9 m).
4. **M4:** M4-A or M4-B (or M4-C, with its selection bias disclosed), plus where
   the check is evaluated ((a), (b) or (c)).
5. **Minor constant:** the `P_atm` value used in B1 (for example the standard
   atmosphere, 101 325 Pa), labelled as a constant.

---

## Final Owner Decisions — M1–M4 and Model Contract Freeze

*Added 2026-09-28. Documentation only. Everything above is unchanged; this
section records the owner's final M1–M4 and `P_atm` decisions and supersedes the
"PENDING OWNER DECISION" rows and the freeze result of the
"Final Decision Gate — M1–M4" section. The decisions are **OWNER / MODEL-DESIGN**
choices, not new scientific findings. No per-well top/base, water level,
temperature, NTG or fracture gradient is introduced.*

### M1 — Storage-assessment interval (DECIDED)

| Field | Content |
| --- | --- |
| Decision ID | M1 |
| Status | DECIDED; per-well intervals that cannot be established are EVIDENCE-BLOCKED |
| Exact decision | The storage interval is **not** inferred from TD and **not** automatically selected from the large stratigraphic units. Each well requires explicit `z_top` and `z_base` for its designated storage-assessment interval, expressed in the **same depth coordinate and datum as the model's normalised well depth `depth_m`**. Raw mixed-datum source depths are never silently combined. If a defensible top/base pair cannot be established: `storage_interval = unavailable`, `h_g = unavailable`, `state_point = unavailable`, and the well produces **no approved capacity result**. `thickness_m = h_g` = gross thickness of the designated interval. `z_state = (z_top + z_base)/2` is a **PROJECT MODEL CONVENTION**, not a physical law |
| Evidence basis | No workbook field designates a storage interval; source depth references differ between sheets (Final Decision Gate, M1 §3) |
| NOT established | Any per-well top/base; `depth_m`'s own reference for TRECATE\|9\|ST |
| Scientific consequence | No capacity without a designated interval; the gross-thickness formulation (A1) acts on a declared interval |
| Implementation consequence | New interval inputs, validation, unavailable status (Phase 14) |
| Dependency | A1, A2, S1, S12; M2 and M3 are evaluated at `z_state` |
| Phase 14 action | Implement interval inputs and unavailable handling; no TD fallback |

*Consequence recorded, not a new decision:* `depth_m` is inferred to be
ground-referenced for SALUZZO|1, DESANA|1, ASTI|1 and MALOSSA|15 and is not
establishable for TRECATE|9|ST (research branch `docs/finding-4.2-datum-provenance.md`).
Under M1, an interval for TRECATE|9|ST cannot be expressed defensibly in
`depth_m`'s datum until that datum is established.

### M2 — Water level / formation head (DECIDED)

| Field | Content |
| --- | --- |
| Decision ID | M2 |
| Status | DECIDED; per-well hydraulic correction EVIDENCE-BLOCKED |
| Exact decision | Two **named deterministic scenarios**: `GROUND_REFERENCE` (formation-head reference at ground elevation) and `SEA_LEVEL_SENSITIVITY` (formation-head reference at sea level). They are **not** measured values, confidence intervals, probability distributions or Monte Carlo priors. Water level is never sampled. Each scenario is evaluated separately. `GROUND_REFERENCE` is the reference/baseline scenario because it matches the current implicit model state, and is labelled a **PROJECT REFERENCE SCENARIO**, not a measured formation head. No MALOSSA pressure transfer |
| Evidence basis | No stabilised water-bearing pressure or static water level at any screened well (audit Finding 4.2 / 10.2 revision §4); Finding 10.2's +1.10% to +15.59% is a sensitivity |
| NOT established | The formation head at any well; that the two scenarios bound it |
| Scientific consequence | `P_gauge = ρ_brine · g · (z_state − z_wl)` with `z_wl = 0` (`GROUND_REFERENCE`) or `z_wl = quota` (`SEA_LEVEL_SENSITIVITY`), both in `depth_m`'s ground-referenced coordinate |
| Implementation consequence | Scenario parameter; one Monte Carlo run per scenario (Phase 14) |
| Dependency | M1 (`z_state`), B1, M4, F1 |
| Phase 14 action | Implement the two named scenarios and their labels |

*Consequence recorded, not a new decision:* `SEA_LEVEL_SENSITIVITY` needs
`depth_m`'s reference relative to ground. Where that is not established
(TRECATE|9|ST), the scenario cannot be evaluated defensibly.

### M3 — Temperature selection (DECIDED, one residual tie case)

| Field | Content |
| --- | --- |
| Decision ID | M3 |
| Status | DECIDED, except residual **R1** below |
| Exact decision | (1) Only defensible corrected observations qualify: Horner-corrected, Fertl–Wichmann, Squarci–Taffi. Non-stabilised, raw, unknown and surface-air values never qualify. (2) The observation depth must lie inside `[z_top, z_base]`. (3) Select the qualifying observation with minimum `\|z_obs − z_state\|`. (4) No interpolation. (5) No new empirical correction. (6) Fertl–Wichmann and Squarci–Taffi are **not** ranked by accuracy. (7) The method name is provenance only. If no qualifying observation exists: `temperature = unavailable`, and the well/scenario produces **no approved EOS capacity result**. **Tie-break:** if two qualifying observations occur at **exactly the same depth**, Squarci–Taffi is used as a **deterministic project convention**, not a claim of accuracy. **TRECATE:** every corrected observation deeper than the recorded TD is excluded until the depth/datum inconsistency is resolved; this explicitly covers **6099 m and 6247.9 m** (recorded TD 6087 m) |
| Evidence basis | Audit Finding 6.3 (FW/ST order unjustified); Finding 10.1; workbook `Temperature` sheet (Final Decision Gate, M3 §3) |
| NOT established | FW vs ST accuracy; temperature exactly at `z_state` |
| Scientific consequence | Temperature is a point value per well from one real observation; wells without an in-interval corrected observation are unavailable |
| Implementation consequence | Replace the 0.85 filter and rank in `_derive_temperature` (Phase 14) |
| Dependency | M1 (interval, `z_state`), S2–S5, S11, M4 |
| Phase 14 action | Implement the rule, the tie-break and the below-TD exclusion |

*Application of M1 to observation depths, recorded as a derived consequence:*
observation depths must be in `depth_m`'s coordinate and datum. A documented
offset (for example a rotary-table height stated in an operator record) is not a
silent combination; an observation whose depth reference cannot be established
does not qualify.

### M4 — EOS operating envelope (DECIDED)

| Field | Content |
| --- | --- |
| Decision ID | M4 |
| Status | DECIDED; PHASE-14 IMPLEMENTATION |
| Exact decision | EOS: Peng–Robinson + constant Peneloux shift. Validated envelope: **1–35 MPa, 280–400 K**. **Flag + block.** The envelope is evaluated for **each Monte Carlo realisation**. Out-of-envelope draws are **not** discarded, and percentiles are **not** computed after dropping draws. If any realisation in a scenario lies outside the envelope: `scenario_status = OUTSIDE_VALIDATED_ENVELOPE`, `validated_percentiles = BLOCKED`. Diagnostic calculations may be retained for analysis but are never presented as validated outputs. If every realisation is inside, P10/P50/P90 may be reported as validated statistical outputs. *Outside the validated envelope ≠ physically impossible* |
| Evidence basis | Phase 1 validation envelope; audit Finding 11.1 revision |
| NOT established | Density error outside the envelope beyond the Span–Wagner comparison |
| Scientific consequence | No validated percentiles for any scenario with an out-of-envelope draw; no selection bias, because no draw is removed |
| Implementation consequence | Per-realisation envelope check, scenario status, blocked-percentile reporting, diagnostics labelling (Phase 14) |
| Dependency | M1, M2, M3, B1 |
| Phase 14 action | Implement the check and the blocked status |

### B1 — Atmospheric pressure (DECIDED)

| Field | Content |
| --- | --- |
| Decision ID | B1 (constant) |
| Status | DECIDED |
| Exact decision | `P_atm = 101 325 Pa`, a declared **PROJECT MODEL CONSTANT**. EOS input: `P_EOS = P_gauge + 101 325 Pa` |
| Provenance | The standard atmosphere (1 atm = 101 325 Pa, exact by definition). Its use as surface pressure is a project model convention; the cited regional methodology uses 1 atm at the surface (audit Finding 9.7) |
| Phase 14 action | Add the constant with its provenance label |

### Residual item

| ID | Item | Why it matters | Status |
| --- | --- | --- | --- |
| **R1** | M3 step 3 selects the minimum `\|z_obs − z_state\|`, but the only tie-break covers observations at **exactly the same depth**. Two qualifying observations at **different depths, equidistant from `z_state`** (for example one 500 m above and one 500 m below), or two observations of the same method at the same depth with different values, have no defined winner | Squarci–Taffi values often sit at round 1000 m spacing, so an interval midpoint equidistant from two of them is realistic. Phase 14 would otherwise have to choose | **Owner choice outstanding** (for example: the shallower, the deeper, or temperature unavailable) |

### Final Model Contract

| # | Item | Contract content | Status |
| --- | --- | --- | --- |
| 1 | Model purpose | Scenario-based volumetric screening; not a site-specific estimate | PROVISIONAL |
| 2 | Area | Caller-supplied structural closure area; required; basin-scale `An/At` inside E remains a disclosed mismatch | PROVISIONAL |
| 3 | Thickness | `thickness_m = h_g` = gross thickness of the designated storage-assessment interval | DECIDED |
| 4 | Storage interval | Explicit per-well `z_top`, `z_base` in `depth_m`'s coordinate and datum; no TD or megaunit inference; unavailable if not establishable (M1) | DECIDED; unestablished intervals EVIDENCE-BLOCKED |
| 5 | NTG | Not in capacity; no Piemonte NTG; `NTG = h_net/h_g` as consistency check only | DECIDED; numerical NTG EVIDENCE-BLOCKED |
| 6 | Porosity | Uniform(0.10, 0.35), Donda et al. (2011) | PROVISIONAL |
| 7 | Pressure | `P_EOS = 101 325 Pa + ρ_brine · g · (z_state − z_wl)` | DECIDED |
| 8 | Water level / formation head | `GROUND_REFERENCE` (project reference scenario) and `SEA_LEVEL_SENSITIVITY`; deterministic; not sampled; not a distribution (M2) | DECIDED; per-well correction EVIDENCE-BLOCKED |
| 9 | State-point depth | `z_state = (z_top + z_base)/2`, project model convention | DECIDED |
| 10 | Temperature | Nearest in-interval corrected observation; no interpolation; no FW/ST accuracy ranking; same-depth tie → Squarci–Taffi (convention); below-TD corrected observations excluded; else unavailable (M3) | DECIDED, **except residual R1** |
| 11 | CO2 EOS | Peng–Robinson + constant Peneloux; justification corrected (E1, E2) | DECIDED |
| 12 | EOS operating envelope | 1–35 MPa, 280–400 K; checked per realisation; flag + block; no draws discarded (M4) | DECIDED; PHASE-14 IMPLEMENTATION |
| 13 | Brine density | Uniform(1020, 1100) kg/m³ | PROVISIONAL |
| 14 | Storage efficiency E | Aggregate DOE-style E containing the gross-to-net term | DECIDED |
| 15 | E statistical interpretation | Uniform(0.01, 0.04): project-defined prior over DOE's P15–P85 bounds; not DOE's distribution | DECIDED |
| 16 | Monte Carlo distributions | Only variables with an explicit distribution and justified role vary: E (decided), porosity and brine density (provisional); water level and temperature are not sampled | PROVISIONAL |
| 17 | Dependency structure | One state point and datum for P and T; each named scenario is one joint P/T/EOS state | DECIDED |
| 18 | Output percentiles | P10/P50/P90, statistical convention, conditional on the declared model; reported as validated only if no realisation leaves the envelope | DECIDED |
| 19 | Systematic-effect reporting | Reported separately from the Monte Carlo band | DECIDED |
| 20 | Combined methodology | Single joint scenario per named scenario (F1). Under this contract the computed systematic contrast is `SEA_LEVEL_SENSITIVITY` vs `GROUND_REFERENCE` (derived from M2; 3.1 is resolved by the gross formulation, 4.1 by B1, 11.1 by the envelope) | DECIDED; PHASE-14 IMPLEMENTATION |
| 21 | Fracture/injectivity scope | Uncited fracture criterion removed from approved scope (D1); headroom convention deferred (B2) | PHASE-14 IMPLEMENTATION; well-specific gradient EVIDENCE-BLOCKED |
| 22 | Provenance | Citations for external constants; owner conventions labelled PROJECT ASSUMPTIONS / PROJECT MODEL CONSTANTS | DECIDED |
| 23 | Known limitations | §13 above, plus: wells may be unavailable (no interval, no in-interval corrected temperature) or blocked (outside envelope) | DECIDED |
| 24 | Deferred items | §12 above; B2 | DEFERRED / PHASE-14 IMPLEMENTATION |
| 25 | Atmospheric pressure | `P_atm = 101 325 Pa`, project model constant | DECIDED |

No row is "NOT YET DEFINED". One row (10) carries an outstanding owner choice
(R1).

### Evidence-blocked items

These do **not** reopen the scientific audit.

1. Per-well hydraulic (formation-head) correction, and any MALOSSA analogue
   transfer.
2. Well-specific fracture gradient.
3. Numerical Piemonte NTG.
4. Any storage interval that cannot be established for a well (including every
   interval at TRECATE|9|ST while its depth datum is unestablished).

### Phase 13 completion criteria

| Criterion | Met? |
| --- | --- |
| Capacity equation fixed | **YES** — `M = A · h_g · φ · ρ_CO2(P_EOS, T) · E` |
| `h_g` semantics fixed | **YES** — A1, M1 |
| Storage interval policy fixed | **YES** — M1 |
| State-point rule fixed | **YES** — midpoint convention |
| Pressure convention fixed | **YES** — B1, `P_atm = 101 325 Pa` |
| Water-level scenarios fixed | **YES** — M2 |
| Temperature-selection rule fixed | **NO** — fixed except the equidistant tie case **R1** |
| EOS and envelope fixed | **YES** — E1, M4 |
| E interpretation fixed | **YES** — A5, A6 |
| Monte Carlo treatment fixed | **YES** — S6, A6, M2, M4 |
| 12.4 combined methodology fixed | **YES** — F1 with the M2 scenario pair |
| Evidence-blocked items isolated | **YES** — above |
| Phase 14 implementation items isolated | **YES** — §12 and the rows marked PHASE-14 IMPLEMENTATION |

**Result:**

NOT READY FOR MODEL CONTRACT APPROVAL

The single remaining item is **R1**. Once the owner states the rule for
equidistant temperature observations at different depths (and for same-depth,
same-method duplicates), every criterion above is met and nothing else in the
contract requires a new scientific decision.

### Phase 14 entry conditions

1. R1 decided and recorded here.
2. Explicit owner approval of this Model Contract.
3. Formulation freeze: this section's contract is the implementation
   specification.
4. Written list of baseline and characterisation tests expected to change
   (including `tests/test_capacity_audit.py:154–159`,
   `tests/test_provenance_audit.py:107–117`, `tests/test_ntg_disclosure.py`,
   `tests/test_cross_model_audit.py`, and the temperature-selection tests).
5. Phase 14 branches from `417398ea6c10fa851cabfbed0efad3bd5610899a` (or its
   approved successor), never from `research/finding-3.1-4.2-evidence`.

---

## R1 — Final Owner Decision and Model Contract Freeze

*Added 2026-09-28. Documentation only. Everything above is unchanged; this
section records the owner's R1 decision and supersedes the "Residual item" table,
row 10's status, the "Temperature-selection rule fixed" criterion and the freeze
result of the "Final Owner Decisions — M1–M4 and Model Contract Freeze" section.*

### R1 — Temperature-selection tie handling (DECIDED)

| Field | Content |
| --- | --- |
| Decision ID | R1 |
| Status | DECIDED (OWNER / MODEL-DESIGN) |
| Exact decision | **(1)** If two or more otherwise-valid corrected observations lie at exactly the same minimum `\|z_obs − z_state\|` but at **different depths**, select the **shallower** observation. This is a deterministic **PROJECT SELECTION CONVENTION**, not a claim that shallower temperatures are more accurate. **(2)** If two observations from the **same correction method** occur at the **same depth** with **different values**, and no additional provenance resolves the conflict: `temperature = unavailable`. No value is chosen arbitrarily. **(3)** The previously approved same-depth rule is preserved: if observations at the same depth come from **different eligible methods** and otherwise qualify, **Squarci–Taffi** is used as the deterministic project tie-break. This is **not** an accuracy ranking |
| Evidence basis | Audit Finding 6.3 (no FW/ST accuracy ranking established); workbook `Temperature` sheet |
| NOT established | Any accuracy difference between shallower and deeper observations, or between FW and ST |
| Scientific consequence | M3 yields exactly one temperature, or `unavailable`, for every case that arises in the project's data |
| Implementation consequence | Deterministic tie handling in the Phase 14 temperature path |
| Dependency | M1, M3, S2, S5 |
| Phase 14 action | Implement R1 with the evaluation order below |

**Evaluation order (the literal composition of M3 and R1; no new decision).**

1. Keep only eligible observations: corrected method (Horner-corrected,
   Fertl–Wichmann, Squarci–Taffi); depth inside `[z_top, z_base]`; depth
   reference established in `depth_m`'s coordinate and datum; not deeper than
   the recorded TD.
2. Take the minimum `|z_obs − z_state|`.
3. If observations at that minimum lie at different depths, keep only the
   shallower depth (R1-1).
4. At the selected depth, if any single method has two or more observations with
   different values: `temperature = unavailable` (R1-2, applied as written).
   Observations of the same method with identical values are not a conflict.
5. If more than one method remains at that depth, use Squarci–Taffi (R1-3).
6. If no observation is eligible: `temperature = unavailable` (M3).

**Coverage check against the project's data (read-only).** The workbook
`Temperature` sheet (452 rows) contains Squarci–Taffi 243, non-stabilised 131,
surface air 40, Fertl–Wichmann 38 and **Horner-corrected 0**. Eight well/depth
pairs carry more than one corrected observation, and all eight are
Fertl–Wichmann + Squarci–Taffi pairs (resolved by R1-3). No same-method,
same-depth duplicate exists (R1-2 is a safeguard).

**Scope note (DEFERRED; not reachable with current data).** R1-3 names
Squarci–Taffi, so it does not resolve a same-depth tie between Horner-corrected
and Fertl–Wichmann with no Squarci–Taffi present. No Horner-corrected
observation exists in any ingested source, so this case cannot occur with the
project's data. If Horner-corrected data are ever ingested, this case needs an
owner rule before use. Until then, Phase 14 must implement it as an explicit
**unresolved-case guard** that reports the conflict and selects no value; this
is an implementation safeguard, not a scientific choice.

### Final Model Contract status

| # | Item | Status |
| --- | --- | --- |
| 1 | Model purpose | PROVISIONAL |
| 2 | Area | PROVISIONAL |
| 3 | Thickness (`h_g`) | DECIDED |
| 4 | Storage interval (M1) | DECIDED; unestablished intervals EVIDENCE-BLOCKED |
| 5 | NTG | DECIDED; numerical NTG EVIDENCE-BLOCKED |
| 6 | Porosity | PROVISIONAL |
| 7 | Pressure (`P_EOS = 101 325 Pa + ρ_brine · g · (z_state − z_wl)`) | DECIDED |
| 8 | Water level / formation head (M2) | DECIDED; per-well correction EVIDENCE-BLOCKED |
| 9 | State-point depth (midpoint convention) | DECIDED |
| 10 | Temperature (M3 + R1) | **DECIDED**; Horner-vs-FW same-depth case DEFERRED (not reachable with current data) |
| 11 | CO2 EOS | DECIDED |
| 12 | EOS operating envelope (M4) | DECIDED; PHASE-14 IMPLEMENTATION |
| 13 | Brine density | PROVISIONAL |
| 14 | Storage efficiency E | DECIDED |
| 15 | E statistical interpretation | DECIDED |
| 16 | Monte Carlo distributions | PROVISIONAL |
| 17 | Dependency structure | DECIDED |
| 18 | Output percentiles | DECIDED |
| 19 | Systematic-effect reporting | DECIDED |
| 20 | Combined methodology | DECIDED; PHASE-14 IMPLEMENTATION |
| 21 | Fracture/injectivity scope | PHASE-14 IMPLEMENTATION; well-specific gradient EVIDENCE-BLOCKED |
| 22 | Provenance | DECIDED |
| 23 | Known limitations | DECIDED |
| 24 | Deferred items | DEFERRED / PHASE-14 IMPLEMENTATION |
| 25 | Atmospheric pressure (`P_atm = 101 325 Pa`) | DECIDED |

No row is "NOT YET DEFINED" or "PENDING OWNER DECISION".

### Phase 13 completion criteria (final)

| Criterion | Met? |
| --- | --- |
| Capacity equation fixed | **YES** — `M = A · h_g · φ · ρ_CO2(P_EOS, T) · E` |
| `h_g` semantics fixed | **YES** — A1, M1 |
| Storage interval policy fixed | **YES** — M1 |
| State-point rule fixed | **YES** — midpoint convention (S1, M1) |
| Pressure convention fixed | **YES** — B1, `P_atm = 101 325 Pa` |
| Water-level scenarios fixed | **YES** — M2 |
| Temperature-selection rule fixed | **YES** — M3 + R1 |
| EOS and envelope fixed | **YES** — E1, M4 |
| E interpretation fixed | **YES** — A5, A6 |
| Monte Carlo treatment fixed | **YES** — S6, A6, M2, M4 |
| 12.4 combined methodology fixed | **YES** — F1 with the M2 scenario pair |
| Evidence-blocked items isolated | **YES** — below |
| Phase 14 implementation items isolated | **YES** — §12 and the rows marked PHASE-14 IMPLEMENTATION |

**Result:**

READY FOR MODEL CONTRACT APPROVAL

This document does not approve the contract; approval is the owner's.

### Evidence-blocked items (do not reopen the audit)

1. Per-well hydraulic (formation-head) correction, and any MALOSSA analogue
   transfer.
2. Well-specific fracture gradient.
3. Numerical Piemonte NTG.
4. Any storage interval that cannot be established for a well, including every
   interval at TRECATE|9|ST while its depth datum is unestablished.

### Phase 14 entry conditions

1. Explicit owner approval of this Model Contract.
2. Formulation freeze: this contract (A1–A7, B1, C1–C2, D1–D2, E1–E2, F1–F3,
   S1–S12, M1–M4, R1, `P_atm`) is the implementation specification.
3. A written list of the baseline and characterisation tests expected to change,
   including `tests/test_capacity_audit.py:154–159`,
   `tests/test_provenance_audit.py:107–117`, `tests/test_ntg_disclosure.py`,
   `tests/test_cross_model_audit.py` and the temperature-selection tests.
4. The unresolved-case guard for the deferred Horner-vs-FW same-depth tie.
5. Phase 14 branches from `417398ea6c10fa851cabfbed0efad3bd5610899a` (or its
   approved successor), never from `research/finding-3.1-4.2-evidence`.

---

## Final Gap Closure

*Added 2026-09-28. Documentation only. This section records clarifications of
decisions the owner has already made, and supersedes any earlier wording it
contradicts. It adds no new scientific decision. The contract is **not**
owner-approved.*

### A. M1 — input model (clarification of the existing M1 decision)

| Item | Contract wording |
| --- | --- |
| Inputs | `z_top` and `z_base` of the designated storage-assessment interval are **explicit caller/API inputs** for each well |
| Depth reference | Both are expressed in the same depth coordinate and datum as `depth_m`, and that reference must be established for the well (C2 below) |
| Derived thickness | `h_g = z_base − z_top` is **derived**, not separately supplied |
| Derived state point | `z_state = (z_top + z_base) / 2` (PROJECT MODEL CONVENTION) |
| `thickness_m` | There is **no independent `thickness_m` input** in the approved formulation. In the capacity equation, the thickness term is the derived `h_g`. This supersedes the A7 wording "thickness_m semantic contract changes … to h_g": the API input changes from a thickness value to the interval pair |
| No inference | No interval from TD; no interval from generic stratigraphic units |
| Unavailable | If no defensible interval exists: interval, `h_g`, `z_state`, temperature and pressure are unavailable, and **no approved capacity** is produced |

### B. D1, Findings 5.1, 5.2, 12.1 — fracture/injectivity outputs

**Existing CLI outputs** (`src/ccs_screen/cli.py:182–214`; the API computes
none of them):

| CLI output | Depends on | Approved scientific output? |
| --- | --- | --- |
| `fracture_pressure_pa` | 15 000 Pa/m gradient | **No** |
| `allowable_delta_p_pa` (headroom) | Gradient, SF = 0.9, initial pressure | **No** |
| `max_rate_m3_s` | Headroom, and the Theis infinite-acting solution at `radius_m` | **No** |
| `within_limit` | Headroom | **No** |
| `planned_delta_p_pa` | Theis infinite-acting solution at `radius_m` (an injectivity formulation not adopted by the contract; Findings 5.1, 12.1) | **No** |
| `initial_pressure_pa` | Pressure-prior midpoint; used only for the headroom check (Finding 5.2) | **No** (as an injectivity input) |

**Contract rule (conservative; owner decision).**

1. Any output whose validity depends on an unapproved fracture-gradient,
   headroom or injectivity criterion or formulation is **not** part of the
   approved scientific model.
2. Such output must not be presented as validated scientific output.
3. Phase 14 may implement explicit `UNAVAILABLE` / `NOT_VALIDATED` handling and
   diagnostics for such outputs. Either handling satisfies the contract.
4. Phase 14 must **not** invent or choose a fracture-gradient criterion, a
   safety factor, an evaluation radius or a bounded-aquifer solution.
5. The old criterion (15 000 Pa/m, SF = 0.9) is not silently retained as
   approved.
6. Historical CLI behaviour is not scientifically approved.

**Coverage of the findings.**

| Finding | Recorded action | Covered by the rule? |
| --- | --- | --- |
| 5.1 | Evaluate the fracture check at a wellbore radius (owner decision) | **Yes.** No fracture criterion is approved, so the rate ceiling is `NOT_VALIDATED`. Choosing an evaluation radius is needed only if a criterion is approved in future |
| 5.2 | Tie initial pressure to depth for the headroom check | **Yes.** Headroom is `NOT_VALIDATED`; `initial_pressure_pa` has no approved injectivity role |
| 12.1 | Closed trap vs infinite-acting Theis | **Yes.** The Theis outputs are `NOT_VALIDATED`. Adopting a bounded-aquifer formulation would be a future owner decision, not a Phase 14 task |
| D1 / B2 | Fracture criterion and headroom convention | **Yes.** Removed from approved scope; B2 remains DEFERRED |

This supersedes D1's Phase 14 action "Decide CLI treatment within Phase 14":
Phase 14 applies the rule above and decides nothing scientific.

### C. Explicit clarifications

**C1 — EOS envelope pressure basis.** The validated pressure envelope
(1–35 MPa) is checked against **`P_EOS = P_gauge + P_atm`**, with
`P_atm = 101 325 Pa`. It is **not** applied to gauge pressure. The temperature
bound (280–400 K) applies to the selected temperature.

**C2 — Depth-reference strictness.** For every depth-dependent quantity used by
the storage interval, temperature selection and pressure calculation, the depth
reference must be **explicitly established and defensible for that well**.

- An inferred datum is **not** treated as formally established while the
  underlying evidence remains marked UNKNOWN.
- Where the reference cannot be defensibly established, the affected input is
  unavailable, no silent correction is applied, and no approved capacity is
  produced.
- TRECATE|9|ST: its depth reference is not establishable from public sources;
  this limitation stands.

*Consequence recorded, not a new decision.* The pipeline labels `depth_m`'s
datum `UNKNOWN`. For SALUZZO|1, DESANA|1, ASTI|1 and MALOSSA|15 the
relationship "`depth_m` = operator rotary-table TD minus rotary-table height" is
an **inferred** arithmetic identity, marked OPEN pending GEOTHOPICA/CNR-IGG
confirmation (research branch `docs/finding-4.2-datum-provenance.md` §4). Under
C2, `depth_m`'s reference is therefore **not yet formally established for any
screened well**, and the same applies to the `Temperature` sheet depths. Until
it is established, no screened well can produce an approved capacity. This
supersedes the M2 wording "both in `depth_m`'s ground-referenced coordinate" and
the M1 consequence note, which both read the inferred reference as usable.
Establishing it is an evidence matter (see Evidence-blocked items).

**C3 — R1 same-method conflict.** If the selected candidate set contains two
observations from the **same method at the same depth with different values**,
the selected temperature is **`UNAVAILABLE`** and a **conflict diagnostic** is
emitted. No resolution mechanism exists; the R1 phrase "no additional
provenance resolves the conflict" introduces none.

### D. S11 wording

The S11 row (§9) now names both below-TD observations, 6099 m and 6247.9 m
(recorded TD 6087 m). The decision is unchanged.

### E. Remaining owner decision

| ID | Decision | Why it is needed | Options (not ranked) |
| --- | --- | --- | --- |
| **O1** | **Does the Model Contract govern the CLI's own capacity calculation?** | The CLI capacity path (`src/ccs_screen/cli.py`, defaults `DEPLETED_GAS_ANALOG`, `src/ccs_screen/monte_carlo.py:59–67`) is a synthetic depleted-gas demo: `thickness_m` labelled "net storage thickness (m)" (`cli.py:30`) with a 25–55 m prior; a 12–20 MPa pressure prior independent of depth; P and T sampled independently (Finding 7.3, S8, deferred to Phase 14 with no rule); E = 0.02–0.07. It shares `ScreeningConfig.thickness_m` (`src/ccs_screen/config.py:106`) with the API path. A7 and M1 change the API input; nothing states whether the CLI changes too. Without a rule, Phase 14 would decide it | **(a)** The contract applies to the CLI capacity path: it adopts the interval inputs, derived `h_g`, the contract pressure, temperature, E and envelope rules. **(b)** The CLI capacity path is outside the approved scientific model: its outputs are labelled `NOT_VALIDATED` demo output, as in rule B, and Finding 7.3 is covered by that label |

### Final Model Contract status

| # | Item | Status |
| --- | --- | --- |
| 1 | Model purpose | PROVISIONAL |
| 2 | Area | PROVISIONAL |
| 3 | Thickness: derived `h_g = z_base − z_top`; no independent thickness input | DECIDED |
| 4 | Storage interval: caller-supplied `z_top`, `z_base`; established depth reference (C2) | DECIDED; unestablished intervals EVIDENCE-BLOCKED |
| 5 | NTG | DECIDED; numerical NTG EVIDENCE-BLOCKED |
| 6 | Porosity | PROVISIONAL |
| 7 | Pressure: `P_EOS = 101 325 Pa + ρ_brine · g · (z_state − z_wl)` | DECIDED |
| 8 | Water level: `GROUND_REFERENCE`, `SEA_LEVEL_SENSITIVITY` | DECIDED; per-well correction EVIDENCE-BLOCKED |
| 9 | State-point depth: `z_state = (z_top + z_base)/2` | DECIDED |
| 10 | Temperature: M3 + R1 + C3 | DECIDED; Horner-vs-FW same-depth case DEFERRED (unreachable) |
| 11 | CO2 EOS | DECIDED |
| 12 | EOS envelope: 1–35 MPa on `P_EOS`, 280–400 K; per realisation; flag + block | DECIDED; PHASE-14 IMPLEMENTATION |
| 13 | Brine density | PROVISIONAL |
| 14 | Storage efficiency E | DECIDED |
| 15 | E statistical interpretation | DECIDED |
| 16 | Monte Carlo distributions | PROVISIONAL |
| 17 | Dependency structure | DECIDED |
| 18 | Output percentiles | DECIDED |
| 19 | Systematic-effect reporting | DECIDED |
| 20 | Combined methodology | DECIDED; PHASE-14 IMPLEMENTATION |
| 21 | Fracture/injectivity scope: rule B; outputs `UNAVAILABLE`/`NOT_VALIDATED` | DECIDED; PHASE-14 IMPLEMENTATION; well-specific gradient EVIDENCE-BLOCKED |
| 22 | Provenance | DECIDED |
| 23 | Known limitations | DECIDED |
| 24 | Deferred items: B2; Horner-vs-FW tie | DEFERRED |
| 25 | Atmospheric pressure: 101 325 Pa | DECIDED |
| 26 | Depth-reference strictness (C2) | DECIDED; datum confirmation per well EVIDENCE-BLOCKED |
| 27 | CLI capacity path scope | **OWNER DECISION O1** |

### Evidence-blocked items (do not reopen the audit)

1. Per-well hydraulic (formation-head) correction, and any MALOSSA analogue
   transfer.
2. Well-specific fracture gradient.
3. Numerical Piemonte NTG.
4. Any storage interval that cannot be established for a well.
5. Formal establishment of `depth_m`'s depth reference for each screened well
   (inferred for four wells; not establishable for TRECATE|9|ST), and of the
   `Temperature` sheet depth reference.

### Freeze status

| Check | Result |
| --- | --- |
| No scientific decision hidden inside Phase 14 | **NO** — O1 |
| All approved formulation decisions explicit | YES |
| Evidence-blocked matters remain evidence-blocked | YES |
| Deferred matters remain deferred | YES |
| Contract owner-approved | NO (not claimed) |

**Result:**

NOT READY FOR OWNER APPROVAL

The single remaining item is **O1**. Once it is decided and recorded, every
check above is met.

---

## O1 Decision and Owner-Approval Gate

*Added 2026-09-28. Documentation only. This section records the owner's O1
decision and supersedes row 27 and the freeze status of "Final Gap Closure".
Everything else in "Final Gap Closure" stands. No new scientific decision is
introduced. The contract is **not** owner-approved.*

### O1 — CLI capacity path (DECIDED: option (b))

| Field | Content |
| --- | --- |
| Decision ID | O1 |
| Status | DECIDED (OWNER / MODEL-DESIGN) |
| Exact decision | The CLI synthetic capacity calculation path (`DEPLETED_GAS_ANALOG`) is **outside** the approved Model Contract. Its outputs are **`NOT_VALIDATED`** and must not be presented as validated scientific screening results |
| Rationale (existing findings only) | (1) It is a synthetic depleted-gas demo formulation: `DEPLETED_GAS_ANALOG` is documented as "Synthetic depleted-gas analog used by the demo. Not a real site." (`src/ccs_screen/monte_carlo.py:59–67`). (2) Its thickness is represented independently as "net storage thickness (m)" (`src/ccs_screen/cli.py:30`), with a 25–55 m prior, not as the derived `h_g`. (3) Pressure uses a synthetic 12–20 MPa range, not the approved depth-based formulation (Finding 5.2). (4) Pressure and temperature are sampled independently (Finding 7.3). (5) E uses 0.02–0.07, not the approved Uniform(0.01, 0.04) aggregate prior. (6) Finding 7.3 / S8 remains DEFERRED to Phase 14 |
| NOT decided here | Finding 7.3 (independent P/T sampling); any change to the CLI implementation |
| Phase 14 action | Apply the `NOT_VALIDATED` label to CLI demo outputs. Phase 14 may separately document or refactor the demo path, but must not claim or invent scientific equivalence with the Model Contract |

### Scope boundary

| Governed by the approved Model Contract | Not governed (`NOT_VALIDATED` demo output) |
| --- | --- |
| The validated scientific screening/capacity model: the formulation of this record (A1–A7, B1, C1–C2, E1–E2, F1–F3, S1–S12, M1–M4, R1, `P_atm`, and the Final Gap Closure clarifications A, B, C1–C3) | The CLI synthetic capacity calculation path (`cli._screen`) and every output it computes: capacity P10/P50/P90/mean, surrogate fit metrics and `sensitivity_mt_per_sigma`. Supplying CLI flags or a `--config` file does not bring this path under the contract, because the path does not implement the approved formulation (interval inputs, derived `h_g`, depth-based `P_EOS`, M3 temperature selection, M4 envelope check) |
| — | The CLI injectivity outputs, already outside the approved model under Final Gap Closure rule B |

Rules at the boundary:

1. CLI demo outputs remain available only as `NOT_VALIDATED` / demo outputs.
2. Phase 14 must not silently reinterpret the CLI demo as compliant with the
   Model Contract.
3. Phase 14 may document or refactor the demo path, but must not invent
   scientific equivalence.
4. Finding 7.3 is not reopened and independent P/T sampling is not decided here.

### C2 status (unchanged)

The strict C2 decision stands:

- An inferred depth reference is **not** formally established.
- Where the required depth reference cannot be defensibly established, the
  affected model input is unavailable.
- No silent datum correction is allowed, and no approved capacity result is
  produced.

**Consequence (evidence-blocked, not an owner decision):** documented wells
whose depth reference remains UNKNOWN or only inferred cannot produce an
approved capacity result until the required depth reference is formally
established. At present this applies to every screened well (Final Gap
Closure, C2).

### Final Model Contract status

Rows 1–26 are as in "Final Gap Closure". Row 27 is superseded:

| # | Item | Status |
| --- | --- | --- |
| 27 | CLI capacity path scope | DECIDED (O1): outside the approved Model Contract; outputs `NOT_VALIDATED`; PHASE-14 IMPLEMENTATION (labelling) |

Deferred items remain deferred: B2 (fracture/headroom convention); the
unreachable Horner-vs-Fertl–Wichmann same-depth tie; Finding 7.3 / S8.

Evidence-blocked items remain evidence-blocked: per-well hydraulic correction
and MALOSSA transfer; well-specific fracture gradient; numerical Piemonte NTG;
any storage interval that cannot be established; formal establishment of each
screened well's `depth_m` and `Temperature` depth reference.

### Freeze status

| Check | Result |
| --- | --- |
| No owner decision hidden in Phase 14 | YES |
| All approved formulation decisions explicit | YES |
| Evidence-blocked matters remain evidence-blocked | YES |
| Deferred matters remain deferred | YES |
| Contract owner-approved | NO (not claimed) |

**Result:**

READY FOR OWNER APPROVAL

---

## Owner Approval — Phase 13 Model Contract

*Added 2026-09-28. Records the owner's explicit approval. It does not change any
decision above.*

| Field | Content |
| --- | --- |
| Approval | **APPROVED BY THE OWNER**: "I explicitly approve the Phase 13 Model Contract as recorded in `docs/phase13-owner-decision-record.md`. Approve the contract exactly as documented." |
| Date | 2026-09-28 |
| What is approved | The Model Contract exactly as documented in lines 1–1304 of this file, as they stood at approval: the decisions A1–A7, B1–B2, C1–C2, D1–D2, E1–E2, F1–F3, S1–S12, M1–M4, R1, `P_atm = 101 325 Pa`, the "Final Gap Closure" clarifications (A, B, C1–C3, D) and O1, with the contract status given in "Final Gap Closure" (rows 1–26) and "O1 Decision and Owner-Approval Gate" (row 27) |
| Approved text fingerprint | SHA-256 of lines 1–1304 (LF line endings): `51346f529b48448e42c5515f65db82fb304913edd71a3cd2f060e75e1363cb2b` |
| Base | `eyo/ccs-screening-starter` @ `417398ea6c10fa851cabfbed0efad3bd5610899a` |
| Not changed by approval | No scientific decision, status, evidence-blocked item or deferred item is altered |

### Phase 13 freeze status

**FORMULATION FROZEN (owner-approved).** The approved Model Contract is the
Phase 14 implementation specification. Any change to it requires a new, explicit
owner decision recorded in this file.

### Status carried forward unchanged

- **PROVISIONAL (current behaviour retained, approved as such):** model purpose,
  area, porosity, brine density, Monte Carlo distributions.
- **EVIDENCE-BLOCKED:** per-well hydraulic (formation-head) correction and any
  MALOSSA analogue transfer; well-specific fracture gradient; numerical Piemonte
  NTG; any storage interval that cannot be established; formal establishment of
  each screened well's `depth_m` and `Temperature` depth reference (under C2, no
  screened well can currently produce an approved capacity result).
- **DEFERRED:** B2 (fracture/headroom pressure convention); the unreachable
  Horner-vs-Fertl–Wichmann same-depth tie (Phase 14 guard: select no value,
  report the conflict); Finding 7.3 / S8.
- **Outside the approved model (`NOT_VALIDATED`):** CLI injectivity outputs
  (rule B) and the CLI synthetic capacity path (O1).

### Phase 14 entry point

- Branch from `417398ea6c10fa851cabfbed0efad3bd5610899a`, never from
  `research/finding-3.1-4.2-evidence`.
- Remaining entry conditions: a written list of the baseline and
  characterisation tests expected to change, and the deferred-tie guard as part
  of the implementation.
