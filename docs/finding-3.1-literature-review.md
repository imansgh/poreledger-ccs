# Finding 3.1 -- literature-backed design review

**Net-to-gross and effective thickness in the CSLF-style storage-capacity equation**

Prepared 2026-09-21, after the 12-phase scientific validation audit.
**Research phase only. No file under `src/` was modified and no scientific
number was changed.**

Sources obtained and read in full are marked **[primary, read]**. One source is
cited from its abstract and search metadata only; it is marked **[secondary]**
and nothing in this report's conclusions rests on it.

---

## 1. Executive conclusion

**Finding 3.1 is confirmed from the DOE primary source, which names the failure
mode in the project's own words and prescribes a remedy.**

The DOE-NETL methodology behind the 1-4% efficiency range is unambiguous:

```
G_CO2    = A_t * h_g * phi_tot * rho_CO2 * E_saline          (CO2-SCREEN eq. 1)
E_saline = E_A * E_h * E_phi * E_V * E_d                     (CO2-SCREEN eq. 2)
```

with `h_g` defined as *"Average **gross** thickness of formation being assessed"*
and `phi_tot` as *"Average **total** porosity of formation being assessed"*, and
with `E_h` = *"Net-to-Gross Thickness: fraction of formation thickness available
for CO2 storage"* sitting **inside** `E_saline`.

The CO2-SCREEN User's Manual then states the remedy directly:

> *"If a dataset does not require an efficiency term, a user can enter a 1 (100
> percent efficiency) for the P10 and P90 range. An example of this situation
> would be if a dataset was using net area instead of gross area. In this case,
> the user would enter a 1 for the P10 and P90 range for Net-to-Gross Area **to
> avoid double discounting**."*

Our API requires **net** thickness and then applies the full 1-4% range. By the
authority that published that range, this is double discounting, and the
prescribed fix is to set the net-to-gross term to 1.

**However -- and this materially changes how the finding should be read --
our structure is also the dominant European practice.** The EU GeoCapacity /
CO2StoP methodology, and a 2025 peer-reviewed application of it, both apply a
net-to-gross reduction to thickness *and* multiply by an efficiency factor whose
numeric value is inherited from the same DOE work. The project has not invented
an error; it has inherited a genuine, unresolved divergence between the
North American and European traditions.

**Three formulations exist in the literature and they are not equivalent:**

| Tradition | Equation | `h` | NTG | `E` |
| --- | --- | --- | --- | --- |
| **DOE-NETL** | `A h_g phi_tot rho E_saline` | gross | inside `E` | 5-term product |
| **EU GeoCapacity / CO2StoP** | `A h NG phi rho S_eff` | gross | **explicit multiplier** | single value, 2% |
| **CSLF trap-scale (Bachu 2007)** | `A h phi rho C_c` | trap gross | inside `C_c` | site-specific, by simulation |

The current implementation is **EU-structured with a DOE number**, which is the
one combination none of the three sources endorses.

**No candidate is recommended yet.** The decisive missing input is a
net-to-gross estimate for the Piemonte reservoirs, which no source in this
repository provides.

---

## 2. Literature table

| # | Source | Year | Setting | Equation | `h` | NTG | `E` | Porosity | Uncertainty |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **CO2-SCREEN User's Manual** (DOE-NETL), implementing Goodman et al. 2011/2016 **[primary, read]** | 2020 | Saline formations, USA | `G = A_t h_g phi_tot rho E_saline` | **gross** (`h_g`, explicit) | **inside E** (`E_h`) | `E_A E_h E_phi E_V E_d` | **total** (`phi_tot`, explicit) | Log-odds transform, Monte Carlo 10 000, P10/P50/P90 |
| 2 | **CSLF-T-2008-04**, Bachu (Phase III report) **[primary, read]** | 2008 | Saline aquifers, methodology comparison | `M = A h phi rho_CO2 E` (eq. 15) | not stated in eq.; components imply gross | **inside E** (0.25-0.75 term) | 7 varied components | not stated; `E` contains interconnected-porosity term | Monte Carlo, P15-P85 = 1-4% |
| 3 | **CO2StoP Final Report**, Poulsen et al. (GEUS R 2014/56) **[primary, read]** | 2014 | Regional saline aquifers, 26 European countries | `M = A h NG phi rho_CO2r S_eff` | **gross** ("average height of regional aquifer") | **explicit multiplier**, default 0.25 | **single value, 2%** | "average reservoir porosity (best estimate)" | min / mean / max per field in database |
| 4 | **Donda, Volpi, Persoglia & Parushev**, IJGGC 5(2) **[primary, read]** | 2011 | 14 Italian deep saline aquifers | `M = A h phi_RS rho_CO2r S_eff` | **net** ("average thickness x average net to gross ratio") | **folded into h** | 1-4%, cited to US DOE 2008 | "average reservoir porosity", sonic-log derived | Two point cases (1%, 4%) |
| 5 | **Wojcicki**, Frontiers in Earth Science **[primary, read]** | **2025** | Regional aquifers + traps, northern Poland | `M = A h NG phi rho_CO2r S_eff` | average thickness | **explicit multiplier** | 2% regional; 3-40% traps; 13+/-8% simulated | stated as "effective porosity" | Monte Carlo 10 000; normal, porosity lognormal; +/-3 sigma |
| 6 | **GEUS for Clean Air Task Force**, EU CO2 storage summary **[primary, read]** | 2021 | EU-wide, from CO2StoP database | as #3 | gross, with net/gross cut-off | **explicit cut-off** | 0.02 regional; 0.4 unconfined structures | not stated | database min/mean/max |
| 7 | **Myshakin et al.**, IJGGC 117, 103720 **[secondary]** | 2022 | Saline formations, lithology-specific | refines `E_V`, `E_d` of #1 | unchanged (gross) | unchanged (inside E) | `E_V`, `E_d` re-derived from new rel-perm data | unchanged (total) | stochastic, by lithology + depositional environment |

**DOIs and URLs**

1. CO2-SCREEN User's Manual, DOE-NETL, 2020 --
   https://netl.doe.gov/projects/files/CO2StorageprospeCtiveResourceEstimationExcelaNalysisCO2SCREENUsersManual_050820.pdf
2. CSLF-T-2008-04, Bachu (2008) --
   https://hgeo.energy.gov/archives/cslf/sites/default/files/documents/PhaseIIIReportStorageCapacityEstimationTaskForce0408.pdf
3. CO2StoP Final Report, GEUS R 2014/56 --
   https://data.geus.dk/pure-pdf/30624_GEUS-R_2014_56_opt.pdf
4. Donda et al. (2011), IJGGC 5(2), 327-335 -- doi:10.1016/j.ijggc.2010.08.009 --
   https://ricerca.ogs.it/retrieve/a6b4ddf0-7272-4bcf-add0-dcd5f2d3416f/Donda%20et%20al.pdf
5. Wojcicki (2025), Front. Earth Sci. -- doi:10.3389/feart.2025.1679609
6. GEUS/CATF (2021), GEUS report 2021-34 --
   https://cdn.catf.us/wp-content/uploads/2021/10/20183953/EU-CO2-storage-summary_GEUS-report-2021-34_Oct2021.pdf
7. Myshakin et al. (2022) -- doi:10.1016/j.ijggc.2022.103720

---

## 3. Equation-by-equation comparison

All five formulations share the skeleton `mass = pore volume x efficiency x
density`. They differ **only in where the geometric reductions live**.

**#1 DOE-NETL (CO2-SCREEN, Goodman et al.)**

```
G_CO2    = A_t * h_g * phi_tot * rho_CO2 * E_saline
E_saline = E_A * E_h * E_phi * E_V * E_d
```

Glossary, verbatim:

| Symbol | Definition |
| --- | --- |
| `h_g` | "Average **gross** thickness of formation being assessed for CO2 storage" |
| `phi_tot` | "Average **total porosity** of formation being assessed for CO2 storage" |
| `E_A` | "Net-to-Total Area: fraction of formation area available for CO2 storage" |
| `E_h` | "Net-to-Gross Thickness: fraction of formation thickness available for CO2 storage" |
| `E_phi` | "Effective-to-total porosity: fraction of formation porosity available for CO2 storage" |
| `E_V` | "Volumetric Displacement: combined fraction of immediate volume surrounding an injection well that can be contacted by CO2 and the fraction of **net** thickness contacted by CO2 as a consequence of the density difference" |
| `E_d` | "Microscopic Displacement: the fraction of pore space unavailable due to immobile in-situ fluids" |
| `E_saline` | "CO2 storage efficiency factor that reflects a fraction of the **total pore volume** that is filled by CO2" |

This is the cleanest formulation found: **every reduction is named, and each
appears exactly once.** The inputs are deliberately raw (gross, total) so the
five efficiency terms carry all the discounting.

**#2 CSLF-T-2008-04 (the source of the 1-4% number)**

```
M_CO2 = A * h * phi * rho_CO2 * E
```

with E produced by Monte Carlo over seven components, verbatim:

| Component | Range | Maps to |
| --- | --- | --- |
| "Fraction of the saline aquifer that is suitable for CO2 storage" | 0.2-0.8 | `E_A` |
| "Fraction of the geological unit that has the porosity and permeability required for CO2 injection" | **0.25-0.75** | **`E_h`** |
| "Fraction of interconnected porosity" | 0.6-0.95 | `E_phi` |
| "Areal displacement efficiency" | 0.5-0.8 | part of `E_V` |
| "Vertical displacement efficiency" | 0.6-0.9 | part of `E_V` |
| "Fraction of net aquifer thickness contacted by CO2 as a result of CO2 buoyancy" | 0.2-0.6 | part of `E_V` |
| "Pore-scale displacement efficiency" | 0.5-0.8 | `E_d` |

The 2008 seven-term list and the 2020 five-term product are **the same
decomposition**, regrouped: the three displacement terms were later merged into
`E_V`. This is a genuine equivalence, and it is the strongest single piece of
evidence in this review, because it means the 1-4% range and the CO2-SCREEN
`E_saline` are the same object.

**#3 CO2StoP / EU GeoCapacity**

```
M_CO2b = A * h * NG * phi * rho_CO2r * S_eff
```

Verbatim definitions: `h` = "average height of regional aquifer";
`NG` = "average net to gross ratio of regional aquifer"; and critically,
*"In the above expression, the product `A h NG phi` is the total **connected**
pore volume."*

`S_eff` = 2%, justified as: *"For bulk volumes of regional aquifers it is
suggested to use a storage efficiency factor of 2% based on work by the US DOE.
Frailey (2007) used Monte Carlo simulations to find a P50 of storage
efficiencies between 1.8 and 2.2% of the **bulk volume** of a regional aquifer
(with low and high values of **1% and 4%**, respectively)."*

CO2StoP is explicit that it is departing from Bachu:

> *"Bachu et al. (2007) include the net to gross ratio (NG) in both the
> theoretical and the effective capacity estimate, which is meaningful when
> assessing individual traps. The net to gross ratio is, however, also a site
> specific parameter ... It may therefore not be meaningful to establish an
> average value for a regional aquifer based on few observations. If limited
> information is available instead suggest that a default value of **0.25** is
> suggested."*

Two observations follow, and they matter.

First, **CO2StoP's default NG of 0.25 is exactly the low end of CSLF's
net-to-gross component (0.25-0.75)**. The same quantity is being estimated; it
has simply been moved outside the efficiency factor.

Second, **CO2StoP applies a "fraction of bulk volume" number to a connected pore
volume.** Frailey's 1-4% is quoted as being *of the bulk volume*, while the
equation multiplies `A h NG phi`, which CO2StoP itself calls the connected pore
volume. Those differ by `NG * phi` -- roughly a factor of 20. CO2StoP does not
reconcile this, and closes the section by calling its own output *"only
indicative"*.

**#4 Donda et al. (2011)** folds NG into `h` and keeps the DOE 1-4%:

> *"h is the effective thickness, i.e. average thickness of aquifer x average
> net to gross ratio (m)"*

while describing `S_eff` as accounting for *"net-to-effective porosity, areal
and vertical displacement efficiency, and gravity effects"* -- a list that
**omits net-to-gross thickness**. The authors appear not to have known that the
DOE factor contains it.

**#5 Wojcicki (2025)** uses the CO2StoP form with NG explicit, `S_eff` = 2% for
regional aquifers and 3-40% for structural traps, and reports simulation-derived
values of 13 +/- 8% for onshore structures and 2 +/- 0.4% for a regional
aquifer. It is the most recent peer-reviewed application located and it confirms
that the European structure is current practice, not a legacy of 2014.

### Which formulations are genuinely equivalent?

| Pair | Equivalent? | Why |
| --- | --- | --- |
| #1 DOE 2020 and #2 CSLF 2008 | **Yes** | Same seven reductions, regrouped into five terms |
| #1 DOE and #3 CO2StoP | **No** | CO2StoP moves `E_h` out of `E` but keeps `E`'s numeric value |
| #3 CO2StoP and #5 Wojcicki | **Yes** | Same equation, same 2% |
| #3 CO2StoP and #4 Donda | **Structurally yes** | Both apply NG then an efficiency factor; Donda folds NG into `h` |
| #4 Donda and #2 CSLF | **No** | Donda applies NG explicitly *and* CSLF's `E`, which already contains it |
| **Our implementation and #1 DOE** | **No** | We supply net thickness and apply the full `E` |
| **Our implementation and #3/#4/#5** | **Yes** | Same structure and same numeric range |

---

## 4. NTG double-counting analysis

The reduction from gross to net rock appears **exactly once** in #1 and #2, and
**twice** in #4 and in our implementation. #3 and #5 move it out of `E` but
retain `E`'s value, which is the same defect expressed differently.

Magnitude, using CSLF's own range for the term:

| `E_h` | Understatement if applied twice |
| --- | --- |
| 0.75 (high) | **1.33x** |
| 0.50 (mid) | 2.00x |
| 0.25 (low, = CO2StoP default) | **4.00x** |

This confirms the Phase 9 bound of **1.33x-4x** and supersedes the Phase 3
estimate of 1.4x-10x.

**The DOE names both the failure and the fix.** The phrase used is *"to avoid
double discounting"*, and the prescribed action is to set the affected
efficiency term to 1 for both P10 and P90. The example given is net area rather
than net thickness, but the terms are structurally identical members of the same
product, so the instruction transfers directly.

**What this analysis does not establish.** It does not show that our capacity
numbers are wrong by 1.33x-4x in an absolute sense, because the *other* four
efficiency terms may be mis-specified for Piemonte in the opposite direction,
and because `E_V` explicitly references *net* thickness in its own definition,
which makes its interaction with a net-thickness input non-obvious. That
interaction is unresolved in every source read here.

---

## 5. Porosity / E double-counting analysis

**No double-count exists on the porosity axis. This resolves cleanly.**

| Question | Answer | Evidence |
| --- | --- | --- |
| What does DOE expect as input? | **Total** porosity | `phi_tot`: "Average total porosity of formation being assessed" |
| Where is the connected fraction? | **Inside `E`** | `E_phi`: "Effective-to-total porosity" |
| What is the adopted range? | **Total** porosity | Donda: sonic-log derived (Schlumberger 2000); sonic transforms return total porosity |

Because the adopted 10-35% is total porosity and `E` supplies the
effective-to-total reduction, the pairing is correct and Phase 9's resolution of
Finding 3.2 stands.

**One inconsistency is worth recording.** Wojcicki (2025) describes the same
`phi` as *"effective porosity"* while using `S_eff` inherited from the same DOE
work. If that description is literal rather than loose, that paper
double-discounts porosity as well as thickness. We could not resolve which from
the text available, and nothing in this report depends on it.

---

## 6. Static vs effective vs practical vs dynamic capacity

The four-level taxonomy originates with the CSLF techno-economic resource
pyramid and is used consistently across the sources read.

| Level | Definition | Typical formulation | Our tool |
| --- | --- | --- | --- |
| **Theoretical / static** | Whole pore volume, minus irreducible water. Physically bounded, economically meaningless. CSLF: *"the maximum amount of CO2 that can be stored in the pore space minus the irreducible water saturation"* | `A h phi rho` | not produced |
| **Effective** | Theoretical reduced by geological and engineering cut-offs. CO2StoP: *"the reservoir capacity evaluated considering technical cutoff limits and technically viable estimate"* | `x E` or `x C_c` | **this is what we compute** |
| **Practical / matched** | Effective reduced by economic, legal, regulatory and source-sink matching constraints | site studies | not produced |
| **Dynamic / injection-constrained** | What can actually be injected under pressure, rate and plume constraints over a project life | reservoir simulation, or CO2StoP "Method 2" (connected pore volume + allowable pressure increase) | **partially, and separately** -- the Theis module |

Two consequences for this project.

First, **our headline number is an effective capacity**, and the API's
`INTERPRETATION` block is accurate in declining to call it certified, proven or
site-specific.

Second, **the static and dynamic estimates are not connected.** CO2StoP's
Method 2 derives capacity *from* the allowable pressure increase, unifying the
two. Our Theis module computes a rate ceiling that never constrains the
volumetric capacity. Audit Finding 12.1 (closed trap vs infinite aquifer) is the
same disconnect seen from the other side.

---

## 7. Implications for our current implementation

1. **Finding 3.1 is confirmed by the authority that published the number we
   use, and that authority prescribes a remedy.** This is stronger evidence than
   Phase 9 had.
2. **We are not uniquely wrong.** Our structure matches CO2StoP, Donda and
   Wojcicki 2025 -- the mainstream European practice. Any change moves us away
   from the European convention and toward the North American one.
3. **The bound narrows to 1.33x-4x** and is now sourced twice: from CSLF's
   component range and from CO2StoP's default NG of 0.25, which agree.
4. **Porosity needs no change.** Total porosity in, `E_phi` inside `E`. Correct
   as built.
5. **The API contract is the thing that would change.** `USER_INPUT_SPEC`
   currently demands *"Net reservoir thickness inside the closure -- NOT the
   gross chronostratigraphic interval"*. Candidates B and C would invert that
   demand, which is a breaking change to a public contract and to the frontend.
6. **`E_V` references net thickness inside its own definition**, so "set `E_h`
   to 1" may not be the complete remedy. No source read here resolves how `E_V`
   should be interpreted when the input is already net.

---

## 8. Candidate formulations

Quantified on the four audited wells, at A = 8e7 m2, net h = 35 m, gross h =
the ingested gross stratigraphic thickness, phi = 0.10-0.35, N = 20 000,
seed 42.

### Candidate A -- status quo

```
M = A * h_net * phi * rho * E,     E = 1-4%
```

**Assumes:** that `E`'s net-to-gross component is either absent or intended to
be applied on top of a net thickness.
**Consequence:** understates capacity by 1.33x-4x relative to the DOE
definition. **Matches** CO2StoP, Donda and Wojcicki 2025.
**Cost to adopt:** zero. It is what ships.

### Candidate B -- DOE-conformant inputs

```
M = A * h_gross * phi_tot * rho * E_saline,     E_saline = E_A E_h E_phi E_V E_d
```

**Assumes:** the caller can supply a gross thickness *of the storage formation*.
**Consequence, measured:**

| Well | P50 vs baseline |
| --- | --- |
| SALUZZO\|1 | **x31.6** |
| DESANA\|1 | x31.4 |
| TRECATE\|9\|ST | x17.7 |
| MALOSSA\|15 | x10.1 |

**These numbers are not defensible and the experiment shows why.** The only
"gross" thickness this project holds is the **gross chronostratigraphic
interval** (355-1105 m), which is the whole logged section, not the gross
thickness of a storage formation. Substituting it reproduces precisely the
10x-32x error the audit's `ThicknessKind` separation exists to prevent.

Candidate B is only implementable if a caller supplies a *formation* gross
thickness, which is a new required input the project does not have and cannot
derive. **It is the most correct formulation and the least available.**

### Candidate B-prime -- DOE remedy, net input retained

```
M = A * h_net * phi * rho * E',     E' = E / E_h
```

With CSLF's `E_h` range of 0.25-0.75, `E' = 1.33% to 16.0%`.

**Assumes:** that dividing the aggregate range by the net-to-gross range is a
valid way to remove one factor from a Monte Carlo product. This is an
approximation -- the correct operation is to re-run CSLF's Monte Carlo with
`E_h` fixed at 1, which would give a narrower range than a naive division of the
endpoints.
**Consequence:** originally reported here as x3.41. **That figure is WITHDRAWN.**
It was computed by dividing distribution endpoints, which pairs extremes that
almost never co-occur. The control experiment of 2026-09-21 re-ran the published
Monte Carlo with `E_h` fixed at 1 and measured **x1.93 on capacity** (x2.095 on
the efficiency median). See `docs/bprime-control-experiment.md`.
**Cost to adopt:** one range constant. The API contract is unchanged; net
thickness stays the required input.
**Risk:** the widened efficiency range (1.33-16%) is no longer the published
CSLF range, so the citation would need rewording -- it becomes a derived
quantity, not an adopted one. Under the project's own provenance rules that is a
demotion from `generic` to a computed value, and the audit's Finding 9.8 already
flags asymmetry in how such values are recorded.

### Candidate C -- CO2StoP / EU GeoCapacity

```
M = A * h_gross * NG * phi * rho * S_eff,     NG = 0.25 default, S_eff = 2%
```

**Assumes:** the European regional-bulk framing, with an explicit NG the caller
or scenario supplies.
**Consequence, measured:**

| Well | P50 vs baseline |
| --- | --- |
| SALUZZO\|1 | **x6.9** |
| DESANA\|1 | x6.9 |
| TRECATE\|9\|ST | x3.9 |
| MALOSSA\|15 | x2.2 |

**Same defect as Candidate B:** it needs a gross thickness the project does not
have, and the figures above use the chronostratigraphic interval as a stand-in.
It also replaces a range with a single 2% point value, which would **collapse
one of the only three priors that currently vary** (Phase 7 Finding 7.1) and
narrow the reported band for the wrong reason.

Candidate C is the most defensible *if* the project were assessing regional
aquifers. It is assessing structural closures, and CO2StoP says explicitly that
its regional efficiency *"is trap/site specific and not applicable to the bulk
volume of a regional aquifer"* in the other direction -- the two scales should
not be mixed. Audit Finding 9.3 already records that mismatch.

### Summary

| | Structure | Needs new input | P50 change | DOE-conformant | EU-conformant |
| --- | --- | --- | --- | --- | --- |
| **A** status quo | net h, full E | no | x1.00 | no | **yes** |
| **B** DOE inputs | gross h, full E | **formation gross h** | x10-32 | **yes** | no |
| **B'** DOE remedy | net h, E/E_h | no | **x1.93** (corrected) | **yes** | no |
| **C** CO2StoP | gross h, NG, 2% | **formation gross h + NG** | x2-7 | no | **yes** |

---

## 9. Recommended next validation experiment

**Not yet run beyond the preview above.** The preview used the
chronostratigraphic interval as a proxy for formation gross thickness, which is
exactly the substitution the project forbids; its B and C columns should be read
as an illustration of why, not as results.

A defensible experiment needs:

1. **Four wells**: SALUZZO|1, DESANA|1, MALOSSA|15, TRECATE|9|ST -- the Phase 11
   set, so the independent implementation can be reused unchanged.
2. **A formation gross thickness per well, or an explicit refusal.** Without it,
   B and C cannot be evaluated and the experiment reduces to A vs B'. That is
   still worth running, because B' is well-independent and needs no new data.
3. **Re-derive `E'` properly** rather than by dividing endpoints: re-run the
   CSLF seven-term Monte Carlo with `E_h` fixed at 1 and read off P15 and P85,
   reproducing the published 1-4% first as a control. If that control does not
   reproduce, the decomposition is not the one that produced the number and
   Candidate B' loses its basis.
4. **Report all four candidates against the Phase 10 baseline** with P10/P50/P90
   and the ratio, per well, using seed 42 and N = 20 000 so the numbers are
   directly comparable with the audit.
5. **Cross-check against Donda's published capacities.** Donda Table 2 gives
   area, effective thickness, porosity and resulting Mt for 14 Italian
   reservoirs. Running each candidate against those inputs and comparing to the
   published 2 950 Mt / 11 800 Mt totals is the only external validation
   available, and it directly tests whether a candidate reproduces a published
   Italian result.

Step 5 is the most valuable and has not been attempted.

---

## 10. What evidence is still missing before changing code

| # | Missing | Why it blocks a decision | Obtainable? |
| --- | --- | --- | --- |
| 1 | **A net-to-gross estimate for Piemonte** | Sets the size of the correction. CSLF's 0.25-0.75 is North American; CO2StoP's 0.25 is a default for "limited information" | **Investigated 2026-09-21: NOT AVAILABLE.** See `docs/piemonte-ntg-evidence.md` -- no Piemonte NTG exists in the literature, and our own data cannot yield one without raster log digitisation |
| 2 | **Formation gross thickness per well** | Candidates B and C are unevaluable without it | Not from the structured sources; would need log interpretation |
| 3 | **Goodman et al. (2011, 2016) themselves** | The CO2-SCREEN manual is an implementation; the methodology papers define `E_h` ranges by lithology | Yes -- doi:10.1016/j.ijggc.2011.03.010 and the 2016 refinement |
| 4 | **The IEA GHG (2009) efficiency tables** | CO2-SCREEN auto-populates `E_h` from them by lithology and depositional environment; a clastic-specific range would replace CSLF's generic 0.25-0.75 | Likely, via the IEAGHG report series |
| 5 | **How `E_V` behaves with a net-thickness input** | `E_V` contains "the fraction of **net** thickness contacted by CO2"; setting `E_h` to 1 may not be the whole remedy | Unresolved in every source read; may need Myshakin et al. (2022) in full |
| 6 | **Frailey (2007)** | CO2StoP attributes the 1-4% range to it; whether it is "of bulk volume" or "of pore volume" is contradictory across sources | Probably, as an SPE/conference paper |
| 7 | **Whether Wojcicki's "effective porosity" is literal** | Determines whether the leading current European application double-discounts porosity too | From the paper's methods section in full |

**Items 1 and 2 are the blockers.** Items 3-7 would sharpen the numbers but do
not change the structure of the decision.

---

## Method and limitations of this review

Six of the seven sources were downloaded and their text extracted locally;
quotations are verbatim from those extractions. The seventh (Myshakin et al.
2022) is behind a paywall and is cited only for the `E_V`/`E_d` refinement,
which no conclusion depends on. Two DOE hosts (`osti.gov`) refused connections
during this review, so the primary Goodman et al. papers were not obtained;
their methodology is represented here through the CO2-SCREEN manual, which
implements them and states so.

No search of Italian-language regional literature was performed. If a Piemonte
or Po Basin net-to-gross study exists in an Italian geological survey
publication, it would answer blocker 1 directly and was not looked for here.

**Separation of source from interpretation:** every table row and block quote
above is sourced. The mapping of CSLF's seven components onto CO2-SCREEN's five
terms (section 3), the equivalence table (section 3), and all four candidate
formulations (section 8) are **this review's interpretation**, not statements
made by any source.
