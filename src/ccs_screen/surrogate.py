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
    coef: np.ndarray  # intercept + 6 features
    feature_mean: np.ndarray
    feature_std: np.ndarray


def _design(samples: list[CapacitySample]) -> np.ndarray:
    return np.array(
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
        ],
        dtype=float,
    )


def fit_linear_surrogate(samples: list[CapacitySample], masses_mt: np.ndarray) -> LinearSurrogate:
    x = _design(samples)
    mean = x.mean(axis=0)
    std = x.std(axis=0)
    std = np.where(std < 1e-12, 1.0, std)
    z = (x - mean) / std
    a = np.column_stack([np.ones(len(z)), z])
    coef, *_ = np.linalg.lstsq(a, np.asarray(masses_mt, dtype=float), rcond=None)
    return LinearSurrogate(coef=coef, feature_mean=mean, feature_std=std)


def predict(model: LinearSurrogate, features: np.ndarray) -> np.ndarray:
    x = np.asarray(features, dtype=float)
    z = (x - model.feature_mean) / model.feature_std
    a = np.column_stack([np.ones(len(z)), z])
    return a @ model.coef
