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

Screening responses are a union discriminated by ``model_path``: the approved
model (``APPROVED_MODEL``) and the NOT_VALIDATED legacy scenarios
(``LEGACY_NOT_VALIDATED``) each validate against their own model, so neither
path acquires the other's fields.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from ccs_screen.api import (
    APPROVED_MODEL_PATH,
    DEFAULT_SAMPLES,
    DEFAULT_SCENARIO,
    LEGACY_MODEL_PATH,
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
    """The geological inputs the caller must supply.

    No defaults. None of these has source data or a literature range, so a
    default here would be a hidden geological assumption presented as a result.

    ``area_m2`` is required on every path. Which of the others is required
    depends on the scenario, so the API validates the combination: the approved
    model (``literature-screening-v1``) takes ``z_top`` and ``z_base`` and
    rejects ``thickness_m``; the NOT_VALIDATED legacy scenarios take
    ``thickness_m``. A mismatch comes back ``blocked`` with the reason.
    """

    model_config = _STRICT

    area_m2: float = Field(
        ...,
        gt=0,
        allow_inf_nan=False,
        description=("Structural closure area in m2. Never inferred from licence "
                     "boundaries, concession polygons, well spacing or a radius."),
        json_schema_extra={"example": 8.0e7},
    )
    z_top: float | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
        description=("Approved model: top of the designated storage-assessment "
                     "interval, m below ground level, in the same depth coordinate "
                     "and datum as the well's depth_m. Never inferred."),
        json_schema_extra={"example": 1400.0},
    )
    z_base: float | None = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
        description=("Approved model: base of the designated storage-assessment "
                     "interval (z_base > z_top), same coordinate and datum. "
                     "h_g = z_base - z_top is derived."),
        json_schema_extra={"example": 1500.0},
    )
    thickness_m: float | None = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
        description=("NOT_VALIDATED legacy scenarios only: net storage thickness in "
                     "m -- not the gross chronostratigraphic interval. Rejected by "
                     "the approved model."),
        json_schema_extra={"example": 35.0},
    )
    net_to_gross: NetToGrossModel | None = Field(
        default=None,
        description=("Optional provenance metadata; never used in any calculation. "
                     "Approved model: h_net / h_g, a consistency check only. Legacy: "
                     "the net-to-gross that thickness_m implies."),
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


class DatasetModel(BaseModel):
    """Which dataset the service reads. ``synthetic`` is true for the demo."""

    kind: Literal["structured_sources", "synthetic_demo", "none"]
    synthetic: bool
    name: str
    version: str | None = None
    statement: str | None = None


class HealthResponse(BaseModel):
    """Liveness. ``status`` is ``ok`` whenever the process is serving.

    ``engine_ready``: user assessments can be evaluated (detail at ``/ready``).
    ``data_ready``: the optional existing well dataset is usable (detail at
    ``/ready/existing-data``)."""

    status: Literal["ok"]
    engine_ready: bool
    data_ready: bool
    dataset: DatasetModel
    wells_loaded: int
    data_dir: str
    scenario_default: str
    limits: dict[str, Any]


class SourceStatusModel(BaseModel):
    source: str
    file: str
    required: bool
    status: Literal["loaded", "missing", "dependency_missing", "unreadable", "conflict"]
    detail: str | None


class EngineReadinessResponse(BaseModel):
    """Engine readiness (``/ready``): 200 when user assessments can be evaluated.

    ``existing_data`` reports the optional well dataset for information only;
    it never makes the service unready."""

    status: Literal["ready", "not_ready"]
    engine: dict[str, Any]
    existing_data: dict[str, Any]


class AssessmentParseRequest(BaseModel):
    """An uploaded file's text. It is parsed as data, never executed."""

    model_config = _STRICT
    format: Literal["json", "csv"]
    content: str = Field(..., max_length=200_000)
    filename: str | None = Field(default=None, max_length=255)


class AssessmentRequest(BaseModel):
    """A ``ccs-assessment/1`` document plus run controls."""

    model_config = _STRICT
    document: dict[str, Any]
    samples: StrictInt = Field(default=2000, ge=1, le=50_000)
    seed: StrictInt = Field(default=42, ge=0, le=2**32 - 1)


class ReadinessResponse(BaseModel):
    """Existing-data readiness: 200 with ``ready``, otherwise 503 with ``not_ready``."""

    status: Literal["ready", "not_ready"]
    dataset: DatasetModel
    wells_loaded: int
    data_dir: str
    sources: list[SourceStatusModel]
    problems: list[str]


class InterpretationModel(BaseModel):
    """Never let a capacity number travel without this.

    Path-specific policy keys (``net_thickness_policy`` on legacy paths;
    ``storage_interval_policy``, ``percentile_interpretation`` and
    ``joint_scenario_methodology`` on the approved model) pass through as
    extras, so neither path acquires the other's keys.
    """

    model_config = ConfigDict(extra="allow")

    type: Literal["scenario_based_capacity"]
    site_specific: Literal[False]
    certified: Literal[False]
    proven_resource: Literal[False]
    basis: str
    statement: str
    area_policy: str
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
    depth_datum: str
    approved_model_depth_reference: dict[str, Any]


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


class ApprovedScreenResponse(BaseModel):
    """The approved-model result: both named water-level scenarios.

    Only the keys every approved payload carries are declared. The rest --
    ``storage_interval``, ``depth_reference``, ``temperature_selection``,
    ``water_level_scenarios`` (each with ``validation_status``,
    ``validated_percentiles``, ``capacity_mt``, ``diagnostic_capacity_mt`` and
    ``diagnostics``), ``systematic_effect``, ``sampled_inputs``,
    ``model_constants`` -- pass through untouched as extras.
    """

    model_config = ConfigDict(extra="allow")

    model_path: Literal["APPROVED_MODEL"]
    status: Literal["evaluated", "blocked"]
    well_id: str
    scenario: dict[str, Any]
    interpretation: InterpretationModel


class LegacyScreenResponse(BaseModel):
    """A NOT_VALIDATED legacy screening result (owner decision O2).

    ``screening_inputs`` stays an open mapping so every provenance field
    (value, unit, provenance, evidence_class, assumed, label, rationale,
    citation, derivation, author) reaches the client untouched.
    """

    model_config = ConfigDict(extra="allow")

    model_path: Literal["LEGACY_NOT_VALIDATED"]
    validation_status: Literal["NOT_VALIDATED"]
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


#: POST /wells/{well_id}/screen returns one of the two, selected by model_path.
ScreenResponse = Annotated[
    Union[ApprovedScreenResponse, LegacyScreenResponse],
    Field(discriminator="model_path"),
]

#: The discriminator values, restated for the consistency test against the API.
SCREEN_RESPONSE_PATHS = {APPROVED_MODEL_PATH: ApprovedScreenResponse,
                         LEGACY_MODEL_PATH: LegacyScreenResponse}


class TemperatureResponse(BaseModel):
    """The temperature-method comparison: a NOT_VALIDATED legacy diagnostic."""

    model_config = ConfigDict(extra="allow")

    status: str
    model_path: Literal["LEGACY_NOT_VALIDATED"]
    validation_status: Literal["NOT_VALIDATED"]
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
    """Uniform error envelope for 400/404/413/503.

    ``detail`` is a string, ``null``, or a list: the field errors of a 422, or
    the failed required sources of a 503 ``DatasetNotReadyError``.
    """

    error: str
    type: str
    detail: str | list[Any] | None = None
