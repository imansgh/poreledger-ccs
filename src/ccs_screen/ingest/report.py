"""Screening reports: what went in, where it came from, what came out.

Every report separates source-derived inputs from assumed ones and prints the
provenance next to each value, so a capacity number can never be read without
also seeing how much of it rests on assumptions.

The functions here are plain Python returning dataclasses with ``to_dict()``,
so the future web API can call them directly without going through the CLI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from ccs_screen.config import REQUIRED_FIELDS, ScreeningConfig
from ccs_screen.ingest.provenance import (
    TEMPERATURE_METHOD_RANK,
    Provenance,
    TemperatureMethod,
)
from ccs_screen.ingest.records import NormalizedWellRecord
from ccs_screen.ingest.scenario import (
    IncompleteScreening,
    ResolvedInput,
    ScreeningScenario,
    apply_scenario,
    resolve_inputs,
)
from ccs_screen.monte_carlo import UniformPriors, run_capacity_mc

DEFAULT_SAMPLES = 2000
DEFAULT_SEED = 42


@dataclass(frozen=True)
class CapacityResult:
    p10_mt: float
    p50_mt: float
    p90_mt: float
    mean_mt: float
    n_samples: int
    deterministic: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "p10_mt": self.p10_mt,
            "p50_mt": self.p50_mt,
            "p90_mt": self.p90_mt,
            "mean_mt": self.mean_mt,
            "n_samples": self.n_samples,
            "deterministic": self.deterministic,
        }


@dataclass(frozen=True)
class TemperatureDetail:
    """Which temperature was used, by which method, and what else was on offer."""

    value_k: float | None
    method: str | None
    provenance: Provenance
    derivation: str | None = None
    alternatives: tuple[tuple[float, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "value_k": self.value_k,
            "value_degc": None if self.value_k is None else round(self.value_k - 273.15, 2),
            "method": self.method,
            "provenance": self.provenance.value,
            "derivation": self.derivation,
            "alternatives": [{"value_k": v, "source": s} for v, s in self.alternatives],
        }


@dataclass(frozen=True)
class WellScreeningReport:
    """Everything needed to audit one well's screening outcome."""

    canonical_id: str
    scenario_name: str
    scenario_version: str
    screenable: bool
    inputs: tuple[ResolvedInput, ...] = ()
    temperature: TemperatureDetail | None = None
    result: CapacityResult | None = None
    missing_fields: tuple[str, ...] = ()
    missing_reasons: tuple[tuple[str, str], ...] = ()
    conflicts: tuple[str, ...] = ()
    depth_m: float | None = None

    @property
    def source_inputs(self) -> tuple[ResolvedInput, ...]:
        return tuple(i for i in self.inputs if not i.is_assumed)

    @property
    def assumed_inputs(self) -> tuple[ResolvedInput, ...]:
        return tuple(i for i in self.inputs if i.is_assumed)

    @property
    def modelled_inputs(self) -> tuple[ResolvedInput, ...]:
        """Derived from source data under a declared generic model."""
        return tuple(i for i in self.inputs if i.label == "MODELLED")

    @property
    def assumption_flags(self) -> tuple[str, ...]:
        return tuple(i.name for i in self.assumed_inputs)

    @property
    def rests_entirely_on_assumptions(self) -> bool:
        """True when no required input came from the source data."""
        return bool(self.inputs) and not self.source_inputs

    def to_dict(self) -> dict[str, Any]:
        return {
            "well_id": self.canonical_id,
            "scenario": {"name": self.scenario_name, "version": self.scenario_version},
            "screenable": self.screenable,
            "depth_m": self.depth_m,
            "source_derived_inputs": [i.name for i in self.source_inputs],
            "assumed_inputs": [i.name for i in self.assumed_inputs],
            "modelled_inputs": [i.name for i in self.modelled_inputs],
            "assumption_flags": list(self.assumption_flags),
            "screening_inputs": {i.name: i.to_dict() for i in self.inputs},
            "temperature": self.temperature.to_dict() if self.temperature else None,
            "conflicts": list(self.conflicts),
            "missing_fields": list(self.missing_fields),
            "missing_reasons": {k: v for k, v in self.missing_reasons},
            "result": self.result.to_dict() if self.result else None,
        }

    def render(self) -> str:
        lines = [
            f"{self.canonical_id}",
            f"  scenario                 : {self.scenario_name} v{self.scenario_version}",
        ]
        if self.depth_m is not None:
            lines.append(f"  total depth              : {self.depth_m:.1f} m")

        lines.append("")
        lines.append("  source-derived inputs    : " + (
            ", ".join(i.name for i in self.source_inputs) or "none"))
        lines.append("  assumed inputs           : " + (
            ", ".join(i.name for i in self.assumed_inputs) or "none"))
        if self.modelled_inputs:
            lines.append("  modelled inputs          : " + ", ".join(
                f"{i.name} ({i.method})" for i in self.modelled_inputs))

        if self.temperature:
            t = self.temperature
            lines += ["", "  temperature"]
            if t.value_k is None:
                lines.append("      value                : MISSING")
            else:
                lines.append(f"      value                : {t.value_k:.2f} K "
                             f"({t.value_k - 273.15:.1f} degC)")
            lines.append(f"      method               : {t.method or 'n/a'}")
            lines.append(f"      provenance           : {t.provenance.value}")
            for value, src in t.alternatives:
                lines.append(f"      not selected         : {value:.2f} K  ({src})")

        if self.inputs:
            lines += ["", "  screening inputs"]
            width = max(len(i.name) for i in self.inputs)
            for i in self.inputs:
                tag = f"{i.label:<8}"
                value = i.value if not isinstance(i.value, list) else (
                    f"[{i.value[0]:g}, {i.value[1]:g}]")
                shown = value if isinstance(value, str) else f"{value:g}"
                lines.append(f"      {i.name:<{width}}  {tag}  {shown}")

        if self.assumption_flags:
            lines += ["", f"  assumption flags         : {len(self.assumption_flags)} of "
                          f"{len(REQUIRED_FIELDS)} required inputs are assumed"]
            if self.rests_entirely_on_assumptions:
                lines.append("      WARNING: no required input is source-derived")

        if self.conflicts:
            lines += ["", "  conflicts"]
            for c in self.conflicts:
                lines.append(f"      {c}")

        lines += ["", "  screening result"]
        if self.result:
            r = self.result
            lines.append(f"      P10 / P50 / P90      : {r.p10_mt:.1f} / {r.p50_mt:.1f} / "
                         f"{r.p90_mt:.1f} Mt")
            lines.append(f"      mean                 : {r.mean_mt:.1f} Mt")
            if r.deterministic:
                lines.append("      NOTE                 : every prior is a point value, "
                             "so P10 = P50 = P90")
        else:
            lines.append("      not computed")

        lines += ["", f"  screenable               : {str(self.screenable).lower()}"]
        if self.missing_fields:
            lines.append(f"  missing required fields  : {', '.join(self.missing_fields)}")
            for name, reason in self.missing_reasons:
                lines.append(f"      {name}: {reason}")
        return "\n".join(lines)


def _temperature_detail(record: NormalizedWellRecord) -> TemperatureDetail:
    fv = record.temperature_k
    alternatives: tuple[tuple[float, str], ...] = ()
    for conflict in record.conflicts:
        if conflict.field_name == "temperature_k":
            alternatives = tuple((float(v), str(s)) for v, s in conflict.alternatives)
            break
    return TemperatureDetail(
        value_k=fv.value if fv.is_present else None,
        method=fv.method,
        provenance=fv.provenance,
        derivation=fv.derivation,
        alternatives=alternatives,
    )


def run_capacity(config: ScreeningConfig, samples: int = DEFAULT_SAMPLES,
                 seed: int = DEFAULT_SEED) -> CapacityResult:
    """Run the existing screening engine over a config."""
    priors = UniformPriors(**config.prior_ranges())
    result = run_capacity_mc(priors.sample(samples, seed=seed))
    return CapacityResult(
        p10_mt=result.p10_mt, p50_mt=result.p50_mt, p90_mt=result.p90_mt,
        mean_mt=result.mean_mt, n_samples=result.n, deterministic=config.is_deterministic(),
    )


def screen_well(record: NormalizedWellRecord, scenario: ScreeningScenario,
                samples: int = DEFAULT_SAMPLES, seed: int = DEFAULT_SEED) -> WellScreeningReport:
    """Screen one well under one scenario, keeping provenance intact."""
    outcome = apply_scenario(record, scenario)
    resolved, missing = resolve_inputs(record, scenario)
    conflicts = tuple(c.describe() for c in record.conflicts)
    temperature = _temperature_detail(record)
    depth = float(record.depth_m.value) if record.depth_m.is_present else None

    if isinstance(outcome, IncompleteScreening):
        return WellScreeningReport(
            canonical_id=record.canonical_id,
            scenario_name=scenario.name, scenario_version=scenario.version,
            screenable=False,
            inputs=tuple(resolved.values()),
            temperature=temperature,
            missing_fields=outcome.missing_fields,
            missing_reasons=outcome.reasons,
            conflicts=conflicts, depth_m=depth,
        )

    ordered = tuple(resolved[name] for name in REQUIRED_FIELDS if name in resolved)
    return WellScreeningReport(
        canonical_id=record.canonical_id,
        scenario_name=scenario.name, scenario_version=scenario.version,
        screenable=True,
        inputs=ordered,
        temperature=temperature,
        result=run_capacity(outcome, samples=samples, seed=seed),
        conflicts=conflicts, depth_m=depth,
    )


# -- temperature-method comparison ------------------------------------------


@dataclass(frozen=True)
class TemperatureVariant:
    method: str
    temperature_k: float
    depth_m: float
    p50_mt: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "temperature_k": self.temperature_k,
            "temperature_degc": round(self.temperature_k - 273.15, 2),
            "depth_m": self.depth_m,
            "p50_mt": self.p50_mt,
        }


@dataclass(frozen=True)
class TemperatureComparison:
    """What capacity would be, had a different temperature method been believed.

    Reconnaissance found method choice moves CO2 density -- and therefore
    capacity, which is linear in density -- by 6-15%. This keeps that visible
    instead of letting the selected method look like the only option.
    """

    canonical_id: str
    selected_method: str | None
    variants: tuple[TemperatureVariant, ...] = ()

    @property
    def p50_spread_mt(self) -> float | None:
        values = [v.p50_mt for v in self.variants if v.p50_mt is not None]
        return (max(values) - min(values)) if len(values) > 1 else None

    @property
    def p50_spread_percent(self) -> float | None:
        values = [v.p50_mt for v in self.variants if v.p50_mt is not None]
        if len(values) < 2 or min(values) <= 0:
            return None
        return 100.0 * (max(values) - min(values)) / min(values)

    def to_dict(self) -> dict[str, Any]:
        return {
            "well_id": self.canonical_id,
            "selected_method": self.selected_method,
            "variants": [v.to_dict() for v in self.variants],
            "p50_spread_mt": self.p50_spread_mt,
            "p50_spread_percent": self.p50_spread_percent,
        }


def compare_temperature_methods(
    record: NormalizedWellRecord, scenario: ScreeningScenario,
    samples: int = 500, seed: int = DEFAULT_SEED,
) -> TemperatureComparison:
    """Re-screen a well once per available reservoir temperature method.

    No method is declared globally correct; the comparison simply shows what
    each one implies for capacity under the same scenario.
    """
    selected = record.temperature_k.method
    reservoir = [
        t for t in record.temperatures
        if TEMPERATURE_METHOD_RANK.get(TemperatureMethod(t.method), 99) < 99
    ]
    if not reservoir:
        return TemperatureComparison(record.canonical_id, selected, ())

    deepest = max(t.depth_m for t in reservoir)
    near_td = [t for t in reservoir if t.depth_m >= 0.85 * deepest]

    base = apply_scenario(record, scenario)
    variants: list[TemperatureVariant] = []
    for obs in sorted(near_td, key=lambda t: (t.method, -t.depth_m)):
        p50: float | None = None
        if isinstance(base, ScreeningConfig):
            payload: dict[str, Any] = {
                name: list(value) for name, value in base.prior_ranges().items()
            }
            payload["temperature_k"] = obs.temperature_k  # the only field varied
            payload["well_id"] = base.well_id
            config = ScreeningConfig.from_mapping(payload)
            p50 = run_capacity(config, samples=samples, seed=seed).p50_mt
        variants.append(TemperatureVariant(
            method=obs.method, temperature_k=obs.temperature_k,
            depth_m=obs.depth_m, p50_mt=p50,
        ))
    return TemperatureComparison(record.canonical_id, selected, tuple(variants))


# -- fleet funnel ------------------------------------------------------------


@dataclass
class ScreeningFunnel:
    """Fleet-level counts that keep the three completeness states distinct.

    * source-complete   -- every required input came from the data (currently 0)
    * scenario-complete -- a scenario supplied the rest
    * screenable        -- a config was actually built and run
    """

    normalized: int = 0
    with_temperature: int = 0
    with_gross_thickness: int = 0
    with_depth: int = 0
    source_complete: int = 0
    scenario_complete: int = 0
    screenable: int = 0
    blocked: tuple[tuple[str, tuple[str, ...]], ...] = field(default_factory=tuple)
    scenario_name: str = ""
    scenario_version: str = ""

    @property
    def blocked_count(self) -> int:
        return len(self.blocked)

    def blocked_by_field(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for _, fields_ in self.blocked:
            for name in fields_:
                counts[name] = counts.get(name, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": {"name": self.scenario_name, "version": self.scenario_version},
            "normalized": self.normalized,
            "with_temperature": self.with_temperature,
            "with_gross_thickness": self.with_gross_thickness,
            "with_depth": self.with_depth,
            "source_complete": self.source_complete,
            "scenario_complete": self.scenario_complete,
            "screenable": self.screenable,
            "blocked": [{"well_id": w, "missing": list(f)} for w, f in self.blocked],
            "blocked_by_field": self.blocked_by_field(),
        }

    def render(self) -> str:
        lines = [
            "CCS screening funnel",
            f"  scenario                          : {self.scenario_name} v{self.scenario_version}",
            "",
            f"  {self.normalized} normalized wells",
            "",
            f"  {self.with_temperature} have temperature",
            f"  {self.with_gross_thickness} have gross thickness",
            f"  {self.with_depth} have depth",
            "",
            f"  {self.source_complete} screenable from source data alone",
            f"  {self.scenario_complete} scenario-complete (assumptions supplied the rest)",
            f"  {self.screenable} screenable",
            f"  {self.blocked_count} blocked",
        ]
        by_field = self.blocked_by_field()
        if by_field:
            lines.append("")
            for name, count in by_field.items():
                lines.append(f"  {count} blocked by missing {name}")
        return "\n".join(lines)


def build_funnel(records: Sequence[NormalizedWellRecord], scenario: ScreeningScenario,
                 reports: Iterable[WellScreeningReport] | None = None) -> ScreeningFunnel:
    """Count the fleet through each distinct completeness state."""
    from ccs_screen.ingest.scenario import NO_SCENARIO

    reports = list(reports) if reports is not None else [
        screen_well(r, scenario, samples=1) for r in records
    ]
    source_complete = sum(
        1 for r in records
        if not resolve_inputs(r, NO_SCENARIO)[1]
    )
    blocked = tuple(
        (rep.canonical_id, rep.missing_fields) for rep in reports if not rep.screenable
    )
    return ScreeningFunnel(
        normalized=len(records),
        with_temperature=sum(1 for r in records if r.temperature_k.is_present),
        with_gross_thickness=sum(1 for r in records if r.gross_thickness_m.is_present),
        with_depth=sum(1 for r in records if r.depth_m.is_present),
        source_complete=source_complete,
        scenario_complete=sum(1 for rep in reports if rep.screenable),
        screenable=sum(1 for rep in reports if rep.screenable),
        blocked=blocked,
        scenario_name=scenario.name,
        scenario_version=scenario.version,
    )
