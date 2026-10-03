"""Phase 1 audit regression tests for the CO2 equation of state.

These lock in what the Phase 1 scientific audit measured. They are not a second
copy of ``test_properties.py``: that file checks phase behaviour and loose
per-point tolerances, this one pins the *accuracy envelope* so a change to the
EOS or to the volume translation cannot silently move it.

Reference densities are Span & Wagner (1996) via CoolProp 8.0.0 (HEOS backend),
recorded here so the suite needs no extra dependency. See
``docs/scientific-validation-audit.md``, Phase 1.

If a bound below is ever loosened, the audit document must be updated in the
same change and say why.
"""

from __future__ import annotations

import math

import pytest

from ccs_screen.properties import (
    CO2_MW_KG_MOL,
    CO2_OMEGA,
    CO2_PC_PA,
    CO2_TC_K,
    co2_density_kg_m3,
    peneloux_shift_m3_mol,
)

#: (pressure_pa, temperature_k, span_wagner_kg_m3), CoolProp-verified.
BENCHMARK = [
    (1e6, 290, 19.35), (1e6, 300, 18.58), (1e6, 320, 17.23),
    (1e6, 333.15, 16.46), (1e6, 350, 15.58), (1e6, 400, 13.48),
    (4e6, 290, 100.47), (4e6, 300, 91.96), (4e6, 320, 80.31),
    (4e6, 333.15, 74.73), (4e6, 350, 68.98), (4e6, 400, 57.09),
    (1e7, 290, 878.06), (1e7, 300, 801.62), (1e7, 320, 448.28),
    (1e7, 333.15, 289.95), (1e7, 350, 228.80), (1e7, 400, 161.53),
    (1.5e7, 290, 920.40), (1.5e7, 300, 865.82), (1.5e7, 320, 726.83),
    (1.5e7, 333.15, 604.09), (1.5e7, 350, 449.20), (1.5e7, 400, 267.42),
    (2e7, 290, 950.97), (2e7, 300, 905.57), (2e7, 320, 802.33),
    (2e7, 333.15, 723.68), (2e7, 350, 614.18), (2e7, 400, 380.50),
    (3e7, 290, 996.01), (3e7, 300, 959.70), (3e7, 320, 883.00),
    (3e7, 333.15, 829.71), (3e7, 350, 758.98), (3e7, 400, 561.50),
    (3.5e7, 290, 1013.92), (3.5e7, 300, 980.32), (3.5e7, 320, 910.53),
    (3.5e7, 333.15, 862.94), (3.5e7, 350, 800.68), (3.5e7, 400, 623.24),
]


def percent_error(pressure_pa: float, temperature_k: float, reference: float) -> float:
    return 100.0 * (co2_density_kg_m3(pressure_pa, temperature_k) - reference) / reference


# -- measured envelope -------------------------------------------------------


def test_worst_case_error_over_the_benchmark_grid():
    """Audit measured 13.98% worst case over 140 points (near-critical).

    This 42-point subset excludes the critical point, so the bound is tighter.
    A regression that pushed any point past 14% would be a real change in EOS
    behaviour, not noise.
    """
    errors = [abs(percent_error(p, t, r)) for p, t, r in BENCHMARK]
    assert max(errors) < 14.0, f"worst error {max(errors):.2f}% exceeds the audited envelope"


def test_typical_error_matches_the_audit():
    """Mean absolute error was 4.06% over the full 140-point grid."""
    errors = [abs(percent_error(p, t, r)) for p, t, r in BENCHMARK]
    mean = sum(errors) / len(errors)
    assert 2.0 < mean < 7.0, f"mean |error| {mean:.2f}% is outside the audited range"


@pytest.mark.parametrize(
    "pressure_pa,temperature_k,reference",
    [(p, t, r) for p, t, r in BENCHMARK if p <= 1.5e7 and 300 <= t <= 360],
)
def test_italian_pilot_window_within_ten_percent(pressure_pa, temperature_k, reference):
    """Below ~15 MPa: the stated reason for keeping the shift is that pilot
    reservoirs sit here, a premise Finding 11.1 does not support.

    The volume translation helps here, which is the stated reason for keeping
    it despite degrading the high-pressure regime.
    """
    assert abs(percent_error(pressure_pa, temperature_k, reference)) < 10.0


def test_high_pressure_bias_is_positive_and_documented():
    """Above 20 MPa the constant Peneloux shift over-corrects.

    Finding 1.1: the shift turns a +3.8% error into +11.8% at 35 MPa / 300 K.
    This test documents the direction of the bias so it cannot flip unnoticed.
    """
    high = [(p, t, r) for p, t, r in BENCHMARK if p >= 3e7 and t <= 333.15]
    errors = [percent_error(p, t, r) for p, t, r in high]
    assert all(e > 0 for e in errors), f"expected positive bias above 30 MPa, got {errors}"
    assert max(errors) < 14.0


# -- near-critical limitation ------------------------------------------------


def test_near_critical_error_is_large_and_known():
    """Finding 1.3: -14.5% at the critical point. Intrinsic to cubic EOS.

    Asserted so the limitation stays visible, not because it is acceptable
    everywhere: a reservoir near 304 K / 7.4 MPa should not be screened with
    this EOS.
    """
    error = percent_error(7.3773e6, 304.1282, 481.0)
    assert -20.0 < error < -5.0, f"near-critical error {error:.1f}% moved unexpectedly"


# -- phase selection ---------------------------------------------------------


@pytest.mark.parametrize(
    "temperature_k,psat_pa,rho_vapour,rho_liquid",
    [
        (260.0, 2.419e6, 64.4, 998.9),
        (270.0, 3.203e6, 88.4, 945.8),
        (280.0, 4.161e6, 121.7, 883.6),
        (290.0, 5.318e6, 172.0, 804.7),
        (300.0, 6.713e6, 268.6, 679.2),
    ],
)
def test_correct_root_on_each_side_of_saturation(
    temperature_k, psat_pa, rho_vapour, rho_liquid
):
    """The fugacity criterion must pick vapour below Psat and liquid above.

    Picking the dense root unconditionally was an 18x error; this is the
    regression guard for it. Audit result: 7 of 7 crossings correct.
    """
    vapour = co2_density_kg_m3(psat_pa * 0.97, temperature_k)
    liquid = co2_density_kg_m3(psat_pa * 1.03, temperature_k)
    assert vapour < liquid, "phase order inverted across saturation"
    assert vapour < rho_liquid * 0.5, f"liquid root selected on the vapour side ({vapour:.1f})"
    assert liquid > rho_vapour * 2.0, f"vapour root selected on the liquid side ({liquid:.1f})"


# -- constants ---------------------------------------------------------------


def test_critical_constants_match_span_wagner():
    """Finding 1.4: all deviations shift density by less than 0.04%."""
    assert CO2_TC_K == pytest.approx(304.1282, abs=1e-4)
    assert CO2_PC_PA == pytest.approx(7_377_298.37, rel=1e-4)
    assert CO2_MW_KG_MOL == pytest.approx(0.0440098, rel=1e-4)
    # Tabulated (Poling et al.) rather than the Span-Wagner 0.22394; the
    # difference is worth +0.039% on density.
    assert CO2_OMEGA == pytest.approx(0.22394, rel=0.01)


def test_peneloux_shift_value():
    """c = 0.40768 (R Tc / Pc)(0.29441 - Z_RA), Peneloux et al. 1982."""
    shift = peneloux_shift_m3_mol()
    assert shift == pytest.approx(3.1036e-6, rel=1e-3)
    # Must be small against the covolume b (~2.67e-5), or translation would
    # dominate the molar volume.
    b = 0.07780 * 8.314462618 * CO2_TC_K / CO2_PC_PA
    assert 0 < shift < 0.2 * b


def test_density_is_finite_and_positive_across_the_grid():
    for pressure_pa, temperature_k, _ in BENCHMARK:
        rho = co2_density_kg_m3(pressure_pa, temperature_k)
        assert math.isfinite(rho) and rho > 0


def test_error_over_the_whole_validated_envelope_against_span_wagner():
    """Live comparison with CoolProp (Span & Wagner 1996) on a 35 x 25 grid
    covering the approved validated envelope, 1-35 MPa x 280-400 K.

    Recorded with CoolProp 8.0.0 (docs/validation-evidence.md): mean |error|
    3.80%, median 2.54%, 95th percentile 11.23%, max 13.58% at 35 MPa / 280 K.
    These bound the EOS component only, inside the envelope; they say nothing
    about the accuracy of a storage estimate. Runs in the CI reference-checks
    job with CCS_REQUIRE_REFERENCE_TESTS=1, so it cannot be skipped there.
    """
    from conftest import coolprop_propssi

    PropsSI = coolprop_propssi()
    errors = []
    for i in range(35):
        pressure = 1e6 + i * (34e6 / 34)
        for j in range(25):
            temperature = 280.0 + j * 5.0
            reference = PropsSI("D", "P", pressure, "T", temperature, "CO2")
            errors.append(abs(percent_error(pressure, temperature, reference)))
    errors.sort()
    mean = sum(errors) / len(errors)
    assert len(errors) == 875
    assert max(errors) < 14.0, f"max |error| {max(errors):.2f}%"
    assert mean < 4.0, f"mean |error| {mean:.2f}%"
    assert errors[int(0.95 * len(errors))] < 12.0
