# Finding 3.1 — SALUZZO 1 — 1987 AGIP Evidence

**Read-only evidence audit, 2026-09-23.**

- No NTG value or estimate, no SP cutoff, no Vsh.
- No change to the model, code, tests, data or audit numbers.
- Uncommitted draft.

**Labels used throughout:**

| Label | Meaning |
| --- | --- |
| **OBSERVED** | Seen on the sheet image |
| **DOCUMENTED** | Stated in text by the source |
| **INFERRED** | This audit's reading or interpretation |
| **UNKNOWN** | Not determinable from the evidence |

---

## 1. Objective

Determine whether the 1987 AGIP/UNMIG well sheet for SALUZZO 1 contains
well-specific evidence that could support a future NTG reconstruction for the
**audited** well SALUZZO|1. No other well was examined.

---

## 2. Source identification

| Item | Value |
| --- | --- |
| Document | *Inventario delle risorse geotermiche nazionali — Regione Piemonte*, **Allegato A: "Schede sorgenti" / "Schede pozzi (con profilo semplificato fino a base acque dolci)"** |
| Issuing bodies | Ministero dell'Industria, del Commercio e dell'Artigianato; Legge 9 dicembre 1986 n. 896; CNR - ENEA - ENEL - ENI/AGIP (cover logo AGIP) |
| Date | Dicembre 1987 |
| File used | `r_piemonte_a1.pdf` (58 pp.) from `https://unmig.mase.gov.it/wp-content/uploads/2020/01/r_piemonte_a1.pdf`. This is the copy retrieved in the previous task, in the session scratchpad (MD5 `8d34535d9d170fcd03e14c97ee24c7dd`). |
| **Sheet location** | The well-sheet index (PDF p. 21) lists *"SCARNAFIGI – CUNEO – SALUZZO 1 – pagina 41"*. Index page numbers are offset by 15 from PDF pages (Borgo d'Ale 1: index p. 7 = PDF p. 22). **SALUZZO 1 = PDF page 56**, a single sheet. Its native image is 2400 × 3376 px. |
| Legend / method pages | PDF pp. 18-19 (introduction "II"-"III"), plus the legend printed on the sheet itself |
| Type | Primary operator compilation. The curves are a **"profilo semplificato"** (simplified profile), not original log prints. **DOCUMENTED** in the section title. |

---

## 3. Well identity

| Attribute | 1987 sheet (PDF p. 56) | Project workbook `Anagrafica` | `data/pozzi-storici.csv` | Status |
| --- | --- | --- | --- | --- |
| Name | "Pozzo: SALUZZO 1 (1957)" | SALUZZO 1 (canonical `SALUZZO\|1`) | SALUZZO 001 | Match |
| Comune / province | SCARNAFIGI (CUNEO) | SCARNAFIGI / CUNEO | CN | Match |
| IGM sheet | F° 68 III S.O. | — | — | — |
| Latitude | 44° 40' 06",5 | 444007 (44°40'07") | 44°40'05,20" | Sheet ≈ workbook; csv differs by ~1-2" |
| Longitude | 4° 54' 36" W of Monte Mario | 45436.28 (4°54'36.28") | 04°54'31,60" W | Sheet ≈ workbook; **csv differs by ~4.7"** (~100 m). **Preserved, not reconciled.** |
| Ground elevation | "Quota del piano campagna: + m 310" | quota 310 | — | Match |
| Year | 1957 | datacomp 00/06/1957 | 1957 | Match |
| Operator | not printed on the sheet | AGIP | AGIP | — |
| Well code | not printed | — | UNMIG code 5938 | — |
| TD | **not printed** (the sheet ends near 500 m) | **1527.5** | **1531** | **Conflict between project sources, already recorded by the pipeline** (see section 10) |
| Rotary-table elevation | not printed | — | — | UNKNOWN |

**Ambiguity check:**

- SALUZZO 2 is a distinct well: Comune RUFFIA, quota 279, TD 2509.15 (workbook),
  1957, on sheet PDF pp. 42-44.
- No other "Saluzzo" variant exists in the index.
- **Identity resolved: the sheet is the project's SALUZZO|1.** [OBSERVED +
  DOCUMENTED]

---

## 4. Data inventory

| # | Data type | Status | Evidence |
| --- | --- | --- | --- |
| A | SP | **AVAILABLE** (simplified redraw) | Track "POTENZIALE SPONTANEO", annotated "PS = 100 millivolt" at the top and "PS = 150 millivolt" at ~250 m [OBSERVED] |
| B | Resistivity | **AVAILABLE** (simplified redraw) | Track "RESISTIVITÀ — PN-GN 0-200 Ω m2/m", two curves (solid and dotted) [OBSERVED] |
| C | GR | NOT AVAILABLE | No GR track |
| D | Sonic | NOT AVAILABLE | — |
| E | Density | NOT AVAILABLE | — |
| F | Neutron | NOT AVAILABLE | — |
| G | Caliper | NOT AVAILABLE | — |
| H | Lithology | **AVAILABLE** (interpreted) | Lithology column with legend *Ciottoli e ghiaia, Sabbia, Argilla, Argilla sabbiosa, Torba* [OBSERVED]. Reconstructed from cuttings plus log interpretation [DOCUMENTED, p. II] |
| I | Formation tops | **UNCLEAR**: age units only, no formation names | Age column: ALLUVIONE / PLIOCENE INFERIORE / NON DATABILE [OBSERVED] |
| J | Water classification | **AVAILABLE** (interpreted) | Legend "FLUIDI IN STRATO: Acqua dolce / Acqua salmastra / Acqua salata" shown as lithology-column overlays [OBSERVED]; method on pp. II-III [DOCUMENTED] |
| K | Temperature | NOT AVAILABLE on this sheet | — |
| L | Core information | NOT AVAILABLE | None shown. The introduction says cores are taken *"soltanto eccezionalmente"* [DOCUMENTED, p. II] |
| M | Drilling / mud information | NOT AVAILABLE | — |
| N | Permeability / porosity | Permeability **AVAILABLE as qualitative classes** only (*Buona / Discreta / Nulla*); porosity NOT AVAILABLE | Right-hand column with depth labels [OBSERVED]. *"La valutazione è soltanto indicativa perchè ricavata dalla analisi dei cuttings"* [DOCUMENTED, p. II] |
| O | Explicit net reservoir / net pay statement | **NOT AVAILABLE** | None on the sheet or in the introduction |
| — | Evaluation-quality flags | AVAILABLE | Legend "ELEMENTI DI VALUTAZIONE: Mancanti / Insufficienti / Incerti ( ? )". "?" is used below 423 m in the permeability column [OBSERVED] |

---

## 5. Depth coverage

| Parameter | Value on the 1987 sheet | Label |
| --- | --- | --- |
| Depth reference | *"Le profondità sono riferite al piano campagna"* (ground level, +310 m) | DOCUMENTED |
| Top of profile | ~0 m. The resistivity curve starts around ~20 m. | OBSERVED |
| **Bottom of profile** | **~500 m** (last depth label "500"; the sheet frame ends just below it) | OBSERVED |
| TD | Not shown | — |
| Base of fresh water | **~423 m** — the "acqua salmastra" overlay starts in the gravel unit below ~423 m | OBSERVED (pattern match to legend = INFERRED) |
| Age boundaries | ALLUVIONE 0 to ~172 m; PLIOCENE INFERIORE ~172 to ~400-410 m; NON DATABILE ~400-410 to ≥ 500 m | OBSERVED; depths read visually against ticks, ±~5 m |
| Permeability-class boundaries | 22, 29, 48, 57, 96, 102, 122, 154, 168, 295, 322, 354, 364, 375, 423 m; "?" (uncertain) below 423 | OBSERVED (printed labels) |
| SP annotation change | "PS = 100 millivolt" → "PS = 150 millivolt" at ~250 m | OBSERVED |

**Comparison with the project:**

| Parameter | Project value | 1987 sheet value | Match status |
| --- | --- | --- | --- |
| Screening depth (state point) | **1527.5 m** (`depth_m`, workbook `profondità`) | Not covered (sheet ends ~500 m) | **NOT COVERED** |
| Lithology interval containing TD | 422.8-1527.5 m `CIOTTOLI E SABBIE` (MIOCENE) | Only ~423-500 m shown, as gravel with brackish overlay, age "NON DATABILE" | **~77 m of 1104.7 m shown (~7 %); the lower ~1027 m is absent** |
| Upper units | QUATERNARIO 0-176.8; PLIOCENE 176.8-422.8 | ALLUVIONE 0 to ~172; PLIOCENE INFERIORE ~172 to ~400-410; NON DATABILE below | Depths approximately consistent; **age name differs** (MIOCENE vs NON DATABILE). **Preserved.** |
| Depth datum | `DepthDatum.UNKNOWN` (pipeline) | Ground level (documented) | **Different reference status; not corrected** |
| TD | 1527.5 (workbook) vs 1531 (pozzi-storici) | not shown | Project-internal conflict, already flagged by the pipeline |

---

## 6. SP evidence

| Question | Answer | Label |
| --- | --- | --- |
| SP present? | Yes, as a simplified redrawn curve, ~20 to ~500 m | OBSERVED |
| Scale | Annotation "PS = 100 millivolt" (upper part) and "PS = 150 millivolt" (from ~250 m). Most plausibly the millivolt span of the track width; **the document does not define it.** | OBSERVED / INFERRED |
| Scale readable? | The annotation is readable. **No zero, no baseline value, no graduated axis.** | OBSERVED |
| Polarity defined? | **No** | OBSERVED (absent) |
| Run boundaries identified? | **No** run information | OBSERVED (absent) |
| Baseline shifts? | The curve shifts position markedly around ~230-250 m, coinciding with the scale annotation change. Whether this is lithology, a new run, or re-scaling is **UNKNOWN**. | OBSERVED / UNKNOWN |
| Continuous? | Visually continuous over the plotted interval | OBSERVED |
| Qualitative or quantitatively digitisable? | **Qualitative.** The operator states for this upper section: *"i tipi di log che vengono registrati in questo tratto non consentono determinazioni numeriche"* (p. II). The curve is a simplified redraw. | DOCUMENTED |
| Graphical resolution | ~500 m over ~2300 native pixels (~4.6 px/m), redrawn. The original resolution is unknown. | OBSERVED / INFERRED |
| Different SP scales at different depths? | **Yes**: 100 mV and 150 mV annotations | OBSERVED |

**Could this SP support a future quantitative methodology for SALUZZO|1?**

- **No, for the screened interval:** it does not reach it.
- **Not as it stands, even for 0-500 m:** it is simplified, has no zero,
  polarity or run data, changes scale mid-sheet, and the operator itself
  disclaims numerical use.

---

## 7. Resistivity evidence

| Question | Answer | Label |
| --- | --- | --- |
| Curves present | Two curves, one solid and one dotted, under the heading "PN-GN" | OBSERVED |
| Curve names | "PN-GN". **Not defined in the document.** Reading them as short and long normal is conventional but not stated here. | OBSERVED / UNKNOWN |
| Scale | "0-200 Ω m2/m" | OBSERVED |
| Depth coverage | ~20 to ~500 m | OBSERVED |
| Readable for quantitative use? | **No**: simplified redraw, no grid values | OBSERVED / DOCUMENTED (p. II disclaimer) |
| Rm / Rmf / Rw given? | **No** | OBSERVED (absent) |
| Nature | Qualitative profile. It is the basis of the operator's water classes (section 9). | DOCUMENTED |

---

## 8. Lithology and formation evidence

**Operator legend terms, exactly as printed:**

- *Ciottoli e ghiaia*
- *Sabbia*
- *Argilla*
- *Argilla sabbiosa*
- *Torba*

**No formation names are printed.** The age column reads:

- *ALLUVIONE*
- *PLIOCENE INFERIORE*
- *NON DATABILE*

**Lithology column, 0-500 m [OBSERVED]:**

- ~0-160 m: interbedded gravel/pebbles, sand and clay.
- ~165-~375 m: mainly sand with peat (torba) symbols, and some clayey and
  gravelly levels.
- ~375 to ~423 m: clay / sandy clay.
- ~423 to ≥ 500 m: *ciottoli e ghiaia* with the brackish-water overlay.

**Workbook `Lito-Stratigrafie` for SALUZZO 1:**

- 0-176.8 `SABBIE,CIOTTOLI,ARGILLE` (QUATERNARIO)
- 176.8-422.8 `ARGILLE,SABBIE,CIOTTOLI` (PLIOCENE)
- 422.8-1527.5 `CIOTTOLI E SABBIE` (MIOCENE)

**Assessment for the audited interval:**

- Only its top ~77 m (~423-500 m) is described on the sheet. That part is
  **gravel-dominated** [OBSERVED].
- The lithology of the remaining ~1027 m down to TD is **UNKNOWN** from this
  source.
- No part is labelled net reservoir by the source.

---

## 9. Water-classification evidence

Definitions, from Allegato A pp. II-III [DOCUMENTED, quoted]:

- *"Non prelevandosi in genere campioni di fluidi mancano analisi chimiche delle
  acque. Tuttavia i logs elettrici consentono determinazioni sufficienti per una
  attendibile classificazione delle acque in: acque dolci, acque salmastre,
  acque salate."*
- **Acque dolci:** clean sands with *"valori di resistività uguali o superiori a
  20 ohm m2/m"*, normally *"non oltre 1 g/l"*.
- **Acque salmastre:** a transition zone; *"convenzionalmente … da 1 a 25 gr/l"*;
  resistivity decreasing with salinity.
- **Acque salate:** *"fino a 250 gr/l"*; very low resistivity.
- *"non può essere indicato con precisione il tenore salino."*

**Classification of the evidence:**

- The classes are **interpretations derived from electric logs.**
- They are **not** laboratory analyses and **not** measured formation-water
  properties.
- They are **not Rw.** No Rw or salinity value is inferred here.

**On this sheet [OBSERVED]:**

- The fresh-water class applies above ~423 m (inferred from the overlay; the
  fine fresh-water stipple is hard to separate from the sand symbol).
- *Acqua salmastra* applies from ~423 m to the sheet's end.
- Below ~500 m: **UNKNOWN**.

---

## 10. Cross-check with project screening interval

**Project reference, read-only:**

- `api.screen_well("SALUZZO|1", …)` returns `screened` at **depth_m = 1527.5**.
- The depth provenance is the workbook `Anagrafica`, row 30.
- The pipeline records the conflict *"sources disagree on total depth"* (1527.5
  vs 1531 from `pozzi-storici.csv`).
- `depth_datum = UNKNOWN`.
- Temperature is *"45.0 degC at 1522.6 m (extrapolated_squarci_taffi)"*.
- Nothing was changed.

| Question | Answer |
| --- | --- |
| 1. Does the sheet cover the entire screened interval? | **No.** It ends at ~500 m; the screening depth is 1527.5 m. |
| 2. SP across the entire interval? | **No** (~423-500 m only) |
| 3. Resistivity across the entire interval? | **No** (~423-500 m only) |
| 4. Lithology across the entire interval? | **No** (~423-500 m only) |
| 5. Gaps? | ~500-1527.5 m entirely absent (~1027 m) |
| 6. Depth references consistent? | **Not established.** The sheet is ground-level; the project datum is UNKNOWN; project TD sources disagree by 3.5 m. |
| 7. Formation names consistent? | No formation names on the sheet. Age of the deepest unit: "NON DATABILE" (sheet) vs "MIOCENE" (workbook). **Preserved.** |

---

## 11. Decision gates D1–D10

| Gate | Status | Evidence | Limitation |
| --- | --- | --- | --- |
| D1 — Correct well identity | **PASS** | Comune, province, coordinates (sheet vs workbook), ground elevation 310 m and year 1957 agree; SALUZZO 2 is distinct | `pozzi-storici.csv` coordinates (~4.7" in longitude) and TD (1531) differ from the workbook; preserved |
| D2 — Full screened-interval coverage | **FAIL** | Sheet ends ~500 m; screening depth 1527.5 m | ~93 % of the TD lithology interval is absent |
| D3 — Defensible depth reference | **PARTIAL** | The sheet states ground-level reference explicitly | Project datum is UNKNOWN; TD conflict 1527.5 vs 1531 |
| D4 — Quantitatively interpretable SP | **FAIL** | Simplified redraw; no zero or polarity; 100 → 150 mV annotation change; operator: logs here *"non consentono determinazioni numeriche"* | It also does not reach the screened depth |
| D5 — Defensible SP baseline / end members | **FAIL** | No baseline value, run data or scale definition | — |
| D6 — Formation-water / Rw evidence | **FAIL** | Only log-derived water classes; the document states that no chemical analyses exist | Classes are conventional ranges, not Rw |
| D7 — Independent lithological validation | **FAIL** | Lithology comes from cuttings plus log interpretation; no cores shown | Not independent of the logs |
| D8 — Independent validation of net fraction | **FAIL** | No net / net-pay statement; permeability classes are *"soltanto indicativa"* from cuttings | — |
| D9 — Resolution for the relevant bed scale | **UNKNOWN** | Bed scale in the screened interval is unknown; the sheet is a redraw at ~4.6 px/m | Moot given D2 |
| D10 — Reproducible methodology | **FAIL** | No documented quantitative method on or for this sheet | — |

No gate is marked PASS on the basis of "not found".

---

## 12. Quantitative NTG feasibility

> ### STILL BLOCKED

- The sheet is a genuine, correctly identified primary record for the audited
  well.
- It stops at ~500 m, ~1027 m above the depth at which SALUZZO|1 is screened.
- Its logs are simplified redraws that the operator itself says do not support
  numerical determinations.
- It carries no Rw, no cores and no net statement.

**Finding 3.1 does not change status.**

---

## 13. Remaining evidence requirements

Only what is necessary, given this evidence:

1. **A log record that covers ~423-1527.5 m (or ~1531 m)**, i.e. the actual
   screened interval. This is the first requirement; nothing else matters
   without it.
   - The project already holds `data/PDF/saluzzo_001.pdf` (ViDEPI composite
     profile, raster). The baseline review recorded it as a single-page scan with
     no text layer.
   - Whether it covers the full depth with SP and resistivity was **not examined
     in this task** (out of scope). It is the obvious next source to inspect.
2. **Depth reference** of that record, reconciled against the project's
   `depth_m` and the 1527.5 / 1531 TD conflict.
3. **Log-heading data** for the relevant runs: SP scale and zero, Rm, Rmf and
   temperature.
4. **Rw or formation-water salinity** for the screened interval. Log-derived
   FW/BW/SW classes do not suffice.
5. **Independent lithology or net calibration** (core, sidewall cores or test
   data), if any exists for this 1957 well.

---

## 14. Conclusion

The 1987 AGIP/UNMIG sheet (Allegato A, PDF p. 56) is the correct SALUZZO 1 record.

**What it contains, down to ~500 m below ground:**

- a simplified SP and PN-GN resistivity profile;
- an interpreted lithology column;
- qualitative permeability classes;
- log-derived water classes, with the fresh-water base at ~423 m.

**Why it doesn't help:**

- The audited well is screened at 1527.5 m, so the sheet covers only the top
  ~7 % of the TD lithology interval.
- The operator explicitly disclaims numerical use of these logs.
- It provides no Rw, no cores and no net statement.

**Result:** decision gates D2 and D4-D8 and D10 fail, D9 is unknown, D3 is partial,
and only D1 passes. **Finding 3.1 remains STILL BLOCKED for SALUZZO|1.** The next
evidence source is a full-depth log for this well; the ViDEPI composite already in
`data/PDF/` is the candidate, pending a separate task.
