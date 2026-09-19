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
from ccs_screen.ingest.records import NormalizedWellRecord
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


def _interpretation(scenario: ScreeningScenario | None = None) -> dict[str, Any]:
    """Interpretation block, with any warnings the scenario earns.

    The scale-mismatch warning attaches when the scenario actually carries
    literature-derived values; a placeholder or empty scenario has no literature
    framing to mismatch. The block is rebuilt per call so the module constant
    never accumulates warnings across requests.
    """
    block = {k: (list(v) if isinstance(v, list) else v) for k, v in INTERPRETATION.items()}
    warnings: list[dict[str, Any]] = []
    if scenario is not None and any(a.is_literature_derived for a in scenario.assumptions):
        warnings.append(dict(SCALE_MISMATCH_WARNING))
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


@dataclass(frozen=True)
class UserInputs:
    """Caller-supplied geological inputs, validated.

    Deliberately has no defaults: constructing one without both values is an
    error, so there is no code path in which a screening runs on a filler.
    """

    area_m2: float
    thickness_m: float

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
        unknown = sorted(set(data) - set(REQUIRED_USER_INPUTS))
        if unknown:
            raise ApiError(
                f"unknown user input(s): {', '.join(unknown)} "
                f"(accepted: {', '.join(REQUIRED_USER_INPUTS)})"
            )
        missing = [n for n in REQUIRED_USER_INPUTS if n not in data]
        if missing:
            raise ApiError(
                f"missing required user input(s): {', '.join(missing)}. "
                f"These have no source data and no literature range, so they must "
                f"be supplied explicitly; they are never inferred."
            )
        return cls(area_m2=data["area_m2"], thickness_m=data["thickness_m"])

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

    payload: dict[str, Any] = {
        "status": "screened" if report.screenable else "blocked",
        "well_id": report.canonical_id,
        "scenario": {
            "name": base.name, "version": base.version, "date": base.date,
            "applied_as": active.name,
        },
        "user_inputs": resolved_inputs.to_dict(),
        "interpretation": _interpretation(active),
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
    if report.screenable and report.result is not None:
        payload["scenario_based_capacity_mt"] = {
            "p10": report.result.p10_mt,
            "p50": report.result.p50_mt,
            "p90": report.result.p90_mt,
            "mean": report.result.mean_mt,
            "n_samples": report.result.n_samples,
            "deterministic": report.result.deterministic,
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
    payload["interpretation"] = _interpretation(active)
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
