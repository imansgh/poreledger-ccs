"""Phase 7 audit regression tests for Monte Carlo uncertainty propagation.

The machinery passed cleanly, so the mechanical tests here are guards rather
than discoveries: the generator, the marginals, the percentile arithmetic and
the 1/sqrt(N) convergence are all pinned so a change to any of them is
deliberate.

The tests that carry the phase are the interpretive ones. Only three of six
priors vary in the real-data path, pressure contributes nothing to the band,
and the two largest multipliers in the model enter as constants -- so the
reported P10-P90 is a sensitivity to two literature ranges, not a statement
about how uncertain a site is.

Statistical tests are seeded and their thresholds are set well outside the
measured values, so they do not flake.

See ``docs/scientific-validation-audit.md``, Phase 7.
"""

from __future__ import annotations

import math
import statistics

import numpy as np
import pytest

from ccs_screen.monte_carlo import (
    DEPLETED_GAS_ANALOG,
    KG_PER_MT,
    UniformPriors,
    run_capacity_mc,
)

PRIOR_NAMES = [
    "area_m2", "thickness_m", "porosity",
    "pressure_pa", "temperature_k", "storage_efficiency",
]

#: The shape resolve_inputs() actually produces for a pilot well: user-supplied
#: area and thickness, a single temperature observation, and three ranges.
REAL_PATH_PRIORS = UniformPriors(
    area_m2=(8e7, 8e7),
    thickness_m=(35.0, 35.0),
    porosity=(0.10, 0.35),
    pressure_pa=(15_279_251.03, 16_477_623.66),
    temperature_k=(318.15, 318.15),
    storage_efficiency=(0.01, 0.04),
)


def draws(priors, name, n, seed):
    return np.array([getattr(s, name) for s in priors.sample(n, seed=seed)])


# -- generator and reproducibility -------------------------------------------


def test_generator_is_pcg64():
    assert type(np.random.default_rng(0).bit_generator).__name__ == "PCG64"


def test_same_seed_reproduces_exactly():
    assert DEPLETED_GAS_ANALOG.sample(500, seed=42) == DEPLETED_GAS_ANALOG.sample(500, seed=42)


def test_different_seeds_differ():
    assert DEPLETED_GAS_ANALOG.sample(500, seed=42) != DEPLETED_GAS_ANALOG.sample(500, seed=43)


def test_smaller_n_is_not_a_prefix_of_larger_n():
    """Each N is an independent experiment, not a nested one.

    Pinned because it is the reason convergence must be measured with repeated
    independent runs rather than one growing sample.
    """
    small = DEPLETED_GAS_ANALOG.sample(100, seed=42)
    large = DEPLETED_GAS_ANALOG.sample(1000, seed=42)
    assert small != large[:100]


def test_public_entry_points_default_to_a_fixed_seed():
    """Every published result must be reproducible."""
    import inspect

    from ccs_screen.api import screen_well

    assert inspect.signature(screen_well).parameters["seed"].default == 42


# -- marginals ---------------------------------------------------------------


@pytest.mark.parametrize("name", PRIOR_NAMES)
def test_draws_respect_their_bounds(name):
    low, high = getattr(DEPLETED_GAS_ANALOG, name)
    x = draws(DEPLETED_GAS_ANALOG, name, 20_000, seed=7)
    assert x.min() >= low
    assert x.max() <= high


@pytest.mark.parametrize("name", PRIOR_NAMES)
def test_draws_are_uniform_by_kolmogorov_smirnov(name):
    """Audit measured KS <= 0.00203 at N=200k against a 0.00304 critical value."""
    n = 20_000
    low, high = getattr(DEPLETED_GAS_ANALOG, name)
    x = np.sort(draws(DEPLETED_GAS_ANALOG, name, n, seed=7))
    scaled = (x - low) / (high - low)
    ks = np.max(np.abs(scaled - np.arange(1, n + 1) / n))
    assert ks < 1.63 / math.sqrt(n), f"KS {ks:.5f} exceeds the 99% critical value"


@pytest.mark.parametrize("name", PRIOR_NAMES)
def test_draw_moments_match_the_uniform(name):
    low, high = getattr(DEPLETED_GAS_ANALOG, name)
    x = draws(DEPLETED_GAS_ANALOG, name, 50_000, seed=7)
    assert x.mean() == pytest.approx((low + high) / 2, rel=0.01)
    assert x.var() == pytest.approx((high - low) ** 2 / 12, rel=0.05)


def test_the_six_streams_are_mutually_independent():
    """Audit measured max |off-diagonal r| = 0.00536 at N=200k."""
    samples = DEPLETED_GAS_ANALOG.sample(50_000, seed=7)
    matrix = np.array([[getattr(s, n) for n in PRIOR_NAMES] for s in samples])
    correlations = np.corrcoef(matrix.T)
    off_diagonal = [
        abs(correlations[i, j])
        for i in range(len(PRIOR_NAMES))
        for j in range(len(PRIOR_NAMES))
        if i != j
    ]
    assert max(off_diagonal) < 0.05


# -- percentiles -------------------------------------------------------------


def test_percentiles_are_ordered_low_to_high():
    """Statistical convention: p10 is the LOW case, not the petroleum P10."""
    result = run_capacity_mc(DEPLETED_GAS_ANALOG.sample(5_000, seed=5))
    assert result.p10_mt < result.p50_mt < result.p90_mt


def test_percentile_matches_a_hand_computed_linear_interpolation():
    result = run_capacity_mc(DEPLETED_GAS_ANALOG.sample(5_000, seed=5))
    ordered = np.sort(result.masses_mt)
    for q in (10, 50, 90):
        position = (len(ordered) - 1) * q / 100
        low_index, high_index = math.floor(position), math.ceil(position)
        manual = ordered[low_index] + (position - low_index) * (
            ordered[high_index] - ordered[low_index]
        )
        assert result.percentile(q) == pytest.approx(manual, abs=1e-9)


def test_mean_exceeds_median_because_a_product_is_right_skewed():
    """Audit measured +16.37% and skewness +1.35. Both mean and p50 are reported."""
    result = run_capacity_mc(DEPLETED_GAS_ANALOG.sample(20_000, seed=5))
    assert result.mean_mt > result.p50_mt
    masses = result.masses_mt
    skewness = float(((masses - masses.mean()) ** 3).mean() / masses.std() ** 3)
    assert skewness > 0.5, "capacity should stay right-skewed"


@pytest.mark.parametrize("q", [-1, 101, 150])
def test_percentile_rejects_values_outside_zero_to_hundred(q):
    result = run_capacity_mc(DEPLETED_GAS_ANALOG.sample(50, seed=1))
    with pytest.raises(ValueError):
        result.percentile(q)


# -- convergence -------------------------------------------------------------


@pytest.mark.parametrize("n,max_range", [(500, 0.20), (2000, 0.10), (10000, 0.05)])
def test_run_to_run_spread_shrinks_with_sample_count(n, max_range):
    """Audit measured 11.3% / 4.4% / 2.4% at these N. Bounds are generous."""
    p50s = [run_capacity_mc(DEPLETED_GAS_ANALOG.sample(n, seed=s)).p50_mt for s in range(5)]
    assert (max(p50s) - min(p50s)) / statistics.mean(p50s) < max_range


def test_the_estimator_is_unbiased_at_small_n():
    """Small N costs precision, not accuracy -- the bias column was noise."""
    reference = statistics.mean(
        run_capacity_mc(DEPLETED_GAS_ANALOG.sample(20_000, seed=s)).p50_mt for s in range(3)
    )
    small = statistics.mean(
        run_capacity_mc(DEPLETED_GAS_ANALOG.sample(200, seed=s)).p50_mt for s in range(12)
    )
    assert small == pytest.approx(reference, rel=0.10)


# -- Finding 7.1: what actually varies in the real path ----------------------


def test_only_three_of_six_priors_vary_in_the_real_data_path():
    """CHARACTERISATION, Finding 7.1.

    area_m2 and thickness_m are user-supplied points and temperature is a single
    observation, so the band cannot reflect uncertainty in any of them -- and
    Phase 3 measured area and thickness as the two largest multipliers, each
    with elasticity exactly +1.
    """
    varying = [n for n in PRIOR_NAMES if getattr(REAL_PATH_PRIORS, n)[0] < getattr(REAL_PATH_PRIORS, n)[1]]
    assert sorted(varying) == ["porosity", "pressure_pa", "storage_efficiency"]
    for constant in ("area_m2", "thickness_m", "temperature_k"):
        low, high = getattr(REAL_PATH_PRIORS, constant)
        assert low == high


def test_pressure_contributes_almost_nothing_to_the_band():
    """CHARACTERISATION, Finding 7.1: collapsing pressure left the band at 100.0%.

    The pressure range comes from the brine-density assumption, which moves CO2
    density very little at this state point. The band is porosity and storage
    efficiency.
    """
    full = run_capacity_mc(REAL_PATH_PRIORS.sample(20_000, seed=42))
    full_band = full.p90_mt - full.p10_mt

    low, high = REAL_PATH_PRIORS.pressure_pa
    midpoint = (low + high) / 2
    collapsed = UniformPriors(
        **{**{n: getattr(REAL_PATH_PRIORS, n) for n in PRIOR_NAMES},
           "pressure_pa": (midpoint, midpoint)}
    )
    without_pressure = run_capacity_mc(collapsed.sample(20_000, seed=42))
    band_without = without_pressure.p90_mt - without_pressure.p10_mt

    assert band_without / full_band > 0.95


@pytest.mark.parametrize("name", ["porosity", "storage_efficiency"])
def test_the_two_literature_ranges_drive_the_band(name):
    """Collapsing either one shrinks the band materially; audit: 74% and 69%."""
    full = run_capacity_mc(REAL_PATH_PRIORS.sample(20_000, seed=42))
    full_band = full.p90_mt - full.p10_mt

    low, high = getattr(REAL_PATH_PRIORS, name)
    midpoint = (low + high) / 2
    collapsed = UniformPriors(
        **{**{n: getattr(REAL_PATH_PRIORS, n) for n in PRIOR_NAMES}, name: (midpoint, midpoint)}
    )
    reduced = run_capacity_mc(collapsed.sample(20_000, seed=42))
    assert (reduced.p90_mt - reduced.p10_mt) / full_band < 0.85


def test_the_real_path_band_is_wide_relative_to_its_median():
    """Audit measured 142% of P50 at N=50000."""
    result = run_capacity_mc(REAL_PATH_PRIORS.sample(20_000, seed=42))
    assert (result.p90_mt - result.p10_mt) / result.p50_mt > 1.0


# -- Finding 7.3: physical dependence of P and T -----------------------------


def test_the_demo_prior_admits_physically_unreachable_pressure_temperature_pairs():
    """CHARACTERISATION, Finding 7.3. CLI demo only -- the real path has T as a point.

    Both P and T are depth-driven, so the corners of the prior rectangle
    correspond to no depth at all.
    """
    gradient_pa_m = 1050.0 * 9.80665
    surface_k, gradient_k_m = 288.15, 0.030

    low_p, high_p = DEPLETED_GAS_ANALOG.pressure_pa
    low_t, high_t = DEPLETED_GAS_ANALOG.temperature_k

    t_at_low_p = surface_k + gradient_k_m * (low_p / gradient_pa_m)
    t_at_high_p = surface_k + gradient_k_m * (high_p / gradient_pa_m)

    assert high_t - t_at_low_p == pytest.approx(31.9, abs=1.0)
    assert low_t - t_at_high_p == pytest.approx(-26.4, abs=1.0)


def test_real_path_is_immune_because_temperature_is_a_point():
    low, high = REAL_PATH_PRIORS.temperature_k
    assert low == high, "Finding 7.3 would apply if temperature became a range"


# -- Finding 7.4 and validation ----------------------------------------------


def test_single_sample_gives_three_identical_percentiles():
    """CHARACTERISATION, Finding 7.4: MIN_SAMPLES = 1 is accepted, unwarned."""
    from ccs_screen.api import MIN_SAMPLES

    assert MIN_SAMPLES == 1
    result = run_capacity_mc(DEPLETED_GAS_ANALOG.sample(1, seed=1))
    assert result.p10_mt == result.p50_mt == result.p90_mt


def test_degenerate_priors_collapse_the_distribution_exactly():
    result = run_capacity_mc(REAL_PATH_PRIORS.sample(50, seed=1))
    assert result.p90_mt > result.p10_mt  # the real path is not degenerate
    fully_fixed = UniformPriors(
        area_m2=(8e7, 8e7), thickness_m=(35.0, 35.0), porosity=(0.18, 0.18),
        pressure_pa=(1.6e7, 1.6e7), temperature_k=(333.15, 333.15),
        storage_efficiency=(0.025, 0.025),
    )
    collapsed = run_capacity_mc(fully_fixed.sample(50, seed=1))
    assert collapsed.p90_mt - collapsed.p10_mt == 0.0


@pytest.mark.parametrize("n", [0, -5])
def test_sample_rejects_non_positive_counts(n):
    with pytest.raises(ValueError):
        DEPLETED_GAS_ANALOG.sample(n)


@pytest.mark.parametrize(
    "override", [{"porosity": (0.0, 0.2)}, {"porosity": (0.3, 0.1)}, {"area_m2": (-1.0, 5.0)}]
)
def test_priors_reject_impossible_ranges(override):
    with pytest.raises(ValueError):
        UniformPriors(**{**{n: getattr(DEPLETED_GAS_ANALOG, n) for n in PRIOR_NAMES}, **override})


def test_impossible_porosity_prior_is_caught_downstream_not_at_construction():
    """Finding: the '< 1' bound is checked one layer later than the others."""
    priors = UniformPriors(
        **{**{n: getattr(DEPLETED_GAS_ANALOG, n) for n in PRIOR_NAMES}, "porosity": (0.5, 1.5)}
    )
    with pytest.raises(ValueError, match="must be < 1"):
        run_capacity_mc(priors.sample(200, seed=1))


def test_empty_sample_list_is_rejected():
    with pytest.raises(ValueError):
        run_capacity_mc([])


def test_megatonne_conversion_is_applied_once():
    from ccs_screen.capacity import volumetric_storage_mass_kg
    from ccs_screen.monte_carlo import sample_mass_mt
    from ccs_screen.properties import co2_density_kg_m3

    sample = DEPLETED_GAS_ANALOG.sample(1, seed=3)[0]
    expected_kg = volumetric_storage_mass_kg(
        area_m2=sample.area_m2, thickness_m=sample.thickness_m, porosity=sample.porosity,
        co2_density_kg_m3=co2_density_kg_m3(sample.pressure_pa, sample.temperature_k),
        storage_efficiency=sample.storage_efficiency,
    )
    assert sample_mass_mt(sample) == pytest.approx(expected_kg / KG_PER_MT, rel=1e-15)
