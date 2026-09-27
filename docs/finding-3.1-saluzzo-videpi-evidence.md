# Finding 3.1 — SALUZZO 1 — ViDEPI Composite Log Evidence

**Read-only evidence audit, 2026-09-24.**

- No NTG value or estimate, no SP cutoff, no Vsh.
- No change to model, code, tests, data files or audit numbers.
- Uncommitted draft.

Companion to `docs/finding-3.1-saluzzo-1987-evidence.md`, whose conclusion was
that the 1987 sheet stops at ~500 m.

**Labels used throughout:**

| Label | Meaning |
| --- | --- |
| **OBSERVED** | Seen on the image |
| **DOCUMENTED** | Printed as text or a value by the source |
| **INFERRED** | This audit's reading or arithmetic |
| **UNKNOWN** | Not determinable from the evidence |

---

## 1. Objective

Determine whether the ViDEPI composite log for SALUZZO 1 provides well-specific
evidence that could support a future NTG reconstruction for the **audited** well
SALUZZO|1. It was checked against the decision gates D1-D10 used in the 1987-sheet
audit. No other well was examined.

---

## 2. Source identification

| Item | Value |
| --- | --- |
| File | `data/PDF/saluzzo_001.pdf` (project data, read-only). 506,756 B, MD5 `3e935a0fe27730c31750c6f1b8105f34` |
| Provenance | `data/data.txt` line 1900 → `https://www.videpi.com/deposito/pozzi/profili/pdf/saluzzo_001.pdf`. The ViDEPI copy is the same size (506,756 B; Last-Modified 2018-12-10). |
| ViDEPI well record | `dettaglio.asp?cod=5938`: SALUZZO 001, code 5938, exploratory, 1957, 1.531 m, "Sterile", AGIP, profile id 3253 |
| Format | One PDF page containing one raster image (3544 × 24157 px, grayscale), **no text layer**. Read visually. |
| Content | (a) AGIP **"Profilo del pozzo — SALUZZO 1"** composite log, scale 1:1000. (b) Below it, an AGIP **tabulated well-data printout**: casing, cementation, verticality, cuttings, cores, sidewall cores, mud, losses, shows, logging operations, plugs, tests, analyses, and mining/geological results. |
| Authorship / date | AGEO-SECR; compiler and reviewer C. De Col; *"Aggiornato al 26.11.91"*. The printout says *"Stratigrafia aggiornata al settembre 91 da STIG. Interpretazione sismica aggiornata al settembre 91 da ELAB - PETR."* |
| Type | Primary operator document: a 1991 compilation of 1957 well data |
| Depth calibration used for this audit | 25 m grid lines at 200 px (7.995 px/m), 100 m at y ≈ 3493; max residual ~5 m. Core boxes on the composite fall within ~0.5 m of the printout core depths (section 8). |

---

## 3. Well identity

| Attribute | Composite / printout | ViDEPI / `pozzi-storici.csv` | Workbook (`Anagrafica`) | 1987 sheet | Status |
| --- | --- | --- | --- | --- | --- |
| Name | "SALUZZO 1" | SALUZZO 001 | SALUZZO 1 | SALUZZO 1 | Match |
| AGIP well code | **01547** ("Cod. pozzo") | UNMIG code 5938 | — | — | — |
| Comune | **SALUZZO (CN)** | — | SCARNAFIGI | SCARNAFIGI | **Differs. Preserved.** |
| Coordinates | E004° 54' 31.6", N44° 40' 05.2" (also TD location); plane E 1,384,543 / N 4,947,203 | 04°54'31,60" W, 44°40'05,20" | 4°54'36.28", 44°40'07" | 4°54'36", 44°40'06.5" | Composite = ViDEPI; workbook ≈ 1987 sheet. **~4.6" longitude difference between the two groups. Preserved.** |
| IGM | Foglio 68, Tav. III SO | — | — | F° 68 III S.O. | Match |
| Operator / titolare | AGIP MINERARIA, 100 % | AGIP | AGIP | — | Match |
| Permit | "AREA ENI" | — | — | — | — |
| Rig / contractor | MASSARENTI R 6 C / AGIP MINERARIA | — | — | — | — |
| Spud / TD reached / rig released | 11-04-57 / 20-06-57 / 20-06-57 | 1957 | 00/06/1957 | 1957 | Match |
| Outcome / status | STERILE / TAPPATO E ABBANDONATO | Sterile | STERILE | — | Match |
| **TD** | **"Profondità totale m. 1530.7"** (RT-referenced; see section 5) | 1531 | 1527.5 | not shown | See section 5 |
| **Elevations** | **Tavola rotary 313.20; prima flangia 309.00; piano campagna 310.00** m a.s.l. | — | quota 310 | ground +310 | Ground: match |

**Ambiguity check.** SALUZZO 2 is a separate well: Ruffia, TD 2509.15 / 2515, and
a different file (`saluzzo_002.pdf`). **Identity resolved: the composite is the
project's SALUZZO|1.**

---

## 4. Data inventory

| # | Data type | Status | Evidence |
| --- | --- | --- | --- |
| A | SP | **AVAILABLE** (raster) | Track "POTENZIALE SPONTANEO (mV)", header "SP 0 … MV 150" [OBSERVED] |
| B | Resistivity | **AVAILABLE** (raster) | Track "RESISTIVITÀ (Ohms m2/m)", headers **"LN 0.2 … OHMM 20"** and **"SN 0.2 … 20"** [OBSERVED]. A third dashed trace near the right edge of the track is **UNCLEAR** (not identified in any header). |
| C | GR | NOT AVAILABLE | No GR track or heading |
| D | Sonic | **NOT AVAILABLE**: the track exists but is empty | "SONIC Δt (µsec/ft)" column holds grid only [OBSERVED] |
| E-G | Density, neutron, caliper | NOT AVAILABLE | — |
| H | Lithology | **AVAILABLE** (interpreted) | Lithology column plus description track [OBSERVED]; cuttings every 10 m (4.2-222 m) and every 5 m (222-1530.7 m), "Lavati" [DOCUMENTED] |
| I | Formation tops | **AVAILABLE** | Age and formation columns (section 8) [OBSERVED] |
| J | Water classification | **AVAILABLE** (interpreted, query-marked) | "MINERALIZZ. MANIFEST." column: FW / FW? / SW? (section 9) [OBSERVED] |
| K | Temperature | **"TEMPERATURE DAI LOGS: NESSUNA"** | [DOCUMENTED] (section 5 notes a workbook discrepancy) |
| L | Cores | **AVAILABLE: 10 conventional cores**; sidewall cores "NESSUNA" | [DOCUMENTED] (section 8) |
| M | Drilling / mud | **Partly AVAILABLE**: mud type code and density by interval; **"Cloruri" column blank** | [DOCUMENTED] |
| N | Porosity / permeability | **NOT AVAILABLE.** The core record fields *"Porosità min. …… max ……; Permeabilità da …… md a …… md"* are left blank for all 10 cores. | [DOCUMENTED] |
| O | Net reservoir / net pay statement | **NOT AVAILABLE** | — |
| — | Tests / analyses | "PROVE DI STRATO: NESSUNA"; "PROVE DI PRODUZIONE: NESSUNA"; "WIRELINE FORMATION TESTS: NESSUNO"; "ANALISI: NESSUNA"; "MANIFESTAZIONI DI INTERESSE MINERARIO: NESSUNA" | [DOCUMENTED] |
| — | Logging operations | ES / SP / TEMP runs, depths, dates, contractor (section 6) | [DOCUMENTED] |

---

## 5. Depth coverage

**Depth reference [DOCUMENTED]:**

- Printout: *"Tutte le profondità sono in metri e riferite al P.T.R."* (rotary
  table).
- Header: RT 313.20 m, ground 310.00 m, so the **RT height above ground = 3.20 m**.
- **INFERRED:** the composite depth track is RT-referenced too. All ten core boxes
  sit within ~0.5 m of the printout core depths.

**Logged interval [DOCUMENTED]:**

| Run | Curves | Top (m RT) | Bottom (m RT) | Date | Contractor |
| --- | --- | --- | --- | --- | --- |
| 1 | ES, SP | 25.0 | 258.5 | not printed | Schlumberger |
| — | TEMP (cement check) | 4.2 | 251.0 | not printed | Schlumberger |
| 2 | ES, SP | 256.0 | **1525.8** | **19/06/57** | Schlumberger |

TD is 1530.7 m RT (*"F.P. PERFORATORI m 1530.7"*). The logger's TD entry reads
*"F.P. SCHLUMBERGER N.R."* [OBSERVED]. **The bottom ~4.9 m (1525.8-1530.7 RT) is
unlogged.**

**Depth comparison.** INFERRED arithmetic; nothing is corrected.

| Parameter | Project value | Composite / printout value | Match status |
| --- | --- | --- | --- |
| Screening depth / TD | **1527.5** (`depth_m`, datum UNKNOWN) | TD 1530.7 **RT** | 1530.7 − 3.2 = **1527.5**. Consistent **if** the workbook is ground-level-referenced (INFERRED) |
| Alternative TD | 1531 (`pozzi-storici.csv` / ViDEPI) | 1530.7 RT | Consistent with RT, rounded (INFERRED) |
| Base of TD lithology interval | 422.8 (workbook boundary) | 425.9 (formation line) / 426.6 (printout, description track) RT | 425.9 − 3.2 = 422.7 ≈ 422.8 (INFERRED) |
| Temperature depth | Workbook: 1522.6 m, 39 °C, 1957-06-19, "non stabilizzata" | Run-2 bottom 1525.8 RT, 19/06/57. **Printout: "TEMPERATURE DAI LOGS: NESSUNA"** | 1525.8 − 3.2 = 1522.6 (INFERRED). **The printout records no log temperature, yet the workbook has a measurement dated the same day.** Its source is UNKNOWN. **Preserved, not reconciled.** |
| Coverage of the screened TD interval (workbook 422.8-1527.5 ≈ 426-1530.7 RT) | — | SP and ES run 2 continuous from 256 to 1525.8 RT | **Covered except the bottom ~4.9 m, which includes the TD state point** |

**Curve continuity [OBSERVED, pixel check 426-1526 m RT]:** the SP and resistivity
tracks carry a curve on ≥ 99.6 % of pixel rows. The sonic track has grid only.

---

## 6. SP evidence

| Question | Answer | Label |
| --- | --- | --- |
| Present? | Yes: run 1 (25-258.5) and run 2 (256-1525.8) | DOCUMENTED + OBSERVED |
| Scale | Single header at the top: "SP 0 … MV 150" | OBSERVED |
| Scale readable? | Yes, for the header | OBSERVED |
| Run-2 scale stated separately? | **No.** No second header at the splice (~256-258.5 m). Whether run 2 shares the header scale is **UNKNOWN**. | OBSERVED / UNKNOWN |
| Polarity | **Not stated** | OBSERVED (absent) |
| Run boundaries | Documented in the printout (run 1 / run 2, overlap 256-258.5). On the composite the SP curve jumps position at ~258 m. | DOCUMENTED / OBSERVED |
| Baseline shift | Yes, at the ~258 m splice (above the screened interval) | OBSERVED |
| Continuous in the screened interval? | Yes. A single run (run 2) covers ~426-1525.8 RT. | DOCUMENTED + OBSERVED |
| Qualitative or digitisable? | A raster curve at 1:1000, ~8 px/m, track ~500 px wide (≈ 0.3 mV/px if the header span applies). Digitisable in principle, **but only by raster digitisation**, which is a standing project constraint requiring your decision. **Saluzzo 1 is not in the Livani 2023 digitised set** (checked against Livani Table 4 in the earlier audit). | OBSERVED / INFERRED |
| Different scales at different depths? | Not shown | OBSERVED |

**Could this SP support a future quantitative methodology?**

- **Possibly**, for the interval ~426-1525.8 m RT, within one run.
- Only after the scale and polarity for run 2 are confirmed and raster
  digitisation is authorised.
- Only after the end-member problem (section 11, D5) is solved.

---

## 7. Resistivity evidence

| Question | Answer | Label |
| --- | --- | --- |
| Curves | **LN** (dashed per header) and **SN**, labelled in the track header; plus an unidentified third dashed trace near the track's right edge | OBSERVED / UNCLEAR |
| Scale | 0.2-20 Ω·m for both. The internal grid lines sit at positions consistent with a **two-decade logarithmic** scale (lines near 1 and 10 Ω·m). | OBSERVED / INFERRED |
| Depth coverage | ES run 1 25-258.5; ES run 2 256-1525.8 m RT | DOCUMENTED |
| Readable for quantitative use? | Raster only, like the SP. Log scale plus curve overlap makes digitisation harder. | OBSERVED / INFERRED |
| Rm / Rmf / Rw | **Not given.** The mud "Cloruri (g/l NaCl)" column is blank; mud types are coded "AR" (to 521 m) and "RS" (below), with **codes not defined** on the document; densities 1200-1400 g/l. | DOCUMENTED / UNKNOWN |
| Nature | Recorded electrical-survey curves (ES = electrical survey, per the printout code), not a simplified redraw | DOCUMENTED |

---

## 8. Lithology and formation evidence

### 8.1 Operator formation and age columns (composite, RT; boundaries from ruled lines, ±~1-5 m)

| From (m RT) | To (m RT) | Age (as written) | Formation (as written) |
| --- | --- | --- | --- |
| 0 | 257.5 | PLIOCENE - PLEISTOCENE | NON DEFINITA |
| 257.5 | 377.1 | PLIOCENE INFERIORE | SABBIE DI ASTI |
| 377.1 | 425.9 | PLIO(CENE INFERIORE) | ARGILLE DEL SANTERNO |
| 425.9 | 598.0 | MIOCENE ? | NON DEFINITA |
| 598.0 | 1530.7 | **OLIGOCENE** | **MOLARE** |

The printout, *RISULTATI GEOLOGICI* [DOCUMENTED], says the well
*"… ha fornito scarsi dati stratigrafici e petrografici, avendo interessato da m
426.6 a fondo pozzo solo ghiaie e conglomerati di età oligocenica nella parte
inferiore (formazione MOLARE), e di probabile età miocenica nella parte
superiore."* It also says the well stopped at 1530.7 m *"per esaurita
potenzialità dell'impianto"*.

**Comparison with the workbook** `Lito-Stratigrafie` (0-176.8 QUATERNARIO;
176.8-422.8 PLIOCENE; **422.8-1527.5 `CIOTTOLI E SABBIE`, MIOCENE**):

- Lithology agrees (gravels / pebbles).
- **Age differs.** The operator gives Miocene? to ~598 m RT and then Oligocene
  (Molare Fm) to TD. The workbook gives Miocene throughout.
- The upper boundaries also differ: 176.8 vs 257.5.
- **Preserved, not corrected.**

### 8.2 Operator description track (from 426.6 m RT)

*"… ciottoli di ortogneiss granitici e dioritici, scisti sericitici e cloritici,
inglobati in una matrice sabbiosa ed argillosa della stessa natura"* — a single
description for the whole interval [OBSERVED].

### 8.3 Conventional cores

Printout *CAROTE DI FONDO* [DOCUMENTED]. All ten are "SCOPO
STRATIGRAFICO/PETROG", all "Manifestazione nessuna", and all have blank
porosity/permeability fields.

| Core | Interval (m RT) | Recovery (as printed) | Age / Formation (as printed) | Description (as printed, abridged) |
| --- | --- | --- | --- | --- |
| 1 | 222.0-226.0 | 1.2 m = 30.0 % | PLIOCENE-PLEISTOCENE / NON DEFINITA | Argilla plastica, molto siltosa |
| 2 | 400.0-405.0 | 3.4 m = 68.0 % | PLIOCENE INFERIORE / ARGILLE DEL SANTERNO | Argilla grigia, molto siltosa |
| 3 | 461.5-466.0 | 1.0 m = 22.2 % | MIOCENE? / NON DEFINITA | Grossi ciottoli di ortogneiss granitico, in matrice di sabbia verdastra … |
| 4 | 552.0-555.0 | 0.9 m = 30.0 % | MIOCENE? / NON DEFINITA | Grossi ciottoli di ortogneiss granitici e dioritici in matrice sabbiosa … con sostanze argillose e noduli giallastri limonitizzati |
| 5 | 700.5-703.5 | 0.7 m = 23.0 % | OLIGOCENE / MOLARE | as core 4 |
| 6 | 947.5-948.7 | 0.8 m = 66.6 % | OLIGOCENE / MOLARE | Grossi ciottoli di ortogneiss granitici, scisti sericitici, cloritici, cloritoscisti, serpentinoscisti |
| 7 | 1184.0-1187.5 | printed "0.7= 50.0%" (**inconsistent**: 0.7 / 3.5 m = 20 %; preserved as printed) | OLIGOCENE / MOLARE | Grossi ciottoli di ortogneiss granitici in matrice sabbiosa e argillosa giallastra della stessa natura |
| 8 | 1491.5-1495.0 | 0.0 m = 0.0 % | OLIGOCENE / MOLARE | *"Il recupero, che è costituito da un solo ciottolo, è scisto sericitico"* (**inconsistent with 0.0 recovery; preserved**) |
| 9 | 1523.5-1525.5 | 0.1 m = 5.0 % | OLIGOCENE / MOLARE | Ciottoli di filladi sericitiche |
| 10 | 1528.0-1530.7 | 0.8 m = 30.0 % | OLIGOCENE / MOLARE | Grossi ciottoli di micascisto granatifero misto ad un impasto argilloso … |

**Assessment of the audited interval (~426-1530.7 m RT):**

- Lithologically described as **gravel/conglomerate-dominated, with a sandy and
  clayey matrix of the same composition**.
- It is **not** described as sand/shale interbeds [OBSERVED + DOCUMENTED].
- **No part is labelled net reservoir by the source.**

---

## 9. Water-classification evidence

**Composite mineralisation column [OBSERVED; column boundaries detected at 377.6,
426.4, 703.0, 1530 m RT]:**

| Interval (m RT) | Label |
| --- | --- |
| top to 377.6 | **FW** |
| 377.6-426.4 | no label (Argille del Santerno) |
| 426.4-703.0 | **FW?** |
| 703.0-1530.7 | **SW?** |

**Printout [DOCUMENTED]:** *"Il sondaggio Saluzzo 1 è risultato mineralizzato ad
acqua dolce e salata senza alcun indizio di idrocarburi"* (interval 0.0-1530.7).

**Nature of the classes [DOCUMENTED, AGIP 1987 Inventory, Allegato A pp. II-III;
applied here by INFERENCE, same operator and same class names]:**

- They are log-derived classifications.
- Water was *"in genere"* not sampled.
- Fresh means ≥ 20 Ω·m and ≤ 1 g/l; brackish 1-25 g/l; salt up to 250 g/l.

**This well specifically [DOCUMENTED]:**

- **"ANALISI: NESSUNA"**
- **"PROVE DI STRATO: NESSUNA"**
- **the mud chlorides column is blank.**

**No measured water property exists in this record.** The "?" marks show the
operator's own uncertainty.

**Conflict with the 1987 sheet (preserved):**

- The 1987 sheet shows *acqua salmastra* from ~423 m (ground level) ≈ 426 m RT.
- The 1991 composite shows **FW?** from 426.4 to 703 m RT, and **SW?** only below
  703 m.

---

## 10. Cross-check with project screening interval

**Project reference, read-only, established in the previous audit:**

- `depth_m = 1527.5`, datum `UNKNOWN`
- pipeline conflict note 1527.5 vs 1531
- TD lithology interval 422.8-1527.5 `CIOTTOLI E SABBIE`
- screening temperature from 1522.6 m

| Question | Answer |
| --- | --- |
| 1. Does the source cover the entire screened interval? | **Almost.** Logs cover ~426-1525.8 m RT. The bottom ~4.9 m, including the TD state point, is unlogged. Cores 9-10 sample 1523.5-1530.7. |
| 2. SP across the interval? | Yes, to 1525.8 RT (single run 2) |
| 3. Resistivity across the interval? | Yes, LN and SN to 1525.8 RT |
| 4. Lithology across the interval? | Yes: description track, cuttings every 5 m, 8 cores within it |
| 5. Gaps | 1525.8-1530.7 m RT unlogged; low core recovery (0-68 %) |
| 6. Depth references consistent? | Source: RT documented. Project: datum UNKNOWN. Workbook TD, the 422.8 boundary and the temperature depth all equal source RT values minus 3.2 m (INFERRED). |
| 7. Formation names consistent? | **No.** Workbook "MIOCENE" vs operator "MIOCENE ? / NON DEFINITA" to ~598 m RT, then "OLIGOCENE / MOLARE". Preserved. |

---

## 11. Decision gates D1–D10

| Gate | Status | Evidence | Limitation |
| --- | --- | --- | --- |
| D1 — Correct well identity | **PASS** | Name, AGIP code 01547, ViDEPI code 5938, ground 310 m, year, TD consistent after the datum offset | Comune (SALUZZO vs SCARNAFIGI) and ~4.6" coordinate difference between source groups; preserved |
| D2 — Full screened-interval coverage | **PARTIAL** | Single-run SP and ES from 256 to 1525.8 m RT spans the TD interval | Bottom ~4.9 m (1525.8-1530.7 RT), containing the TD state point, is unlogged |
| D3 — Defensible depth reference | **PARTIAL** | Source datum documented (RT 313.20; ground 310.00; RT height 3.2 m); composite consistent with RT via core depths | Project datum UNKNOWN; the workbook-vs-source relationship rests on inferred arithmetic |
| D4 — Quantitatively interpretable SP | **PARTIAL** | Recorded (not redrawn) SP at 1:1000, continuous within one run, header "SP 0 … MV 150" | Run-2 scale and polarity not stated; usable only via raster digitisation (project constraint, your decision); not in Livani |
| D5 — Defensible SP baseline / end members | **FAIL** | The interval is described as one matrix-supported conglomerate unit; no shale end member is identified **within** it. The nearest clay unit (Argille del Santerno, 377-426 m RT) is a different formation. | Selecting end members would require assumptions not supported by the source |
| D6 — Formation-water / Rw evidence | **FAIL** | "ANALISI: NESSUNA"; "PROVE DI STRATO: NESSUNA"; chlorides blank; water classes log-derived and query-marked (FW?, SW?) | Rm and Rmf also absent |
| D7 — Independent lithological validation | **PARTIAL** | Eight conventional cores (3-10) within the interval, with petrographic descriptions; 5 m cuttings | Recovery 0-68 %; two printed recovery inconsistencies (cores 7, 8); qualitative only |
| D8 — Independent validation of net fraction | **FAIL** | No net-pay statement; core porosity and permeability fields blank; no tests | — |
| D9 — Resolution for the relevant bed scale | **UNKNOWN** | Raster ~8 px/m | The source describes no bed scale; a matrix-supported conglomerate may have no discrete net/non-net beds |
| D10 — Reproducible methodology | **FAIL** | None documented; D5 and D6 prevent defining one | — |

No gate is marked PASS on the basis of "not found".

---

## 12. Quantitative NTG feasibility

> ### STILL BLOCKED

**What improved over the 1987 sheet** [evidence-based]:

- Full-depth recorded SP and ES logs from a single run through the TD interval
  (D2, D4 → PARTIAL).
- A documented RT datum that explains the 1527.5 / 1531 TD conflict by
  arithmetic (D3 → PARTIAL).
- Eight core descriptions (D7 → PARTIAL).

**Why it remains blocked:**

- No water or mud-filtrate data exists in the record (D6).
- No shale end member exists within an interval the operator describes as one
  matrix-supported conglomerate (D5).
- No independent net or porosity measurement exists (D8).
- No methodology can yet be defined (D10).

**Finding 3.1 does not change status.**

**Observation (INFERRED; not a conclusion about NTG).** Because the operator
describes the entire TD interval as gravels and conglomerates in a sandy-clayey
matrix, the relevant "net" criterion would concern matrix quality (porosity and
permeability) rather than discrete sand-versus-shale beds. That links this well
to the `net_criterion` choice in `docs/net-to-gross-semantics.md`. The record
supplies **no porosity or permeability** to support such a criterion.

---

## 13. Remaining evidence requirements

Only what is necessary, given this evidence:

1. **Rw or formation-water salinity** for ~426-1530.7 m RT. The printout
   states that no analyses or formation tests were performed, so this cannot come
   from this well's record.
   - Any substitute would be non-well-specific (an analogue), which falls under
     your prohibition.
   - **This is the hardest blocker.**
2. **Rm and Rmf and the run-2 SP scale and polarity** from the original 1957
   Schlumberger ES heading. They are not on the composite; the heading is held, if
   anywhere, in UNMIG/ENI archives.
3. **A decision on raster digitisation** of SP and ES from `data/PDF/saluzzo_001.pdf`.
   It is the only path to numeric curves for this well, and it is currently outside
   the project's standing constraints.
4. **Porosity/permeability or matrix characterisation** of the conglomerate
   (core-sample analyses) to support any porosity-based net criterion. The 1991
   record shows none.
5. **Resolution of the formation-age and water-class conflicts** (workbook
   Miocene vs operator Miocene?/Oligocene-Molare; 1987 brackish vs 1991 FW?/SW?).
   This is a documented choice, not new data.

---

## 14. Conclusion

The ViDEPI composite for SALUZZO 1 (AGIP, updated 1991, 1:1000, with an attached
well-data printout) is the correct, primary, full-depth record for the audited
well.

**What it provides:**

- **Recorded SP and LN/SN resistivity in one logging run** (256-1525.8 m RT,
  19/06/57, Schlumberger) across essentially the whole TD interval.
- A **documented RT datum** that reconciles, by arithmetic, the project's
  1527.5 m TD with the 1530.7 / 1531 m source values.
- **Ten conventional-core descriptions**, eight of them in the interval, showing
  gravels and conglomerates of metamorphic and granitic clasts in a sandy-clayey
  matrix, assigned to the Oligocene Molare Formation.

**What it lacks, and says so explicitly:**

- water analyses and formation tests
- mud chlorides, Rm and Rmf
- core porosity and permeability
- any net-pay statement

The SP scale and polarity for the relevant run are not stated. Numeric curves would
require raster digitisation.

**Result:** D1 passes; D2, D3, D4 and D7 are partial; D5, D6, D8 and D10 fail; D9
is unknown. **Finding 3.1 remains STILL BLOCKED for SALUZZO|1.** The decisive
missing item is formation-water evidence, and this well's own record states that
none was acquired.
