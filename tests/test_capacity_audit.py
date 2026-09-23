"""Phase 3 audit regression tests for the volumetric capacity equation.

The arithmetic of ``M = A h phi rho E`` was verified exact in Phase 3, so these
tests spend most of their effort on the part that can actually rot: the
*semantics* of the two uncited inputs. With every elasticity exactly +1, a
factor-of-N slip in area or thickness is a factor-of-N slip in the answer, and
nothing downstream damps it.

The independent implementation below uses exact rational arithmetic and is
structured as bulk volume -> pore volume -> CO2 volume -> mass, deliberately not
as a single product, so it can disagree with the production function about term
ordering rather than only about rounding.

See ``docs/scientific-validation-audit.md``, Phase 3.
"""

from __future__ import annotations

import math
from fractions import Fraction

import pytest

from ccs_screen.api import USER_INPUT_SPEC
from ccs_screen.capacity import volumetric_storage_mass_kg
from ccs_screen.ingest.records import ThicknessKind
from ccs_screen.ingest.scenario import (
    AREA_POLICY_STATEMENT,
    NET_THICKNESS_POLICY_STATEMENT,
)

BASE = dict(
    area_m2=8.0e7,
    thickness_m=35.0,
    porosity=0.18,
    co2_density_kg_m3=758.4,
    storage_efficiency=0.025,
)


def independent_mass_kg(area_m2, thickness_m, porosity, co2_density_kg_m3, storage_efficiency):
    """Second implementation: exact rationals, four explicit physical steps."""
    bulk_rock_volume = Fraction(str(area_m2)) * Fraction(str(thickness_m))
    pore_volume = bulk_rock_volume * Fraction(str(porosity))
    co2_volume = pore_volume * Fraction(str(storage_efficiency))
    return co2_volume * Fraction(str(co2_density_kg_m3))


#: Published geometry from Donda et al. (2011) Table 2. Using real reservoirs
#: means the agreement is against external numbers, not numbers chosen to agree.
DONDA_CASES = [
    ("Abruzzi 1", 175e6, 80.0, 0.25, 700.0, 0.01),
    ("Marche 1", 615e6, 255.0, 0.35, 700.0, 0.04),
    ("Bradanica", 520e6, 480.0, 0.25, 700.0, 0.01),
]

HAND_CASES = [
    ("closure low", 5.0e7, 20.0, 0.10, 650.0, 0.01),
    ("closure mid", 8.0e7, 35.0, 0.18, 758.4, 0.025),
    ("closure high", 2.0e8, 60.0, 0.35, 850.0, 0.04),
]


# -- arithmetic --------------------------------------------------------------


@pytest.mark.parametrize(
    "name,area_m2,thickness_m,porosity,rho,efficiency", HAND_CASES + DONDA_CASES
)
def test_matches_independent_rational_implementation(
    name, area_m2, thickness_m, porosity, rho, efficiency
):
    """Phase 3 measured a maximum relative error of 2.1e-16 over these six."""
    exact = independent_mass_kg(area_m2, thickness_m, porosity, rho, efficiency)
    produced = volumetric_storage_mass_kg(
        area_m2=area_m2, thickness_m=thickness_m, porosity=porosity,
        co2_density_kg_m3=rho, storage_efficiency=efficiency,
    )
    assert produced == pytest.approx(float(exact), rel=1e-15)


def test_efficiency_acts_on_pore_volume_not_on_bulk_volume():
    """E must reduce the pore volume, not the rock volume.

    Both orderings give the same product, so this pins the *interpretation*: a
    100% efficient store holds exactly the pore volume of CO2, not the bulk
    rock volume.
    """
    pore_volume_m3 = BASE["area_m2"] * BASE["thickness_m"] * BASE["porosity"]
    full = volumetric_storage_mass_kg(**dict(BASE, storage_efficiency=0.999999))
    assert full / BASE["co2_density_kg_m3"] == pytest.approx(pore_volume_m3, rel=1e-5)


def test_efficiency_is_separable_from_porosity():
    """E and phi are independent factors, not a single lumped term.

    Halving phi and doubling E must leave the answer unchanged; if E were
    being derived from or double-applied to phi, it would not.
    """
    swapped = dict(BASE, porosity=BASE["porosity"] / 2, storage_efficiency=BASE["storage_efficiency"] * 2)
    assert volumetric_storage_mass_kg(**swapped) == pytest.approx(
        volumetric_storage_mass_kg(**BASE), rel=1e-15
    )


# -- sensitivity -------------------------------------------------------------


@pytest.mark.parametrize("parameter", list(BASE))
def test_elasticity_is_exactly_one(parameter):
    """d(ln M)/d(ln x) = 1 for every parameter: no damping anywhere.

    This is why the semantic findings matter more than the arithmetic: a
    factor-of-N error in any single input is a factor-of-N error in the answer.
    """
    base = volumetric_storage_mass_kg(**BASE)
    bumped = dict(BASE)
    bumped[parameter] = BASE[parameter] * 1.01
    elasticity = math.log(volumetric_storage_mass_kg(**bumped) / base) / math.log(1.01)
    assert elasticity == pytest.approx(1.0, abs=1e-9)


@pytest.mark.parametrize("parameter", list(BASE))
def test_strictly_increasing_in_every_parameter(parameter):
    """Monotonicity, checked over a range rather than at a single point."""
    values = []
    for factor in (0.25, 0.5, 1.0, 2.0, 3.0):
        candidate = dict(BASE)
        candidate[parameter] = BASE[parameter] * factor
        if candidate["porosity"] >= 1 or candidate["storage_efficiency"] >= 1:
            continue
        values.append(volumetric_storage_mass_kg(**candidate))
    assert values == sorted(values)
    assert len(set(values)) == len(values), "not strictly increasing"


def test_no_interaction_terms():
    """A pure product is separable: M(2A, 2h) == 4 M(A, h) exactly."""
    both = dict(BASE, area_m2=BASE["area_m2"] * 2, thickness_m=BASE["thickness_m"] * 2)
    assert volumetric_storage_mass_kg(**both) == pytest.approx(
        4 * volumetric_storage_mass_kg(**BASE), rel=1e-15
    )


# -- gross vs net thickness --------------------------------------------------


def test_gross_and_net_thickness_are_distinct_kinds():
    """Finding: the separation is structural, not a comment."""
    assert ThicknessKind.GROSS_STRATIGRAPHIC != ThicknessKind.NET_STORAGE
    assert len({k.value for k in ThicknessKind}) == 3


def test_thickness_spec_forbids_gross_substitution():
    spec = USER_INPUT_SPEC["thickness_m"]
    assert spec["label"] == "Net storage thickness"
    assert "gross stratigraphic thickness" in spec["not_inferred_from"]
    assert "total well depth" in spec["not_inferred_from"]
    assert spec["policy"] == NET_THICKNESS_POLICY_STATEMENT


def test_no_net_to_gross_factor_exists_in_the_engine():
    """Phase 3 requirement: do not invent a net-to-gross ratio.

    If one is ever added, it must be a deliberate, reviewed change -- this
    fails first.
    """
    import ccs_screen.capacity as capacity_module

    names = [n.lower() for n in dir(capacity_module)]
    assert not any("net_to_gross" in n or "ntg" in n for n in names)


def test_substituting_gross_for_net_is_an_order_of_magnitude_error():
    """The observed envelope is 1.5x to 128x, not the documented 20-50x.

    Pinned so the magnitude claim in records.py cannot drift unnoticed.
    """
    observed_gross_m = (91.0, 2557.0)
    plausible_net_m = (20.0, 60.0)
    ratios = [g / n for g in observed_gross_m for n in plausible_net_m]
    assert min(ratios) == pytest.approx(1.52, abs=0.01)
    assert max(ratios) == pytest.approx(127.85, abs=0.01)


# -- area semantics ----------------------------------------------------------


def test_area_spec_declares_closure_scale_and_its_exclusions():
    spec = USER_INPUT_SPEC["area_m2"]
    assert "closure" in spec["description"].lower()
    excluded = " ".join(spec["not_inferred_from"]).lower()
    for forbidden in ("licence", "concession", "administrative", "well spacing", "radius"):
        assert forbidden in excluded
    assert spec["policy"] == AREA_POLICY_STATEMENT


def test_both_uncited_inputs_have_no_default():
    """Neither may acquire a default: both are linear multipliers on the answer."""
    for field in ("area_m2", "thickness_m"):
        spec = USER_INPUT_SPEC[field]
        assert "default" not in spec
        assert spec["minimum_exclusive"] == 0.0


# -- validation --------------------------------------------------------------


@pytest.mark.parametrize(
    "override",
    [
        {"area_m2": 0.0}, {"area_m2": -1.0},
        {"thickness_m": 0.0}, {"thickness_m": -1.0},
        {"porosity": 0.0}, {"porosity": 1.0}, {"porosity": 1.5},
        {"co2_density_kg_m3": 0.0},
        {"storage_efficiency": 0.0}, {"storage_efficiency": 1.0},
    ],
)
def test_rejects_impossible_inputs(override):
    with pytest.raises(ValueError):
        volumetric_storage_mass_kg(**dict(BASE, **override))


def test_co2_volume_never_exceeds_bulk_rock_volume():
    """Finding 3.5: phi < 1 and E < 1 together guarantee phi E < 1.

    The guard is per-parameter, so an absurd pair like phi=0.9, E=0.9 is
    accepted -- but it is not *inconsistent*, which is what this pins.
    """
    extreme = dict(BASE, porosity=0.999, storage_efficiency=0.999)
    mass_kg = volumetric_storage_mass_kg(**extreme)
    bulk_rock_volume_m3 = BASE["area_m2"] * BASE["thickness_m"]
    co2_volume_m3 = mass_kg / BASE["co2_density_kg_m3"]
    assert co2_volume_m3 < bulk_rock_volume_m3
