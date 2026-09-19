"""The engineering-assumption layer.

Porosity, pressure, area and storage efficiency are not available from any
structured source in the pilot dataset. They can only enter a screening run as
*declared* assumptions, and this module is the single door they come through.

An assumption must name its author, date and rationale. That is not
bureaucracy: a capacity number produced from an undocumented area is
indistinguishable from one produced from a measured area, and the whole point
of this pipeline is that the difference stays visible.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

from ccs_screen.ingest.provenance import (
    Confidence,
    FieldValue,
    Provenance,
    SourceRef,
    Unit,
)

#: Parameters an assumption is allowed to supply. Nothing else may be assumed:
#: depth, temperature and stratigraphy come from sources or not at all.
ASSUMABLE = ("area_m2", "porosity", "pressure_pa", "storage_efficiency", "thickness_m")


class EvidenceClass(str, Enum):
    """How close a value's evidence is to the well it is being applied to.

    The distinction is the whole point of the citation machinery: a range from a
    North American simulation and a measurement from the well next door are both
    "cited", and must not read the same way.
    """

    SITE_SPECIFIC = "site_specific"   # measured in, or derived from, this well
    REGIONAL = "regional"             # same play/basin, different wells
    GENERIC = "generic"               # published methodology, not this region
    USER_INPUT = "user_input"         # supplied at run time by the person asking
    UNSUPPORTED = "unsupported"       # no literature basis and nobody supplied one
    PLACEHOLDER = "placeholder"       # exists to exercise code, not to be used


@dataclass(frozen=True)
class Citation:
    """Structured provenance for an adopted value.

    ``text`` is the full reference as it would appear in a bibliography;
    the split fields exist so a client can filter and display without parsing.
    """

    source: str                 # organisation or lead author
    title: str
    year: int
    text: str                   # full citation
    evidence_class: EvidenceClass = EvidenceClass.GENERIC
    locator: str | None = None  # page, table or section the value came from
    quote: str | None = None    # verbatim supporting sentence, where short
    url: str | None = None

    def __post_init__(self) -> None:
        for name in ("source", "title", "text"):
            if not str(getattr(self, name)).strip():
                raise AssumptionError(f"citation needs a non-empty {name}")
        if not isinstance(self.year, int) or not 1900 <= self.year <= 2100:
            raise AssumptionError(f"citation year looks wrong: {self.year!r}")

    @property
    def is_site_specific(self) -> bool:
        return self.evidence_class is EvidenceClass.SITE_SPECIFIC

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "title": self.title,
            "year": self.year,
            "text": self.text,
            "evidence_class": self.evidence_class.value,
            "locator": self.locator,
            "quote": self.quote,
            "url": self.url,
        }


_UNITS = {
    "area_m2": Unit.SQUARE_METRE,
    "porosity": Unit.DIMENSIONLESS,
    "pressure_pa": Unit.PASCAL,
    "storage_efficiency": Unit.DIMENSIONLESS,
    "thickness_m": Unit.METRE,
}


class AssumptionError(ValueError):
    """An assumption is missing required justification or targets a bad field."""


@dataclass(frozen=True)
class Assumption:
    """One declared engineering assumption.

    ``value`` may be a scalar point estimate or a ``(low, high)`` range, matching
    what :class:`~ccs_screen.config.ScreeningConfig` accepts.
    """

    parameter: str
    value: float | tuple[float, float]
    author: str
    rationale: str
    date: str = field(default_factory=lambda: date.today().isoformat())
    citation: Citation | str | None = None
    unit: Unit | None = None
    confidence: Confidence = Confidence.LOW

    def __post_init__(self) -> None:
        problems = []
        if self.parameter not in ASSUMABLE:
            problems.append(
                f"{self.parameter!r} is not an assumable parameter "
                f"(allowed: {', '.join(ASSUMABLE)})"
            )
        if not str(self.author).strip():
            problems.append("author is required -- an assumption needs an owner")
        if not str(self.rationale).strip():
            problems.append("rationale is required -- an undocumented assumption is not usable")
        if isinstance(self.value, (list, tuple)):
            if len(self.value) != 2:
                problems.append("a range value must be (low, high)")
            elif self.value[0] > self.value[1]:
                problems.append(f"range low must be <= high, got {self.value}")
        if problems:
            raise AssumptionError("; ".join(problems))
        if self.unit is None:
            object.__setattr__(self, "unit", _UNITS.get(self.parameter, Unit.NONE))

    def as_field_value(self) -> FieldValue:
        """Render as a FieldValue carrying ASSUMED provenance.

        The stored value is the midpoint for ranges, but ``notes`` keeps the
        declared range so nothing is lost.
        """
        value = self.value
        notes = [f"assumed by {self.author} on {self.date}: {self.rationale}"]
        if isinstance(value, (list, tuple)):
            notes.append(f"declared range {tuple(value)}")
            stored: float = float(sum(value)) / 2.0
        else:
            stored = float(value)
        if self.citation is not None:
            notes.append(f"citation: {self.citation_text}")
            notes.append(f"evidence class: {self.evidence_class.value}")
        return FieldValue(
            value=stored,
            unit=self.unit or Unit.NONE,
            provenance=Provenance.ASSUMED,
            confidence=self.confidence,
            method="engineering_assumption",
            source=SourceRef(file=f"assumption:{self.author}"),
            notes=tuple(notes),
        )

    @property
    def evidence_class(self) -> EvidenceClass:
        """How close this value's evidence is to the well it is applied to."""
        if isinstance(self.citation, Citation):
            return self.citation.evidence_class
        return EvidenceClass.UNSUPPORTED if self.citation is None else EvidenceClass.GENERIC

    @property
    def citation_text(self) -> str | None:
        if isinstance(self.citation, Citation):
            return self.citation.text
        return self.citation

    @property
    def is_literature_derived(self) -> bool:
        """True only for a structured citation that is not a placeholder."""
        return (
            isinstance(self.citation, Citation)
            and self.citation.evidence_class not in
            (EvidenceClass.PLACEHOLDER, EvidenceClass.UNSUPPORTED,
             EvidenceClass.USER_INPUT)
        )

    def config_value(self) -> float | list[float]:
        """The value in the shape ScreeningConfig expects."""
        if isinstance(self.value, (list, tuple)):
            return [float(self.value[0]), float(self.value[1])]
        return float(self.value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "parameter": self.parameter,
            "value": list(self.value) if isinstance(self.value, (list, tuple)) else self.value,
            "unit": (self.unit or Unit.NONE).value,
            "author": self.author,
            "date": self.date,
            "rationale": self.rationale,
            "citation": (self.citation.to_dict() if isinstance(self.citation, Citation)
                         else self.citation),
            "citation_text": self.citation_text,
            "evidence_class": self.evidence_class.value,
            "literature_derived": self.is_literature_derived,
            "confidence": self.confidence.value,
        }


@dataclass(frozen=True)
class AssumptionSet:
    """A named, auditable bundle of assumptions applied to a screening run."""

    name: str
    assumptions: tuple[Assumption, ...] = ()

    def __post_init__(self) -> None:
        seen: dict[str, int] = {}
        for a in self.assumptions:
            seen[a.parameter] = seen.get(a.parameter, 0) + 1
        duplicated = sorted(p for p, n in seen.items() if n > 1)
        if duplicated:
            raise AssumptionError(f"parameter assumed more than once: {', '.join(duplicated)}")

    def __len__(self) -> int:
        return len(self.assumptions)

    def __iter__(self):
        return iter(self.assumptions)

    def get(self, parameter: str) -> Assumption | None:
        for a in self.assumptions:
            if a.parameter == parameter:
                return a
        return None

    @property
    def parameters(self) -> tuple[str, ...]:
        return tuple(a.parameter for a in self.assumptions)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "AssumptionSet":
        name = str(data.get("name", "unnamed"))
        entries: Iterable[Mapping[str, Any]] = data.get("assumptions", [])
        built = []
        for entry in entries:
            kwargs = dict(entry)
            value = kwargs.pop("value", None)
            if isinstance(value, list):
                value = tuple(value)
            citation = kwargs.pop("citation", None)
            if isinstance(citation, Mapping):
                cdata = dict(citation)
                ev = cdata.pop("evidence_class", None)
                cdata.pop("is_site_specific", None)
                citation = Citation(
                    source=str(cdata.pop("source", "")),
                    title=str(cdata.pop("title", "")),
                    year=int(cdata.pop("year", 0) or 0),
                    text=str(cdata.pop("text", "")),
                    evidence_class=EvidenceClass(ev) if ev else EvidenceClass.GENERIC,
                    locator=cdata.pop("locator", None),
                    quote=cdata.pop("quote", None),
                    url=cdata.pop("url", None),
                )
            conf = kwargs.pop("confidence", None)
            built.append(
                Assumption(
                    parameter=str(kwargs.pop("parameter", "")),
                    value=value,
                    author=str(kwargs.pop("author", "")),
                    rationale=str(kwargs.pop("rationale", "")),
                    date=str(kwargs.pop("date", date.today().isoformat())),
                    citation=citation,
                    confidence=Confidence(conf) if conf else Confidence.LOW,
                )
            )
        return cls(name=name, assumptions=tuple(built))

    @classmethod
    def from_json_file(cls, path: str | Path) -> "AssumptionSet":
        p = Path(path)
        try:
            text = p.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise AssumptionError(f"assumption file not found: {p}") from None
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AssumptionError(f"{p} is not valid JSON: {exc.msg} (line {exc.lineno})") from None
        return cls.from_mapping(data)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "assumptions": [a.to_dict() for a in self.assumptions]}


#: An empty set -- the honest default. Ingestion applies no assumptions unless
#: a caller supplies them.
NO_ASSUMPTIONS = AssumptionSet(name="none")
