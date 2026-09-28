"""The approved screening model (Phase 13 Model Contract, frozen).

This module implements the owner-approved Model Contract recorded in
``docs/phase13-owner-decision-record.md`` ("Final Gap Closure", "O1 Decision and
Owner-Approval Gate", "Owner Approval"). It is the only code path whose results
may carry the statuses ``VALIDATED``, ``OUTSIDE_VALIDATED_ENVELOPE`` or
``UNAVAILABLE``; every other screening path in this package is a legacy path and
is labelled ``NOT_VALIDATED``.

Capacity (A1, A4, M1)::

    M = A * h_g * phi * rho_CO2(P_EOS, T) * E

* ``A`` -- caller-supplied structural closure area (PROVISIONAL, row 2).
* ``h_g = z_base - z_top`` -- gross thickness of the designated
  storage-assessment interval, **derived** from the caller's ``z_top`` and
  ``z_base``; there is no independent thickness input (Final Gap Closure A).
* ``z_state = (z_top + z_base) / 2`` -- PROJECT MODEL CONVENTION (S1), not a
  physical law.
* ``P_EOS = P_atm + rho_brine * g * (z_state - z_wl)`` with
  ``P_atm = 101 325 Pa`` (B1, PROJECT MODEL CONSTANT). ``z_wl = 0`` for
  ``GROUND_REFERENCE`` and ``z_wl = quota`` (ground elevation above sea level)
  for ``SEA_LEVEL_SENSITIVITY`` (M2). Both are deterministic named scenarios,
  never sampled, and each is evaluated separately.
* ``T`` -- one real, corrected observation selected by M3 + R1 + C3; never
  interpolated, never newly corrected.
* ``rho_CO2`` -- Peng-Robinson with a constant Peneloux shift (E1), checked per
  Monte Carlo realisation against the validated envelope 1-35 MPa on ``P_EOS``
  and 280-400 K (M4, C1). Flag and block: no realisation is ever discarded.

Depth reference (C2, O4). Every depth used here -- ``z_top``, ``z_base``,
``z_state``, the recorded total depth and each temperature observation depth --
must be in ``depth_m``'s coordinate with an explicitly established
ground-level reference. ``unknown`` gives ``DEPTH_REFERENCE_NOT_ESTABLISHED``;
``msl``, ``rotary_table`` and ``kelly_bushing`` give
``UNSUPPORTED_DEPTH_DATUM``. No datum conversion is ever applied. Every
ingested well is currently ``unknown``, so every real well's approved result is
``UNAVAILABLE`` -- the consequence the contract records, not a defect.

Nothing here invents a value. Where the contract's inputs are not available,
the result says ``UNAVAILABLE`` and names the reason.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

from ccs_screen.ingest.assumptions import Citation
from ccs_screen.ingest.provenance import TemperatureMethod
from ccs_screen.ingest.records import NormalizedWellRecord, TemperatureObservation
from ccs_screen.ingest.scenario import (
    LITERATURE_SCREENING_V1,
    STANDARD_GRAVITY_M_S2,
    STORAGE_EFFICIENCY_PRIOR_STATEMENT,
    ScreeningScenario,
)
from ccs_screen.ingest.units import DepthDatum
from ccs_screen.monte_carlo import CapacitySample, McResult, run_capacity_mc
from ccs_screen.properties import (
    VALIDATED_ENVELOPE_PRESSURE_PA,
    VALIDATED_ENVELOPE_TEMPERATURE_K,
)

CONTRACT_REFERENCE = "docs/phase13-owner-decision-record.md"

CAPACITY_EQUATION = "M = A * h_g * phi * rho_CO2(P_EOS, T) * E"
PRESSURE_EQUATION = "P_EOS = 101325 Pa + rho_brine * g * (z_state - z_wl)"

#: B1 -- PROJECT MODEL CONSTANT. The standard atmosphere is 101 325 Pa, exact by
#: definition; using it as the surface pressure is a project model convention
#: (the cited regional methodology uses 1 atm at the surface, audit Finding 9.7).
P_ATM_PA = 101_325.0

#: Floating-point hygiene only. The contract's "exactly the same" depth,
#: distance and value are compared with this absolute tolerance, so that
#: rounding in (z_top + z_base) / 2 cannot split a tie that is exact in real
#: arithmetic. It is far below the resolution of any source value (0.1 m,
#: 0.01 K) and is not a scientific tolerance.
EXACT_TIE_TOLERANCE = 1e-9

#: M3 (1): the only temperature methods that can qualify.
ELIGIBLE_TEMPERATURE_METHODS: tuple[TemperatureMethod, ...] = (
    TemperatureMethod.HORNER,
    TemperatureMethod.FERTL_WICHMANN,
    TemperatureMethod.SQUARCI_TAFFI,
)

#: The approved Monte Carlo parameter set is carried by this built-in scenario.
#: Only this exact object selects the approved model; a JSON scenario file, a
#: copy or a derived scenario never does.
APPROVED_PARAMETER_SET: ScreeningScenario = LITERATURE_SCREENING_V1

STATE_POINT_CONVENTION = (
    "PROJECT MODEL CONVENTION (S1): z_state = (z_top + z_base) / 2. "
    "Not a physical law."
)

STORAGE_INTERVAL_REQUIREMENT = (
    "z_top and z_base are explicit caller inputs for the designated "
    "storage-assessment interval, in the same depth coordinate and datum as the "
    "well's depth_m (depth below ground level, positive downwards). They are "
    "never inferred from total depth or from stratigraphic units. "
    "h_g = z_base - z_top is derived; there is no independent thickness input."
)

#: S7, stated wherever validated percentiles are reported.
PERCENTILE_INTERPRETATION = (
    "P10/P50/P90 represent statistical/model uncertainty conditional on the "
    "declared model. They are not total accuracy and not bounds on systematic "
    "bias. Systematic effects are reported separately, as named water-level "
    "scenarios."
)

#: F1, stated on every approved result.
JOINT_SCENARIO_METHODOLOGY = (
    "Single joint scenario evaluation (F1): each named water-level scenario is "
    "one coherent pressure, temperature and EOS state. GROUND_REFERENCE is the "
    "baseline; the individual systematic effect under this contract is "
    "SEA_LEVEL_SENSITIVITY vs GROUND_REFERENCE. No multiplied correction factor "
    "is computed, and no scenario contrast is a correction or a measured bias."
)

OUTSIDE_ENVELOPE_STATEMENT = (
    "At least one Monte Carlo realisation lies outside the validated EOS "
    "envelope (1-35 MPa on P_EOS, 280-400 K). Validated percentiles are "
    "blocked. No realisation was discarded. Outside the validated envelope is "
    "not the same as physically impossible."
)

DIAGNOSTIC_CAPACITY_LABEL = (
    "DIAGNOSTIC ONLY -- NOT VALIDATED. Computed over every realisation, "
    "including those outside the validated EOS envelope. Not a validated "
    "screening result and not to be reported as one."
)


class WaterLevelScenario(str, Enum):
    """M2: the two named deterministic water-level scenarios."""

    GROUND_REFERENCE = "GROUND_REFERENCE"
    SEA_LEVEL_SENSITIVITY = "SEA_LEVEL_SENSITIVITY"


WATER_LEVEL_SCENARIO_INFO: dict[WaterLevelScenario, dict[str, str]] = {
    WaterLevelScenario.GROUND_REFERENCE: {
        "role": "baseline",
        "label": "PROJECT REFERENCE SCENARIO -- not a measured formation head",
        "description": (
            "Formation-head reference at ground elevation: z_wl = 0 in depth_m's "
            "ground-referenced coordinate. The reference/baseline scenario because "
            "it matches the pre-contract implicit model state (M2)."
        ),
        "z_wl_definition": "z_wl = 0 (ground level)",
    },
    WaterLevelScenario.SEA_LEVEL_SENSITIVITY: {
        "role": "sensitivity",
        "label": "SENSITIVITY SCENARIO -- not a measured formation head",
        "description": (
            "Formation-head reference at sea level: z_wl = quota, the ground "
            "elevation above sea level, in depth_m's ground-referenced coordinate "
            "(M2)."
        ),
        "z_wl_definition": "z_wl = quota (ground elevation above mean sea level)",
    },
}

#: Every named scenario is evaluated separately, always both, in this order.
WATER_LEVEL_SCENARIOS: tuple[WaterLevelScenario, ...] = (
    WaterLevelScenario.GROUND_REFERENCE,
    WaterLevelScenario.SEA_LEVEL_SENSITIVITY,
)

WATER_LEVEL_SCENARIO_STATEMENT = (
    "GROUND_REFERENCE and SEA_LEVEL_SENSITIVITY are named deterministic "
    "scenarios. They are not measured values, confidence intervals, probability "
    "distributions or Monte Carlo priors, and they are not claimed to bound the "
    "formation head. Water level is never sampled."
)


class ValidationStatus(str, Enum):
    """Status vocabulary for approved-model results and legacy labels."""

    VALIDATED = "VALIDATED"
    OUTSIDE_VALIDATED_ENVELOPE = "OUTSIDE_VALIDATED_ENVELOPE"
    UNAVAILABLE = "UNAVAILABLE"
    #: Legacy paths and non-approved outputs. Never produced by this module's
    #: own evaluation.
    NOT_VALIDATED = "NOT_VALIDATED"


class Availability(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class Diagnostic(str, Enum):
    """Machine-readable reasons attached to approved-model results."""

    # Depth reference (C2, O4).
    DEPTH_REFERENCE_NOT_ESTABLISHED = "DEPTH_REFERENCE_NOT_ESTABLISHED"
    UNSUPPORTED_DEPTH_DATUM = "UNSUPPORTED_DEPTH_DATUM"
    # Water level (M2).
    SURFACE_ELEVATION_UNAVAILABLE = "SURFACE_ELEVATION_UNAVAILABLE"
    STATE_POINT_ABOVE_WATER_LEVEL = "STATE_POINT_ABOVE_WATER_LEVEL"
    # Temperature: per-observation exclusion reasons (M3, S5, S11, C2).
    METHOD_NOT_ELIGIBLE = "METHOD_NOT_ELIGIBLE"
    OUTSIDE_STORAGE_INTERVAL = "OUTSIDE_STORAGE_INTERVAL"
    BELOW_RECORDED_TOTAL_DEPTH = "BELOW_RECORDED_TOTAL_DEPTH"
    TOTAL_DEPTH_NOT_RECORDED = "TOTAL_DEPTH_NOT_RECORDED"
    # Temperature: selection outcomes (M3, R1, C3, deferred guard).
    NO_ELIGIBLE_TEMPERATURE_OBSERVATION = "NO_ELIGIBLE_TEMPERATURE_OBSERVATION"
    TEMPERATURE_SAME_METHOD_CONFLICT = "TEMPERATURE_SAME_METHOD_CONFLICT"
    TEMPERATURE_METHOD_TIE_UNRESOLVED = "TEMPERATURE_METHOD_TIE_UNRESOLVED"
    EQUAL_DISTANCE_SHALLOWER_SELECTED = "EQUAL_DISTANCE_SHALLOWER_SELECTED"
    SAME_DEPTH_SQUARCI_TAFFI_CONVENTION = "SAME_DEPTH_SQUARCI_TAFFI_CONVENTION"
    TEMPERATURE_UNAVAILABLE = "TEMPERATURE_UNAVAILABLE"
    # EOS envelope (M4, C1).
    OUTSIDE_VALIDATED_ENVELOPE = "OUTSIDE_VALIDATED_ENVELOPE"
    EOS_NOT_EVALUABLE = "EOS_NOT_EVALUABLE"


DIAGNOSTIC_MESSAGES: dict[Diagnostic, str] = {
    Diagnostic.DEPTH_REFERENCE_NOT_ESTABLISHED: (
        "The depth reference is not formally established (datum 'unknown'). Under "
        "C2 the affected input is unavailable, no silent correction is applied and "
        "no approved capacity is produced."
    ),
    Diagnostic.UNSUPPORTED_DEPTH_DATUM: (
        "The depth is referenced to a datum other than ground level, and the "
        "approved contract provides no conversion to the ground-referenced "
        "coordinate. No conversion, equivalence or offset is applied (O4)."
    ),
    Diagnostic.SURFACE_ELEVATION_UNAVAILABLE: (
        "SEA_LEVEL_SENSITIVITY needs the ground elevation above sea level "
        "(quota), which this well does not record."
    ),
    Diagnostic.STATE_POINT_ABOVE_WATER_LEVEL: (
        "z_state lies above the scenario water level (z_state - z_wl < 0), so the "
        "gauge term of P_EOS is negative."
    ),
    Diagnostic.METHOD_NOT_ELIGIBLE: (
        "Only Horner-corrected, Fertl-Wichmann and Squarci-Taffi observations "
        "qualify (M3, S5). Non-stabilised, raw, unknown and surface-air values "
        "never qualify."
    ),
    Diagnostic.OUTSIDE_STORAGE_INTERVAL: (
        "The observation depth is not inside [z_top, z_base] (M3)."
    ),
    Diagnostic.BELOW_RECORDED_TOTAL_DEPTH: (
        "The observation is deeper than the recorded total depth and is excluded "
        "while the depth/datum inconsistency is unresolved (S11, M3)."
    ),
    Diagnostic.TOTAL_DEPTH_NOT_RECORDED: (
        "No total depth is recorded, so the below-total-depth exclusion (S11) "
        "cannot be verified; the observation does not qualify."
    ),
    Diagnostic.NO_ELIGIBLE_TEMPERATURE_OBSERVATION: (
        "No observation qualifies under M3; temperature is unavailable and no "
        "approved EOS capacity result is produced."
    ),
    Diagnostic.TEMPERATURE_SAME_METHOD_CONFLICT: (
        "Two or more observations from the same method at the selected depth have "
        "different values. No value is chosen (R1-2, C3)."
    ),
    Diagnostic.TEMPERATURE_METHOD_TIE_UNRESOLVED: (
        "Horner-corrected and Fertl-Wichmann observations share the selected "
        "depth with no Squarci-Taffi observation. This case is DEFERRED to a "
        "future owner rule; the guard selects no value and reports the conflict."
    ),
    Diagnostic.EQUAL_DISTANCE_SHALLOWER_SELECTED: (
        "Observations at different depths were equally close to z_state; the "
        "shallower was kept. PROJECT SELECTION CONVENTION (R1-1), not a claim "
        "that shallower temperatures are more accurate."
    ),
    Diagnostic.SAME_DEPTH_SQUARCI_TAFFI_CONVENTION: (
        "Different eligible methods at the selected depth; Squarci-Taffi was used "
        "as the deterministic project tie-break (R1-3). Not an accuracy ranking."
    ),
    Diagnostic.TEMPERATURE_UNAVAILABLE: (
        "No approved temperature is available, so no approved EOS capacity result "
        "is produced for this scenario."
    ),
    Diagnostic.OUTSIDE_VALIDATED_ENVELOPE: OUTSIDE_ENVELOPE_STATEMENT,
    Diagnostic.EOS_NOT_EVALUABLE: (
        "At least one realisation has P_EOS <= 0 Pa, where the EOS cannot be "
        "evaluated, so no diagnostic capacity is computed. No realisation was "
        "discarded."
    ),
}


def diagnostic(code: Diagnostic, **details: Any) -> dict[str, Any]:
    """One diagnostic entry: code, fixed message, and any structured detail."""
    entry: dict[str, Any] = {"code": code.value, "message": DIAGNOSTIC_MESSAGES[code]}
    entry.update(details)
    return entry


# -- depth reference (C2, O4) -------------------------------------------------


def depth_reference_diagnostic(datum: DepthDatum | None) -> Diagnostic | None:
    """``None`` when the datum is usable (ground level), else the reason.

    Applies equally to ``depth_m`` (and so to the interval, pressure and the
    total-depth exclusion) and to every temperature-observation depth.
    """
    if datum is DepthDatum.GROUND_LEVEL:
        return None
    if datum is None or datum is DepthDatum.UNKNOWN:
        return Diagnostic.DEPTH_REFERENCE_NOT_ESTABLISHED
    return Diagnostic.UNSUPPORTED_DEPTH_DATUM


# -- storage interval (M1, Final Gap Closure A) -------------------------------


class IntervalError(ValueError):
    """A supplied storage interval is not a valid depth pair."""


def _as_depth(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise IntervalError(f"{name}: expected a number in m, got {type(value).__name__} ({value!r})")
    number = float(value)
    if not math.isfinite(number):
        raise IntervalError(f"{name}: must be a finite number, got {value!r}")
    return number


@dataclass(frozen=True)
class StorageInterval:
    """The designated storage-assessment interval, as supplied by the caller.

    Depths are in ``depth_m``'s coordinate: metres below the depth reference,
    positive downwards. Validity here is input hygiene only (finite,
    ``0 <= z_top < z_base``); whether the depths are *defensible* depends on the
    well's depth reference, which :func:`evaluate_approved_model` checks.
    """

    z_top_m: float
    z_base_m: float

    def __post_init__(self) -> None:
        top = _as_depth("z_top", self.z_top_m)
        base = _as_depth("z_base", self.z_base_m)
        problems = []
        if top < 0:
            problems.append(f"z_top: must be >= 0 m (depth below the reference), got {top:g}")
        if base < 0:
            problems.append(f"z_base: must be >= 0 m (depth below the reference), got {base:g}")
        if not problems and not top < base:
            problems.append(
                f"z_top must be shallower than z_base (z_top < z_base), got "
                f"z_top = {top:g} m, z_base = {base:g} m"
            )
        if problems:
            raise IntervalError("; ".join(problems))
        object.__setattr__(self, "z_top_m", top)
        object.__setattr__(self, "z_base_m", base)

    @property
    def h_g_m(self) -> float:
        """Derived gross storage-assessment thickness, ``z_base - z_top``."""
        return self.z_base_m - self.z_top_m

    @property
    def z_state_m(self) -> float:
        """Derived state-point depth, the PROJECT MODEL CONVENTION midpoint."""
        return (self.z_top_m + self.z_base_m) / 2.0

    def contains(self, depth_m: float) -> bool:
        """Inside the closed interval ``[z_top, z_base]``."""
        return self.z_top_m <= depth_m <= self.z_base_m


# -- pressure (B1, M2) --------------------------------------------------------


def eos_pressure_pa(brine_density_kg_m3: Any, z_state_m: float, z_wl_m: float) -> Any:
    """``P_EOS = P_atm + rho_brine * g * (z_state - z_wl)`` (absolute, Pa).

    Accepts a scalar or an array of brine densities.
    """
    return P_ATM_PA + brine_density_kg_m3 * STANDARD_GRAVITY_M_S2 * (z_state_m - z_wl_m)


def water_level_depth_m(scenario: WaterLevelScenario,
                        record: NormalizedWellRecord) -> float | None:
    """``z_wl`` for a named scenario, or ``None`` when it cannot be formed."""
    if scenario is WaterLevelScenario.GROUND_REFERENCE:
        return 0.0
    quota = record.surface_elevation_m
    if not quota.is_present:
        return None
    try:
        value = float(quota.value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


# -- temperature selection (M3 + R1 + C3) --------------------------------------


def _method(observation: TemperatureObservation) -> TemperatureMethod | None:
    try:
        return TemperatureMethod(observation.method)
    except ValueError:
        return None


def _observation_dict(observation: TemperatureObservation,
                      z_state_m: float | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "depth_m": observation.depth_m,
        "temperature_k": observation.temperature_k,
        "method": observation.method,
        "depth_datum": (observation.depth_datum.value
                        if observation.depth_datum is not None else None),
        "source": str(observation.source) if observation.source else None,
    }
    if observation.original_celsius is not None:
        out["original_celsius"] = observation.original_celsius
    if z_state_m is not None:
        out["distance_to_z_state_m"] = abs(observation.depth_m - z_state_m)
    return out


@dataclass(frozen=True)
class TemperatureSelection:
    """Outcome of M3 + R1 + C3 for one well and interval."""

    status: Availability
    temperature_k: float | None = None
    selected: TemperatureObservation | None = None
    z_state_m: float | None = None
    eligible: tuple[TemperatureObservation, ...] = ()
    excluded: tuple[tuple[TemperatureObservation, tuple[Diagnostic, ...]], ...] = ()
    diagnostics: tuple[dict[str, Any], ...] = ()
    evaluated: bool = True

    @property
    def available(self) -> bool:
        return self.status is Availability.AVAILABLE

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "evaluated": self.evaluated,
            "temperature_k": self.temperature_k,
            "selected_observation": (_observation_dict(self.selected, self.z_state_m)
                                     if self.selected is not None else None),
            "method_is_provenance_only": True,
            "rule": (
                "M3 + R1 + C3: eligible corrected observations (Horner-corrected, "
                "Fertl-Wichmann, Squarci-Taffi) inside [z_top, z_base], with an "
                "established ground-level depth reference, not deeper than the "
                "recorded total depth; nearest to z_state; equal distance -> "
                "shallower (R1-1); same method, same depth, different values -> "
                "unavailable (R1-2, C3); different methods at the same depth -> "
                "Squarci-Taffi (R1-3); Horner vs Fertl-Wichmann without "
                "Squarci-Taffi -> unavailable (deferred guard). No interpolation, "
                "no new correction, no accuracy ranking."
            ),
            "eligible_observations": [_observation_dict(o, self.z_state_m) for o in self.eligible],
            "excluded_observations": [
                {**_observation_dict(o), "reasons": [r.value for r in reasons]}
                for o, reasons in self.excluded
            ],
            "diagnostics": [dict(d) for d in self.diagnostics],
        }


def _unavailable(z_state: float | None, eligible, excluded, *diags: dict[str, Any],
                 evaluated: bool = True) -> TemperatureSelection:
    return TemperatureSelection(
        status=Availability.UNAVAILABLE, z_state_m=z_state,
        eligible=tuple(eligible), excluded=tuple(excluded),
        diagnostics=tuple(diags), evaluated=evaluated,
    )


def exclusion_reasons(observation: TemperatureObservation, record: NormalizedWellRecord,
                      interval: StorageInterval) -> tuple[Diagnostic, ...]:
    """Every M3 eligibility condition the observation fails (empty = eligible)."""
    reasons: list[Diagnostic] = []
    if _method(observation) not in ELIGIBLE_TEMPERATURE_METHODS:
        reasons.append(Diagnostic.METHOD_NOT_ELIGIBLE)
    if not interval.contains(observation.depth_m):
        reasons.append(Diagnostic.OUTSIDE_STORAGE_INTERVAL)
    for datum in (record.depth_datum, observation.depth_datum):
        reason = depth_reference_diagnostic(datum)
        if reason is not None and reason not in reasons:
            reasons.append(reason)
    if not record.depth_m.is_present:
        reasons.append(Diagnostic.TOTAL_DEPTH_NOT_RECORDED)
    elif observation.depth_m > float(record.depth_m.value):  # type: ignore[arg-type]
        reasons.append(Diagnostic.BELOW_RECORDED_TOTAL_DEPTH)
    return tuple(reasons)


def _same(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=0.0, abs_tol=EXACT_TIE_TOLERANCE)


def select_temperature(record: NormalizedWellRecord,
                       interval: StorageInterval) -> TemperatureSelection:
    """Apply the M3 + R1 evaluation order literally.

    1. Keep eligible observations (method, in-interval, established depth
       reference, not deeper than the recorded TD).
    2. Take the minimum ``|z_obs - z_state|``.
    3. Different depths at that minimum: keep the shallower (R1-1).
    4. Any single method with two or more different values at the selected
       depth: unavailable, with a conflict diagnostic (R1-2, C3).
    5. More than one method at that depth: Squarci-Taffi (R1-3). Horner vs
       Fertl-Wichmann with no Squarci-Taffi: unavailable (deferred guard).
    6. Nothing eligible: unavailable (M3).
    """
    z_state = interval.z_state_m
    eligible: list[TemperatureObservation] = []
    excluded: list[tuple[TemperatureObservation, tuple[Diagnostic, ...]]] = []
    for observation in record.temperatures:
        reasons = exclusion_reasons(observation, record, interval)
        if reasons:
            excluded.append((observation, reasons))
        else:
            eligible.append(observation)

    if not eligible:
        return _unavailable(z_state, eligible, excluded,
                            diagnostic(Diagnostic.NO_ELIGIBLE_TEMPERATURE_OBSERVATION))

    distances = [abs(o.depth_m - z_state) for o in eligible]
    nearest_distance = min(distances)
    nearest = [o for o, d in zip(eligible, distances) if _same(d, nearest_distance)]

    notes: list[dict[str, Any]] = []
    selected_depth = min(o.depth_m for o in nearest)
    at_depth = [o for o in nearest if _same(o.depth_m, selected_depth)]
    if len(at_depth) < len(nearest):
        notes.append(diagnostic(
            Diagnostic.EQUAL_DISTANCE_SHALLOWER_SELECTED,
            depths_m=sorted({o.depth_m for o in nearest}), selected_depth_m=selected_depth,
        ))

    by_method: dict[TemperatureMethod, list[TemperatureObservation]] = {}
    for observation in at_depth:
        by_method.setdefault(TemperatureMethod(observation.method), []).append(observation)

    conflicting = sorted(
        (method for method, group in by_method.items()
         if any(not _same(o.temperature_k, group[0].temperature_k) for o in group)),
        key=lambda m: m.value,
    )
    if conflicting:
        return _unavailable(z_state, eligible, excluded, *notes, diagnostic(
            Diagnostic.TEMPERATURE_SAME_METHOD_CONFLICT,
            depth_m=selected_depth,
            methods=[m.value for m in conflicting],
            values_k={m.value: sorted({o.temperature_k for o in by_method[m]})
                      for m in conflicting},
        ))

    if len(by_method) == 1:
        chosen = at_depth[0]
    elif TemperatureMethod.SQUARCI_TAFFI in by_method:
        chosen = by_method[TemperatureMethod.SQUARCI_TAFFI][0]
        notes.append(diagnostic(
            Diagnostic.SAME_DEPTH_SQUARCI_TAFFI_CONVENTION,
            depth_m=selected_depth, methods=sorted(m.value for m in by_method),
        ))
    else:
        return _unavailable(z_state, eligible, excluded, *notes, diagnostic(
            Diagnostic.TEMPERATURE_METHOD_TIE_UNRESOLVED,
            depth_m=selected_depth, methods=sorted(m.value for m in by_method),
            values_k={m.value: by_method[m][0].temperature_k for m in by_method},
        ))

    return TemperatureSelection(
        status=Availability.AVAILABLE, temperature_k=chosen.temperature_k,
        selected=chosen, z_state_m=z_state, eligible=tuple(eligible),
        excluded=tuple(excluded), diagnostics=tuple(notes),
    )


# -- EOS envelope (E1, M4, C1) -------------------------------------------------


def within_validated_envelope(pressure_eos_pa: Any, temperature_k: float) -> Any:
    """Per-realisation envelope membership (closed bounds), on ``P_EOS``."""
    p_low, p_high = VALIDATED_ENVELOPE_PRESSURE_PA
    t_low, t_high = VALIDATED_ENVELOPE_TEMPERATURE_K
    pressure = np.asarray(pressure_eos_pa, dtype=float)
    temperature_inside = t_low <= temperature_k <= t_high
    return (pressure >= p_low) & (pressure <= p_high) & temperature_inside


@dataclass(frozen=True)
class EnvelopeCheck:
    """The M4 check over every realisation of one named scenario."""

    n_realisations: int
    n_outside: int
    n_pressure_below: int
    n_pressure_above: int
    temperature_inside: bool

    @property
    def all_inside(self) -> bool:
        return self.n_outside == 0

    @classmethod
    def evaluate(cls, pressure_eos_pa: np.ndarray, temperature_k: float) -> "EnvelopeCheck":
        p_low, p_high = VALIDATED_ENVELOPE_PRESSURE_PA
        inside = within_validated_envelope(pressure_eos_pa, temperature_k)
        return cls(
            n_realisations=int(pressure_eos_pa.size),
            n_outside=int(np.count_nonzero(~inside)),
            n_pressure_below=int(np.count_nonzero(pressure_eos_pa < p_low)),
            n_pressure_above=int(np.count_nonzero(pressure_eos_pa > p_high)),
            temperature_inside=bool(
                VALIDATED_ENVELOPE_TEMPERATURE_K[0] <= temperature_k
                <= VALIDATED_ENVELOPE_TEMPERATURE_K[1]
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "pressure_basis": "P_EOS (absolute, including P_atm = 101325 Pa)",
            "pressure_pa": list(VALIDATED_ENVELOPE_PRESSURE_PA),
            "temperature_k": list(VALIDATED_ENVELOPE_TEMPERATURE_K),
            "checked_per_realisation": True,
            "n_realisations": self.n_realisations,
            "n_outside": self.n_outside,
            "n_pressure_below_envelope": self.n_pressure_below,
            "n_pressure_above_envelope": self.n_pressure_above,
            "temperature_inside": self.temperature_inside,
            "all_inside": self.all_inside,
            "realisations_discarded": 0,
        }


# -- Monte Carlo (S6) -----------------------------------------------------------


@dataclass(frozen=True)
class ApprovedPriors:
    """The only variables that vary in the approved Monte Carlo (S6, row 16).

    Area, ``h_g``, temperature and water level are deterministic. Citations
    are carried for the externally sourced priors (S10).
    """

    porosity: tuple[float, float]
    brine_density_kg_m3: tuple[float, float]
    storage_efficiency: tuple[float, float]
    porosity_citation: Citation | None = field(default=None, compare=False)
    storage_efficiency_citation: Citation | None = field(default=None, compare=False)

    @classmethod
    def from_scenario(cls, scenario: ScreeningScenario) -> "ApprovedPriors":
        def _assumption(parameter: str) -> Any:
            assumption = scenario.get(parameter)
            if assumption is None:
                raise ValueError(f"scenario {scenario.name!r} has no {parameter} prior")
            return assumption

        def _range(parameter: str) -> tuple[float, float]:
            value = _assumption(parameter).value
            low, high = value if isinstance(value, (list, tuple)) else (value, value)
            return (float(low), float(high))

        def _citation(parameter: str) -> Citation | None:
            citation = _assumption(parameter).citation
            return citation if isinstance(citation, Citation) else None

        brine = scenario.brine_density_kg_m3
        if brine is None:
            raise ValueError(f"scenario {scenario.name!r} declares no brine density")
        brine_range = ((float(brine[0]), float(brine[1])) if isinstance(brine, (list, tuple))
                       else (float(brine), float(brine)))
        return cls(
            porosity=_range("porosity"),
            brine_density_kg_m3=brine_range,
            storage_efficiency=_range("storage_efficiency"),
            porosity_citation=_citation("porosity"),
            storage_efficiency_citation=_citation("storage_efficiency"),
        )

    def to_dict(self) -> dict[str, Any]:
        def _cited(citation: Citation | None) -> dict[str, Any] | None:
            return citation.to_dict() if citation is not None else None

        return {
            "porosity": {
                "distribution": "uniform", "low": self.porosity[0], "high": self.porosity[1],
                "unit": "-", "status": "PROVISIONAL",
                "provenance": "Donda et al. (2011), Table 2 (13 Italian potential reservoirs)",
                "citation": _cited(self.porosity_citation),
            },
            "brine_density_kg_m3": {
                "distribution": "uniform", "low": self.brine_density_kg_m3[0],
                "high": self.brine_density_kg_m3[1], "unit": "kg/m3", "status": "PROVISIONAL",
                "provenance": (
                    "PROJECT ASSUMPTION: declared saline formation-water density range; "
                    "no primary literature source adopted "
                    "(docs/scenario-literature-review.md section 4)"
                ),
                "citation": None,
            },
            "storage_efficiency": {
                "distribution": "uniform", "low": self.storage_efficiency[0],
                "high": self.storage_efficiency[1], "unit": "-", "status": "DECIDED (A6)",
                "provenance": (
                    "CSLF-T-2008-04 / DOE-derived P15-P85 bounds; aggregate DOE-style E "
                    "containing the gross-to-net term (A4, A5)"
                ),
                "statement": STORAGE_EFFICIENCY_PRIOR_STATEMENT,
                "citation": _cited(self.storage_efficiency_citation),
            },
        }


#: The approved priors, read from the approved parameter set.
APPROVED_PRIORS = ApprovedPriors.from_scenario(APPROVED_PARAMETER_SET)

#: Sampler slots. They follow ``UniformPriors.sample``'s field order with brine
#: density in the pressure slot, so a seed feeds porosity, brine density and E
#: from the same uniform streams the legacy sampler uses for porosity, pressure
#: and E. Deterministic inputs occupy their slots as degenerate ranges
#: (low == high) and do not vary.
_SAMPLER_SLOTS = ("area_m2", "thickness_m", "porosity", "brine_density_kg_m3",
                  "temperature_k", "storage_efficiency")


def draw_realisations(*, area_m2: float, h_g_m: float, temperature_k: float,
                      priors: ApprovedPriors, n: int,
                      seed: int | None) -> dict[str, np.ndarray]:
    """Independent uniform draws for the approved sampled variables."""
    if n <= 0:
        raise ValueError("n must be positive")
    ranges = {
        "area_m2": (area_m2, area_m2),
        "thickness_m": (h_g_m, h_g_m),
        "porosity": priors.porosity,
        "brine_density_kg_m3": priors.brine_density_kg_m3,
        "temperature_k": (temperature_k, temperature_k),
        "storage_efficiency": priors.storage_efficiency,
    }
    rng = np.random.default_rng(seed)
    return {slot: rng.uniform(*ranges[slot], size=n) for slot in _SAMPLER_SLOTS}


def _capacity(draws: dict[str, np.ndarray], pressure_eos_pa: np.ndarray) -> McResult:
    samples = [
        CapacitySample(
            area_m2=float(draws["area_m2"][i]),
            thickness_m=float(draws["thickness_m"][i]),
            porosity=float(draws["porosity"][i]),
            pressure_pa=float(pressure_eos_pa[i]),
            temperature_k=float(draws["temperature_k"][i]),
            storage_efficiency=float(draws["storage_efficiency"][i]),
        )
        for i in range(pressure_eos_pa.size)
    ]
    return run_capacity_mc(samples)


def _capacity_dict(result: McResult) -> dict[str, Any]:
    return {
        "p10": result.p10_mt,
        "p50": result.p50_mt,
        "p90": result.p90_mt,
        "mean": result.mean_mt,
        "n_samples": result.n,
    }


# -- results ---------------------------------------------------------------------


@dataclass(frozen=True)
class ScenarioResult:
    """One named water-level scenario, evaluated as one joint state (F1)."""

    scenario: WaterLevelScenario
    status: ValidationStatus
    z_wl_m: float | None = None
    z_state_m: float | None = None
    pressure_eos_range_pa: tuple[float, float] | None = None
    temperature_k: float | None = None
    envelope: EnvelopeCheck | None = None
    capacity: McResult | None = None
    diagnostic_capacity: McResult | None = None
    diagnostics: tuple[dict[str, Any], ...] = ()

    @property
    def validated_percentiles(self) -> str:
        if self.status is ValidationStatus.VALIDATED:
            return "REPORTED"
        if self.status is ValidationStatus.OUTSIDE_VALIDATED_ENVELOPE:
            return "BLOCKED"
        return "UNAVAILABLE"

    def to_dict(self) -> dict[str, Any]:
        info = WATER_LEVEL_SCENARIO_INFO[self.scenario]
        pressure = None
        if self.pressure_eos_range_pa is not None:
            pressure = {
                "low": self.pressure_eos_range_pa[0],
                "high": self.pressure_eos_range_pa[1],
                "unit": "Pa",
                "absolute": True,
                "equation": PRESSURE_EQUATION,
                "delta_z_m": (self.z_state_m - self.z_wl_m
                              if self.z_state_m is not None and self.z_wl_m is not None
                              else None),
                "note": "Range over the brine-density prior bounds; P_EOS varies per realisation.",
            }
        capacity = None
        if self.capacity is not None:
            capacity = {**_capacity_dict(self.capacity),
                        "validation_status": ValidationStatus.VALIDATED.value,
                        "interpretation": PERCENTILE_INTERPRETATION}
        diagnostic_capacity = None
        if self.diagnostic_capacity is not None:
            diagnostic_capacity = {**_capacity_dict(self.diagnostic_capacity),
                                   "validation_status": ValidationStatus.NOT_VALIDATED.value,
                                   "label": DIAGNOSTIC_CAPACITY_LABEL}
        return {
            "name": self.scenario.value,
            "role": info["role"],
            "label": info["label"],
            "description": info["description"],
            "z_wl_definition": info["z_wl_definition"],
            "validation_status": self.status.value,
            "validated_percentiles": self.validated_percentiles,
            "z_wl_m": self.z_wl_m,
            "z_state_m": self.z_state_m,
            "pressure_eos_pa": pressure,
            "temperature_k": self.temperature_k,
            "envelope": self.envelope.to_dict() if self.envelope is not None else None,
            "capacity_mt": capacity,
            "diagnostic_capacity_mt": diagnostic_capacity,
            "diagnostics": [dict(d) for d in self.diagnostics],
        }


@dataclass(frozen=True)
class ApprovedModelResult:
    """Both named water-level scenarios for one well and interval."""

    well_id: str
    area_m2: float
    interval: StorageInterval
    depth_datum: DepthDatum
    depth_reference_diagnostic: Diagnostic | None
    temperature: TemperatureSelection
    scenarios: tuple[ScenarioResult, ...]
    priors: ApprovedPriors
    n_samples: int
    seed: int | None
    depth_m: float | None = None

    @property
    def interval_available(self) -> bool:
        return self.depth_reference_diagnostic is None

    def scenario(self, name: WaterLevelScenario) -> ScenarioResult:
        for result in self.scenarios:
            if result.scenario is name:
                return result
        raise KeyError(name)

    def systematic_effect(self) -> dict[str, Any]:
        """F1: baseline, individual effect and joint scenarios; never a factor."""
        ground = self.scenario(WaterLevelScenario.GROUND_REFERENCE)
        sea = self.scenario(WaterLevelScenario.SEA_LEVEL_SENSITIVITY)
        both = (ground.status is ValidationStatus.VALIDATED
                and sea.status is ValidationStatus.VALIDATED)
        difference = (sea.capacity.p50_mt - ground.capacity.p50_mt
                      if both and sea.capacity is not None and ground.capacity is not None
                      else None)
        return {
            "methodology": JOINT_SCENARIO_METHODOLOGY,
            "baseline": WaterLevelScenario.GROUND_REFERENCE.value,
            "joint_scenarios": [s.value for s in WATER_LEVEL_SCENARIOS],
            "individual_effects": [{
                "effect": "water_level",
                "contrast": "SEA_LEVEL_SENSITIVITY vs GROUND_REFERENCE",
                "status": (Availability.AVAILABLE if both else Availability.UNAVAILABLE).value,
                "p50_difference_mt": difference,
                "definition": "P50(SEA_LEVEL_SENSITIVITY) - P50(GROUND_REFERENCE), same seed",
                "reason": (None if both else
                           "Reported only when both named scenarios are VALIDATED."),
                "is_correction": False,
            }],
            "multiplied_correction_factor": None,
        }

    def to_dict(self) -> dict[str, Any]:
        reason = self.depth_reference_diagnostic
        available = reason is None
        reference = {
            "depth_datum": self.depth_datum.value,
            "status": (Availability.AVAILABLE if available else Availability.UNAVAILABLE).value,
            "diagnostics": ([] if reason is None
                            else [diagnostic(reason, depth_datum=self.depth_datum.value)]),
        }
        return {
            "model_path": "APPROVED_MODEL",
            "contract": CONTRACT_REFERENCE,
            "capacity_equation": CAPACITY_EQUATION,
            "well_id": self.well_id,
            "depth_m": self.depth_m,
            "depth_reference": reference,
            "storage_interval": {
                "status": reference["status"],
                "z_top_m": self.interval.z_top_m,
                "z_base_m": self.interval.z_base_m,
                "h_g_m": self.interval.h_g_m if available else None,
                "z_state_m": self.interval.z_state_m if available else None,
                "h_g_definition": "h_g = z_base - z_top (derived; gross thickness, A1)",
                "state_point_convention": STATE_POINT_CONVENTION,
                "requirement": STORAGE_INTERVAL_REQUIREMENT,
                "diagnostics": list(reference["diagnostics"]),
            },
            "temperature_selection": self.temperature.to_dict(),
            "water_level_scenarios": [s.to_dict() for s in self.scenarios],
            "water_level_scenario_statement": WATER_LEVEL_SCENARIO_STATEMENT,
            "systematic_effect": self.systematic_effect(),
            "sampled_inputs": self.priors.to_dict(),
            "model_constants": model_constants(),
            "n_samples": self.n_samples,
            "seed": self.seed,
        }


def model_constants() -> dict[str, Any]:
    """Deterministic constants and conventions (S9: never ranked as sensitivities)."""
    return {
        "p_atm_pa": {
            "value": P_ATM_PA, "unit": "Pa", "label": "PROJECT MODEL CONSTANT (B1)",
            "provenance": ("Standard atmosphere, 1 atm = 101325 Pa (exact by definition); "
                           "its use as surface pressure is a project model convention"),
        },
        "gravity_m_s2": {
            "value": STANDARD_GRAVITY_M_S2, "unit": "m/s2",
            "provenance": "Standard acceleration of gravity, 9.80665 m/s2 (exact by definition)",
        },
        "eos": {
            "value": "Peng-Robinson with a constant Peneloux volume shift (E1)",
            "validated_envelope": {
                "pressure_pa": list(VALIDATED_ENVELOPE_PRESSURE_PA),
                "temperature_k": list(VALIDATED_ENVELOPE_TEMPERATURE_K),
                "pressure_basis": "P_EOS (absolute)",
                "provenance": "Phase 1 validation envelope vs Span & Wagner (1996)",
            },
        },
        "state_point": {"value": "z_state = (z_top + z_base) / 2",
                        "label": "PROJECT MODEL CONVENTION (S1)"},
        "water_level": {"value": [s.value for s in WATER_LEVEL_SCENARIOS],
                        "label": "named deterministic scenarios (M2); never sampled"},
        "not_ranked_as_sensitivities": True,
    }


def _scenario_result(scenario: WaterLevelScenario, record: NormalizedWellRecord,
                     interval: StorageInterval, area_m2: float,
                     temperature: TemperatureSelection, priors: ApprovedPriors,
                     n: int, seed: int | None) -> ScenarioResult:
    z_state = interval.z_state_m
    z_wl = water_level_depth_m(scenario, record)
    diagnostics: list[dict[str, Any]] = []
    pressure_range = None
    if z_wl is None:
        diagnostics.append(diagnostic(Diagnostic.SURFACE_ELEVATION_UNAVAILABLE))
    else:
        ends = [float(eos_pressure_pa(rho, z_state, z_wl)) for rho in priors.brine_density_kg_m3]
        pressure_range = (min(ends), max(ends))
        if z_state - z_wl < 0:
            diagnostics.append(diagnostic(Diagnostic.STATE_POINT_ABOVE_WATER_LEVEL,
                                          z_state_m=z_state, z_wl_m=z_wl))
    if not temperature.available:
        diagnostics.append(diagnostic(Diagnostic.TEMPERATURE_UNAVAILABLE))
    if z_wl is None or not temperature.available or temperature.temperature_k is None:
        return ScenarioResult(
            scenario=scenario, status=ValidationStatus.UNAVAILABLE, z_wl_m=z_wl,
            z_state_m=z_state, pressure_eos_range_pa=pressure_range,
            temperature_k=temperature.temperature_k, diagnostics=tuple(diagnostics),
        )

    temperature_k = temperature.temperature_k
    draws = draw_realisations(area_m2=area_m2, h_g_m=interval.h_g_m,
                              temperature_k=temperature_k, priors=priors, n=n, seed=seed)
    pressure = eos_pressure_pa(draws["brine_density_kg_m3"], z_state, z_wl)
    envelope = EnvelopeCheck.evaluate(pressure, temperature_k)

    if envelope.all_inside:
        return ScenarioResult(
            scenario=scenario, status=ValidationStatus.VALIDATED, z_wl_m=z_wl,
            z_state_m=z_state, pressure_eos_range_pa=pressure_range,
            temperature_k=temperature_k, envelope=envelope,
            capacity=_capacity(draws, pressure), diagnostics=tuple(diagnostics),
        )

    diagnostics.append(diagnostic(Diagnostic.OUTSIDE_VALIDATED_ENVELOPE,
                                  n_outside=envelope.n_outside,
                                  n_realisations=envelope.n_realisations))
    diagnostic_capacity = None
    if bool(np.all(pressure > 0)):
        diagnostic_capacity = _capacity(draws, pressure)
    else:
        diagnostics.append(diagnostic(Diagnostic.EOS_NOT_EVALUABLE))
    return ScenarioResult(
        scenario=scenario, status=ValidationStatus.OUTSIDE_VALIDATED_ENVELOPE, z_wl_m=z_wl,
        z_state_m=z_state, pressure_eos_range_pa=pressure_range,
        temperature_k=temperature_k, envelope=envelope,
        diagnostic_capacity=diagnostic_capacity, diagnostics=tuple(diagnostics),
    )


def evaluate_approved_model(record: NormalizedWellRecord, *, area_m2: float,
                            interval: StorageInterval, n: int, seed: int | None,
                            priors: ApprovedPriors = APPROVED_PRIORS) -> ApprovedModelResult:
    """Evaluate both named water-level scenarios for one well and interval."""
    if isinstance(area_m2, bool) or not isinstance(area_m2, (int, float)) \
            or not math.isfinite(float(area_m2)) or float(area_m2) <= 0:
        raise ValueError(f"area_m2 must be a finite number > 0, got {area_m2!r}")
    area = float(area_m2)
    depth_m = float(record.depth_m.value) if record.depth_m.is_present else None  # type: ignore[arg-type]
    reference = depth_reference_diagnostic(record.depth_datum)

    if reference is not None:
        # Final Gap Closure A: no defensible interval, so interval, h_g, z_state,
        # temperature and pressure are all unavailable.
        reason = diagnostic(reference, depth_datum=record.depth_datum.value)
        temperature = _unavailable(None, (), (), reason, evaluated=False)
        scenarios = tuple(
            ScenarioResult(scenario=s, status=ValidationStatus.UNAVAILABLE,
                           diagnostics=(reason,))
            for s in WATER_LEVEL_SCENARIOS
        )
    else:
        temperature = select_temperature(record, interval)
        scenarios = tuple(
            _scenario_result(s, record, interval, area, temperature, priors, n, seed)
            for s in WATER_LEVEL_SCENARIOS
        )

    return ApprovedModelResult(
        well_id=record.canonical_id, area_m2=area, interval=interval,
        depth_datum=record.depth_datum, depth_reference_diagnostic=reference,
        temperature=temperature, scenarios=scenarios, priors=priors,
        n_samples=n, seed=seed, depth_m=depth_m,
    )


def is_approved_parameter_set(scenario: ScreeningScenario) -> bool:
    """True only for the built-in approved parameter set object itself."""
    return scenario is APPROVED_PARAMETER_SET
