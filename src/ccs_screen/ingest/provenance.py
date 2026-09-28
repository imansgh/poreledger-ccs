"""Provenance model: where every number came from, and how much to trust it.

The governing rule of this package is that an unavailable field is reported as
unavailable. A value never acquires a provenance it did not earn, and the
transition ``missing -> assumed`` only happens when a caller supplies an
explicit :class:`~ccs_screen.ingest.assumptions.Assumption`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Provenance(str, Enum):
    """How a field's value came to exist.

    The ordering mirrors the reconnaissance classification and is deliberately
    coarse: a reader can tell at a glance whether a number was read off a
    source, computed from one, or supplied by an engineer.
    """

    EXTRACTED = "extracted"       # read directly from a source cell
    DERIVED = "derived"           # computed from extracted values
    SPATIAL = "spatial"           # from structural / GIS data
    ASSUMED = "assumed"           # supplied by a declared engineering assumption
    MODEL_DEFAULT = "model_default"  # the engine's own documented default
    MISSING = "missing"           # no source, no assumption


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class Unit(str, Enum):
    METRE = "m"
    FOOT = "ft"
    KELVIN = "K"
    CELSIUS = "degC"
    PASCAL = "Pa"
    SQUARE_METRE = "m2"
    DEGREE = "deg"
    DIMENSIONLESS = "-"
    YEAR = "yr"
    NONE = ""


#: Temperature acquisition / correction methods seen in the Piemonte sources.
#: These are preserved verbatim rather than collapsed, because the choice
#: between them moves CO2 density (and therefore capacity) by 6-15%.
class TemperatureMethod(str, Enum):
    RAW = "raw"
    NON_STABILIZED = "non_stabilized"
    SQUARCI_TAFFI = "extrapolated_squarci_taffi"
    FERTL_WICHMANN = "extrapolated_fertl_wichmann"
    HORNER = "horner_corrected"
    SURFACE_AIR = "surface_air_mean"
    UNKNOWN = "unknown"


#: Ranked best-to-worst for reservoir temperature. Horner correction of a real
#: bottom-hole reading is the most defensible; a surface air mean is not a
#: reservoir temperature at all and is never selectable as one.
#:
#: Legacy paths only (owner decision O2). Under the approved Model Contract no
#: ranking of Fertl-Wichmann over Squarci-Taffi (or the reverse) is claimed
#: (S2); the approved model does not use this table.
TEMPERATURE_METHOD_RANK: dict[TemperatureMethod, int] = {
    TemperatureMethod.HORNER: 0,
    TemperatureMethod.FERTL_WICHMANN: 1,
    TemperatureMethod.SQUARCI_TAFFI: 2,
    TemperatureMethod.NON_STABILIZED: 3,
    TemperatureMethod.RAW: 4,
    TemperatureMethod.UNKNOWN: 5,
    TemperatureMethod.SURFACE_AIR: 99,
}

TEMPERATURE_METHOD_CONFIDENCE: dict[TemperatureMethod, Confidence] = {
    TemperatureMethod.HORNER: Confidence.HIGH,
    TemperatureMethod.FERTL_WICHMANN: Confidence.MEDIUM,
    TemperatureMethod.SQUARCI_TAFFI: Confidence.MEDIUM,
    TemperatureMethod.NON_STABILIZED: Confidence.LOW,
    TemperatureMethod.RAW: Confidence.LOW,
    TemperatureMethod.UNKNOWN: Confidence.LOW,
    TemperatureMethod.SURFACE_AIR: Confidence.NONE,
}


@dataclass(frozen=True)
class SourceRef:
    """Where a raw value physically lives, precise enough to go back and look."""

    file: str
    table: str | None = None          # sheet name or CSV table
    row: int | None = None            # 1-based row within that table
    column: str | None = None

    def __str__(self) -> str:
        parts = [self.file]
        if self.table:
            parts.append(self.table)
        if self.row is not None:
            parts.append(f"row {self.row}")
        if self.column:
            parts.append(self.column)
        return " / ".join(parts)


@dataclass(frozen=True)
class Conflict:
    """Two sources disagree about the same field.

    Recorded, never silently resolved. The chosen value is whatever the
    normalizer picked; ``alternatives`` keeps what it did not pick.
    """

    field_name: str
    chosen: Any
    alternatives: tuple[tuple[Any, str], ...]  # (value, where it came from)
    note: str = ""

    def describe(self) -> str:
        alts = "; ".join(f"{v!r} ({src})" for v, src in self.alternatives)
        base = f"{self.field_name}: chose {self.chosen!r}, also saw {alts}"
        return f"{base} -- {self.note}" if self.note else base


@dataclass(frozen=True)
class FieldValue:
    """A single normalized quantity with its full lineage.

    ``value`` is ``None`` exactly when ``provenance is Provenance.MISSING``.
    """

    value: float | str | None
    unit: Unit = Unit.NONE
    provenance: Provenance = Provenance.MISSING
    confidence: Confidence = Confidence.NONE
    source: SourceRef | None = None
    method: str | None = None          # acquisition method, e.g. a TemperatureMethod
    derivation: str | None = None      # how a DERIVED value was computed
    original_value: str | None = None  # verbatim source text, before coercion
    original_unit: str | None = None
    conflicts: tuple[Conflict, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.provenance is Provenance.MISSING and self.value is not None:
            raise ValueError("a MISSING field cannot carry a value")
        if self.provenance is not Provenance.MISSING and self.value is None:
            raise ValueError(f"a {self.provenance.value} field must carry a value")
        if self.provenance is Provenance.DERIVED and not self.derivation:
            raise ValueError("a DERIVED field must record its derivation")

    @property
    def is_present(self) -> bool:
        return self.provenance is not Provenance.MISSING

    @property
    def is_from_source(self) -> bool:
        """True only for data actually read from or computed from a source."""
        return self.provenance in (Provenance.EXTRACTED, Provenance.DERIVED, Provenance.SPATIAL)

    @classmethod
    def missing(cls, reason: str = "") -> "FieldValue":
        return cls(
            value=None,
            provenance=Provenance.MISSING,
            confidence=Confidence.NONE,
            notes=(reason,) if reason else (),
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "value": self.value,
            "unit": self.unit.value,
            "provenance": self.provenance.value,
            "confidence": self.confidence.value,
        }
        if self.source:
            out["source"] = str(self.source)
        if self.method:
            out["method"] = self.method
        if self.derivation:
            out["derivation"] = self.derivation
        if self.original_value is not None:
            out["original_value"] = self.original_value
        if self.original_unit:
            out["original_unit"] = self.original_unit
        if self.conflicts:
            out["conflicts"] = [c.describe() for c in self.conflicts]
        if self.notes:
            out["notes"] = list(self.notes)
        return out
