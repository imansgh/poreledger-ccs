# `E_V3` semantics -- is the buoyancy term compatible with a net-thickness input?

**Evidence item 2 from the B-prime control experiment.**

Resolved 2026-09-21. Companion to `docs/bprime-control-experiment.md`,
`docs/finding-3.1-literature-review.md` and `docs/piemonte-ntg-evidence.md`.

**Research only.** No file under `src/`, no production equation, no constant, no
API behaviour and no scientific test was modified.

---

## Decision

> ### `E_V3` is independent of NTG -> B-prime remains mathematically and scientifically plausible.

`E_h` and `E_V3` act on **different quantities at different stages of the same
chain**: `E_h` reduces gross rock to reservoir-quality rock, and `E_V3` reduces
reservoir-quality rock to the part a buoyant plume actually contacts. They are
sequential, not overlapping. Supplying a net thickness and retaining `E_V3` is
semantically coherent.

**This removes the objection, it does not make B-prime correct.** The blocking
issue from the B-prime experiment was never `E_V3`; it was that B-prime relocates
the net-to-gross assumption into an unobservable value implicit in the caller's
thickness. That remains unchanged.

---

## 1. Source-by-source definition

### 1.1 CO2-SCREEN User's Manual (DOE-NETL, 2020) -- **primary, read in full**

The only source read here that defines `E_V` explicitly. Glossary, verbatim:

> **Volumetric Displacement `E_V`** -- *"The combined fraction of immediate
> volume surrounding an injection well that can be contacted by CO2 **and the
> fraction of net thickness that is contacted by CO2** as a consequence of the
> density difference between CO2 and in-situ water"*

> **Net-to-Gross Thickness `E_h`** -- *"Fraction of formation thickness
> available for CO2 storage"*

> **Thickness `h_g`** -- *"Average **gross** thickness of formation being
> assessed for CO2 storage"*

> **Microscopic Displacement `E_d`** -- *"The fraction of pore space unavailable
> due to immobile in-situ fluids"*

Two things follow directly. `E_V` is a **composite** of an areal sweep term and
a buoyancy term. And the buoyancy half is stated as operating on **net
thickness** -- which, in a system whose only declared input is `h_g`, can only
mean `h_g x E_h`.

### 1.2 CSLF-T-2008-04 (Bachu, 2008) -- **primary, read in full**

Lists seven components, verbatim, as separate lines:

```
- Fraction of the saline aquifer that is suitable for CO2 storage: 0.2 to 0.8
- Fraction of the geological unit that has the porosity and permeability
  required for CO2 injection: 0.25 to 0.75
- Fraction of interconnected porosity: 0.6 to 0.95
- Areal displacement efficiency: 0.5 to 0.8
- Vertical displacement efficiency: 0.6 to 0.9
- Fraction of net aquifer thickness contacted (occupied) by CO2 as a result of
  CO2 buoyancy: 0.2 to 0.6
- Pore-scale displacement efficiency: 0.5 to 0.8.
```

The net-to-gross term (line 2) and the buoyancy term (line 6) are **enumerated
separately**, with different ranges and different stated causes: one is a
*rock-property cutoff* ("porosity and permeability required"), the other is a
*fluid-physics sweep* ("as a result of CO2 buoyancy").

### 1.3 Goodman et al. (2011) -- **not obtained; represented indirectly**

`osti.gov` refused connections on four separate attempts across two sessions,
and the ScienceDirect copy returned HTTP 403. The paper is represented here by
the CO2-SCREEN manual, which states it implements *"the methodology detailed in
Goodman et al. (2011) and refined in Goodman et al. (2016)"*, and by search
metadata giving its equation:

> `G = A_d x h_d x phi_d x rho_d x E_saline`, where *"h_d is the **gross
> thickness** of the formation"* and *"phi_d is the **total porosity**"*.

Consistent with 1.1. **Grade: secondary.**

### 1.4 The six-term canonical decomposition -- **secondary**

Widely reproduced in the derivative literature as:

```
E_saline = E_An/At x E_Hn/Hg x E_phie/phit x E_A x E_V x E_d
```

with *"`E_Hn/Hg` is the fraction of the geological formation **in the vertical
dimension** that meets the porosity and permeability requirements for CO2
injection and storage"* and `E_A`, `E_V`, `E_d` as areal, vertical and
microscopic **displacement** terms.

**Grade: secondary**, but it corroborates 1.1 and 1.2 and explains the term-count
difference (see section 2).

### 1.5 Myshakin et al. (2022) -- **not obtained**

Paywalled. It refines the numeric values of `E_V` and `E_d` from new relative
permeability data; nothing in this report depends on it, because the question is
semantic rather than numeric.

---

## 2. Reconciling three published term counts

The same decomposition appears with seven, six and five terms. They are not
different methods; they are different groupings.

| CSLF 2008 (7 terms) | Canonical (6 terms) | CO2-SCREEN (5 terms) | Kind |
| --- | --- | --- | --- |
| Fraction of aquifer suitable | `E_An/At` | `E_A` | geometric |
| **Fraction with required poro/perm** | **`E_Hn/Hg`** | **`E_h`** | **geometric** |
| Fraction of interconnected porosity | `E_phie/phit` | `E_phi` | geometric |
| Areal displacement efficiency | `E_A` | \ | displacement |
| Vertical displacement efficiency | `E_V` | > `E_V` | displacement |
| **Fraction of net thickness contacted (buoyancy)** | (within `E_V`) | / | **displacement** |
| Pore-scale displacement efficiency | `E_d` | `E_d` | displacement |

The three geometric terms are stable across all three groupings. The
displacement terms are progressively merged: CSLF's areal, vertical and buoyancy
lines become `E_A` + `E_V` in the six-term form, and a single `E_V` in
CO2-SCREEN -- which is exactly why CO2-SCREEN's `E_V` glossary entry describes
**two** things joined by "and".

**`E_V3` is not a term in any source's notation.** It is the label this project
gave to CSLF's sixth line. Its canonical home is inside `E_V`.

---

## 3. Dependency map

Every arrow carries the source-defined factor that produces it.

```
  GROSS FORMATION          h_g            "Average gross thickness of formation
       |                                   being assessed"  [CO2-SCREEN]
       |
       |  E_h  /  E_Hn/Hg  /  CSLF line 2
       |  "fraction of formation thickness available for CO2 storage";
       |  "meets the porosity and permeability requirements"
       |  RANGE 0.25 - 0.75          <-- ROCK-PROPERTY CUTOFF
       v
  NET RESERVOIR            h_g x E_h
       |
       |  E_V3  /  within E_V  /  CSLF line 6
       |  "the fraction of NET thickness that is contacted by CO2 as a
       |   consequence of the density difference between CO2 and in-situ water"
       |  RANGE 0.20 - 0.60          <-- FLUID-PHYSICS SWEEP
       v
  CO2-CONTACTED NET        h_g x E_h x E_V3
       |
       |  E_phi  (total -> effective porosity)   [acts on POROSITY, not thickness]
       |  E_A    (net-to-total AREA)             [acts on AREA, not thickness]
       |  E_d    (pore-scale displacement)       [acts on PORE SPACE]
       v
  STORED CO2 VOLUME
```

**The answer to the framing question:** `E_V3` acts on **net -> contacted net**.
It does **not** act on gross -> net. That arrow is `E_h`, and only `E_h`.

---

## 4. Are `E_h` and `E_V3` independent or overlapping?

**Independent.** Four lines of evidence, none of which is terminology alone:

1. **Different physical causes, stated in the sources.** `E_h` is a cutoff on
   rock properties ("porosity and permeability required"). `E_V3` is a
   consequence of fluid density ("as a consequence of the density difference
   between CO2 and in-situ water"). Neither could substitute for the other.
2. **Enumerated separately in the same list**, with different ranges
   (0.25-0.75 versus 0.20-0.60).
3. **Grouped on opposite sides of the geometric/displacement split** in the
   six-term canonical form: `E_h` is geometric, `E_V3` is displacement.
4. **`E_V3`'s own wording presupposes that `E_h` has already been applied.** It
   says *net* thickness. A factor that operated on gross -> net could not
   describe its own input as net.

Point 4 is the decisive one, and it is the inverse of the naive argument the
brief warned against. The brief cautioned against reasoning *"`E_V3` says net,
therefore `E_h` can be removed"*. That inference is indeed invalid. The valid
inference runs the other way: **`E_V3` saying "net" tells us where `E_V3` sits in
the chain -- downstream of `E_h` -- which is evidence that the two are
sequential rather than competing.**

### One unresolved oddity, recorded rather than resolved

CSLF's seven-term list contains **both** *"Vertical displacement efficiency:
0.6 to 0.9"* **and** the buoyancy term *"0.2 to 0.6"*. Both concern vertical
sweep. Whether that is itself a partial double-count **inside the published
decomposition** is not resolved by any source read here.

It does not affect this report's conclusion: whatever those two terms
individually mean, both are displacement terms acting on net thickness, neither
is a gross-to-net cutoff, and the Step 1 control confirmed that the seven-term
product reproduces the published 1-4% range. The decomposition is internally
consistent *as published*, which is what matters for deciding where `E_h` lives.

---

## 5. Is B-prime semantically valid?

**On the `E_V3` axis, yes.** Numerical demonstration, N = 200 000, seed 42,
1 000 m gross formation, caller's implied NTG = 0.4769 (from the B-prime
experiment):

| Formulation | Chain | Contacted thickness P10 / P50 / P90 |
| --- | --- | --- |
| **DOE** | `h_g x E_h x E_V3` | 100.7 / **185.8** / 322.5 m |
| **B-prime** | `h_net x E_V3` | 114.5 / **190.7** / 267.0 m |
| **Status quo (A)** | `h_net x E_h x E_V3` | 48.0 / **88.6** / 153.8 m |

DOE and B-prime agree closely at the median, as they must when the caller's NTG
approximates `E_h`. The status quo produces **roughly half** the contacted
thickness, because `E_h` is applied to rock that is already net -- the
double-count, seen directly in thickness units rather than through the
efficiency factor.

All three remain physical: maximum contacted thickness is 0.449, 0.286 and 0.214
of gross respectively, never exceeding 1.

Order independence was checked and holds exactly, but it is **necessary and not
sufficient** -- it holds for any two scalars and says nothing about semantics.
The semantic argument is section 4.

---

## 6. Is a gross-thickness + NTG formulation possible?

**Yes, and it is the formulation the sources actually specify.** Two variants:

| Variant | Equation | Status |
| --- | --- | --- |
| **Candidate B** (DOE-conformant) | `A x h_g x phi_tot x rho x (E_A E_h E_phi E_V E_d)` | Requires a **formation** gross thickness |
| **Candidate C** (CO2StoP/EU) | `A x h_g x NG x phi x rho x S_eff` | Requires gross thickness **and** an explicit NG |

Both are blocked by the same missing input, established in
`docs/piemonte-ntg-evidence.md`: the only "gross" thickness this project holds is
the gross **chronostratigraphic** interval (355-1 105 m across the audited
wells), which is the whole logged section, not the gross thickness of a storage
formation. Substituting it produced the x10-x32 artifacts recorded in the
literature review.

`E_V3` poses no obstacle to either variant -- in both, `E_h` or `NG` supplies the
gross -> net arrow and `E_V3` acts downstream, exactly as the sources intend.

---

## 7. What happens if `h` is already net?

| Formulation | Gross -> net | Net -> contacted | Net-to-gross applied |
| --- | --- | --- | --- |
| DOE with `h_g` | `E_h` (documented, distributed) | `E_V3` | **once** |
| B-prime with `h_net` | caller's implicit NTG | `E_V3` | **once** |
| **Status quo with `h_net`** | caller's implicit NTG **and** `E_h` | `E_V3` | **twice** |

Supplying a net thickness does **not** break `E_V3` -- `E_V3` expects net
thickness and receives it. What it breaks is `E_h`, which then discounts rock
that has already been discounted.

So the conclusion is narrower than "B-prime is right". It is: **`E_V3` is not
the problem, and removing `E_h` does not damage `E_V3`.** Whether removing `E_h`
is the right response to the double-count remains the open question from the
B-prime experiment, and this report does not answer it.

---

## 8. Evidence still required

| # | Missing | Why it matters | Status after this report |
| --- | --- | --- | --- |
| 1 | **Goodman et al. (2011) and (2016) read directly** | The originating methodology. CO2-SCREEN implements them and is unambiguous, but the source of record was not read | `osti.gov` refused connections 4x; ScienceDirect 403. **Still open** |
| 2 | **Whether CSLF's two vertical terms overlap** | An internal question about the published decomposition; does not affect `E_h` placement | Recorded in section 4, **not resolved** |
| 3 | **Elicit the caller's NTG or gross thickness** | The actual blocker from the B-prime experiment. `E_V3` was never the blocker | **Unchanged and still blocking** |
| 4 | **A Piemonte or Po Plain NTG** | Unblocks Candidates B and C | **Unchanged** -- see `piemonte-ntg-evidence.md` |
| 5 | **Lithology-specific `E_h` ranges (IEA GHG 2009)** | CO2-SCREEN auto-populates `E_h` by lithology and depositional environment; a clastic-specific range would replace CSLF's generic 0.25-0.75 | Identified, **not obtained** |

Item 2 of the original B-prime evidence list -- the `E_V3` question -- is now
**closed**. Item 3 has not moved and is the next blocker.

---

## Method note

Two primary sources were read in full from local text extractions (CSLF-T-2008-04
and the CO2-SCREEN User's Manual); all block quotes above are verbatim from
those. Goodman et al. (2011/2016) and Myshakin et al. (2022) were **not**
obtained, and the six-term canonical decomposition is quoted from derivative
literature rather than from a source document.

**Separation of source from interpretation:** all quotations and the term-count
reconciliation in section 2 are sourced. The dependency map, the four-point
independence argument in section 4, and the thickness-chain demonstration in
section 5 are **this report's interpretation**.
