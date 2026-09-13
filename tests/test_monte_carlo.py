import numpy as np

from ccs_screen.monte_carlo import CapacitySample, run_capacity_mc
from ccs_screen.surrogate import fit_linear_surrogate, predict


def test_monte_carlo_returns_p10_p50_p90_in_order():
    rng = np.random.default_rng(0)
    samples = [
        CapacitySample(
            area_m2=rng.uniform(8e7, 1.2e8),
            thickness_m=rng.uniform(30, 50),
            porosity=rng.uniform(0.12, 0.22),
            pressure_pa=rng.uniform(12e6, 18e6),
            temperature_k=rng.uniform(320, 350),
            storage_efficiency=rng.uniform(0.02, 0.06),
        )
        for _ in range(400)
    ]
    result = run_capacity_mc(samples)
    assert result.p10_mt < result.p50_mt < result.p90_mt
    assert result.n == 400


def test_surrogate_fits_monotonic_area_effect():
    rng = np.random.default_rng(1)
    samples = [
        CapacitySample(
            area_m2=a,
            thickness_m=40.0,
            porosity=0.18,
            pressure_pa=15e6,
            temperature_k=333.15,
            storage_efficiency=0.04,
        )
        for a in rng.uniform(5e7, 1.5e8, size=80)
    ]
    result = run_capacity_mc(samples)
    model = fit_linear_surrogate(samples, result.masses_mt)
    x_small = np.array([[6e7, 40, 0.18, 15e6, 333.15, 0.04]])
    x_large = np.array([[1.4e8, 40, 0.18, 15e6, 333.15, 0.04]])
    assert predict(model, x_large)[0] > predict(model, x_small)[0]
