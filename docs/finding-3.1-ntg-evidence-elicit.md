# Finding 3.1 — NTG Evidence Audit

**Elicit literature search, 2026-09-23. Evidence gathering only.**
No file under `src/` or `tests/` was modified. No audit number, NTG value,
equation, constant or scientific assumption was changed. No NTG value is
assigned to, or inferred for, any project well. This file is an uncommitted
draft.

Companion to `docs/piemonte-ntg-evidence.md` (the baseline) and
`docs/finding-3.1-literature-review.md`.

---

## 1. Baseline conclusion

`docs/piemonte-ntg-evidence.md` (2026-09-21) concluded:

> **NTG evidence INSUFFICIENT.**

No source gave an NTG for any Piemonte reservoir, western Po Plain reservoir, or
any well in our corpus; our own data (GEOTHOPICA workbook, raster composite-log
PDFs) cannot yield one without raster log digitisation; and two of the five
screenable wells (MALOSSA|15, TRECATE|9|ST) bottom in carbonate, so a clastic NTG
would not transfer to them.

The baseline listed four open limitations: no Italian-language search; the
paywalled Malossa CCS feasibility study not obtained; IEAGHG 2023-05 not
obtained; ViDEPI not queried directly.

**What this search tested:** whether published literature or public datasets
located through Elicit can (A) confirm, (B) qualify, or (C) overturn that
conclusion — specifically whether any evidence connects to the formations,
fields or wells in our project, as opposed to relevant-but-generic literature.

---

## 2. Search strategy

Ten independent Elicit **Find papers** sessions on elicit.com (logged-in account),
plus one rejected query (Elicit requires a question form; it was rephrased as
search 7). Elicit ran several sub-queries per session.

| # | Theme | Query focus | Indexed by Elicit | Curated rows reviewed |
| --- | --- | --- | --- | --- |
| 1 | Po Plain + NTG | NTG of Po Plain basin reservoirs | 38 | 12 |
| 2 | Piemonte + logs / petrophysics | GR, SP, resistivity, porosity, permeability, net pay, cutoffs; Novara, Vercelli, Asti, Alessandria, Cuneo | ~5 location-specific | 4 |
| 3 | Target formations / fields | Villafortuna-Trecate, Malossa; Dolomia Principale, Conchodon; net pay, thickness, logs, cores | n/r | 5 |
| 5 | Legacy wells / CCS / geothermal | CO2 storage feasibility, static models, depleted fields, geothermal reuse, N. Italy | 48 | 14 |
| 6 | NTG methodology | Vshale, porosity/permeability cutoffs, net sand vs net reservoir vs net pay, cutoff sensitivity, carbonates, CO2 capacity | n/r | 15 |
| 7 | Public data sources | ViDEPI, UNMIG composite logs, digitised logs, tops, cores, Po Plain 3D models | 31 | 9 |
| 8 | Clastic formations in our wells | Sabbie di Asti, Sergnano gravel, Gonfolite, Serravalle; Tertiary Piedmont Basin | 43 | 7 |
| 9 | Carbonate reservoirs | Net pay / effective thickness / fracture-matrix porosity in Villafortuna-Trecate, Malossa, Gaggiano, Cavone | 57 | 6 |
| 10 | Italian-language | "rapporto netto/lordo", "spessore utile/netto", Pianura Padana piemontese e lombarda, log elettrici, carote | n/r | 9 |

(Theme 4 "carbonate reservoirs" is covered by searches 3 and 9. "n/r": Elicit did
not report an indexed count for that session.)

**Approximate volume:** about 250-300 records indexed by Elicit; **81 curated
rows** reviewed individually; **29 sources** saved to the Elicit collection
**"Finding 3.1 – Po Plain NTG"** (id `7b1c9fac-101d-4b11-bf8e-520b34bcecb2`).

**Full text:** of the 29, Elicit attached full text for **3** (Livani et al.
2023; Lindquist 1999; Gizzi 2021). These were read in full through the Elicit
library connector. Table 4 of Livani et al. (the well list) is an image in the
published article; it was read on the article's web page. For the other 26 only
abstracts were available, and every "not reported" statement below about them
refers to the abstract, not the paper.

**Cross-check against project data:** the well names in Livani Table 4 were
compared with the 46 wells in `data/Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx`
(read-only).

**Nothing was downloaded.** The Livani Zenodo archive (`Primitive_Data.rar`,
24.5 MB) was identified but not downloaded.

---

## 3. Strongest evidence

1. **Livani et al. (2023), ESSD 15, 4261-4293** — *the most consequential new
   finding.* They manually digitised **SP, GR and sonic logs** from **160 ViDEPI
   composite logs** (raster, 1:1000) using WebPlotDigitizer, resampled to 0.5 m,
   and released them as ASCII under CC-BY-4.0 at
   `doi:10.5281/zenodo.8126519`, together with wellhead data, rotary-table
   elevation, MD/TVD, deviation surveys, lithology and a "mineralisation"
   (hydrocarbon/water) discrete log. **This contradicts the baseline statement
   that "the digital-log route is closed both locally and nationally for these
   wells"** — for a subset of wells (section 7).
2. **Lindquist (1999), USGS OFR 99-50-M** (full text read) — the only source
   found that reports **quantitative net thickness for a project field**:
   *"Malossa average net reservoir thickness is 300 m (maximum 580 m)"*, citing
   Mattavelli & Margarucci (1992). It also reports Malossa dolomite porosity
   1-13% and permeability averaging tens of mD. **No gross is given.**
3. **Shogenova et al. (2022)** — the Malossa CCS study that the baseline flagged
   as its first acquisition target. The abstract establishes that the static
   model (PETREL, **18 wells**, **34 km2**) is of the **83 m thick Messinian
   Sergnano Gravel at 1240 m** — *not* the deep carbonate. Full text unavailable.
4. **Mattavelli & Margarucci (1992)** (not in Elicit; identified via Lindquist's
   citation) — the primary Malossa field description behind the 300 m net
   figure. It is the most likely place to find a Malossa gross/net pair.
5. **Casero et al. (2008)** — provenance of ViDEPI: digitisation and web
   delivery of public Italian petroleum records, with priority on composite logs.
6. **Barrera Acosta et al. (2024, EAGE; 2024, MPG)** — 3D Po Plain geomodel
   built from 845 wells using **ViDEPI and Geothopica**, the same source family
   as our workbook. Thermal, not NTG, but it confirms that the same well corpus
   is in active research use.

---

## 4. Direct NTG evidence (E0)

**For any project well, formation interval or field: none.**

One measured NTG was found in the literature, and it is recorded here only so
that it is not mistaken for project evidence:

- **Barbara field** (offshore central Adriatic, Quaternary biogenic-gas sands;
  Lindquist 1999, citing Ianniello et al. 1992): *"net-to-gross ratios ranging
  from 27% in the silty sands to 95% in the coarser sands."* This is a measured
  NTG **for Barbara**. Wrong sector (offshore Adriatic), wrong age (Quaternary),
  wrong play (biogenic-gas turbidite stacks). **Not usable for our wells.** For
  this project it is classed **E4**.

---

## 5. Reconstructable evidence (E1)

**Conditional E1: digital logs exist, but no NTG exists yet.**

For the wells listed in section 7, Livani et al. published digitised **SP and/or
GR** logs. An NTG could in principle be reconstructed from them, **but only after
three decisions this project has not made and this audit does not make**:

1. **A gross interval per well.** Livani provides regional horizons (top of the
   carbonate succession, base of the Pliocene, etc.) and lithology, not
   reservoir intervals.
2. **A declared cutoff methodology** (SP deflection or GR/Vshale threshold). The
   methodology literature (section 6) shows NTG depends materially on this
   choice, so it would become a new, documented project assumption.
3. **Acceptance of third-party digitised raster logs.** The traces were
   hand-digitised from the same kind of 1:1000 raster composite logs the project
   excluded from its own scope. Their accuracy is Livani's, not measured.

**The Malossa field net thickness** (300 m average, 580 m maximum; Lindquist
citing Mattavelli & Margarucci 1992) is a net figure, **not an NTG**. It would
become E1 for the Malossa field *only* if the primary source gives the matching
gross reservoir interval. It does not become E1 for MALOSSA|15 (section 10).

---

## 6. Regional / methodological evidence (E2-E4)

These are **not** direct evidence. None of them may be converted into a
numerical NTG for a project well.

**E2 — strong regional / formation evidence**

- **Irace et al. (2009)**, Regione Piemonte — deep hydrostratigraphy of the
  western Po Plain. It is the most location-specific study found. The abstract
  reports useful fresh-water volumes; no thickness or NTG values are given there.
  The full text was not obtained.
- **Bertello, Fantoni et al. (2008)**; **Bello & Fantoni (2003)**; **Franciosi
  et al. (2002)**
  - They separate Malossa (Rhaetian-Liassic platform carbonate, compressional)
    from Villafortuna-Trecate (Middle-Triassic system, extensional), so the two
    fields should not share a reservoir model.
  - Reservoir depths: Malossa ≈ 5300 m; Villafortuna-Trecate 5700 and 6300 m.
  - They give no NTG.
- **Errico et al. (1980)** — main Malossa pay is Norian Dolomia Principale and
  Liassic Zandobbio. The abstract says reservoir characteristics are given but
  not what they are.
- **Ronchi (2000)** — diagenesis-porosity relationships of the Norian-Hettangian
  carbonate platforms in the Po Valley subsurface. It covers porosity, not NTG.
- **Rocco & D'Agostino (1972)** — Sergnano field. The sand-gravel reservoir is
  closed by an abrupt facies change into lowermost Pliocene shale. No thickness
  is given in the abstract.
- **Amadori et al. (2019)**; **Barrera-Fernandez et al. (2026)** — basin-scale
  Plio-Pleistocene sand/fine architecture from seismic and well logs. They give
  sand distribution, not NTG.
- **Macini et al. (2010)** — a Lombardia deep saline aquifer candidate with more
  than 370 Mt capacity. Full text not obtained; whether an effective thickness
  or NTG was used is unknown.

**E3 — methodological analogue** (how to build an NTG, not what it is)

- **Worthington (2008, 2009)** — tiered net sand / net reservoir / net pay, and
  the point that an NTG without its net class and cutoff is an inadequate
  descriptor. This matches the project's `net_criterion` / `net_basis` design.
- **Dose et al. (2005)**; **Snyder (1971)**; **Cobb & Marek (1998)**;
  **Saboorian-Jooybari (2017)** — cutoff workflows and why cutoffs depend on the
  purpose they serve.
- **Derder (2024)**; **Ali et al. (2024)** — sensitivity of net pay and NTG to
  the choice of cutoff.
- **Bartelucci et al. (2008)**; **Ibrahim & Ogliani (2006)** — Cavone field (Po
  Valley, Mesozoic carbonate). Core-log integration and a permeability cutoff
  for pay, with the porosity type (intergranular, fracture or vuggy) resolved
  from sonic and neutron logs.
  - This is the only Po Valley carbonate net-pay *workflow* found.
  - It is the wrong field, and no values are given in the abstracts.
- **Cui et al. (2018)** — facies-conditioned permeability in heterogeneous
  carbonates.

**E4 — weak analogue**

- **Barbara field** NTG 27-95% (section 4).
- **Cavone** net thicknesses ~10 to >100 m (Lindquist, citing Nardon et al.
  1991). No gross is given, and it is a different field.
- **Cortemaggiore** individual producing zones 1.5-31 m (Lindquist). No gross,
  and it is a Miocene Apennine-front field.
- **Shallow hydrogeology**
  - De Luca et al. (2020): percentage of permeable deposits, 0-50 m depth only.
  - Cavallin et al. (2020): 3D gravel/sand/clay percentages from 11,993
    water-well logs.
  - Lombardian aquifer 3D model (2008): cumulative sand content.
  - Bersezio et al. (2004) and Scardia & Muttoni (2009).
  - All of these are at hundreds of metres, not the 1.5-6 km screening depths.

**E5 — not usable for quantitative NTG inference**

- Piana et al. (2017)
- Morelli et al. (2017)
- Forno et al. (2015)
- Caprara et al. (2020)
- Gelati et al. (Gonfolite)
- Gizzi (2021a, b)
- Alimonti et al. (2023)
- Desideri et al. (2008)
- Rossi et al. (2011)
- Quattrocchi et al. (2008)
- D'Alesio et al. (2011)
- Molinari et al. (2015)
- Turrini (2016)
- D'Ambrogi et al. (2020)

These give geological framework, well reuse, integrity or velocity information,
but no net/gross quantity.

---

## 7. Formation and well mapping

**Overlap between Livani Table 4 (160 wells) and our 46 GEOTHOPICA wells**, found
by matching names:

| Our well | In Livani? | Livani logs | Our project status |
| --- | --- | --- | --- |
| **MORETTA 1** (Cuneo, TD 3091 m) | **Yes** (W101) | lithology, mineralisation, sonic, **SP** | not one of the five screenable audited wells |
| **NOVI LIGURE 2** (Alessandria, TD 1700 m) | **Yes** (W106) | lithology, mineralisation, sonic, **SP** | not one of the five |
| **SOMMARIVA DEL BOSCO 1** (Cuneo, TD 3809 m) | **Yes** (W143) | per Table 4: GR, lithology, mineralisation, sonic, SP — **the released file has no GR** (see "Livani 2023 dataset feasibility") | not one of the five |
| MALOSSA 15 | **No** | — | screenable (carbonate TD) |
| — (same field) | Malossa 4 (W089) | **GR**, lithology, mineralisation, **SP** | not in our corpus |
| — (same field) | Malossa B Iniezione (W090) | lithology, mineralisation, sonic, **SP** | not in our corpus |
| SALUZZO 1, DESANA 1, ASTI 1, TRECATE 9ST | **No** | — | screenable |
| All other TRECATE / VILLA FORTUNA wells | **No** | — | — |

**The five audited screenable wells: none is in Livani.** Three non-audited
Piemonte wells are.

**What the literature ties to each audited well:**

- **SALUZZO\|1** — no well-specific literature found. The TD interval in our
  data is `CIOTTOLI E SABBIE`, 422.8-1527.5 m.
- **DESANA\|1**
  - Lindquist names Desana as the westernmost field of the province, *"of which
    little is published other than its 1954 discovery date, its abandoned
    status, and the fact that it has few reserves"*.
  - Lindquist also says its petroleum-system assignment is uncertain.
  - No reservoir data exists for it in the literature.
- **ASTI\|1** — no well-specific literature. The Asti Sands are described only
  from outcrop and the shallow Turin-plain subsurface: shallow-marine sands
  100-120 m thick, with no porosity or NTG given.
- **MALOSSA\|15** — the **field** is well documented; the **well** is not. See
  section 10 for the interval mismatch.
- **TRECATE\|9\|ST**
  - The Villafortuna-Trecate main reservoir sits at 5800-6100 m (Gizzi 2021,
    citing its ref. 28), in Middle-Triassic-sourced, dolomitised Late
    Triassic-Early Jurassic platform units.
  - No net or NTG is published for the field or the well.

**Observation from our own data (recorded, not acted on):**

- In the GEOTHOPICA `Lito-Stratigrafie` sheet, MALOSSA 15's deepest interval
  (5136-5491 m) is `MAIOLICA, ROSSO AMMONITICO` — `CALCARI`, **Jurassic**.
- The main Malossa pay in the literature is the **Norian Dolomia Principale /
  Liassic Zandobbio**.
- The baseline document calls the deep western plays "Triassic carbonate
  reservoirs" (section 6.5). For MALOSSA|15 specifically, our own data puts TD in
  younger Jurassic limestones.
- This does not change any number. It sharpens the transferability gap in
  section 10.

---

## 8. Public data opportunities

| Resource | What it holds | Relevance | Access |
| --- | --- | --- | --- |
| **Livani et al. 2023, Zenodo `10.5281/zenodo.8126519`** | ASCII SP / GR / sonic at 0.5 m, well headers, deviation, lithology, mineralisation; 160 wells | **Direct**: digital logs for MORETTA 1, NOVI LIGURE 2, SOMMARIVA DEL BOSCO 1, and two Malossa-field wells | Public, CC-BY-4.0. `Primitive_Data.rar` (24.5 MB) was **downloaded with your approval and inspected** into the session scratchpad, outside the repo; see "Livani 2023 dataset feasibility". `Derived_Data.rar` (16.6 MB) was not downloaded. |
| **ViDEPI** (videpi.com; Casero et al. 2008) | Raster composite logs, well tops, final well reports for relinquished Italian licences | Source of Livani's logs; may hold final well reports with interpreted net intervals for our wells | Public web portal; not queried in this session |
| **Mattavelli & Margarucci (1992)**, Malossa field description (AAPG Treatise / Atlas of Oil and Gas Fields) | Primary source of "net reservoir 300 m average, 580 m max" | Most likely source of a Malossa **gross/net pair** | Library acquisition |
| **Shogenova et al. (2022)** and related CLEANKER project reports | Malossa static model (18 wells, PETREL) of Sergnano Gravel | A static model contains an NTG, but for the **1240 m Sergnano** interval | Paywalled / project reports; full text not attached by Elicit |
| **Irace et al. (2009)**, Regione Piemonte / CNR-IGG / Univ. Torino | Deep hydrostratigraphy of the Piemonte plain | Only Piemonte-specific deep-subsurface study; may carry aquifer thickness and sand fraction | Regional publication; full text not obtained |
| **UNMIG / MISE** well archive and **VIGOR** | Well records and dismissed-well data (cited by Gizzi 2021) | Possible final well reports for TRECATE / VILLA FORTUNA wells | Public portals; not queried |
| **BDNG** (Italian National Geothermal Database) | Litho-stratigraphy and temperatures (e.g. Trecate4) | Same family as our GEOTHOPICA workbook; stratigraphy, not NTG | Public |
| **HotLime 3D model** (D'Ambrogi et al. 2020; 305 wells) and **GeoPiemonte** (Piana 2017; Morelli 2017) | Regional horizons and unit tops | Could supply **gross interval** boundaries (formation tops) | Public |

---

## 9. Evidence table

Classification is **relative to our target wells**.

| Source | Year | Identifier | Basin / area | Formation | Field / well | Reservoir type | NTG reported? | NTG value | Net thickness | Gross thickness | Logs | Core | Porosity / permeability | Cutoffs | Class | Applicability to our wells | Key limitation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Livani, Petracchini et al. | 2023 | 10.5194/essd-15-4261-2023; zenodo.8126519 | Po Plain + N. Adriatic | multiple (regional units) | 160 wells incl. Moretta 1, Novi Ligure 2, Sommariva del Bosco 1, Malossa 4, Malossa B Inj. | clastic + carbonate | No | — | — | — | SP, GR, sonic (digitised), resistivity-derived mineralisation | no | no | none | **E1 (conditional)** | 3 non-audited project wells; 0 of 5 audited | Hand-digitised raster; no reservoir intervals; cutoff undeclared |
| Lindquist (USGS) | 1999 | 10.3133/OFR9950M | Po Basin Province | Triassic dolomites (Malossa) | Malossa field | fractured / vuggy dolomite | No | — | **300 m avg, 580 m max** (Malossa) | not given | — | — | φ 1-13%, k tens of mD | — | **E2** (Malossa) | Field-level; not MALOSSA\|15's TD interval | Secondary citation; no gross |
| Lindquist, citing Ianniello 1992 | 1999 | as above | Offshore central Adriatic | Quaternary sands | Barbara field | biogenic gas turbidites | **Yes** | **27-95%** | — | — | — | — | φ ~30%, k 5-1000 mD | — | **E4** (E0 at source) | None | Wrong sector, age and play |
| Shogenova, Shogenov et al. | 2022 | Semantic Scholar 02136a42… | Po Plain, Lombardy | Messinian Sergnano Gravel | Malossa structure (18 wells) | conglomerate saline aquifer | not in abstract | — | — | 83 m (net or gross not stated) | wells used | — | — | — | **E2** | Same structure as MALOSSA\|15, different interval (1240 m vs 5.1-5.5 km TD) | Full text not obtained |
| Errico, Groppi et al. | 1980 | AAPG | Po Valley | Dolomia Principale, Zandobbio | Malossa | dolomite | not in abstract | — | — | — | — | — | "reservoir characteristics given" | — | **E2** | Field only | Abstract only |
| Bertello, Fantoni et al. | 2008 | Boll. Soc. Geol. It. | Italy / Po Valley | Rhaetian-Liassic; Middle Triassic | Malossa; Villafortuna-Trecate | carbonate | No | — | — | — | — | — | — | — | **E2** | Framework only | No reservoir values |
| Bello & Fantoni; Franciosi et al. | 2003; 2002 | AAPG Hedberg | W. Po Valley | Triassic | Malossa; Villafortuna-Trecate | carbonate | No | — | — | — | — | — | — | — | **E2** | Framework; depths | No reservoir values |
| Gizzi | 2021 | 10.3390/app112210551 | W. Po Valley | L. Triassic-E. Jurassic dolomitised platform | Trecate4 (our TRECATE 4) | carbonate | No | — | — | main reservoir 5800-6100 m | litho-strat (BDNG) | — | thermal properties only | — | **E5** | Depth context only | Geothermal study |
| Irace, Clemente et al. | 2009 | Regione Piemonte | W. Po Plain, Piemonte | Plio-Quaternary aquifers | regional | clastic aquifers | not in abstract | — | — | — | — | — | — | — | **E2** | Region matches; depth probably shallower | Full text not obtained |
| Macini, Mesini et al. | 2010 | 10.2118/133941-MS | Lombardia | deep saline aquifer | candidate site | clastic aquifer | not in abstract | — | — | — | — | — | — | — | **E2** | Lombardy, not Piemonte | Full text not obtained |
| Rocco & D'Agostino | 1972 | AAPG | Po Basin (Pede-Alpine) | Sergnano sand-gravel | Sergnano field | clastic strat trap | No | — | — | — | — | — | — | — | **E2** | Formation shared with Malossa structure | Abstract only |
| Amadori et al.; Barrera-Fernandez et al. | 2019; 2026 | 10.1111/bre.12369 | Po Plain-N. Adriatic | Plio-Pleistocene sequences | basin-scale | clastic | No | — | — | — | well logs + seismic | — | — | — | **E2** | Sand-body architecture only | No per-well NTG |
| Bartelucci et al.; Ibrahim & Ogliani | 2008; 2006 | Boll. SGI; EAGE | Po Valley (Modena) | Mesozoic / Jurassic carbonate | Cavone | carbonate | No | — | ~10 to >100 m (Lindquist) | — | core-log, sonic, neutron | yes | φ ~5-10%, k 10-100 mD matrix (Lindquist) | permeability cutoff for pay | **E3** | Workflow analogue for carbonates | Wrong field |
| Worthington; Dose; Snyder; Cobb & Marek; Saboorian-Jooybari; Derder; Ali | 1971-2024 | various | non-Italian | — | — | — | method | — | — | — | — | — | — | yes | **E3** | Method only | Not Po Plain |
| De Luca; Cavallin; Lombardian 3D; Bersezio; Scardia & Muttoni | 2004-2020 | various | Piemonte / Lombardy plains | Quaternary aquifers | water wells | shallow clastic | proxy (sand %) | — | — | — | water-well logs | some | — | — | **E4** | 0-220 m only | Wrong depth range |
| Casero et al. | 2008 | EAGE | Italy | — | ViDEPI archive | — | No | — | — | — | composite logs (raster) | — | — | — | **E5** (data source) | Route to raw logs | Not an analysis |
| Barrera Acosta et al. | 2024 | EAGE; MPG | Po Plain | — | 845 wells (ViDEPI + Geothopica) | — | No | — | — | — | BHT, DST | — | — | — | **E5** | Same corpus, thermal only | No NTG |

**E0 for any project well: 0. E1 (conditional) for project wells: 1 dataset
covering 3 non-audited wells. E1 for audited wells: 0.**

---

## 10. Applicability to our wells — where the chain breaks

| Audited well | Break point |
| --- | --- |
| **SALUZZO\|1** | No publication and no digital log. Not in Livani. The chain breaks at **data existence**. |
| **DESANA\|1** | The field is named in the literature only to say that little is published. Not in Livani. The chain breaks at **data existence**. |
| **ASTI\|1** | The Asti Sands are described only from outcrop or shallow subsurface, with no net/gross. Not in Livani. The chain breaks at **data existence** (and at depth). |
| **MALOSSA\|15** | **Four** independent breaks. (1) The quantitative net figure (300 m) is **field-level**, not for this well. (2) It is a **net** thickness with no gross, so it is not an NTG. (3) It refers to the **Norian-Liassic dolomite** pay, while our data puts MALOSSA 15's TD interval in **Jurassic Maiolica / Rosso Ammonitico limestone**, a different reservoir. (4) The Malossa CCS static model (Shogenova 2022) is of the **1240 m Sergnano Gravel**, a different interval again. Livani has Malossa 4 and Malossa B Iniezione, **not** Malossa 15. |
| **TRECATE\|9\|ST** | Field reservoir depth and play are published, but no net or NTG. No Trecate or Villafortuna well is in Livani. The chain breaks at **data existence**. |

**For the three non-audited wells that *are* in Livani** (MORETTA 1, NOVI
LIGURE 2, SOMMARIVA DEL BOSCO 1), the chain does **not** break at data existence.
It breaks at three **decisions**: the gross-interval definition, the cutoff
methodology, and whether third-party digitised raster logs are acceptable as
evidence. It also breaks at scope, because none of these wells is currently among
the audited screenable wells.

**Guard checks applied:**

- No regional source was treated as well-specific.
- The Malossa field figure was explicitly separated from MALOSSA\|15.
- The Barbara E0 NTG was downgraded to E4 for this project.
- No porosity or permeability value was converted into an NTG.

---

## 11. Finding 3.1 conclusion

> ### STILL BLOCKED

Supporting evidence:

1. **Zero E0 and zero unconditional E1 evidence** exists for any of the five
   audited screenable wells, their formations at the screened (TD) depth, or
   their fields.
2. The **only quantitative net figure** for a project field (Malossa, 300 m) is
   a field-level net with no gross. It describes a different stratigraphic
   interval from MALOSSA\|15's TD interval.
3. The **Italian-language search** (baseline limitation 1) returned only shallow
   hydrogeology (under 220 m) and regional texture models. **This limitation is
   now closed with a negative result.**

**The baseline is qualified in one respect, not overturned.** The baseline
statement that digital logs do not exist nationally for our wells is **no longer
accurate for three of the 46 corpus wells**: MORETTA 1, NOVI LIGURE 2 and
SOMMARIVA DEL BOSCO 1 have public digitised SP (and one has GR) logs in Livani et
al. (2023). This does not unblock Finding 3.1 for the audited wells, so
"PARTIALLY UNBLOCKED" was rejected. Doing so would mean promoting non-audited
wells and three undecided methodological choices into evidence.

**Answer to the brief's A/B/C question:** mostly **A (confirms)**, with a narrow
**B** qualification on data availability for three non-audited wells. **Not C.**

---

## 12. Minimum next dataset

The smallest concrete dataset that would move Finding 3.1 for an **audited**
well:

> **For one audited well: a gross reservoir interval (top and base, same depth
> convention as `thickness_m`) plus the operator's interpreted net interval (or a
> digital SP/GR log over that interval with a declared cutoff), from the final
> well report or composite log.**

The cheapest concrete targets, in order:

1. **Mattavelli & Margarucci (1992)** Malossa field description. One published
   gross/net pair would give a field-level Malossa NTG for the dolomite pay.
   Whether that pay applies to MALOSSA\|15's Jurassic TD interval would still
   need its own check.
2. **ViDEPI final well report** for TRECATE 9ST, SALUZZO 1, DESANA 1 or ASTI 1.
   Interpreted net intervals are sometimes stated in the report text, separately
   from the raster log.

---

## 13. Recommended next research action

Evidence acquisition only. No code changes.

1. **Obtain Mattavelli & Margarucci (1992)** through a library. Extract the
   Malossa gross and net reservoir thickness and the reservoir interval
   definition, and check which stratigraphic unit they refer to.
2. **Query ViDEPI directly** for SALUZZO 1, DESANA 1, ASTI 1, TRECATE 9ST and
   MALOSSA 15. Record whether a final well report exists and whether it states
   interpreted net intervals. (This is baseline limitation 4, still open.)
3. ~~Download and inspect the Livani Zenodo archive.~~ **Done on 2026-09-23**
   (see "Livani 2023 dataset feasibility"). Follow-up: for SOMMARIVA DEL BOSCO 1,
   get the ViDEPI raster master-log header. It supplies the SP scale and
   log-run boundaries and any Rmf/Rw annotation needed to judge SP usability.
   Do **not** compute an NTG until a gross-interval rule and cutoff are
   separately decided and documented.
4. **Obtain the Shogenova et al. (2022) full text or CLEANKER reports** to see
   whether the Sergnano static model states its NTG and the 18 wells used, and
   whether MALOSSA 15 is one of them.
5. **Obtain the Irace et al. (2009) full text** from Regione Piemonte for any
   deep-aquifer thickness and sand-fraction data by well.

---

## Livani 2023 dataset feasibility

**Added 2026-09-23 after you approved the download. Read-only inspection.**
No NTG, net fraction or cutoff was computed. No project file other than this
report was touched.

### Provenance of the inspected files

- **File:** `Primitive_Data.rar` from Zenodo record 8126519 (Livani et al. 2023,
  CC-BY-4.0), 24,530,990 bytes. MD5 `a703b838afeaed3137bb83d7b8ccc57d` matches
  the checksum Zenodo publishes.
- **Location:** downloaded and extracted into the session scratchpad, **outside
  the repository**. Nothing was added to `data/` or anywhere in the repo.
  `Derived_Data.rar` was not downloaded.
- **Files used:**
  - `ASCII_well_Primitive/ReadMe_Well_PrimitiveData.txt`
  - `Well_heads.txt`
  - `WellLogAv.txt`
  - `Well_logs_UOI/W101.txt` (Moretta 1)
  - `W106.txt` (Novi Ligure 2)
  - `W143.txt` (Sommariva del Bosco 1)
- **Project data compared against (read-only):**
  `data/Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx` (`Anagrafica`,
  `Lito-Stratigrafie`), plus one read-only `api.screen_well` call per well to see
  how the pipeline treats it.

### What the dataset is, per its own ReadMe

- SP, sonic and GR were **"digitized manually with a variable sampling step, or
  by a semi-automatic method for line recognition"** from the ViDEPI raster
  master logs (1:1000), then **resampled to a constant 0.5 m**.
- Units: SP in mV, sonic in µs/ft, GR in API. `99999` means no data.
- The `Lithology` and `Mineralization` columns **"have been created during the
  analysis of the available data"**. They are Livani's interpretation, not
  measurements.
  - Lithology codes: 0 sand, 1 shale, 2 alternances, 3 limestone,
    4 conglomerate, 5 crystalline basement, 6 marls, 7 dolomite, 8 gravel,
    9 cemented sands.
  - Mineralization codes: 0 water, 1 gas.
- Each file gives X/Y (UTM 32N), TVDSS, MD, inclination, azimuth and the log
  columns. **The files contain no formation tops, unit names or reservoir
  intervals.**

### Well-by-well table

| Item | **MORETTA 1** (W101) | **NOVI LIGURE 2** (W106) | **SOMMARIVA DEL BOSCO 1** (W143) |
| --- | --- | --- | --- |
| Province / TD (our data) | Cuneo / 3091 m | Alessandria / 1700 m | Cuneo / 3809 m |
| TD in Livani (MD) | 3091.0 m — **matches** | 1700.0 m — **matches** | 3809.0 m — **matches** |
| Well-head elevation | Livani rotary table 269.2 m; our `quota` 260 m (Δ 9.2 m) | 192.5 m vs 188 m (Δ 4.5 m) | 307.7 m vs 300 m (Δ 7.7 m) |
| Trajectory | vertical (INC 0 throughout) | vertical | vertical |
| Status in our pipeline | `screened` at 3091 m | `screened` at 1700 m | `screened` at 3809 m |
| Claimed availability (`WellLogAv.txt` / paper Table 4) | Lith, Min, Sonic, SP | Lith, Min, Sonic, SP | **GR**, Lith, Min, Sonic, SP |
| **SP actually in file** | Yes: MD 100.5-3087.5, 99% of span; gaps 397-410 m and 2006.5-2022.5 m | Yes: MD 30.0-1699.5, 100%, no gaps | Yes: MD 24.0-3795.0, 100%, no gaps |
| **Sonic actually in file** | Yes: MD 47.5-3087.5, 100%; gap 959.5-961.5 m | Yes: MD 308.0-1694.0, 100% | Yes: MD 26.5-3792.0, 100%; gap 478.5-485 m |
| **GR actually in file** | No column | No column | **No column, although availability says "Y"** |
| Resistivity / density / neutron | not in file | not in file | not in file |
| Sampling | 0.5 m (resampled) | 0.5 m (resampled) | 0.5 m (resampled) |
| True vertical resolution | Unknown. Limited by a 1:1000 raster and the variable digitising step. Adjacent-sample values are ~100% distinct, as expected from interpolation. | same | same |
| Data type | Hand- or semi-automatically digitised from raster; resampled | same | same |
| Formation tops in Livani file | None | None | None |
| Livani lithology column | Gravel 47.5-191; Sand 191.5-2500.5; Shale 2501-2623.5; Alternances 2624-2930.5; Basement 2931-3088 | Shale/Conglomerate alternation 40.5-618 (conglomerate beds of 7-29 m); Shale 618.5-793; Marls 793.5-1700 | Gravel 24-240.5; Sand 241-1240; Conglomerate 1240.5-1267; Sand 1267.5-1508; Shale 1508.5-1560.5; Sand 1561-1798; Alternances 1798.5-1915; Sand 1915.5-2475; Shale 2475.5-2588.5; Sand 2589-2722.5; Shale 2723-2856.5; Cemented sands 2857-3795.5 |
| Livani mineralization | Water throughout (47.5-3077) | Water throughout | Water throughout |
| Our tops (GEOTHOPICA) | Alluvione 10-190; **Sabbie di Asti 190-2162**; Sartirana 2162-2450; Gessoso-Solfifera 2450-2483; Gallare 2483-2619; **Gonfolite 2619-2930**; **Basamento metamorfico 2930-3091** | Clays with conglomerates and sands 0-720.2 (L. Pliocene); Clays and gypsum 720.2-760.2; **Clays with sands and conglomerates 760.2-1695.2 (M.-U. Miocene)** | Pleistocene 23-240; **Sabbie di Asti 240-1190**; Sartirana 1190-1560; "Serravalle ?" 1560-1800; **Serravalle 1800-3809** |
| Consistency of Livani lithology with our tops | Good. Boundaries agree within ~20 m (Gallare shale 2483 vs 2501; Gonfolite 2619 vs 2624; basement 2930 vs 2931). | Poor at one boundary: our 720.2 m Plio/Mio contact vs Livani's shale-to-marl change at 793 m. | Good (Pleistocene base 240/240.5; shale at 1508-1560 against our Sartirana base at 1560). |
| **Interval the project screens (TD)** | **Metamorphic basement**, 2930-3091 m. Not a reservoir. | Clays with sands and conglomerates, 760-1695 m. Livani calls it marls. | Serravalle (Tortonian), 1800-3809 m: sand / shale / cemented-sand succession |
| Logs cover the screened interval? | Yes, but the interval is basement | Yes (SP 100%, sonic 100%) | Yes (SP 99-100%, sonic 100%) |
| Logs cover candidate reservoir units? | Yes: Sabbie di Asti (SP coverage 98.6%) and Gonfolite (100%) | Yes: the conglomerate-bearing upper section | Yes: Sabbie di Asti, Serravalle |
| SP signal quality (descriptive) | Wide range in the Asti interval (p5-p95 spread ~89 mV). Level shifts between units. Basement SP -61 to -26 mV, so SP is not a pure lithology signal. | Screened-interval spread ~83 mV. The whole curve sits at positive mV. | Upper Asti interval shows a 178 mV spread and a +417 mV/km trend, implying a **baseline shift inside a named unit**. Serravalle spread ~71 mV. |

### Feasibility for a future NTG reconstruction (assessment only)

A defensible NTG needs six inputs. For each well:

| Required input | MORETTA 1 | NOVI LIGURE 2 | SOMMARIVA DEL BOSCO 1 |
| --- | --- | --- | --- |
| 1. Continuous net indicator over the gross interval | SP only | SP only | SP only (the claimed GR is missing) |
| 2. Gross interval definition | Missing: the screened TD interval is basement, and a reservoir interval has not been chosen | Missing: the screened interval is clay- or marl-dominated in both sources | Missing, but Serravalle 1800-3809 is a candidate from our own tops |
| 3. Declared cutoff method (SP deflection or shale baseline) | Not declared. Level shifts mean a single baseline per well would not be valid. | Not declared | Not declared; a baseline shift was observed within a unit |
| 4. Log-run and scale metadata (where the SP scale or reference changes) | Not in the dataset; needs the raster header from ViDEPI | Missing | Missing |
| 5. Formation-water vs mud-filtrate contrast (SP only works if Rw ≠ Rmf) | Unknown. The shallow Asti aquifers may be fresh (Irace et al. 2009 studies fresh water in very deep Piemonte aquifers), which would suppress or reverse the SP. | Unknown | Unknown |
| 6. Independent check (core, GR, operator net pay) | None | None | None |
| **Classification** | **PARTIALLY RECONSTRUCTABLE** | **PARTIALLY RECONSTRUCTABLE** | **RECONSTRUCTABLE IN PRINCIPLE** |

**Why each class:**

- **SOMMARIVA DEL BOSCO 1 — RECONSTRUCTABLE IN PRINCIPLE.**
  - Its screened interval is a genuine sand/shale/cemented-sand succession.
    Livani's lithology agrees with our tops.
  - That interval is covered continuously by digitised SP and sonic over its
    full length (1800-3795 m).
  - "In principle" means the data *exist* over the right interval. An NTG would
    still need items 2-5 to be decided and documented, and it would be
    SP-only-derived, with no GR, no core and no operator net pay to check it.
  - The GR that the availability table claims **is not in the released file**.
- **NOVI LIGURE 2 — PARTIALLY RECONSTRUCTABLE.**
  - Logs cover the screened interval completely.
  - Both our data and Livani describe that interval as clay- or marl-dominated.
    The only resolved coarse beds (conglomerate, 7-29 m thick) lie *above* it,
    at 358-618 m.
  - The two sources disagree on the unit boundary (720 vs 793 m). A gross
    interval would therefore be a new project choice, not something the data
    identify.
- **MORETTA 1 — PARTIALLY RECONSTRUCTABLE.**
  - Excellent log coverage of the Sabbie di Asti and the Gonfolite.
  - But the interval our pipeline screens at TD is **metamorphic basement**, for
    which an NTG is not meaningful.
  - The logs could support an NTG only for an overlying unit the project does
    not currently screen. For the interval as currently screened, it is **not
    reconstructable**.

**What is still missing for all three:**

- A declared gross-interval rule.
- A declared SP cutoff and baseline method.
- Log-run and scale metadata from the ViDEPI raster headers.
- Formation-water resistivity or salinity (to confirm SP polarity and
  magnitude).
- Any independent check from core, GR or operator net pay.

**None of these is in the Livani dataset.**

### Side observations (recorded, not acted on)

- **Depth datum.** Livani measures MD from the **rotary table**; TVDSS at
  MD = 0 equals the RT elevation. The RT elevations are 4.5-9.2 m above our
  `quota` values, and the TDs match ours exactly. That is consistent with our
  depths also running from the rotary table, which bears on Finding 4.2 / 10.2
  (datum). **No change made.**
- **MORETTA 1 is screened at a TD inside metamorphic basement** (2930-3091 m in
  both sources). That is a data-selection observation about which interval
  the pipeline evaluates. It is **outside the scope of this task and was not
  acted on**.
- **Documentation discrepancy in Livani.** `WellLogAv.txt` and paper Table 4 list
  GR for Sommariva del Bosco 1, but the released log file has no GR column.
  Anyone relying on the table would overstate the evidence.

### Effect on Finding 3.1

**None. The status remains STILL BLOCKED.**

- None of the three wells is one of the five audited screenable wells.
- Even for Sommariva del Bosco 1, the dataset supplies a curve, not an NTG.
  Turning it into one would need four methodological choices that are not yet
  made: gross interval, cutoff, baseline handling, and the Rw/Rmf assumption.
- The section 11 qualification stands, now made precise: public digitised
  **SP and sonic** logs (no GR) exist for three non-audited, screenable corpus
  wells. One of them (Sommariva del Bosco 1) covers a genuine clastic succession
  at its screened depth.

---

## Verification before finishing

- [x] **Well-specific vs regional:** no source was treated as well-specific when
  it was only regional. The Malossa field figure is explicitly separated from
  MALOSSA\|15 (sections 5, 10), and Barbara's measured NTG is classed E4.
- [x] **No NTG assigned or inferred** for any project well. No range is proposed.
- [x] **No audit number changed.** `docs/scientific-validation-audit.md` and
  `docs/piemonte-ntg-evidence.md` were not edited.
- [x] **No code modified.** `git status` shows no tracked-file changes; this
  report is the only new project file. Two untracked stray files (`0`,
  `` dict[str`) ``) are hook artefacts and were left untouched.
- [x] **Uncommitted draft:** this report has not been committed.
- [x] **Livani inspection:** it was read-only.
  - No NTG, net fraction or cutoff was computed.
  - The only statistics produced are descriptive SP percentile spreads and
    trends per formation, used to judge signal quality.
  - The downloaded data sit in the session scratchpad, not in the repository.
  - The Finding 3.1 status is unchanged (STILL BLOCKED).
