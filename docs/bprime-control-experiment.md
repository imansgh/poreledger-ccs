# Candidate B-prime -- control experiment

**Finding 3.1: does removing the net-to-gross component from E have a
defensible basis?**

Run 2026-09-21. Companion to `docs/finding-3.1-literature-review.md` and
`docs/piemonte-ntg-evidence.md`.

**Validation experiment only.** No file under `src/`, no production equation, no
scientific constant, no test encoding scientific behaviour, and no API behaviour
was modified. The analysis script is an audit artifact at
`scratchpad/audit/bprime_experiment.py`; it imports `ccs_screen` only to obtain
the CO2 density and gravity constant, and computes every efficiency term
independently.

---

## Decision

> ### 2. B-prime is mathematically valid but scientifically unresolved -- additional evidence required.

The Step 1 control reproduces the published CSLF result closely enough to
confirm the decomposition. Removing `E_h` is therefore a well-defined operation
on a verified object. But Step 5 shows that **B-prime does not remove an
assumption; it relocates one** -- from a published, cited, distributed parameter
into an undocumented point value implicit in the caller's net thickness. The
experiment cannot establish that the relocation is correct, because the value it
relocates to is not observable through the current API.

**Two numbers in earlier audit documents are corrected below.** Both were
artifacts of dividing distribution endpoints instead of running the Monte Carlo.

---

## Step 1 -- reproducing the published control

The seven CSLF-T-2008-04 components, verbatim, sampled as independent uniforms.
N = 200 000, seed 42.

| Component | Low | High | Mean |
| --- | --- | --- | --- |
| `E_A` fraction of aquifer suitable for storage | 0.20 | 0.80 | 0.500 |
| **`E_h` fraction of unit with required porosity/permeability** | **0.25** | **0.75** | **0.500** |
| `E_phi` fraction of interconnected porosity | 0.60 | 0.95 | 0.775 |
| `E_V1` areal displacement efficiency | 0.50 | 0.80 | 0.650 |
| `E_V2` vertical displacement efficiency | 0.60 | 0.90 | 0.750 |
| `E_V3` fraction of net thickness contacted (buoyancy) | 0.20 | 0.60 | 0.400 |
| `E_d` pore-scale displacement efficiency | 0.50 | 0.80 | 0.650 |

### Result: the control passes

| Statistic | Reconstructed | Published (CSLF) | Difference |
| --- | --- | --- | --- |
| Analytic mean (product of means) | **2.456%** | "average of 2.4% for 50% confidence" | **0.056 pp** |
| P15 | **1.031%** | 1.0% | **+0.031 pp** |
| P85 | **3.966%** | 4.0% | **-0.034 pp** |
| P50 | 2.075% | not published | - |
| Standard deviation | 1.559% | not published | - |
| Skewness | +1.435 | not published | - |

Three independent checks agree: the analytic mean (which requires no simulation
at all, only independence), the P15 and the P85. **This is the same
decomposition that produced the published 1-4% range.**

### The distributional assumption is recovered, not assumed

CSLF states ranges but never states a distribution. Testing the three obvious
candidates:

| Distribution | P15 | P85 | Mean |
| --- | --- | --- | --- |
| **Uniform** | **1.031%** | **3.966%** | 2.455% |
| Triangular | 1.412% | 3.529% | 2.455% |
| PERT / beta(4,4) | 1.592% | 3.335% | 2.456% |

All three share the same mean, because the mean of a product of independent
variables depends only on their means. **Only the uniform reproduces the
published P15 and P85.** The peaked alternatives are far too narrow. This is a
genuine inference: the distribution was not documented, and the reconstruction
recovers it.

### Convergence

| N | P15 | P50 | P85 |
| --- | --- | --- | --- |
| 1 000 | 1.002% | 2.027% | 3.889% |
| 10 000 | 1.032% | 2.069% | 3.986% |
| 50 000 | 1.035% | 2.069% | 3.998% |
| 200 000 | 1.031% | 2.075% | 3.966% |
| 1 000 000 | 1.032% | 2.073% | 3.971% |

Converged by N = 10 000. The values quoted throughout use N = 200 000.

**Step 1 passes. The experiment may proceed.**

---

## Steps 2 and 3 -- removing only `E_h`

`E' = E_A * E_phi * E_V1 * E_V2 * E_V3 * E_d`, with `E_h` fixed at 1.0. No other
component altered. No new NTG value introduced. N = 200 000, seed 42.

| Statistic | `E` (control) | `E'` | Ratio |
| --- | --- | --- | --- |
| P10 | 0.874% | 2.016% | 2.308 |
| P15 | 1.031% | 2.334% | 2.264 |
| **P50** | **2.075%** | **4.347%** | **2.095** |
| P85 | 3.966% | 7.653% | 1.930 |
| P90 | 4.564% | 8.591% | 1.882 |
| Mean | 2.455% | 4.912% | **2.001** |
| Std. deviation | 1.559% | 2.668% | 1.711 |
| Skewness | +1.435 | +1.093 | - |

`E'` spans **2.334% to 7.653%** (P15-P85).

### Correction 1: the naive endpoint division was wrong

`docs/finding-3.1-literature-review.md` proposed Candidate B-prime with
`E' = E / E_h` evaluated at the endpoints, giving **1.33% to 16.0%** and a
capacity ratio of **x3.41**.

That is not what removing `E_h` from the decomposition produces.

| | P15 | P85 | Capacity ratio |
| --- | --- | --- | --- |
| Naive endpoint division (literature review) | 1.333% | 16.000% | x3.41 |
| **Proper Monte Carlo (this experiment)** | **2.334%** | **7.653%** | **x1.93** |
| Error of the naive method | understates by 0.57x | **overstates by 2.09x** | overstates by 1.77x |

The naive division treats the extremes as co-occurring: it pairs the lowest `E`
with the highest `E_h` and vice versa, which the joint distribution makes
vanishingly unlikely. **The literature review's x3.41 is withdrawn. The
measured figure is x1.93 on capacity.**

### Why the mean ratio is exactly 2.000 and the median ratio is not

The mean ratio is **2.0006**, which is `1/mean(E_h) = 1/0.5 = 2.000` to four
significant figures. That is exact by independence: the mean of a product is the
product of the means, so removing a factor divides the mean by that factor's
mean.

The **median** ratio is **2.095**, not 2.000, because medians do not multiply.
This distinction matters: the project reports P50, not the mean, so 2.095 is the
operative number for the efficiency term and 1.93 for capacity (the difference
arising because capacity also multiplies a porosity distribution).

---

## Step 4 -- the four audited wells

N = 50 000, seed 42, A = 8e7 m2, `h_net` = 35 m, porosity 0.10-0.35, brine
1060 kg/m3. Every other input identical to the Phase 10/11 baseline. The
baseline efficiency is the project's adopted `uniform(0.01, 0.04)`; B-prime uses
the reconstructed `E'`.

| Well | Current P50 | B-prime P50 | Ratio | Change |
| --- | ---: | ---: | ---: | ---: |
| SALUZZO\|1 | 10.900 Mt | 21.038 Mt | **1.93** | +93% |
| DESANA\|1 | 10.559 Mt | 20.379 Mt | **1.93** | +93% |
| MALOSSA\|15 | 11.469 Mt | 22.138 Mt | **1.93** | +93% |
| TRECATE\|9\|ST | 10.766 Mt | 20.780 Mt | **1.93** | +93% |

P10 and P90:

| Well | Current P10 | B-prime P10 | Current P90 | B-prime P90 |
| --- | ---: | ---: | ---: | ---: |
| SALUZZO\|1 | 5.234 | 5.960 | 20.570 | **54.340** |
| DESANA\|1 | 5.070 | 5.774 | 19.926 | **52.638** |
| MALOSSA\|15 | 5.507 | 6.272 | 21.645 | **57.179** |
| TRECATE\|9\|ST | 5.169 | 5.887 | 20.318 | **53.672** |

The ratio is **1.93 for every well**, as it must be: the change is a pure
rescaling of the efficiency distribution and is independent of pressure,
temperature and density.

**A side effect that is not a rounding detail.** P90 rises by a factor of about
2.6 while P50 rises by 1.93. The reported band widens substantially in absolute
terms. This happens because the project's adopted `uniform(0.01, 0.04)` is
*narrower and unskewed* compared with the actual CSLF product distribution:

| Distribution | P10/P50 | P90/P50 | Relative span | Skew |
| --- | --- | --- | --- | --- |
| Project's `uniform(0.01, 0.04)` | 0.52 | 1.48 | 0.96 | 0 |
| Reconstructed `E` | 0.42 | 2.20 | 1.78 | +1.44 |
| Reconstructed `E'` | 0.46 | 1.98 | 1.52 | +1.09 |

**This is a pre-existing simplification independent of Finding 3.1.** Adopting
"1-4% uniform" is not the same as adopting CSLF's efficiency distribution: the
real one is right-skewed with a longer upper tail and a lower P10. Whether to
keep the uniform approximation is a separate decision from where NTG belongs,
and it is flagged here only because Step 4 makes it visible.

---

## Step 6 -- stress test against the published NTG range

If the decomposition is implemented correctly, multiplying `E'` by a fixed `E_h`
must recover a predictable ratio.

| `E_h` fixed at | `E'` x `E_h` P50 | Ratio to control P50 | `E'/E` x `E_h` (predicted) |
| --- | --- | --- | --- |
| 0.75 | 3.261% | **1.572** | 2.095 x 0.75 = 1.571 |
| 0.50 | 2.174% | **1.048** | 2.095 x 0.50 = 1.048 |
| 0.25 | 1.087% | **0.524** | 2.095 x 0.25 = 0.524 |

Every row matches its prediction to three decimals. The decomposition behaves
exactly as a product of independent factors should.

### Correction 2: the audit's 1.33x-4.00x bound answers a different question

Phase 9 and the literature review both state that double-counting NTG understates
capacity by **1.33x to 4.00x**, derived as `1/E_h` over the published range.

That derivation treats `E_h` as a **fixed but unknown site value**. It answers:
*"if this site's true net-to-gross were 0.25, and we applied it twice, how far
out would we be?"* Under that reading it is correct, and the measured x2.095
sits inside it.

But it is **not** the size of the correction that removing `E_h` actually makes,
because in the published decomposition `E_h` is **distributed**, not fixed.
Removing a distributed factor from a product of distributions moves the median by
2.095, not by `1/E(E_h) = 2.000` and not by anything in the range 1.33-4.00
selected per site.

**Both numbers are now defined:**

| Question | Answer |
| --- | --- |
| Per-site sensitivity: how wrong could one site be if its NTG were at an extreme? | **1.33x to 4.00x** |
| Actual effect of removing `E_h` from the published decomposition | **x2.095 on E, x1.93 on capacity** |

The second is the operative number for any implementation decision. The first
remains the right way to describe per-site uncertainty.

---

## Step 5 -- is B-prime equivalent to moving NTG from `E` into `h`?

### The algebra

```
DOE       : M = A * h_gross * phi_tot * rho * (E_A E_h E_phi E_V E_d)
B-prime   : M = A * h_net   * phi     * rho * (E_A     E_phi E_V E_d)
```

With `h_net = h_gross * NTG_user`, substituting into B-prime:

```
B-prime   = A * h_gross * NTG_user * phi * rho * (E_A E_phi E_V E_d)
DOE       = A * h_gross            * phi * rho * (E_A E_h E_phi E_V E_d)
```

Dividing:

```
B-prime / DOE = NTG_user / E_h
```

**The two are equal if and only if `NTG_user == E_h`.**

### What that means numerically

`E_h` is not a number; it is `uniform(0.25, 0.75)`. So the question becomes:
what fixed `NTG_user` makes B-prime reproduce DOE at the median?

| `NTG_user` | B-prime / DOE (median) |
| --- | --- |
| 0.250 | 0.524 |
| 0.375 | 0.786 |
| **0.4769** | **1.000** |
| 0.500 | 1.048 |
| 0.625 | 1.310 |
| 0.750 | 1.572 |

**B-prime silently assumes the caller's net thickness implies a net-to-gross of
0.4769.** Not 0.5, and not any value the caller stated -- 0.4769, which is a
property of the median of the remaining six-factor product, not of any
reservoir.

### Therefore: not equivalent, and the difference matters

**B-prime is not "moving NTG from E into h".** Moving a parameter would preserve
it. What B-prime actually does:

| | Before (Candidate A) | After (B-prime) |
| --- | --- | --- |
| Where NTG lives | Inside `E`, as `E_h` | Inside `h_net`, supplied by the caller |
| Is it documented? | **Yes** -- CSLF-T-2008-04, `uniform(0.25, 0.75)` | **No** |
| Is it distributed? | **Yes** | **No** -- a point value implied by one number |
| Can the project observe it? | **Yes**, it is a declared prior | **No** -- the API asks for net thickness and never asks what gross it came from or what cutoff produced it |
| Is it site-specific? | No, it is a North American generic | Yes, in principle -- but unrecorded |
| Applied how many times? | **Twice** (once in `h_net`, once in `E`) | **Once** |

So B-prime fixes a real double-count and creates a real opacity. It trades a
documented, cited, distributed parameter for an undocumented, un-elicited point
value the project cannot inspect, validate, or report.

**This is the finding that blocks a recommendation.** The `docs/piemonte-ntg-evidence.md`
review established that no Piemonte NTG exists in the literature and that our
own data cannot yield one. B-prime does not resolve that; it makes the missing
parameter invisible instead of explicit.

---

## Step 7 -- three separate conclusions

### A. Mathematical result

**Established.** Setting `E_h = 1` in the verified seven-component decomposition
moves the efficiency median from 2.075% to 4.347% (x2.095) and the mean from
2.455% to 4.912% (x2.001, exactly `1/mean(E_h)`). Applied to the four audited
wells, capacity P50 rises by **x1.93** uniformly, and P90 by about x2.6. The
operation is well-defined, reproducible, converged, and behaves correctly under
the Step 6 stress test.

Two earlier figures are corrected: the literature review's **x3.41** was a naive
endpoint-division artifact, and the audit's **1.33x-4.00x** answers a per-site
sensitivity question rather than measuring this correction.

### B. Scientific interpretation

**Not established.** The experiment demonstrates that `E` contains a
net-to-gross component and that removing it is arithmetically sound. It does
**not** demonstrate that removing it is the right thing to do, for three
reasons:

1. **B-prime is only equivalent to the DOE formulation when the caller's implied
   NTG is 0.4769.** For any other value the two disagree, and the project has no
   way to know which applies. The assumption is not removed, only hidden.
2. **`E_V3` is defined as "fraction of **net** aquifer thickness contacted by
   CO2 as a result of CO2 buoyancy".** It is stated relative to net thickness.
   Whether it is already consistent with a net-thickness input, or whether it
   too needs adjustment, is not resolved by any source read in this review. If
   `E_V3` also needs attention, removing `E_h` alone is an incomplete remedy.
3. **The published range is North American.** CSLF states the component ranges
   *"were chosen to reflect various lithologies and geological depositional
   systems that occur in North America"*. Removing `E_h` does not make the
   remaining six terms Italian.

There is also a structural argument the experiment cannot settle: our current
formulation matches the dominant European practice (CO2StoP, EU GeoCapacity,
Wojcicki 2025), and B-prime would move the project away from it toward the
North American convention. That is a choice about which tradition to follow, not
a question this experiment can answer.

### C. Implementation decision

**No.** The evidence does not currently justify changing the production
equation.

Changing it would raise every reported capacity by 93% on the strength of an
implicit NTG of 0.4769 that no caller has stated and the project cannot see.
The most likely consequence is replacing a known, documented conservatism with
an unknown, undocumented one.

**What would change this assessment** is listed below. Note in particular that
two of the four items would also serve Candidate B or C, so the work is not
specific to B-prime.

---

## Evidence still required before implementation

| # | Required | Why | Serves which candidate |
| --- | --- | --- | --- |
| 1 | **Elicit the caller's NTG, or the gross thickness the net came from** | Makes the implicit 0.4769 explicit and inspectable. Without it, B-prime is unauditable by construction | **DESIGNED 2026-09-21**, see `docs/ntg-elicitation-design.md`. Not implemented |
| 2 | ~~Resolve whether `E_V3` is consistent with a net-thickness input~~ | **CLOSED 2026-09-21.** `E_V3` acts on net -> contacted net; `E_h` acts on gross -> net. Sequential, not overlapping. See `docs/ev3-semantics.md` | B-prime |
| 3 | **A Piemonte or Po Plain NTG** | Would let the project compare the caller's implied NTG against something real, and would unblock Candidates B and C | all |
| 4 | **A decision on which tradition to follow** | DOE (NTG inside `E`) vs European (NTG explicit). The two give different answers and both are current practice | all |
| 5 | **A decision on the uniform approximation of `E`** | Separate from Finding 3.1, but Step 4 shows it materially affects the reported band | independent |

Items 1 and 2 are answerable without new geological data. **Item 2 is the
cheapest next step and the one most likely to change the shape of the
question** -- it requires reading Goodman et al. (2011, 2016) or Myshakin et al.
(2022), not field work.

---

## Reproducibility

| Parameter | Value |
| --- | --- |
| Script | `scratchpad/audit/bprime_experiment.py` (audit artifact, not production) |
| Seed | 42 |
| N, control and `E'` | 200 000 (convergence checked to 1 000 000) |
| N, four wells | 50 000 |
| Component ranges | CSLF-T-2008-04, verbatim, seven components |
| Distribution | uniform (recovered in Step 1, not assumed) |
| Well inputs | Phase 10/11 baseline: A = 8e7 m2, `h_net` = 35 m, phi 0.10-0.35, brine 1060 kg/m3 |
| Production code touched | **none** |
| Test suite after the experiment | 1015 passed |
