"""Public screening API.

A small, JSON-shaped boundary over the ingestion, scenario and screening layers.
The FastAPI app in ``ccs_screen.web`` is a thin translation of HTTP onto these
calls; no web framework is imported here.

The contract this module exists to enforce
------------------------------------------
``area_m2`` and ``thickness_m`` have no basis in the source data and no
literature range (see ``docs/scenario-literature-review.md``). They are the two
largest linear multipliers in the capacity equation. So the public API makes
them **required inputs supplied by the caller**, with no defaults anywhere in
the code path. A request that omits them comes back ``blocked`` with a
structured list of what is needed and why -- never a number computed from a
filler value.

Neither is ever inferred from licence boundaries, concession polygons, well
spacing, an arbitrary radius, or gross stratigraphic thickness.

Every result carries an ``interpretation`` block declaring the number to be
scenario-based and not site-specific.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from ccs_screen.ingest.assumptions import (
    Assumption,
    AssumptionError,
    AssumptionSet,
    Citation,
    EvidenceClass,
)
from ccs_screen.ingest.normalize import WellNormalizer
from ccs_screen.ingest.provenance import Confidence
from ccs_screen.ingest.records import NormalizedWellRecord, ThicknessKind
from ccs_screen.ingest.report import (
    compare_temperature_methods as _compare_methods,
)
from ccs_screen.ingest.report import screen_well as _screen_record
from ccs_screen.ingest.scenario import (
    AREA_POLICY_STATEMENT,
    BUILTIN_SCENARIOS,
    LITERATURE_UNSUPPORTED,
    NET_THICKNESS_POLICY_STATEMENT,
    ScreeningScenario,
    load_scenario,
    resolve_inputs,
)

DEFAULT_SCENARIO = "literature-screening-v1"
DEFAULT_DATA_DIR = "data"

#: Monte Carlo realisations allowed on a public endpoint.
#:
#: The screening P50 for a representative well converges by roughly 10,000
#: realisations (2,000 -> 10.64 Mt, 10,000 -> 10.90 Mt, and 50,000 / 100,000 /
#: 200,000 all within 0.03 Mt of that). Cost is linear at about 7 microseconds
#: per realisation, so 50,000 costs ~0.33 s and 200,000 costs ~1.4 s.
#:
#: The cap is therefore set five times past the point of diminishing scientific
#: return: high enough that no screening run is limited by it, low enough that a
#: single request cannot turn into seconds of CPU. Excessive values are
#: rejected, never clamped -- silently returning fewer realisations than asked
#: for would make results irreproducible for the caller.
MIN_SAMPLES = 1
MAX_SAMPLES = 50_000
DEFAULT_SAMPLES = 2_000

#: Inputs the caller must supply for public screening. Both are absent from the
#: source data and unsupported by literature, and both are linear multipliers.
REQUIRED_USER_INPUTS = tuple(LITERATURE_UNSUPPORTED)

#: What each required input means, for a UI to display at the point of entry.
USER_INPUT_SPEC: dict[str, dict[str, Any]] = {
    "area_m2": {
        "unit": "m2",
        "label": "Storage area",
        "description": (
            "Structural closure area of the storage complex. Must come from a "
            "depth-structure map or equivalent interpretation."
        ),
        "policy": AREA_POLICY_STATEMENT,
        "not_inferred_from": [
            "licence boundaries", "concession polygons", "administrative boundaries",
            "well spacing", "arbitrary radius around a well",
        ],
        "minimum_exclusive": 0.0,
    },
    "thickness_m": {
        "unit": "m",
        "label": "Net storage thickness",
        "description": (
            "Net reservoir thickness inside the closure -- NOT the gross "
            "chronostratigraphic interval, which is 1-2 orders of magnitude larger."
        ),
        "policy": NET_THICKNESS_POLICY_STATEMENT,
        "not_inferred_from": ["gross stratigraphic thickness", "total well depth"],
        "minimum_exclusive": 0.0,
    },
}

#: Scale-mismatch disclosure for the literature-constrained scenario.
#:
#: CSLF's storage-efficiency range is a basin/methodology-scale figure (derived
#: against "the area that defines the basin or the region occupied by the
#: aquifer"), and Donda et al.'s porosity range is a regional compilation across
#: 13 Italian reservoirs. The public API applies both against a caller-supplied
#: area and net thickness at closure scale.
#:
#: This does not make the result invalid, and no correction factor is applied --
#: none is derivable from the sources. It is disclosed so a client can show the
#: caveat rather than discover it in a PDF. See
#: docs/scenario-literature-review.md sections 8 and 10.
SCALE_MISMATCH_WARNING = {
    "code": "scale_mismatch_basin_vs_closure",
    "severity": "advisory",
    "message": (
        "Literature-constrained porosity and storage-efficiency ranges are not "
        "site-specific closure-scale calibrations."
    ),
    "detail": (
        "Storage efficiency (CSLF-T-2008-04) is calibrated at basin/aquifer "
        "scale and porosity (Donda et al. 2011) is a regional compilation, "
        "while area and net thickness are supplied at closure scale. The "
        "parameters come from different framings; no correction factor is "
        "applied because none is derivable from the cited sources."
    ),
    "affects": ["porosity", "storage_efficiency"],
    "invalidates_result": False,
    "correction_applied": False,
    "reference": "docs/scenario-literature-review.md sections 8 and 10",
}

#: Percentile semantics, attached wherever P10/P50/P90 are returned (Finding 7.5).
#:
#: The engine uses the statistical convention (see ``monte_carlo``): p10 is the
#: LOW case. Petroleum reserves reporting uses the opposite convention, so a
#: consumer from that domain would invert the risk reading unless the payload
#: says which one it is. Disclosure only -- no percentile is recomputed.
PERCENTILE_CONVENTION = {
    "convention": "statistical",
    "p10": "low case -- 10th percentile of the sampled capacity distribution",
    "p50": "median case -- 50th percentile of the sampled capacity distribution",
    "p90": "high case -- 90th percentile of the sampled capacity distribution",
    "ordering": "p10 <= p50 <= p90",
    "note": (
        "Statistical convention: P10 = low case, P50 = median case, P90 = high "
        "case. This is NOT the petroleum reserves convention, in which P10 "
        "denotes the high case."
    ),
}

#: What the P10-P90 interval does and does not contain (Finding 12.5).
#:
#: The band is the spread of the Monte Carlo sample over the declared input
#: ranges. The percentiles are computed correctly for that sample; what the band
#: cannot contain is bias in the model or its inputs, which is not sampled. The
#: audit found such biases and they are not all small, so the band must not be
#: read as bracketing the true value. Disclosure only -- no value is adjusted.
UNCERTAINTY_BAND_DISCLOSURE = {
    "code": "sampled_uncertainty_band_excludes_systematic_bias",
    "interval": "p10-p90",
    "lower_bound": "p10 -- the lower sampled case",
    "upper_bound": "p90 -- the upper sampled case",
    "represents": (
        "The model's sampled uncertainty band: the spread of the Monte Carlo "
        "realisations over the declared input ranges."
    ),
    "statement": (
        "The reported P10-P90 interval is the model's sampled uncertainty band. "
        "P10 is the lower sampled case and P90 is the upper sampled case of the "
        "Monte Carlo distribution, and both are correctly computed for that "
        "distribution. The band does not necessarily contain systematic or model "
        "bias: systematic biases identified by the scientific validation audit "
        "lie outside the Monte Carlo sampling uncertainty and may place the true "
        "value outside the reported P10-P90 interval. It is not a confidence "
        "interval for the true storage capacity."
    ),
    "includes_systematic_bias": False,
    "values_adjusted": False,
    "reference": "docs/scientific-validation-audit.md, Finding 12.5",
}

#: The Finding 12.5 disclosure as an interpretation warning, so a client that
#: renders warnings shows it next to the number without extra code.
UNCERTAINTY_BAND_WARNING = {
    "code": UNCERTAINTY_BAND_DISCLOSURE["code"],
    "severity": "advisory",
    "message": (
        "The P10-P90 interval is the model's sampled uncertainty band and does "
        "not necessarily contain systematic or model bias."
    ),
    "detail": UNCERTAINTY_BAND_DISCLOSURE["statement"],
    "affects": ["scenario_based_capacity_mt"],
    "invalidates_result": False,
    "correction_applied": False,
    "reference": UNCERTAINTY_BAND_DISCLOSURE["reference"],
}

#: Attached to every screening result. The wording is deliberate: this pipeline
#: cannot produce a certified, proven or site-specific figure, and says so in a
#: field a client can assert on rather than in prose it may not render.
INTERPRETATION = {
    "type": "scenario_based_capacity",
    "site_specific": False,
    "certified": False,
    "proven_resource": False,
    "basis": "literature-constrained screening under explicit engineering assumptions",
    "statement": (
        "Scenario-based screening capacity. This is not a certified storage "
        "capacity, not a proven storage resource, and not a site-specific "
        "estimate. It is conditional on user-supplied area and net thickness, "
        "for which no source data or literature range exists."
    ),
    "area_policy": AREA_POLICY_STATEMENT,
    "net_thickness_policy": NET_THICKNESS_POLICY_STATEMENT,
    "warnings": [],
}

#: Meaning of each input label, so a client can render a legend.
LABEL_LEGEND = {
    "source": "extracted from, or derived from, this well's own data",
    "MODELLED": "computed from source data under a declared generic model",
    "ASSUMED": "supplied by the scenario (literature-constrained where cited)",
    "USER": "supplied by the caller for this request",
}

#: Published request limits, so a client can validate before sending.
REQUEST_LIMITS = {
    "samples": {"min": MIN_SAMPLES, "max": MAX_SAMPLES, "default": DEFAULT_SAMPLES,
                "clamped": False,
                "note": ("Rejected rather than clamped. The screening result "
                         "converges well below the maximum.")},
}

#: The four label buckets are disjoint and together cover every required input.
INPUT_PARTITION_KEYS = (
    "source_derived_inputs",
    "modelled_inputs",
    "assumed_inputs",
    "user_supplied_inputs",
)

_USER_CITATION = Citation(
    source="caller",
    title="User-supplied screening input",
    year=2026,
    text=(
        "USER INPUT supplied at request time. No source data and no literature "
        "range exists for this parameter; see docs/scenario-literature-review.md "
        "sections 8 and 9."
    ),
    evidence_class=EvidenceClass.USER_INPUT,
)


def _interpretation(scenario: ScreeningScenario | None = None,
                    user_inputs: "UserInputs | None" = None,
                    band_reported: bool = False) -> dict[str, Any]:
    """Interpretation block, with any warnings the scenario earns.

    The scale-mismatch warning attaches when the scenario actually carries
    literature-derived values; a placeholder or empty scenario has no literature
    framing to mismatch. The block is rebuilt per call so the module constant
    never accumulates warnings across requests.

    Net-to-gross disclosure applies only when ``user_inputs`` is given, i.e. to a
    per-well result whose thickness_m the caller supplied. Fleet-level and
    input-free calls pass nothing and get no net-to-gross warning.
    ``band_reported`` attaches the Finding 12.5 disclosure when a P10-P90 band
    is actually in the payload.
    """
    block = {k: (list(v) if isinstance(v, list) else v) for k, v in INTERPRETATION.items()}
    warnings: list[dict[str, Any]] = []
    if scenario is not None and any(a.is_literature_derived for a in scenario.assumptions):
        warnings.append(dict(SCALE_MISMATCH_WARNING))
    if user_inputs is not None:
        if user_inputs.net_to_gross is None:
            warnings.append(dict(NET_TO_GROSS_UNDECLARED_WARNING))
        elif user_inputs.net_to_gross.is_point:
            warnings.append(dict(NET_TO_GROSS_POINT_WARNING))
    if band_reported:
        warnings.append(dict(UNCERTAINTY_BAND_WARNING))
    block["warnings"] = warnings
    return block


class ApiError(ValueError):
    """A request could not be served as asked."""


class UnknownWellError(ApiError):
    """No well with that canonical id."""


def validate_samples(samples: Any) -> int:
    """Bound the Monte Carlo realisation count for a public endpoint.

    Rejects rather than clamps: a caller who asks for 10 million and silently
    receives 50,000 cannot reproduce the run they think they made.
    """
    if isinstance(samples, bool):
        raise ApiError(
            f"samples: expected an integer, got bool ({samples!r}). "
            f"Booleans are not sample counts."
        )
    if not isinstance(samples, int):
        raise ApiError(
            f"samples: expected an integer between {MIN_SAMPLES} and "
            f"{MAX_SAMPLES}, got {type(samples).__name__} ({samples!r})"
        )
    if samples < MIN_SAMPLES:
        raise ApiError(f"samples: must be >= {MIN_SAMPLES}, got {samples}")
    if samples > MAX_SAMPLES:
        raise ApiError(
            f"samples: must be <= {MAX_SAMPLES}, got {samples}. The screening "
            f"result converges well below this limit; the cap bounds CPU per "
            f"request and is not clamped silently."
        )
    return samples


# -- thickness provenance (Phase 1: disclosure only) -------------------------
#
# net_to_gross records the ratio the caller's thickness_m implies. It is NOT an
# Assumption: Assumption validates against ASSUMABLE, and ASSUMABLE feeds
# SCENARIO_PARAMETERS, so registering it there would let a scenario assert a
# net-to-gross it cannot know. See docs/net-to-gross-semantics.md section 4.


class NetCriterion(str, Enum):
    """What test defined "net" in the caller's thickness_m.

    POROSITY_PERMEABILITY matches CSLF-T-2008-04's wording for E_h exactly --
    "the geological unit that has the porosity and permeability required for
    CO2 injection". The others are weaker or different measurements of the same
    intent, and are recorded rather than rejected.
    """

    POROSITY_PERMEABILITY = "porosity_permeability"
    POROSITY_ONLY = "porosity_only"
    PERMEABILITY_ONLY = "permeability_only"
    LITHOLOGY_NET_SAND = "lithology_net_sand"
    FLOW_UNIT = "flow_unit"
    UNSPECIFIED = "unspecified"


class NetBasis(str, Enum):
    """How the caller obtained the ratio."""

    LOG_DERIVED = "log_derived"
    CORE_DERIVED = "core_derived"
    MODEL_DERIVED = "model_derived"
    ANALOGUE = "analogue"
    ASSUMED = "assumed"
    UNKNOWN = "unknown"


class ThicknessConvention(str, Enum):
    """The convention shared by numerator and denominator.

    The ratio is invariant to which one it is, provided both use the same.
    Declared so a reader can tell that they did.
    """

    MEASURED = "measured"
    TRUE_VERTICAL = "tvd"
    TRUE_STRATIGRAPHIC = "tst"


#: Reuses the existing evidence hierarchy rather than inventing a second one.
NET_BASIS_EVIDENCE: dict[NetBasis, EvidenceClass] = {
    NetBasis.LOG_DERIVED: EvidenceClass.SITE_SPECIFIC,
    NetBasis.CORE_DERIVED: EvidenceClass.SITE_SPECIFIC,
    NetBasis.MODEL_DERIVED: EvidenceClass.SITE_SPECIFIC,
    NetBasis.ANALOGUE: EvidenceClass.REGIONAL,
    NetBasis.ASSUMED: EvidenceClass.USER_INPUT,
    NetBasis.UNKNOWN: EvidenceClass.UNSUPPORTED,
}

NET_BASIS_CONFIDENCE: dict[NetBasis, Confidence] = {
    NetBasis.CORE_DERIVED: Confidence.HIGH,
    NetBasis.LOG_DERIVED: Confidence.HIGH,
    NetBasis.MODEL_DERIVED: Confidence.MEDIUM,
    NetBasis.ANALOGUE: Confidence.LOW,
    NetBasis.ASSUMED: Confidence.LOW,
    NetBasis.UNKNOWN: Confidence.NONE,
}

NET_TO_GROSS_FIELDS = ("low", "high", "net_criterion", "net_basis",
                       "cutoff_note", "thickness_convention")
NET_TO_GROSS_REQUIRED = ("low", "high", "net_criterion", "net_basis")

NET_TO_GROSS_DEFINITION = (
    "Fraction of the gross formation interval that satisfies the caller's "
    "declared reservoir-quality criterion, over the same interval from which "
    "thickness_m was derived. Numerator and denominator must share a thickness "
    "convention. NOT derived from the chronostratigraphic gross_thickness_m. "
    "See docs/net-to-gross-semantics.md."
)

#: Stated in every thickness_provenance block, declared or not.
NET_TO_GROSS_USAGE_STATEMENT = (
    "net_to_gross is provenance metadata about thickness_m. It is recorded and "
    "reported only: it is not used in any calculation, is never inferred, and "
    "never adjusts thickness_m or capacity."
)

#: Emitted when the caller does not declare a net-to-gross. Mirrors
#: SCALE_MISMATCH_WARNING: advisory, does not invalidate, applies no correction.
NET_TO_GROSS_UNDECLARED_WARNING = {
    "code": "net_to_gross_not_declared",
    "severity": "advisory",
    "message": (
        "The net-to-gross implied by thickness_m was not declared."
    ),
    "detail": (
        "thickness_m is a net thickness, but the ratio it bears to its gross "
        "interval was not supplied, so this result cannot state what "
        "net-to-gross it assumes. The adopted storage-efficiency range "
        "(CSLF-T-2008-04) contains its own net-to-gross term, so the two may "
        "overlap. No correction is applied and the reported capacity is "
        "unaffected by this warning."
    ),
    "affects": ["thickness_m"],
    "invalidates_result": False,
    "correction_applied": False,
    "reference": "docs/finding-3.1-literature-review.md",
}

#: Emitted when net_to_gross is declared as a point (low == high).
NET_TO_GROSS_POINT_WARNING = {
    "code": "net_to_gross_point_value",
    "severity": "advisory",
    "message": "net_to_gross was declared as a point value (low == high).",
    "detail": (
        "A point value states no uncertainty in the ratio; a (low, high) range "
        "is preferred. net_to_gross is recorded only, so this does not change "
        "the reported capacity or its P10-P90 band."
    ),
    "affects": ["thickness_m"],
    "invalidates_result": False,
    "correction_applied": False,
    "reference": "docs/net-to-gross-semantics.md section 10",
}

#: Optional caller fields. Never required, never an Assumption.
OPTIONAL_USER_INPUTS = ("net_to_gross",)


def _coerce_enum(enum_cls, value, field_name: str):
    if isinstance(value, enum_cls):
        return value
    accepted = ", ".join(m.value for m in enum_cls)
    if not isinstance(value, str) or not value.strip():
        raise ApiError(f"net_to_gross.{field_name} must be a non-empty string, "
                       f"one of: {accepted}")
    try:
        return enum_cls(value.strip())
    except ValueError:
        raise ApiError(f"net_to_gross.{field_name}: unknown value {value!r} "
                       f"(accepted: {accepted})") from None


def _coerce_note(value) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ApiError(f"net_to_gross.cutoff_note must be a string, "
                       f"got {type(value).__name__}")
    text = value.strip()
    if len(text) > 500:
        raise ApiError("net_to_gross.cutoff_note must be at most 500 characters")
    return text or None


@dataclass(frozen=True)
class NetToGross:
    """The net-to-gross the caller's ``thickness_m`` implies.

    Phase 1 records this and nothing else: it never enters the capacity
    equation, never enters ``screening_inputs``, and is never inferred -- there
    is deliberately no constructor that takes a well record. See
    docs/net-to-gross-semantics.md for the canonical definition.
    """

    low: float
    high: float
    net_criterion: NetCriterion
    net_basis: NetBasis
    cutoff_note: str | None = None
    thickness_convention: ThicknessConvention | None = None

    def __post_init__(self) -> None:
        problems: list[str] = []
        for name in ("low", "high"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                problems.append(f"net_to_gross.{name}: expected a number, "
                                f"got {type(value).__name__} ({value!r})")
                continue
            number = float(value)
            if number != number or number in (float("inf"), float("-inf")):
                problems.append(f"net_to_gross.{name}: must be finite, got {value!r}")
            elif not 0 < number <= 1:
                problems.append(f"net_to_gross.{name}: must be in (0, 1], got {number:g}")
        if not problems and self.low > self.high:
            problems.append(
                f"net_to_gross: low must be <= high, got ({self.low:g}, {self.high:g})"
            )
        if problems:
            raise ApiError("; ".join(problems))
        object.__setattr__(self, "low", float(self.low))
        object.__setattr__(self, "high", float(self.high))
        object.__setattr__(self, "net_criterion",
                           _coerce_enum(NetCriterion, self.net_criterion, "net_criterion"))
        object.__setattr__(self, "net_basis",
                           _coerce_enum(NetBasis, self.net_basis, "net_basis"))
        object.__setattr__(self, "cutoff_note", _coerce_note(self.cutoff_note))
        if self.thickness_convention is not None:
            object.__setattr__(self, "thickness_convention",
                               _coerce_enum(ThicknessConvention, self.thickness_convention,
                                            "thickness_convention"))

    @property
    def is_point(self) -> bool:
        return self.low == self.high

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "NetToGross":
        if not isinstance(data, Mapping):
            raise ApiError(f"net_to_gross must be an object, got {type(data).__name__}")
        unknown = sorted(set(data) - set(NET_TO_GROSS_FIELDS))
        if unknown:
            raise ApiError(f"unknown net_to_gross field(s): {', '.join(unknown)} "
                           f"(accepted: {', '.join(NET_TO_GROSS_FIELDS)})")
        missing = [k for k in NET_TO_GROSS_REQUIRED if data.get(k) is None]
        if missing:
            raise ApiError(
                f"net_to_gross is missing required field(s): {', '.join(missing)}. "
                f"A net-to-gross without a stated criterion and basis is the "
                f"undocumented assumption this field exists to remove."
            )
        return cls(
            low=data["low"], high=data["high"],
            net_criterion=data["net_criterion"], net_basis=data["net_basis"],
            cutoff_note=data.get("cutoff_note"),
            thickness_convention=data.get("thickness_convention"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "low": self.low,
            "high": self.high,
            "unit": "-",
            "net_criterion": self.net_criterion.value,
            "net_basis": self.net_basis.value,
            "evidence_class": NET_BASIS_EVIDENCE[self.net_basis].value,
            "confidence": NET_BASIS_CONFIDENCE[self.net_basis].value,
            "cutoff_note": self.cutoff_note,
            "thickness_convention": (self.thickness_convention.value
                                     if self.thickness_convention else None),
            "is_point": self.is_point,
            "used_in_calculation": False,
            "definition": NET_TO_GROSS_DEFINITION,
        }


@dataclass(frozen=True)
class UserInputs:
    """Caller-supplied geological inputs, validated.

    Deliberately has no defaults for the two required inputs: constructing one
    without both values is an error, so there is no code path in which a
    screening runs on a filler. ``net_to_gross`` is optional provenance metadata
    about ``thickness_m`` and is never used in a calculation.
    """

    area_m2: float
    thickness_m: float
    net_to_gross: NetToGross | None = None

    def __post_init__(self) -> None:
        problems: list[str] = []
        for name in REQUIRED_USER_INPUTS:
            value = getattr(self, name)
            spec = USER_INPUT_SPEC[name]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                problems.append(
                    f"{name}: expected a number in {spec['unit']}, "
                    f"got {type(value).__name__} ({value!r})"
                )
                continue
            number = float(value)
            if number != number or number in (float("inf"), float("-inf")):
                problems.append(f"{name}: must be a finite number, got {value!r}")
            elif number <= spec["minimum_exclusive"]:
                problems.append(
                    f"{name}: must be > {spec['minimum_exclusive']:g} {spec['unit']}, "
                    f"got {number:g}"
                )
        if self.net_to_gross is not None and not isinstance(self.net_to_gross, NetToGross):
            problems.append(f"net_to_gross: expected NetToGross or None, "
                            f"got {type(self.net_to_gross).__name__}")
        if problems:
            raise ApiError("; ".join(problems))
        object.__setattr__(self, "area_m2", float(self.area_m2))
        object.__setattr__(self, "thickness_m", float(self.thickness_m))

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "UserInputs":
        """Build from a request body, naming anything missing."""
        data = data or {}
        if not isinstance(data, Mapping):
            raise ApiError(f"user_inputs must be an object, got {type(data).__name__}")
        unknown = sorted(set(data) - set(REQUIRED_USER_INPUTS) - set(OPTIONAL_USER_INPUTS))
        if unknown:
            raise ApiError(
                f"unknown user input(s): {', '.join(unknown)} "
                f"(accepted: {', '.join(REQUIRED_USER_INPUTS + OPTIONAL_USER_INPUTS)})"
            )
        missing = [n for n in REQUIRED_USER_INPUTS if n not in data]
        if missing:
            raise ApiError(
                f"missing required user input(s): {', '.join(missing)}. "
                f"These have no source data and no literature range, so they must "
                f"be supplied explicitly; they are never inferred."
            )
        raw_ntg = data.get("net_to_gross")
        return cls(
            area_m2=data["area_m2"],
            thickness_m=data["thickness_m"],
            net_to_gross=NetToGross.from_mapping(raw_ntg) if raw_ntg is not None else None,
        )

    def as_assumptions(self) -> tuple[Assumption, ...]:
        return tuple(
            Assumption(
                parameter=name,
                value=getattr(self, name),
                author="caller (user input)",
                rationale=(
                    f"{USER_INPUT_SPEC[name]['description']} "
                    f"Supplied by the caller for this request. "
                    f"{USER_INPUT_SPEC[name]['policy']}"
                ),
                citation=_USER_CITATION,
            )
            for name in REQUIRED_USER_INPUTS
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            name: {"value": getattr(self, name), "unit": USER_INPUT_SPEC[name]["unit"]}
            for name in REQUIRED_USER_INPUTS
        }

    def thickness_provenance(self) -> dict[str, Any]:
        """How thickness_m was obtained. Metadata, never a model input."""
        return {
            "thickness_m": self.thickness_m,
            "thickness_kind": ThicknessKind.NET_STORAGE.value,
            "declared": self.net_to_gross is not None,
            "net_to_gross_status": ("declared" if self.net_to_gross is not None
                                    else "unknown -- not supplied by the caller"),
            "net_to_gross": self.net_to_gross.to_dict() if self.net_to_gross else None,
            "used_in_calculation": False,
            "usage": NET_TO_GROSS_USAGE_STATEMENT,
            "policy": NET_THICKNESS_POLICY_STATEMENT,
        }


# -- record access -----------------------------------------------------------

_CACHE: dict[str, tuple[NormalizedWellRecord, ...]] = {}
_CACHE_LOCK = threading.Lock()


def load_records(data_dir: str | Path = DEFAULT_DATA_DIR,
                 refresh: bool = False) -> tuple[NormalizedWellRecord, ...]:
    """Normalized wells, cached per data directory.

    Concurrency
    -----------
    Reads and writes of the cache dict are individually atomic under the GIL, so
    the dict itself cannot be corrupted. The problem the lock solves is a
    thundering herd: without it, N concurrent requests arriving on a cold cache
    each run a full normalization, so the first burst of traffic multiplies the
    most expensive operation in the system by the number of workers. The
    double-checked lock means exactly one of them does the work.

    Callers must treat the returned records as **read-only**. They are shared
    across every request for that directory, and ``NormalizedWellRecord`` is a
    mutable dataclass. Nothing in this module mutates them; a future handler
    that did would contaminate every subsequent request. ``refresh=True``
    rebuilds rather than mutating.
    """
    key = str(Path(data_dir).resolve())
    if not refresh:
        cached = _CACHE.get(key)
        if cached is not None:
            return cached

    path = Path(data_dir)
    if not path.exists():
        raise ApiError(f"data directory not found: {path}")

    with _CACHE_LOCK:
        if not refresh:
            cached = _CACHE.get(key)
            if cached is not None:
                return cached
        records = tuple(WellNormalizer(path).run())
        _CACHE[key] = records
        return records


def clear_cache() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()


def _record(well_id: str, data_dir: str | Path) -> NormalizedWellRecord:
    for record in load_records(data_dir):
        if record.canonical_id == well_id:
            return record
    raise UnknownWellError(f"no well with id {well_id!r}")


def _scenario(scenario: str | ScreeningScenario) -> ScreeningScenario:
    if isinstance(scenario, ScreeningScenario):
        return scenario
    try:
        return load_scenario(scenario)
    except AssumptionError as exc:
        raise ApiError(str(exc)) from None


def _with_user_inputs(base: ScreeningScenario, user_inputs: UserInputs) -> ScreeningScenario:
    """Overlay caller inputs on a scenario.

    Caller inputs win over a scenario's own value for the same parameter: the
    public contract is that the caller supplies these, so a scenario default
    must not silently shadow what was asked for.
    """
    kept = tuple(a for a in base.assumptions if a.parameter not in REQUIRED_USER_INPUTS)
    return ScreeningScenario(
        name=f"{base.name}+user-inputs",
        description=f"{base.description} Area and net thickness supplied by the caller.",
        version=base.version,
        date=base.date,
        rationale=base.rationale,
        citation=base.citation,
        brine_density_kg_m3=base.brine_density_kg_m3,
        assumptions=AssumptionSet(
            name=f"{base.name}+user-inputs",
            assumptions=kept + user_inputs.as_assumptions(),
        ),
    )


# -- public API --------------------------------------------------------------


def list_wells(data_dir: str | Path = DEFAULT_DATA_DIR) -> list[dict[str, Any]]:
    """Every normalized well, with enough detail for a picker."""
    out = []
    for record in load_records(data_dir):
        out.append({
            "well_id": record.canonical_id,
            "original_names": sorted({r.original_name for r in record.raw_records})
                              or [record.identity.original],
            "depth_m": record.depth_m.value if record.depth_m.is_present else None,
            "has_temperature": record.temperature_k.is_present,
            "has_gross_thickness": record.gross_thickness_m.is_present,
            "operator": record.operator.value if record.operator.is_present else None,
            "outcome": record.outcome.value if record.outcome.is_present else None,
            "screenable_without_user_inputs": False,
        })
    return out


def get_well(well_id: str, data_dir: str | Path = DEFAULT_DATA_DIR) -> dict[str, Any]:
    """One well's normalized record, with full field-level provenance."""
    record = _record(well_id, data_dir)
    payload = record.to_dict()
    payload["required_user_inputs"] = list(REQUIRED_USER_INPUTS)
    payload["interpretation"] = _interpretation(_scenario(DEFAULT_SCENARIO))
    return payload


def required_user_inputs(well_id: str, scenario: str | ScreeningScenario = DEFAULT_SCENARIO,
                         data_dir: str | Path = DEFAULT_DATA_DIR) -> dict[str, Any]:
    """What the caller must supply before this well can be screened."""
    record = _record(well_id, data_dir)
    base = _scenario(scenario)
    _, missing = resolve_inputs(record, base)
    missing_names = {name for name, _ in missing}
    blockers = [
        {"field": name, "reason": reason}
        for name, reason in missing
        if name not in REQUIRED_USER_INPUTS
    ]
    return {
        "well_id": record.canonical_id,
        "scenario": {"name": base.name, "version": base.version},
        "required": [
            {"field": name, **USER_INPUT_SPEC[name], "needed": name in missing_names}
            for name in REQUIRED_USER_INPUTS
        ],
        "blocked_by_missing_source_data": blockers,
        "can_be_screened_with_user_inputs": not blockers,
        "interpretation": _interpretation(base),
    }


def screen_well(well_id: str, user_inputs: Mapping[str, Any] | UserInputs | None = None,
                scenario: str | ScreeningScenario = DEFAULT_SCENARIO,
                data_dir: str | Path = DEFAULT_DATA_DIR,
                samples: int = DEFAULT_SAMPLES, seed: int = 42) -> dict[str, Any]:
    """Screen one well under a scenario plus caller-supplied inputs.

    Returns a JSON-shaped result. When a required input is missing the result
    has ``"status": "blocked"`` and lists what is needed -- no default is ever
    substituted to make a number appear.

    ``samples`` must be an integer in [MIN_SAMPLES, MAX_SAMPLES]; an
    out-of-range value raises :class:`ApiError` rather than being clamped.
    """
    record = _record(well_id, data_dir)
    base = _scenario(scenario)
    samples = validate_samples(samples)

    try:
        resolved_inputs = (user_inputs if isinstance(user_inputs, UserInputs)
                           else UserInputs.from_mapping(user_inputs))
    except ApiError as exc:
        return _blocked_for_user_inputs(record, base, str(exc))

    active = _with_user_inputs(base, resolved_inputs)
    report = _screen_record(record, active, samples=samples, seed=seed)
    band_reported = report.screenable and report.result is not None

    payload: dict[str, Any] = {
        "status": "screened" if report.screenable else "blocked",
        "well_id": report.canonical_id,
        "scenario": {
            "name": base.name, "version": base.version, "date": base.date,
            "applied_as": active.name,
        },
        "user_inputs": resolved_inputs.to_dict(),
        "thickness_provenance": resolved_inputs.thickness_provenance(),
        "interpretation": _interpretation(active, resolved_inputs, band_reported),
        "label_legend": dict(LABEL_LEGEND),
        "depth_m": report.depth_m,
        # Disjoint partition by label. A parameter appears in exactly one list,
        # so a client can render provenance without resolving overlaps itself.
        "source_derived_inputs": [i.name for i in report.inputs if i.label == "source"],
        "modelled_inputs": [i.name for i in report.inputs if i.label == "MODELLED"],
        "assumed_inputs": [i.name for i in report.inputs if i.label == "ASSUMED"],
        "user_supplied_inputs": [i.name for i in report.inputs if i.label == "USER"],
        "screening_inputs": {i.name: i.to_dict() for i in report.inputs},
        "temperature": report.temperature.to_dict() if report.temperature else None,
        "conflicts": list(report.conflicts),
    }
    if band_reported:
        payload["scenario_based_capacity_mt"] = {
            "p10": report.result.p10_mt,
            "p50": report.result.p50_mt,
            "p90": report.result.p90_mt,
            "mean": report.result.mean_mt,
            "n_samples": report.result.n_samples,
            "deterministic": report.result.deterministic,
            # Disclosure only (Findings 7.5, 12.5); no value above is altered.
            "percentile_convention": dict(PERCENTILE_CONVENTION),
            "uncertainty_band": dict(UNCERTAINTY_BAND_DISCLOSURE),
        }
    else:
        payload["scenario_based_capacity_mt"] = None
        payload["missing_fields"] = list(report.missing_fields)
        payload["missing_reasons"] = {k: v for k, v in report.missing_reasons}
    return payload


def compare_temperature_methods(
    well_id: str, user_inputs: Mapping[str, Any] | UserInputs | None = None,
    scenario: str | ScreeningScenario = DEFAULT_SCENARIO,
    data_dir: str | Path = DEFAULT_DATA_DIR,
    samples: int = 500, seed: int = 42,
) -> dict[str, Any]:
    """What each available temperature method implies for capacity."""
    record = _record(well_id, data_dir)
    base = _scenario(scenario)
    samples = validate_samples(samples)
    try:
        resolved_inputs = (user_inputs if isinstance(user_inputs, UserInputs)
                           else UserInputs.from_mapping(user_inputs))
    except ApiError as exc:
        return _blocked_for_user_inputs(record, base, str(exc))

    active = _with_user_inputs(base, resolved_inputs)
    comparison = _compare_methods(record, active, samples=samples, seed=seed)
    payload = comparison.to_dict()
    payload["status"] = "compared" if comparison.variants else "no_alternatives"
    payload["scenario"] = {"name": base.name, "version": base.version}
    payload["user_inputs"] = resolved_inputs.to_dict()
    payload["thickness_provenance"] = resolved_inputs.thickness_provenance()
    payload["interpretation"] = _interpretation(active, resolved_inputs)
    payload["percentile_convention"] = dict(PERCENTILE_CONVENTION)
    payload["note"] = (
        "No temperature method is authoritative. Temperature cannot be supplied "
        "as an engineering assumption; a well without a usable reservoir "
        "temperature stays blocked."
    )
    return payload


def screening_funnel(scenario: str | ScreeningScenario = DEFAULT_SCENARIO,
                     user_inputs: Mapping[str, Any] | UserInputs | None = None,
                     data_dir: str | Path = DEFAULT_DATA_DIR,
                     samples: int = 200, seed: int = 42) -> dict[str, Any]:
    """Fleet-level counts, keeping the completeness states distinct."""
    from ccs_screen.ingest.report import build_funnel

    records = load_records(data_dir)
    base = _scenario(scenario)
    samples = validate_samples(samples)
    if user_inputs is None:
        active = base
    else:
        supplied = (user_inputs if isinstance(user_inputs, UserInputs)
                    else UserInputs.from_mapping(user_inputs))
        active = _with_user_inputs(base, supplied)
    reports = [_screen_record(r, active, samples=samples, seed=seed) for r in records]
    payload = build_funnel(list(records), active, reports).to_dict()
    payload["interpretation"] = _interpretation(active)
    payload["required_user_inputs"] = list(REQUIRED_USER_INPUTS)
    return payload


def list_scenarios() -> list[dict[str, Any]]:
    """Built-in scenarios, with their evidence posture."""
    seen: dict[str, dict[str, Any]] = {}
    for key, scenario in BUILTIN_SCENARIOS.items():
        entry = seen.setdefault(scenario.name, {
            "name": scenario.name,
            "aliases": [],
            "version": scenario.version,
            "date": scenario.date,
            "description": scenario.description,
            "assumed_parameters": list(scenario.assumed_parameters),
            "evidence_classes": sorted({a.evidence_class.value for a in scenario.assumptions}),
            "literature_derived": all(a.is_literature_derived for a in scenario.assumptions)
                                  and bool(len(scenario.assumptions)),
            "supplies_user_inputs": [p for p in REQUIRED_USER_INPUTS
                                     if p in scenario.assumed_parameters],
        })
        entry["aliases"].append(key)
    for entry in seen.values():
        entry["aliases"].sort()
    return sorted(seen.values(), key=lambda e: e["name"])


def _blocked_for_user_inputs(record: NormalizedWellRecord, scenario: ScreeningScenario,
                             message: str) -> dict[str, Any]:
    """A structured refusal, never a default-filled result."""
    return {
        "status": "blocked",
        "reason": "missing_or_invalid_user_inputs",
        "well_id": record.canonical_id,
        "scenario": {"name": scenario.name, "version": scenario.version},
        "error": message,
        "required_user_inputs": [
            {"field": name, **USER_INPUT_SPEC[name]} for name in REQUIRED_USER_INPUTS
        ],
        "scenario_based_capacity_mt": None,
        "interpretation": _interpretation(scenario),
    }
