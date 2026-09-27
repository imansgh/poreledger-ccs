# Finding 4.2 / 10.2 — Depth-Datum Provenance (step a)

**Read-only provenance audit, 2026-09-24.**

- No code, data, equation, pressure, capacity or audit number was changed.
- This is step (a) of audit item 3 (*"Establish the depth datum"*,
  `docs/scientific-validation-audit.md` §"Recommended order of work").
- It establishes what the operator documents say. It does **not** apply any
  correction.
- Uncommitted draft.

**Labels used throughout:**

| Label | Meaning |
| --- | --- |
| **DOCUMENTED** | Printed in a primary operator document |
| **OBSERVED** | Read from project data |
| **INFERRED** | This audit's arithmetic or reading |
| **OPEN** | Unresolved |

---

## 1. Question

Finding 10.2 states: *"If that statement [AGIP: 'Tutte le profondità sono riferite
al piano tavola rotary'] can be established as applying to these wells, the
correction becomes computable."* This step answers, for each audited well:

1. What reference does the operator state for its depths?
2. What are the rotary-table (RT) and ground elevations?
3. How do the project's depth values relate to the operator's?

The audited wells, per `scientific-validation-audit.md` Phase 10, are SALUZZO|1,
DESANA|1, ASTI|1, MALOSSA|15 and TRECATE|9|ST.

---

## 2. Sources

| Code | Document | Access |
| --- | --- | --- |
| C-SAL | AGIP *Profilo del pozzo* SALUZZO 1, code 01547, updated 26.11.91, 1:1000, plus data printout | `data/PDF/saluzzo_001.pdf` (= ViDEPI) |
| C-DES | AGIP Mineraria *Servizio Geologico del Sottosuolo*, DESANA pozzo n°1, *"Profilo aggiornato al 31-12-1961"* | `data/PDF/desana_001.pdf` |
| C-AST | AGIP *Profilo del pozzo* ASTI 1, code 01497, updated 06.12.91, plus data printout | `data/PDF/asti_001.pdf` |
| C-MAL | AGIP SpA GESO-SNOR *Profilo del pozzo* MALOSSA 15 (Area ENI), dated Jan 1980, updated Apr 1988 | `data/PDF/malossa_015.pdf` |
| INV | AGIP for MICA, *Inventario delle risorse geotermiche nazionali — Piemonte*, Allegato B (Dec 1987), well sheets ASTI 1 (p. 19), DESANA 1 (p. 40), SALUZZO 1 (p. 22) | UNMIG `r_piemonte_a2.pdf` (retrieved earlier) |
| W | Project workbook `Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx` (`Anagrafica`, `Lito-Stratigrafie`, `Temperature`) | `data/` |
| PS | `data/pozzi-storici.csv` (`Prof`) | `data/` |

**TRECATE|9|ST:** no composite exists in `data/PDF/`. ViDEPI returns **404** for
`trecate_009_st.pdf`, and no TRECATE well appears in ViDEPI's public well list.
That is consistent with ViDEPI covering relinquished titles only, while
Villafortuna-Trecate is a producing concession. **Not establishable from public
operator documents.**

---

## 3. Operator statements (DOCUMENTED)

| Well | Depth-reference statement (verbatim) | RT elevation (m a.s.l.) | Ground elevation | RT height | TD as printed |
| --- | --- | --- | --- | --- | --- |
| SALUZZO\|1 | C-SAL printout: *"NOTA: Tutte le profondita' sono in metri e riferite al P.T.R."* | 313.20 (C-SAL); 313.2 (INV) | 310.00 | 3.20 (INV: *"Altezza della tavola rotary: 3,20 s.p.c."*) | 1530.7 (C-SAL); 1530,70 (INV) |
| DESANA\|1 | C-DES observations column: *"Tutte le profondità sono riferite al piano tavola rotary."* | 145,60 | 142,00 ("Piano terra") | 3,60 (INV) | 3228,50 (C-DES, INV) |
| ASTI\|1 | C-AST printout: *"NOTA: Tutte le profondita' sono in metri e riferite al P.T.R."*; "Q.T.R. 135.0 m.s.l.m." | 135.00 | 132.00 | 3,00 (INV) | 1250.0 (C-AST); 1250,00 (INV) |
| MALOSSA\|15 | C-MAL observations column: *"Tutte le profondità sono riferite al piano tavola rotary."* | 120,00 | 111,00 ("Piano terra") | 9.00 (INFERRED: 120.00 − 111.00; no INV sheet) | **"5500 v.5497~"** |
| TRECATE\|9\|ST | — | — | — | — | — |

The first-flange elevations (309.00, 141,00, 131,20, 110,65) are also printed.
They are not used here.

**Consistency:** RT elevation, ground elevation, RT height and TD agree between
C-SAL/INV, C-DES/INV and C-AST/INV to the printed precision.

---

## 4. Project values vs operator values

| Well | W `depth_m` (`Anagrafica`) | Operator TD (RT) − RT height | Match | PS `Prof` | W `quota` | W deepest `Lito-Stratigrafie` bottom |
| --- | --- | --- | --- | --- | --- | --- |
| SALUZZO\|1 | 1527.5 | 1530.7 − 3.2 = **1527.5** | exact | 1531 (≈ RT TD) | 310 (= ground) | 1527.5 |
| DESANA\|1 | 3224.9 | 3228.5 − 3.6 = **3224.9** | exact | 3229 (≈ RT TD) | 142 (= ground) | 3224.9 |
| ASTI\|1 | 1247.0 | 1250.0 − 3.0 = **1247.0** | exact | 1250 (= RT TD) | 132 (= ground) | **1250.0** (= RT TD) |
| MALOSSA\|15 | 5491.0 | 5500 − 9.0 = **5491.0** | exact | 5497 (= printed "v.5497~") | 111 (= ground) | 5491.0 |

**INFERRED:**

- For all four wells, the workbook `Anagrafica` depth equals the operator's
  RT-referenced TD **minus the RT height**, to the printed precision.
- The workbook depth therefore behaves as a **ground-level-referenced** depth.
- The workbook `quota` is the **ground** elevation, as Finding 10.2 already noted.
- `pozzi-storici.csv` carries the RT-referenced values, rounded.

This is an arithmetic identity across four independent wells. No document states
that GEOTHOPICA converted the depths. **OPEN:** confirmation from GEOTHOPICA /
CNR-IGG metadata.

**Mixed reference inside the workbook (OBSERVED):**

- ASTI 1's deepest `Lito-Stratigrafie` bottom (1250.0) equals the **RT** TD, while
  its `Anagrafica` depth (1247.0) is RT − 3.0.
- The earlier SOMMARIVA DEL BOSCO 1 audit found the same pattern: `Temperature`
  depths equal INV RT depths − 7.7 m.
- So the workbook does **not** use one depth reference across sheets. Each column
  needs its own datum label.

**MALOSSA 15 "v.5497~" (DOCUMENTED; meaning OPEN):**

- The TD field prints a second value. PS carries 5497.
- If it is a vertical depth (the well would then be deviated), `P = rho g z` should
  use vertical depth. The difference is ~3 m, ≈ 0.05 % of depth.
- The document does not define "v."; **not interpreted further.**

---

## 5. Implications for Finding 10.2 (not acted on)

### 5.1 Datum label: established for four of five wells

The operator reference (RT) and elevations are **documented** for SALUZZO|1,
DESANA|1, ASTI|1 and MALOSSA|15. The relationship of the workbook depth to them
is **inferred** (ground-referenced). TRECATE|9|ST remains **unknown**.

### 5.2 Finding 10.2's derrick-height caveat

Finding 10.2 says its figures *"slightly understate the true correction, by the
derrick height"*. That assumes the workbook depth is RT-referenced.

The evidence above indicates the workbook depth is **already ground-referenced**.
If so, the caveat does not apply to `depth_m`: the RT height has already been
removed (INFERRED).

### 5.3 A scientific question the correction depends on (OPEN — for your decision)

Finding 10.2's magnitude table (+1.10 % to +15.59 % capacity) corrects `z` to
**sub-sea** depth, i.e. depth minus ground elevation. That treats the hydrostatic
brine column as starting at **mean sea level**.

Finding 4.2's own text says *"The brine column starts at the water table, not at
the rotary table"*. For an onshore well, the water table (piezometric surface) is
typically near ground level, not at sea level.

For a hydrostatically connected aquifer, `P ≈ rho·g·(depth below the piezometric
surface)`. The current pipeline uses a depth that appears to be ground-referenced,
so it may already approximate that reference, within the water-table depth.

Converting to sub-sea depth would then **understate** pressure by roughly
`rho·g·(ground elevation)`:
- ~3.2 MPa at SALUZZO|1 (310 m);
- ~1.2 MPa at MALOSSA|15 (111 m).

That is the same size as the "overstatement" Finding 10.2 attributes to the
current code, in the opposite direction.

**Which reference is correct is a scientific decision, not a provenance fact.** It
depends on the regional hydraulic head of each reservoir unit, and **no head or
pressure measurement exists in the audited data** (Finding 4.2). The provenance
work shows **only** that the choice must be made explicitly:

| Option | Reference for z | Evidence status |
| --- | --- | --- |
| (i) Ground-referenced depth, as now | piezometric head ≈ ground | Consistent with the data's apparent datum; head unmeasured |
| (ii) Sub-sea depth (Finding 10.2 table) | head at MSL | Assumes head at sea level; unmeasured |
| (iii) Explicit head per well / unit | measured or regional piezometry | Requires data not held |

**No option is chosen here.** Finding 10.2's numbers are **not** changed.

---

## 6. Status of step (a)

| Well | Operator datum | Elevations | Workbook relationship | Status |
| --- | --- | --- | --- | --- |
| SALUZZO\|1 | RT (DOCUMENTED) | RT 313.20 / ground 310.00 (DOCUMENTED ×2) | `depth_m` = RT TD − 3.2 (INFERRED) | **Established** |
| DESANA\|1 | RT (DOCUMENTED) | 145.60 / 142.00 (DOCUMENTED ×2) | = RT TD − 3.6 (INFERRED) | **Established** |
| ASTI\|1 | RT (DOCUMENTED) | 135.00 / 132.00 (DOCUMENTED ×2) | = RT TD − 3.0; `Lito` uses RT (INFERRED) | **Established; mixed within workbook** |
| MALOSSA\|15 | RT (DOCUMENTED) | 120.00 / 111.00 (DOCUMENTED ×1) | = RT TD − 9.0 (INFERRED); "v.5497~" OPEN | **Established; TD variant OPEN** |
| TRECATE\|9\|ST | — | — | — | **Not establishable from public sources** |

---

## 7. What step (b) — any correction — would still require

These are decisions, not implemented:

1. **Decide the hydrostatic reference** (§5.3, options i-iii). This is the
   scientific decision everything else depends on.
2. Decide how to treat TRECATE|9|ST, where the datum is unknown.
3. Decide whether the workbook columns get explicit per-sheet datum labels in
   ingestion (a software/provenance change).
4. Only then: a re-baselined numerical change, with sign-off. It would break the
   pinned bit-exact baseline in `tests/test_percentile_disclosure.py` by design,
   and it interacts with the Finding 12.4 `combined_factor` characterisation,
   whose review thread is still open.
