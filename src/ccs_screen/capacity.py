"""CSLF-style volumetric screening mass: M = A h φ ρ E.

On the approved model (Phase 13 Model Contract, A1 and M1) the thickness
argument is ``h_g = z_base - z_top``, the gross thickness of the caller-designated
storage-assessment interval, and the density is evaluated at the absolute EOS
pressure and the selected temperature (``ccs_screen.approved_model``). The
NOT_VALIDATED legacy paths pass their own ``thickness_m``. The arithmetic is the
same for both.
"""

from __future__ import annotations


def volumetric_storage_mass_kg(
    area_m2: float,
    thickness_m: float,
    porosity: float,
    co2_density_kg_m3: float,
    storage_efficiency: float,
) -> float:
    for name, value in {
        "area_m2": area_m2,
        "thickness_m": thickness_m,
        "porosity": porosity,
        "co2_density_kg_m3": co2_density_kg_m3,
        "storage_efficiency": storage_efficiency,
    }.items():
        if value <= 0:
            raise ValueError(f"{name} must be positive")
    if porosity >= 1 or storage_efficiency >= 1:
        raise ValueError("porosity and storage efficiency must be < 1")
    return area_m2 * thickness_m * porosity * co2_density_kg_m3 * storage_efficiency
