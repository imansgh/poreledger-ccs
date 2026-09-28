"""Phase 5 audit regression tests for the Theis injectivity model.

The Theis mathematics is exact, so the tests that matter here are the ones about
*composition*: the rate ceiling pairs a far-field pressure rise with a
near-wellbore fracture limit, and the CLI feeds it a depth and an initial
pressure that disagree by 29%. Both are pinned below as characterisation tests.

``well_function_series`` reimplements W(u) from its defining series so the
production path (``scipy.special.exp1``) is checked against something that does
not share its code, and both are checked against published tables.

See ``docs/scientific-validation-audit.md``, Phase 5.
"""

from __future__ import annotations

import inspect
import math

import pytest

from ccs_screen.pressure import (
    allowable_delta_p_pa,
    max_injection_rate_m3_s,
    theis_injection_delta_p_pa,
    theis_transmissivity,
)

EULER_MASCHERONI = 0.5772156649015328606

#: CLI defaults, so the tests measure the configuration that actually ships.
BASE = dict(
    permeability_m2=8e-14,
    thickness_m=40.0,
    viscosity_pa_s=4.5e-4,
    time_s=10 * 365.25 * 24 * 3600,
    radius_m=500.0,
    porosity=0.18,
    compressibility_1_pa=1.2e-9,
)
DEFAULT_RATE_M3_S = 0.08

#: Phase 14 (D1, rule B): no fracture gradient or safety factor is approved and
#: neither has a default. Arbitrary caller-supplied values for the arithmetic.
CALLER_CRITERION = dict(fracture_gradient_pa_m=17_000.0, safety_factor=0.8)

#: Wenzel (1942), reproduced in Freeze & Cherry (1979) Appendix and
#: Kruseman & de Ridder (1990) Annex 3.
PUBLISHED_WELL_FUNCTION = {
    1e-15: 33.9616, 1e-10: 22.4486, 1e-8: 17.8435, 1e-5: 10.9357,
    1e-4: 8.6332, 1e-3: 6.3315, 1e-2: 4.0379, 1e-1: 1.8229,
    1.0: 0.2194, 2.0: 0.0489,
}


def well_function_series(u: float, terms: int = 200) -> float:
    """W(u) from its defining series, independent of scipy."""
    total = 0.0
    factorial_term = 1.0
    for n in range(1, terms + 1):
        factorial_term *= u / n
        total += ((-1) ** (n + 1)) * factorial_term / n
    return -EULER_MASCHERONI - math.log(u) + total


def independent_delta_p_pa(rate, k, h, mu, t, r, phi, ct):
    """Theis from first principles. No production import."""
    transmissivity = k * h / mu
    storativity = phi * ct * h
    u = r * r * storativity / (4 * transmissivity * t)
    return rate / (4 * math.pi * transmissivity) * well_function_series(u)


# -- well function -----------------------------------------------------------


@pytest.mark.parametrize("u,published", sorted(PUBLISHED_WELL_FUNCTION.items()))
def test_well_function_matches_published_tables(u, published):
    """scipy's exp1 IS the Theis well function, checked against printed tables."""
    from scipy.special import exp1

    assert float(exp1(u)) == pytest.approx(published, rel=2e-4)


@pytest.mark.parametrize("u", [1e-8, 1e-5, 1e-3, 1e-2, 1e-1, 1.0, 2.0])
def test_well_function_identity_with_the_defining_series(u):
    """W(u) == E1(u) is verified here, not assumed."""
    from scipy.special import exp1

    assert float(exp1(u)) == pytest.approx(well_function_series(u), rel=1e-12)


def test_well_function_decreases_monotonically():
    from scipy.special import exp1

    values = [float(exp1(u)) for u in (1e-10, 1e-6, 1e-3, 1e-2, 1e-1, 1.0, 5.0)]
    assert values == sorted(values, reverse=True)


# -- full calculation --------------------------------------------------------


def test_matches_independent_implementation_bit_for_bit():
    """Phase 5 measured a relative error of exactly zero here."""
    independent = independent_delta_p_pa(
        DEFAULT_RATE_M3_S, BASE["permeability_m2"], BASE["thickness_m"],
        BASE["viscosity_pa_s"], BASE["time_s"], BASE["radius_m"],
        BASE["porosity"], BASE["compressibility_1_pa"],
    )
    produced = theis_injection_delta_p_pa(rate_m3_s=DEFAULT_RATE_M3_S, **BASE)
    assert produced == pytest.approx(independent, rel=1e-15)
    assert produced / 1e6 == pytest.approx(6.942878, abs=1e-5)


def test_transmissivity_is_kh_over_mu():
    assert theis_transmissivity(8e-14, 40.0, 4.5e-4) == pytest.approx(
        8e-14 * 40.0 / 4.5e-4, rel=1e-15
    )


def test_u_is_in_the_cooper_jacob_validity_window_at_defaults():
    """u < 0.01 is where the logarithmic approximation regime holds."""
    transmissivity = BASE["permeability_m2"] * BASE["thickness_m"] / BASE["viscosity_pa_s"]
    storativity = BASE["porosity"] * BASE["compressibility_1_pa"] * BASE["thickness_m"]
    u = BASE["radius_m"] ** 2 * storativity / (4 * transmissivity * BASE["time_s"])
    assert u == pytest.approx(2.406314e-04, rel=1e-5)
    assert u < 0.01


# -- rate inversion ----------------------------------------------------------


@pytest.mark.parametrize("target_pa", [1e6, 5e6, 12.5e6])
def test_rate_inversion_round_trips_exactly(target_pa):
    """dP is proportional to Q, so the inversion is a single division."""
    qmax = max_injection_rate_m3_s(allowable_delta_p_pa=target_pa, **BASE)
    assert theis_injection_delta_p_pa(rate_m3_s=qmax, **BASE) == pytest.approx(
        target_pa, rel=1e-12
    )


def test_delta_p_is_exactly_linear_in_rate():
    base = theis_injection_delta_p_pa(rate_m3_s=DEFAULT_RATE_M3_S, **BASE)
    doubled = theis_injection_delta_p_pa(rate_m3_s=DEFAULT_RATE_M3_S * 2, **BASE)
    assert doubled / base == pytest.approx(2.0, abs=1e-12)


# -- Finding 5.1: far-field dP vs near-well fracture limit --------------------


def test_pressure_rise_is_highest_at_the_wellbore():
    """Radial flow peaks at the well; that is where fracturing happens."""
    radii = [0.1, 1.0, 10.0, 100.0, 500.0, 1000.0, 5000.0]
    values = [
        theis_injection_delta_p_pa(rate_m3_s=DEFAULT_RATE_M3_S, **dict(BASE, radius_m=r))
        for r in radii
    ]
    assert values == sorted(values, reverse=True)


def test_default_radius_understates_wellbore_pressure_by_about_three_times():
    """CHARACTERISATION, Finding 5.1 -- the largest issue in Phase 5.

    The fracture headroom is a near-wellbore constraint, but the CLI compares it
    against dP evaluated 500 m away. The permitted rate is overstated by 3.20x.

    When Finding 5.1 is resolved, the fracture check should evaluate at a
    wellbore radius and this test must be replaced.
    """
    at_well = theis_injection_delta_p_pa(rate_m3_s=DEFAULT_RATE_M3_S, **dict(BASE, radius_m=0.1))
    at_default = theis_injection_delta_p_pa(rate_m3_s=DEFAULT_RATE_M3_S, **BASE)
    assert at_well / at_default == pytest.approx(3.20, abs=0.02)


def test_rate_ceiling_inherits_the_same_three_times_overstatement():
    """CHARACTERISATION, Finding 5.1, expressed as the number a user acts on.

    Phase 14: the rate ceiling is NOT_VALIDATED (rule B) and needs a
    caller-supplied criterion; the 3.20x ratio does not depend on it.
    """
    headroom_pa = allowable_delta_p_pa(initial_pressure_pa=1.6e7, depth_m=2000.0,
                                       **CALLER_CRITERION)
    at_default = max_injection_rate_m3_s(allowable_delta_p_pa=headroom_pa, **BASE)
    at_well = max_injection_rate_m3_s(
        allowable_delta_p_pa=headroom_pa, **dict(BASE, radius_m=0.1)
    )
    assert at_default / at_well == pytest.approx(3.20, abs=0.02)
    unit_default = theis_injection_delta_p_pa(rate_m3_s=1.0, **BASE)
    unit_well = theis_injection_delta_p_pa(rate_m3_s=1.0, **dict(BASE, radius_m=0.1))
    assert at_default == pytest.approx(headroom_pa / unit_default, rel=1e-12)
    assert at_well == pytest.approx(headroom_pa / unit_well, rel=1e-12)


# -- Finding 5.2: depth and initial pressure disagree ------------------------


def test_cli_default_depth_and_pressure_are_mutually_inconsistent():
    """CHARACTERISATION, Finding 5.2.

    The pressure prior midpoint (16.0 MPa) implies 1554 m at rho = 1050, but
    depth_m defaults to 2000 m, which implies 20.59 MPa. 28.7% apart.
    """
    from ccs_screen.ingest.scenario import STANDARD_GRAVITY_M_S2
    from ccs_screen.monte_carlo import DEPLETED_GAS_ANALOG

    prior_midpoint_pa = sum(DEPLETED_GAS_ANALOG.pressure_pa) / 2
    implied_by_depth_pa = 1050.0 * STANDARD_GRAVITY_M_S2 * 2000.0
    assert prior_midpoint_pa == pytest.approx(1.6e7)
    disagreement = (implied_by_depth_pa - prior_midpoint_pa) / prior_midpoint_pa
    assert disagreement == pytest.approx(0.287, abs=0.005)


def test_inconsistent_defaults_inflate_the_headroom():
    """CHARACTERISATION, Finding 5.2: the 16 MPa prior midpoint against the
    2000 m default depth inflates headroom. Phase 14: headroom is NOT_VALIDATED
    and its criterion is caller-supplied (rule B); the former 1.72x figure was
    specific to the removed 15 000 Pa/m / 0.9 defaults."""
    from ccs_screen.ingest.scenario import STANDARD_GRAVITY_M_S2

    depth_m = 2000.0
    consistent_initial = 1050.0 * STANDARD_GRAVITY_M_S2 * depth_m
    as_shipped = allowable_delta_p_pa(initial_pressure_pa=1.6e7, depth_m=depth_m,
                                      **CALLER_CRITERION)
    consistent = allowable_delta_p_pa(initial_pressure_pa=consistent_initial, depth_m=depth_m,
                                      **CALLER_CRITERION)
    limit = (CALLER_CRITERION["safety_factor"] * CALLER_CRITERION["fracture_gradient_pa_m"]
             * depth_m)
    assert as_shipped / consistent == pytest.approx(
        (limit - 1.6e7) / (limit - consistent_initial), rel=1e-12)
    assert as_shipped > consistent


# -- Finding 5.3: brine analog ----------------------------------------------


def test_brine_analog_gives_about_seven_times_the_co2_mobility_pressure_rise():
    """Finding 5.3: conservative on mobility, but not a bound of known tightness."""
    brine = theis_injection_delta_p_pa(rate_m3_s=DEFAULT_RATE_M3_S, **BASE)
    co2 = theis_injection_delta_p_pa(
        rate_m3_s=DEFAULT_RATE_M3_S, **dict(BASE, viscosity_pa_s=5.0e-5)
    )
    assert brine / co2 == pytest.approx(7.0, abs=0.2)


def test_theis_takes_no_absolute_pressure_argument():
    """Why Phase 4's gauge/absolute finding cannot reach the Theis mathematics."""
    parameters = inspect.signature(theis_injection_delta_p_pa).parameters
    assert not any("pressure" in name for name in parameters)


# -- time behaviour ----------------------------------------------------------


def test_pressure_grows_without_reaching_steady_state():
    """Infinite-acting radial flow: logarithmic growth, no plateau."""
    years = [0.1, 1, 10, 30, 100, 1000]
    values = [
        theis_injection_delta_p_pa(
            rate_m3_s=DEFAULT_RATE_M3_S, **dict(BASE, time_s=y * 365.25 * 24 * 3600)
        )
        for y in years
    ]
    assert values == sorted(values)
    assert values[0] / 1e6 == pytest.approx(2.8413, abs=0.01)
    assert values[-1] / 1e6 == pytest.approx(11.0654, abs=0.01)
    # Growth is logarithmic, so a 10000x longer injection is under 4x the rise.
    assert values[-1] / values[0] < 4.0


# -- validation --------------------------------------------------------------


@pytest.mark.parametrize(
    "override",
    [
        {"rate_m3_s": 0.0}, {"rate_m3_s": -1.0},
        {"time_s": 0.0}, {"radius_m": 0.0},
        {"permeability_m2": 0.0}, {"compressibility_1_pa": 0.0},
        {"porosity": 0.0}, {"viscosity_pa_s": 0.0}, {"thickness_m": 0.0},
    ],
)
def test_rejects_non_positive_inputs(override):
    kwargs = dict(BASE, rate_m3_s=DEFAULT_RATE_M3_S)
    kwargs.update(override)
    with pytest.raises(ValueError):
        theis_injection_delta_p_pa(**kwargs)


def test_rate_ceiling_rejects_zero_headroom():
    with pytest.raises(ValueError):
        max_injection_rate_m3_s(allowable_delta_p_pa=0.0, **BASE)


@pytest.mark.parametrize(
    "override", [{"radius_m": 1e6}, {"time_s": 1.0}]
)
def test_extreme_arguments_underflow_to_zero_rather_than_raising(override):
    """Physically right -- the signal has not arrived -- but silently so."""
    value = theis_injection_delta_p_pa(
        rate_m3_s=DEFAULT_RATE_M3_S, **dict(BASE, **override)
    )
    assert value == 0.0


# -- fracture coupling -------------------------------------------------------


def test_headroom_and_ceiling_are_proportional():
    """Qmax is linear in the allowance, so a headroom error passes straight through."""
    a = max_injection_rate_m3_s(allowable_delta_p_pa=5e6, **BASE)
    b = max_injection_rate_m3_s(allowable_delta_p_pa=10e6, **BASE)
    assert b / a == pytest.approx(2.0, abs=1e-12)


def test_fracture_limit_uses_the_derated_gradient():
    """Arithmetic only. Phase 14 (D1, rule B): the gradient and safety factor are
    caller-supplied with no default; the values below are arbitrary test inputs."""
    depth_m, initial_pressure_pa = 2000.0, 1.6e7
    gradient, safety_factor = 17_000.0, 0.8
    expected = safety_factor * depth_m * gradient - initial_pressure_pa
    assert allowable_delta_p_pa(
        initial_pressure_pa=initial_pressure_pa, depth_m=depth_m,
        fracture_gradient_pa_m=gradient, safety_factor=safety_factor,
    ) == pytest.approx(expected, rel=1e-15)
