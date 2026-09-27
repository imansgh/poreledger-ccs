# Finding 3.1 — Primary Well Evidence

**Well: SOMMARIVA DEL BOSCO 1. Evidence retrieval and verification only, 2026-09-23.**

This document contains no NTG, no cutoff, no model change, and no correction of
workbook formation names. Every item is labelled by source type and by whether it
is **measured**, **interpreted** or **metadata**. It is an uncommitted draft.

Companion to `docs/finding-3.1-ntg-feasibility.md` and
`docs/finding-3.1-ntg-evidence-elicit.md`.

---

## 1. Objective

Find and verify the original AGIP/operator documentation for SOMMARIVA DEL BOSCO 1.
The target content was:

- logging-run details
- mud and formation-water data
- core evidence
- the operator's formation tops
- the original logs

The same documents were used to verify ten observations made in the feasibility
study.

---

## 2. Search scope and sources

Sources were searched in the priority order requested.

| # | Source | Identifiers / queries used | Result |
| --- | --- | --- | --- |
| 1 | **ViDEPI** — well list (`/videpi/pozzi/tutti.asp`), well record (`dettaglio.asp?cod=6201`), LAS index (`/videpi/cessati/las.asp`) | SOMMARIVA DEL BOSCO 001; code 6201 | Well record found; composite profile only; **not** in the LAS/LIS list (48 wells) |
| 1 | **ViDEPI** — dossier of the relinquished title containing the well (point-in-polygon on `data/KML/titoli-cessati.kml`) | Coordinates 7.784972 E, 44.783889 N | Title **1569 "AREA ENI APPENNINO OCCIDENTALE"** (ENI exclusive area, 1957-1996). Two AGIP reports plus 8 attachments, all retrieved and read |
| 2 | **UNMIG / MASE** — *Inventario delle risorse geotermiche nazionali*, Regione Piemonte (AGIP, Dec 1987) | Regional report, "Schede pozzi", "Misure di temperature in pozzo", base-of-fresh-water map | **Temperature annex contains a dedicated SOMMARIVA DEL BOSCO 1 sheet.** The well-sheet annex does *not* include it. |
| 2 | UNMIG hydrocarbon well pages / WebGIS | "Sommariva del Bosco", UNMIG | Only a generic well registry; no well documents found online |
| 3-4 | AGIP / ENI archive, final well report ("rapporto finale di pozzo"), drilling report, log headings | Web searches: "Sommariva del Bosco" pozzo AGIP 1981 3809; UNMIG; Geothopica | **No final well report, drilling report, log heading or core report located online** |
| 5 | Institutional: Regione Piemonte / CNR-IGG / Univ. Torino, *Geologia e idrostratigrafia profonda della Pianura Padana occidentale* (Irace et al., 2009) | "Sommariva del Bosco" | Found and read (text layer). **Secondary**: it uses AGIP well stratigraphies; its content is Messinian-Quaternary only. |
| — | Project data (read-only) | `data/PDF/sommariva_del_bosco_001.pdf`; GEOTHOPICA workbook; `data/pozzi-storici.csv`; `data/KML/*.kml`; `data/data.txt` | Provenance of our composite log traced to ViDEPI |

Italian search terms used: *pozzo Sommariva del Bosco 1*, *profilo pozzo*,
*rapporto finale pozzo*, *diagrafie*, *carote*, *analisi acque*,
*resistività fango*, *archivio AGIP / UNMIG*.

**Retrieved files.** All are public official PDFs, stored in the session
scratchpad, **not the repository**:

| File | Size | Source |
| --- | --- | --- |
| ViDEPI `relazioni/4050.pdf` | 2,284,979 B | ViDEPI |
| ViDEPI `relazioni/4051.pdf` | 3,929,732 B | ViDEPI |
| ViDEPI `allegati/6675-6678.pdf` | — | ViDEPI |
| UNMIG `r_piemonte.pdf` | 344,844 B | UNMIG |
| UNMIG `r_piemonte_a1.pdf` | 1,440,290 B | UNMIG |
| UNMIG `r_piemonte_a2.pdf` | 361,645 B | UNMIG |
| UNMIG `c_pi_6.pdf` | 4,658,269 B | UNMIG |
| Regione Piemonte `testo_idrostat2.pdf` | 10,868,221 B | Regione Piemonte |

The ViDEPI and UNMIG PDFs are **raster scans without a usable text layer** and
were read visually.

---

## 3. Sommariva del Bosco 1 identifiers

| Identifier | Value | Source | Type |
| --- | --- | --- | --- |
| UNMIG / ViDEPI well code | **6201** | ViDEPI well record; `pozzi-storici.csv` | metadata |
| AGIP well code | **04254** ("Cod. pozzo") | Composite log header | metadata |
| ViDEPI profile id | 1738 | ViDEPI well record; `pozzi-storici.csv` ("Profilo") | metadata |
| Name variants | SOMMARIVA DEL BOSCO 001 (UNMIG/ViDEPI); SOMMARIVA DEL BOSCO 1 (AGIP) | as above | metadata |
| Permit | "AREA ENI" (log header) = ViDEPI title 1569 AREA ENI APPENNINO OCCIDENTALE | Log header; ViDEPI dossier | metadata |
| Operator | AGIP (100 %) | Log header; ViDEPI | metadata |
| Spud / TD reached / rig released | 04-04-81 / 23-06-81 / 27-06-81 | Log header | metadata |
| Rig / contractor | NATIONAL 80 UE / FORITALIA | Log header | metadata |
| Outcome / status | STERILE / TAPPATO E ABBANDONATO | Log header; ViDEPI "Sterile" | metadata |
| TD | 3809.0 m | Log header; ViDEPI; 1987 Inventory | metadata |
| Elevations | Rotary table 307.70; first flange 298.60; ground 300.00 m a.s.l. (log header). Inventory: ground 300, **RT height 7.7**, RT 307.7 | Log header; 1987 Inventory | metadata |
| Coordinates | Long. W004°40'02.5" (from Monte Mario), Lat. N44°47'02.0"; plane E 1,403,873 / N 4,959,750 | Log header; Inventory | metadata |

---

## 4. Original AGIP / operator documentation found

| # | Source | Title | Date | Identifier | Accessibility | Relevance | Primary? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | ViDEPI `deposito/pozzi/profili/pdf/` | AGIP **"Profilo del pozzo" — SOMMARIVA DEL BOSCO 1**, 1:1000 composite log (compiler/reviewer C. De Col) | Updated **06.02.92** (AGEO-SECR) | `sommariva_del_bosco_001.pdf`, 709,543 B | Public. **Identical in size to our `data/PDF` copy**; ViDEPI Last-Modified 2018-12-10 | **High** — the only well-specific document with logs | Yes (operator) |
| P2 | UNMIG, *Inventario delle risorse geotermiche nazionali*, Regione Piemonte, Allegato B *"Misure di temperatura in pozzo"* | Well sheet **"POZZO: SOMMARIVA DEL BOSCO 1"** (p. 26 of 42) | **Dicembre 1987** (AGIP for MICA) | `r_piemonte_a2.pdf` | Public scan | **High** — litho-stratigraphy, RT datum, dated temperature measurements | Yes (operator compilation) |
| P3 | same Inventory, Allegato A *"Schede sorgenti / Schede pozzi (con profilo semplificato fino a base acque dolci)"* | Introduction pp. II-III (method); index of 23 Piemonte wells | Dec 1987 | `r_piemonte_a1.pdf` | Public scan | **Medium** — defines the fresh/brackish/salt-water convention. **Sommariva del Bosco 1 is not among its well sheets.** | Yes (operator) |
| P4 | ViDEPI title 1569, report 4050 | AGIP, *AREA ENI — Dominio Appenninico Occidentale — Lineamenti geologico minerari* | Dicembre 1996 | `relazioni/4050.pdf` (12 pp.) + 8 attachments | Public scan | **Low-medium** — regional unit scheme (Fig. 3) and exploration summary; **no well-specific data** | Yes (operator, regional) |
| P5 | ViDEPI title 1569, report 4051 | AGIP, *AREA ENI — Lineamenti geologico-minerari (generale)* | 01/12/1996 | `relazioni/4051.pdf` (32 pp.) | Public scan | **Low** — Po-Plain-wide synthesis; no well-specific data | Yes (operator, regional) |
| P6 | ViDEPI attachments 6675-6678 | Index map; geological cross-sections SEZ-1, SEZ-2, SEZ-4 | 1996 | `allegati/667x.pdf` | Public scan | **None for this well**: the section well list (index map) does **not** include Sommariva del Bosco 1 | Yes |
| S1 | Regione Piemonte | Irace et al. (2009), *Geologia e idrostratigrafia profonda della Pianura Padana occidentale* | 2009 | `testo_idrostat2.pdf` | Public | **Low** for the target interval. It cites **AGIP (1972) and AGIP (1994)** stratigraphies of this well, but discusses only Messinian-Quaternary units. | **Secondary** |

**Referenced but not found or accessible:**

- The **1981 Schlumberger log prints and headings**.
- The **AGIP final well report** ("rapporto finale").
- **Core reports**.
- **Water analyses**.
- The **"AGIP (1994)"** well stratigraphy cited by S1, which could be the source
  of the 1992-style nomenclature. Its existence is known only from that citation.

---

## 5. Logging-run evidence

| Run | Depth (m, RT) | Date | Tool | Company | SP scale | Resistivity | Other curves | Evidence status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 23 ("INIZIO REGISTRAZIONE m 23") – ~302 | BHT **08/04/81** at **301.5 m** (P2) | ILD, SFLU (curve mnemonics, P1) | Schlumberger (implied only by the footer "F.P. SCHLUMBERGER") | −150 … +150 mV (P1 header) | ILD 0.2-20 Ω·m; SFLU 0.2-20 Ω·m (P1) | DT 140-40 µs/ft (P1) | **CONFIRMED** (run exists: P1 header + P2 BHT set). Tool and company **not documented** beyond mnemonics and footer. |
| 2 | ~302 – ~1602 | BHT **22/04/81** at **1596 m** and **1594 m** (P2) | ILD, SFLU (P1) | as above | −150 … +150 mV (P1 header at ~300 m) | 0.2-20 Ω·m (P1) | DT 140-40 (P1) | **CONFIRMED** (P1 + P2) |
| 3 | ~1602 – ~2899 | BHT **22/05/81** at 2900 m; **23/05/81** at 2902 m and 2901 m (P2) | ILD, SFLU (P1) | as above | −150 … +150 mV (P1 header at ~1600 m) | 0.2-20 Ω·m (P1) | DT 140-40 (P1) | **CONFIRMED** (P1 + P2) |
| 4 | ~2899 – ≥3802 | BHT **20/06/81** at **3801 m** and **3802 m** (P2) | ILD, SFLU (P1) | as above | **Illegible** on P1 (possibly "−100 … +1?0") | 0.2-20 Ω·m (P1) | DT 140-40 (P1; run-4 label to be re-read) | Run **CONFIRMED**; SP scale **UNVERIFIABLE** with available documents |

**Supporting quotation (P2, Premessa):** the sheets report *"la temperatura di
fondo pozzo (BHT) rilevata ad ogni registrazione di logs e la relativa
profondità"*. Four dated BHT sets therefore correspond to four logging
registrations. [primary; metadata]

**Not documented in any source found:**

- Tool string names.
- Run numbers as printed on the original headings.
- SP polarity convention (beyond the scale sign).
- Chart speed of the original prints. The composite is 1:1000 (P1).
- Per-run depth datum statement. P2 states *"tutte le profondità sono riferite
  alla tavola rotary"* for its own sheet.

**Casing shoes** (P1 casing column labels only): **302, 1602, 2899 m**. They are
consistent with the P2 BHT depths (301.5, 1596, 2900-2902). No independent
casing record was found.

---

## 6. Mud and formation-water evidence

### Measured

| Item | Value | Source |
| --- | --- | --- |
| Temperatures during logging | 301.5 m: 28.9 °C (circ. 0h30', stop 3h30'). 1596 m: 50.5 °C (3h30' / 5h30'). 1594 m: 52.2 °C (3h30' / 9h20'). 2900 m: 80.5 °C (2h30' / 9h30'). 2902 m: 83.3 °C (2h30' / 15h). 2901 m: 84.1 °C (2h30' / 20h10'). 3801 m: 102.7 °C (2h45' / 11h45'). 3802 m: 104.4 °C (2h45' / 15h30'). | P2 (primary, measured, non-stabilised) |
| Derived BHT ("BHT ricavato") | 53.8 °C (run 2); 86.6 °C (run 3); **109.2 °C (run 4)** | P2 (primary; **derived**, not measured) |
| Rm, Rmf, mud type, mud salinity, mud temperature | — | **Not found in any source** |
| Rw, formation-water salinity, water samples, chemistry | — | **Not found in any source** |

### Interpreted

**Mineralisation column on P1** ("FW", "FW?", "BW?", "SW", "SW?"): fresh water
from the start of logging to ~1506 m; BW? 1531-1560; SW / SW? from 1560 to TD,
including the whole candidate interval.

**Nature of these labels (P3, AGIP 1987, pp. II-III), quoted:**

> *"Non prelevandosi in genere campioni di fluidi mancano analisi chimiche delle
> acque. Tuttavia i logs elettrici consentono determinazioni sufficienti per una
> attendibile classificazione delle acque in: acque dolci, acque salmastre,
> acque salate."*

- **Acque dolci:** clean sands with log resistivity ≥ 20 Ω·m, "*a non oltre 1 g/l*".
- **Salmastre:** conventionally 1-25 g/l.
- **Salate:** "*tenore salino alto od altissimo (fino a 250 gr/l)*", with very
  low resistivity.
- The report adds that the salt content "*non può essere indicato con
  precisione*".

**Assessment:**

- The FW/BW/SW labels are **log-derived classes, not water analyses**. [primary
  statement of method]
- That P1's 1992 labels follow the same convention is an **inference**: same
  operator, same class names.
- Under that convention "SW" places the water in a **class** (> 25 g/l by
  convention). **It is not an Rw value, and no Rw is inferred here.**

**Base of fresh water (regional):** the Inventory map `c_pi_6` ("Isobate della
base delle acque dolci") exists and was retrieved. It is regional and was **not**
used to infer any well value.

### Missing

Rm, Rmf, mud type, mud salinity, Rw, formation-water salinity, water samples and
water chemistry for any run. **None of these exists in any source located.**

---

## 7. Core and sidewall-core evidence

| Item | Evidence | Source | Status |
| --- | --- | --- | --- |
| Conventional core ~3801-3809 m | Black box labelled "1" in the CAROTE column at the base of the log | P1 (symbol only) | **UNVERIFIABLE.** No core report, description, analysis or photograph found. P2 contains no core information. |
| Sidewall cores from ~2900 m | Open circles in the CAROTE column. The legend defines the circle as *"carote di parete"*. | P1 (symbols only) | **UNVERIFIABLE** as to content. Presence is shown only as symbols. |
| Core lithology, grain size, sand/shale proportions, porosity, permeability, mineralogy, thin sections | — | — | **Not found** |
| Operator net reservoir / net pay | — | — | **Not found.** The well is recorded as *STERILE* (P1, ViDEPI). |

**Interpreted lithology, per logging interval (P2 table):**

- 301.5 m: *"Sabbie e ghiaie con intercalaz. di argille"*
- 1594-1596 m: *"Sabbie e conglomerati con intercalazioni di argille e marne"*
- 2900-2902 m: *"Sabbie e arenaria con intercalaz. di argille"*
- 3801-3802 m: *"Sabbie e arenarie con intercalaz. di argille"*

These are interpretations, not core measurements. P2's Premessa says the profiles
are reconstructed from cuttings, cores and continuous logs.

---

## 8. Formation-top evidence

Operator terminology is recorded **exactly**. **No nomenclature is judged
correct.**

### 8.1 AGIP 1987 (P2, "SUCCESSIONE LITOSTRATIGRAFICA"; depths referred to the rotary table)

| From (m) | To (m) | Age | Unit (as written) |
| --- | --- | --- | --- |
| 23 | 240 | PLEISTOCENE | — |
| 240 | 580 | PLIOCENE medio-superiore | (SABBIE DI ASTI) |
| 580 | 1190 | PLIOCENE inferiore | (SABBIE DI ASTI) |
| 1190 | 1560 | MESSINIANO | (SARTIRANA) |
| 1560 | 1800 | MESSINIANO | (SERRAVALLE ?) |
| 1800 | 3809 | TORTONIANO | (SERRAVALLE) |

### 8.2 AGIP 1992 composite (P1)

Read visually. Depths come from a raster calibrated on 25 m grid lines, with
**±~1 m agreement at shared tops and up to ~8.5 m residual overall**.

| From (m) | To (m) | Age (as written) | Formation (as written) |
| --- | --- | --- | --- |
| 240 | 580 | PLIOCENE MEDIO - PLIOCENE SUPERIORE | SABBIE DI ASTI |
| 580 | ~1015 | PLIOCENE INFERIORE | SABBIE DI ASTI |
| ~1015 | ~1561 | MESSINIANO | CONGLOMERATI DI CASSANO SPINOLA |
| ~1561 | ~1801 | MESSINIANO | NON DEFINITA |
| ~1801 | ~1916 | (TORTONIANO) | MARNE DI SANT'AGATA FOSSILI |
| ~1916 | ~3439 | TORTONIANO | LEQUIO – MARNE DI SANT'AGATA FOSSILI EQ. |
| ~3439 | ~3499 | SERRAVALLIANO | CASSINASCO |
| ~3499 | 3808.5 | SERRAVALLIANO ? | CASSINASCO |

### 8.3 AGIP 1996 regional unit scheme (P4, Fig. 3 legend)

Lists *Fne di Cassinasco (CSI)*, *Fne di Lequio (LEQ)*, *Marne di S.Agata fossili
(SAF)*, *Congl. di Cassano Spinola (CCS)*, *Sabbie di Asti (AST)*,
*Gessoso Solfifera (GES)*, and SAT among others. **"Serravalle" does not appear
in this legend.** [primary, regional, interpreted]

### 8.4 Comparison with the project workbook

- The workbook `Lito-Stratigrafie` rows for SOMMARIVA DEL BOSCO 1 reproduce **8.1
  (AGIP 1987) exactly**: the same depths and the same unit names, including
  "SERRAVALLE ?" and "SERRAVALLE".
- The discrepancy recorded in the feasibility study is therefore **between two
  AGIP documents** (1987 vs the 1992 revision). It is **not** a workbook
  transcription error.
- The workbook is unchanged.

---

## 9. Original log availability

| Curve | On P1 (1992 composite, raster) | Digital anywhere? | Notes |
| --- | --- | --- | --- |
| SP | Yes (4 runs) | **Livani 2023** (hand-/semi-automatically digitised, 0.5 m) | — |
| ILD (deep induction) | **Yes**, 0.2-20 Ω·m | **No.** Not in Livani, not in the ViDEPI LAS list, not in any source found. | Usable only by digitising P1 (raster, 1:1000) or by obtaining the original prints/tapes |
| SFLU (shallow/flushed) | **Yes**, 0.2-20 Ω·m | **No** | as ILD |
| Sonic DT | Yes, 140-40 µs/ft | Livani 2023 | — |
| GR | **Not seen as a curve on P1** | **No.** The Livani metadata claims it; the Livani file lacks it. | The Livani GR discrepancy is **preserved, not reconciled**. P1 gives no support for a GR curve. |
| Density, neutron, caliper | Not seen on P1 | No | — |
| Original service-company prints / tapes | — | **Not located** | Held, if anywhere, in ENI/AGIP or UNMIG archives (not online) |

**Conclusion:**

- The resistivity curves **exist** in the operator composite.
- They are **not available in usable digital form** from any public source found.
- Obtaining them would need either digitising the raster, which falls under the
  project's standing constraint on raster digitisation and needs your decision,
  or a request to ENI / UNMIG for the originals.

---

## 10. Livani cross-check

| Evidence item | Livani 2023 | AGIP / original | Status | Interpretation |
| --- | --- | --- | --- | --- |
| Depth datum | MD from RT; TVDSS at MD 0 = **307.7** | P1: RT 307.70; P2: RT 307.7, *"profondità riferite alla tavola rotary"* | **Consistent** | Livani MD = RT-referenced depth |
| TD | 3809.0 | 3809 (P1, P2) | Consistent | — |
| SP coverage | 24.0-3795.0 m | P1: logging starts at 23 m. P2: run-4 BHT at 3801-3802 m, so the logger reached ≥ 3802 m. | **Partial.** Livani stops ~7 m short of the deepest documented logging depth. | The unlogged 3795-3809 m includes the core-1 position |
| Sonic coverage | 26.5-3792.0 m (one gap 478.5-485) | P1 sonic from ~23 m | Partial (ends 3792) | Cause of the shortfall not documented |
| Run boundaries | Not marked. SP offsets at ~302 m (~147 mV) and ~1602 m (~68 mV) carried through unnormalised. | 4 runs (P1 headers; P2 BHT dates); shoes 302 / 1602 / 2899 | **Consistent location; not handled by Livani** | Livani's SP is not baseline-normalised across runs |
| Curve scales | ReadMe gives units only (mV, µs/ft, API), no per-run scales | P1: SP −150…+150 (runs 1-3), run 4 illegible; DT 140-40 | **Unresolved** for run 4 | — |
| Formation boundaries | None in file; lithology codes only | P1 and P2 (different nomenclatures) | Not applicable | — |
| Curves omitted | SP, sonic digitised; **ILD and SFLU not digitised** | P1 shows ILD and SFLU on all runs | **Discrepancy documented** | The paper says resistivity was used to derive the "Mineralization" column; the curve itself is not released |
| GR | Metadata "Y"; file has no GR | Not seen on P1 | **Contradiction inside Livani, preserved** | Not reconciled |
| Mineralization | Codes 0 = water / 1 = gas; all water | P1: FW / BW / SW classes (log-derived per P3) | Different content | Livani does not carry the salinity class |
| Trace fidelity | No error reported | Raster available | **Not yet checked** | An independent re-read at control depths remains open (feasibility gate D6) |

### 10.1 Verification of the feasibility-study observations

| # | Observation (from `data/PDF/sommariva_del_bosco_001.pdf`) | Verdict | Basis |
| --- | --- | --- | --- |
| 1 | Four logging runs | **CONFIRMED** | P1 repeated headers, plus P2's four dated BHT sets, which P2 defines as recorded at each log registration |
| 2 | Casing shoes ~302, 1602, 2899 m | **PARTIALLY CONFIRMED** | Only on P1 (casing labels). Consistent with P2 logging depths 301.5 / 1596 / 2900. No independent casing record. |
| 3 | Run 4 contains the candidate interval | **CONFIRMED** | P1 run-4 header at ~2900 m; P2 run-3 BHT at 2900-2902 m and run-4 BHT at 3801-3802 m |
| 4 | Candidate interval ~3439-3795 m | **PARTIALLY CONFIRMED** | 3439 m is the Cassinasco top on the **1992** composite only; P2 (1987) has no boundary there. 3795 m is Livani's SP end; P2 shows logging reached ≥ 3802 m. |
| 5 | SP run-splice offsets in Livani at ~302 and ~1602 m | **CONFIRMED** | Reproducible from `W143.txt`; located at run boundaries documented by P1 and P2 |
| 6 | AGIP log shows resistivity curves | **CONFIRMED** | ILD and SFLU, 0.2-20 Ω·m, on P1 run headers. Not available digitally. |
| 7 | Conventional core ~3801-3809 m | **UNVERIFIABLE** | Symbol on P1 only; no core documentation found |
| 8 | Sidewall cores from ~2900 m | **UNVERIFIABLE** | Symbols on P1 only |
| 9 | Qualitative fresh/salt-water annotations | **CONFIRMED** (presence). Their nature is now **clarified**. | P1 labels exist. P3 states that such classes are log-derived, with no chemical analyses: **interpreted, not measured**. |
| 10 | Formation split within 1800-3809 m | **CONFIRMED** as an inter-document discrepancy | P2 (AGIP 1987): SERRAVALLE 1800-3809. P1 (AGIP 1992): Marne di S.Agata Fossili / Lequio eq. / Cassinasco. The workbook matches P2. |

---

## 11. Evidence gaps

Only evidence that remains genuinely unavailable after this search:

1. **Rm, Rmf, mud type and mud salinity** for any run.
2. **Rw or formation-water salinity**; any water sample or chemistry.
3. **Run-4 SP scale.** It is illegible on P1, and no heading was found.
4. **Tool strings and original run headings.**
5. **Core 1** (~3801-3809 m) and **sidewall-core** descriptions and analyses.
6. **Digital resistivity (ILD, SFLU)** in any public form.
7. **GR** in any form.
8. **AGIP final well report**, and the "AGIP (1994)" stratigraphy cited by S1.

---

## 12. Implications for Finding 3.1

**No NTG was calculated.**

**The feasibility status is unchanged: quantitative NTG remains BLOCKED.**

**What changed:**

- **Gate D1 (formation assignment)** is now better defined. The conflict is
  between two dated AGIP documents (1987 "Serravalle" vs 1992
  "Lequio-S.Agata eq. / Cassinasco"), and the workbook traces to the 1987 one.
  **It is still unresolved.** Which version to use is a documented decision for
  you, not a data gap.
- **Gate D4 (run structure)** is now **confirmed from a second primary
  source** (P2) for the existence, dates and bottom depths of four runs. The
  run-4 SP scale is still unconfirmed.
- **Gate D5 (fluid data)** is **clarified negatively**. The operator itself
  states that no water chemistry was normally sampled, and that FW/BW/SW are
  log-derived classes. The "SW" annotation is therefore **not** a measured Rw.
  No Rmf was found.
- **Gate D8 (calibration)** is still not passed. Cores are shown only as symbols.

---

## 13. Decision gate

### Now sufficient for the next methodological phase

- **Datum:** MD from RT (307.7 m a.s.l.), consistent across Livani, P1 and P2.
- **Logging-run structure:** four runs with dated BHT depths. The candidate
  interval lies wholly within run 4.
- **Temperatures for run 4:** measured 102.7 / 104.4 °C and derived 109.2 °C at
  3801-3802 m. Adequate for temperature corrections **if** Rmf and Rw are ever
  obtained.
- **Operator nomenclature options:** both documented, so the gross-interval
  decision can now be made explicitly and cited.

### Still missing (blocking)

- **Rmf and Rw**, or any measured salinity (gate D5).
- **Run-4 SP scale** (gate D4, partly).
- An **independent lithology or porosity calibration** in the interval: core 1,
  sidewall cores, or GR (gate D8).
- A **digitisation fidelity check** of Livani against P1 (gate D6). This is
  doable from P1 now, but only worth doing if D5 becomes passable.
- A **decision** on which AGIP nomenclature defines the gross interval (gate D1),
  plus the net-criterion and cutoff pre-registration (D3, D9).

### Next evidence action (not implemented)

A formal request to **UNMIG (MASE, Divisione VI / archivio pozzi)** and/or
**ENI archives** for the SOMMARIVA DEL BOSCO 1 package:

- original Schlumberger log prints with headings (Rm, Rmf, mud type, scales) for
  the four runs;
- the final well report;
- core 1 and sidewall-core reports;
- any formation-test or water-analysis records.

Quote UNMIG code **6201**, AGIP code **04254**, and permit **AREA ENI**.

---

## Integrity notes

- No NTG value, cutoff, or model / code / test / audit change.
- Workbook formation names are **not** corrected.
- The Livani GR discrepancy is preserved.
- **A separate data observation, recorded and not acted on:**
  - The workbook `Temperature` depths for this well are **293.8, 1587.3, 2893.3
    and 3793.3 m**.
  - Three of the four equal the P2 RT-referenced depths minus the 7.7 m rotary
    height: 301.5 − 7.7; 2901 − 7.7; 3801 − 7.7.
  - The fourth (1587.3) does not match either 1596 − 7.7 or 1594 − 7.7.
  - The workbook formation tops equal P2's RT-referenced tops.
  - The workbook may therefore **mix depth references between its Temperature and
    Lito-Stratigrafie sheets** for this well. This bears on the datum findings
    (4.2 / 10.2) and is outside this task.
