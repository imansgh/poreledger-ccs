"""Phase 11 audit: a second implementation of the chain, kept in the suite.

The functions in the INDEPENDENT block below are written from the published
equations, not from the production code. They use ``math`` only -- not even
scipy, so the exponential integral is computed from its own series and
continued-fraction expansions. Keeping them here means the production code stays
checked against something that does not share a line with it.

A test at the bottom enforces the discipline by parsing this module's AST: the
independent block must not reference ``ccs_screen``.

Phase 11 measured a worst relative difference of 1.64e-16 across every
comparison -- one ulp. The bounds below are tight because anything looser would
stop being evidence.

See ``docs/scientific-validation-audit.md``, Phase 11.
"""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest
from conftest import coolprop_propssi

# =============================== INDEPENDENT ===============================
# From the published equations. Nothing below this line may use ccs_screen.

R_GAS = 8.314462618
G_STANDARD = 9.80665
EULER = 0.5772156649015328606
TC, PC, OMEGA, MW, Z_RA = 304.1282, 7.3773e6, 0.225, 0.0440095, 0.2722


def _pr_ab(pressure, temperature):
    kappa = 0.37464 + 1.54226 * OMEGA - 0.26992 * OMEGA * OMEGA
    alpha = (1.0 + kappa * (1.0 - math.sqrt(temperature / TC))) ** 2
    a = 0.45724 * (R_GAS * TC) ** 2 / PC * alpha
    b = 0.07780 * R_GAS * TC / PC
    return a * pressure / (R_GAS * temperature) ** 2, b * pressure / (R_GAS * temperature)


def _cubic_roots(b, c, d):
    p = c - b * b / 3.0
    q = d + (2.0 * b ** 3 - 9.0 * b * c) / 27.0
    shift = b / 3.0
    disc = (q / 2.0) ** 2 + (p / 3.0) ** 3
    if disc > 0:
        s = math.sqrt(disc)
        u = math.copysign(abs(-q / 2.0 + s) ** (1.0 / 3.0), -q / 2.0 + s)
        v = math.copysign(abs(-q / 2.0 - s) ** (1.0 / 3.0), -q / 2.0 - s)
        return [u + v - shift]
    r = math.sqrt(max(-p / 3.0, 0.0))
    if r < 1e-300:
        return [-shift]
    phi = math.acos(max(-1.0, min(1.0, -q / (2.0 * r ** 3))))
    return [2.0 * r * math.cos((phi + 2.0 * math.pi * k) / 3.0) - shift for k in range(3)]


def _ln_phi(z, a_dim, b_dim):
    root_two = math.sqrt(2.0)
    inner = (z + (1.0 + root_two) * b_dim) / (z + (1.0 - root_two) * b_dim)
    if z <= b_dim or inner <= 0:
        return math.inf
    return z - 1.0 - math.log(z - b_dim) - a_dim / (2.0 * root_two * b_dim) * math.log(inner)


def independent_z_factor(pressure, temperature):
    a_dim, b_dim = _pr_ab(pressure, temperature)
    roots = _cubic_roots(
        -(1.0 - b_dim),
        a_dim - 2.0 * b_dim - 3.0 * b_dim * b_dim,
        -(a_dim * b_dim - b_dim * b_dim - b_dim ** 3),
    )
    physical = [z for z in roots if z > b_dim]
    if len(physical) == 1:
        return physical[0]
    low, high = min(physical), max(physical)
    return low if _ln_phi(low, a_dim, b_dim) <= _ln_phi(high, a_dim, b_dim) else high


def independent_peneloux_shift():
    return 0.40768 * (R_GAS * TC / PC) * (0.29441 - Z_RA)


def independent_density(pressure, temperature, translate=True):
    volume = independent_z_factor(pressure, temperature) * R_GAS * temperature / pressure
    if translate:
        volume -= independent_peneloux_shift()
    return MW / volume


def independent_hydrostatic(brine_density, depth):
    return brine_density * G_STANDARD * depth


def independent_capacity_mt(area, thickness, porosity, density, efficiency):
    return area * thickness * porosity * efficiency * density / 1.0e9


def independent_e1(x):
    """Exponential integral, series below 1 and modified Lentz above."""
    if x < 1.0:
        total, term = 0.0, 1.0
        for n in range(1, 200):
            term *= x / n
            total += ((-1) ** (n + 1)) * term / n
        return -EULER - math.log(x) + total
    b, c, d = x + 1.0, 1e300, 1.0 / (x + 1.0)
    h = d
    for i in range(1, 300):
        a = -i * i
        b += 2.0
        d = 1.0 / (a * d + b)
        c = b + a / c
        delta = c * d
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h * math.exp(-x)


def independent_theis_delta_p(rate, perm, thickness, viscosity, time_s, radius, porosity, ct):
    transmissivity = perm * thickness / viscosity
    storativity = porosity * ct * thickness
    u = radius * radius * storativity / (4.0 * transmissivity * time_s)
    return rate / (4.0 * math.pi * transmissivity) * independent_e1(u)


# ============================= END INDEPENDENT =============================

#: Four real wells, at their ingested depths and temperatures.
CASES = [
    ("SALUZZO|1", 1527.5, 318.15),
    ("DESANA|1", 3224.9, 370.15),
    ("MALOSSA|15", 5491.0, 416.15),
    ("TRECATE|9|ST", 6087.0, 452.15),
]
BRINE_DENSITY = 1060.0
GEOMETRY = dict(area=8.0e7, thickness=35.0, porosity=0.225, efficiency=0.025)

AQUIFER = dict(
    perm=8e-14, thickness=40.0, viscosity=4.5e-4,
    time_s=10 * 365.25 * 24 * 3600, radius=500.0, porosity=0.18, ct=1.2e-9,
)


# -- constants ---------------------------------------------------------------


def test_standard_gravity_agrees():
    from ccs_screen.ingest.scenario import STANDARD_GRAVITY_M_S2

    assert independent_hydrostatic(1.0, 1.0) == STANDARD_GRAVITY_M_S2


def test_peneloux_shift_agrees_exactly():
    from ccs_screen.properties import peneloux_shift_m3_mol

    assert independent_peneloux_shift() == pytest.approx(peneloux_shift_m3_mol(), rel=1e-15)


def test_megatonne_conversion_agrees():
    from ccs_screen.monte_carlo import KG_PER_MT

    assert KG_PER_MT == 1.0e9


# -- the chain, well by well -------------------------------------------------


@pytest.mark.parametrize("well,depth_m,temperature_k", CASES)
def test_hydrostatic_pressure_agrees(well, depth_m, temperature_k):
    from ccs_screen.ingest.scenario import STANDARD_GRAVITY_M_S2

    assert independent_hydrostatic(BRINE_DENSITY, depth_m) == pytest.approx(
        BRINE_DENSITY * STANDARD_GRAVITY_M_S2 * depth_m, rel=1e-15
    )


@pytest.mark.parametrize("well,depth_m,temperature_k", CASES)
def test_compressibility_agrees(well, depth_m, temperature_k):
    """The cubic solution and the fugacity root selection, reproduced."""
    from ccs_screen.properties import co2_compressibility

    pressure = independent_hydrostatic(BRINE_DENSITY, depth_m)
    assert independent_z_factor(pressure, temperature_k) == pytest.approx(
        co2_compressibility(pressure, temperature_k), rel=1e-14
    )


@pytest.mark.parametrize("well,depth_m,temperature_k", CASES)
def test_density_agrees(well, depth_m, temperature_k):
    from ccs_screen.properties import co2_density_kg_m3

    pressure = independent_hydrostatic(BRINE_DENSITY, depth_m)
    assert independent_density(pressure, temperature_k) == pytest.approx(
        co2_density_kg_m3(pressure, temperature_k), rel=1e-14
    )


@pytest.mark.parametrize("well,depth_m,temperature_k", CASES)
def test_capacity_agrees_end_to_end(well, depth_m, temperature_k):
    """Depth to megatonnes, by two routes that share no code."""
    from ccs_screen.capacity import volumetric_storage_mass_kg
    from ccs_screen.monte_carlo import KG_PER_MT
    from ccs_screen.properties import co2_density_kg_m3

    pressure = independent_hydrostatic(BRINE_DENSITY, depth_m)
    mine = independent_capacity_mt(
        density=independent_density(pressure, temperature_k), **GEOMETRY
    )
    theirs = volumetric_storage_mass_kg(
        area_m2=GEOMETRY["area"], thickness_m=GEOMETRY["thickness"],
        porosity=GEOMETRY["porosity"],
        co2_density_kg_m3=co2_density_kg_m3(pressure, temperature_k),
        storage_efficiency=GEOMETRY["efficiency"],
    ) / KG_PER_MT
    assert mine == pytest.approx(theirs, rel=1e-14)


# -- injectivity -------------------------------------------------------------


def test_exponential_integral_agrees_with_scipy():
    """A third route to the well function: own series vs scipy's exp1."""
    from scipy.special import exp1

    for u in (1e-8, 2.40631417e-04, 1e-2, 0.5, 1.0, 2.0, 5.0):
        assert independent_e1(u) == pytest.approx(float(exp1(u)), rel=1e-12)


def test_theis_drawdown_agrees():
    from ccs_screen.pressure import theis_injection_delta_p_pa

    mine = independent_theis_delta_p(0.08, **AQUIFER)
    theirs = theis_injection_delta_p_pa(
        rate_m3_s=0.08, permeability_m2=AQUIFER["perm"], thickness_m=AQUIFER["thickness"],
        viscosity_pa_s=AQUIFER["viscosity"], time_s=AQUIFER["time_s"],
        radius_m=AQUIFER["radius"], porosity=AQUIFER["porosity"],
        compressibility_1_pa=AQUIFER["ct"],
    )
    assert mine == pytest.approx(theirs, rel=1e-13)
    assert mine / 1e6 == pytest.approx(6.942878, abs=1e-5)


def test_rate_ceiling_agrees():
    """Arithmetic only. Phase 14 (D1, rule B): the fracture criterion has no
    default; 17 000 Pa/m and 0.8 are arbitrary caller-supplied test values."""
    from ccs_screen.pressure import allowable_delta_p_pa, max_injection_rate_m3_s

    headroom = max(0.8 * 2000.0 * 17000.0 - 1.6e7, 0.0)
    assert headroom == pytest.approx(
        allowable_delta_p_pa(initial_pressure_pa=1.6e7, depth_m=2000.0,
                             fracture_gradient_pa_m=17000.0, safety_factor=0.8),
        rel=1e-15,
    )
    mine = headroom / independent_theis_delta_p(1.0, **AQUIFER)
    theirs = max_injection_rate_m3_s(
        allowable_delta_p_pa=headroom, permeability_m2=AQUIFER["perm"],
        thickness_m=AQUIFER["thickness"], viscosity_pa_s=AQUIFER["viscosity"],
        time_s=AQUIFER["time_s"], radius_m=AQUIFER["radius"],
        porosity=AQUIFER["porosity"], compressibility_1_pa=AQUIFER["ct"],
    )
    assert mine == pytest.approx(theirs, rel=1e-13)


# -- Finding 11.1: the validated envelope ------------------------------------



@pytest.mark.parametrize("well,depth_m,temperature_k", CASES)
def test_error_against_span_wagner_grows_with_pressure(well, depth_m, temperature_k):
    """CHARACTERISATION, Finding 11.1.

    Phase 1 validated the EOS over 1-35 MPa. MALOSSA and TRECATE sit at 57 and
    63 MPa, where the constant Peneloux shift over-corrects to about +7%.
    """
    PropsSI = coolprop_propssi()

    pressure = independent_hydrostatic(BRINE_DENSITY, depth_m)
    reference = PropsSI("D", "P", pressure, "T", temperature_k, "CO2")
    error = (independent_density(pressure, temperature_k) - reference) / reference

    if pressure > 35e6:
        assert error > 0.05, f"{well} should show the high-pressure over-correction"
    else:
        assert abs(error) < 0.05


def test_the_shift_helps_at_low_pressure_and_hurts_at_high():
    """The trade-off that makes Finding 11.1 a judgement rather than a bug."""
    PropsSI = coolprop_propssi()

    def errors(depth_m, temperature_k):
        pressure = independent_hydrostatic(BRINE_DENSITY, depth_m)
        reference = PropsSI("D", "P", pressure, "T", temperature_k, "CO2")
        translated = independent_density(pressure, temperature_k, translate=True)
        plain = independent_density(pressure, temperature_k, translate=False)
        return abs(translated - reference) / reference, abs(plain - reference) / reference

    shallow_translated, shallow_plain = errors(1527.5, 318.15)
    deep_translated, deep_plain = errors(5491.0, 416.15)

    assert shallow_translated < shallow_plain, "the shift should help at 16 MPa"
    assert deep_translated > deep_plain, "the shift should hurt at 57 MPa"


# -- the independence guard --------------------------------------------------


def test_the_independent_block_does_not_reference_production_code():
    """The discipline this module exists for, checked by AST rather than by eye.

    Every ccs_screen import in this file must sit inside a test function, so the
    independent implementations above cannot accidentally be written in terms of
    the code they are meant to check.
    """
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    module_level_imports = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            module_level_imports.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            module_level_imports.add(node.module.split(".")[0])
    assert "ccs_screen" not in module_level_imports

    independent_names = {
        "independent_z_factor", "independent_density", "independent_peneloux_shift",
        "independent_hydrostatic", "independent_capacity_mt", "independent_e1",
        "independent_theis_delta_p", "_pr_ab", "_cubic_roots", "_ln_phi",
    }
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in independent_names:
            source = ast.dump(node)
            assert "ccs_screen" not in source, f"{node.name} references production code"
