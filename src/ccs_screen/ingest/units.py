"""Number parsing, unit conversion and depth-datum handling.

Every function here refuses to guess. The reconnaissance found Italian decimal
commas (``120,00``) next to decimal points (``313.20``) and thousands-dotted
coordinates (``1.384.543``) in the same document family, plus depths measured
from the rotary table rather than sea level. Each of those is a silent
order-of-magnitude or hundreds-of-metres error if handled by assumption, so an
genuinely ambiguous input raises :class:`AmbiguousValueError` instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from ccs_screen.ingest.provenance import Unit

FEET_PER_METRE = 3.280839895013123
METRES_PER_FOOT = 0.3048
KELVIN_OFFSET = 273.15


class AmbiguousValueError(ValueError):
    """The text could mean more than one number and we refuse to choose."""


class UnitError(ValueError):
    """A conversion was requested that the evidence does not support."""


#: Markers meaning "approximately" or "true vertical", seen as ``5500 v.5497~``.
_APPROX = re.compile(r"[~≈]|\bca\.?\b|\bcirca\b", re.IGNORECASE)
_NUMERIC = re.compile(r"^[+-]?[\d.,]+$")


@dataclass(frozen=True)
class ParsedNumber:
    value: float
    original: str
    approximate: bool = False
    note: str = ""


def parse_number(text: object, *, field_name: str = "value") -> ParsedNumber:
    """Parse a European-or-Anglo formatted number without guessing.

    Rules, applied in order:

    1. Both ``.`` and ``,`` present -> the *last* one is the decimal separator.
    2. One separator type, appearing more than once -> thousands separator.
    3. One separator, appearing once:
       - with exactly 3 digits after it, the text is ambiguous
         (``1.384`` is either 1384 or 1.384) -> raise.
       - otherwise it is the decimal separator.

    ``~`` and ``circa`` mark the result approximate rather than being dropped.
    """
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        return ParsedNumber(value=float(text), original=str(text))

    raw = str(text).strip()
    if not raw:
        raise ValueError(f"{field_name}: empty value")

    approximate = bool(_APPROX.search(raw))
    cleaned = _APPROX.sub("", raw).strip()
    cleaned = cleaned.replace(" ", "").replace("\xa0", "")
    if not _NUMERIC.match(cleaned):
        raise ValueError(f"{field_name}: not a plain number: {raw!r}")

    sign = -1.0 if cleaned.startswith("-") else 1.0
    body = cleaned.lstrip("+-")
    dots, commas = body.count("."), body.count(",")

    if dots and commas:
        decimal_sep = "." if body.rfind(".") > body.rfind(",") else ","
        thousands_sep = "," if decimal_sep == "." else "."
        digits = body.replace(thousands_sep, "").replace(decimal_sep, ".")
        return ParsedNumber(sign * float(digits), raw, approximate,
                            f"mixed separators; '{decimal_sep}' read as decimal")

    sep = "." if dots else ("," if commas else None)
    if sep is None:
        return ParsedNumber(sign * float(body), raw, approximate)

    count = dots or commas
    if count > 1:
        return ParsedNumber(sign * float(body.replace(sep, "")), raw, approximate,
                            f"repeated '{sep}' read as thousands separator")

    after = len(body.split(sep)[1])
    if after == 3:
        raise AmbiguousValueError(
            f"{field_name}: {raw!r} is ambiguous -- '{sep}' with 3 trailing digits "
            f"could be a decimal separator ({body.replace(sep, '.')}) or a thousands "
            f"separator ({body.replace(sep, '')}). The source must disambiguate."
        )
    return ParsedNumber(sign * float(body.replace(sep, ".")), raw, approximate)


def to_metres(value: float, unit: Unit | str) -> float:
    """Convert an explicitly-labelled length to metres.

    There is no magnitude heuristic here by design: a 3000 could be metres or
    feet, and guessing wrong is a 900 m error.
    """
    u = Unit(unit) if not isinstance(unit, Unit) else unit
    if u is Unit.METRE:
        return float(value)
    if u is Unit.FOOT:
        return float(value) * METRES_PER_FOOT
    raise UnitError(f"cannot convert {u.value!r} to metres")


def to_kelvin(value: float, unit: Unit | str) -> float:
    u = Unit(unit) if not isinstance(unit, Unit) else unit
    if u is Unit.KELVIN:
        return float(value)
    if u is Unit.CELSIUS:
        return float(value) + KELVIN_OFFSET
    raise UnitError(f"cannot convert {u.value!r} to kelvin")


class DepthDatum(str, Enum):
    """The reference surface a depth is measured from.

    AGIP composite logs state "Tutte le profondita sono riferite al piano
    tavola rotary" -- depths run from the rotary table, which sat 120.00 m above
    sea level at MALOSSA 15 and 238.7 m at CAVAGLIETTO 1. Treating those as
    sub-sea depths overstates burial by exactly that elevation.
    """

    MEAN_SEA_LEVEL = "msl"
    ROTARY_TABLE = "rotary_table"
    GROUND_LEVEL = "ground_level"
    KELLY_BUSHING = "kelly_bushing"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DepthMeasurement:
    """A depth plus the surface it was measured from."""

    value_m: float
    datum: DepthDatum
    datum_elevation_m: float | None = None  # elevation of the datum above MSL

    @property
    def can_convert_to_msl(self) -> bool:
        if self.datum is DepthDatum.MEAN_SEA_LEVEL:
            return True
        return self.datum is not DepthDatum.UNKNOWN and self.datum_elevation_m is not None

    def to_msl(self) -> "DepthMeasurement":
        """Depth below mean sea level.

        Raises when the datum is unknown or its elevation was not supplied --
        an uncorrectable depth stays uncorrected rather than being passed off
        as sub-sea.
        """
        if self.datum is DepthDatum.MEAN_SEA_LEVEL:
            return self
        if self.datum is DepthDatum.UNKNOWN:
            raise UnitError(
                "depth datum is unknown; cannot convert to MSL without knowing "
                "what surface the depth was measured from"
            )
        if self.datum_elevation_m is None:
            raise UnitError(
                f"depth is referenced to {self.datum.value} but that datum's "
                "elevation above MSL was not supplied; cannot correct"
            )
        return DepthMeasurement(
            value_m=self.value_m - self.datum_elevation_m,
            datum=DepthDatum.MEAN_SEA_LEVEL,
            datum_elevation_m=0.0,
        )

    def describe(self) -> str:
        if self.datum is DepthDatum.MEAN_SEA_LEVEL:
            return f"{self.value_m:.1f} m below MSL"
        elev = "" if self.datum_elevation_m is None else f" (datum at {self.datum_elevation_m:.2f} m MSL)"
        return f"{self.value_m:.1f} m below {self.datum.value}{elev}"
