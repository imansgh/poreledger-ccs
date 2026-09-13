from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(ROOT))

from ccs_screen.monte_carlo import CapacitySample, run_capacity_mc
from ccs_screen.pressure import theis_injection_delta_p_pa
from ccs_screen.properties import co2_density_kg_m3
from ccs_screen.surrogate import fit_linear_surrogate, predict


def main() -> None:
    rng = np.random.default_rng(42)
    n = 800
    samples = [
        CapacitySample(
            area_m2=rng.uniform(50e6, 150e6),
            thickness_m=rng.uniform(25, 55),
            porosity=rng.uniform(0.12, 0.24),
            pressure_pa=rng.uniform(12e6, 20e6),
            temperature_k=rng.uniform(320, 355),
            storage_efficiency=rng.uniform(0.02, 0.07),
        )
        for _ in range(n)
    ]
    result = run_capacity_mc(samples)
    model = fit_linear_surrogate(samples, result.masses_mt)
    pred = predict(
        model,
        np.array(
            [
                [
                    s.area_m2,
                    s.thickness_m,
                    s.porosity,
                    s.pressure_pa,
                    s.temperature_k,
                    s.storage_efficiency,
                ]
                for s in samples
            ]
        ),
    )
    rmse = float(np.sqrt(np.mean((pred - result.masses_mt) ** 2)))

    rho = co2_density_kg_m3(15e6, 333.15)
    dp = theis_injection_delta_p_pa(
        rate_m3_s=0.08,
        permeability_m2=8e-14,
        thickness_m=40.0,
        viscosity_pa_s=4.5e-4,
        time_s=10 * 365 * 24 * 3600,
        radius_m=500.0,
        porosity=0.18,
        compressibility_1_pa=1.2e-9,
    )

    print("CCS screening demo (synthetic depleted-gas analog - not a site model)")
    print(f"  CO2 density @ 15 MPa, 60 C : {rho:.0f} kg/m3")
    print(f"  Capacity P10 / P50 / P90   : {result.p10_mt:.1f} / {result.p50_mt:.1f} / {result.p90_mt:.1f} Mt")
    print(f"  Linear surrogate RMSE      : {rmse:.2f} Mt")
    print(f"  Theis dP @ 500 m, 10 yr    : {dp/1e6:.2f} MPa  (brine analog, screening only)")


if __name__ == "__main__":
    main()
