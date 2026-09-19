"""Validated input contract between data ingestion and the screening engine.

This module is the stable boundary in::

    PDF / KML -> extraction -> validated well record -> ScreeningConfig
              -> ccs_screen -> screening result

It deliberately knows nothing about PDFs, KML, or any parser. A future
extractor's only job is to produce the JSON-shaped mapping that
:func:`ScreeningConfig.from_mapping` accepts; everything downstream is already
pinned by the engine's own tests.

Every field carries an explicit unit in its name (``_m``, ``_pa``, ``_k``,
``_m2``) or is explicitly dimensionless. Fractions use ``(-)``.

Range vs point values
---------------------
The engine's six capacity inputs are *uniform priors*, but extraction yields
point values. Both spellings are therefore accepted per field::

    "porosity": 0.18            -> a point estimate (low == high)
    "porosity": [0.12, 0.24]    -> an uncertainty range

A config built entirely from point values is a valid deterministic run: the
Monte Carlo collapses so P10 == P50 == P90. That is reported honestly rather
than hidden, and is the expected first output of the ingestion pipeline before
uncertainty is assigned.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Mapping

Range = tuple[float, float]


class ConfigError(ValueError):
    """Raised when a configuration is structurally or physically invalid.

    Subclasses :class:`ValueError` so the CLI's existing error path reports it
    on stderr with exit code 2, like every other rejected input.
    """

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems))


#: Physically meaningful bounds: (low, high, inclusive_high, unit).
#: These reject impossible values, not merely unusual ones -- a screening tool
#: must still be able to describe a bad prospect.
BOUNDS: dict[str, tuple[float, float, bool, str]] = {
    "area_m2": (0.0, 1e12, False, "m2"),
    "thickness_m": (0.0, 5_000.0, False, "m"),
    "porosity": (0.0, 1.0, False, "-"),
    "pressure_pa": (0.0, 2e8, False, "Pa"),
    "temperature_k": (0.0, 1_000.0, False, "K"),
    "storage_efficiency": (0.0, 1.0, False, "-"),
    "depth_m": (0.0, 15_000.0, False, "m"),
    "permeability_m2": (0.0, 1e-8, False, "m2"),
    "aquifer_thickness_m": (0.0, 5_000.0, False, "m"),
    "viscosity_pa_s": (0.0, 1.0, False, "Pa.s"),
    "radius_m": (0.0, 1e6, False, "m"),
    "years": (0.0, 10_000.0, False, "yr"),
    "aquifer_porosity": (0.0, 1.0, False, "-"),
    "compressibility_1_pa": (0.0, 1e-6, False, "1/Pa"),
    "rate_m3_s": (0.0, 1e4, False, "m3/s"),
    "fracture_gradient_pa_m": (0.0, 50_000.0, False, "Pa/m"),
    "safety_factor": (0.0, 1.0, True, "-"),
    "samples": (0.0, 1e7, False, "count"),
}

#: The six capacity inputs the engine cannot run without.
REQUIRED_FIELDS = (
    "area_m2",
    "thickness_m",
    "porosity",
    "pressure_pa",
    "temperature_k",
    "storage_efficiency",
)

#: Fields expressed as uniform priors (scalar or [low, high]).
RANGE_FIELDS = REQUIRED_FIELDS


@dataclass(frozen=True)
class ScreeningConfig:
    """A complete, validated screening input set.

    Required (uniform priors; scalar or ``[low, high]``):
        area_m2, thickness_m, porosity, pressure_pa, temperature_k,
        storage_efficiency

    Optional metadata:
        well_id -- free-text provenance label, carried into the report

    Optional scalars default to the engine's documented screening defaults.
    """

    # Required capacity priors.
    area_m2: Range
    thickness_m: Range
    porosity: Range
    pressure_pa: Range
    temperature_k: Range
    storage_efficiency: Range

    # Provenance.
    well_id: str | None = None

    # Injectivity / Theis brine analog.
    depth_m: float = 2_000.0
    permeability_m2: float = 8e-14
    aquifer_thickness_m: float = 40.0
    viscosity_pa_s: float = 4.5e-4
    radius_m: float = 500.0
    years: float = 10.0
    aquifer_porosity: float = 0.18
    compressibility_1_pa: float = 1.2e-9
    rate_m3_s: float = 0.08
    fracture_gradient_pa_m: float = 15_000.0
    safety_factor: float = 0.9

    # Run control.
    samples: int = 2_000
    seed: int = 42

    def __post_init__(self) -> None:
        problems: list[str] = []
        for name in RANGE_FIELDS:
            problems += _check_range(name, getattr(self, name))
        for spec in fields(self):
            if spec.name in RANGE_FIELDS or spec.name in ("well_id", "seed"):
                continue
            problems += _check_scalar(spec.name, getattr(self, spec.name))
        if self.well_id is not None and not str(self.well_id).strip():
            problems.append("well_id: must be a non-empty string when present")
        if problems:
            raise ConfigError(sorted(problems))

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ScreeningConfig":
        """Build from a JSON-shaped mapping, validating structure and physics.

        Reports *every* problem at once rather than the first, so an extractor
        gets a complete diagnosis per well instead of one error per re-run.
        """
        if not isinstance(data, Mapping):
            raise ConfigError([f"config root must be a JSON object, got {type(data).__name__}"])

        known = {spec.name for spec in fields(cls)}
        problems: list[str] = []

        unknown = sorted(set(data) - known)
        if unknown:
            problems.append(
                f"unknown field(s): {', '.join(unknown)} (known: {', '.join(sorted(known))})"
            )

        missing = [name for name in REQUIRED_FIELDS if name not in data]
        if missing:
            problems.append(f"missing required field(s): {', '.join(missing)}")

        kwargs: dict[str, Any] = {}
        for name in sorted(known & set(data)):
            value = data[name]
            if name == "well_id":
                kwargs[name] = value
                continue
            if name in RANGE_FIELDS:
                parsed, err = _coerce_range(name, value)
            else:
                parsed, err = _coerce_scalar(name, value)
            if err:
                problems.append(err)
                continue
            kwargs[name] = parsed
            # Bound-check here as well as in __post_init__, so a config with
            # both a missing field and an out-of-range value reports both in
            # one pass instead of one error per re-run.
            if name in RANGE_FIELDS:
                problems += _check_range(name, parsed)
            else:
                problems += _check_scalar(name, parsed)

        if problems:
            raise ConfigError(sorted(set(problems)))
        return cls(**kwargs)

    @classmethod
    def from_json_file(cls, path: str | Path) -> "ScreeningConfig":
        """Load and validate a JSON config file."""
        p = Path(path)
        try:
            text = p.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise ConfigError([f"config file not found: {p}"]) from None
        except OSError as exc:
            raise ConfigError([f"cannot read config file {p}: {exc}"]) from None
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigError(
                [f"{p} is not valid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})"]
            ) from None
        return cls.from_mapping(data)

    def prior_ranges(self) -> dict[str, Range]:
        """The six capacity priors, ready for ``UniformPriors(**...)``."""
        return {name: getattr(self, name) for name in RANGE_FIELDS}

    def is_deterministic(self) -> bool:
        """True when every prior is a point value, so the Monte Carlo collapses."""
        return all(low == high for low, high in self.prior_ranges().values())


def _unit(name: str) -> str:
    return BOUNDS[name][3] if name in BOUNDS else "-"


def _unit_suffix(name: str) -> str:
    """Trailing unit for messages; empty for dimensionless fields."""
    unit = _unit(name)
    return "" if unit == "-" else f" {unit}"


def _coerce_number(name: str, value: Any) -> tuple[float | None, str | None]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None, f"{name}: expected a number{_unit_suffix(name)}, got {type(value).__name__} ({value!r})"
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        return None, f"{name}: must be a finite number{_unit_suffix(name)}, got {value!r}"
    return number, None


def _coerce_scalar(name: str, value: Any) -> tuple[float | int | None, str | None]:
    number, err = _coerce_number(name, value)
    if err:
        return None, err
    if name in ("samples", "seed"):
        return int(number), None
    return number, None


def _coerce_range(name: str, value: Any) -> tuple[Range | None, str | None]:
    if isinstance(value, (list, tuple)):
        if len(value) != 2:
            return None, f"{name}: a range must have exactly 2 values [low, high], got {len(value)}"
        low, err_low = _coerce_number(name, value[0])
        high, err_high = _coerce_number(name, value[1])
        if err_low or err_high:
            return None, err_low or err_high
        return (float(low), float(high)), None
    number, err = _coerce_number(name, value)
    if err:
        return None, err
    return (number, number), None


def _bounds_message(name: str, value: float) -> str | None:
    if name not in BOUNDS:
        return None
    low, high, inclusive_high = BOUNDS[name][:3]
    unit = _unit_suffix(name)
    over = value > high if inclusive_high else value >= high
    if value <= low:
        return f"{name}: must be > {low:g}{unit}, got {value:g}"
    if over:
        limit = "<=" if inclusive_high else "<"
        return f"{name}: must be {limit} {high:g}{unit}, got {value:g}"
    return None


def _check_scalar(name: str, value: Any) -> list[str]:
    number, err = _coerce_number(name, value)
    if err:
        return [err]
    message = _bounds_message(name, number)
    return [message] if message else []


def _check_range(name: str, value: Any) -> list[str]:
    if not isinstance(value, tuple) or len(value) != 2:
        return [f"{name}: expected a (low, high) range{_unit_suffix(name)}, got {value!r}"]
    problems: list[str] = []
    low, high = value
    for bound_value in (low, high):
        number, err = _coerce_number(name, bound_value)
        if err:
            problems.append(err)
            continue
        message = _bounds_message(name, number)
        if message:
            problems.append(message)
    if not problems and low > high:
        problems.append(f"{name}: low must be <= high, got [{low:g}, {high:g}]{_unit_suffix(name)}")
    return problems
