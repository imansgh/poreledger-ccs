# Phase 1 draft -- `net_to_gross` disclosure

**Review only. Nothing in `src/` was modified. No equation, constant, scientific
test or API behaviour was changed. This document is a patch proposal.**

Companion to `docs/net-to-gross-semantics.md` and
`docs/ntg-elicitation-design.md`.

---

## 1. Files that would change

| File | Change | Lines |
| --- | --- | --- |
| `src/ccs_screen/api.py` | Two enums, one dataclass, one warning constant, `UserInputs` gains an optional field, payload gains one block | ~+150 |
| `src/ccs_screen/web/schemas.py` | One nested request model | ~+55 |
| `tests/test_ntg_disclosure.py` | **New.** 16 tests from the brief plus regression guards | ~+330 |
| `docs/http-api.md` | Document the optional block | ~+40 |

**Not changed:** `capacity.py`, `properties.py`, `pressure.py`, `monte_carlo.py`,
`surrogate.py`, `config.py`, anything under `ingest/`, and all 22 existing test
files that reference `thickness_m`.

---

## 2. Ambiguities discovered during implementation design

Three, found by reading the code rather than by design. The first is
load-bearing.

### 2.1 `net_to_gross` cannot be an `Assumption`

`Assumption.__post_init__` rejects any parameter not in `ASSUMABLE`:

```python
ASSUMABLE = ("area_m2", "porosity", "pressure_pa", "storage_efficiency", "thickness_m")
```

and `scenario.py` derives from it directly:

```python
SCENARIO_PARAMETERS = tuple(ASSUMABLE)
...
overreach = [p for p in self.assumptions.parameters if p not in SCENARIO_PARAMETERS]
```

So adding `net_to_gross` to `ASSUMABLE` would immediately make it
**scenario-supplyable** -- a scenario could assert a net-to-gross for a well.
That is wrong: NTG describes how *this caller* derived *this* `thickness_m`,
and no scenario can know it.

**Resolution:** `net_to_gross` is **not** an `Assumption`. It is a dedicated
frozen dataclass that reuses `EvidenceClass` and `Confidence` but stays outside
the assumption machinery. `ASSUMABLE` is untouched.

This is the concrete form of the `screening_inputs` rule from the semantics
spec: NTG is metadata about an input, not an input.

### 2.2 `from_mapping` rejects unknown keys

```python
unknown = sorted(set(data) - set(REQUIRED_USER_INPUTS))
if unknown: raise ApiError(...)
```

`REQUIRED_USER_INPUTS` drives three things at once: rejection of unknown keys,
the missing-field message, and the `as_assumptions()` loop. Adding
`net_to_gross` to it would make it **required** and would try to build an
`Assumption` from it.

**Resolution:** a separate `OPTIONAL_USER_INPUTS` tuple, subtracted in the
unknown-key check only.

### 2.3 The module lives in `api.py`, not `ingest/`

NTG is a caller-facing concept and nothing in ingestion can produce it. Putting
the enums in `ingest/provenance.py` would imply the normaliser will one day
populate them. In Phase 1 it will not.

**Resolution:** `api.py`. If a later phase derives NTG from logs, moving it is a
one-line import change.

---

## 3. Proposed schema and model changes

### 3.1 `src/ccs_screen/api.py`

```python
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


@dataclass(frozen=True)
class NetToGross:
    """The net-to-gross the caller's ``thickness_m`` implies.

    Phase 1 records this and nothing else: it never enters the capacity
    equation, never enters ``screening_inputs``, and is never inferred. See
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

    @property
    def is_point(self) -> bool:
        return self.low == self.high

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "NetToGross":
        if not isinstance(data, Mapping):
            raise ApiError(
                f"net_to_gross must be an object, got {type(data).__name__}"
            )
        allowed = {"low", "high", "net_criterion", "net_basis",
                   "cutoff_note", "thickness_convention"}
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise ApiError(f"unknown net_to_gross field(s): {', '.join(unknown)} "
                           f"(accepted: {', '.join(sorted(allowed))})")
        missing = [k for k in ("low", "high", "net_criterion", "net_basis")
                   if k not in data]
        if missing:
            raise ApiError(
                f"net_to_gross is missing required field(s): {', '.join(missing)}. "
                f"A net-to-gross without a stated criterion and basis is the "
                f"undocumented assumption this field exists to remove."
            )
        return cls(
            low=data["low"], high=data["high"],
            net_criterion=_coerce_enum(NetCriterion, data["net_criterion"], "net_criterion"),
            net_basis=_coerce_enum(NetBasis, data["net_basis"], "net_basis"),
            cutoff_note=_coerce_note(data.get("cutoff_note")),
            thickness_convention=(
                _coerce_enum(ThicknessConvention, data["thickness_convention"],
                             "thickness_convention")
                if data.get("thickness_convention") is not None else None
            ),
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


def _coerce_enum(enum_cls, value, field_name: str):
    if isinstance(value, enum_cls):
        return value
    if not isinstance(value, str) or not value.strip():
        raise ApiError(f"net_to_gross.{field_name} must be a non-empty string, "
                       f"one of: {', '.join(m.value for m in enum_cls)}")
    try:
        return enum_cls(value.strip())
    except ValueError:
        raise ApiError(f"net_to_gross.{field_name}: unknown value {value!r} "
                       f"(accepted: {', '.join(m.value for m in enum_cls)})") from None


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


NET_TO_GROSS_DEFINITION = (
    "Fraction of the gross formation interval that satisfies the caller's "
    "declared reservoir-quality criterion, over the same interval from which "
    "thickness_m was derived. Numerator and denominator must share a thickness "
    "convention. NOT derived from the chronostratigraphic gross_thickness_m. "
    "See docs/net-to-gross-semantics.md."
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

OPTIONAL_USER_INPUTS = ("net_to_gross",)
```

### 3.2 `UserInputs` -- three edits

```python
@dataclass(frozen=True)
class UserInputs:
    area_m2: float
    thickness_m: float
    net_to_gross: NetToGross | None = None      # NEW, optional
```

`__post_init__` is **unchanged** -- it loops `REQUIRED_USER_INPUTS`, and
`NetToGross` validates itself on construction.

```python
    @classmethod
    def from_mapping(cls, data):
        ...
        unknown = sorted(set(data) - set(REQUIRED_USER_INPUTS)
                                   - set(OPTIONAL_USER_INPUTS))     # CHANGED
        ...
        raw_ntg = data.get("net_to_gross")                          # NEW
        return cls(
            area_m2=data["area_m2"],
            thickness_m=data["thickness_m"],
            net_to_gross=(NetToGross.from_mapping(raw_ntg)
                          if raw_ntg is not None else None),        # NEW
        )
```

`as_assumptions()` is **unchanged** -- it loops `REQUIRED_USER_INPUTS`, so NTG
never becomes an `Assumption` (ambiguity 2.1).

`to_dict()` is **unchanged** -- NTG is reported separately, so
`payload["user_inputs"]` keeps its exact current shape.

```python
    def thickness_provenance(self) -> dict[str, Any]:                # NEW
        """How thickness_m was obtained. Metadata, never a model input."""
        return {
            "thickness_m": self.thickness_m,
            "thickness_kind": "net_storage",
            "declared": self.net_to_gross is not None,
            "net_to_gross": (self.net_to_gross.to_dict()
                             if self.net_to_gross else None),
            "policy": NET_THICKNESS_POLICY_STATEMENT,
        }
```

### 3.3 `_interpretation` -- one new parameter

```python
def _interpretation(scenario=None, net_to_gross: NetToGross | None = None):
    ...
    if net_to_gross is None:
        warnings.append(dict(NET_TO_GROSS_UNDECLARED_WARNING))       # NEW
    elif net_to_gross.is_point:
        warnings.append(dict(NET_TO_GROSS_POINT_WARNING))            # NEW
    block["warnings"] = warnings
```

The point-value warning states that a scalar narrows the reported band by about
15% relative to a range (measured in `docs/bprime-control-experiment.md`).

### 3.4 `screen_well` payload -- two lines

```python
        "user_inputs": resolved_inputs.to_dict(),
        "thickness_provenance": resolved_inputs.thickness_provenance(),   # NEW
        "interpretation": _interpretation(active, resolved_inputs.net_to_gross),  # CHANGED
```

`compare_temperature_methods` and `screening_funnel` call `from_mapping`, so
they inherit the validation with no edit.

### 3.5 `src/ccs_screen/web/schemas.py`

```python
class NetToGrossModel(BaseModel):
    """Optional declaration of the net-to-gross that thickness_m implies."""

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
    def _ordered(self):
        if self.low > self.high:
            raise ValueError(f"low must be <= high, got ({self.low}, {self.high})")
        return self


class UserInputsModel(BaseModel):
    ...
    net_to_gross: NetToGrossModel | None = Field(default=None)       # NEW
```

`gt=0, le=1` rejects NaN (all comparisons false) and both infinities.
`extra="forbid"` is inherited.

---

## 4. Request and response examples

### 4.1 Declared

```json
POST /wells/SALUZZO%7C1/screen
{ "user_inputs": {
    "area_m2": 8.0e7,
    "thickness_m": 35.0,
    "net_to_gross": {
      "low": 0.30, "high": 0.55,
      "net_criterion": "porosity_permeability",
      "net_basis": "log_derived",
      "cutoff_note": "porosity >= 8% and permeability >= 1 mD, 1200-1450 m",
      "thickness_convention": "measured"
    } } }
```

```json
{ "status": "screened",
  "user_inputs": { "area_m2": {...}, "thickness_m": {...} },
  "thickness_provenance": {
    "thickness_m": 35.0,
    "thickness_kind": "net_storage",
    "declared": true,
    "net_to_gross": {
      "low": 0.30, "high": 0.55, "unit": "-",
      "net_criterion": "porosity_permeability",
      "net_basis": "log_derived",
      "evidence_class": "site_specific",
      "confidence": "high",
      "cutoff_note": "porosity >= 8% and permeability >= 1 mD, 1200-1450 m",
      "thickness_convention": "measured",
      "is_point": false,
      "used_in_calculation": false,
      "definition": "Fraction of the gross formation interval that ..."
    },
    "policy": "Net storage thickness is not derived from gross ..."
  },
  "scenario_based_capacity_mt": { "p10": 5.234, "p50": 10.900, "p90": 20.570, ... }
}
```

**`used_in_calculation: false` is the honest part of this payload.** It states
in the response that the field is recorded and unused.

### 4.2 Not declared -- today's request, unchanged

```json
{ "user_inputs": { "area_m2": 8.0e7, "thickness_m": 35.0 } }
```

```json
{ "thickness_provenance": { "declared": false, "net_to_gross": null, ... },
  "interpretation": { "warnings": [
      { "code": "scale_mismatch_basin_vs_closure", ... },
      { "code": "net_to_gross_not_declared", ... } ] },
  "scenario_based_capacity_mt": { "p50": 10.900, ... }   /* identical */ }
```

### 4.3 Rejected

```json
{ "user_inputs": { "area_m2": 8.0e7, "thickness_m": 35.0,
                   "net_to_gross": { "low": 0.30, "high": 0.55 } } }
```
-> `400`: *"net_to_gross is missing required field(s): net_criterion, net_basis.
A net-to-gross without a stated criterion and basis is the undocumented
assumption this field exists to remove."*

---

## 5. Test plan -- `tests/test_ntg_disclosure.py`

| # | Test | Assertion |
| --- | --- | --- |
| 1 | NTG absent, behaviour identical | `screen_well(...)` with and without the field present in the module -> `scenario_based_capacity_mt` dicts compare `==` against values captured before the change |
| 2 | Valid range + basis + criterion accepted and exposed | `payload["thickness_provenance"]["net_to_gross"]["low"] == 0.30`; `declared is True` |
| 3 | Missing `net_basis` rejected | `ApiError` raised, message names `net_basis` |
| 4 | Missing `net_criterion` rejected | `ApiError`, message names `net_criterion` |
| 5 | `low > high` rejected | `ApiError` matching `low must be <= high` |
| 6 | Outside `(0, 1]` rejected | parametrised over `0.0, -0.1, 1.01, 2.0` |
| 7 | NaN / infinity rejected | parametrised over `nan, inf, -inf` on both `low` and `high` |
| 8 | 0.25-0.75 accepted as ordinary metadata | Accepted; `evidence_class` follows `net_basis`, **not** `generic`; no citation attached |
| 9 | Outside 0.25-0.75 but in `(0, 1]` accepted | `low=0.05, high=0.15` and `low=0.85, high=0.95` both accepted |
| 10 | Carbonate + `porosity_permeability` accepted | MALOSSA\|15 and TRECATE\|9\|ST screen normally with that criterion |
| 11 | NTG not in `screening_inputs` | `"net_to_gross" not in payload["screening_inputs"]`; the four label lists still union to exactly the six equation parameters |
| 12 | NTG does not change capacity | Same seed, with and without NTG -> `p10/p50/p90/mean` equal by `==`, not `approx` |
| 13 | NTG does not change Monte Carlo output | `n_samples` and `deterministic` unchanged; P50 bitwise equal |
| 14 | Five screenable wells numerically identical | Parametrised over SALUZZO\|1, DESANA\|1, ASTI\|1, MALOSSA\|15, TRECATE\|9\|ST; skips if `data/` absent |
| 15 | No automatic derivation | `NetToGross` has no constructor taking a record; `net_thickness / gross_thickness_m` appears nowhere in `api.py` (AST/source scan) |
| 16 | `ThicknessKind` unchanged | Three members, same values; `net_to_gross` is not a member |

Plus four regression guards beyond the brief:

| # | Test | Why |
| --- | --- | --- |
| 17 | `ASSUMABLE` still has exactly five entries | Ambiguity 2.1 -- NTG must never become scenario-supplyable |
| 18 | `net_to_gross` is not an `Assumption` | `Assumption(parameter="net_to_gross", ...)` still raises `AssumptionError` |
| 19 | Point value accepted **with** a warning | `is_point is True` and `net_to_gross_point_value` in warnings |
| 20 | `used_in_calculation` is `False` | The payload asserts its own inertness |

Test 12 uses `==` rather than `pytest.approx` deliberately: the brief requires
"not one floating-point unit", and `approx` would hide exactly the drift being
tested for.

---

## 6. Backward compatibility

| Surface | Impact |
| --- | --- |
| `UserInputs(area_m2=..., thickness_m=...)` | Works. New field has a default |
| `UserInputs.from_mapping({"area_m2":..., "thickness_m":...})` | Works. `net_to_gross` optional |
| `payload["user_inputs"]` | **Unchanged shape.** NTG is reported elsewhere |
| `payload["screening_inputs"]` | **Unchanged.** Six parameters, four disjoint labels |
| `scenario_based_capacity_mt` | **Bitwise identical** |
| `interpretation.warnings` | **Gains one entry** when NTG is absent |
| HTTP `extra="forbid"` | Still forbids; the accepted set grows by one |
| 22 existing test files using `thickness_m` | Unaffected |
| Frontend | Unaffected. `thickness_provenance` is additive and ignored by existing code |

**One behaviour does change, deliberately:** a caller who sends a *malformed*
`net_to_gross` now gets `blocked` where previously they got `unknown user
input(s): net_to_gross`. Both are rejections; the new message is more useful.
This is the "except where required to validate malformed metadata" carve-out in
the brief.

**One judgement call for the reviewer.** Adding a warning when NTG is absent
means **every existing caller immediately sees a new advisory**. That is the
point -- it is what "every result explicitly reports that NTG is unknown" means
-- but it is a visible change to every response, and a reviewer may prefer it
gated behind a flag for one release. I have not gated it, because a warning
nobody sees does not remove the defect.

---

## 7. What this draft deliberately does not do

- No numerical GR, porosity or permeability cutoff anywhere.
- No Piemonte value, no default value, no suggested value.
- CSLF's 0.25-0.75 appears **only** in the comment explaining why
  `POROSITY_PERMEABILITY` matches `E_h`'s wording -- never as data.
- No derivation from `net_thickness / gross_thickness_m`; test 15 enforces it.
- No optional gross-thickness field. It was considered and dropped for Phase 1:
  the only thing it enables is the `net > gross` swap check, and introducing a
  second gross-thickness concept alongside the chronostratigraphic one is a
  bigger semantic risk than the check is worth. It can be added in Phase 2 with
  an explicit name such as `formation_gross_thickness_m`.
- `E_h` is not removed, the equation is not touched, and capacity does not move.

---

## 8. Patch proposal

Unified-diff sketch. **Not applied.** Line numbers are approximate; the enum
import is the only change to the import block.

```diff
--- a/src/ccs_screen/api.py
+++ b/src/ccs_screen/api.py
@@
 from __future__ import annotations

 import threading
 from dataclasses import dataclass
+from enum import Enum
 from pathlib import Path
 from typing import Any, Mapping

 from ccs_screen.ingest.assumptions import (
     Assumption,
     AssumptionError,
     AssumptionSet,
     Citation,
     EvidenceClass,
 )
+from ccs_screen.ingest.provenance import Confidence
@@ class UserInputs:
     area_m2: float
     thickness_m: float
+    net_to_gross: NetToGross | None = None
@@ def from_mapping(cls, data):
-        unknown = sorted(set(data) - set(REQUIRED_USER_INPUTS))
+        unknown = sorted(set(data) - set(REQUIRED_USER_INPUTS)
+                                   - set(OPTIONAL_USER_INPUTS))
@@
-        return cls(area_m2=data["area_m2"], thickness_m=data["thickness_m"])
+        raw_ntg = data.get("net_to_gross")
+        return cls(
+            area_m2=data["area_m2"],
+            thickness_m=data["thickness_m"],
+            net_to_gross=(NetToGross.from_mapping(raw_ntg)
+                          if raw_ntg is not None else None),
+        )
@@ def to_dict(self):
         return {...}          # unchanged
+
+    def thickness_provenance(self) -> dict[str, Any]:
+        return {
+            "thickness_m": self.thickness_m,
+            "thickness_kind": "net_storage",
+            "declared": self.net_to_gross is not None,
+            "net_to_gross": (self.net_to_gross.to_dict()
+                             if self.net_to_gross else None),
+            "policy": NET_THICKNESS_POLICY_STATEMENT,
+        }
@@ def _interpretation(
-def _interpretation(scenario: ScreeningScenario | None = None) -> dict[str, Any]:
+def _interpretation(scenario: ScreeningScenario | None = None,
+                    net_to_gross: "NetToGross | None" = None) -> dict[str, Any]:
@@
     if scenario is not None and any(a.is_literature_derived for a in scenario.assumptions):
         warnings.append(dict(SCALE_MISMATCH_WARNING))
+    if net_to_gross is None:
+        warnings.append(dict(NET_TO_GROSS_UNDECLARED_WARNING))
+    elif net_to_gross.is_point:
+        warnings.append(dict(NET_TO_GROSS_POINT_WARNING))
     block["warnings"] = warnings
@@ def screen_well(...):
         "user_inputs": resolved_inputs.to_dict(),
-        "interpretation": _interpretation(active),
+        "thickness_provenance": resolved_inputs.thickness_provenance(),
+        "interpretation": _interpretation(active, resolved_inputs.net_to_gross),
```

```diff
--- a/src/ccs_screen/web/schemas.py
+++ b/src/ccs_screen/web/schemas.py
@@
-from pydantic import BaseModel, ConfigDict, Field, StrictInt
+from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator
+from typing import Literal
@@
+class NetToGrossModel(BaseModel):
+    """Optional declaration of the net-to-gross that thickness_m implies."""
+
+    model_config = _STRICT
+    low: float = Field(..., gt=0, le=1)
+    high: float = Field(..., gt=0, le=1)
+    net_criterion: Literal["porosity_permeability", "porosity_only",
+                           "permeability_only", "lithology_net_sand",
+                           "flow_unit", "unspecified"]
+    net_basis: Literal["log_derived", "core_derived", "model_derived",
+                       "analogue", "assumed", "unknown"]
+    cutoff_note: str | None = Field(default=None, max_length=500)
+    thickness_convention: Literal["measured", "tvd", "tst"] | None = None
+
+    @model_validator(mode="after")
+    def _ordered(self):
+        if self.low > self.high:
+            raise ValueError(f"low must be <= high, got ({self.low}, {self.high})")
+        return self
+
+
 class UserInputsModel(BaseModel):
@@
     thickness_m: float = Field(...)
+    net_to_gross: NetToGrossModel | None = Field(
+        default=None,
+        description=("Optional: the net-to-gross that thickness_m implies. "
+                     "Recorded for provenance; not used in any calculation."),
+    )
```

---

## 9. Estimated review effort

| Item | Size |
| --- | --- |
| `api.py` | ~150 added lines, 6 edited |
| `schemas.py` | ~55 added, 2 edited |
| New test file | ~330 lines, 20 tests |
| `docs/http-api.md` | ~40 lines |
| Existing files touched | **0** beyond the two above |

The riskiest line is the `_interpretation` signature change, because it is
called from `screen_well`, `compare_temperature_methods` and
`screening_funnel`. The new parameter defaults to `None`, so the two call sites
that are not updated keep working -- but they would then emit the
"not declared" warning unconditionally. **A reviewer should decide whether
`screening_funnel` (fleet-level, often called without user inputs) should emit
it at all.** That is the one open question in the patch.

---

**Phase 1 draft ready for implementation review -- no files modified.**
