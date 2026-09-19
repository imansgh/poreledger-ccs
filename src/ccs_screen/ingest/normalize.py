"""Assemble RawWellRecords from the structured sources into normalized records.

Design rules, all of them consequences of the reconnaissance:

* Depths are captured with their datum. GEOTHOPICA and the national registry
  do not state one, so those stay ``UNKNOWN`` and are never silently treated as
  sub-sea. A datum correction happens only where an elevation is available.
* Conflicting depths across sources are recorded as a
  :class:`~ccs_screen.ingest.provenance.Conflict`; the value from the most
  specific source wins, and the alternatives are kept.
* Temperature keeps its acquisition method. Selection picks the best-ranked
  *reservoir* method near total depth, and a surface air mean is never
  selectable.
* Gross stratigraphic thickness is populated; net storage thickness is not,
  and there is no code path from one to the other.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from ccs_screen.ingest.identity import WellIdentity, canonical_well_id
from ccs_screen.ingest.provenance import (
    TEMPERATURE_METHOD_CONFIDENCE,
    TEMPERATURE_METHOD_RANK,
    Conflict,
    Confidence,
    FieldValue,
    Provenance,
    SourceRef,
    TemperatureMethod,
    Unit,
)
from ccs_screen.ingest.records import (
    NormalizedWellRecord,
    RawWellRecord,
    StratigraphicInterval,
    TemperatureObservation,
)
from ccs_screen.ingest.sources import (
    GEOTHOPICA_FILE,
    PO_WELLS_FILE,
    POZZI_STORICI_FILE,
    SourceNotFoundError,
    SourceTable,
    StructuredSources,
    classify_temperature_method,
)
from ccs_screen.ingest.units import (
    AmbiguousValueError,
    DepthDatum,
    DepthMeasurement,
    parse_number,
    to_kelvin,
)

#: Depth agreement tolerance before a conflict is raised (metres).
DEPTH_CONFLICT_TOLERANCE_M = 1.0

#: A temperature counts as reservoir temperature when it sits within this
#: fraction of total depth. Shallow modelled points (300/500/1000 m grid) are
#: not reservoir conditions.
RESERVOIR_DEPTH_FRACTION = 0.85


def _num(value: Any, field_name: str) -> tuple[float | None, str | None]:
    """Parse, returning (value, problem). Never raises."""
    try:
        return parse_number(value, field_name=field_name).value, None
    except AmbiguousValueError as exc:
        return None, str(exc)
    except ValueError:
        return None, None


class WellNormalizer:
    """Builds normalized records by merging the structured sources."""

    def __init__(self, data_dir: str | Path):
        self.sources = StructuredSources(Path(data_dir))
        self._raw: list[RawWellRecord] = []
        self._wells: dict[str, NormalizedWellRecord] = {}
        self._used_sources: set[str] = set()

    # -- record plumbing ---------------------------------------------------

    def _well(self, name: str) -> NormalizedWellRecord | None:
        try:
            identity = canonical_well_id(name)
        except ValueError:
            return None
        if identity.number is None and not identity.base:
            return None
        rec = self._wells.get(identity.canonical)
        if rec is None:
            rec = NormalizedWellRecord(identity=identity)
            self._wells[identity.canonical] = rec
        return rec

    def _capture(self, rec: NormalizedWellRecord, name: str, field_name: str,
                 value: Any, ref: SourceRef, **kw: Any) -> RawWellRecord:
        raw = RawWellRecord.capture(name, field_name, value, ref, **kw)
        self._raw.append(raw)
        rec.raw_records = rec.raw_records + (raw,)
        if ref.file not in rec.source_names:
            rec.source_names = rec.source_names + (ref.file,)
        return raw

    def _set_depth(self, rec: NormalizedWellRecord, value: float, ref: SourceRef,
                   original: str, datum: DepthDatum) -> None:
        """Set or reconcile total depth, recording disagreement."""
        incoming = FieldValue(
            value=value, unit=Unit.METRE, provenance=Provenance.EXTRACTED,
            confidence=Confidence.HIGH, source=ref, original_value=original,
            original_unit="m", method="structured_read",
        )
        current = rec.depth_m
        if not current.is_present:
            rec.depth_m = incoming
            rec.depth_datum = datum
            return
        if abs(float(current.value) - value) <= DEPTH_CONFLICT_TOLERANCE_M:
            return
        conflict = Conflict(
            field_name="depth_m",
            chosen=current.value,
            alternatives=((value, str(ref)),),
            note="sources disagree on total depth; kept the first (most specific) source",
        )
        rec.depth_m = FieldValue(
            value=current.value, unit=current.unit, provenance=current.provenance,
            confidence=Confidence.MEDIUM, source=current.source,
            original_value=current.original_value, original_unit=current.original_unit,
            method=current.method, conflicts=current.conflicts + (conflict,),
            notes=current.notes + ("depth disagrees between sources",),
        )
        rec.conflicts = rec.conflicts + (conflict,)

    # -- source loaders ----------------------------------------------------

    def load_geothopica_anagrafica(self) -> int:
        table = self.sources.geothopica("Anagrafica")
        self._used_sources.add(table.file)
        count = 0
        for row_no, row in table.records():
            name = row.get("nome")
            if not name:
                continue
            rec = self._well(str(name))
            if rec is None:
                continue
            count += 1
            depth_col = next((c for c in table.header if c.lower().startswith("profondit")), None)
            if depth_col and str(row.get(depth_col) or "").strip():
                ref = table.ref(row_no, depth_col)
                value, problem = _num(row[depth_col], "depth_m")
                self._capture(rec, str(name), "depth_m", row[depth_col], ref,
                              original_unit="m", datum=DepthDatum.UNKNOWN,
                              notes=(problem,) if problem else ())
                if value is not None and value > 0:
                    self._set_depth(rec, value, ref, str(row[depth_col]), DepthDatum.UNKNOWN)

            if str(row.get("quota") or "").strip():
                ref = table.ref(row_no, "quota")
                value, _ = _num(row["quota"], "surface_elevation_m")
                self._capture(rec, str(name), "surface_elevation_m", row["quota"], ref, original_unit="m")
                if value is not None:
                    rec.surface_elevation_m = FieldValue(
                        value=value, unit=Unit.METRE, provenance=Provenance.EXTRACTED,
                        confidence=Confidence.MEDIUM, source=ref,
                        original_value=str(row["quota"]), original_unit="m",
                        notes=("ground elevation above MSL as reported by GEOTHOPICA",),
                    )
            for col, attr in (("proprietario", "operator"), ("esito", "outcome")):
                if str(row.get(col) or "").strip():
                    ref = table.ref(row_no, col)
                    self._capture(rec, str(name), attr, row[col], ref)
                    setattr(rec, attr, FieldValue(
                        value=str(row[col]).strip(), unit=Unit.NONE,
                        provenance=Provenance.EXTRACTED, confidence=Confidence.HIGH,
                        source=ref, original_value=str(row[col]),
                    ))
        return count

    def load_geothopica_temperatures(self) -> int:
        table = self.sources.geothopica("Temperature")
        self._used_sources.add(table.file)
        cols = {c.lower(): c for c in table.header}
        depth_col = next((c for k, c in cols.items() if k.startswith("profondit")), None)
        temp_col = next((c for k, c in cols.items() if k.startswith("temperatura")), None)
        stop_col = next((c for k, c in cols.items() if "stop" in k), None)
        type_col = next((c for k, c in cols.items() if "tipo" in k), None)
        count = 0
        for row_no, row in table.records():
            name = row.get(table.header[0])
            if not name or depth_col is None or temp_col is None:
                continue
            rec = self._well(str(name))
            if rec is None:
                continue
            depth, _ = _num(row.get(depth_col), "depth_m")
            celsius, _ = _num(row.get(temp_col), "temperature")
            if depth is None or celsius is None:
                continue
            method = classify_temperature_method(row.get(type_col) if type_col else None)
            hours, _ = _num(row.get(stop_col), "hours") if stop_col else (None, None)
            ref = table.ref(row_no, temp_col)
            self._capture(rec, str(name), "temperature", row.get(temp_col), ref,
                          original_unit="degC", extraction_method=method.value)
            rec.temperatures = rec.temperatures + (TemperatureObservation(
                depth_m=depth, temperature_k=to_kelvin(celsius, Unit.CELSIUS),
                method=method.value, hours_since_circulation=hours or None,
                source=ref, original_celsius=celsius,
            ),)
            count += 1
        return count

    def load_geothopica_stratigraphy(self) -> int:
        table = self.sources.geothopica("Lito-Stratigrafie")
        self._used_sources.add(table.file)
        cols = {c.lower(): c for c in table.header}
        top_col, bot_col = cols.get("top"), cols.get("bottom")
        lith_col = cols.get("litologia")
        age_col = next((c for k, c in cols.items() if k.startswith("da et")), None)
        count = 0
        for row_no, row in table.records():
            name = row.get(table.header[0])
            if not name or top_col is None or bot_col is None:
                continue
            rec = self._well(str(name))
            if rec is None:
                continue
            top, _ = _num(row.get(top_col), "top_m")
            bottom, _ = _num(row.get(bot_col), "bottom_m")
            if top is None or bottom is None or bottom <= top:
                continue
            ref = table.ref(row_no, f"{top_col}/{bot_col}")
            self._capture(rec, str(name), "stratigraphic_interval",
                          f"{row.get(top_col)}-{row.get(bot_col)}", ref, original_unit="m")
            rec.intervals = rec.intervals + (StratigraphicInterval(
                top_m=top, bottom_m=bottom,
                lithology=(str(row.get(lith_col)).strip() if lith_col and row.get(lith_col) else None),
                age=(str(row.get(age_col)).strip() if age_col and row.get(age_col) else None),
                source=ref,
            ),)
            count += 1
        return count

    def load_pozzi_storici(self) -> int:
        table = self.sources.pozzi_storici()
        self._used_sources.add(table.file)
        count = 0
        for row_no, row in table.records():
            name = row.get("Nome pozzo")
            if not name:
                continue
            identity = None
            try:
                identity = canonical_well_id(str(name))
            except ValueError:
                continue
            # Only enrich wells the pilot already knows; the registry has 7300.
            rec = self._wells.get(identity.canonical)
            if rec is None:
                continue
            count += 1
            if str(row.get("Prof") or "").strip():
                ref = table.ref(row_no, "Prof")
                value, _ = _num(row["Prof"], "depth_m")
                self._capture(rec, str(name), "depth_m", row["Prof"], ref,
                              original_unit="m", datum=DepthDatum.UNKNOWN)
                if value is not None and value > 0:
                    self._set_depth(rec, value, ref, str(row["Prof"]), DepthDatum.UNKNOWN)
            for col, attr in (("Anno", "year"), ("Operatore", "operator"), ("Esito", "outcome")):
                if str(row.get(col) or "").strip() and not getattr(rec, attr).is_present:
                    ref = table.ref(row_no, col)
                    self._capture(rec, str(name), attr, row[col], ref)
                    val: Any = str(row[col]).strip()
                    if attr == "year":
                        parsed, _ = _num(val, "year")
                        val = parsed
                        if val is None:
                            continue
                    setattr(rec, attr, FieldValue(
                        value=val, unit=Unit.NONE, provenance=Provenance.EXTRACTED,
                        confidence=Confidence.HIGH, source=ref, original_value=str(row[col]),
                    ))
        return count

    def load_po_wells(self) -> int:
        table = self.sources.po_wells()
        self._used_sources.add(table.file)
        count = 0
        for row_no, row in table.records():
            name = row.get("Well_name")
            if not name:
                continue
            try:
                identity = canonical_well_id(str(name))
            except ValueError:
                continue
            rec = self._wells.get(identity.canonical)
            if rec is None:
                continue
            count += 1
            for col, attr, unit in (("Lat_WGS84_approx", "latitude_deg", Unit.DEGREE),
                                    ("Lon_WGS84_approx", "longitude_deg", Unit.DEGREE)):
                if str(row.get(col) or "").strip() and not getattr(rec, attr).is_present:
                    ref = table.ref(row_no, col)
                    value, _ = _num(row[col], attr)
                    self._capture(rec, str(name), attr, row[col], ref, original_unit="deg")
                    if value is not None:
                        setattr(rec, attr, FieldValue(
                            value=value, unit=unit, provenance=Provenance.EXTRACTED,
                            confidence=Confidence.MEDIUM, source=ref,
                            original_value=str(row[col]), original_unit="deg",
                            notes=("WGS84, approximate per source column name",),
                        ))
            if str(row.get("Depth_m") or "").strip():
                ref = table.ref(row_no, "Depth_m")
                value, _ = _num(row["Depth_m"], "depth_m")
                self._capture(rec, str(name), "depth_m", row["Depth_m"], ref, original_unit="m")
                if value is not None and value > 0:
                    self._set_depth(rec, value, ref, str(row["Depth_m"]), DepthDatum.UNKNOWN)
        return count

    # -- derivation --------------------------------------------------------

    def _derive(self, rec: NormalizedWellRecord) -> None:
        self._derive_gross_thickness(rec)
        self._derive_temperature(rec)
        self._derive_depth_msl(rec)

    def _derive_gross_thickness(self, rec: NormalizedWellRecord) -> None:
        if not rec.intervals:
            return
        deepest = max(rec.intervals, key=lambda i: i.bottom_m)
        total = sum(i.gross_thickness_m for i in rec.intervals)
        rec.gross_thickness_m = FieldValue(
            value=deepest.gross_thickness_m, unit=Unit.METRE,
            provenance=Provenance.DERIVED, confidence=Confidence.MEDIUM,
            source=deepest.source,
            derivation=(
                f"bottom-top of the deepest logged chronostratigraphic unit "
                f"({deepest.age or 'unknown age'}: {deepest.top_m}-{deepest.bottom_m} m)"
            ),
            notes=(
                "GROSS stratigraphic interval, not net storage thickness",
                f"{len(rec.intervals)} intervals logged, {total:.1f} m total gross section",
                "net thickness requires a net-to-gross ratio that no source provides",
            ),
        )

    def _derive_temperature(self, rec: NormalizedWellRecord) -> None:
        if not rec.temperatures:
            return
        reservoir = [t for t in rec.temperatures
                     if TEMPERATURE_METHOD_RANK.get(TemperatureMethod(t.method), 99) < 99]
        if not reservoir:
            rec.temperature_k = FieldValue.missing(
                "only surface air temperature available; not a reservoir temperature"
            )
            return
        deepest = max(t.depth_m for t in reservoir)
        near_td = [t for t in reservoir if t.depth_m >= RESERVOIR_DEPTH_FRACTION * deepest]
        chosen = min(near_td, key=lambda t: (TEMPERATURE_METHOD_RANK[TemperatureMethod(t.method)],
                                             -t.depth_m))
        alternatives = tuple(
            (round(t.temperature_k, 2), f"{t.method} @ {t.depth_m:g} m")
            for t in sorted(near_td, key=lambda t: t.method) if t is not chosen
        )
        conflicts: tuple[Conflict, ...] = ()
        if alternatives:
            spread = max(t.temperature_k for t in near_td) - min(t.temperature_k for t in near_td)
            conflicts = (Conflict(
                field_name="temperature_k",
                chosen=round(chosen.temperature_k, 2),
                alternatives=alternatives,
                note=(f"methods disagree by {spread:.1f} K at comparable depth; "
                      f"selected the best-ranked reservoir method"),
            ),)
            rec.conflicts = rec.conflicts + conflicts
        method = TemperatureMethod(chosen.method)
        rec.temperature_k = FieldValue(
            value=chosen.temperature_k, unit=Unit.KELVIN, provenance=Provenance.DERIVED,
            confidence=TEMPERATURE_METHOD_CONFIDENCE[method], source=chosen.source,
            method=chosen.method, original_value=str(chosen.original_celsius),
            original_unit="degC",
            derivation=(
                f"{chosen.original_celsius} degC at {chosen.depth_m:g} m "
                f"({chosen.method}) converted to K"
            ),
            conflicts=conflicts,
            notes=(f"hours since circulation: {chosen.hours_since_circulation}",)
            if chosen.hours_since_circulation else (),
        )

    def _derive_depth_msl(self, rec: NormalizedWellRecord) -> None:
        if not rec.depth_m.is_present:
            return
        if rec.depth_datum is DepthDatum.UNKNOWN:
            rec.depth_msl_m = FieldValue.missing(
                "source does not state a depth datum; cannot express as sub-sea depth"
            )
            return
        if not rec.surface_elevation_m.is_present:
            rec.depth_msl_m = FieldValue.missing(
                f"depth is referenced to {rec.depth_datum.value} but no datum elevation is available"
            )
            return
        measurement = DepthMeasurement(
            value_m=float(rec.depth_m.value), datum=rec.depth_datum,
            datum_elevation_m=float(rec.surface_elevation_m.value),
        )
        corrected = measurement.to_msl()
        rec.depth_msl_m = FieldValue(
            value=corrected.value_m, unit=Unit.METRE, provenance=Provenance.DERIVED,
            confidence=Confidence.MEDIUM, source=rec.depth_m.source,
            derivation=(f"{rec.depth_m.value} m below {rec.depth_datum.value} "
                        f"minus {rec.surface_elevation_m.value} m datum elevation"),
        )

    # -- entry point -------------------------------------------------------

    def run(self) -> list[NormalizedWellRecord]:
        """Load every available source, then derive. Missing files are skipped."""
        loaders = (
            self.load_geothopica_anagrafica,
            self.load_geothopica_temperatures,
            self.load_geothopica_stratigraphy,
            self.load_pozzi_storici,
            self.load_po_wells,
        )
        for loader in loaders:
            try:
                loader()
            except (SourceNotFoundError, ImportError):
                continue
        for rec in self._wells.values():
            self._derive(rec)
        return sorted(self._wells.values(), key=lambda r: r.canonical_id)

    @property
    def raw_records(self) -> tuple[RawWellRecord, ...]:
        return tuple(self._raw)

    @property
    def used_sources(self) -> tuple[str, ...]:
        return tuple(sorted(self._used_sources))
