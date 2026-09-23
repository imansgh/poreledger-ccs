# Design note -- making the implicit net-to-gross explicit

**Evidence item 3 from the B-prime control experiment: the API accepts
`h_net` but never records the NTG it implies.**

Drafted 2026-09-21. Companion to `docs/bprime-control-experiment.md` and
`docs/ev3-semantics.md`.

**Design only.** No file under `src/`, no production equation, no scientific
constant, no API behaviour and no test was modified. Nothing below is a
Piemonte NTG value, and no gross thickness is invented.

---

## Decision

> ### API design ready for implementation review.

The interface question is fully answerable and is answered below. The
recommended variant is **Option C in two phases**, with phase 1 recording the
declaration and changing **no number at all**.

The reason this is "ready" despite Finding 3.1 being unresolved: **the
elicitation is worth making even if B-prime is never adopted.** Today the API
cannot state what net-to-gross a result assumed. That is a provenance defect on
its own terms, independent of which formulation eventually wins, and it is the
only thing standing between the project and a testable B-prime.

---

## 1. Current thickness semantics

### Where `h` enters

There is exactly **one** entry point:

| Layer | Field | Behaviour |
| --- | --- | --- |
| `api.UserInputs` | `thickness_m: float` | Required, no default, validated `> 0`, finite, numeric |
| `api.UserInputs.from_mapping` | - | Rejects unknown keys; names anything missing |
| `web.schemas.UserInputsModel` | `thickness_m: float` | `extra="forbid"`, example 35.0 |
| `frontend/components/InputForm.tsx` | `thickness` | Labelled "Net reservoir thickness" |

### What the system declares it to mean

`USER_INPUT_SPEC["thickness_m"]`, verbatim:

```
label:            "Net storage thickness"
description:      "Net reservoir thickness inside the closure -- NOT the gross
                   chronostratigraphic interval, which is 1-2 orders of
                   magnitude larger."
not_inferred_from: ["gross stratigraphic thickness", "total well depth"]
policy:            NET_THICKNESS_POLICY_STATEMENT
```

So `h` is documented as **net**, unambiguously, in four places (the spec, the
policy statement, the frontend label, and `ThicknessKind`).

### What `ThicknessKind` means operationally

`ThicknessKind` is a three-valued enum on the **ingestion** side only:

| Member | Populated from | Reaches the equation? |
| --- | --- | --- |
| `GROSS_STRATIGRAPHIC` | `Lito-Stratigrafie` tops/bottoms | **No** -- reported, never used |
| `NET_STORAGE` | nothing; always MISSING | No -- the caller supplies it instead |
| `AQUIFER_HYDRAULIC` | nothing; CLI default only | Theis only |

It is a **taxonomy that prevents substitution**, not a mechanism that routes
values. `record.gross_thickness_m` is computed and exposed
(`has_gross_thickness` in `list_wells`), but no code path connects it to
`thickness_m`.

### Can the model distinguish the three quantities?

| Quantity | Representable today? |
| --- | --- |
| `gross_thickness` | **Yes** on the ingestion record -- but it is the gross *chronostratigraphic interval*, not a formation gross thickness |
| `net_thickness` | **Yes** -- the caller's `thickness_m` |
| `net_to_gross` | **No.** The concept does not exist anywhere in `src/` |

**The gap is precisely and only NTG.**

---

## 2. The hidden assumption

The caller supplies one number. The provenance machinery records it faithfully:

```python
Assumption(parameter="thickness_m", value=<float>, author="caller (user input)",
           rationale="Net reservoir thickness inside the closure ... Supplied by
                      the caller for this request.", citation=_USER_CITATION)
```

**What is recorded:** the value, that a human supplied it, and what it is
supposed to mean.

**What is not recorded:** the gross thickness it came from, the cutoff that
produced it, and therefore the net-to-gross it implies. The `Assumption` object
has no field for any of them, and `to_dict()` emits only `{"value", "unit"}`.

The B-prime experiment showed the model behaves *as if* NTG were about 0.477.
Nobody supplied that. It is a property of the published efficiency distribution,
not of any reservoir. **That is the defect this note addresses.**

---

## 3. Algebraic equivalence -- and where it does not hold

Write `E = E_h x E'` with `E' = E_A E_phi E_V E_d`.

```
DOE        :  M = A x h_gross x phi x rho x E_h x E'
Net-input  :  M = A x h_net   x phi x rho x E'
```

Substituting `h_net = h_gross x NTG`:

```
Net-input  =  A x h_gross x NTG x phi x rho x E'
DOE        =  A x h_gross x E_h x phi x rho x E'
```

so

```
Net-input / DOE = NTG / E_h
```

**Equality requires `NTG = E_h`. But `E_h` is a random variable, not a scalar**
-- `uniform(0.25, 0.75)` in the published decomposition. So "equality" has to be
qualified, and the qualification is the substantive result.

Measured, N = 500 000, seed 42:

| Equality in what sense | Scalar NTG required | Holds? |
| --- | --- | --- |
| Pathwise (per realisation) | `NTG = E_h` for every draw | **Never**, for any scalar |
| In distribution | `NTG ~ uniform(0.25, 0.75)` | **Never**, for any scalar |
| Of the **mean** | **0.4999** (`= E[E_h]`, exact by independence) | Yes, at that one value |
| Of the **median** | **0.4768** | Yes, at that one value |
| Of P10 | 0.4330 | Yes, at that one value |
| Of P90 | 0.5308 | Yes, at that one value |

The four moment-matching values span **20.5%** of the median. **No single scalar
NTG reproduces the DOE distribution.**

### The design consequence

Replacing a distributed `E_h` with a scalar NTG **removes variance the published
method has**:

| | P10 | P50 | P90 | span/P50 | sd |
| --- | --- | --- | --- | --- | --- |
| DOE, `E_h` distributed | 0.873% | 2.071% | 4.563% | **1.781** | 1.558% |
| Scalar NTG = 0.4768 | 0.962% | 2.071% | 4.099% | **1.515** | 1.271% |

A point NTG narrows the reported band by 15% while leaving the median
untouched -- a silent increase in apparent confidence.

Supplying NTG as a **range** restores it:

| Caller supplies | P50 | span/P50 (DOE = 1.781) |
| --- | --- | --- |
| `NTG ~ U(0.25, 0.75)` | 2.071% | **1.781** -- exact, as it must be |
| `NTG ~ U(0.35, 0.60)` | 2.036% | 1.583 |
| `NTG ~ U(0.45, 0.51)` | 2.083% | 1.519 |

**The interface must accept NTG as a range, not a point.** A caller who knows
their NTG tightly should narrow the band; a caller who does not should not be
able to accidentally narrow it by supplying a single number.

---

## 4. Options

### Option A -- gross thickness + NTG, model derives net

```
caller supplies:  gross_thickness_m, net_to_gross
model derives:    thickness_m = gross_thickness_m x net_to_gross
```

**Semantically the cleanest.** It matches the DOE input contract exactly, makes
both quantities first-class, and the derived net is auditable.

**Fatal for this dataset.** `docs/piemonte-ntg-evidence.md` established that no
caller can supply a *formation* gross thickness: the only gross this project
holds is the chronostratigraphic interval (355-1 105 m across the audited
wells), and substituting it produced the x10-x32 artifacts in the literature
review. Option A forces every caller through a field they cannot populate, and
the failure mode is the substitution `ThicknessKind` exists to prevent.

**Verdict: correct in principle, unusable in practice, actively dangerous here.**

### Option B -- gross + net, model derives NTG

```
caller supplies:  gross_thickness_m, thickness_m
model derives:    net_to_gross = thickness_m / gross_thickness_m
```

Inherits Option A's blocker (still needs gross) and adds a consistency surface:
two independent numbers that can contradict each other, requiring the validation
in section 5.

It has one advantage over A -- a caller whose workflow *does* produce both can
supply both and have the ratio checked. But it cannot be the required form.

**Verdict: viable as an optional path, not as the contract.**

### Option C -- keep net thickness, require an NTG declaration

```
caller supplies:  thickness_m           (unchanged)
                  net_to_gross          (new, as a range)
                  net_to_gross_basis    (new, an enum)
model derives:    nothing
```

The caller is not asked for a gross thickness. They are asked to declare **the
net-to-gross implied by the net thickness they just supplied**, and how they
know it.

`net_to_gross_basis` -- a provenance enum mirroring the project's existing
`Provenance` and `EvidenceClass` vocabulary:

| Value | Meaning |
| --- | --- |
| `log_derived` | From a cutoff applied to GR/SP/resistivity over a defined interval |
| `core_derived` | From core |
| `model_derived` | From a static or geocellular model |
| `analogue` | From a comparable field or published analogue |
| `assumed` | A judgement call, no data |
| `unknown` | The caller does not know |

**This is the only option that works with the data that exists**, and it is
strictly additive: `thickness_m` keeps its meaning and its validation.

**Verdict: recommended. See section 8 for the phasing.**

---

## 5. Validation rules

Designed for Option C with Option B available as an optional path. `G` = gross,
`N` = net, `R` = NTG range.

| # | Case | Rule | Rationale |
| --- | --- | --- | --- |
| 1 | N + R, consistent | **Accept** | The Option C contract |
| 2 | G + R, no N | **Accept**, derive `N = G x R` | Option A path, for callers who have gross |
| 3 | G + N, no R | **Accept**, derive `R = N / G` | Option B path |
| 4 | G + N + R, consistent within tolerance | **Accept**, keep all three, record the residual | Over-determined but coherent |
| 5 | G + N + R, inconsistent | **Reject**, name all three values and the implied ratio | Never silently pick one |
| 6 | N only | **Reject** under the final contract; **accept with a warning** in phase 1 | See section 6 |
| 7 | `G <= 0` | **Reject** | Matches the existing `minimum_exclusive: 0.0` |
| 8 | `N > G` | **Reject** | Net cannot exceed gross. This is the check that catches a gross/net swap |
| 9 | `R` outside `(0, 1]` | **Reject** | `NTG = 1` is legal (a clean sand); `NTG = 0` means no reservoir |
| 10 | `R` is a point value | **Accept with a warning** | Section 3: a point narrows the band by ~15% |
| 11 | `R` low > high | **Reject** | Same as the existing `UniformPriors` ordering check |
| 12 | `basis = unknown` | **Accept with a warning**, and mark the result | An honest "I don't know" must be expressible, and visible |
| 13 | `basis` absent while `R` present | **Reject** | A number without provenance is what this design exists to eliminate |
| 14 | `R` outside the published `E_h` range (0.25-0.75) | **Accept with a warning** | The published range is North American; a genuine Italian NTG may fall outside it and must not be rejected |

**Tolerance for case 4/5.** The consistency check is `abs(N - G x R) <= tol`.
Given that the project already treats depth agreement at 1 m as a `Conflict`
rather than an error, the natural choice is a **relative** tolerance of 1%, with
the discrepancy recorded as a `Conflict` rather than swallowed. That reuses an
existing mechanism instead of inventing one.

**Rule 8 deserves emphasis.** It is the only rule that catches the substitution
the whole `ThicknessKind` taxonomy exists to prevent. With gross optional, it
only fires when gross is supplied -- which is an argument for encouraging
Option B's path even though it cannot be required.

---

## 6. Backward compatibility

Measured blast radius:

| Symbol | `src/` | `tests/` | `docs/` | `frontend/` |
| --- | --- | --- | --- | --- |
| `REQUIRED_USER_INPUTS` | 2 | 1 | 0 | 0 |
| `USER_INPUT_SPEC` | 2 | 2 | 2 | 0 |
| `UserInputsModel` | 1 | 0 | 0 | 0 |
| `thickness_m` | 15 | **22** | 4 | 7 |

The `thickness_m` row is the cost. Adding a **required** field breaks every one
of those 22 test files and every existing caller, because
`UserInputs.from_mapping` rejects unknown keys *and* names missing ones -- the
strictness that makes the contract trustworthy also makes it rigid.

**Three-tier phasing avoids that:**

| Phase | `net_to_gross` | Behaviour | Numbers change? |
| --- | --- | --- | --- |
| **1** | Optional | Recorded in provenance and echoed in the result. Absent -> a warning in `interpretation.warnings`, exactly like `SCALE_MISMATCH_WARNING` | **No. None at all.** |
| **2** | Optional | Phase 1 plus: when supplied, report both the current capacity and the B-prime capacity side by side, as `compare_temperature_methods()` already does for temperature | No -- the headline number is unchanged |
| **3** | Required | Contract change, major version | Only if a formulation change is separately approved |

**Phase 1 changes no computed value.** It is pure disclosure, it breaks no
caller, and it is the phase that actually removes the defect: after it, every
result either states its NTG or states that it does not know.

Phase 2 is the scientifically interesting one -- it makes B-prime *testable per
caller* without adopting it, which is exactly what the B-prime experiment said
was missing.

---

## 7. Impact on the four audited wells

**Phase 1: none.** Capacity for SALUZZO|1, DESANA|1, MALOSSA|15 and
TRECATE|9|ST is byte-identical, because nothing in the equation changes. The
only difference is that each result would carry either a declared NTG or an
explicit "not declared" warning.

**Phase 2**, if a caller declared an NTG, the side-by-side would show the
current P50 and the B-prime P50 (x1.93, per the control experiment) with the
declared NTG printed next to both -- letting the caller see that the current
number assumes 0.477 and judge whether their reservoir resembles that.

**Two of the four wells have a complication that this interface must not
obscure.** MALOSSA|15 and TRECATE|9|ST bottom in carbonate
(`CALCARI`, `CALCARI,MARNE E DOLOMIE`), per
`docs/piemonte-ntg-evidence.md`. "Net-to-gross" as a *net sand* fraction is a
clastic concept. For a carbonate reservoir the analogous quantity is a
reservoir-quality or porosity cutoff, which is not the same measurement.

The `net_to_gross_basis` enum partly handles this -- a carbonate caller would
choose `log_derived` or `core_derived` and mean something different by it. But
**the interface should not pretend the two are the same quantity**, and this
design does not resolve that. It is recorded in section 8.

---

## 8. Additional geological data eventually required

| # | Required | For what | Status |
| --- | --- | --- | --- |
| 1 | **A Piemonte or Po Plain NTG** | To judge whether a caller's declaration is plausible, and to populate a default | **Not available** -- `piemonte-ntg-evidence.md` |
| 2 | **A formation gross thickness** | Options A and B; also Candidates B and C from the literature review | **Not available** |
| 3 | **A cutoff convention** | Two callers can report different NTG for the same rock under different cutoffs | **SETTLED 2026-09-21**: caller-declared via a mandatory `net_criterion`, mirroring `TemperatureMethod`. See `docs/net-to-gross-semantics.md` |
| 4 | **A carbonate-equivalent definition** | Two of the audited wells are carbonate | **SETTLED 2026-09-21**: none needed. The DOE criterion is lithology-neutral, so one field serves both. See `docs/net-to-gross-semantics.md` section 7 |
| 5 | **Lithology-specific `E_h` ranges (IEA GHG 2009)** | To make the rule-14 warning meaningful rather than generic | Identified, not obtained |

**Items 3 and 4 are design inputs, not geology**, and both are answerable by
decision rather than by fieldwork. Item 3 in particular should be settled before
phase 1 ships, because the field's meaning depends on it.

---

## 9. Recommended design

**Option C, phased, with NTG as a range and a mandatory basis.**

```
user_inputs: {
  area_m2:     8.0e7,          # unchanged
  thickness_m: 35.0,           # unchanged: NET, as today

  net_to_gross: {              # NEW, optional in phase 1
    low:   0.30,
    high:  0.55,
    basis: "log_derived",      # required whenever net_to_gross is present
    note:  "GR cutoff 60 API over the 1200-1450 m interval"   # optional
  }
}
```

**Why this shape:**

1. **A range, not a point** -- section 3 showed a scalar silently narrows the
   band by 15%. The range is the honest representation and it is consistent with
   how the project already carries `porosity` and `storage_efficiency`.
2. **`basis` required when `net_to_gross` is present** (rule 13) -- the project's
   existing standard is that every adopted value carries provenance; a bare NTG
   would be the only scientific number in the system without it.
3. **`thickness_m` untouched** -- 22 test files, 7 frontend files and every
   existing caller keep working.
4. **Gross stays optional**, enabling rule 8's swap check for callers who have
   it, without forcing the substitution that Option A would invite.
5. **Phase 1 changes no number** -- the defect is removed before any scientific
   question is settled.

**What this design explicitly does not do:** it does not choose a Piemonte NTG,
does not supply a default, does not remove `E_h`, does not change the equation,
and does not decide Finding 3.1. It makes the hidden assumption visible so that
decision can be taken on evidence rather than in the dark.

---

## Method note

Section 1 is traced from `src/` by inspection. Section 3's figures are from a
Monte Carlo at N = 500 000, seed 42, using the CSLF component ranges verbatim;
the mean-matching value of 0.4999 is a check against the analytic `E[E_h] = 0.5`.
Section 6's blast radius is a `grep` count over the working tree.

**Separation of fact from proposal:** sections 1, 2 and 6 describe the system as
it is. Section 3 is measurement. Sections 4, 5, 7, 8 and 9 are **proposals**, and
nothing in them has been implemented.
