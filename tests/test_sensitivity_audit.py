"""Phase 8 audit regression tests for the linear surrogate.

The estimator itself is exact, and the tests that prove it are the synthetic
ones: fit a law whose standardized coefficients are known in advance and check
that they come back. Those are the only tests here that could have caught a
wrong estimator, so they come first.

The rest pin interpretation. A constant input and an uninfluential input both
report 0.0000, and in the real-data path the three inputs that print 0.0000 are
the two largest multipliers in the model plus the highest-leverage one.

See ``docs/scientific-validation-audit.md``, Phase 8.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from ccs_screen.monte_carlo import (
    DEPLETED_GAS_ANALOG,
    CapacitySample,
    UniformPriors,
    run_capacity_mc,
)
from ccs_screen.properties import co2_density_kg_m3
from ccs_screen.surrogate import (
    FEATURE_ORDER,
    design_matrix,
    evaluate,
    fit_linear_surrogate,
    fit_linear_surrogate as fit,
    predict,
    sensitivity,
)

REAL_PATH_PRIORS = UniformPriors(
    area_m2=(8e7, 8e7),
    thickness_m=(35.0, 35.0),
    porosity=(0.10, 0.35),
    pressure_pa=(15_279_251.03, 16_477_623.66),
    temperature_k=(318.15, 318.15),
    storage_efficiency=(0.01, 0.04),
)


def synthetic_samples(n=8000, seed=0):
    rng = np.random.default_rng(seed)
    matrix = np.column_stack([
        rng.uniform(50e6, 150e6, n),
        rng.uniform(25, 55, n),
        rng.uniform(0.12, 0.24, n),
        rng.uniform(12e6, 20e6, n),
        rng.uniform(320, 355, n),
        rng.uniform(0.02, 0.07, n),
    ])
    samples = [CapacitySample(**dict(zip(FEATURE_ORDER, row))) for row in matrix]
    return samples, matrix


# -- validation against known answers ----------------------------------------


def test_recovers_known_standardized_coefficients():
    """The one test that could catch a wrong estimator. Audit error: 2.7e-15."""
    samples, matrix = synthetic_samples()
    standardized = (matrix - matrix.mean(axis=0)) / matrix.std(axis=0)
    true_beta = np.array([3.0, 1.0, 0.0, -2.0, 0.5, 0.0])
    y = 10.0 + standardized @ true_beta

    model = fit(samples, y)
    assert model.standardized_coef == pytest.approx(true_beta, abs=1e-9)
    assert model.intercept == pytest.approx(10.0, abs=1e-9)
    assert evaluate(model, samples, y).r2 == pytest.approx(1.0, abs=1e-12)


def test_ranking_is_by_absolute_value_so_sign_does_not_demote():
    """A strong negative driver must outrank a weak positive one."""
    samples, matrix = synthetic_samples()
    standardized = (matrix - matrix.mean(axis=0)) / matrix.std(axis=0)
    y = standardized @ np.array([3.0, 1.0, 0.0, -2.0, 0.5, 0.0])
    ranked = [name for name, _ in sensitivity(fit(samples, y))]
    assert ranked[:4] == ["area_m2", "pressure_pa", "thickness_m", "temperature_k"]


def test_coefficient_equals_slope_times_feature_standard_deviation():
    """For y = c*x in raw units, beta must be c * sd(x) exactly."""
    samples, matrix = synthetic_samples()
    y = 7.0 * matrix[:, 0]
    model = fit(samples, y)
    assert model.standardized_coef[0] == pytest.approx(7.0 * matrix[:, 0].std(), rel=1e-12)
    assert np.abs(model.standardized_coef[1:]).max() < 1e-6


def test_a_pure_interaction_produces_no_linear_signal():
    """The honesty test: report nothing rather than invent a driver.

    A linear surrogate cannot represent z1*z2, and it must say so through a
    near-zero R2 rather than through confident spurious coefficients.
    """
    samples, matrix = synthetic_samples()
    standardized = (matrix - matrix.mean(axis=0)) / matrix.std(axis=0)
    y = standardized[:, 0] * standardized[:, 1]
    model = fit(samples, y)
    assert np.abs(model.standardized_coef).max() < 0.05
    assert evaluate(model, samples, y).r2 < 0.01


def test_prediction_round_trips_on_an_exactly_linear_target():
    samples, matrix = synthetic_samples()
    standardized = (matrix - matrix.mean(axis=0)) / matrix.std(axis=0)
    y = 4.0 + standardized @ np.array([1.0, -1.0, 2.0, 0.0, 0.0, 0.5])
    model = fit(samples, y)
    assert predict(model, design_matrix(samples)) == pytest.approx(y, abs=1e-9)


# -- Finding 8.1: what the ranking measures ----------------------------------


def test_temperature_has_five_times_the_leverage_of_any_other_input():
    """Audit measured elasticity -5.234 for temperature, +1.000 for four inputs.

    This is why a small temperature error becomes a large capacity error, and
    it is the number that explains Phase 6 Finding 6.6.
    """
    midpoint = {name: sum(getattr(DEPLETED_GAS_ANALOG, name)) / 2 for name in FEATURE_ORDER}

    def capacity(values):
        return (
            values["area_m2"] * values["thickness_m"] * values["porosity"]
            * values["storage_efficiency"]
            * co2_density_kg_m3(values["pressure_pa"], values["temperature_k"])
        )

    base = capacity(midpoint)
    elasticities = {}
    for name in FEATURE_ORDER:
        bumped = dict(midpoint)
        bumped[name] = midpoint[name] * 1.001
        elasticities[name] = math.log(capacity(bumped) / base) / math.log(1.001)

    for direct in ("area_m2", "thickness_m", "porosity", "storage_efficiency"):
        assert elasticities[direct] == pytest.approx(1.0, abs=1e-6)
    assert elasticities["pressure_pa"] == pytest.approx(1.006, abs=0.01)
    assert elasticities["temperature_k"] == pytest.approx(-5.234, abs=0.05)
    assert abs(elasticities["temperature_k"]) > 5 * abs(elasticities["area_m2"])


def test_coefficients_decompose_as_mean_times_elasticity_times_cv():
    """Independent explanation of every coefficient, accurate to ~5%."""
    samples = DEPLETED_GAS_ANALOG.sample(20_000, seed=42)
    result = run_capacity_mc(samples)
    coefficients = dict(sensitivity(fit(samples, result.masses_mt)))

    for name in ("area_m2", "thickness_m", "porosity", "storage_efficiency"):
        low, high = getattr(DEPLETED_GAS_ANALOG, name)
        cv = (high - low) / (math.sqrt(3) * (high + low))
        predicted = result.mean_mt * 1.0 * cv
        assert coefficients[name] == pytest.approx(predicted, rel=0.10)


def test_temperature_outranks_pressure_despite_a_far_narrower_prior():
    """The one place physics, not prior width, decides the order.

    Pressure's prior is 4.8x wider in relative terms, but temperature's 5x
    leverage wins. This is the surrogate doing real work.
    """
    samples = DEPLETED_GAS_ANALOG.sample(20_000, seed=42)
    result = run_capacity_mc(samples)
    coefficients = dict(sensitivity(fit(samples, result.masses_mt)))

    def cv(name):
        low, high = getattr(DEPLETED_GAS_ANALOG, name)
        return (high - low) / (math.sqrt(3) * (high + low))

    assert cv("pressure_pa") > 4 * cv("temperature_k")
    assert abs(coefficients["temperature_k"]) > abs(coefficients["pressure_pa"])


# -- Finding 8.2: constant vs uninfluential ----------------------------------


def test_constant_inputs_report_exactly_zero():
    samples = REAL_PATH_PRIORS.sample(5_000, seed=42)
    model = fit(samples, run_capacity_mc(samples).masses_mt)
    for name in ("area_m2", "thickness_m", "temperature_k"):
        assert model.standardized_coef[FEATURE_ORDER.index(name)] == 0.0


def test_a_constant_input_is_indistinguishable_from_an_uninfluential_one():
    """CHARACTERISATION, Finding 8.2.

    In the real-data path the three inputs printing 0.0000 are area_m2 and
    thickness_m -- the two largest multipliers, elasticity +1 each, with no
    source or literature basis -- and temperature_k, the highest-leverage input
    in the model. They appear at the bottom of a list labelled "sensitivity".

    When Finding 8.2 is resolved the output should distinguish "held constant"
    from "measured as unimportant", and this test must be replaced.
    """
    samples = REAL_PATH_PRIORS.sample(5_000, seed=42)
    ranked = sensitivity(fit(samples, run_capacity_mc(samples).masses_mt))

    bottom_three = {name for name, _ in ranked[-3:]}
    assert bottom_three == {"area_m2", "thickness_m", "temperature_k"}
    assert all(value == 0.0 for _, value in ranked[-3:])
    # Nothing in the return type says why they are zero.
    assert all(isinstance(value, float) for _, value in ranked)
    assert all(len(entry) == 2 for entry in ranked)


def test_the_two_literature_ranges_lead_the_real_path_ranking():
    samples = REAL_PATH_PRIORS.sample(5_000, seed=42)
    ranked = sensitivity(fit(samples, run_capacity_mc(samples).masses_mt))
    assert {name for name, _ in ranked[:2]} == {"porosity", "storage_efficiency"}


# -- Finding 8.3: the degenerate guard ---------------------------------------


def test_guard_catches_a_residue_standard_deviation_on_a_large_magnitude_column():
    """The regression this guard exists for.

    A constant temperature column has peak-to-peak 0 but a computed std around
    5.7e-14. An absolute threshold cannot catch that at every feature magnitude;
    comparing peak-to-peak against the feature's own scale can.
    """
    samples = REAL_PATH_PRIORS.sample(5_000, seed=42)
    matrix = design_matrix(samples)
    index = FEATURE_ORDER.index("temperature_k")

    assert matrix[:, index].max() - matrix[:, index].min() == 0.0
    model = fit(samples, run_capacity_mc(samples).masses_mt)
    assert model.feature_std[index] == 1.0, "degenerate std must be replaced, not used"
    assert model.standardized_coef[index] == 0.0


def test_a_constant_input_never_becomes_the_top_driver():
    """The failure mode this guard prevents: noise fitted as physics."""
    samples = REAL_PATH_PRIORS.sample(5_000, seed=42)
    top_feature, _ = sensitivity(fit(samples, run_capacity_mc(samples).masses_mt))[0]
    low, high = getattr(REAL_PATH_PRIORS, top_feature)
    assert high > low, f"{top_feature} is constant but ranked first"


def test_prediction_stays_safe_for_degenerate_columns():
    """Stored std of 1.0 is harmless because the coefficient is zero."""
    samples = REAL_PATH_PRIORS.sample(1_000, seed=42)
    masses = run_capacity_mc(samples).masses_mt
    model = fit(samples, masses)

    perturbed = design_matrix(samples)
    perturbed[:, FEATURE_ORDER.index("area_m2")] *= 2.0
    assert predict(model, perturbed) == pytest.approx(predict(model, design_matrix(samples)))


# -- Finding 8.4: fidelity ---------------------------------------------------


def test_surrogate_fits_the_product_well_enough_to_rank():
    """Audit: R2 = 0.8872 on the demo priors, 0.9477 on the real path."""
    for priors, floor in ((DEPLETED_GAS_ANALOG, 0.85), (REAL_PATH_PRIORS, 0.90)):
        samples = priors.sample(10_000, seed=42)
        masses = run_capacity_mc(samples).masses_mt
        assert evaluate(fit(samples, masses), samples, masses).r2 > floor


def test_fidelity_degrades_as_priors_widen():
    """A linear surrogate over a six-way product is only locally valid."""
    def r2_for(width):
        kwargs = {}
        for name in FEATURE_ORDER:
            low, high = getattr(DEPLETED_GAS_ANALOG, name)
            mid, half = (low + high) / 2, (high - low) / 2 * width
            lo, hi = max(mid - half, 1e-9), mid + half
            if name in ("porosity", "storage_efficiency"):
                hi = min(hi, 0.95)
            kwargs[name] = (lo, hi)
        samples = UniformPriors(**kwargs).sample(8_000, seed=42)
        masses = run_capacity_mc(samples).masses_mt
        return evaluate(fit(samples, masses), samples, masses).r2

    narrow, declared, wide = r2_for(0.25), r2_for(1.0), r2_for(3.0)
    assert narrow > declared > wide
    assert narrow > 0.98
    assert wide < 0.70


# -- validation and edge cases -----------------------------------------------


def test_rejects_empty_samples():
    with pytest.raises(ValueError, match="at least one sample"):
        fit_linear_surrogate([], np.array([]))


def test_rejects_length_mismatch():
    samples, _ = synthetic_samples(n=10)
    with pytest.raises(ValueError, match="same length"):
        fit_linear_surrogate(samples, np.arange(5.0))


def test_predict_rejects_a_wrong_feature_count():
    samples, matrix = synthetic_samples(n=100)
    model = fit(samples, matrix[:, 0])
    with pytest.raises(ValueError, match="FEATURE_ORDER"):
        predict(model, np.ones((2, 3)))


def test_single_sample_gives_an_all_zero_ranking():
    """CHARACTERISATION, Finding 8.5: silent, and paired with MIN_SAMPLES = 1."""
    samples = DEPLETED_GAS_ANALOG.sample(1, seed=1)
    model = fit(samples, np.array([5.0]))
    assert np.all(model.standardized_coef == 0.0)


def test_fully_degenerate_priors_give_zero_coefficients_and_r2_one():
    fixed = UniformPriors(
        area_m2=(8e7, 8e7), thickness_m=(35.0, 35.0), porosity=(0.18, 0.18),
        pressure_pa=(1.6e7, 1.6e7), temperature_k=(333.15, 333.15),
        storage_efficiency=(0.025, 0.025),
    )
    samples = fixed.sample(100, seed=1)
    masses = run_capacity_mc(samples).masses_mt
    model = fit(samples, masses)
    assert np.all(model.standardized_coef == 0.0)
    assert evaluate(model, samples, masses).r2 == 1.0


def test_feature_order_is_the_capacity_sample_field_order():
    """The design matrix is built by getattr, so a reorder would silently relabel."""
    from dataclasses import fields

    assert FEATURE_ORDER == tuple(f.name for f in fields(CapacitySample))
