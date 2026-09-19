"""Completeness reporting and the gate onto ScreeningConfig.

This is where the pipeline's governing rule is enforced: a well that lacks a
required input produces a *rejection naming what is missing*, never a config
with a plausible-looking substitute in it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from ccs_screen.config import REQUIRED_FIELDS, ScreeningConfig
from ccs_screen.ingest.assumptions import NO_ASSUMPTIONS, AssumptionSet
from ccs_screen.ingest.provenance import FieldValue, Provenance
from ccs_screen.ingest.records import NormalizedWellRecord

#: How each ScreeningConfig requirement is satisfied from a normalized record.
#: ``thickness_m`` maps to nothing: net storage thickness is not derivable from
#: the sources, so it can only ever arrive as an explicit assumption.
REQUIRED_SOURCES: dict[str, str | None] = {
    "area_m2": None,
    "thickness_m": None,
    "porosity": None,
    "pressure_pa": None,
    "temperature_k": "temperature_k",
    "storage_efficiency": None,
}

#: Reported alongside the required fields because they are the pilot's real
#: output even though the engine does not consume them directly.
INFORMATIONAL = ("depth_m", "gross_thickness_m")

TICK, CROSS = "OK", "--"


@dataclass(frozen=True)
class FieldStatus:
    name: str
    available: bool
    provenance: Provenance
    detail: str = ""


@dataclass(frozen=True)
class WellCompleteness:
    """Per-well answer to: can this well be screened, and if not, why not."""

    canonical_id: str
    statuses: tuple[FieldStatus, ...]
    missing_required: tuple[str, ...]
    assumed: tuple[str, ...]
    conflicts: tuple[str, ...] = ()

    @property
    def screening_config_buildable(self) -> bool:
        return not self.missing_required

    def render(self) -> str:
        lines = [self.canonical_id, ""]
        width = max(len(s.name) for s in self.statuses)
        for s in self.statuses:
            mark = TICK if s.available else CROSS
            tail = f"  ({s.detail})" if s.detail else ""
            lines.append(f"  {s.name:<{width}}  {mark}{tail}")
        lines.append("")
        lines.append(f"  screening_config_buildable = {str(self.screening_config_buildable).lower()}")
        if self.missing_required:
            lines.append(f"  missing_required_fields    = {', '.join(self.missing_required)}")
        if self.assumed:
            lines.append(f"  supplied_by_assumption     = {', '.join(self.assumed)}")
        for c in self.conflicts:
            lines.append(f"  conflict: {c}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "well_id": self.canonical_id,
            "fields": {s.name: {"available": s.available,
                                "provenance": s.provenance.value,
                                "detail": s.detail} for s in self.statuses},
            "screening_config_buildable": self.screening_config_buildable,
            "missing_required_fields": list(self.missing_required),
            "supplied_by_assumption": list(self.assumed),
            "conflicts": list(self.conflicts),
        }


def assess(record: NormalizedWellRecord,
           assumptions: AssumptionSet = NO_ASSUMPTIONS) -> WellCompleteness:
    """Determine whether a well can be screened, and record why not."""
    values = record.field_values()
    statuses: list[FieldStatus] = []
    missing: list[str] = []
    assumed: list[str] = []

    for name in INFORMATIONAL:
        fv = values.get(name, FieldValue.missing())
        statuses.append(FieldStatus(
            name=name, available=fv.is_present, provenance=fv.provenance,
            detail=("" if fv.is_present else (fv.notes[0] if fv.notes else "")),
        ))

    for name in REQUIRED_FIELDS:
        source_attr = REQUIRED_SOURCES.get(name)
        fv = values.get(source_attr) if source_attr else None
        assumption = assumptions.get(name)

        if fv is not None and fv.is_present:
            statuses.append(FieldStatus(name, True, fv.provenance,
                                        f"{fv.provenance.value} via {fv.method or 'source'}"))
            continue
        if assumption is not None:
            assumed.append(name)
            statuses.append(FieldStatus(name, True, Provenance.ASSUMED,
                                        f"assumed by {assumption.author}"))
            continue
        missing.append(name)
        reason = ""
        if fv is not None and fv.notes:
            reason = fv.notes[0]
        elif source_attr is None:
            reason = "no source; requires an explicit engineering assumption"
        statuses.append(FieldStatus(name, False, Provenance.MISSING, reason))

    return WellCompleteness(
        canonical_id=record.canonical_id,
        statuses=tuple(statuses),
        missing_required=tuple(missing),
        assumed=tuple(assumed),
        conflicts=tuple(c.describe() for c in record.conflicts),
    )


class IncompleteWellError(ValueError):
    """A ScreeningConfig was requested for a well that lacks required inputs."""

    def __init__(self, canonical_id: str, missing: Iterable[str]):
        self.canonical_id = canonical_id
        self.missing = tuple(missing)
        super().__init__(
            f"{canonical_id}: cannot build ScreeningConfig, missing "
            f"{', '.join(self.missing)}. Supply these as declared assumptions "
            f"or leave the well unscreened -- defaults are not substituted."
        )


def build_screening_config(record: NormalizedWellRecord,
                           assumptions: AssumptionSet = NO_ASSUMPTIONS) -> ScreeningConfig:
    """Construct a ScreeningConfig, or refuse and say what is missing.

    Extracted and derived values win over assumptions for the same parameter:
    an assumption can fill a hole, never overwrite a measurement.
    """
    status = assess(record, assumptions)
    if not status.screening_config_buildable:
        raise IncompleteWellError(record.canonical_id, status.missing_required)

    values = record.field_values()
    payload: dict[str, Any] = {"well_id": record.canonical_id}
    for name in REQUIRED_FIELDS:
        source_attr = REQUIRED_SOURCES.get(name)
        fv = values.get(source_attr) if source_attr else None
        if fv is not None and fv.is_present:
            payload[name] = fv.value
            continue
        assumption = assumptions.get(name)
        assert assumption is not None  # guaranteed by assess()
        payload[name] = assumption.config_value()

    if record.depth_m.is_present:
        payload["depth_m"] = float(record.depth_m.value)
    return ScreeningConfig.from_mapping(payload)


@dataclass
class CompletenessReport:
    """Fleet-level view across every normalized well."""

    wells: tuple[WellCompleteness, ...] = field(default_factory=tuple)
    sources: tuple[str, ...] = field(default_factory=tuple)

    @property
    def buildable(self) -> tuple[WellCompleteness, ...]:
        return tuple(w for w in self.wells if w.screening_config_buildable)

    def missing_field_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {name: 0 for name in REQUIRED_FIELDS}
        for w in self.wells:
            for name in w.missing_required:
                counts[name] = counts.get(name, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))

    def field_availability(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for w in self.wells:
            for s in w.statuses:
                counts[s.name] = counts.get(s.name, 0) + (1 if s.available else 0)
        return counts

    def render_summary(self) -> str:
        n = len(self.wells)
        lines = [
            "CCS ingestion completeness report",
            f"  sources                : {', '.join(self.sources) or 'none'}",
            f"  wells normalized       : {n}",
            f"  screenable             : {len(self.buildable)}",
            "",
            "Field availability",
        ]
        if n:
            for name, count in self.field_availability().items():
                lines.append(f"  {name:<20} {count:>5} / {n}")
            lines += ["", "Missing required fields (well count)"]
            for name, count in self.missing_field_counts().items():
                lines.append(f"  {name:<20} {count:>5}")
        conflicts = sum(len(w.conflicts) for w in self.wells)
        lines += ["", f"Conflicts recorded       : {conflicts}"]
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sources": list(self.sources),
            "wells_normalized": len(self.wells),
            "screenable": len(self.buildable),
            "field_availability": self.field_availability(),
            "missing_required_counts": self.missing_field_counts(),
            "wells": [w.to_dict() for w in self.wells],
        }


def build_report(records: Iterable[NormalizedWellRecord],
                 assumptions: AssumptionSet = NO_ASSUMPTIONS,
                 sources: Iterable[str] = ()) -> CompletenessReport:
    return CompletenessReport(
        wells=tuple(assess(r, assumptions) for r in records),
        sources=tuple(sources),
    )
