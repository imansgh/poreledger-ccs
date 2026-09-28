"""Auditable screening scenarios.

A scenario is a named, dated, versioned bundle of engineering assumptions that
can fill the inputs the source data does not provide::

    NormalizedWellRecord + ScreeningScenario -> ScreeningConfig
                                             or IncompleteScreening

The point of the layer is bookkeeping, not science. Applying a scenario never
makes an assumption look like a measurement: source-derived values always win,
the assumed parameters are listed explicitly on every result, and a well that is
still short of a required input comes back as :class:`IncompleteScreening` with
the reasons attached rather than as a config with a plausible filler in it.

Temperature is deliberately outside the assumable set. It is the one required
input the pilot sources do *supply*, and letting a scenario override it would
quietly discard the only reservoir measurement in the dataset.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Mapping

from ccs_screen.config import REQUIRED_FIELDS, ScreeningConfig
from ccs_screen.ingest.assumptions import (
    ASSUMABLE,
    Assumption,
    AssumptionError,
    AssumptionSet,
    Citation,
    EvidenceClass,
)
from ccs_screen.ingest.completeness import REQUIRED_SOURCES
from ccs_screen.ingest.provenance import Confidence, FieldValue, Provenance
from ccs_screen.ingest.records import NormalizedWellRecord

#: Inputs a scenario is allowed to supply. Identical to ASSUMABLE, restated here
#: so the exclusion of temperature_k is visible at the scenario boundary too.
SCENARIO_PARAMETERS = tuple(ASSUMABLE)

#: Required inputs that a scenario may never supply.
SOURCE_ONLY_PARAMETERS = tuple(f for f in REQUIRED_FIELDS if f not in SCENARIO_PARAMETERS)

#: Standard gravity, for the hydrostatic pressure model.
STANDARD_GRAVITY_M_S2 = 9.80665

#: Mandatory disclosure wherever an area is shown. Reconnaissance found the only
#: polygons in the dataset are expired mining licences (median 268 km2, max
#: 21,138 km2), which are legal instruments unrelated to reservoir geometry.
AREA_POLICY_STATEMENT = (
    "Area is not inferred from administrative licence boundaries. "
    "area_m2 is explicit scenario or user input."
)

#: Gross stratigraphic thickness is source-derived; net storage thickness is not
#: derivable from it without a net-to-gross ratio, which no source provides.
#: Legacy paths only (``thickness_m`` input); the approved model has no
#: thickness input and states STORAGE_INTERVAL_POLICY_STATEMENT instead.
NET_THICKNESS_POLICY_STATEMENT = (
    "Net storage thickness is not derived from gross stratigraphic thickness. "
    "thickness_m is explicit scenario or user input."
)

#: Approved Model Contract (M1, Final Gap Closure A): the thickness term is the
#: gross thickness h_g of a caller-designated storage-assessment interval.
STORAGE_INTERVAL_POLICY_STATEMENT = (
    "The storage-assessment interval (z_top, z_base) is explicit user input in the "
    "same depth coordinate and datum as depth_m. It is not inferred from total depth "
    "or from stratigraphic units. h_g = z_base - z_top is derived; there is no "
    "independent thickness input."
)

#: A6 -- the exact wording the Model Contract requires wherever the storage
#: efficiency prior is documented.
STORAGE_EFFICIENCY_PRIOR_STATEMENT = (
    "The Uniform distribution is a project-defined prior over the DOE-derived "
    "P15–P85 bounds. It is not claimed to reproduce the DOE probability distribution."
)

#: O2 -- every screening path other than the approved model keeps its behaviour
#: and carries this label.
NOT_VALIDATED = "NOT_VALIDATED"

NOT_VALIDATED_STATEMENT = (
    "NOT_VALIDATED: this path predates the approved Model Contract "
    "(docs/phase13-owner-decision-record.md) and does not implement it. It is kept "
    "for compatibility and demonstration only; its outputs are not validated "
    "scientific screening results."
)

#: Reasons given when a parameter with no literature basis is not supplied.
UNSUPPORTED_PARAMETER_REASON = {
    "area_m2": AREA_POLICY_STATEMENT,
    "thickness_m": NET_THICKNESS_POLICY_STATEMENT,
}


@dataclass(frozen=True)
class ScreeningScenario:
    """A reproducible set of engineering assumptions, with its paperwork."""

    name: str
    description: str
    assumptions: AssumptionSet
    version: str = "1"
    date: str = field(default_factory=lambda: date.today().isoformat())
    rationale: str = ""
    citation: Citation | str | None = None
    #: Brine density (kg/m3), scalar or (low, high). When set, pressure_pa is
    #: DERIVED per well from source-derived depth rather than assumed flat.
    #: A single pressure range cannot serve wells spanning 897-6694 m.
    brine_density_kg_m3: float | tuple[float, float] | None = None

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise AssumptionError("a scenario needs a name")
        if not str(self.description).strip():
            raise AssumptionError("a scenario needs a description")
        if self.brine_density_kg_m3 is not None and self.assumptions.get("pressure_pa"):
            raise AssumptionError(
                f"scenario {self.name!r} declares both a brine density (pressure derived "
                f"from depth) and a flat pressure_pa assumption; choose one"
            )
        overreach = [p for p in self.assumptions.parameters if p not in SCENARIO_PARAMETERS]
        if overreach:
            raise AssumptionError(
                f"scenario {self.name!r} tries to assume {', '.join(sorted(overreach))}, "
                f"which must come from source data (assumable: {', '.join(SCENARIO_PARAMETERS)})"
            )

    @property
    def assumed_parameters(self) -> tuple[str, ...]:
        return self.assumptions.parameters

    def get(self, parameter: str) -> Assumption | None:
        return self.assumptions.get(parameter)

    @property
    def derives_pressure_from_depth(self) -> bool:
        return self.brine_density_kg_m3 is not None

    def pressure_gradient_pa_per_m(self) -> tuple[float, float] | None:
        """Hydrostatic gradient implied by the declared brine density."""
        if self.brine_density_kg_m3 is None:
            return None
        rho = self.brine_density_kg_m3
        low, high = (rho, rho) if not isinstance(rho, (list, tuple)) else (rho[0], rho[1])
        return (low * STANDARD_GRAVITY_M_S2, high * STANDARD_GRAVITY_M_S2)

    def hydrostatic_pressure_pa(self, depth_m: float) -> tuple[float, float]:
        """P = rho * g * depth, as a (low, high) pair."""
        gradient = self.pressure_gradient_pa_per_m()
        if gradient is None:
            raise AssumptionError(f"scenario {self.name!r} declares no brine density")
        return (gradient[0] * float(depth_m), gradient[1] * float(depth_m))

    @property
    def is_deterministic(self) -> bool:
        """True when every assumption is a point value rather than a range."""
        return all(not isinstance(a.value, (list, tuple)) for a in self.assumptions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "date": self.date,
            "rationale": self.rationale,
            "deterministic": self.is_deterministic,
            "area_policy": AREA_POLICY_STATEMENT,
            "net_thickness_policy": NET_THICKNESS_POLICY_STATEMENT,
            "brine_density_kg_m3": (list(self.brine_density_kg_m3)
                                    if isinstance(self.brine_density_kg_m3, (list, tuple))
                                    else self.brine_density_kg_m3),
            "pressure_derived_from_depth": self.derives_pressure_from_depth,
            "citation": (self.citation.to_dict() if isinstance(self.citation, Citation)
                         else self.citation),
            "assumed_parameters": list(self.assumed_parameters),
            "assumptions": [a.to_dict() for a in self.assumptions],
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ScreeningScenario":
        assumptions = AssumptionSet.from_mapping(
            {"name": data.get("name", "unnamed"), "assumptions": data.get("assumptions", [])}
        )
        return cls(
            name=str(data.get("name", "")),
            description=str(data.get("description", "")),
            assumptions=assumptions,
            version=str(data.get("version", "1")),
            date=str(data.get("date", date.today().isoformat())),
            rationale=str(data.get("rationale", "")),
            citation=data.get("citation"),
            brine_density_kg_m3=(tuple(bd) if isinstance(bd := data.get("brine_density_kg_m3"), list)
                                 else bd),
        )

    @classmethod
    def from_json_file(cls, path: str | Path) -> "ScreeningScenario":
        p = Path(path)
        try:
            text = p.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise AssumptionError(f"scenario file not found: {p}") from None
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AssumptionError(f"{p} is not valid JSON: {exc.msg} (line {exc.lineno})") from None
        if not isinstance(data, Mapping):
            raise AssumptionError(f"{p}: a scenario must be a JSON object")
        return cls.from_mapping(data)


@dataclass(frozen=True)
class IncompleteScreening:
    """A well the scenario could not complete, and why.

    Returned rather than raised: at fleet scale, an unscreenable well is an
    ordinary outcome to be counted, not an exception to be handled.
    """

    canonical_id: str
    scenario_name: str
    missing_fields: tuple[str, ...]
    reasons: tuple[tuple[str, str], ...] = ()

    @property
    def screenable(self) -> bool:
        return False

    def describe(self) -> str:
        parts = [f"{self.canonical_id}: not screenable under {self.scenario_name!r}"]
        for name, reason in self.reasons:
            parts.append(f"    {name}: {reason}")
        return "\n".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "well_id": self.canonical_id,
            "scenario": self.scenario_name,
            "screenable": False,
            "missing_fields": list(self.missing_fields),
            "reasons": {name: reason for name, reason in self.reasons},
        }


@dataclass(frozen=True)
class ResolvedInput:
    """One screening input, with where it came from kept attached."""

    name: str
    value: float | list[float]
    provenance: Provenance
    detail: str = ""
    method: str | None = None
    unit: str = ""
    rationale: str | None = None
    citation: Citation | str | None = None
    evidence_class: EvidenceClass | None = None
    author: str | None = None
    assumption_ignored: bool = False
    derivation: str | None = None

    @property
    def is_assumed(self) -> bool:
        return self.provenance is Provenance.ASSUMED

    @property
    def is_from_source(self) -> bool:
        return self.provenance in (Provenance.EXTRACTED, Provenance.DERIVED)

    @property
    def label(self) -> str:
        """Short tag for display.

        ``MODELLED`` exists so a value computed from source data *under a
        declared generic model* (hydrostatic pressure from depth) cannot be read
        as a plain measurement. It is neither purely source nor purely assumed.
        """
        if self.evidence_class is EvidenceClass.USER_INPUT:
            return "USER"
        if self.is_assumed:
            return "ASSUMED"
        if (self.provenance is Provenance.DERIVED
                and self.evidence_class is EvidenceClass.GENERIC):
            return "MODELLED"
        return "source"

    def to_dict(self) -> dict[str, Any]:
        """Machine-readable audit trail.

        A client receiving this can always tell whether a number was measured,
        computed from a measurement, or supplied by a person -- and on whose
        authority.
        """
        out: dict[str, Any] = {
            "value": self.value,
            "unit": self.unit,
            "provenance": self.provenance.value,
            "assumed": self.is_assumed,
            "from_source": self.is_from_source,
            "label": self.label,
            "assumption_ignored_source_won": self.assumption_ignored,
            "evidence_class": (self.evidence_class.value if self.evidence_class
                               else EvidenceClass.UNSUPPORTED.value),
        }
        if self.detail:
            out["detail"] = self.detail
        if self.method:
            out["method"] = self.method
        if self.derivation:
            out["derivation"] = self.derivation
        if self.rationale:
            out["rationale"] = self.rationale
        if self.author:
            out["author"] = self.author
        out["citation"] = (self.citation.to_dict() if isinstance(self.citation, Citation)
                           else self.citation)
        return out


def resolve_inputs(
    record: NormalizedWellRecord, scenario: ScreeningScenario
) -> tuple[dict[str, ResolvedInput], list[tuple[str, str]]]:
    """Work out each required input's value and origin.

    Returns ``(resolved, missing)``. Source-derived values take precedence: an
    assumption for a parameter the record already supplies is ignored, and the
    fact is recorded on the resolved input.
    """
    values = record.field_values()
    resolved: dict[str, ResolvedInput] = {}
    missing: list[tuple[str, str]] = []

    for name in REQUIRED_FIELDS:
        source_attr = REQUIRED_SOURCES.get(name)
        fv: FieldValue | None = values.get(source_attr) if source_attr else None
        assumption = scenario.get(name)

        if fv is not None and fv.is_present:
            ignored = assumption is not None
            detail = f"{fv.provenance.value} from source"
            if ignored:
                detail += "; scenario assumption ignored (source data wins)"
            resolved[name] = ResolvedInput(
                name=name, value=fv.value, provenance=fv.provenance,
                detail=detail, method=fv.method, unit=fv.unit.value,
                derivation=fv.derivation, assumption_ignored=ignored,
                evidence_class=EvidenceClass.SITE_SPECIFIC,
            )
            continue

        # Pressure from source depth under the scenario's declared hydrostatic
        # model. A flat pressure range cannot serve wells spanning 897-6694 m.
        if (name == "pressure_pa" and scenario.derives_pressure_from_depth
                and record.depth_m.is_present):
            depth = float(record.depth_m.value)
            low, high = scenario.hydrostatic_pressure_pa(depth)
            gradient = scenario.pressure_gradient_pa_per_m()
            resolved[name] = ResolvedInput(
                name=name, value=[low, high], provenance=Provenance.DERIVED,
                detail="derived from source depth and the scenario hydrostatic model",
                method="hydrostatic_from_depth", unit="Pa",
                derivation=(
                    f"P = rho*g*z with rho = {scenario.brine_density_kg_m3} kg/m3, "
                    f"g = {STANDARD_GRAVITY_M_S2} m/s2, z = {depth:g} m (source-derived); "
                    f"gradient {gradient[0]:.0f}-{gradient[1]:.0f} Pa/m"
                ),
                rationale=(
                    "Normally-pressured hydrostatic assumption. The structured sources "
                    "contain no pressure, so this is not calibrated by any measurement "
                    "for this well. "
                    f"z is the source depth as recorded (datum: {record.depth_datum.value}), "
                    "not a reservoir reference depth. Where the water level stands, and "
                    "so where the brine column begins, is not established; the "
                    "direction of any resulting pressure error is unknown."
                ),
                evidence_class=EvidenceClass.GENERIC,
                author=f"{scenario.name} v{scenario.version}",
            )
            continue

        if assumption is not None:
            resolved[name] = ResolvedInput(
                name=name, value=assumption.config_value(), provenance=Provenance.ASSUMED,
                detail=f"assumed by {assumption.author} ({scenario.name} v{scenario.version})",
                method="engineering_assumption",
                unit=(assumption.unit.value if assumption.unit else ""),
                rationale=assumption.rationale, citation=assumption.citation,
                evidence_class=assumption.evidence_class, author=assumption.author,
            )
            continue

        if name == "pressure_pa" and scenario.derives_pressure_from_depth:
            missing.append((name, "scenario derives pressure from depth, but this well "
                                  "has no source-derived depth"))
            continue
        if name in SOURCE_ONLY_PARAMETERS:
            reason = (
                f"no source value, and {name} may not be supplied by a scenario "
                f"(assumable: {', '.join(SCENARIO_PARAMETERS)})"
            )
        elif name in UNSUPPORTED_PARAMETER_REASON:
            reason = (f"{UNSUPPORTED_PARAMETER_REASON[name]} "
                      f"Scenario {scenario.name!r} does not supply it.")
        elif fv is not None and fv.notes:
            reason = f"{fv.notes[0]}; scenario {scenario.name!r} does not supply it"
        else:
            reason = f"scenario {scenario.name!r} does not supply it"
        missing.append((name, reason))

    return resolved, missing


def apply_scenario(
    record: NormalizedWellRecord, scenario: ScreeningScenario
) -> ScreeningConfig | IncompleteScreening:
    """Combine a normalized well with a scenario.

    Produces a :class:`ScreeningConfig` when every required input is available,
    otherwise an :class:`IncompleteScreening` naming what is still short.
    """
    resolved, missing = resolve_inputs(record, scenario)
    if missing:
        return IncompleteScreening(
            canonical_id=record.canonical_id,
            scenario_name=scenario.name,
            missing_fields=tuple(name for name, _ in missing),
            reasons=tuple(missing),
        )

    payload: dict[str, Any] = {"well_id": record.canonical_id}
    for name, resolved_input in resolved.items():
        payload[name] = resolved_input.value
    if record.depth_m.is_present:
        payload["depth_m"] = float(record.depth_m.value)
    return ScreeningConfig.from_mapping(payload)


# ---------------------------------------------------------------------------
# Built-in scenarios
#
# Every number below is a PLACEHOLDER chosen to exercise the pipeline, not a
# site estimate or a literature value. Reconnaissance established that the
# source data constrains none of these parameters, so nothing here could be
# authoritative. Replace them before any result is presented as a real
# screening outcome.
#
# Phase 14 (owner decision O2): the placeholder scenarios are kept operational
# and every output they produce is NOT_VALIDATED. They are not migrated to the
# approved Model Contract.
# ---------------------------------------------------------------------------

_PLACEHOLDER = (
    "PLACEHOLDER value, not a site estimate and not a literature citation. "
    "The source data does not constrain this parameter; replace before use."
)


#: Placeholder scenarios carry a citation object whose evidence class says, in
#: machine-readable form, that there is no evidence. That is deliberate: a
#: client filtering on evidence_class must be able to reject these without
#: reading prose.
_PLACEHOLDER_CITATION = Citation(
    source="none",
    title="No source. Placeholder value for exercising the pipeline.",
    year=2026,
    text=("PLACEHOLDER - no literature basis. Not for use in any reported result. "
          "See docs/scenario-literature-review.md."),
    evidence_class=EvidenceClass.PLACEHOLDER,
)


def _placeholder(parameter: str, value: Any, note: str) -> Assumption:
    return Assumption(
        parameter=parameter,
        value=value,
        author="unassigned (placeholder)",
        rationale=f"{_PLACEHOLDER} {note}",
        citation=_PLACEHOLDER_CITATION,
    )


CONSERVATIVE = ScreeningScenario(
    name="conservative-placeholder",
    description=(
        "NOT_VALIDATED legacy placeholder scenario. Deliberately pessimistic point "
        "values, for a lower-bound sanity check. All values are placeholders."
    ),
    version="0-placeholder",
    rationale=(
        "Exists to show the scenario machinery under a deterministic, low-side "
        "assumption set. Produces P10 = P50 = P90 because every input is a point."
    ),
    assumptions=AssumptionSet(
        name="conservative-placeholder",
        assumptions=(
            _placeholder("area_m2", 5.0e7, "Low end of the range used by the demo."),
            _placeholder("thickness_m", 25.0, "Low end of the engine's representative net thickness."),
            _placeholder("porosity", 0.12, "Low end of the demo prior."),
            _placeholder("pressure_pa", 1.2e7, "Low end of the demo prior."),
            _placeholder("storage_efficiency", 0.02, "Low end of the demo prior."),
        ),
    ),
)

CENTRAL = ScreeningScenario(
    name="central-placeholder",
    description=(
        "NOT_VALIDATED legacy placeholder scenario. Mid-range point values for a "
        "deterministic base case. All values are placeholders."
    ),
    version="0-placeholder",
    rationale=(
        "Midpoints of the demo priors. Deterministic, so the Monte Carlo collapses "
        "and the result is a single capacity number."
    ),
    assumptions=AssumptionSet(
        name="central-placeholder",
        assumptions=(
            _placeholder("area_m2", 1.0e8, "Midpoint of the demo prior."),
            _placeholder("thickness_m", 40.0, "Midpoint of the demo prior."),
            _placeholder("porosity", 0.18, "Midpoint of the demo prior."),
            _placeholder("pressure_pa", 1.6e7, "Midpoint of the demo prior."),
            _placeholder("storage_efficiency", 0.045, "Midpoint of the demo prior."),
        ),
    ),
)

SENSITIVITY = ScreeningScenario(
    name="sensitivity-placeholder",
    description=(
        "NOT_VALIDATED legacy placeholder scenario. Ranges on the major uncertain "
        "parameters, so the Monte Carlo produces a real P10/P50/P90 spread. All "
        "ranges are placeholders."
    ),
    version="0-placeholder",
    rationale=(
        "The ranges are the demo priors, carried over to exercise uncertainty "
        "propagation. They express no knowledge about any particular well: the "
        "spread they produce is a property of the placeholders, not of the subsurface."
    ),
    assumptions=AssumptionSet(
        name="sensitivity-placeholder",
        assumptions=(
            _placeholder("area_m2", (5.0e7, 1.5e8), "Demo prior range."),
            _placeholder("thickness_m", (25.0, 55.0), "Demo prior range."),
            _placeholder("porosity", (0.12, 0.24), "Demo prior range."),
            _placeholder("pressure_pa", (1.2e7, 2.0e7), "Demo prior range."),
            _placeholder("storage_efficiency", (0.02, 0.07), "Demo prior range."),
        ),
    ),
)

# ---------------------------------------------------------------------------
# literature-screening-v1
#
# The one scenario in this file whose values have a documented basis. Every
# number is traceable to a primary source read in full; see
# docs/scenario-literature-review.md for the review, including what the
# literature does NOT support.
#
# Nothing here is site-specific. No value was measured in, or derived from,
# any well in this dataset.
# ---------------------------------------------------------------------------

CSLF_2008 = Citation(
    source="CSLF Task Force on CO2 Storage Capacity Estimation / USDOE Capacity and Fairways Subgroup",
    title=("Comparison between Methodologies Recommended for Estimation of CO2 Storage "
           "Capacity in Geological Media - Phase III Report"),
    year=2008,
    text=("Bachu, S. (2008). Comparison between Methodologies Recommended for Estimation of "
          "CO2 Storage Capacity in Geological Media, Phase III Report. CSLF-T-2008-04, "
          "21 April 2008. Carbon Sequestration Leadership Forum, Technical Group."),
    evidence_class=EvidenceClass.GENERIC,
    locator="Executive Summary / Section on USDOE methodology",
    quote=("through Monte Carlo simulations ... the USDOE Subgroup obtained a range of values "
           "for these storage efficiency coefficients for the 15% and 85% confidence intervals, "
           "which are ... between 1% and 4% for deep saline aquifers"),
    url="https://hgeo.energy.gov/archives/cslf/sites/default/files/documents/PhaseIIIReportStorageCapacityEstimationTaskForce0408.pdf",
)

DONDA_2011 = Citation(
    source="Donda, Volpi, Persoglia & Parushev (OGS, Trieste)",
    title="CO2 storage potential of deep saline aquifers: The case of Italy",
    year=2011,
    text=("Donda, F., Volpi, V., Persoglia, S., Parushev, D. (2011). CO2 storage potential of "
          "deep saline aquifers: The case of Italy. International Journal of Greenhouse Gas "
          "Control, 5(2), 327-335. DOI: 10.1016/j.ijggc.2010.08.009"),
    evidence_class=EvidenceClass.REGIONAL,
    locator="Table 2, porosity column (13 Italian potential reservoirs)",
    quote=("Key parameters of the Italian potential reservoirs for the evaluation of the CO2 "
           "geological storage: porosity 10-35%, derived from sonic-log P-wave velocities"),
    url="https://doi.org/10.1016/j.ijggc.2010.08.009",
)

_LIT_AUTHOR = "Iman (geoenergy engineer)"
_LIT_DATE = "2026-09-19"
_NOT_SITE_SPECIFIC = (
    "LITERATURE-DERIVED, NOT SITE-SPECIFIC: this value was not measured in, or "
    "derived from, this well."
)

LITERATURE_SCREENING_V1 = ScreeningScenario(
    name="literature-screening-v1",
    description=(
        "Literature-constrained parameter set of the approved Model Contract. Storage "
        "efficiency and porosity are taken from published methodology and a regional "
        "Italian compilation; brine density declares the hydrostatic model. In the public "
        "API this scenario runs the approved model: the caller supplies area_m2 and the "
        "storage-assessment interval (z_top, z_base), and both named water-level scenarios "
        "(GROUND_REFERENCE, SEA_LEVEL_SENSITIVITY) are evaluated. Applied through the "
        "legacy scenario resolver (ccs-ingest) its outputs are NOT_VALIDATED."
    ),
    version="1",
    date=_LIT_DATE,
    rationale=(
        "Replaces placeholder values with the only two parameters the literature supports "
        "for this play type. Area and the storage-assessment interval have no literature "
        "basis and are explicit user inputs rather than silent defaults. Produces "
        "scenario-based capacity, not a site estimate. See docs/scenario-literature-review.md "
        "and docs/phase13-owner-decision-record.md."
    ),
    citation=CSLF_2008,
    brine_density_kg_m3=(1020.0, 1100.0),
    assumptions=AssumptionSet(
        name="literature-screening-v1",
        assumptions=(
            Assumption(
                parameter="storage_efficiency",
                value=(0.01, 0.04),
                author=_LIT_AUTHOR,
                date=_LIT_DATE,
                rationale=(
                    "CSLF/USDOE P15-P85 storage efficiency for deep saline aquifers, from "
                    "Monte Carlo simulation of North American formations. Applied to Italian "
                    "aquifers by Donda et al. (2011). Aggregate DOE-style E: the gross-to-net "
                    "reduction is represented inside E, which is never divided by a "
                    "net-to-gross ratio. "
                    + STORAGE_EFFICIENCY_PRIOR_STATEMENT + " "
                    + _NOT_SITE_SPECIFIC +
                    " The range is calibrated against basin-scale area, which is why area_m2 "
                    "must be supplied consistently (see the area policy)."
                ),
                citation=CSLF_2008,
                confidence=Confidence.MEDIUM,
            ),
            Assumption(
                parameter="porosity",
                value=(0.10, 0.35),
                author=_LIT_AUTHOR,
                date=_LIT_DATE,
                rationale=(
                    "Full porosity range across the 13 Italian potential reservoirs tabulated "
                    "by Donda et al. (2011), Table 2, derived by those authors from sonic-log "
                    "P-wave velocities. Same play type (Plio-Pleistocene clastics) as the "
                    "pilot wells. " + _NOT_SITE_SPECIFIC +
                    " The range is wide: its ends differ by 3.5x in capacity."
                ),
                citation=DONDA_2011,
                confidence=Confidence.MEDIUM,
            ),
        ),
    ),
)

#: Parameters literature-screening-v1 deliberately does NOT supply. Both are
#: linear multipliers in the capacity equation, so a run is always conditional
#: on two numbers the user provides and the data cannot check.
LITERATURE_UNSUPPORTED = ("area_m2", "thickness_m")


#: The empty scenario: source data only, no assumptions at all. Applying it
#: answers "what could be screened from the data as it stands", which is the
#: honest baseline every other scenario should be read against.
NO_SCENARIO = ScreeningScenario(
    name="source-data-only",
    description="No assumptions. Only wells whose every required input is in the source data.",
    version="1",
    rationale="The baseline: what the data supports with nothing added.",
    assumptions=AssumptionSet(name="source-data-only"),
)

#: Name -> scenario, for CLI lookup.
BUILTIN_SCENARIOS: dict[str, ScreeningScenario] = {
    "none": NO_SCENARIO,
    "conservative": CONSERVATIVE,
    "central": CENTRAL,
    "sensitivity": SENSITIVITY,
    "literature-screening-v1": LITERATURE_SCREENING_V1,
    "literature": LITERATURE_SCREENING_V1,
}


def load_scenario(reference: str) -> ScreeningScenario:
    """Resolve a built-in scenario name or a path to a scenario JSON file."""
    key = str(reference).strip().lower()
    if key in BUILTIN_SCENARIOS:
        return BUILTIN_SCENARIOS[key]
    path = Path(reference)
    if path.exists():
        return ScreeningScenario.from_json_file(path)
    raise AssumptionError(
        f"unknown scenario {reference!r}: not a built-in "
        f"({', '.join(sorted(BUILTIN_SCENARIOS))}) and not an existing file"
    )
