"""Pydantic request and response models.

Request models are strict: ``extra="forbid"`` so an unrecognised field is
rejected rather than ignored. That is what stops a caller slipping
``temperature_k`` in as an assumption -- temperature is source-derived or the
well stays blocked, and a silently-dropped field would hide the attempt.

Response models are typed at the top level but keep the per-parameter
provenance entries as open mappings. That is deliberate: FastAPI filters
response payloads against the declared model, so an over-tight schema would
*silently delete* provenance fields and quietly break the audit contract. The
shapes that must never be filtered are declared as ``dict[str, Any]`` and a
test asserts the HTTP payload still matches the Python one key for key.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from ccs_screen.api import (
    DEFAULT_SAMPLES,
    DEFAULT_SCENARIO,
    MAX_SAMPLES,
    MIN_SAMPLES,
)

_STRICT = ConfigDict(extra="forbid")


# -- requests ----------------------------------------------------------------


class NetToGrossModel(BaseModel):
    """Optional declaration of the net-to-gross that thickness_m implies.

    Recorded for provenance only; never used in a calculation. ``gt=0, le=1``
    also rejects NaN and both infinities.
    """

    model_config = _STRICT

    low: float = Field(..., gt=0, le=1, json_schema_extra={"example": 0.30})
    high: float = Field(..., gt=0, le=1, json_schema_extra={"example": 0.55})
    net_criterion: Literal[
        "porosity_permeability", "porosity_only", "permeability_only",
        "lithology_net_sand", "flow_unit", "unspecified",
    ] = Field(..., description="What test defined 'net'.")
    net_basis: Literal[
        "log_derived", "core_derived", "model_derived",
        "analogue", "assumed", "unknown",
    ] = Field(..., description="How the ratio was obtained.")
    cutoff_note: str | None = Field(default=None, max_length=500)
    thickness_convention: Literal["measured", "tvd", "tst"] | None = None

    @model_validator(mode="after")
    def _ordered(self) -> "NetToGrossModel":
        if self.low > self.high:
            raise ValueError(f"low must be <= high, got ({self.low}, {self.high})")
        return self


class UserInputsModel(BaseModel):
    """The two geological inputs the caller must supply.

    No defaults. Both have no source data and no literature range, so a default
    here would be a hidden geological assumption presented as a result.
    """

    model_config = _STRICT

    area_m2: float = Field(
        ...,
        gt=0,
        description=("Structural closure area in m2. Never inferred from licence "
                     "boundaries, concession polygons, well spacing or a radius."),
        json_schema_extra={"example": 8.0e7},
    )
    thickness_m: float = Field(
        ...,
        gt=0,
        description=("Net storage thickness in m -- not the gross "
                     "chronostratigraphic interval."),
        json_schema_extra={"example": 35.0},
    )
    net_to_gross: NetToGrossModel | None = Field(
        default=None,
        description=("Optional: the net-to-gross that thickness_m implies. "
                     "Recorded for provenance; not used in any calculation."),
    )


class ScreenRequest(BaseModel):
    """Body for POST /wells/{well_id}/screen."""

    model_config = _STRICT

    user_inputs: UserInputsModel
    scenario: str = Field(default=DEFAULT_SCENARIO, max_length=200)
    # StrictInt so "2000" and 2.0 are rejected rather than coerced. A caller
    # who sends a string is confused about the contract; silently accepting it
    # hides that.
    samples: StrictInt = Field(
        default=DEFAULT_SAMPLES,
        ge=MIN_SAMPLES,
        le=MAX_SAMPLES,
        description=(f"Monte Carlo realisations, {MIN_SAMPLES}-{MAX_SAMPLES}. "
                     f"Out-of-range values are rejected, never clamped."),
    )
    seed: StrictInt = Field(default=42, ge=0, le=2**32 - 1)


class TemperatureRequest(BaseModel):
    """Body for POST /wells/{well_id}/temperature."""

    model_config = _STRICT

    user_inputs: UserInputsModel
    scenario: str = Field(default=DEFAULT_SCENARIO, max_length=200)
    samples: StrictInt = Field(default=500, ge=MIN_SAMPLES, le=MAX_SAMPLES)
    seed: StrictInt = Field(default=42, ge=0, le=2**32 - 1)


# -- responses ---------------------------------------------------------------


class HealthResponse(BaseModel):
    status: Literal["ok"]
    wells_loaded: int
    data_dir: str
    scenario_default: str
    limits: dict[str, Any]


class InterpretationModel(BaseModel):
    """Never let a capacity number travel without this."""

    model_config = ConfigDict(extra="allow")

    type: Literal["scenario_based_capacity"]
    site_specific: Literal[False]
    certified: Literal[False]
    proven_resource: Literal[False]
    basis: str
    statement: str
    area_policy: str
    net_thickness_policy: str
    warnings: list[dict[str, Any]] = Field(default_factory=list)


class WellSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    well_id: str
    original_names: list[str]
    depth_m: float | None
    has_temperature: bool
    has_gross_thickness: bool
    operator: str | None
    outcome: str | None
    screenable_without_user_inputs: bool


class CapacityModel(BaseModel):
    """P10/P50/P90 in the statistical convention: low / median / high case.

    The two disclosure blocks are open mappings so FastAPI cannot filter them.
    """

    model_config = ConfigDict(extra="allow")

    p10: float = Field(..., description="Low case: 10th percentile, Mt CO2.")
    p50: float = Field(..., description="Median case: 50th percentile, Mt CO2.")
    p90: float = Field(..., description="High case: 90th percentile, Mt CO2.")
    mean: float
    n_samples: int
    deterministic: bool
    percentile_convention: dict[str, Any] | None = None
    uncertainty_band: dict[str, Any] | None = None


class ScreenResponse(BaseModel):
    """The screening result.

    ``screening_inputs`` stays an open mapping so every provenance field
    (value, unit, provenance, evidence_class, assumed, label, rationale,
    citation, derivation, author) reaches the client untouched.
    """

    model_config = ConfigDict(extra="allow")

    status: Literal["screened", "blocked"]
    well_id: str
    scenario: dict[str, Any]
    interpretation: InterpretationModel
    scenario_based_capacity_mt: CapacityModel | None = None

    # The disjoint partition. Every required input appears in exactly one.
    source_derived_inputs: list[str] = Field(default_factory=list)
    modelled_inputs: list[str] = Field(default_factory=list)
    assumed_inputs: list[str] = Field(default_factory=list)
    user_supplied_inputs: list[str] = Field(default_factory=list)

    screening_inputs: dict[str, Any] = Field(default_factory=dict)
    label_legend: dict[str, str] = Field(default_factory=dict)
    user_inputs: dict[str, Any] = Field(default_factory=dict)
    thickness_provenance: dict[str, Any] | None = None
    temperature: dict[str, Any] | None = None
    conflicts: list[str] = Field(default_factory=list)
    depth_m: float | None = None

    # Present on a blocked result.
    reason: str | None = None
    error: str | None = None
    missing_fields: list[str] | None = None
    missing_reasons: dict[str, str] | None = None
    required_user_inputs: list[dict[str, Any]] | None = None


class TemperatureResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    well_id: str | None = None
    selected_method: str | None = None
    variants: list[dict[str, Any]] = Field(default_factory=list)
    p50_spread_mt: float | None = None
    p50_spread_percent: float | None = None
    interpretation: InterpretationModel
    note: str | None = None
    scenario: dict[str, Any] | None = None
    user_inputs: dict[str, Any] | None = None
    thickness_provenance: dict[str, Any] | None = None
    percentile_convention: dict[str, Any] | None = None
    reason: str | None = None
    error: str | None = None


class ErrorResponse(BaseModel):
    """Uniform error envelope for 400/404/413."""

    error: str
    type: str
    detail: str | None = None
