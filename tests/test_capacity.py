import math

from ccs_screen.capacity import volumetric_storage_mass_kg
from ccs_screen.properties import co2_density_kg_m3


def test_co2_density_is_liquid_like_at_typical_storage_conditions():
    rho = co2_density_kg_m3(pressure_pa=15e6, temperature_k=333.15)
    assert 500 < rho < 900


def test_storage_mass_scales_with_area_and_porosity():
    kwargs = dict(
        thickness_m=40.0,
        porosity=0.2,
        co2_density_kg_m3=700.0,
        storage_efficiency=0.04,
    )
    m1 = volumetric_storage_mass_kg(area_m2=1e6, **kwargs)
    m2 = volumetric_storage_mass_kg(area_m2=2e6, **kwargs)
    assert math.isclose(m2, 2 * m1)
    m3 = volumetric_storage_mass_kg(area_m2=1e6, thickness_m=40.0, porosity=0.1, co2_density_kg_m3=700.0, storage_efficiency=0.04)
    assert math.isclose(m3, 0.5 * m1)


def test_storage_mass_rejects_non_physical_inputs():
    try:
        volumetric_storage_mass_kg(
            area_m2=0,
            thickness_m=40,
            porosity=0.2,
            co2_density_kg_m3=700,
            storage_efficiency=0.04,
        )
    except ValueError:
        return
    raise AssertionError("expected ValueError")
