"""User-supplied assessments: parse, validate, normalize, then evaluate.

A user assessment is one well or site described by its own data (schema
``ccs-assessment/1``, JSON or CSV). This module turns it into exactly the inputs
the approved model already takes -- a :class:`NormalizedWellRecord` built in
memory plus :class:`ApprovedUserInputs` -- and evaluates it through
``ccs_screen.api._screen_approved``, the same path every existing well uses.
There is no second calculator: the formulas, priors, temperature rule, depth
reference guard, named water-level scenarios and EOS envelope are the engine's.

Stages, kept separate:

1. **Parse** (``parse_json_text``, ``parse_csv_text``): bytes/text -> a schema
   document (plain dicts), with row numbers for CSV. Nothing is computed.
2. **Validate and normalize** (``validate_document``): every value checked
   (finite numbers, explicit supported units, ranges, ordering, identifiers,
   limits) and converted to SI with tested factors. Errors block evaluation;
   *notices* explain inputs that will make a result UNAVAILABLE.
3. **Evaluate** (``evaluate_document``): build the in-memory record, call the
   shared engine path, wrap the result with provenance and an outcome summary.

Nothing here touches the cached existing-data records, writes files, or logs
submitted values. See docs/assessment-input-schema.md.

Depth convention (implementation-level interpretation, docs/scientific-notes.md):
the approved pressure term ``rho_brine * g * (z_state - z_wl)`` is a hydrostatic
column, which needs true vertical depth. The Model Contract is silent on MD vs
TVD. This layer therefore evaluates only assessments declared ``TVD``; ``MD`` or
``unknown`` returns UNAVAILABLE for both named scenarios without calling the
engine, and observations not in TVD are withheld from it. MD is never converted
or relabelled. This can only withhold a result, never create one.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import math
import re
import threading
from dataclasses import dataclass, field
from importlib import resources
from typing import Any, Iterable, Mapping

from ccs_screen import api
from ccs_screen.approved_model import (
    APPROVED_PRIORS,
    DIAGNOSTIC_MESSAGES,
    ELIGIBLE_TEMPERATURE_METHODS,
    WATER_LEVEL_SCENARIOS,
    Diagnostic,
    ScenarioResult,
    StorageInterval,
    ValidationStatus,
    depth_reference_diagnostic,
    diagnostic,
)
from ccs_screen.ingest.identity import WellIdentity
from ccs_screen.ingest.provenance import (
    Confidence,
    FieldValue,
    Provenance,
    SourceRef,
    TemperatureMethod,
    Unit,
)
from ccs_screen.ingest.records import NormalizedWellRecord, TemperatureObservation
from ccs_screen.ingest.units import DepthDatum

SCHEMA_VERSION = "ccs-assessment/1"
SUPPORTED_SCHEMA_VERSIONS = (SCHEMA_VERSION,)

# -- units: explicit, exact factors ------------------------------------------------

#: Area units -> m2. 1 acre = 4046.8564224 m2 exactly (international acre).
AREA_UNITS: dict[str, float] = {"m2": 1.0, "km2": 1.0e6, "ha": 1.0e4, "acre": 4046.8564224}
#: Length units -> m. 1 ft = 0.3048 m exactly (international foot).
LENGTH_UNITS: dict[str, float] = {"m": 1.0, "ft": 0.3048}
TEMPERATURE_UNITS = ("degC", "K", "degF")


def area_to_m2(value: float, unit: str) -> float:
    return value * AREA_UNITS[unit]


def length_to_m(value: float, unit: str) -> float:
    return value * LENGTH_UNITS[unit]


def temperature_to_k(value: float, unit: str) -> float:
    if unit == "K":
        return value
    if unit == "degC":
        return value + 273.15
    if unit == "degF":
        return (value - 32.0) * 5.0 / 9.0 + 273.15
    raise KeyError(unit)


# -- conventions --------------------------------------------------------------------

DATUMS = tuple(d.value for d in DepthDatum)  # ground_level, rotary_table, ...
DEPTH_CONVENTIONS = ("TVD", "MD", "unknown")
ELEVATION_REFERENCES = ("msl", "unknown")
METHODS = tuple(m.value for m in TemperatureMethod)
ELIGIBLE_METHODS = tuple(m.value for m in ELIGIBLE_TEMPERATURE_METHODS)
#: Declarations are accepted as stated; this tool cannot verify them.
DEPTH_REFERENCE_BASIS = "user_declared"

# -- limits -------------------------------------------------------------------------

MAX_ASSESSMENTS = 50
MAX_OBSERVATIONS = 100
MAX_STRATIGRAPHY_UNITS = 100
MAX_IMPORT_BYTES = 200_000
MAX_CSV_ROWS = 5_000
MAX_TEXT_LENGTH = 1_000
#: Total Monte Carlo realisations per request (assessments x samples).
MAX_TOTAL_SAMPLES = 200_000
MAX_SEED = 2**32 - 1
DEFAULT_SAMPLES = 2_000
DEFAULT_SEED = 42
#: Physical-possibility bounds shared with the screening config (config.BOUNDS):
#: they reject impossible values, not unusual ones.
MAX_AREA_M2 = 1.0e12
MAX_DEPTH_M = 15_000.0
MAX_TEMPERATURE_K = 1_000.0
ELEVATION_RANGE_M = (-1_000.0, 9_000.0)

ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._:/|()#+-]{0,63}$")

LIMITS = {
    "max_assessments_per_request": MAX_ASSESSMENTS,
    "max_temperature_observations_per_assessment": MAX_OBSERVATIONS,
    "max_import_bytes": MAX_IMPORT_BYTES,
    "max_csv_rows": MAX_CSV_ROWS,
    "max_total_samples_per_request": MAX_TOTAL_SAMPLES,
    "samples": {"min": api.MIN_SAMPLES, "max": api.MAX_SAMPLES, "default": DEFAULT_SAMPLES},
    "seed": {"min": 0, "max": MAX_SEED, "default": DEFAULT_SEED},
}


class AssessmentError(api.ApiError):
    """The submitted document cannot be evaluated; ``problems`` says why."""

    def __init__(self, problems: list[dict[str, Any]]) -> None:
        self.problems = problems
        errors = [p for p in problems if p["severity"] == "error"]
        first = errors[0] if errors else (problems[0] if problems else {"message": "invalid"})
        where = f"{first.get('path')}: " if first.get("path") else ""
        super().__init__(f"{len(errors)} input error(s); first: {where}{first['message']}")


def _problem(path: str, code: str, message: str, severity: str = "error",
             row: int | None = None) -> dict[str, Any]:
    return {"path": path, "row": row, "code": code, "message": message, "severity": severity}


# -- normalized assessment ------------------------------------------------------------


@dataclass(frozen=True)
class Observation:
    index: int
    temperature_k: float
    depth_m: float
    depth_datum: str
    depth_convention: str
    method: str
    original: dict[str, Any]
    source: str | None = None

    @property
    def eligible_method(self) -> bool:
        return self.method in ELIGIBLE_METHODS

    @property
    def passed_to_engine(self) -> bool:
        return self.depth_convention == "TVD"


@dataclass(frozen=True)
class NormalizedAssessment:
    """One assessment in SI units, as declared. Nothing here is inferred."""

    index: int
    id: str
    name: str | None
    synthetic: bool
    example: dict[str, Any] | None
    area_m2: float
    area_original: dict[str, Any]
    z_top_m: float
    z_base_m: float
    interval_original: dict[str, Any]
    depth_datum: str
    depth_convention: str
    observations: tuple[Observation, ...]
    surface_elevation_m: float | None = None
    surface_elevation_reference: str | None = None
    surface_elevation_original: dict[str, Any] | None = None
    total_depth_m: float | None = None
    total_depth_original: dict[str, Any] | None = None
    stratigraphy: tuple[dict[str, Any], ...] = ()
    notes: str | None = None
    sources: dict[str, str] = field(default_factory=dict)

    def inputs_dict(self) -> dict[str, Any]:
        """Normalized inputs with their original values and units."""
        elevation = None
        if self.surface_elevation_original is not None:
            elevation = {
                "value_m": self.surface_elevation_m,
                "reference": self.surface_elevation_reference,
                "original": self.surface_elevation_original,
                "used_by_model": self.surface_elevation_reference == "msl",
                "role": "z_wl of SEA_LEVEL_SENSITIVITY (ground elevation above mean sea level)",
                "source": self.sources.get("surface_elevation"),
            }
        total_depth = None
        if self.total_depth_original is not None:
            total_depth = {"value_m": self.total_depth_m, "original": self.total_depth_original,
                           "role": "temperature eligibility (observations deeper than total "
                                   "depth are excluded)",
                           "source": self.sources.get("total_depth")}
        return {
            "storage_area": {"value_m2": self.area_m2, "original": self.area_original,
                             "source": self.sources.get("storage_area")},
            "storage_interval": {"z_top_m": self.z_top_m, "z_base_m": self.z_base_m,
                                 "original": self.interval_original,
                                 "source": self.sources.get("storage_interval")},
            "depth_reference": {
                "datum": self.depth_datum, "convention": self.depth_convention,
                "basis": DEPTH_REFERENCE_BASIS, "independently_verified": False,
                "applies_to": "storage interval and total depth",
                "source": self.sources.get("depth_reference"),
            },
            "surface_elevation": elevation,
            "total_depth": total_depth,
            "temperature_observations": [
                {"index": o.index, "temperature_k": o.temperature_k, "depth_m": o.depth_m,
                 "depth_datum": o.depth_datum, "depth_convention": o.depth_convention,
                 "method": o.method, "eligible_method": o.eligible_method,
                 "passed_to_engine": o.passed_to_engine, "original": o.original,
                 "source": o.source}
                for o in self.observations
            ],
            "stratigraphy": [dict(s) for s in self.stratigraphy],
            "stratigraphy_role": "context only; not used by the approved model",
            "notes": self.notes,
        }


# -- parsing ----------------------------------------------------------------------------

_DOC_KEYS = {"schema_version", "assessments"}
#: Marks a partial import preview (see ``parse_upload``); never evaluated.
BLOCKED_IMPORT_KEY = "blocked_import"
_ASSESSMENT_KEYS = {
    "id", "name", "synthetic", "example", "storage_area", "storage_interval",
    "depth_reference", "surface_elevation", "total_depth", "temperature_observations",
    "stratigraphy", "notes",
}
_REQUIRED_ASSESSMENT_KEYS = ("id", "storage_area", "storage_interval", "depth_reference")


def _reject_constant(token: str) -> Any:
    raise ValueError(f"{token} is not a finite number")


def parse_json_text(text: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Parse a JSON assessment document. Data only: nothing in it is executed."""
    if len(text.encode("utf-8")) > MAX_IMPORT_BYTES:
        return None, [_problem("", "FILE_TOO_LARGE",
                               f"file is larger than {MAX_IMPORT_BYTES} bytes")]
    try:
        document = json.loads(text, parse_constant=_reject_constant)
    except ValueError as exc:
        return None, [_problem("", "INVALID_JSON", f"not valid JSON: {exc}")]
    if not isinstance(document, dict):
        return None, [_problem("", "INVALID_DOCUMENT",
                               "the document must be a JSON object with schema_version "
                               "and assessments")]
    return document, []


#: CSV columns -> where they go. Assessment-level columns repeat on every row of
#: an assessment and must agree; obs_* columns describe one observation per row.
CSV_REQUIRED_COLUMNS = (
    "schema_version", "assessment_id", "area_value", "area_unit", "interval_top",
    "interval_base", "depth_unit", "depth_datum", "depth_convention",
)
CSV_ASSESSMENT_COLUMNS = CSV_REQUIRED_COLUMNS + (
    "assessment_name", "synthetic", "total_depth", "surface_elevation",
    "surface_elevation_unit", "surface_elevation_reference", "notes", "area_source",
    "interval_source", "depth_reference_source", "total_depth_source", "surface_elevation_source",
)
CSV_OBSERVATION_COLUMNS = (
    "obs_temperature", "obs_temperature_unit", "obs_depth", "obs_depth_unit",
    "obs_depth_datum", "obs_depth_convention", "obs_method", "obs_source",
)
_CSV_OBS_REQUIRED = CSV_OBSERVATION_COLUMNS[:-1]
CSV_COLUMNS = CSV_ASSESSMENT_COLUMNS + CSV_OBSERVATION_COLUMNS
_CSV_NUMBER_COLUMNS = {"area_value", "interval_top", "interval_base", "total_depth",
                       "surface_elevation", "obs_temperature", "obs_depth"}


def _csv_number(text: str) -> float | str:
    """A CSV cell as a float, or the original text so validation can name it."""
    cleaned = text.strip()
    try:
        number = float(cleaned)
    except ValueError:
        return cleaned
    if not math.isfinite(number):
        return cleaned  # "nan", "inf": rejected by validation, never coerced
    return number


def parse_csv_text(text: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]],
                                       dict[str, Any]]:
    """Parse the long CSV format into a schema document.

    One row per temperature observation; rows sharing ``assessment_id`` form one
    assessment, in order of first appearance. Assessment-level columns must be
    identical on every row of an assessment. A row whose obs_* cells are all
    empty contributes no observation. Lines starting with ``#`` before the
    header are comments. Returns the document, problems (with 1-based file row
    numbers) and a row index mapping assessments and observations to rows.
    """
    row_index: dict[str, Any] = {"assessments": []}
    if len(text.encode("utf-8")) > MAX_IMPORT_BYTES:
        return None, [_problem("", "FILE_TOO_LARGE",
                               f"file is larger than {MAX_IMPORT_BYTES} bytes")], row_index
    lines = text.lstrip("﻿").splitlines()
    first = 0
    while first < len(lines) and (not lines[first].strip() or lines[first].lstrip().startswith("#")):
        first += 1
    if first >= len(lines):
        return None, [_problem("", "EMPTY_FILE", "no header row found")], row_index

    reader = csv.reader(lines[first:])
    try:
        header = [h.strip() for h in next(reader)]
    except csv.Error as exc:
        return None, [_problem("", "INVALID_CSV", f"cannot read the header: {exc}",
                               row=first + 1)], row_index
    problems: list[dict[str, Any]] = []
    unknown = [h for h in header if h not in CSV_COLUMNS]
    if unknown:
        problems.append(_problem("", "UNKNOWN_COLUMN",
                                 f"unknown column(s): {', '.join(unknown)}. Allowed: "
                                 f"{', '.join(CSV_COLUMNS)}", row=first + 1))
    missing = [c for c in CSV_REQUIRED_COLUMNS if c not in header]
    if missing:
        problems.append(_problem("", "MISSING_COLUMN",
                                 f"missing required column(s): {', '.join(missing)}",
                                 row=first + 1))
    duplicates = sorted({h for h in header if header.count(h) > 1})
    if duplicates:
        problems.append(_problem("", "DUPLICATE_COLUMN",
                                 f"duplicate column(s): {', '.join(duplicates)}", row=first + 1))
    if problems:
        return None, problems, row_index

    groups: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    n_rows = 0
    try:
        for offset, cells in enumerate(reader, start=first + 2):
            if not any(c.strip() for c in cells):
                continue
            n_rows += 1
            if n_rows > MAX_CSV_ROWS:
                return None, [_problem("", "TOO_MANY_ROWS",
                                       f"more than {MAX_CSV_ROWS} data rows")], row_index
            if len(cells) != len(header):
                problems.append(_problem("", "ROW_LENGTH",
                                         f"row has {len(cells)} cells, header has {len(header)}",
                                         row=offset))
                continue
            row = {h: c.strip() for h, c in zip(header, cells)}
            key = row["assessment_id"]
            if not key:
                problems.append(_problem("assessment_id", "MISSING_VALUE",
                                         "assessment_id is empty", row=offset))
                continue
            assessment_cells = {c: row.get(c, "") for c in CSV_ASSESSMENT_COLUMNS if c in header}
            group = groups.get(key)
            if group is None:
                group = groups[key] = {"cells": assessment_cells, "rows": [offset],
                                       "observations": []}
                order.append(key)
            else:
                for column, value in assessment_cells.items():
                    if value != group["cells"][column]:
                        problems.append(_problem(
                            column, "CONFLICTING_VALUE",
                            f"assessment {key!r}: {column} is {value!r} here but "
                            f"{group['cells'][column]!r} on row {group['rows'][0]}; "
                            "assessment-level columns must be identical on every row",
                            row=offset))
                group["rows"].append(offset)
            obs_cells = {c: row.get(c, "") for c in CSV_OBSERVATION_COLUMNS if c in header}
            # A unit on its own (as in the template) is not an observation.
            if any(v for c, v in obs_cells.items() if not c.endswith("_unit")):
                absent = [c for c in _CSV_OBS_REQUIRED if not obs_cells.get(c)]
                if absent:
                    problems.append(_problem(
                        "temperature_observations", "INCOMPLETE_OBSERVATION",
                        f"assessment {key!r}: observation is missing {', '.join(absent)}",
                        row=offset))
                    continue
                group["observations"].append((offset, obs_cells))
    except csv.Error as exc:
        return None, problems + [_problem("", "INVALID_CSV", f"cannot read the file: {exc}")], \
            row_index

    assessments = []
    versions = set()
    for key in order:
        cells = groups[key]["cells"]
        versions.add(cells["schema_version"])

        def num(column: str) -> Any:
            value = cells.get(column, "")
            return None if value == "" else _csv_number(value)

        depth_unit = cells["depth_unit"]
        assessment: dict[str, Any] = {
            "id": key,
            "storage_area": {"value": num("area_value"), "unit": cells["area_unit"]},
            "storage_interval": {"top": num("interval_top"), "base": num("interval_base"),
                                 "unit": depth_unit},
            "depth_reference": {"datum": cells["depth_datum"],
                                "convention": cells["depth_convention"]},
            "temperature_observations": [],
        }
        if cells.get("assessment_name"):
            assessment["name"] = cells["assessment_name"]
        synthetic = cells.get("synthetic", "").lower()
        if synthetic:
            assessment["synthetic"] = (True if synthetic == "true" else
                                       False if synthetic == "false" else synthetic)
        if cells.get("total_depth"):
            assessment["total_depth"] = {"value": num("total_depth"), "unit": depth_unit}
        if cells.get("surface_elevation") or cells.get("surface_elevation_unit"):
            assessment["surface_elevation"] = {
                "value": num("surface_elevation"),
                "unit": cells.get("surface_elevation_unit", ""),
                "reference": cells.get("surface_elevation_reference", ""),
            }
        for column, target in (("area_source", "storage_area"),
                               ("interval_source", "storage_interval"),
                               ("depth_reference_source", "depth_reference"),
                               ("total_depth_source", "total_depth"),
                               ("surface_elevation_source", "surface_elevation")):
            if cells.get(column) and target in assessment:
                assessment[target]["source"] = cells[column]
        if cells.get("notes"):
            assessment["notes"] = cells["notes"]
        obs_rows = []
        for offset, obs in groups[key]["observations"]:
            entry = {
                "value": _csv_number(obs["obs_temperature"]), "unit": obs["obs_temperature_unit"],
                "depth": _csv_number(obs["obs_depth"]), "depth_unit": obs["obs_depth_unit"],
                "depth_datum": obs["obs_depth_datum"],
                "depth_convention": obs["obs_depth_convention"], "method": obs["obs_method"],
            }
            if obs.get("obs_source"):
                entry["source"] = obs["obs_source"]
            assessment["temperature_observations"].append(entry)
            obs_rows.append(offset)
        assessments.append(assessment)
        row_index["assessments"].append({"rows": groups[key]["rows"], "observations": obs_rows})

    if len(versions) > 1:
        problems.append(_problem("schema_version", "CONFLICTING_VALUE",
                                 f"rows declare different schema versions: {sorted(versions)}"))
    version = versions.pop() if len(versions) == 1 else ""
    if version == "1":  # the short form used in CSV files
        version = SCHEMA_VERSION
    document = {"schema_version": version, "assessments": assessments}
    return document, problems, row_index


def parse_upload(fmt: str, content: str) -> dict[str, Any]:
    """The ``/assessments/parse`` response for an uploaded JSON or CSV file.

    ``import_blocked`` is true when the parser itself reported an error:
    conflicting assessment-level cells, a skipped incomplete observation, a
    wrong row length, conflicting schema versions. What was parsed is then
    partial (it keeps the first row's value, drops the bad rows) and cannot
    hold what the file said: ``document`` is ``None`` and the partial data is
    returned as ``preview_document``, carrying a ``blocked_import`` marker
    with the parser problems. ``validate_document`` rejects any document with
    that marker (IMPORT_BLOCKED), so the preview is never evaluated, edited
    or not; the file has to be corrected and imported again. Validation
    problems of a complete document never block: they are editable.
    """
    if fmt == "csv":
        document, problems, row_index = parse_csv_text(content)
    else:
        document, problems = parse_json_text(content)
        row_index = {}
    import_blocked = any(p["severity"] == "error" for p in problems)
    preview = None
    if import_blocked and document is not None:
        # Partial: never returned as an evaluatable document. The marker makes
        # validate_document reject the preview however it is resubmitted.
        preview = {**document, BLOCKED_IMPORT_KEY: {
            "format": fmt,
            "reason": "the parser could not represent the file faithfully; correct the "
                      "file and import it again",
            "problems": problems,
        }}
        document = None
    if document is not None and not problems:
        _, found = validate_document(document)
        problems = annotate_rows(found, row_index)
    valid = document is not None and not any(p["severity"] == "error" for p in problems)
    return {"format": fmt, "document": document, "preview_document": preview,
            "problems": problems, "valid": valid, "import_blocked": import_blocked}


def annotate_rows(problems: list[dict[str, Any]], row_index: dict[str, Any]) -> list[dict[str, Any]]:
    """Attach CSV row numbers to validation problems found on the parsed document."""
    pattern = re.compile(r"^assessments\[(\d+)\](?:\.temperature_observations\[(\d+)\])?")
    out = []
    for problem in problems:
        match = pattern.match(problem.get("path") or "")
        if match and problem.get("row") is None:
            i = int(match.group(1))
            entries = row_index.get("assessments", [])
            if i < len(entries):
                if match.group(2) is not None and int(match.group(2)) < len(entries[i]["observations"]):
                    problem = {**problem, "row": entries[i]["observations"][int(match.group(2))]}
                else:
                    problem = {**problem, "row": entries[i]["rows"][0]}
        out.append(problem)
    return out


# -- validation and normalization -------------------------------------------------------


class _Checker:
    """Collects every problem rather than stopping at the first."""

    def __init__(self) -> None:
        self.problems: list[dict[str, Any]] = []

    def error(self, path: str, code: str, message: str) -> None:
        self.problems.append(_problem(path, code, message))

    def notice(self, path: str, code: str, message: str) -> None:
        self.problems.append(_problem(path, code, message, severity="notice"))

    def keys(self, path: str, value: Any, allowed: set[str], required: Iterable[str] = ()) -> bool:
        if not isinstance(value, Mapping):
            self.error(path, "EXPECTED_OBJECT", f"expected an object, got {type(value).__name__}")
            return False
        unknown = sorted(set(value) - allowed)
        if unknown:
            self.error(path, "UNKNOWN_FIELD",
                       f"unknown field(s): {', '.join(unknown)}. Allowed: {', '.join(sorted(allowed))}")
        for name in required:
            if value.get(name) is None or value.get(name) == "":
                self.error(f"{path}.{name}" if path else name, "MISSING_VALUE",
                           f"{name} is required")
        return True

    def number(self, path: str, value: Any) -> float | None:
        if value is None or value == "":
            self.error(path, "MISSING_VALUE", "a number is required")
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            hint = " (use '.' as the decimal separator)" if isinstance(value, str) and "," in value else ""
            self.error(path, "NOT_A_NUMBER", f"expected a number, got {value!r}{hint}")
            return None
        try:
            number = float(value)
        except OverflowError:  # an int beyond the float range, e.g. 10**400
            number = math.inf
        if not math.isfinite(number):
            self.error(path, "NOT_FINITE", f"must be a finite number, got {value!r}")
            return None
        return number

    def choice(self, path: str, value: Any, allowed: Iterable[str], what: str) -> str | None:
        allowed = tuple(allowed)
        if value is None or value == "":
            self.error(path, "MISSING_VALUE", f"{what} is required; one of: {', '.join(allowed)}")
            return None
        if value not in allowed:
            self.error(path, "UNSUPPORTED_VALUE",
                       f"unsupported {what} {value!r}; supported: {', '.join(allowed)}")
            return None
        return value

    def text(self, path: str, value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            self.error(path, "NOT_TEXT", f"expected text, got {type(value).__name__}")
            return None
        if len(value) > MAX_TEXT_LENGTH:
            self.error(path, "TEXT_TOO_LONG", f"longer than {MAX_TEXT_LENGTH} characters")
            return None
        return value.strip() or None


def _depth(check: _Checker, path: str, value: Any, unit: str | None,
           allow_zero: bool = True) -> float | None:
    number = check.number(path, value)
    if number is None or unit is None:
        return None
    metres = length_to_m(number, unit)
    if metres < 0 or (metres == 0 and not allow_zero):
        check.error(path, "OUT_OF_RANGE",
                    f"must be {'>= 0' if allow_zero else '> 0'} (depth below the reference), got {number:g} {unit}")
        return None
    if metres > MAX_DEPTH_M:
        check.error(path, "OUT_OF_RANGE", f"deeper than {MAX_DEPTH_M:g} m, got {number:g} {unit}")
        return None
    return metres


def _validate_one(check: _Checker, raw: Any, index: int) -> NormalizedAssessment | None:
    p = f"assessments[{index}]"
    if not check.keys(p, raw, _ASSESSMENT_KEYS, _REQUIRED_ASSESSMENT_KEYS):
        return None
    before = sum(1 for x in check.problems if x["severity"] == "error")
    sources: dict[str, str] = {}

    ident = raw.get("id")
    if ident is not None and ident != "":
        if not isinstance(ident, str) or not ID_PATTERN.match(ident):
            check.error(f"{p}.id", "INVALID_ID",
                        "id must be 1-64 characters: letters, digits, spaces and . _ : / | ( ) # + -, "
                        "starting with a letter or digit")
    name = check.text(f"{p}.name", raw.get("name"))
    synthetic = raw.get("synthetic", False)
    if not isinstance(synthetic, bool):
        check.error(f"{p}.synthetic", "NOT_BOOLEAN", f"synthetic must be true or false, got {synthetic!r}")
        synthetic = False
    example = raw.get("example")
    if example is not None:
        if check.keys(f"{p}.example", example, {"key", "demonstrates"}, ("key",)):
            if not synthetic:
                check.error(f"{p}.example", "EXAMPLE_NOT_SYNTHETIC",
                            "an example must be marked synthetic: true")
            for key in ("key", "demonstrates"):
                check.text(f"{p}.example.{key}", example.get(key))
        example = dict(example) if isinstance(example, Mapping) else None

    area_m2 = None
    area_original: dict[str, Any] = {}
    area = raw.get("storage_area")
    if area is not None and check.keys(f"{p}.storage_area", area, {"value", "unit", "source"},
                                       ("value", "unit")):
        unit = check.choice(f"{p}.storage_area.unit", area.get("unit"), AREA_UNITS, "area unit")
        value = check.number(f"{p}.storage_area.value", area.get("value"))
        if value is not None and unit is not None:
            area_m2 = area_to_m2(value, unit)
            area_original = {"value": value, "unit": unit}
            if not 0 < area_m2 < MAX_AREA_M2:
                check.error(f"{p}.storage_area.value", "OUT_OF_RANGE",
                            f"area must be > 0 and < {MAX_AREA_M2:g} m2, got {value:g} {unit}")
                area_m2 = None
        if (source := check.text(f"{p}.storage_area.source", area.get("source"))):
            sources["storage_area"] = source

    z_top = z_base = None
    interval_original: dict[str, Any] = {}
    interval = raw.get("storage_interval")
    if interval is not None and check.keys(f"{p}.storage_interval", interval,
                                           {"top", "base", "unit", "source"},
                                           ("top", "base", "unit")):
        unit = check.choice(f"{p}.storage_interval.unit", interval.get("unit"), LENGTH_UNITS,
                            "depth unit")
        z_top = _depth(check, f"{p}.storage_interval.top", interval.get("top"), unit)
        z_base = _depth(check, f"{p}.storage_interval.base", interval.get("base"), unit)
        if z_top is not None and z_base is not None and not z_top < z_base:
            check.error(f"{p}.storage_interval", "INTERVAL_ORDER",
                        f"top must be shallower than base (top < base), got top = "
                        f"{interval.get('top')} {unit}, base = {interval.get('base')} {unit}")
            z_top = z_base = None
        if unit is not None:
            interval_original = {"top": interval.get("top"), "base": interval.get("base"),
                                 "unit": unit}
        if (source := check.text(f"{p}.storage_interval.source", interval.get("source"))):
            sources["storage_interval"] = source
        interval_unit = unit
    else:
        interval_unit = None

    datum = convention = None
    reference = raw.get("depth_reference")
    if reference is not None and check.keys(f"{p}.depth_reference", reference,
                                            {"datum", "convention", "source"},
                                            ("datum", "convention")):
        datum = check.choice(f"{p}.depth_reference.datum", reference.get("datum"), DATUMS,
                             "depth datum")
        convention = check.choice(f"{p}.depth_reference.convention", reference.get("convention"),
                                  DEPTH_CONVENTIONS, "depth convention")
        if (source := check.text(f"{p}.depth_reference.source", reference.get("source"))):
            sources["depth_reference"] = source

    elevation_m = elevation_ref = None
    elevation_original = None
    elevation = raw.get("surface_elevation")
    if elevation is not None and check.keys(f"{p}.surface_elevation", elevation,
                                            {"value", "unit", "reference", "source"},
                                            ("value", "unit", "reference")):
        unit = check.choice(f"{p}.surface_elevation.unit", elevation.get("unit"), LENGTH_UNITS,
                            "elevation unit")
        value = check.number(f"{p}.surface_elevation.value", elevation.get("value"))
        elevation_ref = check.choice(f"{p}.surface_elevation.reference",
                                     elevation.get("reference"), ELEVATION_REFERENCES,
                                     "elevation reference")
        if value is not None and unit is not None:
            elevation_m = length_to_m(value, unit)
            low, high = ELEVATION_RANGE_M
            if not low <= elevation_m <= high:
                check.error(f"{p}.surface_elevation.value", "OUT_OF_RANGE",
                            f"must be between {low:g} m and {high:g} m, got {value:g} {unit}")
                elevation_m = None
            elevation_original = {"value": value, "unit": unit, "reference": elevation_ref}
        if (source := check.text(f"{p}.surface_elevation.source", elevation.get("source"))):
            sources["surface_elevation"] = source

    total_depth_m = None
    total_original = None
    total = raw.get("total_depth")
    if total is not None and check.keys(f"{p}.total_depth", total, {"value", "unit", "source"},
                                        ("value", "unit")):
        unit = check.choice(f"{p}.total_depth.unit", total.get("unit"), LENGTH_UNITS, "depth unit")
        total_depth_m = _depth(check, f"{p}.total_depth.value", total.get("value"), unit,
                               allow_zero=False)
        if total_depth_m is not None:
            total_original = {"value": total.get("value"), "unit": unit}
        if (source := check.text(f"{p}.total_depth.source", total.get("source"))):
            sources["total_depth"] = source

    observations: list[Observation] = []
    raw_obs = raw.get("temperature_observations", [])
    if raw_obs is None:
        raw_obs = []
    if not isinstance(raw_obs, list):
        check.error(f"{p}.temperature_observations", "EXPECTED_LIST", "expected a list")
        raw_obs = []
    if len(raw_obs) > MAX_OBSERVATIONS:
        check.error(f"{p}.temperature_observations", "TOO_MANY_OBSERVATIONS",
                    f"at most {MAX_OBSERVATIONS} observations per assessment, got {len(raw_obs)}")
        raw_obs = []
    for j, obs in enumerate(raw_obs):
        q = f"{p}.temperature_observations[{j}]"
        if not check.keys(q, obs, {"value", "unit", "depth", "depth_unit", "depth_datum",
                                    "depth_convention", "method", "source"},
                          ("value", "unit", "depth", "depth_unit", "depth_datum",
                           "depth_convention", "method")):
            continue
        t_unit = check.choice(f"{q}.unit", obs.get("unit"), TEMPERATURE_UNITS, "temperature unit")
        value = check.number(f"{q}.value", obs.get("value"))
        temperature_k = None
        if value is not None and t_unit is not None:
            temperature_k = temperature_to_k(value, t_unit)
            if not 0 < temperature_k < MAX_TEMPERATURE_K:
                check.error(f"{q}.value", "PHYSICALLY_INVALID",
                            f"{value:g} {t_unit} is {temperature_k:.2f} K; a temperature must be "
                            f"> 0 K and < {MAX_TEMPERATURE_K:g} K")
                temperature_k = None
        d_unit = check.choice(f"{q}.depth_unit", obs.get("depth_unit"), LENGTH_UNITS, "depth unit")
        depth_m = _depth(check, f"{q}.depth", obs.get("depth"), d_unit)
        obs_datum = check.choice(f"{q}.depth_datum", obs.get("depth_datum"), DATUMS, "depth datum")
        obs_conv = check.choice(f"{q}.depth_convention", obs.get("depth_convention"),
                                DEPTH_CONVENTIONS, "depth convention")
        method = check.choice(f"{q}.method", obs.get("method"), METHODS, "temperature method")
        source = check.text(f"{q}.source", obs.get("source"))
        if None not in (temperature_k, depth_m, obs_datum, obs_conv, method):
            observations.append(Observation(
                index=j, temperature_k=temperature_k, depth_m=depth_m,  # type: ignore[arg-type]
                depth_datum=obs_datum, depth_convention=obs_conv,  # type: ignore[arg-type]
                method=method,  # type: ignore[arg-type]
                original={"value": value, "unit": t_unit, "depth": obs.get("depth"),
                          "depth_unit": d_unit},
                source=source,
            ))

    stratigraphy: list[dict[str, Any]] = []
    raw_strat = raw.get("stratigraphy") or []
    if not isinstance(raw_strat, list) or len(raw_strat) > MAX_STRATIGRAPHY_UNITS:
        check.error(f"{p}.stratigraphy", "EXPECTED_LIST",
                    f"expected a list of at most {MAX_STRATIGRAPHY_UNITS} units")
        raw_strat = []
    for j, unit_entry in enumerate(raw_strat):
        q = f"{p}.stratigraphy[{j}]"
        if not check.keys(q, unit_entry, {"top", "base", "unit", "description"},
                          ("top", "base", "unit")):
            continue
        s_unit = check.choice(f"{q}.unit", unit_entry.get("unit"), LENGTH_UNITS, "depth unit")
        top = _depth(check, f"{q}.top", unit_entry.get("top"), s_unit)
        base = _depth(check, f"{q}.base", unit_entry.get("base"), s_unit)
        if top is not None and base is not None:
            if not top < base:
                check.error(q, "INTERVAL_ORDER", "top must be shallower than base")
            else:
                stratigraphy.append({"top_m": top, "base_m": base,
                                     "description": check.text(f"{q}.description",
                                                               unit_entry.get("description"))})

    notes = check.text(f"{p}.notes", raw.get("notes"))
    errors_now = sum(1 for x in check.problems if x["severity"] == "error")
    if errors_now > before or None in (area_m2, z_top, z_base, datum, convention) \
            or not isinstance(ident, str):
        return None

    assessment = NormalizedAssessment(
        index=index, id=ident, name=name, synthetic=synthetic, example=example,
        area_m2=area_m2, area_original=area_original,  # type: ignore[arg-type]
        z_top_m=z_top, z_base_m=z_base,  # type: ignore[arg-type]
        interval_original=interval_original, depth_datum=datum,  # type: ignore[arg-type]
        depth_convention=convention, observations=tuple(observations),  # type: ignore[arg-type]
        surface_elevation_m=elevation_m, surface_elevation_reference=elevation_ref,
        surface_elevation_original=elevation_original, total_depth_m=total_depth_m,
        total_depth_original=total_original, stratigraphy=tuple(stratigraphy), notes=notes,
        sources=sources,
    )
    _notices(check, p, assessment, interval_unit)
    return assessment


def _notices(check: _Checker, p: str, a: NormalizedAssessment, unit: str | None) -> None:
    """Explain, before evaluation, which inputs will make a result UNAVAILABLE."""
    if a.depth_convention != "TVD":
        check.notice(f"{p}.depth_reference.convention", "DEPTH_CONVENTION_NOT_TVD",
                     "the approved model needs true vertical depth (TVD); with "
                     f"'{a.depth_convention}' it is not evaluated and both scenarios are "
                     "UNAVAILABLE. Measured depth is never converted or relabelled.")
    if a.depth_datum != "ground_level":
        check.notice(f"{p}.depth_reference.datum", "DEPTH_DATUM_NOT_GROUND_LEVEL",
                     f"datum '{a.depth_datum}': only depths measured from ground level can be "
                     "used, and no datum conversion is applied, so both scenarios will be "
                     "UNAVAILABLE.")
    if a.total_depth_m is None:
        check.notice(f"{p}.total_depth", "TOTAL_DEPTH_MISSING",
                     "no total depth: the approved temperature rule excludes every observation "
                     "when the total depth is not recorded, so both scenarios will be UNAVAILABLE.")
    elif a.total_depth_m < a.z_base_m:
        check.notice(f"{p}.storage_interval", "INTERVAL_BELOW_TOTAL_DEPTH",
                     "the storage interval extends below the total depth; observations below the "
                     "total depth are not eligible.")
    if a.surface_elevation_m is None or a.surface_elevation_reference != "msl":
        check.notice(f"{p}.surface_elevation", "SURFACE_ELEVATION_NOT_USABLE",
                     "no ground elevation above mean sea level: SEA_LEVEL_SENSITIVITY will be "
                     "UNAVAILABLE (GROUND_REFERENCE is unaffected).")
    if not a.observations:
        check.notice(f"{p}.temperature_observations", "NO_TEMPERATURE_OBSERVATIONS",
                     "no temperature observations: temperature is never assumed, so both "
                     "scenarios will be UNAVAILABLE.")
    elif not any(o.eligible_method and o.passed_to_engine for o in a.observations):
        check.notice(f"{p}.temperature_observations", "NO_ELIGIBLE_METHOD",
                     "no observation uses an eligible corrected method in TVD "
                     f"({', '.join(ELIGIBLE_METHODS)}): both scenarios will be UNAVAILABLE.")
    for o in a.observations:
        if not o.passed_to_engine:
            check.notice(f"{p}.temperature_observations[{o.index}].depth_convention",
                         "OBSERVATION_NOT_TVD",
                         f"depth convention '{o.depth_convention}': this observation is withheld "
                         "from the model (only TVD depths are comparable with the interval).")


def validate_document(document: Any) -> tuple[list[NormalizedAssessment], list[dict[str, Any]]]:
    """Validate a schema document; return normalized assessments and every problem.

    Assessments are returned only when the whole document has no errors.
    Notices never block.
    """
    check = _Checker()
    if isinstance(document, Mapping) and BLOCKED_IMPORT_KEY in document:
        check.error(BLOCKED_IMPORT_KEY, "IMPORT_BLOCKED",
                    "this is a blocked import preview, not an assessment document: the file "
                    "had row problems the parser could not represent (see "
                    f"{BLOCKED_IMPORT_KEY}.problems). Correct the file and import it again")
        return [], check.problems
    if not check.keys("", document, _DOC_KEYS, ("schema_version", "assessments")):
        return [], check.problems
    version = document.get("schema_version")
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        check.error("schema_version", "UNSUPPORTED_SCHEMA_VERSION",
                    f"unsupported schema_version {version!r}; supported: "
                    f"{', '.join(SUPPORTED_SCHEMA_VERSIONS)}")
        return [], check.problems
    assessments = document.get("assessments")
    if not isinstance(assessments, list) or not assessments:
        check.error("assessments", "EXPECTED_LIST", "assessments must be a non-empty list")
        return [], check.problems
    if len(assessments) > MAX_ASSESSMENTS:
        check.error("assessments", "TOO_MANY_ASSESSMENTS",
                    f"at most {MAX_ASSESSMENTS} assessments per request, got {len(assessments)}")
        return [], check.problems

    normalized = [_validate_one(check, raw, i) for i, raw in enumerate(assessments)]
    ids = [raw.get("id") for raw in assessments if isinstance(raw, Mapping)]
    for i, raw in enumerate(assessments):
        if isinstance(raw, Mapping) and raw.get("id") and ids.count(raw.get("id")) > 1:
            check.error(f"assessments[{i}].id", "DUPLICATE_ID",
                        f"id {raw.get('id')!r} is used by more than one assessment")
    flags = {raw.get("synthetic", False) is True for raw in assessments if isinstance(raw, Mapping)}
    if len(flags) > 1:
        check.error("assessments", "MIXED_SYNTHETIC",
                    "a document must not mix synthetic examples with real (non-synthetic) "
                    "assessments; submit them separately")
    if any(p["severity"] == "error" for p in check.problems):
        return [], check.problems
    return [a for a in normalized if a is not None], check.problems


# -- evaluation --------------------------------------------------------------------------


class _AssessmentIdentity(WellIdentity):
    """The user's identifier, used verbatim as the record's id."""

    @property
    def canonical(self) -> str:  # type: ignore[override]
        return self.original


def _observation_source(a: NormalizedAssessment, o: Observation) -> SourceRef:
    """Where an observation came from; unique per submitted observation."""
    origin = "synthetic-example" if a.synthetic else "user-assessment"
    return SourceRef(file=origin, table=f"{a.id}.temperature_observations", row=o.index + 1)


def _with_input_indexes(a: NormalizedAssessment, result: dict[str, Any]) -> dict[str, Any]:
    """Tag each observation in the engine's temperature selection with ``input_index``.

    The engine reports observations by value; two submitted readings can share
    depth, temperature and method yet differ in datum or source. The index of
    the submitted observation is recovered from the source reference the
    engine echoes back, so the selection never has to be matched by value.
    Nothing in the selection itself is changed.
    """
    selection = result.get("temperature_selection")
    if not selection:
        return result
    index = {str(_observation_source(a, o)): o.index
             for o in a.observations if o.passed_to_engine}

    def tag(o: dict[str, Any] | None) -> dict[str, Any] | None:
        return None if o is None else {**o, "input_index": index.get(o.get("source"))}

    selection = {
        **selection,
        "selected_observation": tag(selection.get("selected_observation")),
        "eligible_observations": [tag(o) for o in selection.get("eligible_observations", [])],
        "excluded_observations": [tag(o) for o in selection.get("excluded_observations", [])],
    }
    return {**result, "temperature_selection": selection}


def build_record(a: NormalizedAssessment) -> NormalizedWellRecord:
    """An in-memory record for the engine. Never cached, never merged."""
    rec = NormalizedWellRecord(identity=_AssessmentIdentity(base=a.id, number=None, suffix="",
                                                            original=a.id))
    origin = "synthetic-example" if a.synthetic else "user-assessment"
    rec.source_names = (origin,)

    def fv(value: float, column: str, unit: Unit) -> FieldValue:
        return FieldValue(value=value, unit=unit, provenance=Provenance.EXTRACTED,
                          confidence=Confidence.LOW,
                          source=SourceRef(file=origin, table=a.id, column=column),
                          method="user_declared",
                          notes=(("SYNTHETIC example value" if a.synthetic
                                  else "user-supplied, not independently verified"),))

    rec.depth_datum = DepthDatum(a.depth_datum)
    if a.total_depth_m is not None:
        rec.depth_m = fv(a.total_depth_m, "total_depth", Unit.METRE)
    if a.surface_elevation_m is not None and a.surface_elevation_reference == "msl":
        rec.surface_elevation_m = fv(a.surface_elevation_m, "surface_elevation", Unit.METRE)
    rec.temperatures = tuple(
        TemperatureObservation(
            depth_m=o.depth_m, temperature_k=o.temperature_k, method=o.method,
            source=_observation_source(a, o),
            depth_datum=DepthDatum(o.depth_datum),
        )
        for o in a.observations if o.passed_to_engine
    )
    return rec


def _convention_gate(a: NormalizedAssessment) -> dict[str, Any]:
    """Both named scenarios UNAVAILABLE without evaluation: depths are not TVD."""
    code = ("DEPTH_CONVENTION_NOT_ESTABLISHED" if a.depth_convention == "unknown"
            else "DEPTH_CONVENTION_NOT_TVD")
    reasons: list[dict[str, Any]] = [{
        "code": code,
        "message": (
            f"Depths are declared '{a.depth_convention}'. The approved pressure term "
            "rho_brine * g * (z_state - z_wl) is a vertical hydrostatic column and needs true "
            "vertical depth (TVD). Measured depth is never converted or relabelled, so the "
            "approved model is not evaluated."),
        "source": "assessment input contract (docs/scientific-notes.md)",
    }]
    datum_reason = depth_reference_diagnostic(DepthDatum(a.depth_datum))
    if datum_reason is not None:
        reasons.append(diagnostic(datum_reason, depth_datum=a.depth_datum))
    scenarios = [ScenarioResult(scenario=s, status=ValidationStatus.UNAVAILABLE,
                                diagnostics=tuple(reasons)).to_dict()
                 for s in WATER_LEVEL_SCENARIOS]
    return {"status": "not_evaluated", "model_path": api.APPROVED_MODEL_PATH,
            "well_id": a.id, "water_level_scenarios": scenarios,
            "reason": "depth convention is not TVD"}


#: What a user can do about each blocking reason.
NEXT_ACTIONS: dict[str, str] = {
    "DEPTH_CONVENTION_NOT_TVD": (
        "Provide true vertical depths (TVD) for the interval, total depth and temperature "
        "depths, e.g. from a deviation survey or a printed TVD. Measured depth is not converted."),
    "DEPTH_CONVENTION_NOT_ESTABLISHED": (
        "State whether your depths are true vertical depth (TVD) or measured depth (MD)."),
    Diagnostic.DEPTH_REFERENCE_NOT_ESTABLISHED.value: (
        "Find the depth datum in your source documents and declare it. Only depths measured "
        "from ground level can be used; do not guess the datum."),
    Diagnostic.UNSUPPORTED_DEPTH_DATUM.value: (
        "The approved model only accepts depths measured from ground level and applies no "
        "datum conversion. Use ground-level depths if your sources provide them."),
    Diagnostic.SURFACE_ELEVATION_UNAVAILABLE.value: (
        "Add the ground elevation above mean sea level to evaluate SEA_LEVEL_SENSITIVITY."),
    Diagnostic.STATE_POINT_ABOVE_WATER_LEVEL.value: (
        "The interval midpoint lies above the sea-level water level, so this scenario is not "
        "evaluable for this geometry. No input change is implied."),
    Diagnostic.TOTAL_DEPTH_NOT_RECORDED.value: (
        "Add the well's total depth: the approved temperature rule needs it to check that an "
        "observation is not below the bottom of the well."),
    Diagnostic.NO_ELIGIBLE_TEMPERATURE_OBSERVATION.value: (
        "Add a corrected temperature (Horner-corrected, Fertl-Wichmann or Squarci-Taffi) "
        "measured inside the storage interval, from ground level, in TVD, and not deeper than "
        "the total depth."),
    Diagnostic.TEMPERATURE_SAME_METHOD_CONFLICT.value: (
        "Two values from the same method at the selected depth disagree. Check your source "
        "and keep the correct one."),
    Diagnostic.TEMPERATURE_METHOD_TIE_UNRESOLVED.value: (
        "Horner-corrected and Fertl-Wichmann values at the same depth, without Squarci-Taffi, "
        "are not resolved by the approved rule. Check your source."),
    Diagnostic.OUTSIDE_VALIDATED_ENVELOPE.value: (
        "Conditions fall outside the density model's validated range (1-35 MPa absolute, "
        "280-400 K). This model cannot give a reportable estimate here; the diagnostic value "
        "must not be used as an estimate."),
    Diagnostic.EOS_NOT_EVALUABLE.value: (
        "Pressure is not positive at the state point for this geometry; the density model "
        "cannot be evaluated."),
}

#: Order in which a blocking reason is chosen as the main one.
_PRIORITY = ("DEPTH_CONVENTION_NOT_TVD", "DEPTH_CONVENTION_NOT_ESTABLISHED",
             Diagnostic.DEPTH_REFERENCE_NOT_ESTABLISHED.value,
             Diagnostic.UNSUPPORTED_DEPTH_DATUM.value,
             Diagnostic.TOTAL_DEPTH_NOT_RECORDED.value,
             Diagnostic.NO_ELIGIBLE_TEMPERATURE_OBSERVATION.value,
             Diagnostic.TEMPERATURE_SAME_METHOD_CONFLICT.value,
             Diagnostic.TEMPERATURE_METHOD_TIE_UNRESOLVED.value,
             Diagnostic.OUTSIDE_VALIDATED_ENVELOPE.value,
             Diagnostic.EOS_NOT_EVALUABLE.value,
             Diagnostic.STATE_POINT_ABOVE_WATER_LEVEL.value,
             Diagnostic.SURFACE_ELEVATION_UNAVAILABLE.value)


def _message(code: str) -> str:
    try:
        return DIAGNOSTIC_MESSAGES[Diagnostic(code)]
    except (ValueError, KeyError):
        return code


#: Plain-language headings and explanations for blocking reasons. The exact
#: engine message stays in the diagnostics; these are for the result summary.
REASON_TEXT: dict[str, tuple[str, str]] = {
    "DEPTH_CONVENTION_NOT_TVD": (
        "Depths are measured depth (MD)",
        "The pressure calculation needs true vertical depth. Measured depth is not converted."),
    "DEPTH_CONVENTION_NOT_ESTABLISHED": (
        "Depth convention not stated",
        "It is not stated whether depths are true vertical depth or measured depth."),
    Diagnostic.DEPTH_REFERENCE_NOT_ESTABLISHED.value: (
        "Depth datum not established",
        "The surface the depths are measured from is unknown, so no depth can be used."),
    Diagnostic.UNSUPPORTED_DEPTH_DATUM.value: (
        "Depths are not measured from ground level",
        "The approved model only uses depths below ground level and applies no conversion."),
    Diagnostic.TOTAL_DEPTH_NOT_RECORDED.value: (
        "Total depth missing",
        "Without the well's total depth, no temperature observation can be accepted."),
    Diagnostic.NO_ELIGIBLE_TEMPERATURE_OBSERVATION.value: (
        "No usable temperature in the storage interval",
        "No corrected temperature measured inside the interval meets the selection rule."),
    Diagnostic.TEMPERATURE_SAME_METHOD_CONFLICT.value: (
        "Conflicting temperatures",
        "Two values from the same method at the selected depth disagree."),
    Diagnostic.TEMPERATURE_METHOD_TIE_UNRESOLVED.value: (
        "Temperature methods disagree",
        "Horner-corrected and Fertl-Wichmann values at the same depth cannot be resolved."),
    Diagnostic.OUTSIDE_VALIDATED_ENVELOPE.value: (
        "Outside the validated range of the density model",
        "Pressure or temperature falls outside 1-35 MPa / 280-400 K, where the CO2 density "
        "model was checked. No estimate is reported."),
    Diagnostic.EOS_NOT_EVALUABLE.value: (
        "Pressure not positive at the state point",
        "The density model cannot be evaluated for this geometry."),
    Diagnostic.STATE_POINT_ABOVE_WATER_LEVEL.value: (
        "Interval lies above sea level",
        "The interval midpoint is above the sea-level water table, so this scenario does not "
        "apply."),
    Diagnostic.SURFACE_ELEVATION_UNAVAILABLE.value: (
        "Ground elevation above sea level missing",
        "Needed only for the sea-level water-table scenario."),
}

#: Readable scenario names; the codes stay in every payload.
SCENARIO_LABELS = {
    "GROUND_REFERENCE": "Water table at ground level (reference)",
    "SEA_LEVEL_SENSITIVITY": "Water table at sea level (sensitivity)",
}

#: Diagnostics that explain a choice but do not block a result.
_INFORMATIONAL = {Diagnostic.EQUAL_DISTANCE_SHALLOWER_SELECTED.value,
                  Diagnostic.SAME_DEPTH_SQUARCI_TAFFI_CONVENTION.value}


def _scenario_reasons(scenario: Mapping[str, Any], selection: Mapping[str, Any]) -> list[str]:
    """Blocking reason codes of one non-VALIDATED scenario, most specific first."""
    codes: list[str] = []
    for d in scenario.get("diagnostics", []):
        code = d["code"]
        if code in _INFORMATIONAL:
            continue
        if code == Diagnostic.TEMPERATURE_UNAVAILABLE.value:
            # Replace the generic code by the specific temperature reason.
            excluded = {r for o in selection.get("excluded_observations", []) for r in o["reasons"]}
            if Diagnostic.TOTAL_DEPTH_NOT_RECORDED.value in excluded:
                codes.append(Diagnostic.TOTAL_DEPTH_NOT_RECORDED.value)
            else:
                codes += [x["code"] for x in selection.get("diagnostics", [])
                          if x["code"] not in _INFORMATIONAL]
            continue
        codes.append(code)
    return codes


def _rank(code: str) -> int:
    return _PRIORITY.index(code) if code in _PRIORITY else len(_PRIORITY)


def outcome_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    """Overall status and category, per-scenario status, and every distinct
    blocking reason once, naming the scenarios it affects and what to do."""
    scenarios = result.get("water_level_scenarios") or []
    statuses = [s["validation_status"] for s in scenarios]
    overall = statuses[0] if statuses and len(set(statuses)) == 1 else "MIXED"
    selection = result.get("temperature_selection") or {}

    grouped: dict[str, dict[str, Any]] = {}
    for s in scenarios:
        if s["validation_status"] == ValidationStatus.VALIDATED.value:
            continue
        for code in _scenario_reasons(s, selection):
            entry = grouped.get(code)
            if entry is None:
                title, text = REASON_TEXT.get(code, (code.replace("_", " ").capitalize(), ""))
                technical = next((d.get("message") for d in s.get("diagnostics", [])
                                  if d["code"] == code), None) or _message(code)
                entry = grouped[code] = {
                    "code": code, "title": title, "explanation": text,
                    "action": NEXT_ACTIONS.get(code), "technical_message": technical,
                    "scenarios": [], "kind": ("outside_validated_range"
                                              if code == Diagnostic.OUTSIDE_VALIDATED_ENVELOPE.value
                                              else "input"),
                }
            if s["name"] not in entry["scenarios"]:
                entry["scenarios"].append(s["name"])
    reasons = sorted(grouped.values(), key=lambda r: _rank(r["code"]))

    validated = statuses.count(ValidationStatus.VALIDATED.value)
    if statuses and validated == len(statuses):
        category = "estimate"
    elif validated:
        category = "partial_estimate"
    elif statuses and all(x == ValidationStatus.OUTSIDE_VALIDATED_ENVELOPE.value for x in statuses):
        category = "outside_validated_range"
    else:
        category = "information_needed"

    main = reasons[0] if reasons else None
    return {
        "overall_status": overall,
        "category": category,
        "scenarios": [{"name": s["name"], "label": SCENARIO_LABELS.get(s["name"], s["name"]),
                       "validation_status": s["validation_status"],
                       "reportable_estimate": s.get("capacity_mt") is not None,
                       "diagnostic_value_only": s.get("diagnostic_capacity_mt") is not None}
                      for s in scenarios],
        "blocking_reasons": reasons,
        "main_reason": ({"code": main["code"], "message": main["technical_message"]}
                        if main else None),
        "next_action": main["action"] if main else None,
        "meaning": (
            "VALIDATED means the approved calculation ran and met its validation conditions for "
            "the inputs as declared. It does not verify the inputs, the reservoir's suitability "
            "or the actual storage capacity."),
    }


SYNTHETIC_EXAMPLE_WARNING = {
    "code": "synthetic_example",
    "severity": "synthetic",
    "message": ("SYNTHETIC EXAMPLE: every input of this assessment is fictional. The result "
                "demonstrates the workflow and the model's behaviour; it is not an estimate for "
                "any real site and does not show real-world accuracy."),
    "affects": ["all values"],
    "invalidates_result": True,
    "correction_applied": False,
}

USER_DECLARED_WARNING = {
    "code": "user_declared_inputs",
    "severity": "advisory",
    "message": ("Inputs are as declared by the submitter and are not independently verified by "
                "this tool. Results are conditional on them."),
    "detail": ("Depth datum and convention, interval, area, elevation and temperatures are taken "
               "as stated. A VALIDATED status concerns the calculation's validation conditions, "
               "not the accuracy of the inputs."),
    "affects": ["all values"],
    "invalidates_result": False,
    "correction_applied": False,
}


def _provenance(a: NormalizedAssessment, result: Mapping[str, Any]) -> dict[str, Any]:
    supplied = ["storage_area", "storage_interval", "depth_reference.datum",
                "depth_reference.convention", "temperature_observations"]
    if a.total_depth_m is not None:
        supplied.append("total_depth")
    if a.surface_elevation_m is not None:
        supplied.append("surface_elevation")
    sampled = result.get("sampled_inputs") or APPROVED_PRIORS.to_dict()
    return {
        "user_supplied": {
            "fields": supplied,
            "basis": "synthetic_example" if a.synthetic else DEPTH_REFERENCE_BASIS,
            "independently_verified": False,
            "sources": dict(a.sources),
        },
        "model_derived": [
            "h_g = z_base - z_top (gross storage-interval thickness)",
            "z_state = (z_top + z_base) / 2 (project model convention)",
            "z_wl per named water-level scenario (0, or ground elevation above sea level)",
            "P_EOS = 101325 Pa + rho_brine * g * (z_state - z_wl), per realisation",
            "temperature: selected from the submitted observations by the approved rule",
            "CO2 density rho(P_EOS, T): Peng-Robinson with Peneloux shift",
            "capacity percentiles from the Monte Carlo realisations",
        ],
        "literature_constrained": {k: v for k, v in sampled.items()
                                   if k in ("porosity", "storage_efficiency")},
        "project_assumption": {k: v for k, v in sampled.items() if k == "brine_density_kg_m3"},
        "not_user_adjustable": ("Porosity, storage efficiency and brine density are the approved "
                                "parameter set's priors; the approved workflow does not accept "
                                "overrides."),
    }


def evaluate_assessment(a: NormalizedAssessment, samples: int, seed: int) -> dict[str, Any]:
    """Evaluate one normalized assessment through the shared approved-model path."""
    base = api._scenario(api.DEFAULT_SCENARIO)
    if a.depth_convention != "TVD":
        result = _convention_gate(a)
    else:
        inputs = api.ApprovedUserInputs(area_m2=a.area_m2,
                                        interval=StorageInterval(a.z_top_m, a.z_base_m))
        result = api._screen_approved(build_record(a), base, inputs, samples, seed)
        result = _with_input_indexes(a, result)
    interpretation = result.get("interpretation") or api._approved_interpretation()
    warnings = list(interpretation.get("warnings", []))
    warnings.insert(0, dict(USER_DECLARED_WARNING))
    if a.synthetic:
        warnings.insert(0, dict(SYNTHETIC_EXAMPLE_WARNING))
    interpretation = {**interpretation, "warnings": warnings}
    result = {**result, "interpretation": interpretation}
    return {
        "assessment_id": a.id,
        "name": a.name,
        "synthetic": a.synthetic,
        "data_origin": "synthetic_example" if a.synthetic else "user_supplied",
        "example": a.example,
        "schema_version": SCHEMA_VERSION,
        "model": {
            "model_path": api.APPROVED_MODEL_PATH,
            "parameter_set": {"name": base.name, "version": base.version},
            "contract": result.get("contract", "docs/phase13-owner-decision-record.md"),
            "capacity_equation": "M = A * h_g * phi * rho_CO2(P_EOS, T) * E",
            "engine": "ccs_screen.approved_model.evaluate_approved_model",
            "evaluated": result.get("status") == "evaluated",
        },
        "run": {"samples": samples, "seed": seed},
        "outcome": outcome_summary(result),
        "inputs": a.inputs_dict(),
        "provenance": _provenance(a, result),
        "result": result,
        "interpretation": interpretation,
        "limitations": [
            "Scenario-based screening estimate; never a certified or site-specific capacity.",
            "Percentiles describe the sampled priors only, not total uncertainty or model bias.",
            "The two water-level scenarios are named project scenarios, not measured heads.",
            "Inputs are as declared and not independently verified.",
        ],
    }


def _check_run_controls(samples: Any, seed: Any, n_assessments: int) -> tuple[int, int]:
    samples = api.validate_samples(samples)
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= MAX_SEED:
        raise api.ApiError(f"seed: expected an integer between 0 and {MAX_SEED}, got {seed!r}")
    if samples * n_assessments > MAX_TOTAL_SAMPLES:
        raise api.ApiError(
            f"computation limit: {n_assessments} assessments x {samples} samples exceeds "
            f"{MAX_TOTAL_SAMPLES} realisations per request; lower samples or split the file")
    return samples, seed


def evaluate_document(document: Any, samples: Any = DEFAULT_SAMPLES,
                      seed: Any = DEFAULT_SEED) -> dict[str, Any]:
    """Validate then evaluate every assessment. Raises AssessmentError on input errors."""
    normalized, problems = validate_document(document)
    if any(p["severity"] == "error" for p in problems):
        raise AssessmentError(problems)
    samples, seed = _check_run_controls(samples, seed, len(normalized))
    results = [evaluate_assessment(a, samples, seed) for a in normalized]
    return {
        "schema_version": SCHEMA_VERSION,
        "run": {"samples": samples, "seed": seed},
        "notices": [p for p in problems if p["severity"] != "error"],
        "assessments": results,
        "summary_csv": summary_csv(results),
    }


# -- exports -------------------------------------------------------------------------------

SUMMARY_COLUMNS = (
    "assessment_id", "assessment_name", "synthetic", "data_origin", "scenario",
    "validation_status", "value_type", "p10_mt", "p50_mt", "p90_mt", "mean_mt",
    "diagnostic_p50_mt_not_an_estimate", "main_reason", "selected_temperature_k", "z_state_m",
    "z_wl_m", "n_samples", "seed", "model_path", "parameter_set", "schema_version",
    "interpretation",
)


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


def spreadsheet_safe(text: str) -> str:
    """User text that a spreadsheet will show literally instead of evaluating.

    Text whose first character, or first character after leading whitespace,
    could start a formula (= + - @, tab, CR, LF) is prefixed with an
    apostrophe (OWASP CSV-injection guidance). CSV quoting alone does not
    stop evaluation. Only the CSV export is escaped; JSON keeps the text.
    """
    if text.startswith(_FORMULA_PREFIXES) or text.lstrip().startswith(_FORMULA_PREFIXES):
        return "'" + text
    return text


def summary_csv(results: list[dict[str, Any]]) -> str:
    """One row per assessment and named scenario, statuses preserved.

    Percentile columns are filled only for VALIDATED scenarios (a reportable
    estimate); an OUTSIDE_VALIDATED_ENVELOPE diagnostic P50 goes in its own,
    explicitly named column and never in the estimate columns.
    """
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(SUMMARY_COLUMNS)
    for item in results:
        result = item["result"]
        main = (item["outcome"].get("main_reason") or {}).get("code", "")
        parameter_set = item["model"]["parameter_set"]
        for scenario in result.get("water_level_scenarios", []):
            capacity = scenario.get("capacity_mt")
            diagnostic_capacity = scenario.get("diagnostic_capacity_mt")
            value_type = ("reportable_estimate" if capacity
                          else "diagnostic_only" if diagnostic_capacity else "none")
            interpretation = ("Conditional screening estimate; not a certified capacity"
                              if capacity else "No reportable estimate")
            if item["synthetic"]:
                interpretation = "SYNTHETIC EXAMPLE - fictional inputs. " + interpretation
            codes = [d["code"] for d in scenario.get("diagnostics", [])]
            writer.writerow([_fmt(v) for v in (
                spreadsheet_safe(item["assessment_id"]),
                spreadsheet_safe(item.get("name") or ""), "true" if item["synthetic"] else "false",
                item["data_origin"], scenario["name"], scenario["validation_status"], value_type,
                capacity and capacity["p10"], capacity and capacity["p50"],
                capacity and capacity["p90"], capacity and capacity["mean"],
                diagnostic_capacity and diagnostic_capacity["p50"],
                ";".join(codes) or main, scenario.get("temperature_k"), scenario.get("z_state_m"),
                scenario.get("z_wl_m"), item["run"]["samples"], item["run"]["seed"],
                item["model"]["model_path"],
                f"{parameter_set['name']} v{parameter_set['version']}",
                item["schema_version"], interpretation,
            )])
    return out.getvalue()


def _cell(value: Any) -> str:
    """A CSV cell that parses back to the same value (round-trip safe)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else repr(value)
    return str(value)


def document_to_csv(document: Mapping[str, Any]) -> str:
    """Write a (valid) schema document in the import CSV format."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for a in document["assessments"]:
        interval = a["storage_interval"]
        elevation = a.get("surface_elevation") or {}
        total = a.get("total_depth") or {}
        if total and total.get("unit") != interval["unit"]:
            raise ValueError("CSV export needs total_depth in the interval's depth unit")
        base = {
            "schema_version": "1", "assessment_id": a["id"], "assessment_name": a.get("name", ""),
            "synthetic": "true" if a.get("synthetic") else "",
            "area_value": a["storage_area"]["value"], "area_unit": a["storage_area"]["unit"],
            "interval_top": interval["top"], "interval_base": interval["base"],
            "depth_unit": interval["unit"], "depth_datum": a["depth_reference"]["datum"],
            "depth_convention": a["depth_reference"]["convention"],
            "total_depth": total.get("value", ""),
            "surface_elevation": elevation.get("value", ""),
            "surface_elevation_unit": elevation.get("unit", ""),
            "surface_elevation_reference": elevation.get("reference", ""),
            "notes": a.get("notes", ""),
            "area_source": a["storage_area"].get("source", ""),
            "interval_source": interval.get("source", ""),
            "depth_reference_source": a["depth_reference"].get("source", ""),
            "total_depth_source": total.get("source", ""),
            "surface_elevation_source": elevation.get("source", ""),
        }
        observations = a.get("temperature_observations") or [None]
        for obs in observations:
            row = dict(base)
            if obs:
                row.update({
                    "obs_temperature": obs["value"], "obs_temperature_unit": obs["unit"],
                    "obs_depth": obs["depth"], "obs_depth_unit": obs["depth_unit"],
                    "obs_depth_datum": obs["depth_datum"],
                    "obs_depth_convention": obs["depth_convention"], "obs_method": obs["method"],
                    "obs_source": obs.get("source", ""),
                })
            writer.writerow([_cell(row.get(c)) for c in CSV_COLUMNS])
    return out.getvalue()


# -- packaged files: examples and templates ----------------------------------------------------

#: Files under ccs_screen/assessment_data that may be served to users.
DATA_FILES = {
    "synthetic-examples.json": "application/json",
    "synthetic-examples.csv": "text/csv",
    "assessment-template.json": "application/json",
    "assessment-template.csv": "text/csv",
}


def data_file(name: str) -> str:
    if name not in DATA_FILES:
        raise KeyError(name)
    return resources.files("ccs_screen").joinpath("assessment_data", name).read_text(encoding="utf-8")


def examples_document() -> dict[str, Any]:
    return json.loads(data_file("synthetic-examples.json"))


def input_contract() -> dict[str, Any]:
    """Machine-readable summary of the input schema, units and limits."""
    return {
        "schema_version": SCHEMA_VERSION,
        "supported_schema_versions": list(SUPPORTED_SCHEMA_VERSIONS),
        "documentation": "docs/assessment-input-schema.md",
        "required": ["id", "storage_area {value, unit}", "storage_interval {top, base, unit}",
                     "depth_reference {datum, convention}"],
        "required_for_an_approved_result": [
            "depth_reference.datum = ground_level", "depth_reference.convention = TVD",
            "total_depth", "an eligible temperature observation inside the interval (TVD, "
            "ground level, not deeper than total depth)",
            "surface_elevation (reference msl) for SEA_LEVEL_SENSITIVITY",
        ],
        "optional_context": ["name", "notes", "stratigraphy", "source on every value"],
        "units": {"area": list(AREA_UNITS), "length": list(LENGTH_UNITS),
                  "temperature": list(TEMPERATURE_UNITS)},
        "unit_factors": {"area_to_m2": AREA_UNITS, "length_to_m": LENGTH_UNITS,
                         "temperature": "K = degC + 273.15; K = (degF - 32) * 5/9 + 273.15"},
        "depth_datums": list(DATUMS),
        "supported_depth_datum": "ground_level",
        "depth_conventions": list(DEPTH_CONVENTIONS),
        "supported_depth_convention": "TVD",
        "elevation_references": list(ELEVATION_REFERENCES),
        "temperature_methods": list(METHODS),
        "eligible_temperature_methods": list(ELIGIBLE_METHODS),
        "depth_reference_basis": DEPTH_REFERENCE_BASIS,
        "csv": {"required_columns": list(CSV_REQUIRED_COLUMNS), "columns": list(CSV_COLUMNS),
                "grouping": "rows with the same assessment_id form one assessment; one row per "
                            "temperature observation; assessment-level columns must be "
                            "identical on every row of an assessment"},
        "limits": LIMITS,
        "persistence": "submitted data is processed in memory and not stored",
    }


# -- engine readiness ---------------------------------------------------------------------------

_log = logging.getLogger(__name__)
_SELF_CHECK: dict[str, Any] | None = None
_SELF_CHECK_LOCK = threading.Lock()

#: The self-check evaluates the complete synthetic example; it must come back
#: VALIDATED for both named scenarios with a reportable estimate.
SELF_CHECK_EXAMPLE = "SYNTH ALPHA|1"


def engine_readiness(refresh: bool = False) -> dict[str, Any]:
    """Whether the approved engine can evaluate user assessments.

    Independent of any bundled or local well dataset. Runs the complete
    synthetic example once (64 realisations, fixed seed) through the same
    path as every assessment, and caches the outcome for the process.
    """
    global _SELF_CHECK
    with _SELF_CHECK_LOCK:
        if _SELF_CHECK is not None and not refresh:
            return _SELF_CHECK
        try:
            document = examples_document()
            document = {**document, "assessments": [a for a in document["assessments"]
                                                    if a["id"] == SELF_CHECK_EXAMPLE]}
            result = evaluate_document(document, samples=64, seed=1)["assessments"][0]
            statuses = [s["validation_status"] for s in result["outcome"]["scenarios"]]
            ready = (statuses == [ValidationStatus.VALIDATED.value] * 2
                     and all(s["reportable_estimate"] for s in result["outcome"]["scenarios"]))
            problem = None if ready else f"self-check returned {statuses}, expected VALIDATED x2"
        except (OSError, ValueError, KeyError) as exc:
            # Packaged example missing or unreadable, or the engine refused it.
            _log.exception("assessment engine self-check failed")
            ready, problem = False, f"{type(exc).__name__}: {exc}"
        _SELF_CHECK = {
            "ready": ready,
            "check": (f"evaluates the synthetic example {SELF_CHECK_EXAMPLE} through the approved "
                      "engine (64 realisations, seed 1); expects VALIDATED for both scenarios"),
            "problem": problem,
            "schema_version": SCHEMA_VERSION,
        }
        return _SELF_CHECK
