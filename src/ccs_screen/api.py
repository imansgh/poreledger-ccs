"""Public screening API.

A small, JSON-shaped boundary over the ingestion, scenario and screening layers.
The FastAPI app in ``ccs_screen.web`` is a thin translation of HTTP onto these
calls; no web framework is imported here.

Two explicitly separated paths
------------------------------
**Approved model** (``literature-screening-v1``, the default). The owner-approved
Phase 13 Model Contract (``docs/phase13-owner-decision-record.md``), implemented
in :mod:`ccs_screen.approved_model`. The caller supplies ``area_m2`` and the
storage-assessment interval ``z_top``, ``z_base``; ``h_g = z_base - z_top`` is
derived and there is no thickness input. Both named water-level scenarios,
``GROUND_REFERENCE`` and ``SEA_LEVEL_SENSITIVITY``, are always evaluated, each
with its own ``validation_status`` (``VALIDATED``,
``OUTSIDE_VALIDATED_ENVELOPE`` or ``UNAVAILABLE``) and diagnostics.

**Legacy scenarios** (``conservative``, ``central``, ``sensitivity``, ``none``,
and any scenario or assumption JSON file). Kept operational by owner decision
O2, with their existing inputs (``area_m2``, net ``thickness_m``) and their
existing arithmetic, and labelled ``validation_status = NOT_VALIDATED``. They
never carry an approved-model status.

The contract this module exists to enforce
------------------------------------------
Area, the storage interval and (on legacy paths) net thickness have no basis in
the source data and no literature range (see
``docs/scenario-literature-review.md``). So the public API makes them **required
inputs supplied by the caller**, with no defaults anywhere in the code path. A
request that omits them comes back ``blocked`` with a structured list of what is
needed and why -- never a number computed from a filler value.

None is ever inferred from licence boundaries, concession polygons, well
spacing, an arbitrary radius, total depth, stratigraphic units or gross
stratigraphic thickness.

Every result carries an ``interpretation`` block declaring the number to be
scenario-based and not site-specific.
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from ccs_screen.approved_model import (
    DIAGNOSTIC_MESSAGES,
    JOINT_SCENARIO_METHODOLOGY,
    PERCENTILE_INTERPRETATION,
    Availability,
    ApprovedModelResult,
    IntervalError,
    StorageInterval,
    ValidationStatus,
    depth_reference_diagnostic,
    evaluate_approved_model,
    is_approved_parameter_set,
)
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
    NOT_VALIDATED_STATEMENT,
    STORAGE_INTERVAL_POLICY_STATEMENT,
    ScreeningScenario,
    load_scenario,
    resolve_inputs,
)

DEFAULT_SCENARIO = "literature-screening-v1"
DEFAULT_DATA_DIR = "data"

#: ``model_path`` values. Every screening payload carries one.
APPROVED_MODEL_PATH = "APPROVED_MODEL"
LEGACY_MODEL_PATH = "LEGACY_NOT_VALIDATED"

#: The label every legacy output carries (owner decision O2).
NOT_VALIDATED = ValidationStatus.NOT_VALIDATED.value

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

#: Inputs the caller must supply on the approved model (the default path):
#: area and the storage-assessment interval (Model Contract M1, Final Gap
#: Closure A). There is no thickness input; h_g = z_base - z_top is derived.
APPROVED_REQUIRED_USER_INPUTS = ("area_m2", "z_top", "z_base")

#: Inputs the NOT_VALIDATED legacy scenarios require (owner decision O2: legacy
#: inputs are preserved). Both are absent from the source data and unsupported
#: by literature, and both are linear multipliers.
LEGACY_REQUIRED_USER_INPUTS = tuple(LITERATURE_UNSUPPORTED)

#: Required inputs of the default path, which is the approved model.
REQUIRED_USER_INPUTS = APPROVED_REQUIRED_USER_INPUTS

_INTERVAL_NOT_INFERRED_FROM = [
    "total well depth", "stratigraphic units", "gross stratigraphic thickness",
]

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
    "z_top": {
        "unit": "m",
        "label": "Storage interval top (z_top)",
        "description": (
            "Top of the designated storage-assessment interval: depth below ground "
            "level, in the same depth coordinate and datum as the well's depth_m."
        ),
        "policy": STORAGE_INTERVAL_POLICY_STATEMENT,
        "not_inferred_from": list(_INTERVAL_NOT_INFERRED_FROM),
        "minimum_inclusive": 0.0,
        "model_path": APPROVED_MODEL_PATH,
    },
    "z_base": {
        "unit": "m",
        "label": "Storage interval base (z_base)",
        "description": (
            "Base of the designated storage-assessment interval, deeper than z_top, "
            "in the same depth coordinate and datum. h_g = z_base - z_top (gross "
            "thickness of the interval) and z_state = (z_top + z_base) / 2 are derived."
        ),
        "policy": STORAGE_INTERVAL_POLICY_STATEMENT,
        "not_inferred_from": list(_INTERVAL_NOT_INFERRED_FROM),
        "minimum_exclusive": 0.0,
        "must_exceed": "z_top",
        "model_path": APPROVED_MODEL_PATH,
    },
    "thickness_m": {
        "unit": "m",
        "label": "Net storage thickness",
        "description": (
            "Net reservoir thickness inside the closure -- NOT the gross "
            "chronostratigraphic interval, which is 1-2 orders of magnitude larger. "
            "Legacy NOT_VALIDATED scenarios only; the approved model has no "
            "thickness input."
        ),
        "policy": NET_THICKNESS_POLICY_STATEMENT,
        "not_inferred_from": ["gross stratigraphic thickness", "total well depth"],
        "minimum_exclusive": 0.0,
        "model_path": LEGACY_MODEL_PATH,
    },
}


def required_inputs_for(scenario: ScreeningScenario) -> tuple[str, ...]:
    """The caller inputs the path this scenario belongs to requires."""
    if is_approved_parameter_set(scenario):
        return APPROVED_REQUIRED_USER_INPUTS
    return LEGACY_REQUIRED_USER_INPUTS

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

#: Interpretation block of the approved model.
APPROVED_INTERPRETATION = {
    "type": "scenario_based_capacity",
    "site_specific": False,
    "certified": False,
    "proven_resource": False,
    "basis": (
        "approved Model Contract (docs/phase13-owner-decision-record.md): "
        "literature-constrained priors, gross thickness h_g derived from a "
        "caller-designated storage-assessment interval, absolute EOS pressure at "
        "z_state, two named deterministic water-level scenarios, and a validated "
        "EOS envelope checked per realisation"
    ),
    "statement": (
        "Scenario-based screening capacity under the approved Model Contract. This "
        "is not a certified storage capacity, not a proven storage resource, and not "
        "a site-specific estimate. It is conditional on the user-supplied area and "
        "storage-assessment interval (z_top, z_base), for which no source data or "
        "literature range exists, and on two named deterministic water-level "
        "scenarios that are not measured formation heads."
    ),
    "area_policy": AREA_POLICY_STATEMENT,
    "storage_interval_policy": STORAGE_INTERVAL_POLICY_STATEMENT,
    "percentile_interpretation": PERCENTILE_INTERPRETATION,
    "joint_scenario_methodology": JOINT_SCENARIO_METHODOLOGY,
    "warnings": [],
}

#: The scale-mismatch disclosure on the approved path. DOE's E contains a
#: basin-scale area term; the contract discloses the mismatch with a
#: closure-scale area and does not resolve it (Model Contract row 2).
APPROVED_SCALE_MISMATCH_WARNING = {
    **SCALE_MISMATCH_WARNING,
    "detail": (
        "Storage efficiency (CSLF-T-2008-04 / DOE) is calibrated at basin/aquifer "
        "scale, with a basin-scale area term inside E, and porosity (Donda et al. "
        "2011) is a regional compilation, while area and the storage-assessment "
        "interval are supplied at closure scale. The mismatch is disclosed, not "
        "resolved; no correction factor is applied because none is derivable from "
        "the cited sources."
    ),
}

#: The Finding 12.5 disclosure where approved validated percentiles are reported.
APPROVED_UNCERTAINTY_BAND_WARNING = {
    **UNCERTAINTY_BAND_WARNING,
    "affects": ["water_level_scenarios.capacity_mt"],
}

#: Owner decision O2, as an interpretation warning, so a client that renders
#: warnings shows the label next to any legacy number.
NOT_VALIDATED_WARNING = {
    "code": "not_validated_legacy_path",
    "severity": "not_validated",
    "message": (
        "NOT_VALIDATED: this result comes from a legacy path outside the approved "
        "Model Contract."
    ),
    "detail": NOT_VALIDATED_STATEMENT,
    "affects": ["scenario_based_capacity_mt"],
    "invalidates_result": False,
    "correction_applied": False,
    "reference": "docs/phase13-owner-decision-record.md; Phase 14 owner decision O2",
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
                    band_reported: bool = False,
                    not_validated: bool = False) -> dict[str, Any]:
    """Legacy interpretation block, with any warnings the scenario earns.

    The scale-mismatch warning attaches when the scenario actually carries
    literature-derived values; a placeholder or empty scenario has no literature
    framing to mismatch. The block is rebuilt per call so the module constant
    never accumulates warnings across requests.

    Net-to-gross disclosure applies only when ``user_inputs`` is given, i.e. to a
    per-well result whose thickness_m the caller supplied. Fleet-level and
    input-free calls pass nothing and get no net-to-gross warning.
    ``band_reported`` attaches the Finding 12.5 disclosure when a P10-P90 band
    is actually in the payload. ``not_validated`` attaches the O2 label first.
    """
    block = {k: (list(v) if isinstance(v, list) else v) for k, v in INTERPRETATION.items()}
    warnings: list[dict[str, Any]] = []
    if not_validated:
        warnings.append(dict(NOT_VALIDATED_WARNING))
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


def _approved_interpretation(band_reported: bool = False) -> dict[str, Any]:
    """Interpretation block of the approved model, rebuilt per call.

    The scale-mismatch disclosure always attaches: the approved priors are
    literature-constrained. No net-to-gross warning attaches: on the approved
    path the gross-to-net reduction is represented inside E by construction
    (A4), and a declared net-to-gross is a consistency check only (S12).
    """
    block = {k: (list(v) if isinstance(v, list) else v)
             for k, v in APPROVED_INTERPRETATION.items()}
    warnings: list[dict[str, Any]] = [dict(APPROVED_SCALE_MISMATCH_WARNING)]
    if band_reported:
        warnings.append(dict(APPROVED_UNCERTAINTY_BAND_WARNING))
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

#: Approved model (A3, A4, A5, S12): the ratio refers to the designated
#: storage-assessment interval, and is a consistency/provenance check only.
APPROVED_NET_TO_GROSS_DEFINITION = (
    "h_net / h_g: the fraction of the designated storage-assessment interval "
    "(h_g = z_base - z_top) that satisfies the caller's declared reservoir-quality "
    "criterion. Not identified with DOE hn/hg. A consistency/provenance check only: "
    "with 0 < net_to_gross <= 1, 0 < h_net <= h_g holds by construction."
)

APPROVED_NET_TO_GROSS_USAGE_STATEMENT = (
    "net_to_gross is recorded as a consistency/provenance check only (S12). It never "
    "enters the capacity equation: the gross-to-net reduction is represented inside "
    "the aggregate storage efficiency E (A4, A5), and E is never divided by it."
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
    """Caller-supplied geological inputs for the NOT_VALIDATED legacy paths.

    Deliberately has no defaults for the two required inputs: constructing one
    without both values is an error, so there is no code path in which a
    screening runs on a filler. ``net_to_gross`` is optional provenance metadata
    about ``thickness_m`` and is never used in a calculation. The approved model
    takes :class:`ApprovedUserInputs` instead.
    """

    area_m2: float
    thickness_m: float
    net_to_gross: NetToGross | None = None

    def __post_init__(self) -> None:
        problems: list[str] = []
        for name in LEGACY_REQUIRED_USER_INPUTS:
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
        unknown = sorted(set(data) - set(LEGACY_REQUIRED_USER_INPUTS) - set(OPTIONAL_USER_INPUTS))
        if unknown:
            interval = sorted(set(unknown) & {"z_top", "z_base"})
            raise ApiError(
                f"unknown user input(s): {', '.join(unknown)} "
                f"(accepted: {', '.join(LEGACY_REQUIRED_USER_INPUTS + OPTIONAL_USER_INPUTS)})"
                + (". The storage interval (z_top, z_base) is an input of the approved "
                   "model only; NOT_VALIDATED legacy paths take area_m2 and thickness_m."
                   if interval else "")
            )
        missing = [n for n in LEGACY_REQUIRED_USER_INPUTS if n not in data]
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
            for name in LEGACY_REQUIRED_USER_INPUTS
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            name: {"value": getattr(self, name), "unit": USER_INPUT_SPEC[name]["unit"]}
            for name in LEGACY_REQUIRED_USER_INPUTS
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


#: Optional caller fields on the approved path. Never required, never used in a
#: calculation.
APPROVED_OPTIONAL_USER_INPUTS = ("net_to_gross",)

THICKNESS_NOT_AN_APPROVED_INPUT = (
    "thickness_m is not an input of the approved model: its thickness term is "
    "h_g = z_base - z_top, derived from the storage-assessment interval (Model "
    "Contract A1, M1). Supply z_top and z_base instead. thickness_m is accepted only "
    "by NOT_VALIDATED legacy scenarios."
)


def _finite_positive(name: str, value: Any, unit: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ApiError(f"{name}: expected a number in {unit}, got {type(value).__name__} ({value!r})")
    number = float(value)
    if not math.isfinite(number):
        raise ApiError(f"{name}: must be a finite number, got {value!r}")
    if number <= 0:
        raise ApiError(f"{name}: must be > 0 {unit}, got {number:g}")
    return number


@dataclass(frozen=True)
class ApprovedUserInputs:
    """Caller inputs of the approved model: area and the storage interval.

    No defaults. ``h_g`` and ``z_state`` are derived from the interval; there is
    no thickness input. ``net_to_gross`` is an optional consistency/provenance
    check (S12) and is never used in a calculation.
    """

    area_m2: float
    interval: StorageInterval
    net_to_gross: NetToGross | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "area_m2",
                           _finite_positive("area_m2", self.area_m2, "m2"))
        if not isinstance(self.interval, StorageInterval):
            raise ApiError(f"interval: expected StorageInterval, got {type(self.interval).__name__}")
        if self.net_to_gross is not None and not isinstance(self.net_to_gross, NetToGross):
            raise ApiError(f"net_to_gross: expected NetToGross or None, "
                           f"got {type(self.net_to_gross).__name__}")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "ApprovedUserInputs":
        """Build from a request body, naming anything missing or misplaced."""
        data = data or {}
        if not isinstance(data, Mapping):
            raise ApiError(f"user_inputs must be an object, got {type(data).__name__}")
        if "thickness_m" in data:
            raise ApiError(THICKNESS_NOT_AN_APPROVED_INPUT)
        accepted = APPROVED_REQUIRED_USER_INPUTS + APPROVED_OPTIONAL_USER_INPUTS
        unknown = sorted(set(data) - set(accepted))
        if unknown:
            raise ApiError(f"unknown user input(s): {', '.join(unknown)} "
                           f"(accepted: {', '.join(accepted)})")
        missing = [n for n in APPROVED_REQUIRED_USER_INPUTS if n not in data]
        if missing:
            raise ApiError(
                f"missing required user input(s): {', '.join(missing)}. "
                f"These have no source data and no literature range, so they must "
                f"be supplied explicitly; they are never inferred."
            )
        area = _finite_positive("area_m2", data["area_m2"], "m2")
        try:
            interval = StorageInterval(data["z_top"], data["z_base"])
        except IntervalError as exc:
            raise ApiError(str(exc)) from None
        raw_ntg = data.get("net_to_gross")
        return cls(
            area_m2=area, interval=interval,
            net_to_gross=NetToGross.from_mapping(raw_ntg) if raw_ntg is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "area_m2": {"value": self.area_m2, "unit": "m2"},
            "z_top": {"value": self.interval.z_top_m, "unit": "m"},
            "z_base": {"value": self.interval.z_base_m, "unit": "m"},
        }

    def net_to_gross_check(self) -> dict[str, Any]:
        """S12 consistency/provenance record. Metadata, never a model input."""
        ntg = self.net_to_gross
        return {
            "declared": ntg is not None,
            "net_to_gross": ({**ntg.to_dict(), "definition": APPROVED_NET_TO_GROSS_DEFINITION}
                             if ntg is not None else None),
            "relative_to": "h_g = z_base - z_top",
            "consistency": ("0 < h_net <= h_g holds by construction" if ntg is not None
                            else "not applicable -- no net-to-gross declared"),
            "used_in_calculation": False,
            "usage": APPROVED_NET_TO_GROSS_USAGE_STATEMENT,
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
    must not silently shadow what was asked for. Legacy paths only.
    """
    kept = tuple(a for a in base.assumptions if a.parameter not in LEGACY_REQUIRED_USER_INPUTS)
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


def _depth_reference_status(record: NormalizedWellRecord) -> dict[str, Any]:
    """The approved model's view of a well's depth reference (C2, O4)."""
    reason = depth_reference_diagnostic(record.depth_datum)
    return {
        "depth_datum": record.depth_datum.value,
        "status": (Availability.AVAILABLE if reason is None else Availability.UNAVAILABLE).value,
        "diagnostic": None if reason is None else reason.value,
        "message": None if reason is None else DIAGNOSTIC_MESSAGES[reason],
    }


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
            "depth_datum": record.depth_datum.value,
            "approved_model_depth_reference": _depth_reference_status(record),
        })
    return out


def get_well(well_id: str, data_dir: str | Path = DEFAULT_DATA_DIR) -> dict[str, Any]:
    """One well's normalized record, with full field-level provenance."""
    record = _record(well_id, data_dir)
    payload = record.to_dict()
    payload["required_user_inputs"] = list(REQUIRED_USER_INPUTS)
    payload["approved_model_depth_reference"] = _depth_reference_status(record)
    payload["interpretation"] = _approved_interpretation()
    return payload


def required_user_inputs(well_id: str, scenario: str | ScreeningScenario = DEFAULT_SCENARIO,
                         data_dir: str | Path = DEFAULT_DATA_DIR) -> dict[str, Any]:
    """What the caller must supply before this well can be screened.

    Reports the inputs of whichever path the scenario belongs to: ``area_m2``,
    ``z_top``, ``z_base`` for the approved model; ``area_m2``, ``thickness_m``
    for a NOT_VALIDATED legacy scenario.
    """
    record = _record(well_id, data_dir)
    base = _scenario(scenario)
    if is_approved_parameter_set(base):
        reference = _depth_reference_status(record)
        approved_blockers = ([] if reference["diagnostic"] is None else [{
            "field": "depth_datum",
            "reason": f"{reference['diagnostic']}: {reference['message']}",
        }])
        return {
            "well_id": record.canonical_id,
            "scenario": {"name": base.name, "version": base.version},
            "model_path": APPROVED_MODEL_PATH,
            "required": [
                {"field": name, **USER_INPUT_SPEC[name], "needed": True}
                for name in APPROVED_REQUIRED_USER_INPUTS
            ],
            "blocked_by_missing_source_data": approved_blockers,
            "can_be_screened_with_user_inputs": not approved_blockers,
            "depth_reference": reference,
            "interpretation": _approved_interpretation(),
        }

    _, missing = resolve_inputs(record, base)
    missing_names = {name for name, _ in missing}
    blockers = [
        {"field": name, "reason": reason}
        for name, reason in missing
        if name not in LEGACY_REQUIRED_USER_INPUTS
    ]
    return {
        "well_id": record.canonical_id,
        "scenario": {"name": base.name, "version": base.version},
        "model_path": LEGACY_MODEL_PATH,
        "validation_status": NOT_VALIDATED,
        "required": [
            {"field": name, **USER_INPUT_SPEC[name], "needed": name in missing_names}
            for name in LEGACY_REQUIRED_USER_INPUTS
        ],
        "blocked_by_missing_source_data": blockers,
        "can_be_screened_with_user_inputs": not blockers,
        "interpretation": _interpretation(base, not_validated=True),
    }


def screen_well(well_id: str,
                user_inputs: Mapping[str, Any] | UserInputs | ApprovedUserInputs | None = None,
                scenario: str | ScreeningScenario = DEFAULT_SCENARIO,
                data_dir: str | Path = DEFAULT_DATA_DIR,
                samples: int = DEFAULT_SAMPLES, seed: int = 42) -> dict[str, Any]:
    """Screen one well under a scenario plus caller-supplied inputs.

    ``literature-screening-v1`` (the default) runs the approved model: both
    named water-level scenarios, each with its own ``validation_status`` and
    diagnostics (``"status": "evaluated"``). Any other scenario runs the
    NOT_VALIDATED legacy path unchanged (``"status": "screened"``).

    When a required input is missing or invalid the result has
    ``"status": "blocked"`` and lists what is needed -- no default is ever
    substituted to make a number appear.

    ``samples`` must be an integer in [MIN_SAMPLES, MAX_SAMPLES]; an
    out-of-range value raises :class:`ApiError` rather than being clamped.
    """
    record = _record(well_id, data_dir)
    base = _scenario(scenario)
    samples = validate_samples(samples)
    if is_approved_parameter_set(base):
        return _screen_approved(record, base, user_inputs, samples, seed)
    return _screen_legacy(record, base, user_inputs, samples, seed)


def _screen_approved(record: NormalizedWellRecord, base: ScreeningScenario,
                     user_inputs: Any, samples: int, seed: int) -> dict[str, Any]:
    try:
        if isinstance(user_inputs, UserInputs):
            raise ApiError(THICKNESS_NOT_AN_APPROVED_INPUT)
        inputs = (user_inputs if isinstance(user_inputs, ApprovedUserInputs)
                  else ApprovedUserInputs.from_mapping(user_inputs))
    except ApiError as exc:
        return _approved_blocked(record, base, str(exc))

    result = evaluate_approved_model(record, area_m2=inputs.area_m2, interval=inputs.interval,
                                     n=samples, seed=seed)
    return _approved_payload(base, inputs, result)


def _approved_payload(base: ScreeningScenario, inputs: ApprovedUserInputs,
                      result: ApprovedModelResult) -> dict[str, Any]:
    body = result.to_dict()
    band_reported = False
    for entry in body["water_level_scenarios"]:
        if entry["capacity_mt"] is not None:
            band_reported = True
            # Disclosure only (Findings 7.5, 12.5); no value is altered.
            entry["capacity_mt"]["percentile_convention"] = dict(PERCENTILE_CONVENTION)
            entry["capacity_mt"]["uncertainty_band"] = dict(UNCERTAINTY_BAND_DISCLOSURE)
        if entry["diagnostic_capacity_mt"] is not None:
            entry["diagnostic_capacity_mt"]["percentile_convention"] = dict(PERCENTILE_CONVENTION)
    return {
        "status": "evaluated",
        **body,
        "scenario": {"name": base.name, "version": base.version, "date": base.date,
                     "applied_as": "approved-model"},
        "user_inputs": inputs.to_dict(),
        "net_to_gross_check": inputs.net_to_gross_check(),
        "interpretation": _approved_interpretation(band_reported),
    }


def _approved_blocked(record: NormalizedWellRecord, scenario: ScreeningScenario,
                      message: str) -> dict[str, Any]:
    """A structured refusal on the approved path, never a default-filled result."""
    return {
        "status": "blocked",
        "model_path": APPROVED_MODEL_PATH,
        "reason": "missing_or_invalid_user_inputs",
        "well_id": record.canonical_id,
        "scenario": {"name": scenario.name, "version": scenario.version},
        "error": message,
        "required_user_inputs": [
            {"field": name, **USER_INPUT_SPEC[name]} for name in APPROVED_REQUIRED_USER_INPUTS
        ],
        "water_level_scenarios": [],
        "interpretation": _approved_interpretation(),
    }


def _screen_legacy(record: NormalizedWellRecord, base: ScreeningScenario,
                   user_inputs: Any, samples: int, seed: int) -> dict[str, Any]:
    """The pre-contract path, unchanged in arithmetic and labelled NOT_VALIDATED (O2)."""
    try:
        if isinstance(user_inputs, ApprovedUserInputs):
            raise ApiError(
                "the storage interval (z_top, z_base) is an input of the approved model "
                "only; NOT_VALIDATED legacy scenarios take area_m2 and thickness_m"
            )
        resolved_inputs = (user_inputs if isinstance(user_inputs, UserInputs)
                           else UserInputs.from_mapping(user_inputs))
    except ApiError as exc:
        return _blocked_for_user_inputs(record, base, str(exc))

    active = _with_user_inputs(base, resolved_inputs)
    report = _screen_record(record, active, samples=samples, seed=seed)
    band_reported = report.screenable and report.result is not None

    payload: dict[str, Any] = {
        "status": "screened" if report.screenable else "blocked",
        "model_path": LEGACY_MODEL_PATH,
        "validation_status": NOT_VALIDATED,
        "well_id": report.canonical_id,
        "scenario": {
            "name": base.name, "version": base.version, "date": base.date,
            "applied_as": active.name,
        },
        "user_inputs": resolved_inputs.to_dict(),
        "thickness_provenance": resolved_inputs.thickness_provenance(),
        "interpretation": _interpretation(active, resolved_inputs, band_reported,
                                          not_validated=True),
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
            "validation_status": NOT_VALIDATED,
            # Disclosure only (Findings 7.5, 12.5); no value above is altered.
            "percentile_convention": dict(PERCENTILE_CONVENTION),
            "uncertainty_band": dict(UNCERTAINTY_BAND_DISCLOSURE),
        }
    else:
        payload["scenario_based_capacity_mt"] = None
        payload["missing_fields"] = list(report.missing_fields)
        payload["missing_reasons"] = {k: v for k, v in report.missing_reasons}
    return payload


#: O2 consequence 2: the comparison runs the legacy resolver and the legacy
#: ingestion-time temperature machinery.
TEMPERATURE_COMPARISON_NOT_VALIDATED = (
    "NOT_VALIDATED legacy diagnostic (owner decision O2). The comparison runs the "
    "legacy scenario resolver and the legacy ingestion-time temperature selection, "
    "not the approved model. Under the approved model, temperature is selected by "
    "the M3/R1 rule and reported in the screening result's temperature_selection."
)

COMPARISON_NEEDS_LEGACY_INPUTS = (
    "The temperature-method comparison is a NOT_VALIDATED legacy diagnostic: it "
    "needs the legacy inputs area_m2 and thickness_m, not the approved model's "
    "storage interval (z_top, z_base). Under the approved model, temperature is "
    "selected by the M3/R1 rule and reported in the screening result's "
    "temperature_selection."
)


def compare_temperature_methods(
    well_id: str, user_inputs: Mapping[str, Any] | UserInputs | None = None,
    scenario: str | ScreeningScenario = DEFAULT_SCENARIO,
    data_dir: str | Path = DEFAULT_DATA_DIR,
    samples: int = 500, seed: int = 42,
) -> dict[str, Any]:
    """What each available temperature method implies for capacity.

    A NOT_VALIDATED legacy diagnostic for every scenario (O2 consequence 2),
    with the legacy inputs ``area_m2`` and ``thickness_m``.
    """
    record = _record(well_id, data_dir)
    base = _scenario(scenario)
    samples = validate_samples(samples)
    try:
        if isinstance(user_inputs, ApprovedUserInputs) or (
                isinstance(user_inputs, Mapping) and {"z_top", "z_base"} & set(user_inputs)):
            raise ApiError(COMPARISON_NEEDS_LEGACY_INPUTS)
        resolved_inputs = (user_inputs if isinstance(user_inputs, UserInputs)
                           else UserInputs.from_mapping(user_inputs))
    except ApiError as exc:
        return _blocked_for_user_inputs(record, base, str(exc))

    active = _with_user_inputs(base, resolved_inputs)
    comparison = _compare_methods(record, active, samples=samples, seed=seed)
    payload = comparison.to_dict()
    payload["status"] = "compared" if comparison.variants else "no_alternatives"
    payload["model_path"] = LEGACY_MODEL_PATH
    payload["validation_status"] = NOT_VALIDATED
    payload["validation_note"] = TEMPERATURE_COMPARISON_NOT_VALIDATED
    payload["scenario"] = {"name": base.name, "version": base.version}
    payload["user_inputs"] = resolved_inputs.to_dict()
    payload["thickness_provenance"] = resolved_inputs.thickness_provenance()
    payload["interpretation"] = _interpretation(active, resolved_inputs, not_validated=True)
    payload["percentile_convention"] = dict(PERCENTILE_CONVENTION)
    payload["note"] = (
        "No temperature method is authoritative. Temperature cannot be supplied "
        "as an engineering assumption; a well without a usable reservoir "
        "temperature stays blocked."
    )
    return payload


FLEET_INTERVAL_NOT_DEFINED = (
    "The approved model needs a storage-assessment interval (z_top, z_base) designated "
    "for each well (Model Contract M1); a single fleet-level interval is not defined, "
    "so fleet-level user inputs are not accepted for the approved model."
)


def screening_funnel(scenario: str | ScreeningScenario = DEFAULT_SCENARIO,
                     user_inputs: Mapping[str, Any] | UserInputs | None = None,
                     data_dir: str | Path = DEFAULT_DATA_DIR,
                     samples: int = 200, seed: int = 42) -> dict[str, Any]:
    """Fleet-level counts, keeping the completeness states distinct.

    Under the approved model the funnel reports depth-reference readiness only:
    an approved result needs a per-well interval, so none is computed here.
    Under a legacy scenario it is the existing funnel, labelled NOT_VALIDATED.
    """
    from ccs_screen.ingest.report import build_funnel

    records = load_records(data_dir)
    base = _scenario(scenario)
    samples = validate_samples(samples)
    if is_approved_parameter_set(base):
        if user_inputs is not None:
            raise ApiError(FLEET_INTERVAL_NOT_DEFINED)
        return _approved_funnel(records, base)

    if user_inputs is None:
        active = base
    else:
        supplied = (user_inputs if isinstance(user_inputs, UserInputs)
                    else UserInputs.from_mapping(user_inputs))
        active = _with_user_inputs(base, supplied)
    reports = [_screen_record(r, active, samples=samples, seed=seed) for r in records]
    payload = build_funnel(list(records), active, reports).to_dict()
    payload["model_path"] = LEGACY_MODEL_PATH
    payload["validation_status"] = NOT_VALIDATED
    payload["interpretation"] = _interpretation(active, not_validated=True)
    payload["required_user_inputs"] = list(LEGACY_REQUIRED_USER_INPUTS)
    return payload


def _approved_funnel(records: tuple[NormalizedWellRecord, ...],
                     base: ScreeningScenario) -> dict[str, Any]:
    by_reference: dict[str, int] = {"ESTABLISHED_GROUND_LEVEL": 0}
    for record in records:
        reason = depth_reference_diagnostic(record.depth_datum)
        key = "ESTABLISHED_GROUND_LEVEL" if reason is None else reason.value
        by_reference[key] = by_reference.get(key, 0) + 1
    return {
        "model_path": APPROVED_MODEL_PATH,
        "scenario": {"name": base.name, "version": base.version},
        "total_wells": len(records),
        "depth_reference": by_reference,
        "approved_results_computed": 0,
        "note": (
            "An approved result needs a storage-assessment interval designated for each "
            "well and an established ground-level depth reference (C2). Wells without an "
            "established reference return UNAVAILABLE for both named water-level "
            "scenarios. No capacity is computed at fleet level."
        ),
        "required_user_inputs": list(APPROVED_REQUIRED_USER_INPUTS),
        "interpretation": _approved_interpretation(),
    }


def list_scenarios() -> list[dict[str, Any]]:
    """Built-in scenarios, with their evidence posture and validation status."""
    seen: dict[str, dict[str, Any]] = {}
    for key, scenario in BUILTIN_SCENARIOS.items():
        approved = is_approved_parameter_set(scenario)
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
            "supplies_user_inputs": ([] if approved else
                                     [p for p in LEGACY_REQUIRED_USER_INPUTS
                                      if p in scenario.assumed_parameters]),
            "validation_status": APPROVED_MODEL_PATH if approved else NOT_VALIDATED,
            "model_path": APPROVED_MODEL_PATH if approved else LEGACY_MODEL_PATH,
            "required_user_inputs": list(required_inputs_for(scenario)),
        })
        entry["aliases"].append(key)
    for entry in seen.values():
        entry["aliases"].sort()
    return sorted(seen.values(), key=lambda e: e["name"])


def _blocked_for_user_inputs(record: NormalizedWellRecord, scenario: ScreeningScenario,
                             message: str) -> dict[str, Any]:
    """A structured refusal on a legacy path, never a default-filled result."""
    return {
        "status": "blocked",
        "model_path": LEGACY_MODEL_PATH,
        "validation_status": NOT_VALIDATED,
        "reason": "missing_or_invalid_user_inputs",
        "well_id": record.canonical_id,
        "scenario": {"name": scenario.name, "version": scenario.version},
        "error": message,
        "required_user_inputs": [
            {"field": name, **USER_INPUT_SPEC[name]} for name in LEGACY_REQUIRED_USER_INPUTS
        ],
        "scenario_based_capacity_mt": None,
        "interpretation": _interpretation(scenario, not_validated=True),
    }
