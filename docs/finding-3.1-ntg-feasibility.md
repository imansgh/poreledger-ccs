# Finding 3.1 — NTG Reconstruction Feasibility

**Well: SOMMARIVA DEL BOSCO 1. Feasibility study only, prepared 2026-09-23.**

This document contains **no NTG value**: no net fraction, no net thickness and
no numerical cutoff. It does not modify any production code, equation,
screening input, prior, Monte Carlo setting, audit number or scientific result.
It is an uncommitted draft.

Companion to `docs/finding-3.1-ntg-evidence-elicit.md` (section "Livani 2023
dataset feasibility"), `docs/piemonte-ntg-evidence.md` and
`docs/net-to-gross-semantics.md`.

### Evidence labels used throughout

| Label | Meaning |
| --- | --- |
| **[OBS-L]** | Observed in the released Livani et al. (2023) dataset (Zenodo 8126519, `Primitive_Data`, file `W143.txt`) |
| **[OBS-R]** | Observed on the operator's raster composite log in *our own* project data, `data/PDF/sommariva_del_bosco_001.pdf` (AGIP "Profilo del pozzo", scale 1:1000, updated 06.02.92), read visually |
| **[OBS-W]** | Observed in our GEOTHOPICA workbook, `data/Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx` |
| **[LIT]** | Supported by cited published literature |
| **[INF]** | Methodological inference made in this document |
| **[ASM]** | An assumption that a reconstruction would have to make |
| **[OPEN]** | Unresolved question |

---

## 1. Current finding status

**Quantitative NTG remains BLOCKED.**

- **No audit-grade NTG can be computed today** for SOMMARIVA DEL BOSCO 1, or for
  any other well.
- The block is **no longer "no data exist"**. It is now:
  - undecided methodology (gross-interval rule, net criterion, SP baseline and
    cutoff);
  - missing fluid data (Rmf and Rw);
  - an SP resolution problem relative to the published bed scale;
  - no independent validation.
- SOMMARIVA DEL BOSCO 1 is **not** one of the five audited screenable wells.
  Nothing here may be used as a substitute NTG for an audited well, or as a
  Piemonte-wide value.
- **The Finding 3.1 status is unchanged: STILL BLOCKED.**

---

## 2. Evidence inventory

### 2.1 Project data

| Item | Content | Label |
| --- | --- | --- |
| Workbook, `Anagrafica` | TD 3809 m; `quota` 300 m; outcome STERILE; purpose hydrocarbons; Cuneo province | [OBS-W] |
| Workbook, `Lito-Stratigrafie` | Pleistocene 23-240; Sabbie di Asti 240-580 (Pliocene M-U); Sabbie di Asti 580-1190 (Pliocene inf.); Sartirana 1190-1560 (Messinian); "Serravalle ?" 1560-1800 (Messinian); **Serravalle 1800-3809 (Tortonian)** | [OBS-W] |
| Workbook, `Temperature` | Unstabilised BHT sets at **293.8 m (1981-04-08), 1587.3 m (1981-04-22), 2893.3 m (1981-05-22), 3793.3 m (1981-06-20)**, each with circulation and stop times; the 3793.3 m readings are 102.7-109.2 °C (measured / extrapolated) | [OBS-W] |
| Raster composite log (PDF, 2608 × 32125 px) | Tracks: cuttings, age, formation, depth, lithology column, SP, **mineralisation**, **resistivity (ILD, SFLU)**, sonic Δt, cores, environment, zones, gas, tests, casing, drilling progress | [OBS-R] |
| Pipeline status | `api.screen_well` returns `screened` at depth 3809.0 m (read-only call) | [OBS] |

### 2.2 Livani et al. (2023) dataset

| Item | Content | Label |
| --- | --- | --- |
| `WellLogAv.txt` and paper Table 4 | W143 "Sommariva Del Bosco 1": **GR = Y**, Lithology Y, Mineralization Y, Sonic Y, SP Y | [OBS-L] |
| `Well_logs_UOI/W143.txt` header and data | Columns: X, Y, TVDSS, MD, INC, AZ, Lithology, Mineralization, Sonic, SP. **There is no GR column.** | [OBS-L] |
| **Discrepancy** | The metadata claims GR; the released file has none. **This is preserved, not reconciled.** Whether GR was never digitised, was dropped at export, or the metadata is wrong is **[OPEN]**. | [OBS-L] |
| Well head | RT 307.7 m a.s.l.; X 403848, Y 4959735 (UTM 32N) | [OBS-L] |
| ReadMe | SP, sonic and GR were *"digitized manually with a variable sampling step, or by a semi-automatic method for line recognition"*, then *"resampled to a constant step of 0.5 m"*; Lithology and Mineralization *"have been created during the analysis of the available data"* | [OBS-L] |
| Paper text | Source is ViDEPI raster composite logs at 1:1000. Data were *"graphically and spatially checked to eliminate errors due to low graphical quality and distortions, scale errors, or bad positioning"*. **There is no quantified digitisation error and no mention of SP baseline, logging runs or scale normalisation.** | [OBS-L] |

### 2.3 Literature

| Claim used here | Source | Label |
| --- | --- | --- |
| SP measures the potential drop along the hole caused by current in the mud. It indicates permeability but is not an absolute measure of permeability or porosity, and it depends on formation and mud resistivity and on bed thickness. | Doll, H.G. (1949), *The S.P. Log: Theoretical Analysis and Principles of Interpretation*, Trans. AIME 179, 146-185 ([OnePetro](https://onepetro.org/TRANS/article/179/01/146/161788/The-S-P-Log-Theoretical-Analysis-and-Principles-of)) | [LIT] |
| In thin beds (quoted as < ~3 m) the measured SP does not reach the static SP (SSP) and needs a bed-thickness correction. Vsh = 1 − PSP/SSP. When Rmf < Rw the SP is "reversed" (fresh formation water). Deflection magnitude depends on the salinity contrast and on clay content. | Glover, P.W.J., *Petrophysics* lecture notes, ch. 18 "The Spontaneous Potential Log", University of Leeds ([link](https://homepages.see.leeds.ac.uk/~earpwjg/PG_EN/CD%20Contents/GGL-66565%20Petrophysics%20English/Chapter%2018.PDF)). **Taken from the search-result excerpt only: the PDF could not be retrieved (expired certificate / error page).** It must be verified against Doll (1949), Schlumberger *Log Interpretation Principles/Applications* (1989, [SLB](https://www.slb.com/resource-library/book/log-interpretation-principles-applications)) or Asquith & Krygowski, *Basic Well Log Analysis*, 2nd ed. (AAPG, 2004) before being relied on. | [LIT, unverified full text] |
| Net pay and NTG are not meaningful without the net class (net sand / net reservoir / net pay) and the cutoff basis being declared. Cutoffs should be tied to the purpose and the rock type. | Worthington, P.F. (2009), *The Quantification of Net Pay for the Estimation of Petroleum Resources*; Worthington, P.F. (2008), *The Application of Cutoffs in Integrated Reservoir Studies*. Both are abstract-level in the Elicit collection. | [LIT, abstract only] |
| **Cassinasco Formation:** litharenites deposited by high-density turbidity currents flowing ENE into the deep basin floor, sourced from the Alpine fold-thrust belt. **Serravalle Sandstones:** hybrid arenites (bioclastic lithic arkoses) of a shallow shelf in the eastern basin. The two are distinct petrofacies. | Caprara, Garzanti, Gnaccolini & Mutti, *Shelf-basin transition: sedimentology and petrology of the Serravallian of the Tertiary Piedmont Basin*, Riv. It. Paleont. Strat. 90(4), **1985**, doi:10.54103/2039-4942/13321 ([abstract](https://riviste.unimi.it/index.php/RIPS/article/view/13321)). Correction: the Elicit draft cited this as "2020", which is the digitisation year. | [LIT, abstract] |
| Cassinasco and Lequio formations are deep-sea turbidites infilling the western (Langhe) TPB, while the Serravalle Sandstones were shelf-slope deposits in the east. Lequio: Serravallian-Tortonian. | Maino et al. (2013), *Tectonics*, doi:10.1002/tect.20047 (search-result excerpt; the full text returned HTTP 403) | [LIT, excerpt] |
| Cassinasco lithofacies **CSIb = sandstone-pelite alternations in centimetric to decimetric beds**, equivalent to the "Lequio Formation" of the 1:100,000 Ceva sheet. | ResearchGate figure caption, "Dintorni di Lequio Berria" ([link](https://www.researchgate.net/figure/Dintorni-di-Lequio-Berria-Alternanze-di-arenarie-e-peliti-in-strati-da-centimetrici-a_fig3_344300070)); the primary source to acquire is the ISPRA CARG sheet notes (e.g. Foglio 194 Acqui Terme) | [LIT, secondary] |

### 2.4 Missing evidence

- **Mud and fluid data:** Rm, Rmf and mud type per logging run (normally on the
  original service-company log heading, which is not in either dataset), and Rw
  or formation-water salinity (water analyses, test recoveries).
- **SP scale for run 4.** The label on the raster is illegible (section 3.3).
- **GR** for this well. It is claimed by the metadata and absent from the file.
- **Resistivity (ILD, SFLU):** present on the raster, **not digitised** by
  Livani, and not in any project file as numbers.
- **Descriptions of core 1 and the sidewall cores.** Only symbols are on the
  raster.
- **Final well report** (AGIP 1981) with interpreted zones.
- A **declared project decision** on gross interval, net criterion and cutoff
  basis.

---

## 3. SOMMARIVA DEL BOSCO 1

### 3.1 Operator formation tops vs our workbook

The raster was depth-calibrated from its 25 m grid lines (5.958 px/m).
Formation and age boundaries were detected as ruled lines in those columns. At
the tops that both sources share, they agree with the workbook to about 1 m
(240, 580, 1560.7, 1800.9; TD 3808.5). The overall calibration residual is up to
~8.5 m. [OBS-R]

| Depth (m, raster) | Operator formation (raster) | Operator age (raster) | Workbook formation | Agreement |
| --- | --- | --- | --- | --- |
| 240-1015 | Sabbie di Asti | Pliocene medio-sup. (to 580) / inferiore | Sabbie di Asti 240-1190 | **Base differs: 1015 vs 1190** |
| 1015-1561 | **Conglomerati di Cassano Spinola** | Messinian | Sabbie di Asti (to 1190); **Sartirana** 1190-1560 | **Name and top differ** |
| 1561-1801 | **"non definita"** | Messinian | "Serravalle ?" 1560-1800 | Boundaries agree; name differs |
| 1801-1916 | Marne di Sant'Agata Fossili | Tortonian | Serravalle | **Name differs** |
| 1916-3439 | **"Lequio – Marne di Sant'Agata Fossili eq."** | Tortonian | Serravalle | **Name differs** |
| **3439-3808.5** | **Cassinasco** | Serravallian (3439-3499) / **"Serravalliano ?"** (3499-TD) | Serravalle (Tortonian) | **Name and age differ** |

**Observation [OBS-R/OBS-W]:** the workbook labels 1800-3809 m as a single unit,
"SERRAVALLE" (Tortonian). The operator log divides it into Marne di Sant'Agata
Fossili / Lequio-equivalent marls (Tortonian) over **Cassinasco** (Serravallian?).
Per [LIT] (Caprara et al. 1985; Maino et al. 2013), Cassinasco and Serravalle are
distinct formations with distinct petrofacies and settings.

**[OPEN]:** which label is correct. This document does not correct the workbook.
The discrepancy is recorded because it determines which gross interval and which
formation-specific literature apply.

### 3.2 Operator descriptions and mineralisation [OBS-R]

**Lithology descriptions in the lithology track:**

- **1800-1915:** *"fitte alternanze di argilla grigio-verde, siltoso-sabbiosa e
  di sabbia quarzosa a grana da media a finissima"* (dense alternations of
  clay and fine sand).
- **~3300-3440:** *"banchi di sabbia e arenaria quarzoso-micacea… con livelli di
  argilla grigia siltoso-sabbiosa"*.
- **3440-TD:** *"sabbia e arenaria litica, a grana medio-fine, a cemento
  argilloso-carbonatico con frequenti intercalazioni di argilla… passante a
  marna nella parte alta"*.

**Mineralisation column (operator interpretation, not measured):**

- **FW (acqua dolce)** from the top of logging down to ~1506 m, with "FW?" around
  1190-1318.
- **BW? (acqua salmastra?)** at 1531-1560.
- **SW / SW? (acqua salata)** from 1560 to TD, subdivided at interval boundaries
  (…, 3440, 3473, 3530, 3543, 3801).
- The **Cassinasco interval is marked SW/SW? throughout.**

**Cores:**

- The CAROTE column shows a **conventional core "1" at approximately
  3801-3809 m**.
- It shows open-circle symbols from ~2900 m to TD. The legend defines the circle
  as *"carote di parete"* (sidewall cores).
- **No core analyses are printed on the log.**

**Footer:** *"F.P. PERFORATORI m 3809; F.P. SCHLUMBERGER N.R."* — the logger's TD
entry reads "N.R.". Its meaning is **[OPEN]**.

### 3.3 Logging runs [OBS-R, OBS-W, OBS-L]

Three independent sources agree on **four logging runs**:

| Run | Approx. interval (m) | Raster evidence | Workbook BHT (logger TD, date) | Casing shoe (raster) |
| --- | --- | --- | --- | --- |
| 1 | 23 ("inizio registrazione m 23") – ~300 | Header at top | 293.8 m, 1981-04-08 | 302 |
| 2 | ~300 – ~1600 | Repeated header box across all tracks at ~300 m; SP restarts at a new offset | 1587.3 m, 1981-04-22 | 1602 |
| 3 | ~1600 – ~2900 | Repeated header at ~1600 m | 2893.3 m, 1981-05-22 | 2899 |
| 4 | ~2900 – ~3795 | Repeated header at ~2900 m | 3793.3 m, 1981-06-20 | — |

**Scale labels on the raster:**

- Runs 1-3 read **SP −150 … +150 mV**, **ILD/SFLU 0.2-20 Ω·m**, **DT 140-40 µs/ft**.
- **The SP scale label for run 4 is not legible.** It may read "−100 … +1?0".
  **[OPEN]**: if run 4 used a different SP scale, any digitisation that assumed
  −150 … +150 would be mis-scaled in exactly the screened interval.

**Livani's digitised SP carries the splice offsets unnormalised [OBS-L]:**

- Mean SP 15 m above vs below **302 m**: −71.2 vs +75.7 mV (**~147 mV step**).
- At **1602 m**: +30.2 vs −37.8 mV (~68 mV step).
- At **2899 m**: +1.6 vs +9.2 mV.
- There is also a +65 mV rise over **2879-2887 m**, just above that splice,
  where the raster shows the SP running into the header box.

**[INF]:** SP levels in the Livani file are therefore **not comparable across
runs**. The absolute SP value carries no lithological meaning without per-run
baselines.

### 3.4 Coverage in the candidate interval [OBS-L]

- SP is valid MD 24.0-3795.0 m, with no gaps > 0.5 m.
- Sonic is valid MD 26.5-3792.0 m, with one gap at 478.5-485.0 m.
- Sampling is 0.5 m (resampled).
- Adjacent samples are almost all distinct, consistent with interpolation rather
  than native sampling. The true vertical resolution is unknown.
- **Cassinasco (raster 3439-3808.5):** SP covers 3439-3795 (713 valid samples);
  the lowest ~13 m, which includes core 1, is unlogged in the Livani file.
  - SP p1 / p5 / p50 / p95 / p99 = −33.7 / −29.8 / −14.1 / +7.5 / +10.7 mV, a
    total p5-p95 span of ~37 mV.
  - Sonic p5 / p50 / p95 = 60.9 / 64.5 / 70.1 µs/ft.
  - Detrended SP crosses zero 35 times, a mean spacing of ~9.9 m.
- **The whole Cassinasco interval lies within run 4** (2899-3795 m), so no run
  splice falls *inside* it. [INF]
- **Livani lithology over the same depths:** "Cem. Sands" 2857-3795.5, with no
  internal subdivision. It is coarser than the operator's description. [OBS-L]

### 3.5 Candidate intervals (not a decision)

| ID | Interval | Basis | Comment |
| --- | --- | --- | --- |
| **G1** | **3439-3795 m MD** (operator Cassinasco, logged part) | Raster formation boundary; within run 4; contains the screened TD point | Excludes the unlogged 3795-3808.5 m |
| G2 | 1800-3809 m MD (workbook "Serravalle") | Workbook | Spans two operator formations and runs 3-4, including a splice |
| G3 | Operator lithology-description sub-intervals (e.g. 3440-3473, 3473-3530, …) | Raster | Operator-defined bed packages; finer than formation scale |

---

## 4. Candidate Method A — SP

SP-based shale volume / clean-sand separation.

| # | Item | Assessment |
| --- | --- | --- |
| 1 | Geological applicability | **Partly supported.** SP responds to permeable beds in a salinity-contrast setting [LIT: Doll 1949]. The operator marks the interval as salt water [OBS-R], so normal (negative) SP polarity is **indirectly supported**. The Cassinasco sandstones have argillaceous-carbonate cement and frequent clay interbeds [OBS-R]; published lithofacies include cm-dm sand-pelite alternations [LIT, secondary]. These are conditions under which SP underestimates sand content. |
| 2 | Required inputs | SP per run with a correct scale; shale baseline per run and per formation; clean-sand (SSP) end member; bed-thickness correction; Rmf and Rw at formation temperature; confirmed depth registration |
| 3 | Available | Digitised SP 3439-3795 (run 4) [OBS-L]; raster SP for visual cross-check [OBS-R]; BHT 102.7-109.2 °C at 3793.3 m [OBS-W]; qualitative SW mineralisation [OBS-R] |
| 4 | Missing | Rm and Rmf (mud data); Rw or salinity; the run-4 SP scale (illegible); a thick clean-sand reference bed to fix SSP; a GR cross-check (claimed but absent) |
| 5 | Assumptions | [ASM] single baseline valid within run 4; [ASM] Rmf/Rw contrast constant over the interval; [ASM] SSP reachable in at least one bed; [ASM] linear Vsh–PSP relation; [ASM] Livani digitisation faithful to the raster within a stated tolerance |
| 6 | Evidence status | Single baseline within run 4: **indirectly supported** (no splice inside G1), but baseline drift within a run is not excluded. Constant Rmf/Rw: **unsupported** (no fluid data). SSP reachable: **unsupported** (the published bed scale is cm-dm; the observed SP oscillation scale is ~10 m). Linear Vsh: **unsupported** (a convention, not calibrated here). Digitisation fidelity: **unsupported** (no error reported by Livani). |
| 7 | Gross interval | G1, 3439-3795 m MD, to be declared together with the depth convention of `thickness_m` (docs/net-to-gross-semantics.md) |
| 8 | Cutoff methodology | Vsh threshold on SP-derived Vsh, selected **before** looking at the resulting NTG and tied to a declared net class (`net_criterion = lithology_net_sand` at most — SP gives no porosity or permeability). Per Worthington (2008, 2009) [LIT], the cutoff should be calibrated to core or rock type, not chosen by convention. **No numerical cutoff is proposed:** none is independently justified with the available data. |
| 9 | Sensitivity | **High.** The p5-p95 SP span in G1 is only ~37 mV [OBS-L], so a few-mV shift in either end member moves a large fraction of samples across any Vsh threshold. The result depends on the baseline pick, the SSP pick, the Vsh transform and the threshold. It must be reported as a sensitivity envelope, never a point. [INF] |
| 10 | Digitisation uncertainty | Must be measured: re-read the raster SP independently at control depths and compare with Livani. Resampling to 0.5 m does not add resolution. [INF] |
| 11 | Run / scale discontinuities | G1 avoids splices. **But the run-4 SP scale is unconfirmed.** If it differs from ±150 mV, Livani's amplitudes in G1 would be mis-scaled by a constant factor. That changes Vsh only if the SSP or baseline are taken from outside run 4, or from an absolute scale. [INF] |
| 12 | Validation | Core 1 (~3801-3809 m, outside the logged SP); sidewall-core descriptions; cuttings; operator lithology descriptions; resistivity on the raster (qualitative) |
| 13 | Expected uncertainty | **Large and structurally biased.** Thin beds lead to systematic underestimation of clean sand; carbonate and clay cement plus unknown Rw/Rmf leave SSP undetermined. Not quantifiable today. [INF] |
| 14 | Audit-grade NTG? | **No**, not with current data. |
| 15 | What would convert it | (a) Rmf and Rw for run 4 at formation temperature; (b) the confirmed run-4 SP scale; (c) a digitisation check against the raster; (d) independent sand/shale calibration (core or sidewall descriptions, or GR); (e) a bed-thickness assessment showing the SP resolves the beds, or a documented thin-bed treatment; (f) a pre-registered cutoff with a sensitivity envelope |

---

## 5. Candidate Method B — SP + Sonic

| # | Item | Assessment |
| --- | --- | --- |
| 1 | Geological applicability | Sonic Δt responds to porosity, lithology, cementation and compaction. In G1 it is fast and narrow (p5-p95 60.9-70.1 µs/ft) [OBS-L]. For comparison, the sandstone matrix Δt commonly tabulated is ~51-55.5 µs/ft (Schlumberger 1989; Wyllie, Gregory & Gardner 1956, *Geophysics* 21). The measured Δt is close to matrix values, so sonic porosity would be **highly sensitive** to the matrix choice. [INF from LIT] |
| 2 | Required inputs | Sonic; matrix Δt for a lithic, carbonate-cemented sandstone; fluid Δt; a shale Δt at this depth; a compaction model (if Wyllie is used) or a Raymer-Hunt-Gardner-type transform; the SP inputs of Method A |
| 3 | Available | Digitised sonic 3439-3792 [OBS-L]; raster sonic for cross-check [OBS-R]; qualitative mineralogy from the operator (litharenite, argillaceous-carbonate cement) [OBS-R] and the literature (lithic, Alpine-derived) [LIT: Caprara et al. 1985] |
| 4 | Missing | Measured matrix and mineralogy (XRD or thin sections); core porosity for calibration; shale Δt end members; density or neutron logs (not in either dataset) |
| 5 | Assumptions | [ASM] a single matrix Δt; [ASM] shale and sand separable in Δt at 3.4-3.8 km (both compacted); [ASM] no cycle-skipping or washout artefacts in the digitised curve |
| 6 | Evidence status | Matrix Δt: **unsupported** (mixed lithic and cement mineralogy). Separability: **unsupported**. At this depth shales and cemented sands can overlap in Δt; the SP-sonic crossplot has not been shown to separate them. No-artefact: **unsupported**. |
| 7 | Gross interval | Same as Method A (G1) |
| 8 | Cutoff methodology | Sonic can support a *porosity* criterion (net reservoir: `net_criterion = porosity_only`, or `porosity_permeability` only with a permeability link, which is absent). The cutoff would have to be tied to core porosity. **No numerical porosity or Δt cutoff is proposed.** |
| 9 | Sensitivity | **High.** Near-matrix Δt means small changes in matrix Δt produce large relative porosity changes. Combining with SP multiplies the degrees of freedom. [INF] |
| 10 | Digitisation uncertainty | As Method A. Sonic features at the metre scale are at the limit of a 1:1000 raster. |
| 11 | Run / scale discontinuities | The sonic scale reads 140-40 µs/ft on runs 1-3; run 4 needs to be confirmed. Sonic is less baseline-dependent than SP. [INF] |
| 12 | Validation | Core 1 and sidewall cores, if porosity measurements exist in the final well report; otherwise none |
| 13 | Expected uncertainty | Sonic adds a partly independent variable (porosity and cementation) but **does not independently identify shale**. It can flag tight, cemented beds that SP would count as "clean". Its net contribution is to *reclassify* SP-clean beds, not to reduce the SP baseline ambiguity. [INF] |
| 14 | Audit-grade NTG? | **No.** Sonic is usable only as **supporting evidence** today, not quantitatively. |
| 15 | What would convert it | Core or sidewall porosity to calibrate the Δt transform; mineralogy; a density or neutron log (would need the original log prints); plus everything in Method A item 15 |

---

## 6. Candidate Method C — Formation-specific

| # | Item | Assessment |
| --- | --- | --- |
| 1 | Geological applicability | Literature for the **operator-assigned formation (Cassinasco)** exists at facies and petrography level: high-density turbidite litharenites [LIT: Caprara et al. 1985]; deep-basin (Langhe) turbidites [LIT: Maino et al. 2013, excerpt]; outcrop lithofacies with cm-dm sand-pelite alternations [LIT, secondary]. **No published subsurface NTG, net-sand or cutoff methodology for Cassinasco, Lequio or Serravalle was found** (Elicit searches 3, 8, 9 and 10 in the companion document; the Tertiary Piedmont Basin search in this session). If the workbook label "Serravalle" were correct instead, the applicable facies literature would be different (shelf hybrid arenites) [LIT]. |
| 2 | Required inputs | A formation-specific sand/shale discrimination calibrated in *this* formation (outcrop bed statistics, core, or regional well studies) and a demonstrated transfer to the subsurface at ~3.4-3.8 km |
| 3 | Available | Well-specific qualitative inputs that *are* formation-specific: the operator's lithology descriptions, the cuttings track, core and sidewall-core positions [OBS-R]. Published outcrop facies descriptions (qualitative) [LIT]. |
| 4 | Missing | Any quantitative bed-thickness statistics or sand fraction for Cassinasco; the CARG sheet notes (primary); the description of core 1; the formation assignment itself (section 3.1 [OPEN]) |
| 5 | Assumptions | [ASM] the operator's formation assignment is correct; [ASM] outcrop facies proportions apply at 3.4-3.8 km depth, 20-60 km from outcrop; [ASM] the cuttings percentages represent in-situ proportions |
| 6 | Evidence status | Formation assignment: **directly evidenced** on the operator log, but **contradicted** by the workbook label. Outcrop transfer: **unsupported** (this would be an analogue, which the brief prohibits as a substitute). Cuttings representativeness: **unsupported** (caving and lag mixing). |
| 7 | Gross interval | G1, **conditional** on resolving the formation assignment |
| 8 | Cutoff methodology | None exists in the formation literature found. A formation-specific method could only *constrain* Method A or B (e.g. expected bed-thickness distribution for a thin-bed correction). It does not replace them. **No cutoff is proposed.** |
| 9 | Sensitivity | Dominated by the formation assignment (Cassinasco vs Serravalle facies models differ fundamentally) and by the analogue transfer |
| 10 | Digitisation uncertainty | Not applicable to literature inputs. It applies to any use of the raster cuttings track. |
| 11 | Run / scale discontinuities | Not applicable |
| 12 | Validation | Core 1 and sidewall-core descriptions from the final well report; CARG outcrop logs |
| 13 | Expected uncertainty | Not quantifiable; outcrop-to-subsurface transfer is the dominant term |
| 14 | Audit-grade NTG? | **No.** On its own it would amount to an analogue NTG, which is prohibited. |
| 15 | What would convert it | A published or measured bed-thickness or sand-fraction dataset *for Cassinasco* (primary: the CARG notes), the core 1 description, and resolution of the formation assignment. It would still serve only as a constraint on Method A or B. |

---

## 7. Method comparison

Not ranked.

| Dimension | A — SP | B — SP + sonic | C — Formation-specific |
| --- | --- | --- | --- |
| Geological applicability | Partly supported (saline water per operator; thin beds against it) | Partly supported (porosity information; shale separation undemonstrated) | Facies-level only; depends on an unresolved formation assignment |
| Data available now | SP (run 4) digitised; raster for checking | SP + sonic digitised | Qualitative operator descriptions and outcrop facies |
| Critical missing evidence | Rmf and Rw; run-4 SP scale; SSP reference; calibration | As A, plus matrix, core porosity, density/neutron | Quantitative formation data; core description; formation assignment |
| Key assumptions | Baseline, SSP, linear Vsh, bed resolution | As A, plus matrix Δt and Δt shale/sand separability | Outcrop transfer; label correctness |
| Assumptions evidenced? | Mostly unsupported; single-run baseline indirectly supported | Mostly unsupported | Assignment evidenced but contradicted; transfer unsupported |
| Net class obtainable | At most net sand (lithology) | Net reservoir (porosity) with calibration | Constraint only |
| Uncertainty character | Large; biased low for sand in thin beds | Large; reclassifies tight beds | Unquantifiable |
| Validation route | Cores / sidewall cores / cuttings; GR if found | Core porosity | Core 1; CARG outcrop data |
| Audit-grade today | No | No | No |

---

## 8. Remaining blockers

These prevent an audit-grade NTG number today:

1. **Formation assignment conflict.** Workbook "Serravalle (Tortonian)" vs
   operator "Cassinasco (Serravallian?)" at the screened depth [OBS-W vs OBS-R].
2. **No gross-interval decision** consistent with the `thickness_m` definition
   and its depth convention.
3. **No Rmf or Rw.** SP polarity and magnitude rest on the operator's
   qualitative "SW" alone.
4. **Run-4 SP scale unconfirmed.** The label is illegible; Livani does not
   document per-run scales.
5. **Resolution mismatch.** Published Cassinasco lithofacies include cm-dm beds,
   and SP does not reach SSP in thin beds [LIT]. There is no thin-bed treatment
   and no bed-thickness data.
6. **GR absent.** The metadata claims it but the file lacks it. There is no
   independent shale indicator.
7. **Digitisation fidelity unquantified.** Livani reports no error, and no
   independent re-read has been done.
8. **No calibration or validation data.** Core 1 and the sidewall cores exist
   on the log, but their descriptions and analyses are not in hand.
9. **No pre-registered net criterion or cutoff.**
10. **Scope.** The well is not one of the five audited wells. Any NTG derived
    here cannot be transferred to them.

---

## 9. Decision gate

All of the following must hold **before** any NTG calculation is run. Each is
checkable.

| Gate | Criterion | Pass evidence |
| --- | --- | --- |
| D1 | Formation assignment at the screened depth resolved | A written reconciliation of workbook vs operator log, citing the final well report or ViDEPI |
| D2 | Gross interval declared | Top, base and depth convention (MD from RT) documented, and consistent with how `thickness_m` would be derived for this well |
| D3 | Net class declared | One `net_criterion` value (docs/net-to-gross-semantics.md) and the reason SP / sonic can support it |
| D4 | Run structure and scales confirmed | SP and sonic scale for every run intersecting the gross interval, read from the raster or original prints, including run 4 |
| D5 | Fluid data | Rmf (with temperature) and Rw or salinity for the gross interval from a documented source; SP polarity shown to be normal |
| D6 | Digitisation check | Independent re-read of the raster SP (and sonic, if used) at ≥ 20 control depths in the gross interval, with a stated tolerance met by the Livani values |
| D7 | Resolution adequacy | Evidence that the bed thickness in the gross interval is resolvable, or a documented thin-bed method with its bias stated |
| D8 | Calibration target | At least one independent lithology or porosity constraint in the interval (core 1 or sidewall-core description or analysis, or GR) |
| D9 | Pre-registration | Baseline method, end-member method, Vsh transform, cutoff basis and sensitivity range fixed in writing **before** computing, and reported as an envelope |
| D10 | Scope statement | Explicit statement that the result applies to SOMMARIVA DEL BOSCO 1 only, is not an audited-well NTG, and does not change Finding 3.1 by itself |

If D1-D9 cannot all be passed, **no NTG is to be computed.**

---

## 10. Recommendation for next research step

This is evidence acquisition only; no NTG is implemented.

**Obtain the final well report and original log headings for SOMMARIVA DEL
BOSCO 1** (AGIP, 1981; permit "Area ENI"; well code 04254 per the raster
header) from ViDEPI or the UNMIG archive. The target items are:

- mud data (Rm, Rmf, mud type) for each of the four runs;
- the SP scale of run 4;
- the core 1 and sidewall-core descriptions and analyses;
- any water analyses or test recoveries;
- the operator's formation tops.

Together these address gates D1, D4, D5 and D8. D6 (the digitisation check) can
be done from the raster already in `data/PDF/`, but it is only worth doing once
D5 is shown to be passable.

---

## Scope and integrity checks

- **No NTG value**, net fraction, net thickness or numerical cutoff appears in
  this document.
- The statistics shown are descriptive SP / sonic percentiles, splice offsets and
  an oscillation length scale. None is a net estimate.
- **Not modified:** production code, screening inputs, priors, Monte Carlo,
  `combined_factor`, audit documents and numbers.
- Finding 4.1 was not started; P_atm was not introduced.
- The workbook formation-label discrepancy is **recorded, not corrected**.
- The Livani GR discrepancy is **recorded, not reconciled**.
- Raster reading, depth calibration and all derived images and scripts live in
  the session scratchpad, outside the repository.
