# `net_to_gross` -- semantic specification

**Settled before any Phase 1 draft.** Companion to
`docs/ntg-elicitation-design.md`.

**Specification only.** No file under `src/`, no equation, no constant, no API
behaviour and no test was modified. No Piemonte NTG value is chosen and no
numerical cutoff is introduced.

---

## Decision

> ### A. Semantic contract closed -- Phase 1 can now be drafted.

The contract closes **because the cutoff is caller-declared, not
project-mandated.** That is not a dodge; it is the only consistent reading of
the sources, and it is exactly how this project already handles temperature.

Two facts make it work:

1. **The DOE criterion is lithology-neutral**, so carbonate needs no second
   field (section 7).
2. **`thickness_m` already carries this ambiguity today, unmandated.** Adding
   `net_to_gross` with a declared criterion *reduces* the ambiguity rather than
   introducing it (section 11).

The cutoff *value* remains an evidence input. The cutoff *convention* -- that
the caller states theirs -- is now defined.

---

## 1. Canonical definition

```
                 thickness within the gross interval that satisfies
                 the caller's declared reservoir-quality criterion
net_to_gross  =  ---------------------------------------------------
                 gross thickness of the same interval
```

**Numerator:** the summed thickness of rock inside the gross interval that meets
the criterion the caller declares in `net_criterion`.

**Denominator:** the gross thickness of that same interval, measured the same
way.

### Why this wording, and not "net sand"

The collected sources do not agree, and the disagreement is not cosmetic:

| Source | Criterion, verbatim | Lithology-specific? |
| --- | --- | --- |
| **CSLF-T-2008-04** | *"Fraction of the geological unit that has the **porosity and permeability required for CO2 injection**"* | **No** |
| **CO2-SCREEN (DOE)** | *"Net-to-Gross Thickness: Fraction of formation thickness **available for CO2 storage**"* | **No** |
| **Donda et al. 2011** | *"the sum of thicknesses of each **permeable coarse-grained, sandy-gravelly layer**"*, with GR and SP giving *"the thickness of any clay interbeds"* | **Yes -- clastic** |
| **CO2StoP** | *"average net to gross ratio of regional aquifer"* -- undefined | not stated |

The quantity this project needs is **whatever `E_h` represents**, because
`net_to_gross` exists to make explicit the thing `E_h` currently supplies
implicitly. `E_h` is defined by CSLF and DOE as a **property** cutoff
(porosity and permeability), not a **lithology** cutoff.

So the canonical definition is property-based. Donda's net-sand measurement is a
*valid but different* way of estimating it, and is representable through
`net_criterion` rather than through a different field.

### Thickness convention

**The numerator and denominator must use the same thickness convention.** Under
that condition the ratio is invariant to which convention it is -- measured,
true vertical, or true stratigraphic all cancel.

The canonical decomposition states *"the fraction of the geological formation
**in the vertical dimension**"*, so true vertical is the reference convention
where it is known. The project's own depths are measured depth (Phase 4 Finding
4.4), and no deviation survey exists.

**Rule:** the ratio is accepted under any convention provided both terms share
it; mixing conventions between numerator and denominator is invalid and is the
one thickness error this field can still hide.

### Is this "net-to-gross" or "reservoir-quality fraction"?

**It is a reservoir-quality fraction, and it keeps the name `net_to_gross`.**

Naming it `reservoir_quality_fraction` would be more accurate and would sever
the link to every source the project cites -- CSLF, CO2-SCREEN, CO2StoP, Donda
and Wojcicki all say "net-to-gross" or "NG". CO2-SCREEN itself attaches the name
"Net-to-Gross Thickness" to a lithology-neutral definition.

**The name is the literature's; the semantics are the source's.** The gap
between them is closed by making `net_criterion` mandatory, so the field can
never be read as net sand unless the caller says so.

---

## 2. Scope and applicability

| Applies to | Does not apply to |
| --- | --- |
| The gross interval the caller's `thickness_m` was derived from | The gross **chronostratigraphic** interval in `record.gross_thickness_m` |
| Clastic and carbonate reservoirs alike (section 7) | The aquifer hydraulic thickness used by Theis |
| One well or one storage complex per request | Regional or basin averages, unless the caller says so via `net_criterion` |

**It is scoped to the caller's own interval.** The project holds a
`gross_thickness_m` per well, but that is the whole logged chronostratigraphic
section (355-1 105 m across the audited wells) and is **not** a valid denominator
(`docs/piemonte-ntg-evidence.md`).

---

## 3. Required basis and provenance

Two mandatory companions whenever `net_to_gross` is present. The pattern
deliberately mirrors `TemperatureMethod` (section 4).

### `net_criterion` -- *what test defined "net"*

| Value | Meaning | Matches `E_h`? |
| --- | --- | --- |
| `porosity_permeability` | Both a porosity and a permeability cutoff | **Exactly** -- this is CSLF's wording |
| `porosity_only` | A porosity cutoff alone | Partially |
| `permeability_only` | A permeability cutoff alone | Partially |
| `lithology_net_sand` | Net sand from lithology, e.g. GR/SP clay-interbed exclusion. **Donda's method** | Approximately, for clastics |
| `flow_unit` | From a static or dynamic reservoir model | Approximately |
| `unspecified` | The caller cannot say | **No** |

### `net_basis` -- *how it was obtained*

`log_derived` | `core_derived` | `model_derived` | `analogue` | `assumed` |
`unknown`

The two are orthogonal: a `porosity_permeability` criterion can be `log_derived`
or `core_derived`; a `lithology_net_sand` criterion is almost always
`log_derived`.

### Optional but encouraged

`cutoff_note` -- free text stating the actual thresholds and the interval, e.g.
the log used, the numeric cutoff and the depth range. **The project does not
mandate any value here** (section 5).

---

## 4. Fit with the existing architecture

| Component | Interaction | Verdict |
| --- | --- | --- |
| **`ThicknessKind`** | `net_to_gross` is the *ratio between* `GROSS_STRATIGRAPHIC` and `NET_STORAGE`. It names the arrow the enum's three nodes already imply | **Completes it.** No change to the enum |
| **`thickness_m`** | Unchanged: still net, still required, still `> 0`, same validation | **No second meaning.** See below |
| **`gross_thickness_m`** | Untouched. Explicitly **not** the denominator | No change |
| **`Assumption`** | `net_to_gross` is caller-supplied, so it is an `Assumption` with `author="caller (user input)"`, exactly like `area_m2` and `thickness_m` | Fits directly |
| **`EvidenceClass`** | `net_basis` maps onto the existing vocabulary: `core_derived`/`log_derived` -> `site_specific`; `analogue` -> `regional`; `assumed` -> `user_input`; `unknown` -> `unsupported` | Reuses it |
| **Conflict handling** | If gross and net are both supplied and `net / gross` disagrees with the declared ratio, that is a `Conflict`, not an error, at 1% relative tolerance | Reuses it |
| **Blocking** | `net_to_gross` is **not** blocking in Phase 1. Its absence produces a warning, not a `blocked` status | Preserves the contract |
| **Four-label partition** | **`net_to_gross` must NOT enter `screening_inputs`** | See below |

### The partition must stay clean

`screening_inputs` is a disjoint partition over exactly the six equation
parameters, and `source_derived_inputs` + `modelled_inputs` + `assumed_inputs` +
`user_supplied_inputs` must continue to cover it exactly. Phase 10 verified this
holds for all five screenable wells.

**In Phase 1 `net_to_gross` is metadata about how `thickness_m` was obtained, not
a seventh equation parameter.** It belongs in a `thickness_provenance` block
alongside `user_inputs`, not inside `screening_inputs`. Putting it in the
partition would break the invariant the audit spent Phase 10 confirming.

If a later phase makes `net_to_gross` an actual multiplier, *that* is when it
enters the partition -- and that is a separate decision.

### Why `thickness_m` gains no second meaning

`thickness_m` means net storage thickness today and continues to. What changes
is that the caller must additionally say **what "net" meant to them**. The field
is not redefined; its interpretation is made recoverable.

---

## 5. What counts as valid evidence, and what does not

### Valid

| Evidence | `net_criterion` | `net_basis` |
| --- | --- | --- |
| Porosity + permeability cutoffs applied over a stated interval | `porosity_permeability` | `log_derived` / `core_derived` |
| Core-measured net pay | `porosity_permeability` | `core_derived` |
| GR/SP clay-interbed exclusion, Donda's method | `lithology_net_sand` | `log_derived` |
| Net-to-gross read from a static model | `flow_unit` | `model_derived` |
| A published value for a comparable field, cited | any | `analogue` |
| An explicit engineering judgement, declared as such | any | `assumed` |

### Not valid

| Not evidence | Why |
| --- | --- |
| **`net_thickness / record.gross_thickness_m`** | The denominator is the chronostratigraphic interval, not a formation. This is the substitution `ThicknessKind` exists to prevent |
| **The CO2StoP default of 0.25** | Its own source calls it a default *"if limited information is available"* |
| **The CSLF range 0.25-0.75** | North American, generic, and it is `E_h` itself -- supplying it as `net_to_gross` would be circular |
| **Inference from a qualitative lithology string** | `SABBIE E ARGILLE` states which lithologies are present, not in what proportion (`piemonte-ntg-evidence.md`) |
| **A value with no `net_criterion`** | Rejected. A number whose definition is unknown is the defect this field exists to remove |

The third row deserves emphasis: **supplying CSLF's own `E_h` range as the
caller's `net_to_gross` would be circular** and must be rejected in review even
though no validation rule can detect it.

---

## 6. Clastic treatment

A clastic caller may use either `porosity_permeability` (the DOE definition) or
`lithology_net_sand` (Donda's). Both are accepted; they are not the same
measurement and the criterion records which was used.

A well-cemented sandstone counts as "sand" but may fail a permeability cutoff.
The two criteria can therefore give different numbers for the same rock, and
neither is wrong -- which is precisely why the criterion must be declared rather
than assumed.

---

## 7. Carbonate treatment

**Option 2: one generalised field. The justification is source semantics, not
API convenience.**

The DOE/CSLF criterion is *"the geological unit that has the porosity and
permeability required for CO2 injection"*. That sentence contains no lithology
term. A vuggy or fractured dolomite that meets a porosity and permeability
cutoff satisfies it exactly as a clean sandstone does. **`E_h` was never a
net-sand ratio**; the name is clastic, the definition is not.

So a carbonate caller -- MALOSSA|15 or TRECATE|9|ST, both of which bottom in
`CALCARI` and `CALCARI,MARNE E DOLOMIE` -- supplies `net_to_gross` with
`net_criterion = porosity_permeability` and means something well-defined.

**Options 1 and 3 were considered and rejected:**

| Option | Why rejected |
| --- | --- |
| **1. Clastic-only NTG** | Would leave two of the five screenable wells with no way to declare the quantity `E_h` represents, while `E_h` itself applies to them perfectly well |
| **3. Two fields** | A caller with one number must decide which field it goes in; the model must decide which feeds `E_h`; both-supplied is ambiguous. It duplicates the field to express a distinction the criterion enum already expresses |

**What Option 2 does not do.** `lithology_net_sand` remains meaningless for
carbonate, and a carbonate caller selecting it should be warned. The
distinction the brief was right to protect is preserved -- in the criterion,
where it belongs, rather than in a duplicated field.

---

## 8. Units

**Dimensionless.** A ratio of two thicknesses in the same convention.

Not a percentage: expressed as a fraction, consistent with how `porosity` and
`storage_efficiency` are already carried. `unit: "-"` in `USER_INPUT_SPEC`
terms.

---

## 9. Valid numerical domain

`0 < net_to_gross <= 1`

| Bound | Reason |
| --- | --- |
| `> 0` strictly | `net_to_gross = 0` means no reservoir, which makes capacity zero and is better expressed by not screening the well |
| `<= 1` inclusive | `= 1` is legitimate: a clean interval where all rock meets the cutoff |
| Outside `(0, 1]` | Reject. A ratio of a part to its whole cannot exceed 1 |
| Outside `0.25-0.75` | **Accept with a warning.** That range is CSLF's North American `E_h`; a genuine Italian value may fall outside it and must not be rejected |

---

## 10. Range or point?

**A range is required. A point is accepted with a warning.**

The B-prime control experiment measured the consequence: replacing the
distributed `E_h` with a scalar narrows the reported band by about 15%
(span/P50 1.781 -> 1.515) while leaving the median unmoved -- a silent increase
in apparent confidence. Supplying `net_to_gross` as a range restores it.

This also matches how the project already carries every other uncertain
parameter: `porosity`, `storage_efficiency` and `pressure_pa` are all `(low,
high)` pairs.

**Shape:** `{low, high}` with `low <= high`, reusing the `UniformPriors`
ordering check. `low == high` is the point case: permitted, warned.

---

## 11. Can the project populate it today?

**No -- and that is the honest state, not a blocker for the contract.**

> NTG cannot yet be populated from project-held data; the semantic field can be
> defined, but the **cutoff value** remains an evidence/design input.

| Would-be source | Status |
| --- | --- |
| GEOTHOPICA workbook | No GR, SP, resistivity, density or neutron. Lithology is qualitative |
| Digital logs (LAS) | Zero on disk; zero of the 57 national LAS wells match our 46 |
| Composite-log PDFs | 42/46 present, single-page raster, zero text layer |
| Literature | No Piemonte NTG exists (`piemonte-ntg-evidence.md`) |

**Why the contract still closes.** The project is not required to *compute* this
value -- the caller supplies it, exactly as they already supply `area_m2` and
`thickness_m`, neither of which the project can compute either.

And the decisive point: **`thickness_m` already embeds an undeclared cutoff
today.** Every capacity number the tool has ever produced rests on a caller's
private definition of "net" that the API never asked about and never recorded.
Adding `net_to_gross` with a mandatory `net_criterion` does not introduce that
problem; it surfaces it.

**The precedent is `TemperatureMethod`.** The project does not mandate one
temperature method. It records which was used, ranks them, preserves the
alternatives as `Conflict`s, and exposes the spread through
`compare_temperature_methods()`. A caller-declared `net_criterion` is the same
pattern applied to thickness, and it is the pattern the codebase already
demonstrates works.

---

## 12. API field semantics

```
user_inputs: {
  area_m2:     8.0e7,               # unchanged
  thickness_m: 35.0,                # unchanged: NET, as today

  net_to_gross: {                   # NEW, optional in Phase 1
    low:  0.30,                     # required, 0 < low <= high <= 1
    high: 0.55,                     # required
    net_criterion: "porosity_permeability",   # REQUIRED when present
    net_basis:     "log_derived",             # REQUIRED when present
    cutoff_note:   "...",                     # optional, free text
    thickness_convention: "measured"          # optional: measured|tvd|tst
  }
}
```

| Field | Required | Semantics |
| --- | --- | --- |
| `low`, `high` | yes, when the block is present | The ratio's range. Point value allowed via `low == high`, warned |
| `net_criterion` | **yes** | What test defined "net". Rejecting a value without it is the core of this contract |
| `net_basis` | **yes** | How it was obtained. Maps to `EvidenceClass` |
| `cutoff_note` | no | The actual thresholds. Encouraged; not validated |
| `thickness_convention` | no | Declares the shared convention. Absent means "same for both, unstated" |

**Phase 1 behaviour:** recorded as an `Assumption`, echoed in a
`thickness_provenance` block, **not** placed in `screening_inputs`, **not** used
in any computation. Absence produces a warning in `interpretation.warnings`
alongside `SCALE_MISMATCH_WARNING`.

**Capacity for all four audited wells is byte-identical in Phase 1.**

---

## What remains open after this specification

| # | Open item | Blocks Phase 1? |
| --- | --- | --- |
| 1 | A defensible Piemonte NTG **value** | **No** -- Phase 1 records, never computes |
| 2 | A project-recommended cutoff **value** | **No** -- caller-declared by design |
| 3 | Whether `net_criterion` should be **ranked**, as `TemperatureMethod` is | **No**, but it is the natural next refinement, and `porosity_permeability` would rank first as the definition `E_h` actually uses |
| 4 | Whether removing `E_h` is correct | **No** -- that is Finding 3.1 and Phase 1 does not touch it |

**None of the four blocks a Phase 1 draft**, because Phase 1 changes no number.

---

## Method note

Sections 1, 5, 6 and 7 are grounded in verbatim quotations from CSLF-T-2008-04,
the CO2-SCREEN User's Manual, Donda et al. (2011) and the CO2StoP Final Report,
all read in full from local extractions. Section 4 is traced from `src/` by
inspection. Section 10's measurement is from the B-prime control experiment.

**Separation of source from proposal:** the source-comparison table in section 1
is fact. Everything else -- the canonical definition, the two enums, the
carbonate resolution, the domain and the field layout -- is **this
specification's proposal**, and none of it is implemented.

## Phase 14 addendum: the approved model

*Added in Phase 14. The specification above is unchanged and continues to
describe the `NOT_VALIDATED` legacy paths, where `thickness_m` is a caller net
thickness.*

The Phase 13 Model Contract (`docs/phase13-owner-decision-record.md`) changes
what the ratio refers to on the approved model, without adding any number:

- There is no `thickness_m` input. The thickness term is `h_g = z_base - z_top`,
  the gross thickness of the caller-designated storage-assessment interval
  (A1, M1).
- A declared `net_to_gross` is read as `h_net / h_g` for that interval. It is a
  consistency/provenance check only (S12): with `0 < net_to_gross <= 1`,
  `0 < h_net <= h_g` holds by construction. It is reported in
  `net_to_gross_check` with `used_in_calculation: false`.
- It never enters the capacity equation: the gross-to-net reduction is
  represented inside the aggregate storage efficiency E (A4, A5), and E is never
  divided by it.
- It is not identified with DOE `hn/hg` (A3), and no Piemonte value is
  introduced (numerical NTG remains evidence-blocked).
- The `net_to_gross_not_declared` and `net_to_gross_point_value` advisories do
  not apply on the approved model, where the Finding 9.1 double count cannot
  arise by construction.
