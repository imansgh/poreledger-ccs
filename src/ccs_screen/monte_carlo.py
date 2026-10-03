"""Monte Carlo propagation of screening capacity uncertainty.

Percentile convention: ``p10_mt`` is the 10th percentile, i.e. the *low* case.
This is the statistical convention, not the petroleum P10/P90 convention where
P10 is the high case. Read ``p10 < p50 < p90`` literally.

``run_capacity_mc`` takes percentiles over every sample it is given and drops
none. The approved model (``ccs_screen.approved_model``) checks the validated
EOS envelope on those same realisations and blocks validated percentiles when
any lies outside it (Model Contract M4); it never removes a draw.
``DEPLETED_GAS_ANALOG`` feeds only the NOT_VALIDATED CLI demo (O1).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields

import numpy as np

from ccs_screen.capacity import volumetric_storage_mass_kg
from ccs_screen.properties import co2_density_kg_m3

KG_PER_MT = 1e9  # 1 Mt = 1e9 kg


@dataclass(frozen=True)
class CapacitySample:
    area_m2: float
    thickness_m: float
    porosity: float
    pressure_pa: float
    temperature_k: float
    storage_efficiency: float


@dataclass(frozen=True)
class UniformPriors:
    """Independent uniform (low, high) ranges for each screening input."""

    area_m2: tuple[float, float]
    thickness_m: tuple[float, float]
    porosity: tuple[float, float]
    pressure_pa: tuple[float, float]
    temperature_k: tuple[float, float]
    storage_efficiency: tuple[float, float]

    def __post_init__(self) -> None:
        for field in fields(self):
            low, high = getattr(self, field.name)
            if not (math.isfinite(low) and math.isfinite(high)):
                raise ValueError(f"{field.name} bounds must be finite")
            if low <= 0:
                raise ValueError(f"{field.name} lower bound must be positive")
            if high < low:
                raise ValueError(f"{field.name} upper bound must be >= lower bound")

    def sample(self, n: int, seed: int | None = None) -> list[CapacitySample]:
        """Draw ``n`` independent samples from the priors."""
        if n <= 0:
            raise ValueError("n must be positive")
        rng = np.random.default_rng(seed)
        names = [field.name for field in fields(self)]
        draws = {name: rng.uniform(*getattr(self, name), size=n) for name in names}
        return [CapacitySample(**{name: float(draws[name][i]) for name in names}) for i in range(n)]


#: Synthetic depleted-gas analog used by the demo. Not a real site.
DEPLETED_GAS_ANALOG = UniformPriors(
    area_m2=(50e6, 150e6),
    thickness_m=(25.0, 55.0),
    porosity=(0.12, 0.24),
    pressure_pa=(12e6, 20e6),
    temperature_k=(320.0, 355.0),
    storage_efficiency=(0.02, 0.07),
)


@dataclass(frozen=True)
class McResult:
    masses_mt: np.ndarray
    p10_mt: float
    p50_mt: float
    p90_mt: float
    n: int

    @property
    def mean_mt(self) -> float:
        return float(np.mean(self.masses_mt))

    def percentile(self, q: float) -> float:
        """Capacity in Mt at percentile ``q`` (0-100)."""
        if not 0 <= q <= 100:
            raise ValueError("percentile must be in [0, 100]")
        return float(np.percentile(self.masses_mt, q))


def sample_mass_mt(sample: CapacitySample) -> float:
    """Storage mass in Mt for a single realisation."""
    return (
        volumetric_storage_mass_kg(
            area_m2=sample.area_m2,
            thickness_m=sample.thickness_m,
            porosity=sample.porosity,
            co2_density_kg_m3=co2_density_kg_m3(sample.pressure_pa, sample.temperature_k),
            storage_efficiency=sample.storage_efficiency,
        )
        / KG_PER_MT
    )


def run_capacity_mc(samples: list[CapacitySample]) -> McResult:
    if not samples:
        raise ValueError("need at least one sample")
    masses = np.array([sample_mass_mt(s) for s in samples], dtype=float)
    p10, p50, p90 = np.percentile(masses, [10, 50, 90])
    return McResult(masses_mt=masses, p10_mt=float(p10), p50_mt=float(p50), p90_mt=float(p90), n=len(samples))
