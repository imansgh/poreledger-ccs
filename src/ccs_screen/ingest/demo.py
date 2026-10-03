"""The public synthetic demonstration dataset.

The real structured sources (``data/``) are not redistributable with this
repository. So that a fresh clone can run the API and the website, the
repository ships a small, deterministic, **entirely fictional** dataset in
``demo/data/ccs-synthetic-demo.json``. This module reads it into the same
:class:`~ccs_screen.ingest.records.NormalizedWellRecord` the normalizer builds,
so every downstream path -- the approved model, the legacy paths, the HTTP API
-- runs unchanged on it.

What makes it different from real data, and stays visible everywhere:

* It is selected only by its manifest file. A data directory is a demo dataset
  if and only if it contains ``ccs-synthetic-demo.json``; a directory holding
  both the manifest and real source files is refused, so synthetic and real
  data are never combined and real data never silently falls back to demo data.
* The manifest must declare ``"dataset_kind": "synthetic_demo"`` and
  ``"synthetic": true``, and every well name must start with ``SYNTH``, so
  every well id is visibly fictional (``SYNTH ALPHA|1``).
* Every field value carries a ``SYNTHETIC`` note and points at the manifest as
  its source; the API adds a ``dataset`` block with ``synthetic: true`` and a
  ``synthetic_demo_dataset`` interpretation warning to every response.

Nothing in this module touches the Model Contract. Datums, temperature
methods and values are *inputs*; a ground-level datum here is a declared
property of a fictional well, which is exactly the condition the contract
already states for an approved result. The same guards apply to it as to any
real well: a demo well with an unknown datum is ``UNAVAILABLE``.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ccs_screen.ingest.identity import canonical_well_id
from ccs_screen.ingest.provenance import (
    Confidence,
    FieldValue,
    Provenance,
    SourceRef,
    TemperatureMethod,
    Unit,
)
from ccs_screen.ingest.records import (
    NormalizedWellRecord,
    StratigraphicInterval,
    TemperatureObservation,
)
from ccs_screen.ingest.units import DepthDatum, to_kelvin

#: The manifest file that marks a directory as the synthetic demo dataset.
DEMO_MANIFEST = "ccs-synthetic-demo.json"
DEMO_DATASET_KIND = "synthetic_demo"
#: Every demo well name must start with this, so its id is visibly fictional.
DEMO_NAME_PREFIX = "SYNTH "
#: Attached to every demo field value.
SYNTHETIC_NOTE = "SYNTHETIC: fictional demonstration value, not a measurement"
#: Method label on every demo field value.
SYNTHETIC_METHOD = "synthetic_demo_dataset"

_WELL_KEYS = {
    "name", "description", "depth_m", "depth_datum", "surface_elevation_m",
    "operator", "year", "outcome", "temperatures", "intervals",
}
_TEMPERATURE_KEYS = {"depth_m", "temperature_c", "method", "depth_datum",
                     "hours_since_circulation"}
_INTERVAL_KEYS = {"top_m", "bottom_m", "lithology", "age"}
_MANIFEST_KEYS = {"dataset_kind", "synthetic", "name", "version", "statement", "wells"}


class DemoDatasetError(ValueError):
    """The demo manifest is malformed or does not declare itself synthetic."""


@dataclass(frozen=True)
class DatasetInfo:
    """What kind of dataset a data directory holds. Reported by the API."""

    kind: str
    synthetic: bool
    name: str
    version: str | None = None
    statement: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "synthetic": self.synthetic, "name": self.name,
                "version": self.version, "statement": self.statement}


#: The real structured sources (GEOTHOPICA workbook + registry CSVs).
STRUCTURED_SOURCES = DatasetInfo(
    kind="structured_sources", synthetic=False,
    name="Structured well sources (GEOTHOPICA workbook and registry CSVs)",
)


def is_demo_dataset(data_dir: str | Path) -> bool:
    """True when ``data_dir`` holds the synthetic demo manifest."""
    return (Path(data_dir) / DEMO_MANIFEST).is_file()


def _number(where: str, value: Any, *, positive: bool = False,
            allow_none: bool = False) -> float | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DemoDatasetError(f"{where}: expected a number, got {value!r}")
    number = float(value)
    if not math.isfinite(number):
        raise DemoDatasetError(f"{where}: must be finite, got {value!r}")
    if positive and number <= 0:
        raise DemoDatasetError(f"{where}: must be > 0, got {value!r}")
    return number


def _keys(where: str, item: Any, allowed: set[str]) -> Mapping[str, Any]:
    if not isinstance(item, Mapping):
        raise DemoDatasetError(f"{where}: expected an object")
    unknown = sorted(set(item) - allowed)
    if unknown:
        raise DemoDatasetError(f"{where}: unknown field(s) {', '.join(unknown)}")
    return item


def _datum(where: str, value: Any) -> DepthDatum:
    try:
        return DepthDatum(value)
    except ValueError:
        raise DemoDatasetError(
            f"{where}: depth_datum must be one of {[d.value for d in DepthDatum]}, got {value!r}"
        ) from None


def _synthetic(value: Any, unit: Unit, ref: SourceRef, **extra: Any) -> FieldValue:
    return FieldValue(
        value=value, unit=unit, provenance=Provenance.EXTRACTED, confidence=Confidence.LOW,
        source=ref, method=SYNTHETIC_METHOD, notes=(SYNTHETIC_NOTE,), **extra,
    )


def _well(index: int, item: Any) -> NormalizedWellRecord:
    where = f"wells[{index}]"
    well = _keys(where, item, _WELL_KEYS)
    name = well.get("name")
    if not isinstance(name, str) or not name.startswith(DEMO_NAME_PREFIX):
        raise DemoDatasetError(
            f"{where}.name: demo well names must start with {DEMO_NAME_PREFIX!r} so "
            f"their ids are visibly fictional, got {name!r}"
        )
    try:
        identity = canonical_well_id(name)
    except ValueError as exc:
        raise DemoDatasetError(f"{where}.name: {exc}") from None

    row = index + 1
    rec = NormalizedWellRecord(identity=identity)
    rec.source_names = (DEMO_MANIFEST,)

    def ref(column: str) -> SourceRef:
        return SourceRef(file=DEMO_MANIFEST, table="wells", row=row, column=column)

    depth = _number(f"{where}.depth_m", well.get("depth_m"), positive=True, allow_none=True)
    if depth is not None:
        rec.depth_m = _synthetic(depth, Unit.METRE, ref("depth_m"))
    rec.depth_datum = _datum(f"{where}.depth_datum", well.get("depth_datum", "unknown"))
    elevation = _number(f"{where}.surface_elevation_m", well.get("surface_elevation_m"),
                        allow_none=True)
    if elevation is not None:
        rec.surface_elevation_m = _synthetic(elevation, Unit.METRE, ref("surface_elevation_m"))
    for key in ("operator", "outcome"):
        if well.get(key) is not None:
            setattr(rec, key, _synthetic(str(well[key]), Unit.NONE, ref(key)))
    if well.get("year") is not None:
        rec.year = _synthetic(_number(f"{where}.year", well["year"]), Unit.NONE, ref("year"))

    temperatures = []
    for j, raw in enumerate(well.get("temperatures") or ()):
        tw = f"{where}.temperatures[{j}]"
        obs = _keys(tw, raw, _TEMPERATURE_KEYS)
        try:
            method = TemperatureMethod(obs.get("method"))
        except ValueError:
            raise DemoDatasetError(f"{tw}.method: unknown method {obs.get('method')!r}") from None
        celsius = _number(f"{tw}.temperature_c", obs.get("temperature_c"))
        temperatures.append(TemperatureObservation(
            depth_m=_number(f"{tw}.depth_m", obs.get("depth_m"), positive=True),
            temperature_k=to_kelvin(celsius, Unit.CELSIUS),
            method=method.value,
            hours_since_circulation=_number(f"{tw}.hours_since_circulation",
                                            obs.get("hours_since_circulation"), allow_none=True),
            source=SourceRef(file=DEMO_MANIFEST, table=f"wells[{index}].temperatures", row=j + 1),
            original_celsius=celsius,
            depth_datum=_datum(f"{tw}.depth_datum", obs.get("depth_datum", "unknown")),
        ))
    rec.temperatures = tuple(temperatures)

    intervals = []
    for j, raw in enumerate(well.get("intervals") or ()):
        iw = f"{where}.intervals[{j}]"
        unit = _keys(iw, raw, _INTERVAL_KEYS)
        top = _number(f"{iw}.top_m", unit.get("top_m"))
        bottom = _number(f"{iw}.bottom_m", unit.get("bottom_m"))
        if not 0 <= top < bottom:
            raise DemoDatasetError(f"{iw}: need 0 <= top_m < bottom_m, got {top}, {bottom}")
        intervals.append(StratigraphicInterval(
            top_m=top, bottom_m=bottom, lithology=unit.get("lithology"), age=unit.get("age"),
            source=SourceRef(file=DEMO_MANIFEST, table=f"wells[{index}].intervals", row=j + 1),
        ))
    rec.intervals = tuple(intervals)
    return rec


def load_demo_dataset(data_dir: str | Path) -> tuple[list[NormalizedWellRecord], DatasetInfo]:
    """Read and validate the demo manifest; raise DemoDatasetError if malformed.

    Records are returned *before* derivation; the caller runs the normalizer's
    own derivation step on them so the demo uses the same rules as real data.
    """
    path = Path(data_dir) / DEMO_MANIFEST
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise DemoDatasetError(f"cannot read {DEMO_MANIFEST}: {type(exc).__name__}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise DemoDatasetError(f"{DEMO_MANIFEST} is not valid JSON: {exc}") from exc

    manifest = _keys(DEMO_MANIFEST, manifest, _MANIFEST_KEYS)
    if manifest.get("dataset_kind") != DEMO_DATASET_KIND or manifest.get("synthetic") is not True:
        raise DemoDatasetError(
            f"{DEMO_MANIFEST} must declare \"dataset_kind\": \"{DEMO_DATASET_KIND}\" and "
            "\"synthetic\": true"
        )
    wells = manifest.get("wells")
    if not isinstance(wells, list) or not wells:
        raise DemoDatasetError(f"{DEMO_MANIFEST}: \"wells\" must be a non-empty list")
    records = [_well(i, item) for i, item in enumerate(wells)]
    ids = [r.canonical_id for r in records]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise DemoDatasetError(f"{DEMO_MANIFEST}: duplicate well id(s) {', '.join(duplicates)}")

    info = DatasetInfo(
        kind=DEMO_DATASET_KIND, synthetic=True,
        name=str(manifest.get("name") or "Synthetic demonstration dataset"),
        version=None if manifest.get("version") is None else str(manifest["version"]),
        statement=None if manifest.get("statement") is None else str(manifest["statement"]),
    )
    return records, info
