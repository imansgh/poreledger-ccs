# Finding 3.1 — External NTG Evidence Hunt

**Research evidence package, 2026-09-24.**

- No NTG value is chosen.
- Nothing is inserted into the model, priors or Monte Carlo.
- No code, `combined_factor`, P_atm or audit numbers are changed.
- Finding 3.1 is **not** marked resolved.
- Uncommitted draft.

**Values are reported exactly as each source defines them.**

Companion to `docs/piemonte-ntg-evidence.md`, `docs/finding-3.1-ntg-evidence-elicit.md`,
`docs/finding-3.1-primary-evidence.md` and the SALUZZO 1 audits.

---

## 0. Scope note — which wells are "audited"

The task brief lists the audited wells as MORETTA|1, NOVI LIGURE|2,
SOMMARIVA DEL BOSCO|1, SALUZZO|1 and MALOSSA|15.

The repository's audit uses a different list:

- `docs/scientific-validation-audit.md`, Phase 10, names the screenable wells as
  **SALUZZO|1, TRECATE|9|ST, DESANA|1, ASTI|1, MALOSSA|15**.
- `docs/piemonte-ntg-evidence.md` §6.2 and Finding 12.4 use the same wells.
- MORETTA|1, NOVI LIGURE|2 and SOMMARIVA DEL BOSCO|1 entered the Finding 3.1 work
  as the three corpus wells present in Livani et al. (2023). They are **not**
  audited wells in the repository.

**This discrepancy is recorded, not resolved.** Relevance below is assessed against
**both** lists: eight wells in total.

**Screened (TD) interval of each well**, from the project workbook
`Lito-Stratigrafie` and prior audits, read-only:

| Well | In brief | In repo audit | TD (m) | Lithology interval containing TD (workbook) | Operator unit where verified |
| --- | --- | --- | --- | --- | --- |
| SALUZZO\|1 | ✓ | ✓ | 1527.5 | 422.8-1527.5 `CIOTTOLI E SABBIE`, MIOCENE | AGIP 1991: Miocene?/non definita to ~598 m RT, then **OLIGOCENE / MOLARE** (conglomerates) |
| MALOSSA\|15 | ✓ | ✓ | 5491 | 5136-5491 `MAIOLICA, ROSSO AMMONITICO` (CALCARI), GIURASSICO | — |
| DESANA\|1 | — | ✓ | 3224.9 | 2126.4-3224.9 `MARNE ARENACEE CON CONGLOMERATI E GESSI`, MIOCENE | — |
| ASTI\|1 | — | ✓ | 1247 | 370-1250 `MARNE, SABBIE E GESSI`, MIOCENE | — |
| TRECATE\|9\|ST | — | ✓ | 6087 | 5468-6087 `CALCARI, MARNE E DOLOMIE`, ALBIANO | — |
| MORETTA\|1 | ✓ | — | 3091 | 2930-3091 `BASAMENTO METAMORFICO` | — |
| NOVI LIGURE\|2 | ✓ | — | 1700 | 760.2-1695.2 `ARGILLE CON LIVELLI DI SABBIE E CONGLOMERATI`, MIOCENE MEDIO-SUP (TD 1700 lies just below the last listed interval) | — |
| SOMMARIVA DEL BOSCO\|1 | ✓ | — | 3809 | 1800-3809 `SERRAVALLE`, TORTONIANO | AGIP 1992: **CASSINASCO** below ~3439 m RT (see `finding-3.1-primary-evidence.md`) |

---

## 1. Executive finding

> ### REGIONAL NTG CONTEXT FOUND, NOT SUFFICIENT FOR AUDIT

- The only Tier-1/2 source found that publishes **reservoir-level NTG values from
  a field model** in the Po Basin is **Teatini et al. (2011)**.
- It reports *"Net/gross pay"* for five pools of a Pliocene turbidite gas field,
  "Lombardia" (a pseudonym), operated by Stogit-Eni.
- The values trace to an **unpublished AGIP static-model report** that is not
  publicly accessible.
- The field's reservoir is **Pliocene turbidite sand**. None of the eight wells is
  screened in such a unit:
  - their TD intervals are Oligocene / Miocene conglomerates and marls, Miocene
    turbidites, Mesozoic carbonates, or metamorphic basement;
  - so **no source is a direct or strong analogue for any screened interval.**
- No Piemonte / western-Po source with a published NTG was found. This is
  consistent with the ten Elicit searches in the companion document.

---

## 2. Evidence table

| Source | Location | Formation / reservoir | NTG | NTG basis | Net/gross definition | Data basis | Geological relevance to audited wells | Applicability | Exact citation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Teatini et al. (2011)** | "Lombardia" gas field (pseudonym; Stogit-Eni UGS), northern margin of the pre-Alpine monocline, Lombardy | *"sandy sediments corresponding to the lateral end of Pliocene turbidites onlapping the partly folded Messinian basin"*; stratigraphic traps pinching out against Santerno Fm clays; pools A, B, C1, C2, C3; top 1080-1180 m bsl | **"Net/gross pay png (%)": A 54, B 67, C1 83, C2 89, C3 100** | **Modelled**: pool averages from an operator static model | *"net/gross pay"* — **pay**, not reservoir. Net and gross not otherwise defined; **no cutoffs stated** | *"Data are made available by Stogit-Eni S.p.A. [Repossi, 1998]"*; Repossi (1998) *Campo di "Lombardia" — Modello Statico*, Rep. AGIP/GIAC17/98 (internal) | **None of the eight TD intervals is a Pliocene turbidite sand** (§0). Closest in lithology type: SOMMARIVA's Miocene deep-marine turbidites (Cassinasco per AGIP 1992), at a different age, sub-basin and depth (3.4-3.8 km vs ~1.1 km) | **REGIONAL CONTEXT ONLY.** WEAK ANALOGUE at most for SOMMARIVA DEL BOSCO\|1; NOT APPLICABLE to the other seven | Teatini, P., et al. (2011), *J. Geophys. Res.* 116, F02002, doi:10.1029/2010JF001793 — §2.2 [15]-[16] (p. 3-4); **Table 1 (p. 5)**; §3.1 [23] (p. 7) |
| Lombardi et al. (2025) — Cornegliano | Cornegliano Laudense UGS (IGS), central Po Plain (Lodi) | *"sands and shaly sands of the 'Sabbie di Caviaga' formation, of Lower Pliocene age"*, 1350-1450 m; zones B, C1-C3 | **None reported** | — | — | Porosity *"15% and 29%"*; permeability *"~0.01 … ~1700 mD"*; Table 1 qualitative zone descriptions | As Teatini (Pliocene sands); not matching any TD interval | **REGIONAL CONTEXT ONLY** (no NTG) | *Geosciences* 15(9):329, doi:10.3390/geosciences15090329 — §2.2 and Table 1 |
| Colucci et al. (2016) | Lombardia Region, study area ~1500 km² | *"caprock-reservoir system … in a clay and conglomerate formation"*. Shogenova et al. (2022) name the Malossa target as the **Messinian Sergnano Gravel**, 83 m thick at 1240 m | **Not in the accessible text** (abstract / highlights) | — | — | 3D static + fluid-dynamic model; full text **paywalled, not read** | Conglomerate reservoir, the closest *lithology type* to SALUZZO's TD interval (Oligocene Molare conglomerates). Different age, formation and basin. MALOSSA\|15's TD is Jurassic carbonate, not Sergnano. | **UNVERIFIED — potential WEAK ANALOGUE** (lithology only), pending full text | *Int. J. Greenh. Gas Control* (2016), doi:10.1016/j.ijggc.2016.10.013 (abstract read via ScienceDirect) |
| Shogenova et al. (2022) | Malossa structure, Lombardy | Messinian Sergnano Gravel conglomerate, 83 m, 1240 m | **Not in abstract**; full text unavailable | Static model (PETREL, 18 wells, 34 km²) | — | Abstract only | Not the MALOSSA\|15 TD interval (Jurassic) | **NOT APPLICABLE** to MALOSSA\|15; lithology-type context for SALUZZO\|1 | Semantic Scholar ss-254293759; see `finding-3.1-ntg-evidence-elicit.md` |
| Lindquist (1999), USGS | Malossa field | Norian Dolomia Principale / Liassic Zandobbio carbonates | **No NTG.** *"Malossa average net reservoir thickness is 300 m (maximum 580 m)"* | Secondary citation of Mattavelli & Margarucci (1992) | Net thickness only; no gross | Field-level | MALOSSA\|15 TD is Jurassic Maiolica / Rosso Ammonitico, not the Norian-Liassic pay | **NOT APPLICABLE** (no NTG; different interval) | USGS OFR 99-50-M, doi:10.3133/OFR9950M — Mesozoic reservoir paragraph |
| Lindquist (1999), USGS | Barbara field, offshore central Adriatic | Quaternary sands, biogenic gas | *"net-to-gross ratios ranging from 27% in the silty sands to 95% in the coarser sands"* | Secondary (Ianniello et al. 1992) | Not defined | Field-level | Different sector, age and play | **NOT APPLICABLE** | as above — Tertiary/Quaternary reservoir paragraph |
| Donda et al. (2011) | Bradanica trough, Basilicata | Late Pliocene basin-floor sand lobes | Implied ~650/800 from *"more than 800 m … exceeding 650 m"* (two lower bounds; not stated as NTG) | Text statement | Effective thickness via GR/SP clay-interbed exclusion | Several boreholes | Wrong basin (Southern Apennine foredeep) | **NOT APPLICABLE** | Donda et al. (2011); see `piemonte-ntg-evidence.md` §2.1 |
| CO2StoP (Poulsen et al. 2014) | Europe | Regional aquifers | **0.25 default** "if limited information is available" | **Assumed / generic** | "average net to gross ratio of regional aquifer" | Default | Generic | **NOT APPLICABLE** (generic background) | CO2StoP Final Report; `piemonte-ntg-evidence.md` §2.2 |
| CSLF-T-2008-04 | North America | Various | 0.25-0.75 | **Generic** Monte-Carlo input | *"Fraction of the geological unit that has the porosity and permeability required for CO2 injection"* | — | Generic | **NOT APPLICABLE** (generic background) | CSLF (2008); `piemonte-ntg-evidence.md` §2.3 |

**Checked, no NTG found:**

- Livani et al. (2023): digitised logs only; no NTG.
- AGIP 1987 Inventory well sheets.
- AGIP 1996 AREA ENI reports.
- Irace et al. (2009, Regione Piemonte): *"spessore utile"* of fresh-water
  aquifers above the fresh/brackish interface, i.e. shallow hydrogeology, not an
  NTG of the screened intervals.
- Operator composites for SALUZZO 1 and SOMMARIVA DEL BOSCO 1.

All of these are documented in the companion files.

---

## 3. Best candidate(s)

### 3.1 Teatini et al. (2011), Table 1 — the only verified field-model NTG in the Po Basin

**What it demonstrates:**

- A Stogit-Eni gas-storage field at the northern margin of the pre-Alpine
  monocline has five pools of Pliocene turbidite sand at ~1080-1215 m bsl.
- An operator static model assigned them *"net/gross pay"* of 54, 67, 83, 89 and
  100 %.
- The paper uses that quantity to compute pore volume: *"the integral of the
  function Sw·png, with png the net/gross pay"* (§3.1, p. 7).
- The same table gives porosity 20-29 %, hydraulic conductivity 380-400 mD,
  Sw 12-27 %, and pool thicknesses 3-50 m.
- The values are verified from the paper itself (open copy on the co-author
  company site).

**What it does not demonstrate:**

- The definition of "net" and "gross".
- The cutoffs (Vclay, porosity, permeability, Sw).
- The number of wells, logs or cores behind the model.
- Whether the values are pool averages over the pay zone or over a stratigraphic
  gross interval.

"Net/gross **pay**" is a hydrocarbon-pay concept inside a gas accumulation. It is
**not** equivalent to the net-*reservoir* (porosity/permeability) concept of a
saline aquifer used for CO2 storage (`docs/net-to-gross-semantics.md`). The field
name is a pseudonym, and **no attempt was made to identify it.**

**Transferability:**

- **A — Stratigraphic.** Pliocene turbidites onlapping the Messinian. None of the
  eight TD intervals is Pliocene.
- **B — Depositional.** Turbiditic. Only SOMMARIVA DEL BOSCO|1 (Cassinasco, deep
  marine turbidites, per AGIP 1992) shares the process. Its age (Serravallian?),
  depth (3.4-3.8 km vs 1.1 km), sub-basin (Tertiary Piedmont vs pre-Alpine
  Lombardy) and petrophysics all differ: sonic 61-70 µs/ft there, against 20-29 %
  porosity at Lombardia.
- **C — Lithological.** Sand vs SALUZZO's matrix-supported conglomerate, the
  Miocene marls and gypsum of ASTI and DESANA, and carbonates.
- **D — Petrophysical.** Not comparable to any screened interval; no porosity data
  exist for most of them.
- **E — Definition.** Pay vs reservoir, and cutoffs undocumented.

**Conclusion:** regional context for Po Basin **Pliocene** clastics; at most a weak
analogue for SOMMARIVA DEL BOSCO|1.

### 3.2 Colucci et al. (2016) — potentially the most relevant, unverified

**Why it matters:**

- It is the only located study that built a **static model of a conglomerate
  saline aquifer** for **CO2 storage** in northern Italy.
- That is the same purpose and a similar lithology type to SALUZZO|1's TD
  interval, which AGIP 1991 describes as gravels and conglomerates in a
  sandy-clayey matrix, Molare Formation.

**What it doesn't give:**

- The accessible abstract does **not** mention NTG.
- The full text is paywalled and was **not read**, so whether it reports an NTG,
  and how it defines one, is **UNKNOWN**.

**Limits on transfer even if an NTG is found:**

- Different formation and age: Messinian Sergnano Gravel vs Oligocene Molare.
- Different basin setting: Lombardy pre-Alpine vs Tertiary Piedmont Basin.
- So it would be a **weak analogue at best** and **not** a well-specific value.

---

## 4. Evidence chain

**Teatini et al. (2011):**

```
Stogit-Eni well / log / core data (not described; not public)
  → AGIP static model: Repossi (1998) "Campo di 'Lombardia' — Modello Statico",
    Rep. AGIP/GIAC17/98 (internal; not public)
  → pool-average "net/gross pay" (definition and cutoffs not published)
  → Teatini et al. (2011), JGR 116, F02002, Table 1 (published)
```

- The link from original data to the static model is **unverifiable publicly**.
- The published number is **modelled**, not measured.

**Colucci et al. (2016) / Shogenova et al. (2022):**

```
18 Malossa-area wells → PETREL static model → (NTG, if any: not verified) → paper
```

**Lindquist (1999):** field summaries citing Mattavelli & Margarucci (1992) and
Ianniello et al. (1992). These are secondary; the primaries were not read.

---

## 5. Gaps

What is still missing for audit-grade evidence:

1. **Formation equivalence.** No source was found for any unit that matches the
   screened interval of any of the eight wells:
   - Molare / Miocene conglomerates (SALUZZO)
   - Miocene marls-sands-gypsum (ASTI, DESANA, NOVI LIGURE 2)
   - Cassinasco / Serravalle turbidites (SOMMARIVA)
   - Jurassic / Albian carbonates (MALOSSA|15, TRECATE)
   - basement (MORETTA)
2. **Definition.** The only published Po-Basin NTG is *net/gross pay* in a gas
   field, with undocumented cutoffs. The project needs net *reservoir* (or a
   declared `net_criterion`) for saline aquifers.
3. **Primary access.** The underlying operator model (Repossi 1998, AGIP/GIAC17/98)
   is internal. The paper cannot be audited back to data.
4. **Unread candidate.** Colucci et al. (2016) full text.
5. **The audited-well list itself** (§0) must be settled before any relevance
   judgement becomes final.

---

## 6. Recommended next research action

One step only:

> **Obtain and read the full text of Colucci et al. (2016), *Int. J. Greenh. Gas
> Control*, doi:10.1016/j.ijggc.2016.10.013.** Record whether its static model
> reports an NTG (or net/gross) for the conglomerate reservoir, with the exact
> definition, cutoffs, wells used and table / page. Then classify it against
> SALUZZO|1 using the A-E criteria above.

This needs library or publisher access, or a copy from the authors. No NTG is to be
adopted from it.

---

## Integrity

- No NTG value chosen. No model, prior, Monte Carlo, code, `combined_factor`,
  P_atm or audit-number change.
- Finding 3.1 **remains open**.
- Retrieved material is in the session scratchpad:
  - Teatini et al. (2011) PDF from the co-author company site (1,424,981 B);
  - the Cornegliano article and the Colucci abstract, read in the browser.
- New Elicit collection entries: Colucci (2016), Cornegliano (2025),
  Teatini (2011), OMC-2021-078.

**Sources:**

- [Teatini et al. 2011 — Wiley](https://agupubs.onlinelibrary.wiley.com/doi/abs/10.1029/2010JF001793)
  ([open copy](https://site.tre-altamira.com/wp-content/uploads/2011_Geomechanical_response_to_seasonal_gas_storage_in_depleted_reservoirs_case_study_in_the_Po_River_basin_Italy.pdf))
- [Lombardi et al. 2025 — Cornegliano](https://doi.org/10.3390/geosciences15090329)
- [Colucci et al. 2016 — ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1750583616307393)
- [USGS OFR 99-50-M](https://pubs.usgs.gov/of/1999/ofr-99-0050/OF99-50M/OF99-50M.pdf)
- [OMC-2021-078](https://onepetro.org/OMCONF/proceedings-abstract/OMC21/All-OMC21/OMC-2021-078/473148)
