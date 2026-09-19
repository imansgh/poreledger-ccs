import numpy as np
import pytest

from ccs_screen.monte_carlo import DEPLETED_GAS_ANALOG, run_capacity_mc
from ccs_screen.surrogate import (
    FEATURE_ORDER,
    design_matrix,
    evaluate,
    fit_linear_surrogate,
    predict,
    predict_samples,
    sensitivity,
)


@pytest.fixture(scope="module")
def fitted():
    samples = DEPLETED_GAS_ANALOG.sample(600, seed=11)
    result = run_capacity_mc(samples)
    model = fit_linear_surrogate(samples, result.masses_mt)
    return samples, result, model


def test_surrogate_explains_most_of_the_variance(fitted):
    samples, result, model = fitted
    metrics = evaluate(model, samples, result.masses_mt)
    assert metrics.r2 > 0.85
    assert metrics.rmse_mt > 0
    assert metrics.mae_mt <= metrics.rmse_mt


def test_sensitivity_is_ranked_and_covers_every_feature(fitted):
    _, _, model = fitted
    ranked = sensitivity(model)
    assert [name for name, _ in ranked] != []
    assert set(name for name, _ in ranked) == set(FEATURE_ORDER)
    magnitudes = [abs(v) for _, v in ranked]
    assert magnitudes == sorted(magnitudes, reverse=True)


def test_area_and_efficiency_dominate_the_ranking(fitted):
    """Capacity is linear in A, h, phi and E, so those outrank temperature."""
    _, _, model = fitted
    ranked = dict(sensitivity(model))
    assert abs(ranked["area_m2"]) > abs(ranked["temperature_k"])
    assert abs(ranked["storage_efficiency"]) > abs(ranked["temperature_k"])


def test_predict_samples_matches_manual_design_matrix(fitted):
    samples, _, model = fitted
    np.testing.assert_allclose(predict_samples(model, samples), predict(model, design_matrix(samples)))


def test_predict_accepts_a_single_row(fitted):
    _, _, model = fitted
    row = [1e8, 40.0, 0.18, 15e6, 333.15, 0.04]
    assert predict(model, np.array(row)).shape == (1,)
    assert predict(model, np.array([row]))[0] == pytest.approx(predict(model, np.array(row))[0])


def test_predict_rejects_wrong_feature_count(fitted):
    _, _, model = fitted
    with pytest.raises(ValueError):
        predict(model, np.array([[1e8, 40.0, 0.18]]))


def test_fit_rejects_mismatched_lengths():
    samples = DEPLETED_GAS_ANALOG.sample(10, seed=2)
    with pytest.raises(ValueError):
        fit_linear_surrogate(samples, np.ones(3))


def test_fit_rejects_empty_samples():
    with pytest.raises(ValueError):
        fit_linear_surrogate([], np.array([]))


def test_design_matrix_column_order_matches_feature_order():
    samples = DEPLETED_GAS_ANALOG.sample(3, seed=5)
    x = design_matrix(samples)
    assert x.shape == (3, len(FEATURE_ORDER))
    for i, name in enumerate(FEATURE_ORDER):
        np.testing.assert_allclose(x[:, i], [getattr(s, name) for s in samples])
