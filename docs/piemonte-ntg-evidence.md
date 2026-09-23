# Piemonte net-to-gross (NTG) evidence review

**Blocker 1 of Finding 3.1: is there a defensible NTG for the Piemonte dataset?**

Prepared 2026-09-21. Companion to `docs/finding-3.1-literature-review.md`.
**Research phase only. No file under `src/` was modified, no scientific constant
or equation was touched, and no test that encodes scientific behaviour was
changed.**

---

## Decision

> ### NTG evidence INSUFFICIENT.
> ### Proceed to the B-prime control experiment, or to data acquisition.

No source located in this review gives a net-to-gross ratio for any Piemonte
reservoir, for the western Po Plain, or for any well in our corpus. One Italian
gross/net pair exists in the literature, from the wrong basin, expressed as two
lower bounds. Our own data cannot yield an NTG without raster log digitisation,
which is explicitly out of scope for this project.

**A further finding makes the question partly moot for two of the five
screenable wells:** MALOSSA|15 and TRECATE|9|ST bottom in **carbonate**, not
clastics. A clastic NTG would not transfer to them, and neither does the clastic
porosity range the project already adopts. See section 6.

---

## 1. Piemonte / Po Plain NTG sources found

**None.**

| Search line | Result |
| --- | --- |
| Piemonte / western Po Plain NTG, sand fraction, reservoir characterisation | No NTG values located |
| Po Plain basin architecture (Amadori et al. 2019; Ghielmi et al.) | Basin geometry, sequences and turbidite facies; **no NTG** |
| Italian CCS capacity studies | Donda et al. 2011 is the only regional assessment; see below |
| Po Valley deep plays (Malossa, Villafortuna-Trecate) | Field descriptions; **no NTG**; reservoirs are Triassic carbonates |
| ISPRA / Servizio Geologico d'Italia | Geological and hydrogeological mapping; **no reservoir NTG** |
| CO2StoP / EU GeoCapacity database | See section 2 -- Italy contributed **one** storage unit |
| ENOS and comparable EU CCS projects | No Piemonte reservoir NTG located |

**The most consequential negative result:** *Donda et al. (2011) -- "CO2 storage
potential of deep saline aquifers: The case of Italy", the only published
regional Italian CCS assessment and the source of this project's adopted
porosity range -- **does not mention Piemonte or Piedmont once**.* Its 14 sites
are Abruzzi (x4), Lombardia (x2), Marche, Molise (x2), Emilia (x2), Sicilia,
Bradanica and Calabria ionica. The western Po Plain is absent from the
assessment the project relies on.

---

## 2. Italian / European fallback sources

### 2.1 Donda et al. (2011) -- one gross/net pair, from the wrong basin

Donda's `h` is defined as *"the effective thickness, i.e. average thickness of
aquifer x average net to gross ratio (m)"*, and the method is a genuine net-sand
determination:

> *"The effective thickness has been calculated by considering the sum of
> thicknesses of each permeable coarse-grained, sandy-gravelly layer within the
> potential reservoir. The Gamma Ray (GR) and Spontaneous Potential (SP) logs
> provided a measure of the thickness of any clay interbeds."*

That is a defensible **net sand / gross interval** definition. But **Table 2
reports only the effective thickness, never the gross**, so NTG is not
recoverable for 13 of the 14 sites.

**One exception**, in the Bradanica site description:

> *"The reservoir is locally **more than 800 m** thick, with an effective
> thickness **exceeding 650 m**, as recorded by several boreholes drilled in
> the area"*

Implied NTG ~ 650/800 = **0.81**. Four reasons this is not usable as a Piemonte
value:

1. **Both numbers are lower bounds** ("more than", "exceeding"), so the ratio is
   indicative only.
2. **It is a local maximum, not an average.** Table 2 gives Bradanica an
   effective thickness of **480 m**, not 650 m. The text and the table describe
   different things, and the gross figure that pairs with 480 m is not given.
3. **Wrong basin.** Bradanica is the Southern Apennine foredeep (Basilicata),
   not the Po Plain.
4. **Wrong facies.** Late Pliocene basin-floor sandstone lobes are sand-rich by
   nature; a high NTG there says nothing about a Piemonte section.

### 2.2 CO2StoP -- Italy contributed essentially nothing

The CO2StoP data-availability table records, for Italy: **"Yes | Only 1 unit |
Yes | Yes"**. One storage unit for the entire country. The pan-European database
therefore carries no Italian NTG population.

CO2StoP's own guidance is explicit that its value is a fallback, not evidence:

> *"The net to gross ratio is, however, also a site specific parameter depending
> on the local geological variations and is not necessarily neither well known
> or equally distributed throughout a region. It may therefore not be meaningful
> to establish an average value for a regional aquifer based on few
> observations. If limited information is available instead suggest that a
> default value of **0.25** is suggested. This value may be too high in some
> cases, but will in many cases be a conservative value."*

**0.25 is a declared default for the case of missing information.** Adopting it
would not resolve blocker 1; it would rename it.

### 2.3 CSLF-T-2008-04 -- generic, and explicitly North American

The 0.25-0.75 range is the *"Fraction of the geological unit that has the
porosity and permeability required for CO2 injection"* component of the Monte
Carlo that produced the 1-4% efficiency. CSLF states the ranges *"were chosen to
reflect various lithologies and geological depositional systems that occur in
**North America**"*. Per the review brief, this is not Piemonte evidence and is
not treated as such here.

---

## 3. Evidence table

| Source | Formation / unit | Location | Setting | NTG definition | Value | Data basis | Transferable to our dataset? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Donda et al. (2011), Bradanica text | N.D. (Late Pliocene) | Bradanica trough, Basilicata | Turbidite basin-floor sand lobes, ~1000 m | net sand / gross, from GR + SP | **~0.81**, from two lower bounds | Several boreholes | **No** -- wrong basin, wrong facies, bounds not averages |
| Donda et al. (2011), Table 2 | Carassai, Sergnano gravel, Porto Garibaldi, Teramo, Terravecchia, Porto Corsini | 14 Italian sites, **none in Piemonte** | Plio-Pleistocene clastics | effective thickness only | **not recoverable** (no gross reported) | GR + SP + sonic + seismic | **No** -- NTG not published |
| Donda et al. (2011), Lombardia 1 | Sergnano gravel (Messinian) | Central Po Plain, Lombardy | Gravel and sand | effective thickness 75 m | no NTG | boreholes + seismic | **Closest analogue**, but no NTG |
| Donda et al. (2011), Lombardia 2 | Porto Garibaldi (Mid-Late Pliocene) | Central Po Plain, Lombardy | Fine to coarse sand | effective thickness 240 m | no NTG | boreholes + seismic | **Closest analogue**, but no NTG |
| CO2StoP / Poulsen et al. (2014) | n/a | Europe, 26 countries | regional saline aquifers | "average net to gross ratio of regional aquifer" | **0.25 default** | **assumed default** for missing data | **No** -- a default, not a measurement |
| CSLF-T-2008-04 (2008) | n/a | North America | various lithologies | "fraction of the geological unit that has the porosity and permeability required" | 0.25-0.75 | Monte Carlo input ranges | **No** -- generic, non-Italian, excluded by brief |
| Wojcicki (2025) | Cambrian / Jurassic-Cretaceous | Northern Poland | regional aquifers + traps | NG as explicit multiplier | not stated numerically in the text available | national database | **No** -- different basin |

---

## 4. Evidence classification

**Directly applicable evidence: none.**
No source gives an NTG for a Piemonte reservoir, a western Po Plain reservoir,
or any well in our corpus.

**Analogous evidence: two sites, without NTG.**
Donda's **Lombardia 1** (Sergnano gravel, Messinian, gravel and sand, effective
thickness 75 m) and **Lombardia 2** (Porto Garibaldi, Mid-Late Pliocene, fine to
coarse sand, effective thickness 240 m) are central Po Plain, the nearest
published analogues to Piemonte in play type and basin. **Neither reports a
gross thickness**, so neither yields an NTG. They are the right wells in the
right basin with the wrong column published.

The Bradanica pair is the only Italian gross/net statement found, and it fails
transferability on basin, facies and precision.

**Generic / default assumptions: two, both explicitly labelled as such by their
own sources.**
CO2StoP's 0.25 ("if limited information is available") and CSLF's 0.25-0.75
(North American). Neither is Piemonte evidence.

---

## 5. Can a defensible Piemonte NTG range be established?

**No.**

To be defensible a range would need to be tied to a formation, a depth interval,
a log suite and a cutoff. Nothing located in this review supplies more than one
of those for any Piemonte well.

**What would be required**, in ascending order of effort:

| # | Missing input | Why it is needed | Where it might come from |
| --- | --- | --- | --- |
| 1 | **Gross thickness for Donda's Lombardia 1 and 2** | Would convert the two closest analogues into two real Po Plain NTG values | The authors, or the underlying OGS/ViDEPI well reports |
| 2 | **A reservoir interval definition per well** | NTG is meaningless without a gross interval to divide by; we have chronostratigraphic units, not reservoirs | Log interpretation, or a published Piemonte reservoir study |
| 3 | **Digital logs (GR, SP, resistivity) for Piemonte wells** | The direct route, and the one Donda used | See section 6 -- none are held, and none exist for our wells in the national LAS index |
| 4 | **A declared cutoff methodology** | Donda used GR/SP to measure clay interbeds; a different cutoff gives a different NTG for the same rock | Would have to be chosen and documented, i.e. a new project assumption |
| 5 | **Separate treatment for carbonate wells** | A clastic net-sand NTG does not apply to a dolomite/limestone reservoir | See section 6 |

Items 1 and 3 are the only ones that could be answered by acquisition rather
than by assumption. Item 1 is much the cheaper.

**No candidate range is proposed.** Proposing one would mean selecting among
0.25 (a foreign default), 0.25-0.75 (North American) and 0.81 (wrong basin, from
lower bounds), none of which is Piemonte evidence. The brief is explicit that a
missing parameter is preferable to an invented regional value, and this review
agrees.

---

## 6. Can our own data support an independent NTG derivation?

**No.** Four checks, all negative.

### 6.1 GEOTHOPICA workbook -- no logs of any kind

| Sheet | Rows | Contents |
| --- | --- | --- |
| `Anagrafica` | 46 | Well header: name, coordinates, `quota`, depth, operator, outcome, purpose |
| `Lito-Stratigrafie` | 178 | `top`, `bottom`, `litologia`, unit names, relative ages |
| `Temperature` | 452 | depth, temperature, circulation/stop times, method |

**There is no GR, no SP, no resistivity, no density, no neutron, and no
interpreted net interval in any sheet.**

### 6.2 The lithology column cannot yield a net fraction

`litologia` is a qualitative, mixed, unquantified descriptor applied to coarse
intervals. Measured across the audited wells:

| Well | Interval containing TD | Lithology | Interval length |
| --- | --- | --- | --- |
| SALUZZO\|1 | 422.8-1527.5 m | `CIOTTOLI E SABBIE` | **1 104.7 m** |
| DESANA\|1 | 2 126.4-3 224.9 m | `MARNE ARENACEE CON CONGLOMERATI E GESSI` | 1 098.5 m |
| ASTI\|1 | 370.0-1 250.0 m | `MARNE,SABBIE E GESSI` | 880.0 m |
| MALOSSA\|15 | 5 136.0-5 491.0 m | `CALCARI` | 355.0 m |
| TRECATE\|9\|ST | 5 468.0-6 087.0 m | `CALCARI,MARNE E DOLOMIE` | 619.0 m |

The most common value across all 178 intervals is `SABBIE E ARGILLE` ("sands and
clays", 26 occurrences). **It states which lithologies are present, not in what
proportion.** SALUZZO carries a single descriptor over 1 104.7 m. There are 178
intervals across 46 wells -- 3.9 per well.

Reading "sands and clays" as 50/50, or inferring dominance from the order of the
words, would be **inventing a regional value**. That is precisely what the brief
forbids.

### 6.3 No digital logs are held, and none exist for our wells nationally

| Check | Result |
| --- | --- |
| `.las` files on disk | **0** |
| Wells in the national LAS index (`data/KML/pozzi-las.kml`) | 57 |
| Of those, matching any of our 46 wells | **0** |
| Coverage of that index | Emilia-Romagna (Alfonsine and similar), not Piemonte |
| `Profilo` column in `pozzi-storici.csv` | 2 654 rows carry `'0'`; it is not a log inventory |

So the digital-log route is closed both locally and nationally for these wells.

### 6.4 Composite-log PDFs exist but are raster scans

42 of the 46 wells have a composite-log PDF in `data/PDF/` (2 338 files total).
Tested directly:

| File | Pages | Extractable text | Embedded images |
| --- | --- | --- | --- |
| `saluzzo_001.pdf` | 1 | **0 characters** | 1 |
| `asigliano_vercellese_001.pdf` | 1 | **0 characters** | 1 |
| `malossa_015.pdf` | 1 | **0 characters** | 1 |

Each is a single-page scanned image with no text layer, confirming the Phase 0
reconnaissance. Extracting GR or SP traces would require **raster log
digitisation**, which the project's standing constraints exclude, and which
would in any case need a declared cutoff methodology (item 4 above) before it
produced a number.

### 6.5 A finding beyond NTG: two wells are carbonate

From our own ingested lithology, **MALOSSA|15 bottoms in `CALCARI` (limestone)
and TRECATE|9|ST in `CALCARI,MARNE E DOLOMIE` (limestones, marls, dolomites)**.
Both are carbonate at total depth, consistent with the published description of
the deep western Po Valley plays as Triassic carbonate reservoirs.

Two consequences:

1. **A clastic net-sand NTG would not transfer to these two wells**, whatever
   value the literature eventually supplies for the Po Plain clastics.
2. **Neither does the porosity range the project already adopts.** Donda's
   10-35% is derived from sonic logs across 14 **Plio-Pleistocene clastic**
   reservoirs. Applying it to a Triassic carbonate is a transferability gap that
   the audit's Phase 9 evidence-class assignment (`regional`, "same play type as
   the pilot wells") does not currently capture.

Point 2 is outside the scope of this review and is **not** a recommendation to
change anything. It is recorded because it was found while answering the NTG
question and it bears on Finding 9.8 and on the `EvidenceClass` reasoning.

---

## 7. Method and limitations

Searches covered peer-reviewed literature, the CO2StoP and EU GeoCapacity
project reports, ISPRA / Servizio Geologico d'Italia, Po Plain basin-analysis
literature and Po Valley petroleum-geology literature. Donda et al. (2011) and
the CO2StoP Final Report were read in full from local text extractions; all
quotations above are verbatim from those.

**Limitations, stated plainly:**

1. **No Italian-language search was performed.** A Piemonte NTG may exist in an
   Italian-language regional study, an ARPA Piemonte or Regione Piemonte
   technical report, or an unindexed thesis. This is the single most likely
   place the missing value would be found, and it was not searched.
2. **Two paywalled Italian CCS papers were not obtained**: "A feasibility study
   for CO2 geological storage in Northern Italy" (which reportedly builds a
   PETREL static model of the **Malossa** structure from 18 wells over 34 km2)
   and "Screening, classification, capacity estimation and reservoir modelling
   of potential CO2 geological storage sites in the NW Adriatic Sea, Italy"
   (IJGGC, 2023). The Malossa study is the most likely published source of a
   usable Po Plain NTG and should be the first acquisition target.
3. **IEAGHG Technical Report 2023-05** ("Classification of Total Storage
   Resources and Storage Coefficients") was identified but its host refused
   connections. It is the most recent authoritative treatment of storage
   coefficients and may carry lithology-specific NTG ranges.
4. **ViDEPI was not queried directly.** The KML index held locally lists 57 LAS
   wells; the live portal may hold more, including scanned well reports with
   interpreted net intervals.

**Separation of source from interpretation:** every quotation and every table
row above is sourced. The judgement that Bradanica fails transferability, the
classification into directly applicable / analogous / generic, and the
conclusion that our own data cannot support a derivation are **this review's
interpretation**.

---

## 8. Decision and next step

> **NTG evidence insufficient. Proceed to the B-prime control experiment, or to
> data acquisition.**

**Recommended next action, in order of value per unit of effort:**

1. **Run the B-prime control experiment.** It needs no NTG. Re-run the CSLF
   seven-component Monte Carlo with the net-to-gross term fixed at 1, first
   reproducing the published 1-4% range as a control. If the control does not
   reproduce, Candidate B-prime has no basis and the whole question changes
   shape. This is the only experiment currently unblocked.
2. **Acquire the Malossa feasibility study** (limitation 2). It is Italian, it
   is in the Po Plain, it models one of our own audited wells, and a static
   PETREL model necessarily contains a net-to-gross.
3. **Search Italian-language regional sources** (limitation 1).
4. **Ask Donda et al. for the gross thicknesses behind Lombardia 1 and 2.** Two
   numbers would convert the closest published analogues into the first real Po
   Plain NTG values.

Acquisition targets 2-4 are worth pursuing in parallel with step 1, but **none
of them blocks it**.
