# Scientific validation audit

Incremental audit of the scientific subsystems. One phase per section, each
independently verified against primary references before any change is made.

Governing rule: **do not try to make the model pass. Find out whether it
deserves to pass.**

Status legend: PASS / PASS WITH CAVEAT / REVIEW REQUIRED / NOT VALIDATED /
NOT APPLICABLE. Severity: CRITICAL / HIGH / MEDIUM / LOW.

---

## Phase 1 -- Thermodynamics / CO2 properties

Audited 2026-09-20 against `src/ccs_screen/properties.py` at commit `6c64830`.

### Method

Three independent lines of evidence:

1. **Algorithm re-implementation.** Peng-Robinson written fresh from Peng &
   Robinson (1976) and Peneloux et al. (1982), with the cubic solved by
   companion-matrix eigenvalues (`numpy.roots`) instead of the project's
   Cardano/trigonometric closed form. A solver bug in one cannot hide in the
   other.
2. **Reference EOS.** CoolProp 8.0.0 HEOS backend = Span & Wagner (1996), the
   reference equation of state for CO2.
3. **Benchmark grid.** 140 points spanning P = 1-35 MPa, T = 280-400 K, plus
   the critical point, six named cases, and seven saturation crossings.

### Equations verified line by line

| Element | Implementation | Reference form | Verdict |
| --- | --- | --- | --- |
| `a` | `0.45724 (R Tc)^2 / Pc * alpha` | 0.45724 R^2Tc^2/Pc | correct |
| `b` | `0.07780 R Tc / Pc` | 0.07780 R Tc/Pc | correct |
| `kappa` | `0.37464 + 1.54226w - 0.26992w^2` | PR 1976, valid w < 0.49 | correct |
| `alpha` | `(1 + kappa(1 - sqrt(Tr)))^2` | PR 1976 | correct |
| `A`, `B` | `aP/(RT)^2`, `bP/(RT)` | standard | correct |
| cubic | `Z^3 -(1-B)Z^2 +(A-2B-3B^2)Z -(AB-B^2-B^3)` | standard PR | correct |
| `ln phi` | `Z-1-ln(Z-B) - A/(2sqrt2 B) ln[(Z+(1+sqrt2)B)/(Z+(1-sqrt2)B)]` | PR fugacity | correct |
| Peneloux `c` | `0.40768 (RTc/Pc)(0.29441 - Z_RA)` | Peneloux 1982 | correct |
| translation | `v = v_EOS - c` | Peneloux 1982 | correct |

No mixing rules apply: the fluid is treated as pure CO2. This is stated in the
module docstring and is appropriate for screening, though real injection
streams contain impurities (see Remaining uncertainty).

### Independent verification

**Algorithm agreement: exact.** Across all 140 grid points, the project
implementation and the independent implementation agree to better than 1 part
in 10^9 when given the same constants. **Zero disagreements.** The Cardano
solver, the root filtering (`Z > B`), and the fugacity-based phase selection are
all correctly implemented.

**Phase selection: correct.** Across seven saturation crossings (260-303 K),
evaluated 3% either side of Psat, the vapour root was selected on the vapour
side and the liquid root on the liquid side in **7 of 7** cases. The
order-of-magnitude error the fugacity criterion exists to prevent does not
occur.

### Accuracy against Span & Wagner

| Region | n | mean abs error | max abs error |
| --- | --- | --- | --- |
| Dense storage (P>=10 MPa, 300-360 K) -- **primary use** | 42 | **5.15%** | **11.84%** |
| Supercritical, other | 54 | 4.50% | 13.58% |
| Subcritical | 14 | 2.01% | 5.26% |
| Low pressure / gas | 21 | 1.24% | 2.66% |
| Near-critical | 9 | 6.16% | 13.98% |

Named cases:

| Case | P (MPa) | T (K) | Span-Wagner | Implementation | Error |
| --- | --- | --- | --- | --- | --- |
| near-critical | 7.38 | 304.13 | 481.0 | 411.1 | **-14.5%** |
| dense storage | 15.0 | 333.15 | 604.1 | 584.1 | -3.3% |
| shallow gas | 1.0 | 300.0 | 18.6 | 18.7 | +0.6% |
| subcritical liquid | 5.0 | 280.0 | 893.9 | 925.2 | +3.5% |
| subcritical vapour | 2.0 | 280.0 | 43.8 | 44.3 | +1.3% |
| deep hot (MALOSSA-like) | 56.6 | 398.15 | 787.1 | 852.8 | **+8.3%** |

### Finding 1.1 -- the Peneloux shift degrades accuracy over most of the envelope

The correction is implemented exactly as published. The problem is its
**applicability**, not its arithmetic: a *constant* volume shift cannot track a
density deficit that varies strongly with pressure.

| | mean abs err | median | max |
| --- | --- | --- | --- |
| Peneloux ON (current) | **4.06%** | 2.86% | 13.98% |
| Peneloux OFF | **2.59%** | 1.99% | 16.67% |

**Disabling the shift is closer to Span & Wagner at 108 of 140 points (77%).**
Within the dense-storage window it improves only **16 of 42** points, and above
20 MPa it degrades essentially every point:

| P (MPa) | T (K) | Span-Wagner | ON | OFF |
| --- | --- | --- | --- | --- |
| 20 | 300 | 905.6 | +7.55% | **+0.64%** |
| 25 | 320 | 848.7 | +6.22% | **-0.13%** |
| 30 | 333 | 829.7 | +6.39% | **+0.15%** |
| 35 | 300 | 980.3 | **+11.84%** | +3.81% |

The shift does lower the worst case (13.98% vs 16.67%, both near-critical) and
does help below ~15 MPa, where most Italian pilot reservoirs sit. It is a
defensible trade only if the intended pressure window is stated and enforced.

*Revised (documentation only):* the phrase "where most Italian pilot reservoirs
sit" is not supported by the Piemonte pilot population. Under the current
pipeline pressure model, 14 of the 45 pilot wells with a depth are below 20 MPa,
and 15 are above 35 MPa. See *Finding 11.1 revision* (Phase 11). The measured
trade-off in this finding is unchanged.

**The module docstring is factually wrong.** It claims the shift "brings the
12-30 MPa / 320-355 K window to within a few percent". Measured in exactly that
window the maximum error is **8.20%** (30 MPa / 320 K), and the shift makes
7 of 15 points in that window worse.

Status: **REVIEW REQUIRED**, severity **MEDIUM**. Not silently changed.

Options, smallest first:
1. **Documentation only** (applied in this phase): correct the docstring to the
   measured envelope. No numerical change.
2. Restrict the shift to P < 15-20 MPa, where it helps.
3. Replace the constant shift with a temperature-dependent shift
   (e.g. Magoulas & Tassios), which is the standard remedy.
4. Disable translation and accept untranslated PR (mean 2.59%).

Option 1 is applied now. Options 2-4 change screening numbers and are out of
scope for an audit phase.

### Finding 1.2 -- eight of nine reference values in the test suite were wrong

`tests/test_properties.py` asserted against values labelled "Span-Wagner (NIST
Webbook)". Checked against CoolProp's Span & Wagner implementation:

| P (MPa) | T (K) | value asserted | true Span-Wagner | reference error |
| --- | --- | --- | --- | --- |
| 8.0 | 290.0 | 796.6 | 854.2 | **-6.74%** |
| 30.0 | 350.0 | 829.8 | 759.0 | **+9.33%** |
| 3.0 | 280.0 | 70.9 | 72.8 | -2.62% |
| 12.0 | 320.0 | 617.7 | 632.2 | -2.30% |
| 20.0 | 340.0 | 692.4 | 679.7 | +1.87% |
| 4.0 | 290.0 | 101.6 | 100.5 | +1.12% |
| 5.0 | 280.0 | 883.6 | 893.9 | -1.15% |
| 2.0 | 280.0 | 43.6 | 43.8 | -0.39% |
| 15.0 | 333.15 | 604.3 | 604.1 | +0.03% (correct) |

These were transcribed from memory, not retrieved from a reference
implementation. The 30 MPa / 350 K case is the most damaging: the test asserted
the code was within 8% of 829.8 and it passed at 790.8, but the true value is
759.0, so the test was **passing for the wrong reason** and would have
concealed a genuine 4.19% deviation.

Status: **REVIEW REQUIRED** -> corrected in this phase, severity **HIGH** (test
validity, not engine behaviour).

All nine values are now replaced with CoolProp-verified Span & Wagner values.
**No engine output changes.** The existing tolerances (8% dense / 20% liquid /
30% gas) still pass against the corrected references.

### Finding 1.3 -- near-critical error is large and intrinsic

At (7.3773 MPa, 304.1282 K) the implementation returns 411.1 kg/m3 against a
true 481.0 kg/m3, **-14.5%**. Cubic equations of state are known to fail near
the critical point; this is a property of Peng-Robinson, not a coding defect.

Status: **PASS WITH CAVEAT**, severity **LOW** for CCS screening -- storage
targets sit well away from the critical point. It matters only if a shallow
reservoir near 304 K / 7.4 MPa is ever screened.

### Finding 1.4 -- constants are not the problem

| Constant | Code | Span-Wagner | Deviation | Effect on density at 15 MPa/333 K |
| --- | --- | --- | --- | --- |
| Tc | 304.1282 K | 304.1282000 K | exact | 0.000% |
| Pc | 7.3773e6 Pa | 7 377 298.37 Pa | -1.6 Pa | 0.000% |
| omega | 0.225 | 0.22394 | +0.47% | **+0.039%** |
| MW | 0.0440095 | 0.0440098 kg/mol | -6.8e-4 % | +0.001% |

Setting every constant to its Span-Wagner value moves density by **0.039%** and
the error from -3.31% to -3.27%. `omega = 0.225` is a standard tabulated value
(Poling et al.). **No change recommended.**

Status: **PASS**, severity **LOW**.

### Finding 1.5 -- high-pressure regime is the worst case and is reachable

The hydrostatic pressure model produces ~56 MPa at MALOSSA 15's depth
(5387 m). At 56.6 MPa / 398 K the implementation is **+8.3%** high. Deep Italian
wells (TRECATE ~6.2-6.7 km, VILLA FORTUNA ~6.2 km) fall in the regime where the
Peneloux shift degrades most.

Status: **PASS WITH CAVEAT**, severity **MEDIUM**. Capacity is linear in
density, so this propagates one-for-one.

### Findings table

| Item | Status | Severity | Evidence | Action |
| --- | --- | --- | --- | --- |
| PR equations (a, b, kappa, alpha, A, B, cubic) | PASS | - | Line-by-line vs PR 1976 | None |
| Cubic root solver | PASS | - | 0/140 disagreements vs `numpy.roots` | None |
| Fugacity phase selection | PASS | - | 7/7 saturation crossings correct | None |
| Peneloux implementation (arithmetic) | PASS | - | Matches Peneloux 1982 | None |
| **Peneloux applicability** | **REVIEW REQUIRED** | **MEDIUM** | Worse at 108/140 points | Docstring corrected; options documented |
| **Test reference values** | **REVIEW REQUIRED** | **HIGH** | 8/9 wrong, worst 9.33% | **Corrected to CoolProp SW** |
| Near-critical accuracy | PASS WITH CAVEAT | LOW | -14.5% at critical point | Documented |
| High-pressure accuracy | PASS WITH CAVEAT | MEDIUM | +8.3% at 56.6 MPa | Documented |
| Critical constants | PASS | LOW | All deviations < 0.04% effect | None |
| Dense-window claim in docstring | REVIEW REQUIRED | LOW | "few percent" vs 8.20% measured | **Docstring corrected** |

### Scientific numbers changed?

**NO.** No equation, constant or algorithm was modified. Every density the
engine produces is byte-identical to before this phase. The changes are:
a corrected docstring, corrected test reference data, and new validation tests.

### Remaining uncertainty

1. **Pure CO2 only.** Real injection streams carry N2, O2, CH4, H2O. Impurities
   shift density by several percent; no mixing rule exists here. NOT VALIDATED.
2. **No independent check of CoolProp itself.** Span & Wagner (1996), as
   implemented in CoolProp, is used as the reference, not as a measurement. Its
   published abstract states an estimated density uncertainty of ±0.03% to
   ±0.05% only "in the technically most important region up to pressures of
   30 MPa and up to temperatures of 523 K". Most of this phase's 1–35 MPa grid
   lies in that region; the 30–35 MPa points do not, and the reference
   uncertainty there was not verified from the accessible primary text. Within
   the stated region the reference uncertainty is negligible against the 2-12%
   deviations measured.
3. **Grid resolution.** 140 points; a finer sweep could find a worse maximum
   than 13.98%.
4. **Below 280 K untested.** The triple point (216.6 K) and the solid region are
   outside the grid and outside any CCS storage condition.

---

## Phase 2 -- Dimensional analysis / unit consistency

Audited 2026-09-20. Scope: equations and runtime units only. Nothing was
inspected for correctness of *value* -- only for consistency of *dimension*.

### Method

1. **Hand derivation** of the dimensional product for every equation.
2. **Scaling verification**: multiply one input by 2 and confirm the output
   scales by the exponent the dimensional analysis predicts. This tests the
   implemented structure, not the documented one.
3. **Constant audit**: every numeric conversion constant in `src/` checked
   against its defining value.
4. **End-to-end trace**: one well from source degC to final Mt, unit named at
   every step, cross-checked by an independent route.

### Dimensional table -- storage capacity

`capacity.py::volumetric_storage_mass_kg`

| Symbol | Argument | Dimension | SI |
| --- | --- | --- | --- |
| A | `area_m2` | L^2 | m2 |
| h | `thickness_m` | L | m |
| phi | `porosity` | 1 | - |
| rho | `co2_density_kg_m3` | M L^-3 | kg/m3 |
| E | `storage_efficiency` | 1 | - |
| **M** | return value | **M** | **kg** |

`m2 * m * 1 * kg/m3 * 1 = kg`. The function name asserts kg; the derivation
agrees. Measured exponents (input x2 -> output ratio):

| Factor | Ratio | log2 | Expected |
| --- | --- | --- | --- |
| area_m2 | 2.000000 | +1.000000 | +1 |
| thickness_m | 2.000000 | +1.000000 | +1 |
| porosity | 2.000000 | +1.000000 | +1 |
| co2_density_kg_m3 | 2.000000 | +1.000000 | +1 |
| storage_efficiency | 2.000000 | +1.000000 | +1 |

All five exactly linear, as a pure product form requires.

### Dimensional table -- mass conversion

`1 Mt = 1e6 t = 1e6 x 1e3 kg = 1e9 kg`. `KG_PER_MT = 1e9`. Correct.
The two near-miss traps -- 1e3 (kg->t) and 1e6 (kg->kt) -- are both excluded.

### Dimensional table -- Theis drawdown

`pressure.py::theis_injection_delta_p_pa`

| Term | Expression | Dimension | SI |
| --- | --- | --- | --- |
| T (transmissivity) | k h / mu | - | m3/(Pa s) |
| S (storativity) | phi c_t h | - | m/Pa |
| u | r^2 S / (4 T t) | **1** | dimensionless |
| W(u) | `scipy.special.exp1` | 1 | dimensionless |
| **dp** | Q / (4 pi T) * W(u) | M L^-1 T^-2 | **Pa** |

`u` = `m2 * (m/Pa) / (m3/(Pa s) * s)` = `(m3/Pa)/(m3/Pa)` = dimensionless.
`dp` = `(m3/s) / (m3/(Pa s))` = `Pa`. Both correct.

This is the **petroleum** convention (T in m3/(Pa s), dp directly in Pa), not
the hydrogeology convention (T in m2/s, drawdown in metres of head). The two
differ by a factor rho g. The implementation is internally consistent in the
petroleum form throughout; no mixing of the two conventions was found.

Measured exponent for `thickness_m` is **exactly -1**, which is a non-obvious
confirmation. h appears in both T and S and cancels inside u, leaving
`dp = Q mu / (4 pi k h) * W(u)` with u independent of h. An error in either the
transmissivity or the storativity formulation would break that cancellation.
It holds to machine precision.

`permeability_m2` (log2 -0.877) and `viscosity_pa_s` (+0.865) are deliberately
non-integer: both appear in the prefactor *and* inside W(u). Correct behaviour,
not a defect.

### Dimensional table -- pressure

| Quantity | Expression | Dimension | SI |
| --- | --- | --- | --- |
| hydrostatic pressure | rho g z | kg/(m s2) | Pa |
| fracture pressure | depth * gradient | m * Pa/m | Pa |

`scenario.py::hydrostatic_pressure_pa` and `pressure.py::fracture_pressure_pa`.
Fracture pressure verified exactly linear in depth (ratio 2.000000 when depth
is doubled).

### Conversion constants

| Constant | Value | Defining value | Verdict |
| --- | --- | --- | --- |
| `KG_PER_MT` | 1e9 | 1 Mt = 1e9 kg | exact |
| `METRES_PER_FOOT` | 0.3048 | international foot, exact | exact |
| `FEET_PER_METRE` | 3.280839895013123 | 1/0.3048 | exact to 1e-16 |
| `KELVIN_OFFSET` | 273.15 | ITS-90 | exact |
| `STANDARD_GRAVITY_M_S2` | 9.80665 | CGPM 1901, exact | exact |
| `SECONDS_PER_YEAR` | 31 557 600 | 365.25 d (Julian year) | see note |
| `M2_PER_KM2` (frontend) | 1e6 | 1 km2 = 1e6 m2 | exact |

Note on `SECONDS_PER_YEAR`: the Julian year (365.25 d) is used rather than a
common year (365 d). The difference is 0.068% on injection time, which reaches
the answer only through `W(u)` and is far below every other uncertainty in the
model. Deliberate and harmless, but a choice rather than a definition.

### End-to-end chain (SALUZZO|1 shape, single realisation)

| Step | Value | Unit | Derivation |
| --- | --- | --- | --- |
| source temperature | 45.0 | degC | GEOTHOPICA |
| to_kelvin | 318.15 | K | +273.15, applied once |
| depth | 1527.5 | m | source |
| brine density | 1050 | kg/m3 | scenario |
| g | 9.80665 | m/s2 | constant |
| P = rho g z | 1.5729e7 | Pa | kg/(m s2) |
| CO2 density | 758.4 | kg/m3 | PR + Peneloux |
| A, h, phi, E | 8e7, 35, 0.18, 0.025 | m2, m, -, - | user + scenario |
| mass | 9.5561e9 | kg | m2*m*1*kg/m3*1 |
| **capacity** | **9.556** | **Mt** | kg / 1e9 |

Cross-checked by an independent route: pore volume `A h phi` = 5.0400e8 m3;
CO2 volume `x E` = 1.2600e7 m3; mass `x rho` = 9.5561e9 kg. Identical.

Temperature is converted from degC exactly once, at ingestion. No second
conversion exists anywhere downstream; the EOS receives kelvin.

### Unit metadata vs stored values (live API, real well)

Every `screening_inputs` entry was checked against a physical plausibility band
for its own declared unit:

| Field | Value | Declared unit | Plausible for that unit |
| --- | --- | --- | --- |
| area_m2 | 8e7 | m2 | yes |
| thickness_m | 35 | m | yes |
| porosity | [0.10, 0.35] | - | yes |
| pressure_pa | [1.528e7, 1.648e7] | Pa | yes |
| temperature_k | 318.15 | K | yes |
| storage_efficiency | [0.01, 0.04] | - | yes |

No field carries a unit label inconsistent with its magnitude. The result key
is `scenario_based_capacity_mt`, so the unit travels in the field name itself.

Display conversions in the frontend (`lib/format.ts`) were checked in the same
way: `m2 -> km2` (/1e6), `Pa -> MPa` (/1e6), `- -> %` (x100), `K` unchanged.
The dimensionless-to-percent rule applies only to porosity and storage
efficiency, both of which are genuine fractions.

### Finding 2.1 -- a pressure/temperature swap would be silently accepted

`co2_density_kg_m3(pressure_pa, temperature_k)` takes two positional floats,
both validated only as `> 0`. Nothing distinguishes them dimensionally at
runtime.

There is exactly **one** call site outside the module (`monte_carlo.py:96`),
and it passes them in the correct order. But a swapped call returns
`1.18e-07 kg/m3` instead of `584.1 kg/m3` without raising.

Status: **PASS WITH CAVEAT**, severity **LOW**. No defect exists today; this is
a latent trap, not a bug. Not changed: adding a plausibility guard would alter
behaviour at the edges for no present benefit, and the change-control rule for
this audit is to document rather than silently harden. A regression test now
pins the single call site and characterises the swap, so the trap stays visible.

### Finding 2.2 -- depth carries a unit but not a reference surface

`depth_m` is unambiguously metres. What it is measured *from* is
`depth_datum = "unknown"` for the pilot wells, and `depth_msl_m` is correctly
reported MISSING rather than assumed.

This is not a unit error -- the dimension is right -- but `z` in `P = rho g z`
is a true depth below a datum only if the datum is known.

Status: **NOT APPLICABLE** to Phase 2 (dimensionally correct). Carried to
**Phase 4**.

### Findings table

| Item | Status | Severity | Evidence | Action |
| --- | --- | --- | --- | --- |
| Capacity dimensional product | PASS | - | 5/5 exponents exactly +1; product = kg | None |
| Mt conversion | PASS | - | 1e9 correct; both near-miss traps excluded | None |
| Theis dimensional consistency | PASS | - | u dimensionless; dp in Pa; h cancels in u exactly | None |
| Hydrostatic pressure units | PASS | - | kg/(m s2) = Pa | None |
| Fracture pressure units | PASS | - | m * Pa/m = Pa, exactly linear | None |
| Conversion constants | PASS | - | All match defining values | None |
| Temperature chain | PASS | - | degC -> K once; no double conversion | None |
| Unit metadata vs magnitude | PASS | - | 6/6 fields plausible for declared unit | None |
| Frontend display conversions | PASS | - | m2/Pa/fraction handled; % only on fractions | None |
| **P/T positional swap** | **PASS WITH CAVEAT** | **LOW** | Swapped call returns 1.18e-07 silently | Test pins call site |
| `SECONDS_PER_YEAR` Julian year | PASS WITH CAVEAT | LOW | 0.068% vs common year | Documented |
| Depth reference surface | NOT APPLICABLE | - | Unit correct; datum unknown | Deferred to Phase 4 |

### Scientific numbers changed?

**NO.** Phase 2 was inspection only. No file under `src/` was modified.

### Downstream impact

None, and that is the useful result: **no unit error was found anywhere in the
chain**. Phases 3, 5, 7, 10 and 11 can now attribute any discrepancy against a
hand calculation to the physics rather than to a conversion, which is exactly
what those phases need in order to be conclusive.

### Remaining uncertainty

1. **Dimensional correctness is not numerical correctness.** A formula can be
   dimensionally perfect and still carry the wrong coefficient. Phases 3-5 test
   values; Phase 2 tested only dimensions.
2. **The petroleum transmissivity convention** was verified self-consistent,
   not verified against an external Theis reference value. That is Phase 5.
3. **Impurity effects** would change the molar mass and therefore the kg stored
   per m3 of pore space. Out of scope, as in Phase 1.

---

## Phase 3 -- Storage-capacity equation

Audited 2026-09-20. Scope: `capacity.py::volumetric_storage_mass_kg` and the
semantics of its five arguments. The EOS (Phase 1) and the pressure model
(Phase 4) were not touched.

### The equation

`M = A h phi rho E`

| Symbol | Argument | Physical meaning as implemented |
| --- | --- | --- |
| A | `area_m2` | Structural closure area of the storage complex |
| h | `thickness_m` | Net storage thickness inside the closure |
| phi | `porosity` | Pore volume fraction (qualification: see Finding 3.2) |
| rho | `co2_density_kg_m3` | CO2 density at reservoir P, T |
| E | `storage_efficiency` | Fraction of pore volume CO2 can occupy |

Read as a chain: `A h` is bulk rock volume, `x phi` is pore volume, `x E` is the
sub-volume CO2 actually occupies, `x rho` converts that volume to mass. Each
step is a volume until the last, which is the only place mass enters. That
ordering is what makes E separable from phi rather than a second porosity.

### Independent implementation

A second implementation was written using exact rational arithmetic
(`fractions.Fraction`), structured as the four-step chain above rather than as a
single product, and with no import of the production function.

| Case | A (m2) | h (m) | phi | rho | E | Independent | Production | Rel. error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Closure, low end | 5.0e7 | 20 | 0.10 | 650 | 0.01 | 0.6500 Mt | 0.6500 Mt | 0 |
| Closure, mid | 8.0e7 | 35 | 0.18 | 758.4 | 0.025 | 9.5558 Mt | 9.5558 Mt | 0 |
| Closure, high end | 2.0e8 | 60 | 0.35 | 850 | 0.04 | 142.8000 Mt | 142.8000 Mt | 2.1e-16 |
| Donda Abruzzi 1 | 1.75e8 | 80 | 0.25 | 700 | 0.01 | 24.5000 Mt | 24.5000 Mt | 0 |
| Donda Marche 1 | 6.15e8 | 255 | 0.35 | 700 | 0.04 | 1536.8850 Mt | 1536.8850 Mt | 0 |
| Donda Bradanica | 5.20e8 | 480 | 0.25 | 700 | 0.01 | 436.8000 Mt | 436.8000 Mt | 0 |

Six cases, maximum relative error 2.1e-16, which is one unit in the last place
of a double. The last three use the published geometry of real Italian
reservoirs from Donda et al. (2011) Table 2, so the agreement is against
external numbers rather than numbers chosen to agree.

**The arithmetic is correct.** Nothing in Phase 3 disputes the implementation.

### Sensitivity

Elasticity `d(ln M)/d(ln x)`, measured by +1% perturbation:

| Parameter | Elasticity |
| --- | --- |
| area_m2 | +1.000000000 |
| thickness_m | +1.000000000 |
| porosity | +1.000000000 |
| co2_density_kg_m3 | +1.000000000 |
| storage_efficiency | +1.000000000 |

All five exactly unity, and all strictly increasing: the model is monotonic in
every parameter with no interaction terms. This is the expected behaviour of a
pure product, and it has a consequence worth stating plainly -- **a factor-of-N
error in any single input is a factor-of-N error in the answer.** There is no
damping anywhere in this equation. That is why the semantic findings below
matter more than the arithmetic.

### Gross vs net thickness -- the central question

The implementation's `thickness_m` means **net storage thickness**, and this is
enforced structurally rather than by comment:

- `ThicknessKind` is a three-valued enum: `GROSS_STRATIGRAPHIC`, `NET_STORAGE`,
  `AQUIFER_HYDRAULIC`.
- `NormalizedWellRecord` carries `gross_thickness_m` and
  `net_storage_thickness_m` as separate fields.
- `net_storage_thickness_m` defaults to MISSING with the reason "net thickness
  is not derivable from gross stratigraphy without net-to-gross".
- `completeness.py` maps `thickness_m` to `None` -- no source field satisfies it.
- `NET_THICKNESS_POLICY_STATEMENT` is attached to the scenario, the API
  interpretation block and the user-input spec.
- `USER_INPUT_SPEC["thickness_m"]["not_inferred_from"]` names "gross
  stratigraphic thickness" and "total well depth" explicitly.

A grep of `src/` found **no code path that converts gross to net**, and no
net-to-gross factor is defined anywhere. The requirement not to invent one is
already satisfied by the existing design; Phase 3 introduced nothing.

Magnitude of the error this prevents, using the observed gross range across the
pilot wells (91-2,557 m) against a plausible net range (20-60 m):

| Gross | Net | Overstatement if substituted |
| --- | --- | --- |
| 91 m | 60 m | 1.5x |
| 91 m | 20 m | 4.6x |
| 2,557 m | 60 m | 42.6x |
| 2,557 m | 20 m | 127.9x |

`records.py` and `docs/ingestion.md` state this as "20-50x". That is
representative of the middle of the distribution but not of its envelope: the
true range is 1.5x to 128x. Documentation-only discrepancy, recorded as
Finding 3.4.

### Finding 3.1 -- E is defined against gross thickness in its own source

**REVIEW REQUIRED. Severity MEDIUM. Conservative direction.**

The adopted `storage_efficiency` of 1-4% is the USDOE Subgroup figure quoted by
CSLF-T-2008-04. In the DOE/NETL volumetric formulation that produced it, the
terms the coefficient multiplies are defined as:

> "...is the **gross thickness** of the cell i, j, k; ...is the **total
> porosity** of the assessed formation volume; ...and is the storage efficiency
> coefficient"

That is, E is calibrated to absorb the reduction from gross to net and from
total to effective porosity. The public API instead requires **net** thickness
and then applies E on top of it. If a caller supplies a genuinely net thickness,
the net-to-gross reduction is applied twice.

Bounding the effect with published sub-factor ranges:

| E_hn/hg | E_phie/phitot | Understatement |
| --- | --- | --- |
| 0.80 | 0.90 | 1.4x |
| 0.50 | 0.75 | 2.7x |
| 0.20 | 0.50 | 10.0x |

So the implementation is **systematically conservative**, plausibly by a factor
of 1.4 to 10, for the thickness term.

Two things stop this from being a defect to correct:

1. **The inconsistency is in the literature, not in this code.** Donda et al.
   (2011), the regional study that applied the same 1-4% to Italy, tabulate an
   "Effective thickness" column (75-480 m) and apply E to "the total pore
   volume" computed from it. Donda therefore already applies a DOE
   gross-thickness coefficient to an effective thickness. The implementation
   inherits that usage from its own cited precedent rather than inventing it.
2. **Correcting it would change every capacity number.** Dividing E by an
   assumed net-to-gross, or switching the input to gross thickness, are both
   new scientific assumptions, and the change-control rule for this audit
   forbids introducing one silently.

Recorded as REVIEW REQUIRED. No code changed. The decision belongs to the
project owner, and the honest framing is: *the screening number is conservative
by an unquantified factor, because a basin-scale efficiency coefficient is being
applied to a closure-scale net volume.*

This is the thickness-axis twin of the area-axis mismatch already disclosed in
`SCALE_MISMATCH_WARNING`. That warning's `detail` field does already say "area
and net thickness are supplied at closure scale", so the disclosure exists; what
was missing is the reason it matters for thickness specifically, which this
section now supplies.

### Finding 3.2 -- porosity is not qualified as total or effective

**REVIEW REQUIRED. Severity LOW.**

A grep of `src/`, `docs/` and `frontend/` found the strings "total porosity",
"effective porosity" and "connected porosity" **zero times**. The parameter is
documented only as "Pore volume fraction".

The evidence resolves it, but only indirectly. Donda et al. derive the 10-35%
range "from sonic-log P-wave velocities and empirical functions (Schlumberger,
2000)". Sonic-log porosity transforms (Wyllie time-average, Raymer-Hunt-Gardner)
return **total** porosity, not effective. The adopted range is therefore total
porosity by construction -- which is the quantity the DOE formulation expects,
so on this axis the pairing with E is consistent and no double-count arises.

The defect is that this reasoning appears nowhere in the code or docs, so a
reader cannot tell whether the pairing is correct by luck or by design. This is
a documentation gap, classified REVIEW REQUIRED rather than fixed inline because
confirming the sonic-transform reading against the Schlumberger reference is
Phase 9 work, not Phase 3 work.

### Finding 3.3 -- area type is declared but the declaration is not enforceable

**PASS WITH CAVEAT. Severity LOW.**

`USER_INPUT_SPEC["area_m2"]` declares the required meaning -- "Structural
closure area of the storage complex. Must come from a depth-structure map or
equivalent interpretation" -- and enumerates four things it must not be derived
from (licence boundaries, concession polygons, administrative boundaries, well
spacing, arbitrary radius). `AREA_POLICY_STATEMENT` repeats this at the scenario
boundary and in every result.

The distinction between basin, licence, closure and reservoir area is therefore
made clearly. What the code cannot do is verify which one the caller supplied:
`area_m2` is a bare positive float bounded only by `(0, 1e12)` exclusive. A
basin-scale area passed as a closure area is accepted and silently inflates the
answer linearly.

No change proposed. Validation cannot distinguish 8e7 m2 of closure from 8e7 m2
of licence; the disclosure is the only available control and it is already
present and prominent.

### Finding 3.4 -- the "20-50x" gross/net figure understates its own envelope

**PASS WITH CAVEAT. Severity LOW. Documentation only.**

`records.py:89` and `docs/ingestion.md:177` state that substituting gross for net
thickness "overstates capacity by 20-50x". Measured against the observed gross
range and a 20-60 m net range, the envelope is **1.5x to 128x**. The stated
figure is a fair midpoint but is not the range.

Not corrected in this phase: the sentence is a warning whose purpose is to
convey "wrong by more than an order of magnitude", which it does. Changing it
touches a frozen module's docstring for no scientific gain. Recorded so the
number is not mistaken for a measured bound.

### Finding 3.5 -- validation bounds phi and E separately, not their product

**PASS. Severity LOW.**

`volumetric_storage_mass_kg` rejects any non-positive argument and rejects
`porosity >= 1` or `storage_efficiency >= 1`. Measured behaviour:

| Input | Result |
| --- | --- |
| porosity = 1.0 | rejected |
| porosity = 0.999 | accepted |
| storage_efficiency = 1.0 | rejected |
| storage_efficiency = 0.99 | accepted |
| area_m2 = 0 | rejected |
| thickness_m = -1 | rejected |
| porosity = 0.9 AND storage_efficiency = 0.9 | accepted |

The last row puts CO2 in 81% of the bulk rock volume, which is geologically
absurd. It is not, however, *mathematically* inconsistent: phi < 1 and E < 1
guarantee phi E < 1, so the CO2 volume never exceeds the rock volume. The
function's contract is arithmetic, and plausibility is enforced upstream --
`config.BOUNDS` and the literature scenario constrain phi to 0.10-0.35 and E to
0.01-0.04.

Classified PASS. Tightening the guard would reject inputs a screening tool must
still be able to describe, which is the stated design intent of `config.BOUNDS`
("These reject impossible values, not merely unusual ones").

### Audit of the user-input caveat

The existing caveat -- that area and net thickness are user-supplied -- was
checked for completeness rather than taken at face value:

| Requirement | Status |
| --- | --- |
| No default value for `area_m2` anywhere in the code path | Confirmed |
| No default value for `thickness_m` anywhere in the code path | Confirmed |
| Omitting either returns `blocked`, not a computed number | Confirmed |
| Neither inferred from licence/concession polygons | Confirmed |
| `thickness_m` never derived from gross stratigraphy | Confirmed, no code path exists |
| Meaning declared at the point of entry | Confirmed, `USER_INPUT_SPEC` |
| Declared in every result | Confirmed, `INTERPRETATION` |
| Scale mismatch disclosed | Confirmed, `SCALE_MISMATCH_WARNING` |

The caveat is accurate and is enforced structurally, not merely asserted. It is
also load-bearing: with both elasticities exactly +1, these two uncited inputs
jointly control the answer linearly.

### Findings table

| Item | Status | Severity | Evidence | Action |
| --- | --- | --- | --- | --- |
| `M = A h phi rho E` arithmetic | PASS | - | 6 cases vs exact rational arithmetic, max rel. error 2.1e-16 | None |
| Term ordering (pore volume before mass) | PASS | - | Independent four-step chain agrees exactly | None |
| Monotonicity and elasticity | PASS | - | All 5 elasticities exactly +1.000000000, strictly increasing | None |
| Gross/net separation | PASS | - | Separate enum, separate fields, no conversion path in `src/` | None |
| **E applied to net thickness** | **REVIEW REQUIRED** | **MEDIUM** | DOE defines E on gross thickness; 1.4x-10x conservative | Documented, no code change |
| **Porosity total vs effective** | **REVIEW REQUIRED** | **LOW** | Zero occurrences of the qualification anywhere; resolved only via sonic-log derivation | Documented, Phase 9 to confirm |
| Area type declared but unverifiable | PASS WITH CAVEAT | LOW | Spec declares closure area; validation is a bare positive float | None available |
| "20-50x" gross/net figure | PASS WITH CAVEAT | LOW | Measured envelope 1.5x-128x | Recorded, not edited |
| phi/E bounded separately | PASS | LOW | phi E < 1 guaranteed; plausibility enforced upstream | None |
| User-input caveat | PASS | - | 8/8 requirements confirmed structurally | None |

### Scientific numbers changed?

**NO.** No file under `src/` was modified in Phase 3.

### Downstream impact

**Phase 3 does not block downstream phases.** The distinction that matters:

- The **equation** is correct, the **implementation** is correct, and the
  **arithmetic** is exact. Nothing downstream is computing on a broken formula.
- Findings 3.1 and 3.2 are about the **semantics of two inputs**, not about the
  transform applied to them. Monte Carlo (Phase 7), sensitivity (Phase 8) and
  the end-to-end traces (Phase 10) all operate on whatever values are supplied
  and are unaffected by what those values are taken to mean.

The one real constraint is on **interpretation**, and it must be carried
forward: any Phase 10 or Phase 11 capacity number is conservative by the
unquantified Finding 3.1 factor. That is a caveat on the reading of the result,
not a defect in its calculation, so `BLOCKED BY UPSTREAM SCIENTIFIC ISSUE` does
not apply.

Phase 9 inherits both REVIEW REQUIRED items, which is where they belong: both
are questions about what the cited sources actually say.

### Remaining uncertainty

1. **Finding 3.1 is unquantified.** The 1.4x-10x bound uses published
   sub-factor ranges, not a value derived for Piemonte. Narrowing it needs a
   net-to-gross estimate that no source in this repository provides.
2. **The DOE decomposition was verified via a secondary source.** The primary
   CSLF-T-2008-04 and 2015 Task Force PDFs were unreachable (DNS failure on
   `fossil.energy.gov` and `hgeo.energy.gov`). The gross-thickness and
   total-porosity definitions are quoted from a peer-reviewed article restating
   the DOE formulation. Primary-source confirmation is Phase 9 work.
3. **Finding 3.2 rests on an inference** about sonic-log transforms returning
   total porosity. It is a standard result, but Donda et al. do not state it,
   and the Schlumberger (2000) reference was not consulted.
4. **Area type cannot be validated**, only declared. A caller who supplies a
   licence-boundary area gets a linearly inflated answer and no warning beyond
   the standing policy statement.

---

## Phase 4 -- Pressure model

Audited 2026-09-20. Scope: `scenario.py::hydrostatic_pressure_pa`,
`pressure.py::fracture_pressure_pa`, `pressure.py::allowable_delta_p_pa`, and
the depth quantity all three consume. The Theis solution itself is Phase 5.

### The two pressure models

| Model | Implementation | Expression | Result |
| --- | --- | --- | --- |
| Reservoir pressure | `ScreeningScenario.hydrostatic_pressure_pa` | `rho_brine * g * z` | Pa |
| Fracture pressure | `pressure.fracture_pressure_pa` | `z * fracture_gradient` | Pa |
| Injection headroom | `pressure.allowable_delta_p_pa` | `max(SF * P_frac - P_init, 0)` | Pa |

The two pressure models are **independently defined**. Fracture pressure is not
derived from hydrostatic pressure: it uses its own constant,
`DEFAULT_FRACTURE_GRADIENT_PA_M = 15 000 Pa/m`, and never reads the brine
density. They meet only in `allowable_delta_p_pa`, where one is subtracted from
the other -- which is exactly where a convention mismatch would bite.

### Hand calculations vs independent implementation

Exact rational arithmetic, no production import:

| Case | rho (kg/m3) | z (m) | Gradient (Pa/m) | Independent | Production | Rel. error |
| --- | --- | --- | --- | --- | --- | --- |
| Shallow pilot | 1020 | 897.0 | 10 002.8 | 8.9725 MPa | 8.9725 MPa | 0 |
| SALUZZO-like | 1050 | 1527.5 | 10 297.0 | 15.7286 MPa | 15.7286 MPa | 0 |
| Mid | 1060 | 3000.0 | 10 395.0 | 31.1851 MPa | 31.1851 MPa | 1.2e-16 |
| Deep pilot | 1100 | 6694.0 | 10 787.3 | 72.2103 MPa | 72.2103 MPa | 2.1e-16 |

Linearity confirmed exactly in both variables: depth x2/x3/x10 gives pressure
ratios 2.000000000000 / 3.000000000000 / 10.000000000000, and the same for
density. **The arithmetic is correct.**

### Finding 4.1 -- the model computes GAUGE pressure and both consumers need ABSOLUTE

**REVIEW REQUIRED. Severity MEDIUM. Two opposing directions.**

A grep of `src/`, `docs/` and `frontend/` for "atmospher", "101325", "gauge",
"absolute press", "psia" and "psig" returns **zero matches**. Atmospheric
pressure is never added anywhere, and the convention is never declared anywhere.

The behaviour settles it: `hydrostatic_pressure_pa(0.0)` returns **0.0 Pa**, not
101 325 Pa. A zero-depth point is at vacuum, so the model is **gauge** --
`P = rho g z` is the weight of the fluid column alone. The physically complete
form is `P_abs(z) = P_atm + rho g z`.

Both consumers require absolute pressure:

1. **Peng-Robinson (`properties.py`)** takes thermodynamic pressure, which is
   absolute by definition. There is no reading of the EOS under which a gauge
   pressure is correct.
2. **The fracture comparison.** A fracture gradient of 15 000 Pa/m applied from
   surface yields an absolute fracture pressure; subtracting a gauge initial
   pressure from it overstates the headroom by exactly `P_atm`.

Measured effect of supplying gauge where absolute is required:

| Case | z (m) | P_atm as % of P | CO2 density bias | Headroom overstated |
| --- | --- | --- | --- | --- |
| Shallow pilot | 897 | 1.129% | **-4.146%** | 3.338% |
| SALUZZO-like | 1527.5 | 0.644% | -0.602% | 2.115% |
| Mid | 3000 | 0.325% | -0.221% | 1.100% |
| Deep pilot | 6694 | 0.140% | -0.085% | 0.561% |

The density bias is far larger than the 1.1% pressure offset at the shallow
well because 897 m / 315 K sits near the steep part of the CO2 isotherm, where
a small pressure change moves density a lot. This is the same near-critical
sensitivity documented in Phase 1, Finding 1.3.

Note the two effects run **in opposite directions** and therefore do not
cancel: capacity is understated by up to 4.1%, while injection headroom is
overstated by up to 3.3%.

**Smallest possible correction**, offered but *not applied*: add `P_atm` once,
at the single point where hydrostatic pressure is produced --

```
return (P_ATM + gradient[0] * z, P_ATM + gradient[1] * z)
```

with `P_ATM = 101_325.0` Pa. One constant, one call site, no refactor. It is not
applied here because it changes every capacity and every headroom number, and
the standing instruction for this audit is that scientific numbers do not change
without the project owner's decision.

### Finding 4.2 -- z is not datum-corrected, and the correction layer is bypassed

**REVIEW REQUIRED. Severity HIGH. Direction not established.** *(Original
status "Anti-conservative for capacity", superseded 2026-09-24. The title and
body below are the original Phase 4 reasoning; the current framing is the
revision note at the end of this finding and* Finding 4.2 / 10.2 revision
*in Phase 10.)*

This is the largest effect found in Phase 4.

The ingestion layer handles depth datums carefully and correctly:

- `DepthDatum` enumerates MSL, rotary table, ground level, kelly bushing,
  unknown.
- `DepthMeasurement.to_msl()` **raises** when the datum is unknown or its
  elevation is unavailable, rather than guessing.
- `_derive_depth_msl` sets `depth_msl_m` to MISSING with the reason "source does
  not state a depth datum; cannot express as sub-sea depth".
- For the pilot wells, `depth_datum` is `UNKNOWN`, so `depth_msl_m` is MISSING.

The pressure derivation then bypasses all of it. `scenario.py:333` reads
`float(record.depth_m.value)` -- the raw, uncorrected, datum-unknown depth --
and uses it as `z` in `P = rho g z`. The module that refuses to state a sub-sea
depth is not consulted; the uncorrected depth is used as though it were one.

The magnitude is quantifiable because the source documents state the elevations.
AGIP composite logs read *"Tutte le profondita sono riferite al piano tavola
rotary"*, and the rotary table stood **120.00 m** above sea level at MALOSSA 15
and **238.7 m** at CAVAGLIETTO 1. The brine column starts at the water table,
not at the rotary table; the air in between contributes nothing.

| Datum elevation | rho = 1020 | rho = 1100 |
| --- | --- | --- |
| 120.00 m (MALOSSA 15) | P overstated by 1.200 MPa | 1.294 MPa |
| 238.7 m (CAVAGLIETTO 1) | P overstated by 2.388 MPa | 2.575 MPa |

Expressed against the corrected pressure, with rho = 1050:

| Well | z raw | P raw | z sub-sea | P corrected | Overstatement |
| --- | --- | --- | --- | --- | --- |
| MALOSSA 15 | 1500 m | 15.445 MPa | 1380 m | 14.210 MPa | **+8.70%** |
| Elevation 238.7 m on a 900 m well | 900 m | 9.267 MPa | 661.3 m | 6.809 MPa | **+36.10%** |

The 900 m figure is the illustrative case `docs/ingestion.md` already uses; it
is not CAVAGLIETTO 1's actual total depth. That document states the same error
as "27%", which is the same discrepancy expressed as a fraction of the raw depth
rather than of the corrected one. Both are correct; they differ only in
denominator.

Direction of the error: overstated `z` gives overstated `P`, which gives
overstated CO2 density, which gives **overstated capacity**. It is
anti-conservative, and it is the opposite direction from Phase 3 Finding 3.1.

Not corrected, and correction is not currently possible: the datum is unknown
for these wells, so there is nothing to subtract. Inventing one is explicitly
forbidden. What *is* missing is disclosure -- the provenance `rationale` for
derived pressure says only "Normally-pressured hydrostatic assumption. No
measured pressure exists in any source, so this is untested for this well." It
does not say that `z` is an uncorrected along-hole depth from an unstated datum.
That is the gap, and it is a documentation gap rather than a code defect.

**Phase 2, Finding 2.2 is hereby resolved and escalated.** Phase 2 deferred the
`depth_datum = "unknown"` item here on the grounds that the unit was correct.
It is: the dimension is metres and `P = rho g z` is dimensionally sound. The
problem is not the unit of `z` but its **origin**.

**Revised 2026-09-24 (documentation only).** This finding merged two separate
questions. They are now separated in *Finding 4.2 / 10.2 revision* (Phase 10):

- **Depth datum: supported for four wells.** The workbook depths for SALUZZO|1,
  DESANA|1, ASTI|1 and MALOSSA|15 are already below-ground depths. No
  rotary-table air gap remains in `z`.
- **Hydraulic reference: unresolved.** Where the water level stands, and so where
  the brine column begins, is not established by any evidence in the repository.

The sentence *"The brine column starts at the water table, not at the rotary
table"* is therefore not a description of the current code, which starts the
column at the depth reference (ground level for those four wells). The magnitude
tables, the "Direction of the error" paragraph and the statement that the datum
is unknown are kept unchanged above as history. They are **not** measurements of
a datum error, and the direction they state is not established.

### Finding 4.3 -- z is total well depth, not a reservoir reference depth

**REVIEW REQUIRED. Severity MEDIUM. Anti-conservative.**

`docs/ingestion.md` documents `depth_m` as *"total depth; datum usually
unstated"*, and the three ingestion call sites capture it from the sources'
total-depth columns.

Pressure is therefore evaluated at **total depth**: the deepest point the bit
reached. That is neither the reservoir top, nor its base, nor its midpoint. In
a well drilled through and past its objective, TD sits below the storage
interval, so the pressure used to evaluate CO2 density is the pressure at a
depth where no storage occurs.

No reservoir reference depth exists anywhere in the codebase. `thickness_m` is
a net thickness with no associated top depth, so even a midpoint cannot be
constructed -- `top + h/2` has no `top`. Note that the temperature path does
better: `RESERVOIR_DEPTH_FRACTION = 0.85` at least filters temperature
observations to those near TD. The pressure path has no equivalent.

No correction proposed. Choosing a reservoir datum is exactly the kind of
invented reference depth this phase is forbidden to introduce.

### Finding 4.4 -- depth is measured depth, not true vertical depth

**PASS WITH CAVEAT. Severity LOW to MEDIUM.**

`StratigraphicInterval` is documented as *"one chronostratigraphic unit as
logged, in metres along-hole"*, so depths are **MD**. `units.py` recognises a
`v.` annotation in strings such as `5500 v.5497~`, which is a true-vertical
note, but it is treated as an approximation marker and no TVD field is stored.

`P = rho g z` requires **TVD**: the hydrostatic column is vertical. For a
vertical well MD = TVD and nothing is wrong. For a deviated well MD > TVD and
the pressure is overstated.

No deviation survey exists in any source in this repository, so the size of the
effect is unknown and unbounded from the available data. The pilot wells are
1950s-1980s onshore exploration wells, which were predominantly vertical, so
the effect is most likely small -- but "most likely" is not a measurement.

### Finding 4.5 -- the fracture gradient is physically sensible but uncited

**PASS WITH CAVEAT. Severity LOW.**

`DEFAULT_FRACTURE_GRADIENT_PA_M = 15 000 Pa/m`. Converted independently:

- `15 000 Pa/m x 0.3048 m/ft / 6894.757 Pa/psi` = **0.6631 psi/ft**, inside the
  0.6-0.8 psi/ft band normally quoted for normally-pressured clastic sequences.
- Equivalent mud weight `15 000 / 9.80665` = **1529.6 kg/m3 = 1.530 SG**, a
  routine value.

Resulting fracture-to-hydrostatic ratios are physically sensible and decline
with depth as expected:

| Case | P_frac | P_hyd | Ratio | Headroom |
| --- | --- | --- | --- | --- |
| Shallow pilot | 13.455 MPa | 8.972 MPa | 1.500 | 3.137 MPa |
| SALUZZO-like | 22.913 MPa | 15.729 MPa | 1.457 | 4.893 MPa |
| Mid | 45.000 MPa | 31.185 MPa | 1.443 | 9.315 MPa |
| Deep pilot | 100.410 MPa | 72.210 MPa | 1.391 | 18.159 MPa |

Headroom was recomputed independently as `max(0.9 * z * 15000 - rho g z, 0)`
and matched the production function exactly in 4 of 4 cases.

Two caveats. The gradient is a **single depth-independent constant** -- real
fracture gradients vary with lithology, and the ratio drifting from 1.50 to
1.39 across the depth range is an artefact of the constant, not a modelled
compaction trend. And unlike `storage_efficiency` and `porosity`, it carries
**no citation**: a grep of `docs/` for "fracture" finds no literature entry for
it. The value is defensible; its provenance is not documented to the standard
the rest of the project sets.

The same applies to `DEFAULT_SAFETY_FACTOR = 0.9`, documented only as "the
fraction of the fracture pressure regulators typically allow" with no regulator
named.

### Finding 4.6 -- brine density is a fixed screening assumption, appropriately

**PASS.**

`literature-screening-v1` declares `brine_density_kg_m3 = (1020.0, 1100.0)`,
giving a gradient of **10 002.8 to 10 787.3 Pa/m (10.00-10.79 kPa/m)**.

Independent reference points: pure water at 4 C gives 9806.6 Pa/m, seawater at
1025 kg/m3 gives 10 051.8 Pa/m, and a near-saturated NaCl brine at 1200 kg/m3
gives 11 768 Pa/m. The declared range sits between seawater and moderately
saline formation water, which is the correct band for normally-pressured
Po Basin formation water.

It is **not** temperature- or salinity-dependent: it is a flat, declared range,
carried as a scenario assumption and surfaced in the derivation string. For
screening this is appropriate, and it is honest -- the range is declared rather
than a single number, and the derived pressure is returned as a `(low, high)`
pair that propagates into the Monte Carlo rather than collapsing to a point.

The assumption that is doing the real work is **normal pressure**, not the
density value. An over- or under-pressured reservoir breaks this model
entirely, and the provenance rationale says exactly that: "Normally-pressured
hydrostatic assumption. No measured pressure exists in any source, so this is
untested for this well."

### Finding 4.7 -- negative depth is accepted by the hydrostatic model

**PASS WITH CAVEAT. Severity LOW.**

Edge-case behaviour:

| Call | Result |
| --- | --- |
| `hydrostatic_pressure_pa(0.0)` | `(0.0, 0.0)` |
| `hydrostatic_pressure_pa(-100.0)` | `(-1 029 698.25, ...)` -- negative pressure |
| `fracture_pressure_pa(0.0)` | rejected |
| `fracture_pressure_pa(-1.0)` | rejected |
| `allowable_delta_p_pa` with P above limit | `0.0`, the no-window signal |
| `allowable_delta_p_pa(safety_factor=0)` | rejected |
| `allowable_delta_p_pa(safety_factor=1)` | `12.5 MPa` |

`pressure.py` guards every input with `_require_positive`;
`hydrostatic_pressure_pa` guards none and will return a negative absolute
pressure. Depth is positive-downward throughout and ingestion parses positive
values, so this is not reachable through the normal path -- but the two modules
apply different standards to the same quantity.

Not changed: adding a guard is a behaviour change to a frozen module for a
condition no code path currently produces.

### Pressure convention traced through every consumer

| Consumer | Quantity | Convention needed | Convention supplied | Compatible? |
| --- | --- | --- | --- | --- |
| Screening scenario | `pressure_pa` (low, high) | declared | gauge, undeclared | Under-specified |
| Capacity | none directly | - | - | Not applicable |
| CO2 density (Peng-Robinson) | absolute thermodynamic P | **absolute** | gauge | **No** (Finding 4.1) |
| Theis `delta_p` | pressure *difference* | either | either | **Yes** -- see below |
| Fracture comparison | absolute vs absolute | **absolute** | absolute frac, gauge init | **No** (Finding 4.1) |
| Frontend display | Pa -> MPa | none | none | Yes |

The Theis row is the important exemption. `theis_injection_delta_p_pa` returns a
pressure *rise*, and a difference is invariant under a constant offset: adding
`P_atm` to both endpoints leaves it unchanged. The Theis mathematics is
therefore entirely immune to Finding 4.1. What is *not* immune is
`max_injection_rate_m3_s`, because its `allowable_delta_p_pa` argument is built
by subtracting a gauge pressure from an absolute one.

### Findings table

| Item | Status | Severity | Evidence | Action |
| --- | --- | --- | --- | --- |
| `P = rho g z` arithmetic | PASS | - | 4 cases vs exact rationals, max rel. error 2.1e-16 | None |
| Linearity in depth and density | PASS | - | Ratios exact to 12 decimal places | None |
| Fracture pressure independently defined | PASS | - | Own constant; never reads brine density | None |
| Headroom formula | PASS | - | Matches independent recomputation 4/4 | None |
| Fracture gradient magnitude | PASS WITH CAVEAT | LOW | 0.6631 psi/ft, 1.530 SG; but uncited and depth-independent | Documented |
| Brine density range | PASS | - | 10.00-10.79 kPa/m, between seawater and saline formation water | None |
| **Gauge P fed to absolute-P consumers** | **REVIEW REQUIRED** | **MEDIUM** | `P(0) = 0`; density -4.15%, headroom +3.34% | Correction proposed, not applied |
| **Hydraulic reference of z unstated** (original label "z not datum-corrected", superseded) | **REVIEW REQUIRED** | **HIGH** | Original: RT elevations 120.0 / 238.7 m, "P overstated 8.7-36.1%" on illustrative depths. Superseded: that is a sea-level water-level sensitivity, direction not established (*Finding 4.2 / 10.2 revision*) | Disclosure gap |
| **z is total depth, not reservoir depth** | **REVIEW REQUIRED** | **MEDIUM** | `depth_m` = "total depth"; no reservoir datum exists | Documented |
| z is MD, not TVD | PASS WITH CAVEAT | LOW-MED | "metres along-hole"; no deviation survey in any source | Documented |
| Negative depth accepted | PASS WITH CAVEAT | LOW | Returns -1.03 MPa; `pressure.py` would reject | Documented |
| Theis `delta_p` convention | PASS | - | A difference is offset-invariant | None |

### Scientific numbers changed?

**NO.** No file under `src/` was modified in Phase 4. The proposed `P_atm`
correction in Finding 4.1 is written out but deliberately not applied.

### Downstream impact

Findings 4.1, 4.2 and 4.3 all act on the same quantity -- the pressure handed to
the EOS and to the fracture comparison -- and all three act on `z` or its
offset, so their effects combine multiplicatively.

As originally written, this section put the combined worst case on reservoir
pressure at "overstated by roughly 8-36% (4.2, dominant)". That figure rested on
the datum-error reading of Finding 4.2, which is superseded (*Finding 4.2 / 10.2
revision*, Phase 10). What remains of 4.2 is a hydraulic-reference sensitivity:
where the water level is assumed to stand. Its direction is not established.
Finding 4.1 is a **0.1-1.1%** understatement from the missing atmosphere, and
Finding 4.3 an unquantified overstatement.

Affected downstream quantities:

- **Capacity** (Phase 3) inherits these through CO2 density. Direction: not
  established for 4.2; understated by 4.1; overstated by 4.3.
- **Injectivity ceiling** (Phase 5) inherits them through
  `allowable_delta_p_pa`. For 4.2 the direction depends on the unresolved water
  level, and a change applied to reservoir pressure alone would move only one
  side of the headroom comparison. Anti-conservative for 4.1.
- **Monte Carlo** (Phase 7) samples a pressure *range* built from this model, so
  the uncertainty band is centred on a value computed under an unstated
  water-level assumption. Widening the brine-density range does not represent
  that assumption.

### Is Phase 5 unblocked?

**Yes, with a carried caveat.** `BLOCKED BY UPSTREAM SCIENTIFIC ISSUE` is not
declared, and the distinction is deliberate:

- Phase 5 audits the **Theis solution** -- transmissivity, storativity, `W(u)`,
  the rate inversion and the validity of Theis for CO2. `delta_p` is a pressure
  difference and is **provably invariant** under the offset in Finding 4.1.
  None of the Phase 4 findings touch the mathematics Phase 5 will examine.
- What Phase 5 must carry forward is that any **absolute rate ceiling** it
  computes rests on `allowable_delta_p_pa`, which inherits Findings 4.1-4.3.
  Phase 5 should therefore audit the *method* as sound or not on its own terms,
  and treat its numeric ceilings as provisional.

Phase 10 and Phase 11 are where this matters most: every real-well pressure,
density and capacity number they produce rests on the unstated water-level
assumption behind Finding 4.2 (originally sized at 8-36% under the superseded
datum-error reading). That must not be rediscovered there as though it were new.

### Remaining uncertainty

1. **Finding 4.2's hydraulic reference is unresolved.** *(Original item: "cannot
   be quantified per well ... the error is unbounded", superseded 2026-09-24.)*
   The depth datum is now documented for four wells and unknown for
   TRECATE|9|ST. What remains is where the water level stands, which no
   measurement in the repository establishes. The size and the sign of the
   effect both depend on that assumption.
2. **Finding 4.3 is unquantified.** Without a reservoir top depth, the gap
   between total depth and storage-interval depth cannot be measured for any
   well in this dataset.
3. **Well deviation is unknown** (Finding 4.4). The MD/TVD gap cannot be bounded
   without deviation surveys, which no source provides.
4. **The fracture gradient has no primary source.** 0.6631 psi/ft is defensible
   against general practice, but "general practice" is not a citation, and
   Phase 9 should decide whether it needs one.
5. **The normal-pressure assumption is untested.** No measured formation
   pressure exists anywhere in the dataset, so nothing in this repository can
   detect an over- or under-pressured reservoir. This is the largest uncertainty
   in the pressure model and it is not reducible with the available data.

---

## Phase 5 -- Injectivity / Theis

Audited 2026-09-20. Scope: `pressure.py::theis_transmissivity`,
`theis_injection_delta_p_pa`, `max_injection_rate_m3_s`, and the way `cli.py`
composes them with the fracture headroom from Phase 4.

### Scope note: injectivity is CLI-only

A grep for `theis`, `inject`, `rate_m3_s` and `permeab` across `api.py`,
`src/ccs_screen/web/` and `frontend/` returns **no matches**. The injectivity
model is reachable only through `ccs-screen` on the command line; the public
HTTP API and the frontend expose capacity and provenance, not injection rates.

This materially limits the blast radius of everything below. The findings in
this phase do not reach any number the public product returns.

### The implemented formulation

| Term | Expression | Units |
| --- | --- | --- |
| Transmissivity `T` | `k h / mu` | m3/(Pa s) |
| Storativity `S` | `phi c_t h` | m/Pa |
| `u` | `r^2 S / (4 T t)` | dimensionless |
| Well function `W(u)` | `scipy.special.exp1(u)` | dimensionless |
| Drawdown `dP` | `Q / (4 pi T) * W(u)` | Pa |
| Rate ceiling | `dP_allowable / dP(Q=1)` | m3/s |

This is the **petroleum** convention throughout (T in m3/(Pa s), `dP` directly
in Pa), confirmed self-consistent in Phase 2. Phase 5 adds the check Phase 2
deferred: verification against an external reference.

### Well function verified against published tables

`W(u)` and the exponential integral `E1(u)` are the same function. That identity
was not assumed: `W(u)` was recomputed from its defining series,

`W(u) = -gamma - ln(u) + sum_{n>=1} (-1)^(n+1) u^n / (n * n!)`

with `gamma = 0.5772156649015329`, independently of scipy, and compared against
the standard tabulation (Wenzel 1942; reproduced in Freeze & Cherry 1979
Appendix and Kruseman & de Ridder 1990 Annex 3):

| u | scipy `exp1` | Independent series | Published | Rel. diff vs published |
| --- | --- | --- | --- | --- |
| 1e-15 | 33.961561 | 33.961561 | 33.9616 | 1.2e-06 |
| 1e-10 | 22.448635 | 22.448635 | 22.4486 | 1.6e-06 |
| 1e-08 | 17.843465 | 17.843465 | 17.8435 | 2.0e-06 |
| 1e-05 | 10.935720 | 10.935720 | 10.9357 | 1.8e-06 |
| 1e-04 | 8.633225 | 8.633225 | 8.6332 | 2.9e-06 |
| 1e-03 | 6.331539 | 6.331539 | 6.3315 | 6.2e-06 |
| 1e-02 | 4.037930 | 4.037930 | 4.0379 | 7.3e-06 |
| 1e-01 | 1.822924 | 1.822924 | 1.8229 | 1.3e-05 |
| 1.0 | 0.219384 | 0.219384 | 0.2194 | 7.3e-05 |
| 2.0 | 0.048901 | 0.048901 | 0.0489 | 1.0e-05 |
| 5.0 | 0.001148 | 0.001148 | 0.0011 | 2.6e-04 |

scipy and the independent series agree to machine precision at every point. The
residual against the published column is the table's own rounding to four or
five significant figures, and it shrinks monotonically as the tabulated
precision improves. **`W(u)` is correct.**

### Independent re-derivation of the full calculation

Written from first principles with no production import, at the CLI defaults
(`k = 8e-14 m2`, `h = 40 m`, `mu = 4.5e-4 Pa s`, `t = 10 yr`, `r = 500 m`,
`phi = 0.18`, `c_t = 1.2e-9 /Pa`, `Q = 0.08 m3/s`):

| Quantity | Independent | Production |
| --- | --- | --- |
| `T = k h / mu` | 7.111111e-09 m3/(Pa s) | 7.111111e-09 |
| `S = phi c_t h` | 8.640000e-09 m/Pa | - |
| `u` | 2.406314e-04 | - |
| `W(u)` | 7.755269 | - |
| `dP` | 6 942 877.978001 Pa | 6 942 877.978001 Pa |

**Relative error 0.000e+00** -- bit-identical.

`u = 2.4e-04` is comfortably inside the Cooper-Jacob validity window
(`u < 0.01`), so the logarithmic approximation regime applies and the solution
is in its well-behaved range at default settings.

### Rate inversion

`dP` is exactly proportional to `Q`, so `max_injection_rate_m3_s` inverts by a
single division rather than iterating. Round-trip verification:

| Target dP | Qmax | dP(Qmax) | Round-trip error |
| --- | --- | --- | --- |
| 1.0 MPa | 0.0115 m3/s | 1.000000 MPa | 1.2e-16 |
| 5.0 MPa | 0.0576 m3/s | 5.000000 MPa | 0 |
| 12.5 MPa | 0.1440 m3/s | 12.500000 MPa | 0 |

The inversion is exact. **PASS.**

### Finding 5.1 -- the rate ceiling compares a far-field dP against a near-well limit

**REVIEW REQUIRED. Severity HIGH. Anti-conservative.**

This is the most consequential finding in Phase 5.

Fracturing occurs where the pressure is highest, which in a radial-flow field is
**at the wellbore**. The fracture headroom from Phase 4 is therefore a
near-wellbore constraint. But `cli.py` evaluates `dP` at `radius_m`, whose
default is **500 m**, and compares *that* against the headroom.

Measured pressure field at the default settings:

| r (m) | u | W(u) | dP (MPa) | vs r = 500 m |
| --- | --- | --- | --- | --- |
| 0.1 | 9.6e-12 | 24.7894 | 22.1926 | **3.20x** |
| 1.0 | 9.6e-10 | 20.1842 | 18.0699 | 2.60x |
| 10 | 9.6e-08 | 15.5791 | 13.9471 | 2.01x |
| 100 | 9.6e-06 | 10.9739 | 9.8244 | 1.42x |
| 500 | 2.4e-04 | 7.7553 | 6.9429 | 1.00x |
| 1 000 | 9.6e-04 | 6.3697 | 5.7024 | 0.82x |
| 5 000 | 2.4e-02 | 3.1738 | 2.8413 | 0.41x |
| 20 000 | 3.9e-01 | 0.7282 | 0.6519 | 0.09x |

Consequence for the rate ceiling, at depth 2000 m and 11.0 MPa headroom:

| Evaluated at | Qmax | As CO2 mass (rho = 700) |
| --- | --- | --- |
| r = 500 m (current default) | 0.1267 m3/s | 88.7 kg/s = **2.80 Mt/yr** |
| r = 0.1 m (wellbore) | 0.0397 m3/s | 27.8 kg/s = **0.88 Mt/yr** |

**The permitted rate is overstated by 3.20x.**

Note what is and is not wrong here. `theis_injection_delta_p_pa` is honest: its
docstring says "pressure rise at `radius_m`", and the CLI help says "radius at
which dP is evaluated". The function computes what it claims. The defect is in
the **composition** -- pairing a far-field `dP` with a near-wellbore fracture
criterion -- and in the choice of 500 m as the default radius for that pairing.

No change made. The smallest correction would be to evaluate the fracture check
at a wellbore radius while leaving `radius_m` free for far-field reporting, but
that changes every injectivity number and is the project owner's decision.

### Finding 5.2 -- initial pressure and depth are independent and inconsistent by default

**REVIEW REQUIRED. Severity HIGH. Anti-conservative.**

`cli.py:183` sets `initial_pressure_pa` from the **midpoint of the capacity
pressure prior**, while `depth_m` is a **separate CLI scalar**. Nothing ties
them together, and the shipped defaults disagree:

| Quantity | Default | Implies |
| --- | --- | --- |
| `pressure_pa` prior midpoint | 16.0 MPa | depth 1554 m at rho = 1050 |
| `depth_m` | 2000 m | pressure 20.59 MPa at rho = 1050 |

**28.7% inconsistent.** The fracture limit is computed from 2000 m while the
initial pressure is the one belonging to 1554 m, so the headroom is inflated
from both ends:

| | Headroom | Qmax |
| --- | --- | --- |
| As shipped (P from prior, P_frac from 2000 m) | 11.00 MPa | 0.1267 m3/s |
| Internally consistent at 2000 m | 6.41 MPa | 0.0738 m3/s |
| Overstatement | **1.72x** | **1.72x** |

Phase 4 established that the scenario layer derives pressure from depth
correctly (`hydrostatic_from_depth`). The CLI does not use that path; it takes
pressure from the Monte Carlo prior and depth from an unrelated flag. The two
models exist side by side and disagree.

Combined with Finding 5.1, the rate ceiling at shipped defaults is overstated by
roughly **3.20 x 1.72 = 5.5x**.

### Finding 5.3 -- the brine analog is conservative on mobility, by about 7x

**PASS WITH CAVEAT. Severity MEDIUM. Conservative, but not a safe offset.**

`viscosity_pa_s` defaults to 4.5e-4 Pa s and the CLI help calls it "brine
viscosity". CO2 at reservoir conditions is roughly an order of magnitude less
viscous:

| Fluid | mu (Pa s) | dP at default Q | Ratio |
| --- | --- | --- | --- |
| Brine (default) | 4.5e-04 | 6.9429 MPa | 1.000x |
| CO2 at reservoir conditions | 5.0e-05 | 0.9900 MPa | 0.143x |
| CO2, upper estimate | 7.0e-05 | 1.3391 MPa | 0.193x |

So the brine analog produces roughly **7x more** pressure rise than a
CO2-mobility calculation would, which is conservative and which
`max_injection_rate_m3_s` turns into a correspondingly lower rate ceiling.

It is tempting to observe that 7x conservatism roughly offsets the 5.5x
anti-conservatism of Findings 5.1 and 5.2, leaving the shipped default answer
accidentally near-correct. **That reasoning should be resisted.** The three
errors act on different physics, the cancellation is a coincidence of one
particular default set, and it evaporates the moment a user changes a flag.
More importantly, a CO2-viscosity calculation is *also* not the right answer:
real CO2 injection involves relative-permeability reduction in the two-phase
bank, which raises `dP`, and dry-out with halite precipitation near the well,
which raises it further. The single-phase brine analog is a bound of unknown
tightness, not a conservative bound with a known margin.

The module docstring is honest about this: *"a screening bound on aquifer
pressurization, not a two-phase CO2 plume model"*.

### Theis assumptions against CCS reality

Each assumption of the Theis (1935) solution, checked against how it is used
here:

| Theis assumption | Status in this model | Direction if violated |
| --- | --- | --- |
| Infinite areal extent | **Violated by design** -- `area_m2` describes a bounded structural closure | Anti-conservative |
| Homogeneous, isotropic, uniform thickness | Screening idealisation; no heterogeneity data exists | Unknown |
| Fully penetrating well | Assumed; no completion data in any source | Anti-conservative if partial |
| Single-phase, slightly compressible fluid | **Violated** -- CO2 is two-phase and highly compressible | See Finding 5.3 |
| Constant density and viscosity | Violated -- CO2 density varies strongly with P and T | Unknown |
| Constant rate | Assumed; reasonable for screening | Neutral |
| Darcy (laminar) flow | Near-well non-Darcy effects possible at high rate | Anti-conservative |
| No wellbore storage, no skin | Assumed; a positive skin raises well pressure further | Anti-conservative |
| Instantaneous release from storage | Standard | Neutral |

The infinite-extent assumption deserves emphasis because it contradicts the
capacity model in the same run: capacity is computed for a **closed structural
trap** while injectivity assumes an **infinite aquifer**. A no-flow boundary at
the closure edge would make pressure rise faster than Theis predicts, without
limit. This is a genuine cross-model inconsistency and is carried to Phase 12.

### Finding 5.4 -- pressure never reaches steady state, so the answer is a function of the chosen duration

**PASS WITH CAVEAT. Severity LOW.**

Infinite-acting radial flow grows logarithmically and never stabilises:

| Injection duration | dP at r = 500 m |
| --- | --- |
| 0.1 yr | 2.8413 MPa |
| 1 yr | 4.8834 MPa |
| 10 yr (default) | 6.9429 MPa |
| 30 yr | 7.9263 MPa |
| 100 yr | 9.0041 MPa |
| 1 000 yr | 11.0654 MPa |

This is correct Theis behaviour, not a defect. It does mean the injectivity
verdict depends entirely on the 10-year default, which is a project convention
rather than a physical result. `SECONDS_PER_YEAR = 365.25 * 24 * 3600` is the
Julian year, consistent with the Phase 2 finding.

### Finding 5.5 -- two thicknesses and two porosities coexist unchecked

**PASS WITH CAVEAT. Severity LOW.**

A single CLI run carries `thickness_m` (net storage, prior 25-55 m) and
`aquifer_thickness_m` (Theis, default 40 m), plus `porosity` (prior 0.12-0.24)
and `aquifer_porosity` (default 0.18). They are separate parameters with no
consistency check.

This is defensible and arguably correct -- `ThicknessKind` explicitly names
`AQUIFER_HYDRAULIC` as distinct from `NET_STORAGE`, and the hydraulic unit
genuinely can exceed the net storage interval. But nothing prevents a user from
setting them to contradictory values, and nothing reports the ratio. Carried to
Phase 12 with Finding 5.1's boundary-condition conflict.

### Input validation

Complete and symmetric -- every argument is guarded by `_require_positive`:

| Input | Behaviour |
| --- | --- |
| `rate_m3_s = 0` | rejected |
| `time_s = 0` | rejected |
| `radius_m = 0` | rejected |
| `permeability_m2 = 0` | rejected |
| `compressibility_1_pa = 0` | rejected |
| `allowable_delta_p_pa = 0` | rejected |
| `radius_m = 1e6` | returns 0.0 Pa (underflow) |
| `time_s = 1 s` | returns 0.0 Pa (underflow) |

This is stricter than `hydrostatic_pressure_pa`, which Phase 4 Finding 4.7 found
accepts a negative depth. The two underflow cases return exactly zero because
`u` grows past the point where `exp1` underflows -- at `t = 1 s` and `r = 500 m`,
`u` is about 7.6e4 and the true `dP` is of order `e^-76000` Pa. Returning zero
is physically right (the pressure signal has not arrived), but it is silent
underflow rather than a modelled result. **PASS.**

### Findings table

| Item | Status | Severity | Evidence | Action |
| --- | --- | --- | --- | --- |
| `W(u)` correctness | PASS | - | Matches independent series to machine precision and 11 published table values | None |
| `W(u) == E1(u)` identity | PASS | - | Verified, not assumed | None |
| `T`, `S`, `u`, `dP` derivation | PASS | - | Bit-identical to an independent implementation (rel. err 0) | None |
| Rate inversion | PASS | - | Round-trip error <= 1.2e-16 over 3 targets | None |
| Cooper-Jacob validity | PASS | - | `u = 2.4e-04 < 0.01` at defaults | None |
| Input validation | PASS | - | 6/6 zero cases rejected | None |
| **Far-field dP vs near-well fracture limit** | **REVIEW REQUIRED** | **HIGH** | dP at wellbore is 3.20x that at 500 m; Qmax overstated 3.20x | Documented |
| **Depth and initial pressure inconsistent** | **REVIEW REQUIRED** | **HIGH** | Defaults disagree by 28.7%; headroom overstated 1.72x | Documented |
| Brine analog vs CO2 mobility | PASS WITH CAVEAT | MEDIUM | 7x higher dP than CO2 viscosity gives; bound of unknown tightness | Documented |
| Infinite extent vs closed trap | PASS WITH CAVEAT | MEDIUM | Contradicts the capacity model in the same run | Phase 12 |
| No steady state | PASS WITH CAVEAT | LOW | dP 2.84 -> 11.07 MPa from 0.1 to 1000 yr | Documented |
| Two thicknesses / two porosities | PASS WITH CAVEAT | LOW | No consistency check between capacity and Theis inputs | Phase 12 |
| Underflow returns exact zero | PASS | LOW | Physically correct, silently | Documented |

### Scientific numbers changed?

**NO.** No file under `src/` was modified in Phase 5.

### Downstream impact

Contained. Injectivity is CLI-only and feeds nothing else: no capacity number,
no Monte Carlo input, no API response and no frontend field depends on any
quantity computed in this phase. Findings 5.1 and 5.2 are severe for the rate
ceiling and severe for nothing else.

The inherited Phase 4 caveat is confirmed and now bounded. `theis_injection_delta_p_pa`
takes no absolute pressure argument, so Finding 4.1 provably cannot reach the
Theis mathematics. It reaches the **rate ceiling** only through
`allowable_delta_p_pa`, and there its effect (about 2% on headroom) is small
next to the 5.5x from Findings 5.1 and 5.2.

Phase 12 inherits two genuine cross-model inconsistencies: closed trap versus
infinite aquifer, and the unchecked duplicate thickness/porosity pairs.

### Remaining uncertainty

1. **The two-phase correction is unquantified and not bounded.** Relative
   permeability and near-well dry-out both raise `dP` while CO2's low viscosity
   lowers it. Nothing in this repository determines the net sign, let alone the
   magnitude.
2. **No permeability data exists for any pilot well.** `8e-14 m2` (about 80 mD)
   is a CLI default with no source. It was not audited against literature
   because no scenario adopts it -- unlike porosity and storage efficiency, it
   has no citation and no provenance record.
3. **Boundary conditions are unknown.** Whether the Piemonte aquifers are
   laterally open or compartmentalised is undetermined, and the two cases differ
   without limit at long times.
4. **Skin and completion are unknown.** No completion data exists in any source,
   so wellbore effects cannot be estimated.
5. **The fracture criterion itself carries Phase 4's uncertainties** -- an
   uncited gradient, an unstated hydraulic (water-level) reference (originally
   described as "an uncorrected depth datum", superseded -- see *Finding 4.2 /
   10.2 revision*), and a gauge/absolute mismatch.

---

## Phase 6 -- Temperature methods

Audited 2026-09-20. Scope: `provenance.py::TemperatureMethod` and
`TEMPERATURE_METHOD_RANK`, `sources.py::classify_temperature_method`,
`normalize.py::_derive_temperature` and `RESERVOIR_DEPTH_FRACTION`.

### Rescoping, confirmed by inspection

The Phase 0 plan listed "Horner, Squarci-Taffi, Fertl-Wichmann: equation,
coefficients, units, applicability, extrapolation". **None of those equations
exists in this repository.** A grep for `horner`, `squarci`, `fertl`,
`wichmann` and `taffi` across `src/` returns only enum members, rank-table keys
and two source-string literals -- no arithmetic anywhere.

That is the correct design. The corrections were applied by the data publisher
(GEOTHOPICA); this project ingests the already-corrected values and records
*which* method produced each one. There is no coefficient to verify and no
extrapolation to re-derive.

Phase 6 therefore audits what actually exists: **the rule that selects one
temperature observation from several, and the rank ordering that rule uses.**

### The selection rule

`_derive_temperature` in four steps:

1. Drop any observation whose method ranks 99 (`surface_air_mean`). If nothing
   remains, `temperature_k` is MISSING with the reason "only surface air
   temperature available; not a reservoir temperature".
2. `deepest` = the deepest surviving observation.
3. `near_td` = observations at depth >= `RESERVOIR_DEPTH_FRACTION` (0.85) x
   `deepest`.
4. Choose `min(near_td, key=(rank, -depth))` -- best method first, deepest as
   tie-break.

Everything not selected is preserved as a `Conflict` with its method and depth,
and `TEMPERATURE_METHOD_CONFIDENCE` is carried onto the `FieldValue`. Nothing is
averaged, and nothing is silently discarded.

### Finding 6.1 -- no correction is ever computed

**PASS.**

The module selects; it does not correct. A `non_stabilized` value chosen because
nothing better exists is used **exactly as recorded**, with no Horner or
empirical correction applied. This is honest -- inventing a correction would be
forbidden -- but it has a quantified consequence, which is Finding 6.6.

### Finding 6.2 -- the best-ranked method is unreachable from the data

**PASS WITH CAVEAT. Severity LOW.**

`classify_temperature_method` can only ever return five of the seven enum
members. `_METHOD_MAP` contains four source strings:

| Source string (verbatim, Italian) | Method |
| --- | --- |
| `estrap.metodo squarci-taffi` | `extrapolated_squarci_taffi` |
| `estrap.metodo fertl-wichmann` | `extrapolated_fertl_wichmann` |
| `non stabilizzata` | `non_stabilized` |
| `temp.atmosferica media annuale` | `surface_air_mean` |

Anything else maps to `UNKNOWN`. So **`horner_corrected` (rank 0) and `raw`
(rank 4) are never produced.** The top of the ranking is aspirational: the most
defensible method is the one the data never contains.

`docs/ingestion.md` already states the underlying fact -- *"Not one of the 452
temperature records in the pilot is a stabilised bottom-hole measurement"* -- so
this is consistent, not contradictory. It is recorded because a reader of the
rank table alone would reasonably assume rank 0 is attainable.

### Finding 6.3 -- Fertl-Wichmann is ranked above Squarci-Taffi without justification

**REVIEW REQUIRED. Severity MEDIUM.**

The implemented order is:

| Rank | Method | Confidence |
| --- | --- | --- |
| 0 | `horner_corrected` | high |
| 1 | `extrapolated_fertl_wichmann` | medium |
| 2 | `extrapolated_squarci_taffi` | medium |
| 3 | `non_stabilized` | low |
| 4 | `raw` | low |
| 5 | `unknown` | low |
| 99 | `surface_air_mean` | none |

Ranks 0, 3, 5 and 99 are defensible on general grounds: a Horner-corrected
reading of a real bottom-hole survey is the standard; an unstabilised reading is
worse than a corrected one; an unlabelled reading is treated as worse than a
labelled one, which is precautionary; and an annual surface air mean is not a
reservoir temperature at all.

The 1-versus-2 ordering is the problem. Both carry `medium` confidence, so the
rank is the only thing separating them, and it decides the answer whenever both
are present.

- **Fertl & Wichmann (1977)** is a generic empirical BHT correction from the
  petroleum literature, developed against Gulf Coast data.
- **Squarci and Taffi** are Italian geothermal researchers; their work underpins
  the Italian national geothermal characterisation (Cataldi, Mongelli, Squarci,
  Taffi, Zito & Calore, "Geothermal ranking of Italian territory", *Geothermics*
  24(1), 115-129, 1995) and the same institutional lineage as GEOTHOPICA, which
  is the source this project ingests.

So the implementation prefers a **generic, non-Italian** correction over a
**regionally calibrated Italian** one, for **Italian wells**, with no stated
reason. That inverts the evidence hierarchy the project applies everywhere
else: Phase 3 established that Donda et al.'s porosity range was adopted
specifically *because* it is Italian and of the same play type, and
`EvidenceClass` exists to rank `regional` above `generic`.

**What this audit can and cannot establish.** No methodological comparison of
the two corrections was located, so this is *not* a finding that Squarci-Taffi
is more accurate. It is a finding that the ordering is **unjustified and
internally inconsistent with the project's own stated preference for regional
calibration**. Documented, not changed -- reversing it would change the selected
temperature for every well where both methods are present, and therefore every
capacity number.

### Finding 6.4 -- the 0.85 filter lets depth masquerade as method disagreement

**REVIEW REQUIRED. Severity MEDIUM.**

`RESERVOIR_DEPTH_FRACTION = 0.85` admits any observation within 15% of the
deepest. The absolute window that opens grows with depth:

| Total depth | Admissible depth spread | Implied temperature spread at 30 K/km |
| --- | --- | --- |
| 1 000 m | 150 m | 4.5 K |
| 2 000 m | 300 m | 9.0 K |
| 4 000 m | 600 m | 18.0 K |
| 6 248 m | 937 m | 28.1 K |

The `Conflict` note generated for those observations reads *"methods disagree by
{spread} K at comparable depth"*. At 6 km, "comparable depth" spans nearly a
kilometre, and the reported spread is **not** a method disagreement.

The project's own worked example demonstrates this. `docs/ingestion.md` prints
TRECATE|9|ST and reports *"P50 spread 1.81 Mt (30.5%) from temperature method
alone"*. Decomposing those three observations at 30 K/km:

| Observation | T (K) | Depth (m) | Passes 0.85 filter |
| --- | --- | --- | --- |
| `extrapolated_fertl_wichmann` (selected) | 452.15 | 6 247.9 | yes |
| `extrapolated_squarci_taffi` | 440.15 | 6 000.0 | yes |
| `non_stabilized` | 399.15 | 5 510.0 | yes |

| Compared with the selected value | Total spread | Depth component | Method component | Depth share |
| --- | --- | --- | --- | --- |
| vs `extrapolated_squarci_taffi` | 12.00 K | 7.44 K | 4.56 K | **62.0%** |
| vs `non_stabilized` | 53.00 K | 22.14 K | 30.86 K | **41.8%** |

So the majority of the Squarci-Taffi "method" spread, and over 40% of the
non-stabilised one, is simply the geothermal gradient between 5 510 m and
6 248 m. The headline "30.5% from temperature method alone" overstates the
method contribution.

The finding is about **labelling and comparison semantics**, not about the
arithmetic: no value is wrong, but a depth effect is being reported as a method
effect in a document and a `Conflict` note a user is expected to act on.

### Finding 6.5 -- temperature and pressure are evaluated at different depths

**REVIEW REQUIRED. Severity MEDIUM. Cross-model.**

The selected temperature belongs to a specific depth, recorded in the derivation
string, and it is passed to the equation of state **without any adjustment to a
common reservoir datum**. Meanwhile Phase 4 Finding 4.3 established that
pressure is computed at **total well depth**.

At TRECATE|9|ST the selected temperature is at 6 247.9 m, which happens to equal
TD. But the filter permits the selected temperature to sit up to 15% shallower
than the deepest reservoir observation, which is itself not necessarily TD. The
two state variables handed to `co2_density_kg_m3` can therefore describe
**different depths in the same well**, with no check and no warning.

Note the asymmetry: the temperature path has a depth-awareness mechanism
(`RESERVOIR_DEPTH_FRACTION`) and the pressure path has none. Neither reduces to
a declared reservoir reference depth, because none exists. Carried to Phase 12
with the Phase 5 cross-model items.

### Finding 6.6 -- an uncorrected BHT biases capacity upward, and nothing corrects it

**REVIEW REQUIRED. Severity MEDIUM. Anti-conservative.**

A non-stabilised bottom-hole temperature reads **low**, because circulating
drilling mud cools the formation near the bit. That is the entire reason Horner
and the empirical corrections exist.

Capacity is linear in CO2 density, and density rises as temperature falls. So an
uncorrected BHT **overstates** capacity. Measured at the TRECATE state point
(64.33 MPa hydrostatic at 6 247.9 m):

| Temperature error | CO2 density | Capacity bias |
| --- | --- | --- |
| low by 1 K | 762.42 kg/m3 | +0.31% |
| low by 5 K | 771.95 kg/m3 | +1.56% |
| low by 10 K | 784.14 kg/m3 | +3.17% |
| low by 20 K | 809.44 kg/m3 | +6.50% |
| low by 30 K | 833.99 kg/m3 | +9.98% |

Method choice alone, at the same state point:

| Method | T (K) | CO2 density | Capacity vs selected |
| --- | --- | --- | --- |
| `extrapolated_fertl_wichmann` (selected) | 452.15 | 760.06 | 0.00% |
| `extrapolated_squarci_taffi` | 440.15 | 789.10 | +3.82% |
| `non_stabilized` | 399.15 | 901.41 | +18.60% |

(These are computed at a single deterministic state point, not the Monte Carlo
P50, so they are not directly comparable with the 6.4-15.0% figure quoted in
`docs/ingestion.md` -- that range is across wells and through the full
screening.)

The ranking does mitigate this: an extrapolated method is always preferred over
`non_stabilized`. The residual exposure is a well where **only** a non-stabilised
reading exists near TD, which is then used uncorrected. That overstates
capacity. *(The original text paired this with Phase 4 Finding 4.2 as a
same-direction effect. The direction of Finding 4.2's hydraulic-reference effect
is not established -- see* Finding 4.2 / 10.2 revision*.)*

### Finding 6.7 -- the classifier is conservative and does not guess

**PASS.**

`classify_temperature_method` normalises case and collapses internal whitespace,
then matches on the first 18 characters of each known string. Probed:

| Input | Result |
| --- | --- |
| `Estrap.metodo Squarci-Taffi` | `extrapolated_squarci_taffi` |
| `ESTRAP.METODO FERTL-WICHMANN` | `extrapolated_fertl_wichmann` |
| `  estrap.metodo   fertl-wichmann  ` | `extrapolated_fertl_wichmann` |
| `Non Stabilizzata` | `non_stabilized` |
| `estrap.metodo` | `unknown` |
| `estrap.metodo sconosciuto` | `unknown` |
| `estrap.metodo squ` | `unknown` |
| `horner`, `Horner corrected` | `unknown` |
| `stabilizzata` | `unknown` |
| `""`, `None`, `"   "` | `unknown` |

Case- and whitespace-insensitive, and every unrecognised string falls through to
`UNKNOWN` rather than being guessed into a known method. The 18-character
truncation is an unexplained magic number, but it produces no collision among
the four entries and does not over-match a shorter prefix (`estrap.metodo squ`,
17 characters, correctly returns `unknown`).

One consequence worth stating: because `horner` maps to `UNKNOWN` (rank 5) and
not to `HORNER` (rank 0), a source that *did* supply a Horner-corrected value in
unexpected wording would be ranked **below** an unstabilised reading. Not
reachable with the present sources, since none contains such a string.

### Finding 6.8 -- surface air temperature is excluded at every layer

**PASS.**

Three independent barriers: rank 99, the explicit pre-filter in
`_derive_temperature`, and `Confidence.NONE`. A well whose only record is a
surface air mean gets `temperature_k` MISSING with a stated reason rather than a
number. Given that temperature is the one required input that is
non-assumable -- no scenario may supply it -- this is the correct and important
behaviour.

### Finding 6.9 -- method disagreement is surfaced, not resolved

**PASS. Credit where due.**

`compare_temperature_methods()` re-screens a well once per available reservoir
method, varying only temperature, and reports what each implies for P50. No
method is declared globally correct, and the user is shown the spread rather
than a single number with hidden method dependence. Combined with the `Conflict`
records, this is the right treatment of an irreducible ambiguity.

The caveat is Finding 6.4: the spread it reports is labelled as method-driven
when it is partly depth-driven.

### Findings table

| Item | Status | Severity | Evidence | Action |
| --- | --- | --- | --- | --- |
| No correction equations implemented | PASS | - | Zero arithmetic for any named method in `src/` | None |
| Selection rule structure | PASS | - | Filter, rank, tie-break by depth; nothing averaged | None |
| Surface air excluded | PASS | - | Rank 99 + pre-filter + `Confidence.NONE` | None |
| Classifier robustness | PASS | - | 16 probes; unrecognised -> `UNKNOWN`, never guessed | None |
| Conflicts preserved and compared | PASS | - | `Conflict` records + `compare_temperature_methods()` | None |
| Rank 0 and rank 4 unreachable | PASS WITH CAVEAT | LOW | `_METHOD_MAP` produces 5 of 7 members | Documented |
| **Fertl-Wichmann ranked above Squarci-Taffi** | **REVIEW REQUIRED** | **MEDIUM** | Generic preferred over regional, for Italian wells, unstated reason | Documented |
| **0.85 filter conflates depth with method** | **REVIEW REQUIRED** | **MEDIUM** | 62% / 42% of the TRECATE spreads are depth, not method | Documented |
| **T and P evaluated at different depths** | **REVIEW REQUIRED** | **MEDIUM** | No common reservoir datum; T within 15% of deepest, P at TD | Phase 12 |
| **Uncorrected BHT overstates capacity** | **REVIEW REQUIRED** | **MEDIUM** | +3.17% per 10 K; +18.60% for `non_stabilized` at TRECATE | Documented |
| `horner` string would rank below `non_stabilized` | PASS WITH CAVEAT | LOW | Maps to `UNKNOWN` (5), not `HORNER` (0) | Not reachable today |

### Scientific numbers changed?

**NO.** No file under `src/` was modified in Phase 6.

### Downstream impact

Temperature reaches exactly one consumer: `co2_density_kg_m3`, and through it
capacity. It does not touch pressure, injectivity or the Theis path.

Sensitivity is `+0.31% capacity per 1 K` at the TRECATE state point, so the
findings translate directly:

- Finding 6.3 (rank ordering) is worth **3.82%** on capacity at TRECATE -- the
  difference between the two extrapolated methods.
- Finding 6.6 (no correction of an unstabilised reading) is worth up to
  **18.60%** where no extrapolated value exists.
- Finding 6.6 **overstates** capacity; Phase 3 Finding 3.1 runs the other way.
  The direction of Phase 4 Finding 4.2's hydraulic-reference effect is not
  established, so it is not paired with either.

Nothing here blocks Phase 7. Monte Carlo samples temperature as a prior range,
and the question of whether that range is sampled and propagated correctly is
independent of which observation seeded it.

### Remaining uncertainty

1. **No stabilised measurement exists anywhere** -- 0 of 452 records. Every
   temperature in this project is extrapolated or unstabilised, so there is no
   ground truth against which any method could be validated.
2. **The two extrapolated methods cannot be compared on accuracy** from anything
   available here. Finding 6.3 rests on provenance and internal consistency,
   not on measured error.
3. **The 30 K/km gradient used to decompose Finding 6.4 is generic.** The actual
   Po Basin gradient is not established in this repository, so the depth/method
   split is indicative rather than exact.
4. **`RESERVOIR_DEPTH_FRACTION = 0.85` has no stated derivation.** It is a
   reasonable heuristic for excluding the 300/500/1000 m modelled grid points,
   but the specific value is uncited.
5. **Whether the ingested values were corrected consistently** by the data
   publisher is unverifiable from this side. The project records the method
   label it was given and trusts it.

---

## Baseline freeze and disclosure-only fixes

Applied 2026-09-20, after Phase 6, on the project owner's instruction:

> *Freeze the scientific baseline; fix disclosure-only issues now; defer all
> numerical/model changes until the full audit identifies their combined net
> effect.*

### What was changed

Three findings whose defect was **missing or wrong disclosure**, not wrong
arithmetic. Under the audit's own change-control rule ("if there is a
documentation problem: fix documentation only") these required no further
approval.

**Finding 4.2 -- the pressure provenance now states that z is uncorrected.**
`scenario.py`, inside the `rationale=` string of the derived `pressure_pa`
input. Previously the rationale disclosed only the normally-pressured
assumption. It now also names the depth datum, states that z is neither
datum-corrected nor a reservoir reference depth, gives the direction of the
bias, and quantifies it with the two elevations the source documents state.

Rendered output for a pilot well:

```
Normally-pressured hydrostatic assumption. No measured pressure exists in any
source, so this is untested for this well. z is the source depth as recorded
(datum: unknown), not corrected to a sub-sea datum and not a reservoir
reference depth. Where depths run from a rotary table standing above sea level,
this overstates the brine column and therefore the pressure; the two datum
elevations stated in the source documents are 120.0 m and 238.7 m, worth
1.2-2.6 MPa.
```

This was the highest-value change available, because Finding 4.2 is the only
HIGH-severity item that reaches the public API and its sole defect was that the
limitation was invisible to a caller.

*Note 2026-09-24:* the rationale text above is recorded as it was written and
still stands in the code. Its sub-sea framing and stated direction ("overstates
the brine column") are superseded by *Finding 4.2 / 10.2 revision*. Changing the
code string is a separate disclosure follow-up.

**Finding 6.4 -- the temperature conflict note no longer calls a depth spread a
method disagreement.** `normalize.py`, inside the `note=` string of the
`temperature_k` `Conflict`. It previously read "methods disagree by {spread} K
at comparable depth", which at 6 km could describe observations 937 m apart. It
now reports the actual depth span and says explicitly that part of the spread is
the geothermal gradient.

Rendered output for the documented TRECATE|9|ST case:

```
values differ by 53.0 K across 738 m of depth; part of that spread is the
geothermal gradient, not method disagreement, and no depth correction is
applied; selected the best-ranked reservoir method
```

**Finding 3.4 -- the gross/net magnitude now states its measured envelope.**
`records.py` (`ThicknessKind` docstring), `docs/ingestion.md` and
`docs/scenario-literature-review.md`. "roughly 20-50x" became "1.5x to 128x",
with the bounding pairs named in the prose version.

### Proof that no scientific number moved

Every changed line in `src/` is inside a string literal or a docstring, with one
exception: a new `depth_span` local in `normalize.py` whose only consumer is the
note string it was added for. The full diff of `src/ccs_screen/ingest/` was
inspected line by line to confirm this.

Two direct checks were run against the modified code paths:

| Check | Result |
| --- | --- |
| Derived `pressure_pa` for a 1527.5 m well | `[15279251.032499999, 16477623.662499998]` Pa, bit-identical to `rho g z` for rho = 1020 and 1100 |
| Selected temperature for TRECATE|9|ST | 452.15 K, `extrapolated_fertl_wichmann` -- unchanged |

Full suite: **776 passed**, unchanged from the Phase 6 end state.

### What remains frozen

The eight findings that would move a number are untouched and await the combined
net-effect assessment:

| Finding | Severity | Change required | Direction |
| --- | --- | --- | --- |
| 3.1 -- E applied to net thickness | MEDIUM | Reconcile E with its gross-thickness definition | Understates capacity 1.4-10x |
| 3.2 -- porosity not qualified | LOW | Confirm total vs effective (Phase 9) | None, if confirmed total |
| 4.1 -- gauge fed to absolute consumers | MEDIUM | Add `P_atm` at one call site | Understates capacity <=4.1%; overstates headroom <=3.3% |
| 4.2 -- hydraulic reference (water level) of z unstated | HIGH | Establish the water level per well; depth datum documented for 4 wells, unknown for TRECATE\|9\|ST | Direction not established; sensitivity only (original entry "Overstates capacity 8-36%", superseded) |
| 4.3 -- z is total depth | MEDIUM | Needs a reservoir reference depth that does not exist | Overstates capacity |
| 5.1 -- far-field dP vs near-well limit | HIGH | Evaluate fracture check at wellbore radius | Overstates rate ceiling 3.2x |
| 5.2 -- depth and pressure inconsistent | HIGH | Tie CLI depth and pressure together | Overstates headroom 1.7x |
| 6.3 -- Fertl-Wichmann above Squarci-Taffi | MEDIUM | Reverse the rank, or justify it | 3.8% on capacity at TRECATE |

The directions do not agree: 3.1 understates capacity while 4.3 and 6.6
overstate it, and the direction of 4.2 is not established. That is precisely why the combined assessment was deferred rather
than fixing them one at a time.

The characterisation tests added in Phases 4, 5 and 6 pin the current behaviour
of every frozen item, so none of them can change silently. Each such test names
its finding and states what it must assert once that finding is resolved.

---

## Phase 7 -- Monte Carlo / uncertainty

Audited 2026-09-20. Scope: `monte_carlo.py` in full -- `UniformPriors.sample`,
`run_capacity_mc`, `McResult`, `DEPLETED_GAS_ANALOG` -- plus how `api.py` and
`report.py` drive it and how the result is exposed.

### The machinery is correct. The interpretation is the finding.

Everything mechanical in this phase passes: the generator, the marginals, the
independence as implemented, the percentile arithmetic, the convergence
behaviour and the input validation. The substantive findings are all about
**what the reported band means**, and the largest of them is that the band is
much narrower in scope than a reader would assume.

### Random number generation

| Check | Result |
| --- | --- |
| Generator | `np.random.default_rng` -> **PCG64** |
| Same seed reproduces | yes, identical samples |
| Different seed differs | yes |
| `seed=None` reproduces | no (OS entropy, as intended) |
| Default seed in `api.py` / `report.py` | 42 -- every public result is reproducible |

One non-obvious property, recorded because it matters for anyone repeating the
convergence work below: `sample()` draws each variable as a full vector of
length `n`, so **N=100 is not a prefix of N=1000 under the same seed**. Each N
is an independent experiment, not a nested one. This is not a defect -- it is
the reason the convergence table below uses repeated independent runs rather
than a single growing one.

### Marginal distributions

200 000 draws per variable, compared against the theoretical uniform:

| Variable | Bounds respected | Mean error | Variance error | KS statistic |
| --- | --- | --- | --- | --- |
| `area_m2` | yes | 0.053% | 0.288% | 0.00203 |
| `thickness_m` | yes | 0.039% | 0.021% | 0.00153 |
| `porosity` | yes | 0.018% | 0.127% | 0.00172 |
| `pressure_pa` | yes | 0.019% | 0.106% | 0.00117 |
| `temperature_k` | yes | 0.004% | 0.045% | 0.00184 |
| `storage_efficiency` | yes | 0.036% | 0.112% | 0.00153 |

The 95% KS critical value at N = 200 000 is **0.00304**. Every statistic is
below it. The draws are uniform on their stated intervals. **PASS.**

### Independence as implemented

Full correlation matrix over the same 200 000 draws: maximum absolute
off-diagonal correlation **0.00536**, against an expected scale of
`1/sqrt(N) = 0.00224`. For the maximum over 15 pairs that is about 2.4 sigma --
ordinary. The six streams are independent as designed. **PASS.**

Whether they *should* be independent is Finding 7.3.

### Percentile computation and convention

`np.percentile(masses, [10, 50, 90])` with the default linear interpolation.
Recomputed by hand from the sorted array at all three quantiles: **exact match**
to 1e-9.

`p10 < p50 < p90` confirmed. The module docstring is explicit that this is the
**statistical** convention (p10 = low case), *not* the petroleum convention
where P10 is the high case. That distinction is load-bearing and the codebase
states it -- see Finding 7.5 for where it stops being stated.

Distribution shape at N = 20 000:

| Quantity | Value |
| --- | --- |
| p10 / p50 / p90 | 7.1018 / 15.9921 / 33.6970 Mt |
| mean | 18.6106 Mt |
| mean vs median | **+16.37%** |
| skewness | **+1.348** |

A product of six positive variables is right-skewed, so mean exceeding median by
16% is expected, not anomalous. Reporting both `mean` and `p50` is correct --
quoting only the mean of a skewed distribution would systematically overstate
the typical case.

### Convergence

Required grid, 12 independent runs at each N:

| N | P10 | P50 | P90 | mean | P50 standard error |
| --- | --- | --- | --- | --- | --- |
| 100 | 6.7254 | 15.3827 | 35.0499 | 18.0308 | 6.347% |
| 500 | 6.7683 | 15.2244 | 32.4104 | 17.9127 | 3.565% |
| 2 000 | 6.8714 | 16.2757 | 34.1469 | 18.7798 | 1.468% |
| 10 000 | 7.1761 | 16.1616 | 33.8595 | 18.7536 | 0.763% |
| 50 000 | 7.1025 | 16.0686 | 33.5330 | 18.5885 | 0.320% |

The standard error falls as `1/sqrt(N)` (successive ratios 1.78, 2.43, 1.92,
2.38 against an expected 2.24 for a 5x step). Against a reference P50 of
16.0871 Mt from 12 runs at N = 50 000:

| N | Mean P50 bias | Run-to-run range |
| --- | --- | --- |
| 100 | -0.457% | **23.21%** |
| 500 | -0.677% | 11.29% |
| 2 000 | +1.042% | **4.39%** |
| 10 000 | +0.260% | 2.35% |
| 50 000 | +0.037% | 1.26% |

The estimator is **unbiased at every N** -- the bias column is noise around
zero, which is the correct behaviour for a percentile of an i.i.d. sample. What
changes with N is precision, not accuracy.

`DEFAULT_SAMPLES = 2 000` therefore carries a **4.4% run-to-run range on P50**.
That is defensible for screening and is small next to every systematic finding
in this audit, but it is not negligible and it is nowhere stated. `MAX_SAMPLES =
50 000` buys 1.26%, consistent with the reasoning recorded in `api.py`.

### Finding 7.1 -- only three of six priors vary in the real-data path

**REVIEW REQUIRED. Severity MEDIUM. Interpretation.**

`DEPLETED_GAS_ANALOG` varies all six inputs, and it is the synthetic CLI demo.
The real-data path through `api.py` is different. Resolved inputs for a pilot
well:

| Prior | Real-data value | Varies? |
| --- | --- | --- |
| `area_m2` | user-supplied scalar | **point** |
| `thickness_m` | user-supplied scalar | **point** |
| `temperature_k` | single selected observation | **point** |
| `porosity` | 0.10-0.35 (Donda et al.) | varies |
| `pressure_pa` | 15.28-16.48 MPa (brine density range) | varies |
| `storage_efficiency` | 0.01-0.04 (CSLF) | varies |

Measured band for that configuration at N = 50 000:
**P10 = 5.235, P50 = 10.868, P90 = 20.672 Mt -- a spread of 142% of P50.**

Contribution of each varying prior, measured by collapsing it to its midpoint:

| Collapsed prior | Band remaining |
| --- | --- |
| `porosity` | 74.4% |
| `storage_efficiency` | 69.1% |
| `pressure_pa` | **100.0%** |

Two consequences.

First, **pressure contributes essentially nothing.** Its range comes from the
brine-density assumption (1020-1100 kg/m3), which at this state point moves CO2
density very little. The uncertainty the band reports is almost entirely the
width of **two literature ranges** -- Donda's porosity and CSLF's storage
efficiency.

Second, **the two largest multipliers contribute zero.** Phase 3 measured the
elasticity of capacity with respect to `area_m2` and `thickness_m` as exactly
+1 each, and Phase 3 established that neither has any source or literature
basis. They enter as user-supplied points with no uncertainty at all, so a
caller who is uncertain about their closure area by a factor of two sees none
of that in the band.

So the reported P10-P90 is best read as: *"how much does the answer move across
the published ranges for porosity and storage efficiency, holding everything
else exactly as given"*. It is not a statement about how uncertain the capacity
of this site is.

### Finding 7.2 -- the band is a precision statement, not an accuracy statement

**REVIEW REQUIRED. Severity MEDIUM. Interpretation. Compounds with Phases 3, 4 and 6.**

Every systematic bias this audit has found lies **outside** the Monte Carlo
band, because none of them is represented as a sampled quantity:

| Finding | Effect on capacity | Inside the band? |
| --- | --- | --- |
| 4.2 -- hydraulic reference of `z` (depth datum documented for 4 wells; water level unstated) | sensitivity, direction not established (original entry "overstates 8-36%", superseded) | **no** |
| 6.6 -- uncorrected BHT | overstates up to 18.6% | **no** |
| 6.3 -- temperature method rank | 3.8% at TRECATE | **no** |
| 3.1 -- E applied to net thickness | understates 1.4-10x | **no** |
| 4.1 -- gauge vs absolute pressure | understates up to 4.1% | **no** |
| 4.3 -- `z` is total depth | overstates, unquantified | **no** |

Sampling more realisations reduces the width of the band around a number that
may be systematically wrong by more than the band itself. A user who reads
"P10-P90 = 5.2-20.7 Mt" as "the true answer is in this range with 80%
confidence" is over-trusting it in both directions.

Temperature is the sharpest case. In the real-data path it is a **point value**,
so the band carries zero temperature uncertainty -- while Phase 6 measured the
temperature-method choice alone as worth up to **18.6%** of capacity. That
uncertainty is real, known, quantified by this project's own
`compare_temperature_methods()`, and deliberately reported **outside** the band
rather than inside it.

That design choice is defensible: the uncertainty is epistemic (which method is
right) rather than aleatory (a range to sample), and folding it into a uniform
prior would manufacture a distribution nobody measured. But the result is that
the headline band and the temperature comparison are two different
uncertainty statements that a reader must combine themselves, and nothing says
so.

### Finding 7.3 -- pressure and temperature are sampled independently though both are depth-driven

**REVIEW REQUIRED. Severity MEDIUM in the CLI demo, NOT APPLICABLE in the real-data path.**

`DEPLETED_GAS_ANALOG` declares `pressure_pa = (12e6, 20e6)` and
`temperature_k = (320, 355)` and samples them independently. Both are functions
of depth, so the corners of that rectangle are physically unreachable:

| Prior corner | Implied depth from P | T that depth implies | Prior T | Error |
| --- | --- | --- | --- | --- |
| Low P / high T | 1 165 m | 323.1 K | 355.0 K | **+31.9 K** |
| High P / low T | 1 942 m | 346.4 K | 320.0 K | **-26.4 K** |
| Low P / low T | 1 165 m | 323.1 K | 320.0 K | -3.1 K |
| High P / high T | 1 942 m | 346.4 K | 355.0 K | +8.6 K |

Measured effect, independent sampling versus coupling T to P through a
hydrostatic depth and a 30 K/km gradient (N = 40 000):

| Sampling | P10 | P50 | P90 | Spread as % of P50 |
| --- | --- | --- | --- | --- |
| Independent (as implemented) | 7.179 | 16.095 | 33.841 | 165.7% |
| Depth-coupled | 8.088 | 17.241 | 34.292 | 152.0% |

Independence inflates the spread by about 14 percentage points and pushes
**P10 down by 11.2%** -- the low case, which is the number a conservative reader
quotes.

**Scope limit, which matters more than the magnitude.** In the real-data path
`temperature_k` is a single selected observation, i.e. a point, so there is no
P-T rectangle to sample and this finding does not arise. It applies to
`DEPLETED_GAS_ANALOG` and any hand-written prior set with both ranges open --
that is, to the CLI demo, not to the API or the frontend.

The magnitudes above use a generic 30 K/km gradient and a 1050 kg/m3
hydrostatic, so they are indicative of direction and scale, not definitive.

### Finding 7.4 -- N = 1 is accepted and returns three identical "percentiles"

**PASS WITH CAVEAT. Severity LOW.**

`MIN_SAMPLES = 1`, and a single realisation produces `p10 == p50 == p90`, with
no warning. The values are correct -- the 10th, 50th and 90th percentile of a
one-element sample really are that element -- but they are labelled as a
distribution in a payload whose field is named
`scenario_based_capacity_mt: {p10, p50, p90}`.

The same is true, legitimately, for fully degenerate priors: collapsing every
range to a point gives a spread of exactly `0.00e+00`, and `McResult` carries a
`deterministic` flag for that case. The flag is the right mechanism; it just is
not driven by sample count.

### Finding 7.5 -- the API does not state the percentile convention

**REVIEW REQUIRED. Severity MEDIUM. Disclosure only.**

The convention is stated in two places:

- `monte_carlo.py` module docstring -- *"``p10_mt`` is the 10th percentile, i.e.
  the *low* case. This is the statistical convention, not the petroleum P10/P90
  convention where P10 is the high case."*
- `frontend/components/ResultPanel.tsx` -- *"P10 is the 10th percentile (low
  case). Values in Mt CO2."*

It is **not** stated in the API payload. `api.py` returns
`{"p10": ..., "p50": ..., "p90": ..., "mean": ...}` with no convention field,
and `web/schemas.py` declares them as bare floats.

Any consumer other than this project's own frontend -- and the petroleum domain
is exactly where such a consumer would come from -- can read `p10` as the
optimistic case and invert the entire risk reading. The project already carries
an `INTERPRETATION` block, a `SCALE_MISMATCH_WARNING` and `LABEL_LEGEND` in the
same payload precisely to prevent this class of misreading, so the omission is
an inconsistency with the project's own standard rather than an oversight of
principle.

This is disclosure-only: adding a convention field changes no number. It is a
candidate for the same treatment as Findings 3.4, 4.2 and 6.4, and is left for
the owner's decision rather than applied inside a phase.

### Finding 7.6 -- uniform priors are the right default and the shape they produce is sensible

**PASS.**

Given only a published low and high with no distributional information, the
uniform is the maximum-entropy choice, and inventing a triangular or PERT shape
would assert a mode that no source states. `EvidenceClass` records these ranges
as `regional` and `generic`, not as fitted distributions, so a uniform is the
honest representation.

The product of six such variables is approximately log-normal, and the measured
skewness of +1.35 is consistent with that. Nothing in the pipeline assumes
normality, so the skew causes no error; it only makes the mean/median
distinction matter, and both are reported.

### Input validation

| Case | Behaviour |
| --- | --- |
| `n = 0`, `n = -5` | rejected, "n must be positive" |
| prior lower bound <= 0 | rejected, per-field message |
| prior upper bound < lower | rejected, per-field message |
| `porosity` prior up to 1.5 | **accepted at prior level**, rejected downstream in `capacity.py` |
| empty sample list | rejected, "need at least one sample" |
| `percentile(-1)`, `percentile(101)` | rejected, "[0, 100]" |
| degenerate priors | spread exactly 0.0, `deterministic` flag set |

One asymmetry: `UniformPriors` enforces positivity and ordering but not the
`< 1` constraint on `porosity` and `storage_efficiency`. An impossible prior is
constructed successfully and only fails when the first sample reaches
`volumetric_storage_mass_kg`. The failure is loud and immediate, so nothing
escapes, but the error surfaces one layer later than the other bound checks.
**PASS.**

### Findings table

| Item | Status | Severity | Evidence | Action |
| --- | --- | --- | --- | --- |
| RNG choice and seeding | PASS | - | PCG64; seed 42 default; reproducible | None |
| Marginal uniformity | PASS | - | 6/6 KS below the 0.00304 critical value at N=200k | None |
| Independence as implemented | PASS | - | max off-diagonal r = 0.00536 vs 1/sqrt(N) = 0.00224 | None |
| Percentile arithmetic | PASS | - | Matches a hand recomputation at all three quantiles | None |
| Convergence behaviour | PASS | - | se ~ 1/sqrt(N); unbiased at every N | None |
| Uniform prior choice | PASS | - | Maximum entropy given bounds only | None |
| Input validation | PASS | - | 7/7 invalid cases rejected | None |
| **Only 3 of 6 priors vary in the real path** | **REVIEW REQUIRED** | **MEDIUM** | Band is 142% of P50; pressure contributes 0%; area and thickness are points | Documented |
| **Band is precision, not accuracy** | **REVIEW REQUIRED** | **MEDIUM** | All six systematic findings lie outside it | Documented |
| **P and T sampled independently** | **REVIEW REQUIRED** | **MEDIUM (CLI only)** | Corners off by +31.9 K / -26.4 K; P10 down 11.2% | Documented |
| **API omits the percentile convention** | **REVIEW REQUIRED** | **MEDIUM** | Stated in the module and the frontend, absent from the payload | Disclosure-only candidate |
| N = 1 returns three identical percentiles | PASS WITH CAVEAT | LOW | `MIN_SAMPLES = 1`, no warning | Documented |
| `DEFAULT_SAMPLES = 2000` run-to-run range | PASS WITH CAVEAT | LOW | 4.39% on P50, unstated | Documented |
| Prior `< 1` bound checked one layer late | PASS | LOW | Caught in `capacity.py`, loudly | None |

### Scientific numbers changed?

**NO.** No file under `src/` was modified in Phase 7.

### Downstream impact

None mechanical. The Monte Carlo consumes capacity and produces percentiles; it
feeds the surrogate (Phase 8) and the reported result, and nothing about its
implementation is in question.

The interpretive findings do propagate. **Phase 8 inherits Finding 7.1
directly**: a sensitivity analysis fitted to these samples can only rank the
parameters that actually vary. In the real-data path that is three of six, and
`area_m2` and `thickness_m` -- the two largest multipliers in the whole
model -- are constant. Phase 8 must establish whether the sensitivity output
says so, or whether it silently presents a ranking over a subset as though it
were a ranking over the model.

Phase 12 inherits Finding 7.2: the relationship between the reported band and
the systematic biases catalogued in Phases 3, 4 and 6 is a cross-model
consistency question, and it is the single most likely way a reader
misinterprets this product.

### Remaining uncertainty

1. **The depth-coupling magnitudes in Finding 7.3 are indicative.** They use a
   generic 30 K/km gradient and a 1050 kg/m3 hydrostatic; the actual Po Basin
   gradient is not established in this repository.
2. **Independence between porosity and storage efficiency was not tested
   against reality.** Phase 3 Finding 3.1 established that the CSLF coefficient
   contains a porosity-related term, which implies the two are not independent.
   Quantifying that correlation needs the sub-factor decomposition Phase 9 will
   examine.
3. **No prior is a fitted distribution.** The uniforms represent published
   min-max pairs. Whether the true parameter distributions are uniform over
   those intervals is unknown and unknowable from the cited sources.
4. **Convergence was measured on `DEPLETED_GAS_ANALOG`.** The real-data prior
   set is narrower in three dimensions and degenerate in three, so its
   convergence is at least as fast; this was not separately measured at every N.

---

## Phase 8 -- Sensitivity analysis

Audited 2026-09-20. Scope: `surrogate.py` in full -- `fit_linear_surrogate`,
`predict`, `evaluate`, `sensitivity`, and the degenerate-column guard.

### Scope note: sensitivity is CLI-only

`fit_linear_surrogate`, `evaluate` and `sensitivity` are imported by exactly one
consumer, `cli.py`, which emits `sensitivity_mt_per_sigma`. A grep across
`api.py`, `ingest/report.py`, `web/schemas.py`, `frontend/lib` and
`frontend/components` finds **no reference to the surrogate at all**.

Like injectivity in Phase 5, this limits the blast radius: no public API field
or frontend element depends on anything in this phase.

### What the method is

Ordinary least squares on **standardized** features, so each coefficient is
"Mt of capacity per one standard deviation of that input over its sampled
range". Ranking by `abs(coefficient)` then answers: *which input moves capacity
most, across the ranges actually sampled.*

This is the standard beta-weight formulation, and for a linear model it is
exact.

### Validation against functions with known answers

Three synthetic cases, N = 20 000, fitted with the production function.

**Case A -- an exact linear law in standardized space,
`y = 10 + 3z1 + 1z2 + 0z3 - 2z4 + 0.5z5 + 0z6`:**

| Feature | True beta | Fitted | Error |
| --- | --- | --- | --- |
| `area_m2` | 3.0 | 3.0000 | -2.7e-15 |
| `thickness_m` | 1.0 | 1.0000 | -6.3e-15 |
| `porosity` | 0.0 | -0.0000 | -2.2e-16 |
| `pressure_pa` | -2.0 | -2.0000 | 1.3e-15 |
| `temperature_k` | 0.5 | 0.5000 | -1.8e-15 |
| `storage_efficiency` | 0.0 | -0.0000 | -2.7e-15 |

Intercept recovered as 10.000000, `R2 = 1.0000000000`, and the ranking is
correct including the sign-insensitive ordering of the negative coefficient.

**Case B -- a single raw feature, `y = 7 * area_m2`:** fitted
`beta(area) = 201 379 621.9677` against the analytic `7 * sd(area) =
201 379 621.9677` -- identical. Every other coefficient below 1e-6.

**Case C -- pure interaction, `y = z1 * z2`, no linear component:** maximum
`|beta| = 0.0101` and `R2 = 0.000239`. The surrogate correctly reports *no
linear signal* rather than manufacturing one from an interaction it cannot
represent. This is the behaviour that matters most for honesty, and it passes.

**The estimator is correct.** Nothing in Phase 8 disputes the implementation.

### Finding 8.1 -- what the ranking actually measures

**PASS WITH CAVEAT. Severity LOW. Interpretation.**

Phase 3 established that capacity is a pure product with every elasticity
exactly +1. If that were the whole model, physics could not break any tie and
the ranking would be determined **entirely by how wide each prior is**, not by
any property of the parameter.

Measured direct elasticities at the prior midpoint tell a more interesting
story:

| Feature | Elasticity `d(ln M)/d(ln x)` |
| --- | --- |
| `area_m2` | +1.000 |
| `thickness_m` | +1.000 |
| `porosity` | +1.000 |
| `storage_efficiency` | +1.000 |
| `pressure_pa` | +1.006 |
| `temperature_k` | **-5.234** |

Pressure and temperature enter through the equation of state rather than
directly, and the EOS amplifies temperature by a factor of five.

The standardized coefficients decompose cleanly as
`beta ~= mean(M) * elasticity * CV`, where CV is the coefficient of variation of
the prior:

| Feature | CV | Elasticity | Predicted beta | Actual beta |
| --- | --- | --- | --- | --- |
| `storage_efficiency` | 0.3208 | +1.000 | 6.019 | 5.966 |
| `area_m2` | 0.2887 | +1.000 | 5.417 | 5.383 |
| `thickness_m` | 0.2165 | +1.000 | 4.063 | 4.062 |
| `porosity` | 0.1925 | +1.000 | 3.611 | 3.602 |
| `pressure_pa` | 0.1443 | +1.006 | 2.725 | 2.612 |
| `temperature_k` | 0.0299 | -5.234 | -2.940 | -2.788 |

Every coefficient predicted within about 5%. So the ranking is
**prior width multiplied by physical leverage**, and for four of six inputs the
leverage term is identically 1.

Ranking by CV alone would give
`[storage_efficiency, area_m2, thickness_m, porosity, pressure_pa,
temperature_k]`; the surrogate gives the same order except that **temperature
and pressure swap**, because temperature's 5x leverage beats pressure's 4.8x
wider prior.

That swap is the surrogate doing real work rather than re-stating the priors,
and it is the correct answer. But four of six positions are decided by prior
width alone, so a reader who interprets the ranking as "which parameter matters
physically" is over-reading it for most of the list.

### Finding 8.2 -- a constant input and an uninfluential input are indistinguishable in the output

**REVIEW REQUIRED. Severity MEDIUM.**

Phase 7 Finding 7.1 established that only three of six priors vary in the
real-data path. The degenerate-column guard handles those three correctly -- the
mechanism is verified below -- and forces their coefficients to exactly `0.0`.

The consequence appears in `sensitivity()` output for the real-data path:

| Feature | Coefficient | Actually |
| --- | --- | --- |
| `storage_efficiency` | +4.1491 | varies |
| `porosity` | +3.8594 | varies |
| `pressure_pa` | +0.1319 | varies |
| `area_m2` | **+0.0000** | **CONSTANT** |
| `thickness_m` | **+0.0000** | **CONSTANT** |
| `temperature_k` | **+0.0000** | **CONSTANT** |

A constant input and a genuinely uninfluential input both print `0.0000`. The
return type is `list[tuple[str, float]]` and carries nothing else.

This is materially misleading in this specific model, because the three inputs
sitting at the bottom of the ranking are:

- `area_m2` and `thickness_m` -- which Phase 3 measured as elasticity exactly +1
  each, the two largest linear multipliers in the equation, and which Phase 3
  also established have **no source data and no literature range**; and
- `temperature_k` -- which this phase measures as the **highest-leverage input
  in the entire model** at elasticity -5.234, and which Phase 6 measured as
  worth up to 18.6% of capacity through method choice alone.

So the three parameters a user most needs to think about are displayed at the
bottom of a list labelled "sensitivity", indistinguishable from parameters that
genuinely do not matter.

Mitigating facts: this is CLI-only, and the CLI also prints `deterministic` and
the prior ranges it used, so the information is recoverable from the same
output. The defect is that the sensitivity block alone inverts the correct
reading.

### Finding 8.3 -- the degenerate-column guard is correct

**PASS.**

The guard exists because a constant column's computed standard deviation is
floating-point residue, not zero, and dividing residue by residue produces noise
that `lstsq` will happily fit. Measured on the real-data path:

| Feature | Peak-to-peak | Raw std | Stored std | Coefficient |
| --- | --- | --- | --- | --- |
| `area_m2` | 0 | 0 | 1 | +0.0000 |
| `thickness_m` | 0 | 0 | 1 | +0.0000 |
| `porosity` | 0.25 | 0.07212 | 0.07212 | +3.8594 |
| `pressure_pa` | 1.198e+06 | 3.442e+05 | 3.442e+05 | +0.1319 |
| `temperature_k` | 0 | **5.684e-14** | 1 | +0.0000 |
| `storage_efficiency` | 0.03 | 0.008653 | 0.008653 | +4.1491 |

`temperature_k` is exactly the case the code comment describes: peak-to-peak is
0 but the computed std is 5.7e-14. An absolute threshold would have to be chosen
per feature magnitude; the implemented test compares peak-to-peak against
`max(|mean|, 1)`, which is scale-free and catches it.

All three constant columns are forced to exactly `0.0`, and `predict()` remains
safe because the stored std of 1.0 is multiplied by a zero coefficient.

**The guard was verified by removing it.** Refitting the real-data path with
only an exact-zero check (`np.where(std == 0.0, 1.0, std)`) in place of the
scale-aware one:

| Feature | Unguarded coefficient | Actually |
| --- | --- | --- |
| `temperature_k` | **+6.0355** | **CONSTANT** |
| `storage_efficiency` | +4.1706 | varies |
| `porosity` | +3.8392 | varies |
| `pressure_pa` | +0.1444 | varies |
| `thickness_m` | +0.0000 | CONSTANT |
| `area_m2` | +0.0000 | CONSTANT |

A constant temperature column is reported as **the single strongest driver**,
ahead of both genuinely varying literature ranges. `area_m2` and `thickness_m`
are still caught, because their computed std is exactly zero -- it is only
`temperature_k`, whose residue std is 5.7e-14, that slips through. That is
precisely the case the code comment describes, and it confirms the guard is
load-bearing rather than defensive.

### Finding 8.4 -- surrogate fidelity depends on prior width and is not guarded

**PASS WITH CAVEAT. Severity LOW.**

A linear surrogate approximates a six-way product, so its fit degrades as the
priors widen:

| Prior width | R2 | RMSE as % of P50 |
| --- | --- | --- |
| x0.25 of declared | 0.9924 | 1.23% |
| as declared (`DEPLETED_GAS_ANALOG`) | 0.8872 | **22.97%** |
| x3 of declared | 0.5211 | **368.24%** |

At the declared priors the surrogate explains 89% of variance but its RMSE is
23% of P50; on the real-data path it does better, `R2 = 0.9477` and RMSE 12.2%
of P50.

Nothing in the code warns when `R2` falls low enough that the ranking becomes
unreliable. But the module docstring is explicit -- *"it is a sensitivity
screen, not a replacement for the volumetric calculation"* -- and `cli.py`
prints `r2` alongside the ranking, so a user has what they need to judge it.
No change proposed.

### Finding 8.5 -- a single sample yields an all-zero ranking, silently

**PASS WITH CAVEAT. Severity LOW.**

With `n = 1` every column has peak-to-peak 0, so every feature is classified
degenerate and all six coefficients are `0.0`. Likewise, when every prior is a
point, `ss_tot = 0` and `evaluate` returns `r2 = 1.0` by the explicit fallback
on line 113.

Both are defensible -- there is genuinely no variance to explain -- and `R2 =
1.0` for a perfectly constant target is the conventional choice. Neither is
signalled as a special case, and an all-zero ranking beside `R2 = 1.0` could
read as a confident result rather than an empty one. Paired with Phase 7
Finding 7.4 (`MIN_SAMPLES = 1`).

### Input validation

| Case | Behaviour |
| --- | --- |
| empty sample list | rejected, "need at least one sample" |
| `len(samples) != len(masses_mt)` | rejected, explicit message |
| `predict` with wrong feature count | rejected, names `FEATURE_ORDER` and both counts |
| `n = 1` | accepted, all coefficients 0.0 |
| all priors degenerate | accepted, all coefficients 0.0, `r2 = 1.0` |

**PASS.**

### Findings table

| Item | Status | Severity | Evidence | Action |
| --- | --- | --- | --- | --- |
| Coefficient estimation | PASS | - | Recovers known betas to 2.7e-15; R2 = 1.0 | None |
| Raw-unit scaling | PASS | - | `beta = 7*sd(area)` reproduced exactly | None |
| Blind to interactions, and says so | PASS | - | Pure interaction gives max abs beta 0.010, R2 = 0.0002 | None |
| Standardization | PASS | - | Population std; coefficients comparable across units | None |
| Degenerate-column guard | PASS | - | Catches a 5.7e-14 residue std; forces exact 0.0 | None |
| Input validation | PASS | - | 3/3 invalid cases rejected with specific messages | None |
| **Constant vs uninfluential indistinguishable** | **REVIEW REQUIRED** | **MEDIUM** | 3 of 6 print 0.0000; they include the 2 largest multipliers and the highest-leverage input | Documented |
| Ranking is prior width x leverage | PASS WITH CAVEAT | LOW | 4 of 6 elasticities are exactly 1; `beta ~= mean*elast*CV` within 5% | Documented |
| Fidelity degrades with prior width | PASS WITH CAVEAT | LOW | R2 0.9924 -> 0.8872 -> 0.5211; no warning, but `r2` is printed | None |
| `n=1` gives an all-zero ranking | PASS WITH CAVEAT | LOW | Every column degenerate; `r2 = 1.0` | Documented |

### Scientific numbers changed?

**NO.** No file under `src/` was modified in Phase 8.

### Downstream impact

None. The surrogate consumes Monte Carlo output and produces a ranking consumed
only by the CLI. Nothing downstream reads it, and no capacity, pressure or
injectivity number depends on it.

The new measurement that *does* propagate is the elasticity table. **Temperature
has elasticity -5.234, five times any other input**, and that number sharpens
three earlier findings into one statement:

- Phase 6 Finding 6.6: temperature method choice is worth up to 18.6% of
  capacity -- now explained, not merely observed. A 3.6% error in T becomes an
  18.6% error in capacity because the leverage is -5.2.
- Phase 7 Finding 7.1: temperature is a **point value** in the real-data path,
  so the highest-leverage input in the model contributes **zero** to the
  reported uncertainty band.
- Phase 8 Finding 8.2: and it is displayed at the **bottom** of the sensitivity
  ranking.

Phase 12 inherits that three-way conjunction. It is the clearest example so far
of the audit's recurring theme: each layer is individually defensible and the
combination misleads.

### Remaining uncertainty

1. **Elasticities were measured at the prior midpoint.** Temperature's -5.234 is
   a local value; the EOS is strongly nonlinear, so leverage varies across the
   sampled range and is larger near the critical region (Phase 1 Finding 1.3).
2. **Only first-order sensitivity is available.** Case C confirms the surrogate
   cannot see interactions. For a pure product the interactions are real but
   structurally simple; a variance-based method (Sobol) would quantify them and
   none is implemented.
3. **No threshold defines an acceptable R2.** 0.8872 was judged adequate for
   ranking here on the basis that the ranking matches the independent
   elasticity-times-CV decomposition, not against any stated criterion.
4. **The ranking is conditional on the priors.** It is not a property of the
   model, and changing any prior width reorders it. Nothing in the output states
   this.

---

## Phase 9 -- Provenance and literature

Audited 2026-09-20. Scope: every scientific constant in `src/`, the `Citation`
and `EvidenceClass` machinery, and the two primary sources the project actually
cites. **Both primary sources were obtained and read in full** -- the Phase 3
and Phase 5 attempts failed on DNS, this one succeeded.

| Source | Obtained | Pages |
| --- | --- | --- |
| CSLF-T-2008-04 (Bachu, 2008), Phase III Report | yes, `hgeo.energy.gov` | 21 |
| Donda, Volpi, Persoglia & Parushev (2011), IJGGC 5(2) | yes, OGS repository | 9 |

This phase resolves the two REVIEW REQUIRED items Phase 3 deferred here, and it
sharpens one of them considerably.

### Finding 9.1 -- Finding 3.1 is CONFIRMED, and now quantified from the source

**REVIEW REQUIRED. Severity MEDIUM. Conservative. Supersedes the Phase 3 estimate.**

CSLF-T-2008-04 equation (15), verbatim:

> `MCO2 = A x h x phi x rhoCO2 x E`
>
> "where rhoCO2 is the average CO2 density evaluated at pressure and temperature
> that represents storage conditions anticipated for a specific deep saline
> aquifer, and **E is a storage efficiency factor that reflects the total pore
> volume filled with CO2**. No distinction is made between CO2 stored by various
> mechanisms."

That is exactly the implemented equation. The decisive passage follows
immediately -- the source lists what was varied to produce the 1-4% range:

> "In the Monte Carlo simulations that produced the recommended range for E,
> various calculation components were varied as follows:
> - Fraction of the saline aquifer that is suitable for CO2 storage: 0.2 to 0.8
> - **Fraction of the geological unit that has the porosity and permeability
>   required for CO2 injection: 0.25 to 0.75**
> - **Fraction of interconnected porosity: 0.6 to 0.95**
> - Areal displacement efficiency: 0.5 to 0.8
> - Vertical displacement efficiency: 0.6 to 0.9
> - Fraction of net aquifer thickness contacted (occupied) by CO2 as a result of
>   CO2 buoyancy: 0.2 to 0.6
> - Pore-scale displacement efficiency: 0.5 to 0.8."

**E contains a net-to-gross term.** The second bullet -- the fraction of the
geological unit with the required porosity and permeability, 0.25 to 0.75 -- is
the net-to-gross reduction, and it is inside E. The third bullet is the
effective-to-total porosity reduction, also inside E.

The public API requires `thickness_m` to be **net** reservoir thickness
(`USER_INPUT_SPEC`: "Net reservoir thickness inside the closure -- NOT the gross
chronostratigraphic interval") and then multiplies by E. The net-to-gross
reduction is therefore applied twice.

Phase 3 bounded this at 1.4x-10x using generic published sub-factor ranges. The
primary source gives the actual range:

| CSLF net-to-gross term | Understatement from double-counting |
| --- | --- |
| 0.75 (high end) | **1.33x** |
| 0.50 (mid) | 2.00x |
| 0.25 (low end) | **4.00x** |

**The corrected bound is 1.33x to 4x.** That replaces the Phase 3 figure, which
was too wide at the top because it also folded in the porosity term -- and the
porosity term turns out not to apply (Finding 9.2).

**The precedent is worse than Phase 3 recorded.** Phase 3 declined to correct
this partly on the grounds that Donda et al. do the same thing. They do, and
explicitly. Donda equation (1):

> `MCO2e = A h phi_RS rho_CO2r Seff`
>
> "where ... **h is the effective thickness, i.e. average thickness of aquifer x
> average net to gross ratio (m)**, phi_RS is the average reservoir porosity (%)
> ... and Seff is the storage efficiency factor."

So Donda multiplies gross thickness by a net-to-gross ratio *and* applies the
USDOE 1-4% E on top. That is an unambiguous double-count, not a different
convention.

More telling, Donda's own description of E omits the term:

> "The storage efficiency factor for aquifers is currently under debate. It
> accounts for several parameters such as **net-to-effective porosity, areal and
> vertical displacement efficiency, and gravity effects**."

Net-to-gross thickness is not in that list. The authors appear to have believed
E contained only a porosity term, and moved the thickness term into `h`
accordingly. The primary CSLF source shows both are inside E.

**Conclusion.** The implementation inherits a real double-count from its own
cited regional precedent, and the precedent itself appears to rest on a
misreading of the methodology it cites. The screening number is conservative by
**1.33x to 4x** on the thickness axis. Still documented rather than corrected:
changing it alters every capacity number and is the frozen-baseline decision.

### Finding 9.2 -- Finding 3.2 is RESOLVED: the porosity pairing is correct

**PASS. Severity resolved from LOW REVIEW REQUIRED.**

Phase 3 could not establish whether `porosity` means total or effective, and
inferred from the derivation method that it must be total. The primary sources
confirm the inference on both sides.

**What E expects.** The CSLF component list includes "Fraction of interconnected
porosity: 0.6 to 0.95" *inside* E. If the caller supplied effective (connected)
porosity, that reduction would be double-counted. E therefore expects **total**
porosity.

**What the adopted range is.** Donda et al.:

> "The porosity of the potential reservoirs was estimated from P-wave velocity
> measurements from sonic logs and empirical functions (Schlumberger, 2000)."

Sonic-log transforms against the Schlumberger interpretation charts return
**total** porosity. Donda then calls it "the average reservoir porosity" and
separately describes E as accounting for "net-to-effective porosity" -- i.e.
treats the connected fraction as living inside E, consistently.

**The pairing is correct**, and unlike the thickness axis there is no
double-count. The defect Phase 3 identified was that this reasoning appeared
nowhere in the code or docs, and that remains true: a grep for "total porosity",
"effective porosity" and "connected porosity" across `src/`, `docs/` and
`frontend/` still returns zero matches. That is now a documentation gap with a
verified answer behind it, and a candidate for disclosure-only treatment.

### Finding 9.3 -- the scale-mismatch warning is accurate, and the source says so explicitly

**PASS. Credit where due.**

CSLF-T-2008-04 on applicability:

> "methods are based on volumetrics and are applicable to country-, regional-
> and basin-scale [assessments]"

and on what is out of scope:

> "**Local- and site-scale assessments are explicitly excluded** from the Carbon
> Sequestration Atlas of United States and Canada."

Donda's area term:

> "A is the area that **defines the basin or the region occupied by the aquifer**
> (m2)"

with Table 2 areas spanning **45 to 1,800 km2**.

The project's `SCALE_MISMATCH_WARNING` states that CSLF's efficiency is
"calibrated at basin/aquifer scale" and Donda's porosity is "a regional
compilation", while area and net thickness are supplied at closure scale, and
that no correction factor is applied because none is derivable. **Every clause
of that warning is confirmed by the primary sources.** It understates nothing.

### Finding 9.4 -- the stored quote and URL are verbatim and live

**PASS.**

`CSLF_2008.quote` as stored:

> "through Monte Carlo simulations ... the USDOE Subgroup obtained a range of
> values for these storage efficiency coefficients for the 15% and 85%
> confidence intervals, which are ... between 1% and 4% for deep saline
> aquifers"

Primary source, page 14:

> "...through Monte Carlo simulations of CO2 storage in coal beds and in deep
> saline aquifers for conditions characteristic to North America, the USDOE
> Subgroup obtained a range of values for these storage efficiency coefficients
> for the 15% and 85% confidence intervals, which are between 0.28 and 0.40 for
> coal beds, and between 1% and 4% for deep saline aquifers."

Verbatim, with both elisions correctly marked, and neither elision removes a
qualifier that changes the meaning. The stored `url` resolves to the document
that was fetched.

### Finding 9.5 -- the recorded Donda discrepancy is real, and the project's resolution is provably right

**PASS. Credit where due.**

`docs/scenario-literature-review.md` records:

> "Note a discrepancy in the published Italian paper: the same paragraph states
> '1% or 4%' and then reports results as '(Seff = 1% or 5%, respectively)'. We
> adopt the CSLF 1-4% figure and record the inconsistency rather than silently
> choosing."

The discrepancy is confirmed verbatim:

> "computations of the potential storage capacity were made assuming that **1% or
> 4%** of the total pore volume can be filled by CO2 (US DOE, 2008). Our
> calculation yields a very conservative estimate of the effective capacity of
> the selected areas, equal to about 3 Gt or about 14.7 Gt (**Seff = 1% or 5%**,
> respectively)."

Phase 9 can now settle which is the typo, from the paper's own arithmetic:

| Evidence | Value | Implies |
| --- | --- | --- |
| Table 2 column headers | `Seff = 1 %` and `Seff = 4 %` | 4% |
| Table 2 totals | 2,950 Mt and 11,800 Mt | ratio exactly **4.00** |
| Text | "about 3 Gt or about 14.7 Gt" | 2,950 x 5 = 14,750 -> 5% |

The table was computed at 4% and the text was written at 5%. The project adopted
the table-consistent value. **The choice was correct**, and it can now be
demonstrated rather than merely asserted.

### Finding 9.6 -- the citation locator says 13 reservoirs; Table 2 has 14

**PASS WITH CAVEAT. Severity LOW. Documentation only.**

`DONDA_2011.locator` reads "Table 2, porosity column (13 Italian potential
reservoirs)", and `docs/scenario-literature-review.md` reproduces a 13-row
table. The published Table 2 has **14** rows -- the omitted one is **Calabria
ionica** (1,280 m, 320 km2, 350 m, 30%).

The adopted range is unaffected: across all 14 rows the porosity minimum is
still 10% (Lombardia 1) and the maximum still 35% (Marche 1, Sicilia 1). Donda's
own text says "Our analysis has identified 14 suitable areas", which is the
figure the locator should carry.

A factual error in a citation locator, with no numerical consequence.

### Finding 9.7 -- the cited methodology uses absolute pressure

**Supports Phase 4 Finding 4.1. Severity MEDIUM (unchanged).**

Donda on how CO2 density was obtained:

> "The CO2 density at the mean reservoir depth was calculated by assuming a
> temperature and **pressure at surface of 15 degC and 1 atm**, respectively."

The regional study this project cites builds its pressure profile from
**1 atm at surface**, i.e. absolute pressure. Phase 4 established that
`hydrostatic_pressure_pa` returns 0 Pa at zero depth -- gauge.

So Finding 4.1 is not merely a thermodynamic argument about what the EOS
requires; the implementation also diverges from the convention of the
methodology it adopts. That strengthens the case for the one-line `P_atm`
correction without changing its magnitude.

A second, smaller divergence: Donda uses per-area geothermal gradients with a
default of **25 degC/km**. Phase 6 used a generic 30 K/km to decompose the
temperature-method spread; at 25 degC/km the depth share of that spread would be
smaller, so the Phase 6 decomposition is conservative in the direction of
attributing *less* to depth than the project's own cited source would.

### Finding 9.8 -- two of roughly twenty scientific constants carry a citation

**REVIEW REQUIRED. Severity MEDIUM.**

Full inventory of module-level scientific constants in `src/`:

| Constant | Value | Class | Citation object? | Verified by |
| --- | --- | --- | --- | --- |
| `storage_efficiency` | 0.01-0.04 | adopted | **yes**, `CSLF_2008` | Phase 9, primary source |
| `porosity` | 0.10-0.35 | adopted | **yes**, `DONDA_2011` | Phase 9, primary source |
| `KG_PER_MT` | 1e9 | definitional | n/a | Phase 2 |
| `METRES_PER_FOOT` | 0.3048 | definitional (exact) | n/a | Phase 2 |
| `FEET_PER_METRE` | 3.280839895013123 | derived | n/a | Phase 2 |
| `KELVIN_OFFSET` | 273.15 | definitional (ITS-90) | n/a | Phase 2 |
| `STANDARD_GRAVITY_M_S2` | 9.80665 | definitional (CGPM 1901) | n/a | Phase 2 |
| `CO2_R_J_MOL_K` | 8.314462618 | definitional (SI 2019) | n/a | Phase 1 |
| `SECONDS_PER_YEAR` | 31 557 600 | convention (Julian) | no | Phase 2 |
| `CO2_TC_K` | 304.1282 | physical property | **no** | Phase 1, numerically |
| `CO2_PC_PA` | 7.3773e6 | physical property | **no** | Phase 1, numerically |
| `CO2_OMEGA` | 0.225 | physical property | **no** | Phase 1, numerically |
| `CO2_MW_KG_MOL` | 0.0440095 | physical property | **no** | Phase 1, numerically |
| `CO2_Z_RA` | 0.2722 | physical property | **no** | Phase 1, numerically |
| `DEFAULT_FRACTURE_GRADIENT_PA_M` | 15 000 | engineering | **no** | Phase 5, plausibility only |
| `DEFAULT_SAFETY_FACTOR` | 0.9 | regulatory | **no** | not validated |
| `RESERVOIR_DEPTH_FRACTION` | 0.85 | heuristic | **no** | not validated |
| `DEPTH_CONFLICT_TOLERANCE_M` | 1.0 | heuristic | **no** | not validated |
| `brine_density_kg_m3` | 1020-1100 | declared physics | no, by design | Phase 4 |
| CLI `permeability_m2` | 8e-14 | engineering | **no** | Phase 5 |
| CLI `viscosity_pa_s` | 4.5e-4 | engineering | **no** | not validated |
| CLI `compressibility_1_pa` | 1.2e-9 | engineering | **no** | not validated |

Two constants carry a `Citation`. Seven more need none, being definitional or
derived. The remaining **thirteen are scientific or engineering choices with no
recorded provenance**, and five of them (the CO2 critical constants) sit inside
the frozen `properties.py` where Phase 1 verified them numerically against Span
& Wagner but recorded no source object.

This is not a correctness finding -- Phases 1, 2, 4 and 5 checked the values
themselves. It is an asymmetry in the project's own standard: the `Citation`
dataclass, `EvidenceClass`, the `locator`/`quote`/`url` fields and the
`_PLACEHOLDER_CITATION` guard all exist to make provenance inescapable for
scenario assumptions, and the machinery stops at the scenario boundary. Anything
hard-coded in a module escapes it entirely.

`DEFAULT_SAFETY_FACTOR = 0.9` is the sharpest instance: it is described as "the
fraction of the fracture pressure regulators typically allow" and names no
regulator, no jurisdiction and no document, while being a direct multiplier on
the injection-rate ceiling.

### Finding 9.9 -- the primary source is internally inconsistent about what E multiplies

**PASS WITH CAVEAT. Severity LOW. The implementation reads it correctly.**

CSLF equation (15) is `A x h x phi x rho x E`, in which E multiplies `A h phi` --
a **pore** volume. Two sentences later the same page says the Monte Carlo
produced "a range for E between 1 and 4% **of the bulk volume** of a deep saline
aquifer".

Those cannot both be right. Donda resolves it the same way the equation does --
"1% or 4% of the **total pore volume** can be filled by CO2" -- and so does this
project: `docs/scenario-literature-review.md` glosses `storage_efficiency` as
"Fraction of pore volume CO2 can occupy".

The implementation follows the equation and the regional precedent, which is the
defensible reading. Recorded because a future reader checking the source against
the code will hit the same contradiction.

### EvidenceClass assignments

| Parameter | Assigned | Justified? |
| --- | --- | --- |
| `storage_efficiency` | `generic` | **yes** -- CSLF says "conditions characteristic to North America" |
| `porosity` | `regional` | **yes** -- 14 Italian reservoirs, same play type |
| `pressure_pa` | `generic` | **yes** -- the normally-pressured assumption, not a measurement |
| placeholder scenarios | `placeholder` | **yes** -- guarded by `_PLACEHOLDER_CITATION` |

All four are correct against the sources. **PASS.**

### Findings table

| Item | Status | Severity | Evidence | Action |
| --- | --- | --- | --- | --- |
| **Finding 3.1 confirmed and re-bounded** | **REVIEW REQUIRED** | **MEDIUM** | CSLF E contains a 0.25-0.75 net-to-gross term; understatement is 1.33x-4x | Supersedes the Phase 3 estimate |
| **Finding 3.2 resolved** | **PASS** | - | E contains the interconnected-porosity term, so it expects total porosity; Donda's is sonic-derived total | Reasoning still undocumented |
| Scale-mismatch warning accuracy | PASS | - | CSLF excludes site-scale explicitly; Donda A is basin area, 45-1,800 km2 | None |
| Stored quote and URL | PASS | - | Verbatim; elisions remove no qualifier; URL live | None |
| Donda 1%/4% vs 5% discrepancy | PASS | - | Real; Table 2 ratio is exactly 4.00, so the project chose correctly | None |
| `EvidenceClass` assignments | PASS | - | 4/4 justified against the sources | None |
| Citation locator "13 reservoirs" | PASS WITH CAVEAT | LOW | Table 2 has 14; range unaffected | Disclosure-only candidate |
| Cited methodology uses absolute pressure | - | MEDIUM | Donda: "pressure at surface of ... 1 atm" | Supports Finding 4.1 |
| **13 constants have no recorded provenance** | **REVIEW REQUIRED** | **MEDIUM** | 2 of ~20 carry a `Citation`; `DEFAULT_SAFETY_FACTOR` names no regulator | Documented |
| CSLF "bulk volume" vs equation (15) | PASS WITH CAVEAT | LOW | Source self-inconsistent; implementation follows the equation | Documented |

### Scientific numbers changed?

**NO.** No file under `src/` was modified in Phase 9.

### Downstream impact

Phase 9 changes no computation but changes two entries in the frozen table:

- **Finding 3.1's bound narrows from 1.4x-10x to 1.33x-4x**, now sourced rather
  than estimated, and its justification strengthens: the double-count is
  explicit in both cited sources, and the regional precedent that Phase 3 used
  as mitigation turns out to rest on a misreading.
- **Finding 3.2 moves from REVIEW REQUIRED to PASS.** The porosity pairing is
  correct. One of the eight frozen items is resolved without a code change.

Finding 9.7 adds an independent argument for the Phase 4 Finding 4.1 correction:
the cited methodology uses absolute pressure, so the gauge/absolute divergence
is a departure from the project's own adopted source, not only from
thermodynamic convention.

Nothing blocks Phase 10. The literature layer is sound where it is cited, and
the gaps are now enumerated.

### Remaining uncertainty

1. **The CSLF sub-factor ranges are North American.** The 0.25-0.75
   net-to-gross range bounding Finding 9.1 reflects "various lithologies and
   geological depositional systems that occur in North America". No Piemonte
   net-to-gross exists in this repository, so 1.33x-4x is a bound from the
   source, not a site estimate.
2. **Schlumberger (2000) was not consulted.** The conclusion that sonic
   transforms return total porosity rests on standard petrophysics rather than
   on the chart book Donda cites.
3. **`van der Meer and Egberts (2008)` and `Vangkilde-Pedersen et al. (2008)`**,
   which Donda invokes for the efficiency factor's meaning and for the
   GeoCapacity 2% value, were not retrieved. The GeoCapacity 2% sits inside the
   adopted 1-4% range, so nothing turns on it.
4. **The thirteen uncited constants were checked for plausibility, not
   provenance.** Phase 5 found the fracture gradient defensible at 0.6631 psi/ft
   and Phase 1 verified the CO2 constants numerically, but plausibility is not a
   source.
5. **`DEFAULT_SAFETY_FACTOR = 0.9` remains unvalidated.** No regulator is named
   and none was located. It multiplies the injection-rate ceiling directly.

---

## Phase 10 -- Real-data end-to-end validation

Audited 2026-09-20. Seven named wells traced raw -> normalized -> assumptions ->
scenario -> model inputs -> result, against the live `data/` directory
(46 normalized well records; all three structured sources present).

All seven requested wells are in the corpus.

### Raw -> normalized

| Well | Depth (m) | Datum | T (K) | Method | Gross h (m) |
| --- | --- | --- | --- | --- | --- |
| SALUZZO\|1 | 1 527.5 | unknown | 318.15 | squarci_taffi | 1 104.7 |
| TRECATE\|9\|ST | 6 087.0 | unknown | 452.15 | fertl_wichmann | 619.0 |
| DESANA\|1 | 3 224.9 | unknown | 370.15 | squarci_taffi | 1 098.5 |
| ASTI\|1 | 1 247.0 | unknown | 318.15 | squarci_taffi | 880.0 |
| MALOSSA\|15 | 5 491.0 | unknown | 416.15 | fertl_wichmann | 355.0 |
| CRESCENTINO\|1 | 1 722.0 | unknown | **MISSING** | - | MISSING |
| ASIGLIANO\|1 | **MISSING** | unknown | 360.15 | squarci_taffi | 914.0 |

Identity parsing is correct in all seven, including the sidetrack suffix:
`TRECATE 9ST -> TRECATE|9|ST`.

### Blocking behaviour is correct, and there are two distinct blocked shapes

`CRESCENTINO|1` has a depth but no reservoir temperature, and is **blocked on
`temperature_k`** with the reason "no source value, and temperature_k may not be
supplied by a scenario". `ASIGLIANO|1` has a temperature but no depth, and is
**blocked on `pressure_pa`**. Both are the correct outcome: temperature is
non-assumable, and pressure is derived from depth.

Note for clients: the API returns **two different blocked payloads**.

| Situation | `status` | Carries | Does not carry |
| --- | --- | --- | --- |
| User inputs omitted | `blocked` | `required_user_inputs`, `reason`, `error` | `missing_fields` |
| Source data incomplete | `blocked` | `missing_fields`, `missing_reasons`, full `screening_inputs` | `required_user_inputs` |

Both are well-formed and both match the documented contract; a consumer must
handle both shapes. An earlier probe in this phase read `missing_fields` on the
first shape, found it absent and briefly looked like a defect. It is not -- the
key belongs to the other shape.

### Full trace with user inputs (A = 8e7 m2, h = 35 m)

| Well | P (MPa) | T (K) | P10 | P50 | P90 | mean |
| --- | --- | --- | --- | --- | --- | --- |
| SALUZZO\|1 | 15.28-16.48 | 318.15 | 5.242 | 10.644 | 20.257 | 11.835 |
| TRECATE\|9\|ST | 60.89-65.66 | 452.15 | 5.171 | 10.514 | 20.004 | 11.691 |
| DESANA\|1 | 32.26-34.79 | 370.15 | 5.071 | 10.311 | 19.616 | 11.465 |
| ASTI\|1 | 12.47-13.45 | 318.15 | 4.610 | 9.383 | 17.849 | 10.434 |
| MALOSSA\|15 | 54.93-59.23 | 416.15 | 5.514 | 11.200 | 21.310 | 12.455 |

Label partition is identical and correct for all five screenable wells:
`source = [temperature_k]`, `MODELLED = [pressure_pa]`,
`ASSUMED = [porosity, storage_efficiency]`, `USER = [area_m2, thickness_m]`.
The four labels are disjoint in every case.

**Independent midpoint recomputation** (no Monte Carlo, computed outside the
production path):

| Well | Midpoint recompute | MC P50 | Ratio | rho_CO2 |
| --- | --- | --- | --- | --- |
| SALUZZO\|1 | 12.004 Mt | 10.644 Mt | 1.128 | 762.14 |
| TRECATE\|9\|ST | 11.856 Mt | 10.514 Mt | 1.128 | 752.77 |
| DESANA\|1 | 11.628 Mt | 10.311 Mt | 1.128 | 738.26 |
| ASTI\|1 | 10.585 Mt | 9.383 Mt | 1.128 | 672.05 |
| MALOSSA\|15 | 12.631 Mt | 11.200 Mt | 1.128 | 801.96 |

The ratio is **1.128 for every well, to three decimals**. That is the expected
signature: the median of a product of uniforms sits below the product of their
midpoints by a factor that depends only on the shapes of the varying priors, and
`porosity` and `storage_efficiency` have identical ranges across all wells. The
only well-to-well variation is CO2 density. This is a strong consistency result
-- it demonstrates that nothing well-specific leaks into the Monte Carlo beyond
the state point.

Results are **bit-identical across repeat calls** (seed 42), and every result
carries the `interpretation` block with `site_specific = False`,
`certified = False` and one warning (the scale mismatch).

### Finding 10.1 -- a temperature observation deeper than the well itself

**REVIEW REQUIRED. Severity MEDIUM. Found only by going to real data.**

`TRECATE|9|ST` carries its total depth from the GEOTHOPICA `Anagrafica` sheet as
**6 087.0 m**. Its temperature observations, from the `Temperature` sheet of the
same workbook, are at:

`0, 1000, 2000, 3000, 3810, 3810, 4000, 5000, 5510, 5510, 6000, 6050, 6099,
6099, 6247.9, 6247.9 m`

The two deepest, at **6 247.9 m**, are **160.9 m below the well's recorded total
depth** -- 2.6% deeper than the hole. The selection rule picks exactly that
observation, because it is the deepest Fertl-Wichmann value and ranks best.

So for this well, pressure is computed at 6 087.0 m and temperature is taken
from a depth the well is not recorded as reaching. Two further source values
(6 096.0 m from both `pozzi-storici.csv` and `po_wells_clean.csv`) are recorded
as depth conflicts, and none of them reaches 6 247.9 m either.

A sidetrack can legitimately run deeper along-hole than the original hole, which
may be the explanation -- but then the recorded total depth is the wrong one, and
nothing reconciles them. **No check exists anywhere in the pipeline that a
temperature observation lies within the well.** The two values come from
different sheets and are never compared.

Checked across all five wells with both fields:

| Well | TD (m) | Deepest T obs (m) | Selected T at (m) | selected / TD |
| --- | --- | --- | --- | --- |
| SALUZZO\|1 | 1 527.5 | 1 522.6 | 1 522.6 | 0.997 |
| **TRECATE\|9\|ST** | **6 087.0** | **6 247.9** | **6 247.9** | **1.026** |
| DESANA\|1 | 3 224.9 | 3 200.4 | 3 200.4 | 0.992 |
| ASTI\|1 | 1 247.0 | 1 244.0 | 1 244.0 | 0.998 |
| MALOSSA\|15 | 5 491.0 | 5 387.0 | 5 387.0 | 0.981 |

This also **settles Phase 6 Finding 6.5 favourably in four cases**. That finding
worried that the 0.85 filter could let the selected temperature sit up to 15%
shallower than total depth. On real data the selected temperature is at
0.981-0.998 of TD in four wells -- effectively at TD. The one exception goes the
other way, and is this finding.

### Finding 10.2 -- Finding 4.2 quantified per well, and the missing piece identified

**REVIEW REQUIRED. Severity HIGH (unchanged). Magnitude narrowed from Phase 4.**

> **Revised 2026-09-24.** Read this finding with *Finding 4.2 / 10.2 revision*
> below. The `rho*g*quota` shift in the table moves the assumed water level from
> ground to sea level. It is not the removal of a datum or derrick-height error.
> The numbers are unchanged.

Every one of the seven wells has `depth_datum = unknown` and `depth_msl_m =
MISSING`, exactly as Phase 4 described. But **`surface_elevation_m` is PRESENT
for all seven** (from the GEOTHOPICA `quota` column).

That is the operative discovery: the elevation needed to correct the depth is
already ingested. The only missing piece is the datum *label* -- what surface the
depth was measured from. `docs/ingestion.md` already quotes the AGIP composite
logs saying *"Tutte le profondita sono riferite al piano tavola rotary"*. If that
statement can be established as applying to these wells, the correction becomes
computable from data the project already holds.

Magnitude, using the ingested elevations and treating depths as
rotary-table referenced, with brine at 1060 kg/m3:

| Well | TD (m) | Elevation (m) | P raw (MPa) | P corrected (MPa) | P overstated | Capacity overstated |
| --- | --- | --- | --- | --- | --- | --- |
| **SALUZZO\|1** | 1 527.5 | **310.0** | 15.878 | 12.656 | **25.46%** | **+15.59%** |
| ASTI\|1 | 1 247.0 | 132.0 | 12.963 | 11.590 | 11.84% | +10.87% |
| CRESCENTINO\|1 | 1 722.0 | 152.0 | 17.900 | 16.320 | 9.68% | n/a (blocked) |
| DESANA\|1 | 3 224.9 | 142.0 | 33.523 | 32.047 | 4.61% | +2.74% |
| TRECATE\|9\|ST | 6 087.0 | 139.0 | 63.275 | 61.830 | 2.34% | +1.37% |
| MALOSSA\|15 | 5 491.0 | 111.0 | 57.079 | 55.925 | 2.06% | +1.10% |

**On the real data the ground-to-sea shift is worth +1.10% to +15.59% on
capacity**, not the 8-36% Phase 4 estimated *(originally reported here as a
"capacity bias"; superseded by the banner above)*. Phase 4's figures used
illustrative depths; these use the actual ingested values and supersede them.
The shift is strongly depth-dependent -- an absolute elevation offset against a
growing column, so it is largest in shallow wells. SALUZZO|1 at 310 m elevation
on a 1 527.5 m well is the largest in this set.

~~One caveat on the correction itself: GEOTHOPICA `quota` is a **ground**
elevation, while a rotary table stands some metres above ground. The figures
above therefore slightly understate the true correction, by the derrick height.~~
*Withdrawn 2026-09-24:* the workbook depths are already below-ground depths (see
the revision below), so the rotary-table height has already been removed from
`z`.

### Finding 4.2 / 10.2 revision -- depth datum vs hydraulic reference

**Documentation revision, 2026-09-24. Status: REVIEW REQUIRED. Severity HIGH
(unchanged). No number, equation, test or baseline changed.**

Findings 4.2 and 10.2 treated one quantity as a single "datum" problem. It is
two questions, with different answers.

| Question | Status |
| --- | --- |
| 1. **Depth datum:** what surface is `depth_m` measured from? | **Supported** for SALUZZO\|1, DESANA\|1, ASTI\|1, MALOSSA\|15. Unknown for TRECATE\|9\|ST. |
| 2. **Hydraulic reference:** where is the water level, i.e. where does the brine column begin? | **Unresolved** for all five wells. |

#### 1. Depth datum -- supported for four wells

The AGIP composite logs state that their depths run from the rotary table. The
workbook `Anagrafica` depth equals the operator's rotary-table total depth
**minus the rotary-table height**, exactly, in all four documented wells:

| Well | Operator statement (composite log) | Rotary table / ground (m a.s.l.) | RT height (m) | Operator TD, RT (m) | Workbook `depth_m` (m) |
| --- | --- | --- | --- | --- | --- |
| SALUZZO\|1 | "riferite al P.T.R." (data printout) | 313.20 / 310.00 | 3.20 | 1530.7 | 1527.5 |
| DESANA\|1 | "Tutte le profondità sono riferite al piano tavola rotary" | 145.60 / 142.00 | 3.60 | 3228.50 | 3224.9 |
| ASTI\|1 | "riferite al P.T.R." (data printout) | 135.00 / 132.00 | 3.00 | 1250.0 | 1247.0 |
| MALOSSA\|15 | "Tutte le profondità sono riferite al piano tavola rotary" | 120.00 / 111.00 | 9.00 | 5500 ("5500 v.5497~") | 5491.0 |
| TRECATE\|9\|ST | No operator document in the project or in ViDEPI's public well list | workbook `quota` 139 only | unknown | unknown | 6087.0 |

Sources: `data/PDF/saluzzo_001.pdf`, `desana_001.pdf`, `asti_001.pdf`,
`malossa_015.pdf` (single-sheet ViDEPI composite logs, header elevation block
and observations column / data printout).

- For these four wells `depth_m` therefore **behaves as a below-ground depth**,
  and `quota` is the ground elevation.
- The relation is an arithmetic identity across four independent wells. No
  document states that GEOTHOPICA converted the depths.
- Conversion to depth below sea level, `depth_m - quota`, is **mathematically
  valid** for these four wells.
- The workbook is not internally uniform: ASTI|1's deepest `Lito-Stratigrafie`
  bottom (1250.0) is rotary-table referenced, while its `Anagrafica` depth is
  not. A datum label has to be per column, not per workbook.
- For TRECATE|9|ST the project holds only the workbook row (`quota` 139,
  `profondità` 6087) and depths of 6096 in `pozzi-storici.csv` and
  `po_wells_clean.csv`. No datum metadata exists. As a sidetrack, whether 6087 m
  is along-hole or vertical is also unrecorded.

#### 2. What the current code assumes about the water level

- `resolve_inputs` passes `float(record.depth_m.value)` as `z`
  (`src/ccs_screen/ingest/scenario.py:333-334`).
- `hydrostatic_pressure_pa` returns `rho * g * z`
  (`scenario.py:130`). It returns 0 at `z = 0`.
- So the brine column, and the zero of gauge pressure, start at `z`'s reference
  surface: **ground level** for the four wells above. The code contains no
  water-level variable, and this assumption is nowhere stated.
- Fracture pressure uses the same `depth_m`
  (`src/ccs_screen/ingest/completeness.py:171-172`, then
  `pressure.fracture_pressure_pa`). Both sides of the headroom comparison share
  that zero.
- The provenance `rationale` for derived pressure (`scenario.py`, the
  `hydrostatic_from_depth` branch) still carries the superseded framing: *"not
  corrected to a sub-sea datum ... this overstates the brine column"*. That is
  code text and is not changed here. It is recorded as a disclosure follow-up.

#### 3. What Finding 10.2's correction actually does

Finding 10.2 replaces `z` with `z - quota`. Because `P = rho*g*z` is linear, the
pressure falls by exactly `rho*g*quota`.

- Given the depth evidence above, `z - quota` is depth below **sea level**, and
  no air gap is being removed.
- The change therefore moves the assumed water level from **ground** to **sea
  level**. It is a change of hydraulic assumption, **not** the removal of a
  datum or derrick-height error.
- The +1.10% to +15.59% capacity figures in Finding 10.2 are the **sensitivity
  of capacity to that choice**. They are not a measured bias of the current
  code.
- The direction of any error in the current code is **not established**. It is
  anti-conservative only if the true water level lies below ground.
- Applied to reservoir pressure alone, the shift would also move only one side
  of the headroom comparison, because fracture pressure keeps the ground zero.
- Finding 4.2's sentence *"the brine column starts at the water table"* is
  consistent with the current code only if the water table is at ground. It is
  consistent with Finding 10.2's table only if the water table is at sea level.
  Neither has been shown.

#### 4. Hydraulic reference -- evidence per well

All four composite logs were read in full, including the data printouts. ViDEPI
was checked for further well documents. No regional compilation is substituted.

| Well | What exists | What it establishes |
| --- | --- | --- |
| SALUZZO\|1 | Printout: "PROVE DI STRATO", "PROVE DI PRODUZIONE", "WIRELINE FORMATION TESTS", "LEAK OFF TEST", "ANALISI" all **NESSUNA/NESSUNO**. Result: "mineralizzato ad acqua dolce e salata". | **No pressure or water-level measurement was made.** |
| DESANA\|1 | Formation test 2, 11-12/4/1954, 3059.12-3228.50 m (RT): salt water, NaCl 13.37 g/l, SG 1.0130 at 15 °C, 750 l recovered in empty drill pipe after 35 h 05 min; **no pressure recorded**. Production tests (1954, 1955, 1957), 2406-2465.50 m, Tortonian gas: wellhead shut-in 223 / 155 / 148 atm. Tubing pressure 197 atm (1955) to 73 atm (1961). | Water-zone test: transient recovery only, no pressure. Pressures are **wellhead pressures on a producing gas column**, not aquifer head. Gauge/absolute unstated. |
| ASTI\|1 | Nine formation tests and two production tests (printout "PROVE DI STRATO", "PROVE DI PRODUZIONE"). Pressures recorded as "Pressione statica di giacimento": 111 kg/cm² at 1139 m (q. -1004), 88 at 1129 m (q. -994), 64.5 at 861 m (q. -726), each marked **"non stabil."**; 96.6 at 1130 m "non stabilizzata"; 96.6 at 861 m (test "INSODDISFACENTE", mixed gas + salt water); 95 at 1167 m (q. -1032), production test 1 "non è interpretabile". Tubing liquid levels 335 m (production test 1, Nov 1958) and 750 m P.T.R. (production test 2, Oct 1963). | Every recorded pressure is **non-stabilised, gas-bearing or mixed, or from a failed/uninterpretable test**. The operator notes the final build-up of test 6 is below virgin pressure. The liquid levels are end-of-test levels in a gas/water well, not static levels. Gauge depths are rotary-table referenced. Gauge/absolute unstated. |
| MALOSSA\|15 | Observations column: formation tests in open hole and in casing, production tests, swab tests, analyses, vacuum test all **"Nessuna/Nessuno"**. Gas/condensate production from Zandobbio from 25/9/1979, no pressure given. | **No pressure or water-level measurement is recorded.** |
| TRECATE\|9\|ST | No composite log or well report in the project or ViDEPI's public well list. | **No evidence.** |

Two anomalies in the ASTI|1 printout are recorded, not resolved: tests 7 and 9
print the same 96.6 kg/cm² at gauge depths 269 m apart, and the printed sub-sea
values place the gauge-depth reference at 135 m, the rotary table, not the
ground.

**Conclusion:** the repository contains **no stabilised static water level and
no stabilised water-bearing formation pressure** for any of the five wells. The
evidence cannot distinguish water level at ground, at sea level, or at another
well-specific head.

#### 5. Minimum evidence before any numerical correction can be authorised

Per well, independently -- a measurement from one well is not transferred to
another:

1. A **stabilised static formation pressure** or a **static water level**,
2. from a **water-bearing** interval,
3. with the measurement depth **and its depth datum** stated,
4. the **pressure datum/reference** stated,
5. **gauge or absolute** stated,
6. and the **fluid** in the measured interval and wellbore column identified.

Pressures from gas-bearing intervals would additionally need the gas-water
contact and gas gradient before they could bear on water head. The likely source
is each well's AGIP final well report and the original test charts. Archive
references printed on the logs: SALUZZO 1 cod. 01547, ASTI 1 cod. 01497, DESANA 1
stamp 40593, MALOSSA 15 "Col 3784". For SALUZZO|1 and MALOSSA|15 the logs record
that no tests were run, so a direct measurement may not exist. A numerical change
would then need an explicit, disclosed owner decision on the water level, not an
unstated default.

#### 6. Not changed

No model output, hydrostatic equation, baseline test or code changed. No
water-level parameter was introduced. Neither ground level nor sea level is
adopted: the finding stays open.

Every passage that stated a datum error or a known direction for Finding 4.2 /
10.2 has been corrected in place, with the original wording quoted where it was
replaced. The only passages retained as original reasoning are labelled where
they stand:

- the Finding 4.2 title and body (Phase 4), under its revised status line and
  closing revision note;
- the Finding 10.2 opening, magnitude table and column labels, under the
  revision banner at the head of that finding;
- the `rationale` string quoted under *Baseline freeze and disclosure-only
  fixes*, which records code text as written.

Combined factors that include the 4.2 term are marked **conditional on a
sea-level water level**: Findings 11.2, 12.4 and 12.5.

### Finding 10.3 -- source depth conflicts are small, real, and fully recorded

**PASS. Credit where due.**

Every well with more than one depth source shows a disagreement, and every one is
captured as a `Conflict` with the file, table, row and column of the rejected
value:

| Well | Chosen | Also seen | Disagreement |
| --- | --- | --- | --- |
| SALUZZO\|1 | 1 527.5 | 1 531.0 (`pozzi-storici.csv` row 5906, `Prof`) | 0.23% |
| TRECATE\|9\|ST | 6 087.0 | 6 096.0 (two independent sources) | 0.15% |
| DESANA\|1 | 3 224.9 | 3 229.0 (two independent sources) | 0.13% |
| ASTI\|1 | 1 247.0 | 1 250.0 (two independent sources) | 0.24% |
| MALOSSA\|15 | 5 491.0 | 5 497.0 (two independent sources) | 0.11% |

All below 0.25%, negligible against the 2-25% pressure shift in Finding 10.2 (a
ground-to-sea water-level sensitivity, not an error magnitude). The provenance quality
here is high: a reader can go to the exact row of the exact file that was not
used.

### Finding 10.4 -- the gross/net separation holds on real data

**PASS.**

| Well | Gross h (m) | Used `thickness_m` (m) | Label | Ratio |
| --- | --- | --- | --- | --- |
| SALUZZO\|1 | 1 104.7 | 35.0 | USER | **31.6x** |
| DESANA\|1 | 1 098.5 | 35.0 | USER | 31.4x |
| ASIGLIANO\|1 | 914.0 | 35.0 | USER | 26.1x |
| ASTI\|1 | 880.0 | 35.0 | USER | 25.1x |
| TRECATE\|9\|ST | 619.0 | 35.0 | USER | 17.7x |
| MALOSSA\|15 | 355.0 | 35.0 | USER | 10.1x |
| CRESCENTINO\|1 | MISSING | 35.0 | USER | n/a |

Gross thickness is ingested and reported but **never** reaches `thickness_m`,
which is labelled `USER` in all seven. Had the substitution occurred, capacity
would have been overstated by 10x to 32x -- inside the 1.5x-128x envelope
Finding 3.4 established, and confirming that envelope on real data.

### Finding 10.5 -- the Phase 6 disclosure fix is doing real work

**PASS.**

The conflict notes rewritten under the baseline freeze now separate the two
cases on live data:

- `SALUZZO|1`: "values differ by 6.0 K **across 0 m of depth**" -- a genuine
  method disagreement at the same depth (318.15 K squarci_taffi vs 312.15 K
  non_stabilized, both at 1 522.6 m).
- `ASTI|1`: "7.0 K across 0 m" -- likewise genuine.
- `TRECATE|9|ST`: "53.0 K **across 738 m** of depth" -- mostly gradient.
- `MALOSSA|15`: "38.0 K across 642 m"; `DESANA|1`: "13.0 K across 200 m";
  `ASIGLIANO|1`: "14.0 K across 366 m".

Before the fix all six read "at comparable depth". The two wells where the
disagreement is purely methodological are now distinguishable from the four
where it is mostly depth, at a glance.

### Findings table

| Item | Status | Severity | Evidence | Action |
| --- | --- | --- | --- | --- |
| Identity parsing | PASS | - | 7/7 correct, incl. `TRECATE 9ST -> TRECATE\|9\|ST` | None |
| Blocking on missing source data | PASS | - | CRESCENTINO blocked on T, ASIGLIANO on P, both correctly | None |
| Label partition | PASS | - | Disjoint and identical across 5 screenable wells | None |
| Independent recomputation | PASS | - | Ratio 1.128 for all 5, explained by prior shape | None |
| Determinism | PASS | - | Bit-identical repeat calls at seed 42 | None |
| Interpretation block | PASS | - | Present on 7/7 with the scale warning | None |
| Depth source conflicts | PASS | - | All < 0.25%, each with file/table/row/column | None |
| Gross/net separation | PASS | - | Never substituted; would have been 10x-32x | None |
| Phase 6 disclosure fix | PASS | - | Separates 0 m from 738 m disagreements live | None |
| **T observation below total depth** | **REVIEW REQUIRED** | **MEDIUM** | TRECATE: 6 247.9 m obs in a 6 087.0 m well; no check exists | Documented |
| **Hydraulic-reference sensitivity, quantified** (original label "Datum bias, quantified", superseded) | **REVIEW REQUIRED** | **HIGH** | +1.10% to +15.59% on capacity if the water level is moved from ground to sea level; direction not established | Supersedes Phase 4 magnitude |
| Two blocked payload shapes | PASS WITH CAVEAT | LOW | Both documented; a client must handle both | Documented |

### Scientific numbers changed?

**NO.** No file under `src/` was modified in Phase 10.

### Downstream impact

Phase 10 revises one frozen entry and adds one:

- **Finding 4.2's magnitude narrows from 8-36% to +1.10%-+15.59% on capacity**,
  now computed on the actual ingested elevations rather than illustrative
  depths. *Revised 2026-09-24:* this range is the sensitivity of capacity to
  moving the assumed water level from ground to sea level. It is not a measured
  bias, and its direction is not established. The severity stays HIGH because
  the water level is unresolved and SALUZZO|1 at +15.6% is the largest
  sensitivity in a seven-well sample, not a bound.
- **Finding 10.2 identifies the missing piece**: elevation is already ingested
  for all seven wells. Only the datum label is absent. That converts Finding 4.2
  from "not correctable" to "correctable if the AGIP rotary-table statement can
  be established for these wells", which is a materially different proposition
  for the owner.
  *Revised 2026-09-24:* the datum label is now established for four wells, and
  those depths are already below ground. Correctability now depends on the
  hydraulic reference, which is unresolved (*Finding 4.2 / 10.2 revision*).
- **Finding 10.1 is new** and belongs to Phase 12's cross-model consistency
  list, alongside the closed-trap/infinite-aquifer and duplicate-thickness items.

Phase 6 Finding 6.5 is largely **discharged**: on real data the selected
temperature sits at 0.981-0.998 of total depth in four of five wells.

Nothing blocks Phase 11.

### Remaining uncertainty

1. **Seven wells is a sample, not a survey.** The corpus holds 46 normalized
   records; the +1.10% to +15.59% ground-to-sea hydraulic-reference sensitivity
   is what these seven show, and it is not a bound for the corpus.
2. **The rotary-table assumption is still unproven for these wells.** Finding
   10.2's figures assume the AGIP convention applies. If some depths are
   ground-level referenced, their correction is smaller.
   *Revised 2026-09-24:* answered for SALUZZO|1, DESANA|1, ASTI|1 and
   MALOSSA|15. The operator depths are rotary-table referenced, and the workbook
   depths are those values minus the rotary-table height, i.e. below ground.
   TRECATE|9|ST remains unknown.
3. **`quota` is a ground elevation, not a rotary-table elevation.** The
   correction is understated by the derrick height, which no source records.
   *Revised 2026-09-24:* withdrawn. The rotary-table heights are documented
   (3.20, 3.60, 3.00, 9.00 m) and already removed from the workbook depths. The
   remaining open item is the hydraulic reference, not the derrick height.
4. **TRECATE's 160.9 m overshoot is unexplained.** Whether the total depth or
   the temperature depth is wrong cannot be determined from the structured
   sources; resolving it would need the composite log.
5. **The 1.128 ratio confirms internal consistency, not correctness.** It shows
   the Monte Carlo behaves identically across wells; it says nothing about
   whether the underlying capacity is right.

---

## Phase 11 -- Independent hand calculations

Audited 2026-09-20. A second implementation of the entire screening chain,
written from the published equations rather than from the production code, and
compared side by side on four real wells.

### Independence, enforced mechanically

`scratchpad/audit/independent.py` implements Peng-Robinson (including the cubic
solution and the fugacity-based root selection), the Peneloux translation, the
hydrostatic model, pore volume, stored mass, the megatonne conversion, the
exponential integral, Theis drawdown and the rate inversion.

The rule was that it must not reach into production code. That was checked by
parsing its AST rather than by inspection:

| Check | Result |
| --- | --- |
| `ccs_screen` modules loaded after importing it | **none** |
| Every module it imports | **`math`** |
| scipy / numpy used | **no** |

Even the exponential integral is independent -- a Maclaurin series below `u = 1`
and a modified-Lentz continued fraction above it, rather than
`scipy.special.exp1`. Production was imported only *after* every independent
number had been computed and stored.

An earlier version of the guard scanned the source text for the string
`ccs_screen` and fired on the docstring that says the module must not import it.
Replacing the substring test with an AST walk fixed the check rather than the
module.

### Case set

Four real wells from the Phase 10 trace, at their ingested depths and
temperatures, with brine at 1060 kg/m3 and A = 8e7 m2, h = 35 m, phi = 0.225,
E = 0.025:

| Well | Depth (m) | T (K) | P = rho g z (MPa) |
| --- | --- | --- | --- |
| SALUZZO\|1 | 1 527.5 | 318.15 | 15.8784 |
| DESANA\|1 | 3 224.9 | 370.15 | 33.5230 |
| MALOSSA\|15 | 5 491.0 | 416.15 | 57.0792 |
| TRECATE\|9\|ST | 6 087.0 | 452.15 | 63.2747 |

### Side by side

| Quantity | Independent | Production | Relative difference |
| --- | --- | --- | --- |
| Standard gravity | 9.80665 | 9.80665 | 0 |
| Peneloux shift c | 3.1035689e-06 | 3.1035689e-06 | 0 |
| Mt conversion | 1e9 | 1e9 | 0 |
| SALUZZO Z factor | 0.36525144 | 0.36525144 | 0 |
| SALUZZO rho_CO2 | 762.1354 | 762.1354 | 0 |
| SALUZZO capacity | 12.003633 Mt | 12.003633 Mt | 0 |
| DESANA Z factor | 0.68313616 | 0.68313616 | 0 |
| DESANA capacity | 11.627656 Mt | 11.627656 Mt | 1.53e-16 |
| MALOSSA Z factor | 0.95649321 | 0.95649321 | 0 |
| MALOSSA capacity | 12.630798 Mt | 12.630798 Mt | 0 |
| TRECATE Z factor | 1.03624477 | 1.03624477 | 0 |
| TRECATE capacity | 11.856087 Mt | 11.856087 Mt | 0 |
| Theis dP | 6 942 877.9780 Pa | 6 942 877.9780 Pa | 0 |
| Fracture pressure | 30 000 000 Pa | 30 000 000 Pa | 0 |
| Headroom | 11 000 000 Pa | 11 000 000 Pa | 0 |
| Qmax | 0.12674859 m3/s | 0.12674859 m3/s | 0 |

**Worst relative difference across every comparison: 1.640e-16** -- one unit in
the last place of a double.

The independent `E1(u)` agreed with `scipy.special.exp1` to **0.00e+00** at
`u = 2.40631417e-04`, so the well function is confirmed by a third route.

**The implementation is exactly what the published equations say it is.** Phases
1 through 8 verified the pieces; Phase 11 confirms the whole chain reproduces
from scratch, including the non-obvious parts -- the cubic root selection, the
volume translation, and the h-cancellation inside the Theis `u`.

### Finding 11.1 -- a third of the corpus sits outside the validated EOS envelope

**REVIEW REQUIRED. Severity MEDIUM-HIGH. Positive departure from the Span–Wagner reference above 35 MPa. New.**

Agreement between two implementations of the same equation says nothing about
whether that equation is right. The external check does.

Against Span & Wagner (1996) via CoolProp 8.0.0, at each well's own state point:

| Well | P (MPa) | PR + Peneloux | Span-Wagner | Departure from Span–Wagner | Departure, untranslated |
| --- | --- | --- | --- | --- | --- |
| SALUZZO\|1 | 15.88 | 762.135 | 757.939 | **+0.554%** | -4.575% |
| DESANA\|1 | 33.52 | 738.264 | 712.265 | +3.650% | -1.479% |
| MALOSSA\|15 | 57.08 | 801.955 | 746.537 | **+7.423%** | +1.673% |
| TRECATE\|9\|ST | 63.27 | 752.767 | 703.079 | **+7.067%** | +1.670% |

Phase 1 measured the EOS over a grid spanning **1-35 MPa** and recorded a mean
absolute error of 4.06%. Two of these four wells sit at **57 and 63 MPa** --
outside that grid entirely.

Extending the check to the whole corpus, over the 44 wells with both a depth and
a temperature:

| Population | Wells | Pooled mean absolute departure from Span–Wagner |
| --- | --- | --- |
| P <= 35 MPa (inside the Phase 1 envelope) | 29 | **2.63%** |
| P > 35 MPa (outside it) | **15** | **7.29%** |
| All | 44 | 4.22% |

"Inside" here means P <= 35 MPa. For this 44-well corpus it is identical to the
full 1–35 MPa / 280–400 K envelope, because no well exceeds 400 K without also
exceeding 35 MPa. Shift on, ground-referenced pressure at rho = 1060 kg/m3.

**15 of 44 wells -- 34% of the screenable corpus -- lie above the pressure range
the EOS was validated over**, and in that region the departure from the reference
is 2.8x larger and always **positive**. If the reference is accurate there,
capacity is overstated.

Worst cases across the corpus:

| Well | P (MPa) | T (K) | PR | Span-Wagner | Departure from Span–Wagner |
| --- | --- | --- | --- | --- | --- |
| NOVI LIGURE\|2\|BIS DIR | 8.13 | 306.15 | 575.74 | 633.93 | **-9.18%** |
| TRECATE\|4 | 65.20 | 421.15 | 844.27 | 775.94 | **+8.81%** |
| GALLIATE\|1 | 69.58 | 447.65 | 804.90 | 742.52 | +8.40% |
| TRECATE\|1 | 66.78 | 446.15 | 790.64 | 732.33 | +7.96% |
| SALI VERCELLESE\|1 | 60.28 | 421.15 | 811.06 | 752.08 | +7.84% |
| CAVAGLIETTO\|1 | 9.33 | 312.15 | 543.24 | 588.75 | -7.73% |

Two distinct departure regions, with opposite signs:

1. **High pressure (> 35 MPa, 15 wells).** The constant Peneloux shift
   over-corrects. Departures of +4.9% to +8.8%, always positive. This is Phase 1
   Finding 1.1 -- previously demonstrated on a synthetic grid, now shown to
   affect a third of the actual dataset.
2. **Near-critical (8-9 MPa, low temperature).** Departures of -7.7% to -9.2%,
   always negative. This is Phase 1 Finding 1.3, and it too is populated:
   NOVI LIGURE|2|BIS DIR and CAVAGLIETTO|1 are real wells in this corpus.

The untranslated columns make the trade-off concrete: at SALUZZO the shift turns
a -4.58% error into +0.55%, but at MALOSSA it turns +1.67% into +7.42%. Phase 1
concluded the shift is kept "because most Italian pilot reservoirs sit below
20 MPa". **That premise is not supported by the pilot population** -- see the
revision below.

Nothing is changed. Restricting the shift to low pressure, or dropping it, are
both scientific changes to a frozen module. But the justification recorded in
`properties.py` should be revisited, because the population it appeals to is not
the population in the data.

#### Finding 11.1 revision -- premise, envelope coverage and shift behaviour

*Documentation revision. Read-only re-analysis; no equation, parameter, test or
baseline changed.*

This finding merged three separate questions. They are separated here.

**Method.** State points are the pipeline's own: pressure `P = rho*g*z` from the
workbook depth. That is gauge pressure with zero at the depth reference. It is
taken at rho = 1060 kg/m3 unless stated. Temperature is the pipeline's selected
value per well. The reference density is Span & Wagner (1996) via CoolProp
8.0.0: `PropsSI("D", "P", P, "T", T, "CO2")`, default HEOS backend, fluid EOS
`Span-JPCRD-1996`. Pressure is passed in Pa and temperature in K. The departure
is `(rho_PR - rho_SW) / rho_SW`. A positive value means Peng–Robinson is denser
than the reference. "Shift off" is the production translated volume with the
Peneloux constant `c` added back. All 264 bracket state points reproduce
independently to within 1.1e-12 in the departure.

These are **departures from a reference equation of state for pure CO2**. They
are not measured density errors. Pressure, temperature and fluid composition at
these wells are themselves unmeasured or modelled.

**1. The Peneloux justification premise is not supported by the pilot
population.**

`properties.py` keeps the shift "because most Italian pilot reservoirs sit below
20 MPa". The Piemonte pilot population has 46 records, 45 of them with a depth,
spanning 782–6694 m.

| Population | < 15 MPa | 15–20 | 20–35 | > 35 | Below 20 MPa |
| --- | --- | --- | --- | --- | --- |
| Pilot wells with a depth (45) | 6 | 8 | 16 | 15 | **14 / 45** |
| Screening corpus, depth and temperature (44) | 6 | 7 | 16 | 15 | 13 / 44 |

Across the scenario's brine-density range (1020–1100 kg/m3), the pilot count
below 20 MPa is 13–18 of 45. The same holds for the ground/sea-level water-level
brackets and the ±P_atm brackets, which are sensitivity cases only. The
"20 MPa" figure matches only the upper bound of the placeholder pressure range in
`examples/pilot-assumptions.json` (12–20 MPa). That file contains no wells.

**2. The Phase 1 validation envelope does not cover the screening corpus.**

Phase 1 validated the EOS over 1–35 MPa and 280–400 K. Of the 44 corpus wells:

- **15 / 44 exceed 35 MPa.** This is the same 15 wells in every water-level and
  ±P_atm bracket at rho = 1060, and 13–17 across the 1020–1100 kg/m3 range.
- **13 / 44 exceed 400 K**, up to 455.15 K. Every one of these 13 also exceeds
  35 MPa.
- 2 wells exceed 35 MPa at or below 400 K: SOMMARIVA DEL BOSCO|1 and
  ROMENTINO|1.
- None is below 280 K.
- Two of the out-of-envelope temperatures are non-stabilised readings
  (VILLA FORTUNA|3, SALI VERCELLESE|1). The rest are extrapolated
  (Fertl–Wichmann or Squarci–Taffi).

The temperature exceedance is new here: the Phase 1 grid stops at 400 K.

**3. Peneloux shift behaviour against the reference.**

Pooled mean absolute departure, ground-referenced pressure at rho = 1060. The
range in brackets is the signed departure.

| Band | n | Shift on | Shift off |
| --- | --- | --- | --- |
| < 15 MPa | 6 | 4.05% (-9.18 to -0.76) | 7.77% |
| 15–20 MPa | 7 | 1.99% | 3.37% |
| 20–35 MPa | 16 | 2.38% | 2.71% |
| > 35 MPa | 15 | 7.29% (+4.87 to +8.81) | 1.78% |
| > 400 K | 13 | 7.65% | 1.98% |

- Below 20 MPa the shift **reduces the mean departure** in every bracket tested.
  Individual near-critical points still depart by up to -9.18%.
- Above 35 MPa, and above 400 K, the shift produces **positive departures in
  every bracket: +3.8% to +8.8%**. With the shift off, departures in that band
  are -1.25% to +2.71%.
- The sign and the band counts do not depend on the water-level or P_atm
  convention.

**Reference uncertainty.** Span & Wagner (1996, J. Phys. Chem. Ref. Data 25,
1509) state a validity range from the triple point to 1100 K at pressures up to
800 MPa. Every project state point (about 6–70 MPa, 306–455 K) lies within it.
The published abstract gives an estimated density uncertainty of ±0.03% to
±0.05% **only up to 30 MPa and 523 K**. For the project's state points above
30 MPa, including all 15 above 35 MPa, the reference uncertainty **was not
independently verified** from the accessible primary text. The same applies to
the near-critical points (about 6–10 MPa, 306–312 K). The departures below
30 MPa are therefore quantitatively supported. The positive departures above
35 MPa are supported qualitatively: the reference is valid there, but its
uncertainty is not quantified here.

**Not decided here:** whether the Peneloux shift should be kept, restricted or
replaced, and what operating envelope the tool should enforce. Both are owner
decisions.

### Finding 11.2 -- the EOS bias and the hydraulic-reference sensitivity vary in opposite ways with depth

**PASS WITH CAVEAT. Severity LOW. Interpretation.**

*Revised 2026-09-24.* As originally written (title: "the EOS bias and the datum
bias are complementary"), this finding treated Finding 10.2 as a datum bias that
overstates capacity, and summed it with Finding 11.1. Finding 10.2 is now a
hydraulic-reference sensitivity whose direction is not established (*Finding 4.2
/ 10.2 revision*). The "Combined" column below therefore holds **only if the
water level is at sea level**. The numbers are retained unchanged as that
conditional case.

Finding 11.1 (EOS) overstates capacity; that direction is established. The 10.2
sensitivity and the 11.1 bias are largest at opposite ends of the depth range:

| Well | Depth (m) | 10.2 sensitivity, ground to sea level | EOS bias (11.1) | Combined (conditional) |
| --- | --- | --- | --- | --- |
| SALUZZO\|1 | 1 527.5 | **+15.59%** | +0.55% | ~+16.2% |
| ASTI\|1 | 1 247.0 | +10.87% | (near-critical region) | - |
| DESANA\|1 | 3 224.9 | +2.74% | +3.65% | ~+6.5% |
| MALOSSA\|15 | 5 491.0 | +1.10% | **+7.42%** | ~+8.6% |
| TRECATE\|9\|ST | 6 087.0 | +1.37% | **+7.07%** | ~+8.5% |

The 10.2 sensitivity is an absolute elevation offset against a growing column,
so it shrinks with depth; the EOS bias grows with pressure. If the water level
were at sea level, the sum would be an overstatement of roughly **6% to 16%
across the depth range**. Without that condition the 10.2 term has no
established sign, and no combined range is stated.

This is a conditional scenario, not an estimate of the tool's bias and not a
correction. It does not include Finding 3.1, which runs the other way at
1.33x-4x and is far larger than both.

### Findings table

| Item | Status | Severity | Evidence | Action |
| --- | --- | --- | --- | --- |
| Independence of the second implementation | PASS | - | AST walk: imports `math` only; no `ccs_screen` module loaded | None |
| Hydrostatic pressure | PASS | - | Exact, 4/4 wells | None |
| Peng-Robinson Z factor | PASS | - | Exact to 8 significant figures, 4/4 | None |
| Peneloux shift | PASS | - | Exact | None |
| CO2 density | PASS | - | Exact, 4/4 | None |
| Pore volume, mass, Mt | PASS | - | Worst relative difference 1.64e-16 | None |
| Exponential integral | PASS | - | Own series/continued fraction matches scipy to 0.00e+00 | None |
| Theis dP, fracture pressure, headroom, Qmax | PASS | - | Exact, all four | None |
| **Screening corpus outside the Phase 1 EOS envelope** | **REVIEW REQUIRED** | **MEDIUM-HIGH** | 15/44 wells outside (all P > 35 MPa; 13 of them also T > 400 K). Pooled mean absolute departure from Span–Wagner, shift on, ground-referenced P at rho = 1060: 7.29% for these 15 vs 2.63% for the 29 wells inside (1–35 MPa, 280–400 K). Pilot premise: 14/45 below 20 MPa | Documented |
| EOS bias plus hydraulic-reference sensitivity (original label "EOS and datum biases compound", superseded) | PASS WITH CAVEAT | LOW | ~+6% to +16% only if the water level is at sea level; 10.2 direction not established | Documented |

### Scientific numbers changed?

**NO.** No file under `src/` was modified in Phase 11.

### Downstream impact

The implementation is vindicated: **every production number reproduces exactly
from an independent implementation of the published equations.** No arithmetic
defect exists anywhere in the chain from depth to megatonnes. That is the
strongest possible result for Phases 2, 3, 4, 5 and 8, and it closes the
question of whether the code computes what it claims.

What Phase 11 adds is the other half of the question. The code is right about
the equation; the equation is 2.63% from a reference EOS where it was validated
and **7.29% where a third of the wells actually are**.

Phase 12 inherits:

- **Finding 11.1**, which should be weighed against Phase 1's REVIEW REQUIRED on
  the Peneloux shift. Phase 1 left the shift in place on a premise about the
  well population. The pilot population does not support that premise (14/45
  below 20 MPa), and the corpus exceeds the validated envelope in both pressure
  and temperature.
- **Finding 11.2**, now a conditional sum that holds only if the water level is
  at sea level (see its revision note). What carries forward unconditionally is
  Finding 11.1's departure from the Span–Wagner reference, which, with the
  Phase 7 Finding 7.2 point, lies outside the reported uncertainty band.

### Remaining uncertainty

1. **CoolProp is an implementation of Span & Wagner, not the correlation
   itself.** It is the standard reference implementation. It cites
   `Span-JPCRD-1996` for CO2, and its implementation was not compared here
   against the paper's own test values. The published density uncertainty
   (±0.03–0.05%) covers only p <= 30 MPa and T <= 523 K. Above 30 MPa it was not
   verified from the accessible primary text.
2. **The corpus comparison uses a single brine density (1060 kg/m3)** to set
   each well's pressure. Across the scenario's declared 1020–1100 range, the
   number of wells above 35 MPa is 13–17 of 44 (15 at 1060). Individual
   departures shift by a few tenths of a percent.
3. **Temperature enters the comparison as the selected observation**, so any
   Phase 6 or Phase 10 temperature finding propagates into the Span-Wagner
   reference point as well as into the PR value. The *difference* between them
   is much less sensitive to this than either absolute value.
4. **Four wells were hand-traced, not forty-four.** The exact-agreement result
   is from four; the error statistics are from 44.
5. **CO2 purity is assumed throughout.** Both implementations model pure CO2,
   so agreeing with each other and with Span-Wagner says nothing about a stream
   containing N2, O2 or CH4.

---

## Phase 12 -- Final scientific consistency review

Audited 2026-09-20. Cross-model consistency, and the combined net effect the
baseline freeze was declared in order to measure.

Phases 1-11 audited each subsystem on its own terms. Phase 12 asks the question
none of them could: **when these models are used together, do they agree with
each other, and what is the net direction of everything found?**

### Finding 12.1 -- the capacity model and the injectivity model contradict each other

**REVIEW REQUIRED. Severity HIGH. Anti-conservative.**

Capacity is computed for a **bounded structural closure** of area `area_m2`.
Injectivity is computed with the **Theis infinite-acting** solution, which
assumes an aquifer of unlimited lateral extent. In a single CLI run, both
assumptions are applied to the same reservoir.

Phase 5 recorded this as a qualitative conflict. It can be quantified. The
radius of investigation for radial flow is `r_inv = sqrt(2.25 T t / S)`; at the
shipped aquifer defaults, `T = 7.111e-09 m3/(Pa s)` and `S = 8.640e-09 m/Pa`:

| Closure area | Equivalent radius | Front reaches the boundary at | r_inv at 10 yr |
| --- | --- | --- | --- |
| 20 km2 | 2 523 m | **39.8 days** | 24 174 m (**9.6x** the closure) |
| 80 km2 | 5 046 m | **159 days** | 24 174 m (**4.8x** the closure) |
| 200 km2 | 7 979 m | **398 days** | 24 174 m (**3.0x** the closure) |

The default injection duration is **10 years**. The front leaves a 20 km2
closure in under six weeks and an 80 km2 closure in about five months; even a
200 km2 closure is exceeded after 398 days. In every case the assumption fails
within the first 4% of the modelled injection period, and the simulation ends
three to ten times beyond the trap.

So the infinite-acting assumption is violated for essentially the entire
modelled injection period. A no-flow boundary makes pressure rise **faster**
than Theis predicts, so the model **understates dP** and therefore
**overstates the permitted rate**.

This compounds with two Phase 5 findings that run the same way: the far-field
evaluation radius (3.20x) and the inconsistent depth/pressure defaults (1.72x).
The rate ceiling is overstated by at least 5.5x from those two alone, before any
boundary effect.

It remains CLI-only, so no API or frontend number is affected.

### Finding 12.2 -- three thicknesses, no check between any pair

**REVIEW REQUIRED. Severity LOW.**

| Well | Gross stratigraphic | Capacity `thickness_m` | Theis `aquifer_thickness_m` |
| --- | --- | --- | --- |
| SALUZZO\|1 | 1 104.7 m | 35.0 m | 40.0 m |
| DESANA\|1 | 1 098.5 m | 35.0 m | 40.0 m |
| ASTI\|1 | 880.0 m | 35.0 m | 40.0 m |
| TRECATE\|9\|ST | 619.0 m | 35.0 m | 40.0 m |
| MALOSSA\|15 | 355.0 m | 35.0 m | 40.0 m |

`ThicknessKind` names all three kinds and the ingestion layer keeps them apart
correctly -- that was verified in Phases 3 and 10. What does not exist is any
**relational** check. The hydraulic thickness may legitimately exceed the net
storage thickness, and here it does by 14%, but nothing computes that ratio,
reports it, or objects if a user sets the Theis thickness *below* the storage
thickness, which would be physically impossible.

The same applies to `porosity` (0.10-0.35, from literature) and
`aquifer_porosity` (0.18, a CLI default): two independent values for the same
rock, never compared.

### Finding 12.3 -- temperature and pressure at different depths costs less than 1.6%

**PASS WITH CAVEAT. Severity LOW. Discharges a Phase 6 concern.**

Phase 6 Finding 6.5 raised that the selected temperature and the modelled
pressure may describe different depths. Phase 10 found the gaps. Phase 12
measures what they cost:

| Well | P depth (TD) | T depth | Gap | Implied T error | Capacity error |
| --- | --- | --- | --- | --- | --- |
| SALUZZO\|1 | 1 527.5 | 1 522.6 | -4.9 m | -0.15 K | -0.18% |
| ASTI\|1 | 1 247.0 | 1 244.0 | -3.0 m | -0.09 K | -0.17% |
| DESANA\|1 | 3 224.9 | 3 200.4 | -24.5 m | -0.73 K | -0.45% |
| MALOSSA\|15 | 5 491.0 | 5 387.0 | -104.0 m | -3.12 K | -1.12% |
| **TRECATE\|9\|ST** | 6 087.0 | 6 247.9 | **+160.9 m** | +4.83 K | **+1.53%** |

At 30 K/km the worst case is **1.53%**, and four of five are below 0.5%. The
concern was legitimate and the measurement retires it: this is the smallest
effect in the entire audit. Finding 10.1 (the observation below total depth)
remains a data-quality defect worth fixing, but it is not a numerical problem.

### Finding 12.4 -- the combined net effect

**This is the result the baseline freeze existed to produce.**

Convention: **factor = true / reported**. A factor above 1 means the tool
**understates** capacity.

*Revised 2026-09-24.* The 4.2 row (original label "4.2 depth datum", direction
"overstates") is the ground-to-sea hydraulic-reference sensitivity from Finding
10.2. It is not a measured bias, and its direction is not established (*Finding
4.2 / 10.2 revision*). Every product below that includes it is therefore
**conditional on a sea-level water level**: the Combined row, the [1.15, 3.76]
interval and the "Excluding Finding 3.1" factors. The numbers are retained
unchanged as that conditional calculation.

| Finding | SALUZZO\|1 | DESANA\|1 | MALOSSA\|15 | TRECATE\|9\|ST | Direction |
| --- | --- | --- | --- | --- | --- |
| 3.1 net-to-gross double count | x1.33-4.00 | x1.33-4.00 | x1.33-4.00 | x1.33-4.00 | understates |
| 4.1 gauge -> absolute | x1.0032 | x1.0018 | x1.0009 | x1.0009 | understates |
| 4.2 hydraulic reference, if water level at sea level | x0.8651 | x0.9733 | x0.9891 | x0.9865 | not established |
| 11.1 EOS vs Span-Wagner | x0.9945 | x0.9648 | x0.9309 | x0.9340 | overstates |
| **Combined (conditional)** | **x1.15-3.45** | **x1.25-3.76** | **x1.23-3.69** | **x1.23-3.69** | **understates** |

**Conditional on a sea-level water level: true / reported lies in [1.15, 3.76].**

Under that condition the reported capacity is **understated** -- by at least
15%, and plausibly by a factor of nearly four. The direction does not depend on
the condition: Finding 3.1 alone (x1.33-4.00) understates capacity and is larger
than every other row. That is the opposite of what the individual HIGH-severity
findings suggested in isolation.

**Excluding Finding 3.1**, the remaining rows give (conditional on a sea-level
water level):

| Well | Factor without 3.1 (conditional) |
| --- | --- |
| SALUZZO\|1 | x0.8632 |
| DESANA\|1 | x0.9407 |
| MALOSSA\|15 | x0.9216 |
| TRECATE\|9\|ST | x0.9222 |

i.e., if the water level is at sea level, capacity **overstated by 6% to 16%**
-- which reproduces the conditional Finding 11.2 sum independently, from a
different construction. Without that condition the 4.2 term has no established
sign, and no range is stated here.

So the decision structure is simple and sharp:

- **Finding 3.1 is the only finding that matters at first order.** Every other
  row is smaller. The rows with an established direction (4.1, 11.1) are small
  beside it, and 4.2 is a sensitivity of unestablished direction (up to +15.59%
  on capacity in Finding 10.2).
- Finding 3.1 was confirmed in Phase 9 **from both primary sources**: CSLF's
  storage-efficiency factor demonstrably contains a net-to-gross term of
  0.25-0.75, and the API demands net thickness before applying it.
- Among the remaining rows with an established direction, the overstatement
  (11.1) dominates the understatement (4.1). 4.2 is left out of that comparison
  because its direction is not established.

### Finding 12.5 -- the systematic bias is wider than the uncertainty band

**REVIEW REQUIRED. Severity HIGH. The most important interpretive finding in the audit.**

For a SALUZZO-like configuration the reported band is
`P10 = 5.264, P50 = 10.915, P90 = 20.742 Mt`, i.e. a multiplicative range of
**x0.482 to x1.900** around P50.

The combined systematic bias for the same well was stated as **x1.15 to
x3.45**. *Revised 2026-09-24:* that range includes Finding 4.2 as a directional
bias, so it is **conditional on a sea-level water level** (Finding 12.4
revision note). It is retained below as that conditional case.

| | Lower | Upper | Span |
| --- | --- | --- | --- |
| Reported uncertainty band (P10-P90) | x0.482 | x1.900 | 3.9x |
| Combined systematic bias (conditional on sea-level water level) | x1.15 | x3.45 | 3.0x |

**The bias upper bound (3.45) lies far above the band upper bound (1.90).** The
conclusion does not depend on Finding 4.2: Finding 3.1 alone reaches x4.00
(Finding 12.4 table), also above 1.90. The true value can sit entirely outside
the reported P10-P90 interval -- above P90, not merely near its edge.

This is Phase 7 Finding 7.2 in its sharpest form. The band is computed from two
literature ranges (Phase 7 Finding 7.1 showed pressure contributes 0% and area,
thickness and temperature contribute nothing at all), while every systematic
finding in this audit sits outside it. Reporting P10-P90 without that caveat
invites a reader to treat an 80% interval as covering the answer when it
provably may not.

### Consistency review across the remaining axes

| Axis | Verdict | Evidence |
| --- | --- | --- |
| temperature -> density | **consistent** | One consumer, one conversion, verified exactly in Phase 11 |
| density -> capacity | **consistent** | Linear, elasticity +1, reproduced to 1.6e-16 |
| pressure -> injectivity | **inconsistent** | Finding 12.1; plus gauge/absolute (4.1) reaching the fracture comparison |
| thickness across models | **unchecked** | Finding 12.2 |
| T and P depths | consistent enough | Finding 12.3, < 1.6% |
| uncertainty propagation | **inconsistent** | Finding 12.5: bias exceeds band |
| provenance | **asymmetric** | Phase 9 Finding 9.8: 2 of ~20 constants cited |
| literature scope | **disclosed, not resolved** | Basin-scale E at closure scale; warning present and accurate |
| P10/P50/P90 semantics | **partially disclosed** | Correct internally; API payload omits the convention (7.5) |

### Scientific numbers changed?

**NO.** No file under `src/` was modified in Phase 12.

---

# Final audit summary

## Verdict

**The implementation is correct. The model is not always right, and the two are
different questions.**

Phase 11 reproduced every production number -- pressure, compressibility, CO2
density, pore volume, stored mass, megatonnes, Theis drawdown, fracture
pressure, headroom and rate ceiling -- from an independent implementation
written from the published equations, importing nothing but `math`. The worst
relative difference across every comparison was **1.64e-16**, one unit in the
last place of a double.

**No arithmetic defect was found anywhere in the codebase.** Not one.

What the audit did find is a set of **scientific and semantic** issues: an
efficiency factor applied against the wrong thickness convention, an unstated
hydraulic (water-level) reference behind the hydrostatic pressure -- the depth
datum itself is documented for four wells and unresolved for TRECATE|9|ST --
an equation of state used a third of the time outside the
range it was validated over, a gauge pressure supplied where an absolute one is
required, and an uncertainty band narrower than the biases it omits.

## Did the model deserve to pass?

The brief was: *"Do not try to make the model pass the audit. Try to find out
whether the model deserves to pass the audit."*

**On engineering: yes, emphatically.** The provenance machinery, the four-label
partition, the refusal to infer area or net thickness, the temperature
non-assumability rule, the conflict records that name the exact rejected source
row, and the blocked-with-reasons contract are all better than the scientific
content they carry. Several times the audit set out to find a defect and instead
confirmed a deliberate, documented decision -- the scale-mismatch warning proved
accurate against both primary sources, and the recorded Donda 1%/4% discrepancy
proved not only real but resolvable in the project's favour from the paper's own
table arithmetic.

**On science: with material qualifications.** Finding 3.1 alone biases the
headline number low by a factor of 1.33 to 4.00. The combined factor with the
other findings is conditional on the unresolved water level (Finding 12.4). The
reported uncertainty band does not contain that bias.

## The finding that matters

Of the 20 open findings, **one dominates**: Finding 3.1. The CSLF storage
efficiency factor contains a net-to-gross term of 0.25-0.75 -- confirmed in
Phase 9 from CSLF-T-2008-04 itself -- and the API requires **net** thickness
before applying it, so the reduction lands twice. Everything else in this audit
is smaller. The one term without an established direction is Finding 4.2's
hydraulic-reference sensitivity (up to +15.59% on capacity in Finding 10.2).

The regional precedent the project follows, Donda et al. (2011), does the same
thing and explicitly: it defines `h` as "average thickness of aquifer x average
net to gross ratio" and applies the USDOE factor on top. Its own description of
that factor omits the thickness term, which suggests the authors did not know it
was there.

## Findings register

Severity counts across all twelve phases:

| Severity | Count |
| --- | --- |
| HIGH | 5 |
| MEDIUM / MEDIUM-HIGH | 11 |
| LOW | 4 |

The five HIGH findings:

| # | Finding | Effect | Scope |
| --- | --- | --- | --- |
| 4.2 | Hydraulic reference (water level) unestablished; depth datum supported for 4 wells | Capacity sensitivity +1.1% to +15.6% (ground vs sea-level water level); direction unestablished | API + frontend |
| 5.1 | Far-field dP vs near-well fracture limit | Rate ceiling 3.20x | CLI only |
| 5.2 | Depth and initial pressure inconsistent | Headroom 1.72x | CLI only |
| 12.1 | Closed trap vs infinite aquifer | Rate ceiling, unbounded | CLI only |
| 12.5 | Systematic bias exceeds the uncertainty band | Interpretive | API + frontend |

Only two of the five reach the public product. Injectivity is CLI-only, which
contains three of them.

## Recommended order of work

1. **Resolve Finding 3.1.** Nothing else changes the answer at first order.
   Either supply gross thickness and keep E as published, or divide E by an
   explicit, documented net-to-gross. Both are scientific decisions.
2. **Disclose Finding 12.5.** One sentence in the API payload stating that the
   band covers two literature ranges and excludes systematic bias. Costs
   nothing, prevents the most likely misreading.
3. **Establish the hydraulic reference (Finding 4.2 / 10.2).** The depth
   datum is now supported for four wells: the workbook depths are below ground.
   Subtracting `quota` would not remove a datum error. It would move the assumed
   water level from ground to sea level, and no evidence supports either. Obtain
   a stabilised static formation pressure or static water level from a
   water-bearing interval, per well, with depth datum, pressure datum,
   gauge/absolute status and fluid identified (*Finding 4.2 / 10.2 revision*,
   item 5). Only then consider a numerical change.
4. **Revisit the Peneloux justification (Finding 11.1).** `properties.py` keeps
   the shift because "most Italian pilot reservoirs sit below 20 MPa"; only 14
   of 45 pilot wells are. The screening corpus also exceeds the Phase 1
   validation envelope: 15/44 wells are above 35 MPa and 13/44 above 400 K.
   There the shift departs from Span–Wagner by +3.8% to +8.8%. The operating
   envelope and the treatment of the shift are owner decisions.
5. **Add `P_atm` (Finding 4.1).** One constant, one call site. Small, but the
   cited methodology (Donda: "pressure at surface of 15 degC and 1 atm") uses
   absolute pressure, so this is a divergence from the project's own source.

Findings 5.1, 5.2 and 12.1 are severe but CLI-only, and should be fixed together
since all three concern the same composition.

## What this audit verified, and what it could not

**Verified:**

- Every equation reproduces from an independent implementation (1.6e-16).
- The well function matches published tables and two independent computations.
- Both cited primary sources were obtained, read, and their quotes confirmed
  verbatim.
- All seven named wells trace end to end; five produce a capacity, two block
  correctly.
- 986 tests pass, of which 342 were added by this audit across 11 new files.

**Not verified:**

- Any hydraulic head. Measured formation-test and wellhead pressures exist in
  the DESANA|1 and ASTI|1 composite logs, but none is a stabilised pressure or
  static water level from a water-bearing interval, so no hydraulic reference
  was established (*Finding 4.2 / 10.2 revision*). The structured sources
  contain no pressure at all.
- Any stabilised bottom-hole temperature. Zero of 452 records.
- Any net-to-gross ratio, permeability, or area for any well.
- Whether the aquifers are laterally open or compartmentalised.
- CO2 purity effects. Both implementations model pure CO2.

**Structurally unverifiable with this data:** a site-specific capacity. The two
largest multipliers in the equation have no source and no literature range, and
the audit confirmed the project is right to demand them from the caller rather
than invent them.

## Baseline

`src/` is unchanged from the start of Phase 1 except for the three
disclosure-only edits recorded under **Baseline freeze**, none of which altered a
scientific number. Every frozen finding is pinned by a characterisation test
naming it and stating what that test must assert once the finding is resolved.
