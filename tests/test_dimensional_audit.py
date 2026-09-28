"""Phase 2 audit regression tests: dimensional and unit consistency.

These pin the dimensional *structure* of the equations, not their values.
A formula can be dimensionally perfect and still carry a wrong coefficient;
that is Phases 3-5. What breaks here is a unit conversion or an exponent, which
is the class of error that produces answers wrong by a factor of 1000 while
looking entirely reasonable.

Method: scale one input, assert the output scales by the exponent the
dimensional analysis predicts. See ``docs/scientific-validation-audit.md``,
Phase 2.
"""

from __future__ import annotations

import inspect
import math

import pytest

from ccs_screen.capacity import volumetric_storage_mass_kg
from ccs_screen.ingest.provenance import Unit
from ccs_screen.ingest.scenario import STANDARD_GRAVITY_M_S2
from ccs_screen.ingest.units import (
    FEET_PER_METRE,
    KELVIN_OFFSET,
    METRES_PER_FOOT,
    UnitError,
    to_kelvin,
    to_metres,
)
from ccs_screen.monte_carlo import KG_PER_MT
from ccs_screen.pressure import (
    fracture_pressure_pa,
    theis_injection_delta_p_pa,
    theis_transmissivity,
)
from ccs_screen.properties import co2_density_kg_m3

CAPACITY_BASE = dict(
    area_m2=1e8,
    thickness_m=40.0,
    porosity=0.2,
    co2_density_kg_m3=700.0,
    storage_efficiency=0.04,
)

THEIS_BASE = dict(
    rate_m3_s=0.08,
    permeability_m2=8e-14,
    thickness_m=40.0,
    viscosity_pa_s=4.5e-4,
    time_s=10 * 365.25 * 24 * 3600,
    radius_m=500.0,
    porosity=0.18,
    compressibility_1_pa=1.2e-9,
)


# -- capacity: M = A h phi rho E ---------------------------------------------


@pytest.mark.parametrize("factor", list(CAPACITY_BASE))
def test_capacity_is_exactly_linear_in_every_factor(factor):
    """A pure product must have exponent +1 in each argument.

    Any exponent other than 1 means a factor is squared, missing, or in a
    denominator.
    """
    base = volumetric_storage_mass_kg(**CAPACITY_BASE)
    doubled = dict(CAPACITY_BASE)
    doubled[factor] = CAPACITY_BASE[factor] * 2
    ratio = volumetric_storage_mass_kg(**doubled) / base
    assert math.log2(ratio) == pytest.approx(1.0, abs=1e-12)


def test_capacity_product_equals_the_hand_calculation():
    """m2 * m * 1 * kg/m3 * 1 = kg, computed independently of the function."""
    expected = (
        CAPACITY_BASE["area_m2"]
        * CAPACITY_BASE["thickness_m"]
        * CAPACITY_BASE["porosity"]
        * CAPACITY_BASE["co2_density_kg_m3"]
        * CAPACITY_BASE["storage_efficiency"]
    )
    assert volumetric_storage_mass_kg(**CAPACITY_BASE) == pytest.approx(expected, rel=1e-15)


def test_capacity_via_pore_volume_route_agrees():
    """Independent route: pore volume -> CO2 volume -> mass."""
    pore_volume_m3 = (
        CAPACITY_BASE["area_m2"] * CAPACITY_BASE["thickness_m"] * CAPACITY_BASE["porosity"]
    )
    co2_volume_m3 = pore_volume_m3 * CAPACITY_BASE["storage_efficiency"]
    mass_kg = co2_volume_m3 * CAPACITY_BASE["co2_density_kg_m3"]
    assert volumetric_storage_mass_kg(**CAPACITY_BASE) == pytest.approx(mass_kg, rel=1e-15)


# -- mass unit ---------------------------------------------------------------


def test_megatonne_conversion_and_its_near_misses():
    """1 Mt = 1e6 t = 1e9 kg. The dangerous neighbours are 1e3 and 1e6."""
    assert KG_PER_MT == 1e9
    assert KG_PER_MT == 1e6 * 1e3
    assert KG_PER_MT != 1e3, "that would be kg->t"
    assert KG_PER_MT != 1e6, "that would be kg->kt"


def test_capacity_in_megatonnes_has_a_sane_magnitude():
    """80 km2 x 35 m closure should give tens of Mt, not thousands or 0.01."""
    kg = volumetric_storage_mass_kg(
        area_m2=8.0e7, thickness_m=35.0, porosity=0.18,
        co2_density_kg_m3=758.4, storage_efficiency=0.025,
    )
    megatonnes = kg / KG_PER_MT
    assert 1.0 < megatonnes < 100.0, f"{megatonnes} Mt is implausible for this geometry"


# -- Theis -------------------------------------------------------------------


def test_theis_u_is_dimensionless():
    """u = r^2 S / (4 T t); recomputed here from the same inputs.

    m2 * (m/Pa) / (m3/(Pa s) * s) = (m3/Pa)/(m3/Pa) = 1.
    """
    transmissivity = theis_transmissivity(
        THEIS_BASE["permeability_m2"], THEIS_BASE["thickness_m"], THEIS_BASE["viscosity_pa_s"]
    )
    storativity = (
        THEIS_BASE["porosity"] * THEIS_BASE["compressibility_1_pa"] * THEIS_BASE["thickness_m"]
    )
    u = (THEIS_BASE["radius_m"] ** 2 * storativity) / (
        4 * transmissivity * THEIS_BASE["time_s"]
    )
    assert 0 < u < 1e6 and math.isfinite(u)


def test_theis_drawdown_is_exactly_linear_in_rate():
    """Q appears only in the prefactor, so the exponent must be exactly +1."""
    base = theis_injection_delta_p_pa(**THEIS_BASE)
    doubled = dict(THEIS_BASE)
    doubled["rate_m3_s"] *= 2
    assert math.log2(theis_injection_delta_p_pa(**doubled) / base) == pytest.approx(1.0, abs=1e-12)


def test_theis_thickness_exponent_is_exactly_minus_one():
    """h cancels inside u, leaving dp = Q mu /(4 pi k h) W(u).

    This is a structural check on the transmissivity and storativity
    formulations together: an error in either would break the cancellation and
    the exponent would drift off -1.
    """
    base = theis_injection_delta_p_pa(**THEIS_BASE)
    doubled = dict(THEIS_BASE)
    doubled["thickness_m"] *= 2
    assert math.log2(theis_injection_delta_p_pa(**doubled) / base) == pytest.approx(-1.0, abs=1e-9)


@pytest.mark.parametrize("parameter", ["permeability_m2", "viscosity_pa_s"])
def test_theis_exponents_are_non_integer_by_design(parameter):
    """k and mu appear in the prefactor AND inside W(u), so |exponent| < 1."""
    base = theis_injection_delta_p_pa(**THEIS_BASE)
    doubled = dict(THEIS_BASE)
    doubled[parameter] = THEIS_BASE[parameter] * 2
    exponent = abs(math.log2(theis_injection_delta_p_pa(**doubled) / base))
    assert 0.5 < exponent < 1.0


def test_transmissivity_is_kh_over_mu():
    assert theis_transmissivity(1e-13, 50.0, 5e-4) == pytest.approx(1e-13 * 50.0 / 5e-4, rel=1e-15)


# -- pressure ----------------------------------------------------------------


def test_hydrostatic_pressure_has_pascal_dimension():
    """rho g z = kg/m3 * m/s2 * m = kg/(m s2) = Pa."""
    pressure_pa = 1050.0 * STANDARD_GRAVITY_M_S2 * 1527.5
    assert pressure_pa == pytest.approx(1050.0 * 9.80665 * 1527.5, rel=1e-15)
    # A 1.5 km column of brine is ~15 MPa; a factor-1000 slip is unmissable.
    assert 1e7 < pressure_pa < 2e7


def test_fracture_pressure_is_exactly_linear_in_depth():
    """Phase 14 (D1): the gradient has no default; 17 000 Pa/m is an arbitrary test value."""
    gradient = 17_000.0
    assert (fracture_pressure_pa(4000.0, gradient) / fracture_pressure_pa(2000.0, gradient)
            == pytest.approx(2.0, abs=1e-12))


# -- conversion constants ----------------------------------------------------


def test_length_conversion_constants_are_exact():
    assert METRES_PER_FOOT == 0.3048, "international foot is exact"
    assert FEET_PER_METRE == pytest.approx(1 / 0.3048, rel=1e-15)
    assert FEET_PER_METRE * METRES_PER_FOOT == pytest.approx(1.0, abs=1e-15)


def test_temperature_and_gravity_constants_are_exact():
    assert KELVIN_OFFSET == 273.15
    assert STANDARD_GRAVITY_M_S2 == 9.80665, "CGPM 1901 standard gravity is exact"


def test_foot_to_metre_conversion():
    assert to_metres(1000.0, Unit.FOOT) == pytest.approx(304.8, rel=1e-12)
    assert to_metres(1000.0, Unit.METRE) == pytest.approx(1000.0)


def test_celsius_to_kelvin_conversion_is_applied_once():
    assert to_kelvin(0.0, Unit.CELSIUS) == pytest.approx(273.15)
    assert to_kelvin(45.0, Unit.CELSIUS) == pytest.approx(318.15)
    # Idempotent on kelvin: a second conversion must not add 273.15 again.
    assert to_kelvin(to_kelvin(45.0, Unit.CELSIUS), Unit.KELVIN) == pytest.approx(318.15)


@pytest.mark.parametrize("unit", [Unit.PASCAL, Unit.DIMENSIONLESS, Unit.KELVIN])
def test_length_conversion_refuses_a_non_length_unit(unit):
    with pytest.raises(UnitError):
        to_metres(3000.0, unit)


# -- Finding 2.1: positional argument order ----------------------------------


def test_density_signature_order_is_pressure_then_temperature():
    """Finding 2.1. Both arguments are positive floats, so a swap is silent.

    This pins the signature so the single production call site cannot be
    invalidated by a parameter reorder.
    """
    parameters = list(inspect.signature(co2_density_kg_m3).parameters)
    assert parameters[:2] == ["pressure_pa", "temperature_k"]


def test_swapped_pressure_and_temperature_is_physically_absurd():
    """Characterises the trap rather than preventing it.

    A swapped call is accepted and returns ~1e-7 kg/m3. Documented as
    PASS WITH CAVEAT; no guard was added, because that would change behaviour.
    """
    correct = co2_density_kg_m3(15e6, 333.15)
    swapped = co2_density_kg_m3(333.15, 15e6)
    assert 500 < correct < 700
    assert swapped < 1e-3, "a swap should be obviously absurd if it ever happens"


def test_production_call_site_passes_pressure_first():
    """The one call site outside properties.py, checked by round-trip.

    sample_mass_mt must produce the same mass as calling the EOS directly with
    (pressure, temperature) in that order.
    """
    from ccs_screen.monte_carlo import CapacitySample, sample_mass_mt

    sample = CapacitySample(
        area_m2=1e8, thickness_m=40.0, porosity=0.2,
        pressure_pa=15e6, temperature_k=333.15, storage_efficiency=0.04,
    )
    expected_kg = volumetric_storage_mass_kg(
        area_m2=sample.area_m2, thickness_m=sample.thickness_m,
        porosity=sample.porosity,
        co2_density_kg_m3=co2_density_kg_m3(sample.pressure_pa, sample.temperature_k),
        storage_efficiency=sample.storage_efficiency,
    )
    assert sample_mass_mt(sample) == pytest.approx(expected_kg / KG_PER_MT, rel=1e-15)


# -- end-to-end chain --------------------------------------------------------


def test_full_chain_from_celsius_to_megatonnes():
    """Every unit boundary in one test, with an independent cross-check."""
    temperature_k = to_kelvin(45.0, Unit.CELSIUS)
    pressure_pa = 1050.0 * STANDARD_GRAVITY_M_S2 * 1527.5
    density_kg_m3 = co2_density_kg_m3(pressure_pa, temperature_k)

    kg = volumetric_storage_mass_kg(
        area_m2=8.0e7, thickness_m=35.0, porosity=0.18,
        co2_density_kg_m3=density_kg_m3, storage_efficiency=0.025,
    )
    megatonnes = kg / KG_PER_MT

    assert temperature_k == pytest.approx(318.15)
    assert 1e7 < pressure_pa < 2e7
    assert 600 < density_kg_m3 < 900
    assert 5 < megatonnes < 20

    # Independent route.
    pore_volume = 8.0e7 * 35.0 * 0.18
    assert megatonnes == pytest.approx(pore_volume * 0.025 * density_kg_m3 / 1e9, rel=1e-12)
