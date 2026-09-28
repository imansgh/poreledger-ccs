# Scenario literature review

Version 1 - 2026-09-19

## 1. Purpose

The ingestion layer establishes that no well in the Piemonte pilot can be
screened from source data alone: `area_m2`, `porosity`, `pressure_pa`,
`storage_efficiency` and net `thickness_m` have no source. Screening therefore
requires a scenario that supplies them explicitly.

This document records what the literature does and does not support for each,
so the resulting scenario (`literature-screening-v1`) can be audited rather than
believed. It is a review of *published methodology and regional parameter
compilations*. It is **not** a site characterisation, and nothing in it makes
any number here site-specific to a well in this dataset.

## 2. Required parameters

| Parameter | Unit | Needed because |
| --- | --- | --- |
| `area_m2` | m2 | Capacity is linear in it; M = A h phi rho E |
| `thickness_m` | m | Net storage thickness (not gross stratigraphy) |
| `porosity` | - | Pore volume fraction |
| `pressure_pa` | Pa | Sets CO2 density with temperature |
| `storage_efficiency` | - | Fraction of pore volume CO2 can occupy |

`temperature_k` is excluded: it is source-derived per well and a scenario may
not override it.

## 3. Sources reviewed

**Primary sources read in full (PDF retrieved and text extracted):**

1. **CSLF-T-2008-04** - Bachu, S. (2008). *Comparison between Methodologies
   Recommended for Estimation of CO2 Storage Capacity in Geological Media -
   Phase III Report*. Prepared for the Technical Group, Carbon Sequestration
   Leadership Forum, 21 April 2008. Joint work of the CSLF Task Force on CO2
   Storage Capacity Estimation and the USDOE Capacity and Fairways Subgroup of
   the Regional Carbon Sequestration Partnerships Program.

2. **Donda, F., Volpi, V., Persoglia, S., Parushev, D. (2011).** *CO2 storage
   potential of deep saline aquifers: The case of Italy.* International Journal
   of Greenhouse Gas Control **5**(2), 327-335. DOI: 10.1016/j.ijggc.2010.08.009

**Consulted but not adopted as a numerical source:**

- US DOE/NETL CO2-SCREEN and Carbon Storage Atlas materials, and Goodman et al.
  (2011), IJGGC 5, 952-965. Several efficiency figures circulate for these
  (component displacement efficiencies in the tens of percent, and total
  efficiencies of a few percent). The primary documents were paywalled or
  unreachable at the time of review, and the figures returned by search were
  summaries rather than verifiable quotations. **No number from these has been
  adopted**, because the distinction between *total* storage efficiency and its
  *component* terms is exactly the kind of thing a summary gets wrong.

- Published hydrostatic gradient compilations. Values around 10-15 kPa/m are
  widely quoted, but the search results could not be traced to a primary
  document. No literature gradient has been adopted; see section 4.

## 4. Adopted ranges

### storage_efficiency = 0.01 to 0.04 (1% to 4%)

Direct quotation, CSLF-T-2008-04:

> "through Monte Carlo simulations of CO2 storage in coal beds and in deep
> saline aquifers for conditions characteristic to North America, the USDOE
> Subgroup obtained a range of values for these storage efficiency coefficients
> for the 15% and 85% confidence intervals, which are between 0.28 and 0.40 for
> coal beds, and **between 1% and 4% for deep saline aquifers**."

Corroborated by regional application: Donda et al. (2011) compute Italian
capacity "assuming that 1% or 4% of the total pore volume can be filled by CO2
(US DOE, 2008)".

Note a discrepancy in the published Italian paper: the same paragraph states
"1% or 4%" and then reports results as "(Seff = 1% or 5%, respectively)". We
adopt the CSLF 1-4% figure and record the inconsistency rather than silently
choosing.

**Two caveats that matter more than the number:**

- The range is a **P15-P85 interval from Monte Carlo simulation of North
  American formations**. It is not a measurement, and not Italian.
- It is calibrated against a **basin- or aquifer-scale area**, not a structural
  closure. Section 8 explains why that forbids mixing it with a closure area.

**Statistical interpretation (Model Contract A6).** The scenario samples E from
Uniform(0.01, 0.04). The Uniform distribution is a project-defined prior over the DOE-derived P15–P85 bounds. It is not claimed to reproduce the DOE probability distribution.
E is the aggregate DOE-style storage efficiency, containing the gross-to-net
term (A4, A5); it is never divided by a net-to-gross ratio.

### porosity = 0.10 to 0.35

Donda et al. (2011), Table 2, "Key parameters of the Italian potential
reservoirs for the evaluation of the CO2 storage capacity", porosity column
across 13 Italian candidate reservoirs:

| Site | Depth (m) | Area (km2) | Effective thickness (m) | Porosity (%) |
| --- | --- | --- | --- | --- |
| Abruzzi 1 | 1340 | 175 | 80 | 25 |
| Abruzzi 2 | 1320 | 340 | 75 | 25 |
| Abruzzi 3 | 1360 | 64 | 125 | 30 |
| Abruzzi mare | 1500 | 1800 | 210 | 30 |
| Lombardia 1 | 1590 | 740 | 75 | 10 |
| Marche 1 | 1270 | 615 | 255 | 35 |
| Molise 1 | 1320 | 45 | 195 | 25 |
| Molise 2 | 1260 | 155 | 270 | 25 |
| Emilia 1 | 1100 | 560 | 210 | 20 |
| Lombardia 2 | 1100 | 615 | 240 | 20 |
| Sicilia 1 | 1050 | 465 | 110 | 35 |
| Bradanica | 1000 | 520 | 480 | 25 |
| Emilia mare | 1400 | 715 | 470 | 30 |

Range 10-35%, derived by the authors from sonic-log P-wave velocities and
empirical functions (Schlumberger, 2000). This is **regional** evidence: Italian
Plio-Pleistocene clastic reservoirs, the same play type as the Piemonte pilot
wells. It is not evidence about any particular pilot well.

### pressure_pa - derived from source depth, not assumed flat

The pilot wells span 897 m to 6,694 m. A single pressure range across that
interval would be indefensible: hydrostatic pressure at 900 m and at 6,700 m
differ by roughly a factor of seven.

No literature gradient was traceable to a primary source (section 3), so instead
of citing one we declare the **physics explicitly** and let the scenario carry
the parameter:

```
P_hydrostatic = rho_brine * g * depth
rho_brine = 1020 to 1100 kg/m3   (saline formation water)
g         = 9.80665 m/s2
          -> 10.0 to 10.8 kPa/m
```

The scenario declares a brine-density range; pressure is then **derived per well
from source-derived depth**. Provenance records it as derived, naming both the
source depth and the scenario gradient. This is classified **generic**: it is
the normally-pressured hydrostatic assumption, and it is wrong for any
over- or under-pressured reservoir. The structured ingestion sources contain no
pressure data, so nothing in them tests that assumption. Project operator
records do contain measured pressures, but none is a stabilised water-bearing
pressure for the five screened wells; pressures from non-screened wells are
analogue evidence only and are not transferred to any screened well
(`docs/scientific-validation-audit.md`, Remaining uncertainty item 5).
*(Scope corrected 2026-09-27; originally "Nothing in the dataset tests that
assumption, because no measured pressure exists.")*

### thickness_m (net storage thickness) - NOT adopted from literature

See section 9.

### area_m2 - NOT adopted from literature

See section 8.

## 5. Rationale

Only two parameters are adopted with a citation:

- `storage_efficiency`, because a named methodology body published a specific
  range for exactly this term, and an Italian regional study applied it.
- `porosity`, because a peer-reviewed Italian study tabulated values for the
  same play type from log data.

Everything else is either derived from source data under a declared physical
model (`pressure_pa`) or left as an explicit, uncited user input
(`area_m2`, `thickness_m`).

## 6. Generic vs regional vs site-specific

| Parameter | Class | Basis |
| --- | --- | --- |
| `storage_efficiency` | **generic** | North American Monte Carlo; applied to Italy by others |
| `porosity` | **regional** | 13 Italian Plio-Pleistocene clastic reservoirs |
| `pressure_pa` | **generic** | hydrostatic model + declared brine density, x source depth |
| `area_m2` | **unsupported** | must be supplied by the user |
| `thickness_m` | **unsupported** | must be supplied by the user |

**No parameter is site-specific.** Not one value in this review was measured in,
or derived from, any of the 46 pilot wells.

## 7. Remaining unsupported parameters

`area_m2` and `thickness_m`. Both are linear multipliers in the capacity
equation, so together they dominate the answer. Any capacity number this
repository produces is therefore conditional on two numbers the user supplies
and the data cannot check.

## 8. Area policy

**Policy: `area_m2` is explicit scenario or user input. It is never inferred.**

Area is not derived from licence polygons, concession boundaries, administrative
boundaries, well spacing, or a radius around a well. Reconnaissance found the
only polygons in the dataset are expired mining licences (median 268 km2, max
21,138 km2), which are legal instruments unrelated to any reservoir geometry.

The literature actively reinforces this. Donda et al. (2011) define their area
term as:

> "A is the area that defines the basin or the region occupied by the aquifer
> (m2)"

and obtain it "through the correlation between the borehole information and the
available seismic lines, which led to the mapping of the reservoir and caprock
depth". That is a seismic interpretation product. This repository has seismic
**line geometry** in KML but no interpreted horizons, so that route is closed.

There is a further trap. The CSLF 1-4% efficiency is calibrated against
basin-scale area, and Donda's Table 2 areas are 45-1,800 km2. Substituting a
structural-closure area (tens of km2) into a relationship calibrated on basin
area, while keeping the basin-scale efficiency, double-counts the reduction and
is not defensible in either direction. A, h and E from that methodology are a
consistent triple; they cannot be mixed piecemeal with values from another
framing.

The API and any future UI must state: **"Area is not inferred from
administrative licence boundaries."**

## 9. Net-thickness policy

**Policy: gross and net thickness are separate fields. Neither is converted into
the other.**

The sources provide gross chronostratigraphic intervals (91-2,557 m across the
pilot wells). The engine's `thickness_m` means net storage thickness. Using one
for the other overstates capacity by 1.5x to 128x across the observed range.

Donda et al. (2011) state the relationship explicitly:

> "h is the effective thickness, i.e. average thickness of aquifer x average net
> to gross ratio (m)"

and compute it "by considering the sum of thicknesses of each permeable
coarse-grained, sandy-gravelly layer within the potential reservoir", using
Gamma Ray logs. So a net-to-gross ratio is exactly what is required - and it is
exactly what this dataset lacks, because GR logs are only present as raster
scans.

Their Table 2 effective thicknesses (75-480 m) cannot be borrowed either: those
are basin-aggregated net sand over areas of 45-1,800 km2, not a net pay column
at a well. Adopting them alongside a well-scale area would be the same
inconsistency described in section 8.

Net thickness therefore remains an explicit user input, and
`gross_thickness_m` remains a separate, source-derived field.

## 10. Limitations

1. **Nothing here is site-specific.** A capacity figure from this scenario
   describes the scenario, not a well.
2. **Two of five inputs have no literature support at all** (`area_m2`,
   `thickness_m`), and both are linear multipliers.
3. **The efficiency range is not Italian** and is a simulation output, not a
   measurement.
4. **The porosity range is broad** (10-35%): the low and high ends differ by
   3.5x in capacity, and nothing selects between them for a given well.
5. **Hydrostatic pressure is assumed**, untested by any calibrating measurement
   for the five screened wells, and wrong for any over-pressured reservoir.
6. **Method-mixing risk.** The adopted efficiency and the adopted porosity come
   from a basin-scale methodology; the pilot applies them at a well. That
   mismatch is recorded here and in the scenario metadata, and is not resolved.
7. **The Donda et al. paper is internally inconsistent** on whether the upper
   efficiency case is 4% or 5%.

Correct terminology for anything produced under this scenario: **screening
scenario**, **scenario-based capacity**, **literature-constrained screening**.
Never *proven storage capacity*, *site capacity*, or *certified CO2 storage
resource*.

## 11. Phase 14: use in the approved model

The Phase 13 Model Contract (`docs/phase13-owner-decision-record.md`) adopts
the ranges reviewed here as the approved Monte Carlo priors: storage efficiency
Uniform(0.01, 0.04) (A6, statement above), porosity Uniform(0.10, 0.35)
(PROVISIONAL) and brine density Uniform(1020, 1100) kg/m3 (PROVISIONAL; a
declared project assumption, no primary source adopted, section 4). No value in
this review is changed.

In the public API, `literature-screening-v1` runs the approved model, which
differs from the scenario resolver described above in three places that are
contract decisions, not literature findings:

- Thickness: the caller supplies the storage-assessment interval (`z_top`,
  `z_base`); the thickness term is the derived gross `h_g = z_base - z_top`,
  not a net thickness (A1, M1). Sections 7 and 9 describe the net-thickness
  input of the legacy resolver.
- Pressure: `P_EOS = 101325 Pa + rho_brine * g * (z_state - z_wl)` at the
  interval midpoint `z_state`, for two named water-level scenarios
  (`GROUND_REFERENCE`, `SEA_LEVEL_SENSITIVITY`), instead of `rho * g * depth`
  at total depth (B1, M2, S1).
- Temperature: one corrected observation inside the interval, selected by the
  contract's rule (M3, R1), instead of the ingestion-time selection.

Applied through the legacy resolver (`ccs-ingest`, scenario JSON files) the
scenario behaves as documented above and its outputs are `NOT_VALIDATED`.
