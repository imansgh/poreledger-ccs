"""Phase-behaviour and accuracy checks for the Peng-Robinson CO2 density.

Reference densities are Span-Wagner (NIST Webbook) values. Peng-Robinson is a
screening EOS, so the tolerances below are deliberately loose; they exist to
catch a wrong *root* (an 18x error) rather than to certify the EOS.
"""

import math

import pytest

from ccs_screen.properties import co2_density_kg_m3

# (pressure_pa, temperature_k, span_wagner_kg_m3)
SUBCRITICAL_GAS = [
    (2.0e6, 280.0, 43.6),   # Psat(280 K) = 4.16 MPa -> vapour
    (3.0e6, 280.0, 70.9),
    (4.0e6, 290.0, 101.6),  # Psat(290 K) = 5.36 MPa -> vapour
]

SUBCRITICAL_LIQUID = [
    (5.0e6, 280.0, 883.6),
    (8.0e6, 290.0, 796.6),
]

DENSE_PHASE = [
    (12.0e6, 320.0, 617.7),
    (15.0e6, 333.15, 604.3),
    (20.0e6, 340.0, 692.4),
    (30.0e6, 350.0, 829.8),
]


@pytest.mark.parametrize("pressure_pa,temperature_k,reference", SUBCRITICAL_GAS)
def test_vapour_root_is_selected_below_saturation(pressure_pa, temperature_k, reference):
    """Below Psat the EOS has three roots; the vapour (largest Z) one is physical."""
    rho = co2_density_kg_m3(pressure_pa, temperature_k)
    assert rho == pytest.approx(reference, rel=0.30)
    assert rho < 200, "picked the liquid root in the vapour region"


@pytest.mark.parametrize("pressure_pa,temperature_k,reference", SUBCRITICAL_LIQUID)
def test_liquid_root_is_selected_above_saturation(pressure_pa, temperature_k, reference):
    rho = co2_density_kg_m3(pressure_pa, temperature_k)
    assert rho == pytest.approx(reference, rel=0.20)
    assert rho > 500, "picked the vapour root in the liquid region"


@pytest.mark.parametrize("pressure_pa,temperature_k,reference", DENSE_PHASE)
def test_dense_phase_density_within_screening_tolerance(pressure_pa, temperature_k, reference):
    """Storage conditions are the design point: keep these within 8%."""
    rho = co2_density_kg_m3(pressure_pa, temperature_k)
    assert rho == pytest.approx(reference, rel=0.08)


def test_density_is_monotonic_in_pressure_at_fixed_temperature():
    rhos = [co2_density_kg_m3(p, 333.15) for p in (8e6, 10e6, 15e6, 20e6, 30e6)]
    assert all(b > a for a, b in zip(rhos, rhos[1:]))


def test_density_falls_with_temperature_at_fixed_pressure():
    rhos = [co2_density_kg_m3(15e6, t) for t in (320.0, 333.15, 350.0, 370.0)]
    assert all(b < a for a, b in zip(rhos, rhos[1:]))


def test_ideal_gas_limit_at_low_pressure():
    """At 0.1 MPa CO2 is nearly ideal: rho -> P*MW/(R*T)."""
    rho = co2_density_kg_m3(1.0e5, 350.0)
    ideal = 1.0e5 * 0.0440095 / (8.314462618 * 350.0)
    assert math.isclose(rho, ideal, rel_tol=0.02)


@pytest.mark.parametrize("pressure_pa,temperature_k", [(0.0, 300.0), (-1.0, 300.0), (1e6, 0.0), (1e6, -5.0)])
def test_rejects_non_physical_state(pressure_pa, temperature_k):
    with pytest.raises(ValueError):
        co2_density_kg_m3(pressure_pa, temperature_k)
