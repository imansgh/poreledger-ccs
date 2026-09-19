"""Linear surrogate over standardized screening inputs.

Because the features are standardized before the fit, the coefficients are
directly comparable: their magnitude ranks how much each input moves capacity
over the sampled range. That ranking is the point of the surrogate -- it is a
sensitivity screen, not a replacement for the volumetric calculation.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ccs_screen.monte_carlo import CapacitySample

FEATURE_ORDER = (
    "area_m2",
    "thickness_m",
    "porosity",
    "pressure_pa",
    "temperature_k",
    "storage_efficiency",
)


@dataclass(frozen=True)
class LinearSurrogate:
    coef: np.ndarray  # intercept + 6 standardized-feature coefficients
    feature_mean: np.ndarray
    feature_std: np.ndarray

    @property
    def intercept(self) -> float:
        return float(self.coef[0])

    @property
    def standardized_coef(self) -> np.ndarray:
        return self.coef[1:]


@dataclass(frozen=True)
class SurrogateMetrics:
    rmse_mt: float
    mae_mt: float
    r2: float


def design_matrix(samples: list[CapacitySample]) -> np.ndarray:
    """Raw (unstandardized) feature matrix in ``FEATURE_ORDER``."""
    return np.array(
        [[getattr(s, name) for name in FEATURE_ORDER] for s in samples],
        dtype=float,
    )


_design = design_matrix  # backwards-compatible alias


def fit_linear_surrogate(samples: list[CapacitySample], masses_mt: np.ndarray) -> LinearSurrogate:
    if not samples:
        raise ValueError("need at least one sample")
    x = design_matrix(samples)
    y = np.asarray(masses_mt, dtype=float)
    if len(y) != len(x):
        raise ValueError("samples and masses_mt must have the same length")
    mean = x.mean(axis=0)
    std = x.std(axis=0)

    # A feature held at a point value carries no information, but its computed
    # std is floating-point residue rather than exactly zero (e.g. 2.7e-12 for a
    # constant 358.15 K column). An absolute threshold cannot catch that, because
    # the residue scales with the feature's own magnitude -- for an area around
    # 1e8 m2 it lands near 1e-8. Comparing the exact peak-to-peak spread against
    # the feature's scale is reliable at any magnitude. Without this, dividing
    # residue by residue yields noise that lstsq happily fits, and a constant
    # input can be reported as the strongest driver in the sensitivity ranking.
    scale = np.maximum(np.abs(mean), 1.0)
    degenerate = (x.max(axis=0) - x.min(axis=0)) <= 1e-12 * scale

    std = np.where(degenerate, 1.0, std)
    z = (x - mean) / std
    z[:, degenerate] = 0.0

    a = np.column_stack([np.ones(len(z)), z])
    coef, *_ = np.linalg.lstsq(a, y, rcond=None)
    coef[1:][degenerate] = 0.0

    return LinearSurrogate(coef=coef, feature_mean=mean, feature_std=std)


def predict(model: LinearSurrogate, features: np.ndarray) -> np.ndarray:
    x = np.atleast_2d(np.asarray(features, dtype=float))
    if x.shape[1] != len(FEATURE_ORDER):
        raise ValueError(f"expected {len(FEATURE_ORDER)} features in FEATURE_ORDER, got {x.shape[1]}")
    z = (x - model.feature_mean) / model.feature_std
    a = np.column_stack([np.ones(len(z)), z])
    return a @ model.coef


def predict_samples(model: LinearSurrogate, samples: list[CapacitySample]) -> np.ndarray:
    """Predict capacity for ``CapacitySample`` objects without building the matrix by hand."""
    return predict(model, design_matrix(samples))


def evaluate(model: LinearSurrogate, samples: list[CapacitySample], masses_mt: np.ndarray) -> SurrogateMetrics:
    """Goodness-of-fit of the surrogate against the physics it approximates."""
    y = np.asarray(masses_mt, dtype=float)
    pred = predict_samples(model, samples)
    residual = pred - y
    ss_res = float(np.sum(residual**2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return SurrogateMetrics(
        rmse_mt=float(np.sqrt(np.mean(residual**2))),
        mae_mt=float(np.mean(np.abs(residual))),
        r2=r2,
    )


def sensitivity(model: LinearSurrogate) -> list[tuple[str, float]]:
    """Features ranked by absolute standardized coefficient (Mt per 1 sigma)."""
    pairs = list(zip(FEATURE_ORDER, (float(c) for c in model.standardized_coef)))
    return sorted(pairs, key=lambda item: abs(item[1]), reverse=True)
