import numpy as np
import pytest

from ccs_screen.monte_carlo import (
    DEPLETED_GAS_ANALOG,
    CapacitySample,
    UniformPriors,
    run_capacity_mc,
    sample_mass_mt,
)


def test_sampling_is_reproducible_for_a_fixed_seed():
    a = DEPLETED_GAS_ANALOG.sample(50, seed=7)
    b = DEPLETED_GAS_ANALOG.sample(50, seed=7)
    assert a == b
    assert DEPLETED_GAS_ANALOG.sample(50, seed=8) != a


def test_samples_respect_the_prior_bounds():
    samples = DEPLETED_GAS_ANALOG.sample(300, seed=1)
    assert len(samples) == 300
    for s in samples:
        assert 50e6 <= s.area_m2 <= 150e6
        assert 25.0 <= s.thickness_m <= 55.0
        assert 0.12 <= s.porosity <= 0.24
        assert 12e6 <= s.pressure_pa <= 20e6
        assert 320.0 <= s.temperature_k <= 355.0
        assert 0.02 <= s.storage_efficiency <= 0.07


def test_degenerate_prior_produces_a_constant():
    priors = UniformPriors(
        area_m2=(1e8, 1e8),
        thickness_m=(40.0, 40.0),
        porosity=(0.18, 0.18),
        pressure_pa=(15e6, 15e6),
        temperature_k=(333.15, 333.15),
        storage_efficiency=(0.04, 0.04),
    )
    samples = priors.sample(5, seed=0)
    assert len({s.area_m2 for s in samples}) == 1


@pytest.mark.parametrize("bad", [{"porosity": (-0.1, 0.2)}, {"thickness_m": (60.0, 20.0)}, {"area_m2": (0.0, 1e8)}])
def test_rejects_invalid_prior_ranges(bad):
    base = dict(
        area_m2=(50e6, 150e6),
        thickness_m=(25.0, 55.0),
        porosity=(0.12, 0.24),
        pressure_pa=(12e6, 20e6),
        temperature_k=(320.0, 355.0),
        storage_efficiency=(0.02, 0.07),
    )
    with pytest.raises(ValueError):
        UniformPriors(**{**base, **bad})


def test_sample_count_must_be_positive():
    with pytest.raises(ValueError):
        DEPLETED_GAS_ANALOG.sample(0)


def test_mc_result_percentiles_agree_with_the_stored_fields():
    result = run_capacity_mc(DEPLETED_GAS_ANALOG.sample(500, seed=3))
    assert result.percentile(10) == pytest.approx(result.p10_mt)
    assert result.percentile(50) == pytest.approx(result.p50_mt)
    assert result.percentile(90) == pytest.approx(result.p90_mt)
    assert result.p10_mt < result.mean_mt < result.p90_mt
    with pytest.raises(ValueError):
        result.percentile(101)


def test_single_sample_mass_matches_the_vectorised_run():
    sample = CapacitySample(
        area_m2=1e8,
        thickness_m=40.0,
        porosity=0.18,
        pressure_pa=15e6,
        temperature_k=333.15,
        storage_efficiency=0.04,
    )
    result = run_capacity_mc([sample])
    assert result.n == 1
    assert result.masses_mt[0] == pytest.approx(sample_mass_mt(sample))


def test_empty_sample_list_is_rejected():
    with pytest.raises(ValueError):
        run_capacity_mc([])
