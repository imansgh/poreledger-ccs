"""The two record layers: verbatim source capture, then SI normalization.

``RawWellRecord`` is deliberately dumb. It stores what a source said, as a
string, with enough coordinates to find the cell again. It never coerces,
converts or drops anything, so a later bug in normalization can always be
re-run against the untouched input.

``NormalizedWellRecord`` is the SI-normalized view, where every field is a
:class:`~ccs_screen.ingest.provenance.FieldValue` carrying its own lineage.
Fields the sources do not provide are present and explicitly MISSING rather
than absent or defaulted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

from ccs_screen.ingest.identity import WellIdentity, canonical_well_id
from ccs_screen.ingest.provenance import (
    Conflict,
    Confidence,
    FieldValue,
    Provenance,
    SourceRef,
    Unit,
)
from ccs_screen.ingest.units import DepthDatum


@dataclass(frozen=True)
class RawWellRecord:
    """One verbatim observation, exactly as a source stated it."""

    canonical_id: str
    original_name: str
    field_name: str
    original_value: str
    source: SourceRef
    original_unit: str | None = None
    extraction_method: str = "structured_read"
    datum: DepthDatum | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def capture(
        cls,
        well_name: str,
        field_name: str,
        value: Any,
        source: SourceRef,
        **kwargs: Any,
    ) -> "RawWellRecord":
        identity = canonical_well_id(well_name)
        return cls(
            canonical_id=identity.canonical,
            original_name=str(well_name),
            field_name=field_name,
            original_value="" if value is None else str(value),
            source=source,
            **kwargs,
        )

    def to_dict(self) -> dict[str, Any]:
        out = {
            "canonical_id": self.canonical_id,
            "original_name": self.original_name,
            "field": self.field_name,
            "original_value": self.original_value,
            "source": str(self.source),
            "extraction_method": self.extraction_method,
        }
        if self.original_unit:
            out["original_unit"] = self.original_unit
        if self.datum:
            out["datum"] = self.datum.value
        if self.notes:
            out["notes"] = list(self.notes)
        return out


class ThicknessKind(str, Enum):
    """The three thicknesses this domain must never conflate.

    Reconnaissance found only GROSS_STRATIGRAPHIC available (91-2557 m across
    the pilot wells), while the engine's ``thickness_m`` means NET_STORAGE
    (tens of metres). Substituting one for the other overstates capacity by
    20-50x, so they are separate types and no code path converts between them.
    """

    GROSS_STRATIGRAPHIC = "gross_stratigraphic"
    NET_STORAGE = "net_storage"
    AQUIFER_HYDRAULIC = "aquifer_hydraulic"


@dataclass(frozen=True)
class StratigraphicInterval:
    """One chronostratigraphic unit as logged, in metres along-hole."""

    top_m: float
    bottom_m: float
    lithology: str | None
    age: str | None
    source: SourceRef | None = None

    @property
    def gross_thickness_m(self) -> float:
        return self.bottom_m - self.top_m


@dataclass(frozen=True)
class TemperatureObservation:
    """One temperature reading with the method that produced it."""

    depth_m: float
    temperature_k: float
    method: str
    hours_since_circulation: float | None = None
    source: SourceRef | None = None
    original_celsius: float | None = None


@dataclass
class NormalizedWellRecord:
    """SI-normalized, provenance-carrying view of one well.

    Every attribute is a ``FieldValue``; none is a bare float. Reading
    ``record.depth_m.value`` without looking at ``.provenance`` is possible but
    the type makes the lineage hard to ignore.
    """

    identity: WellIdentity

    # Extracted / derived from structured sources.
    depth_m: FieldValue = field(default_factory=lambda: FieldValue.missing("no depth source"))
    depth_datum: DepthDatum = DepthDatum.UNKNOWN
    depth_msl_m: FieldValue = field(default_factory=lambda: FieldValue.missing("not datum-corrected"))
    latitude_deg: FieldValue = field(default_factory=lambda: FieldValue.missing())
    longitude_deg: FieldValue = field(default_factory=lambda: FieldValue.missing())
    surface_elevation_m: FieldValue = field(default_factory=lambda: FieldValue.missing())
    temperature_k: FieldValue = field(default_factory=lambda: FieldValue.missing("no temperature source"))
    gross_thickness_m: FieldValue = field(default_factory=lambda: FieldValue.missing("no stratigraphy"))
    net_storage_thickness_m: FieldValue = field(
        default_factory=lambda: FieldValue.missing(
            "net thickness is not derivable from gross stratigraphy without net-to-gross"
        )
    )
    aquifer_thickness_m: FieldValue = field(
        default_factory=lambda: FieldValue.missing("no hydraulic-unit definition in sources")
    )
    operator: FieldValue = field(default_factory=lambda: FieldValue.missing())
    year: FieldValue = field(default_factory=lambda: FieldValue.missing())
    outcome: FieldValue = field(default_factory=lambda: FieldValue.missing())

    # Never populated by ingestion -- see docs/ingestion.md.
    porosity: FieldValue = field(
        default_factory=lambda: FieldValue.missing(
            "no numeric porosity in any source; logs record only qualitative type codes"
        )
    )
    pressure_pa: FieldValue = field(
        default_factory=lambda: FieldValue.missing("no pressure data in any structured source")
    )
    area_m2: FieldValue = field(
        default_factory=lambda: FieldValue.missing(
            "no structural closure data; only administrative licence polygons exist"
        )
    )
    storage_efficiency: FieldValue = field(
        default_factory=lambda: FieldValue.missing("engineering assumption by definition")
    )

    # Supporting detail.
    intervals: tuple[StratigraphicInterval, ...] = field(default_factory=tuple)
    temperatures: tuple[TemperatureObservation, ...] = field(default_factory=tuple)
    raw_records: tuple[RawWellRecord, ...] = field(default_factory=tuple)
    conflicts: tuple[Conflict, ...] = field(default_factory=tuple)
    source_names: tuple[str, ...] = field(default_factory=tuple)

    @property
    def canonical_id(self) -> str:
        return self.identity.canonical

    def field_values(self) -> dict[str, FieldValue]:
        return {
            name: getattr(self, name)
            for name in (
                "depth_m", "depth_msl_m", "latitude_deg", "longitude_deg",
                "surface_elevation_m", "temperature_k", "gross_thickness_m",
                "net_storage_thickness_m", "aquifer_thickness_m", "operator",
                "year", "outcome", "porosity", "pressure_pa", "area_m2",
                "storage_efficiency",
            )
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_id": self.canonical_id,
            "original_names": sorted({r.original_name for r in self.raw_records}) or [self.identity.original],
            "sources": list(self.source_names),
            "depth_datum": self.depth_datum.value,
            "fields": {name: fv.to_dict() for name, fv in self.field_values().items()},
            "n_intervals": len(self.intervals),
            "n_temperature_observations": len(self.temperatures),
            "conflicts": [c.describe() for c in self.conflicts],
        }
