"""Screening-grade tools for geologic CO2 storage."""

from ccs_screen.api import (
    INTERPRETATION,
    REQUIRED_USER_INPUTS,
    USER_INPUT_SPEC,
    ApiError,
    UnknownWellError,
    UserInputs,
)
from ccs_screen.capacity import volumetric_storage_mass_kg
from ccs_screen.config import (
    BOUNDS,
    REQUIRED_FIELDS,
    ConfigError,
    ScreeningConfig,
)
from ccs_screen.monte_carlo import (
    DEPLETED_GAS_ANALOG,
    CapacitySample,
    McResult,
    UniformPriors,
    run_capacity_mc,
    sample_mass_mt,
)
from ccs_screen.pressure import (
    allowable_delta_p_pa,
    fracture_pressure_pa,
    max_injection_rate_m3_s,
    theis_injection_delta_p_pa,
    theis_transmissivity,
)
from ccs_screen.properties import (
    co2_compressibility,
    co2_density_kg_m3,
    co2_molar_volume_m3_mol,
)
from ccs_screen.surrogate import (
    FEATURE_ORDER,
    LinearSurrogate,
    SurrogateMetrics,
    design_matrix,
    evaluate,
    fit_linear_surrogate,
    predict,
    predict_samples,
    sensitivity,
)

__version__ = "0.2.0"

__all__ = [
    "ApiError",
    "BOUNDS",
    "CapacitySample",
    "ConfigError",
    "DEPLETED_GAS_ANALOG",
    "FEATURE_ORDER",
    "INTERPRETATION",
    "LinearSurrogate",
    "McResult",
    "REQUIRED_FIELDS",
    "REQUIRED_USER_INPUTS",
    "ScreeningConfig",
    "SurrogateMetrics",
    "USER_INPUT_SPEC",
    "UniformPriors",
    "UnknownWellError",
    "UserInputs",
    "__version__",
    "allowable_delta_p_pa",
    "co2_compressibility",
    "co2_density_kg_m3",
    "co2_molar_volume_m3_mol",
    "design_matrix",
    "evaluate",
    "fit_linear_surrogate",
    "fracture_pressure_pa",
    "max_injection_rate_m3_s",
    "predict",
    "predict_samples",
    "run_capacity_mc",
    "sample_mass_mt",
    "sensitivity",
    "theis_injection_delta_p_pa",
    "theis_transmissivity",
    "volumetric_storage_mass_kg",
]
