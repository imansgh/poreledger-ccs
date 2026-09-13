from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ccs_screen.capacity import volumetric_storage_mass_kg
from ccs_screen.properties import co2_density_kg_m3


@dataclass(frozen=True)
class CapacitySample:
    area_m2: float
    thickness_m: float
    porosity: float
    pressure_pa: float
    temperature_k: float
    storage_efficiency: float


@dataclass(frozen=True)
class McResult:
    masses_mt: np.ndarray
    p10_mt: float
    p50_mt: float
    p90_mt: float
    n: int


def run_capacity_mc(samples: list[CapacitySample]) -> McResult:
    if not samples:
        raise ValueError("need at least one sample")
    masses = np.array(
        [
            volumetric_storage_mass_kg(
                area_m2=s.area_m2,
                thickness_m=s.thickness_m,
                porosity=s.porosity,
                co2_density_kg_m3=co2_density_kg_m3(s.pressure_pa, s.temperature_k),
                storage_efficiency=s.storage_efficiency,
            )
            / 1e9
            for s in samples
        ],
        dtype=float,
    )
    p10, p50, p90 = np.percentile(masses, [10, 50, 90])
    return McResult(masses_mt=masses, p10_mt=float(p10), p50_mt=float(p50), p90_mt=float(p90), n=len(samples))
