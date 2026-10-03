"""Readers for the structured sources identified during reconnaissance.

Only these files are read. The 11 GB scanned-PDF corpus is deliberately not
touched: it carries no reservoir properties, only metadata already present here.

===========================================  ==========================================
File                                          What it supplies
===========================================  ==========================================
Requested_data_GEOTHOPICA_pozzi_piemonte      temperature vs depth (+ method),
  sheet "Temperature"                         the only temperature source anywhere
  sheet "Lito-Stratigrafie"                   gross chronostratigraphic intervals
  sheet "Anagrafica"                          depth, coordinates, elevation, operator
pozzi-storici.csv                             national registry: depth, year, outcome
po_wells_clean.csv                            cleaned Po-valley subset: depth, WGS84
===========================================  ==========================================

Every CSV in this dataset is cp1252, not UTF-8.

Read failures. A source that is absent raises :class:`SourceNotFoundError`. A
source that is present but cannot be read -- an inaccessible file, a corrupt
ZIP container, a workbook missing its required parts, malformed workbook XML,
a truncated compressed member, or a sheet with no header row -- raises
:class:`SourceReadError`, naming the file, the table and the underlying error.
Only those expected I/O and format failures are translated; anything else
(a programming error) propagates unchanged.
"""

from __future__ import annotations

import csv
import io
import zipfile
import zlib
from dataclasses import dataclass
from xml.etree.ElementTree import ParseError
from pathlib import Path
from typing import Any, Iterator

from ccs_screen.ingest.provenance import SourceRef, TemperatureMethod

CSV_ENCODING = "cp1252"

GEOTHOPICA_FILE = "Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx"
POZZI_STORICI_FILE = "pozzi-storici.csv"
PO_WELLS_FILE = "po_wells_clean.csv"

#: Verbatim method strings in the GEOTHOPICA Temperature sheet, mapped to the
#: provenance enum. Unrecognised strings map to UNKNOWN rather than being
#: guessed into a known method.
_METHOD_MAP = {
    "estrap.metodo squarci-taffi": TemperatureMethod.SQUARCI_TAFFI,
    "estrap.metodo fertl-wichmann": TemperatureMethod.FERTL_WICHMANN,
    "non stabilizzata": TemperatureMethod.NON_STABILIZED,
    "temp.atmosferica media annuale": TemperatureMethod.SURFACE_AIR,
}


def classify_temperature_method(raw: object) -> TemperatureMethod:
    key = " ".join(str(raw or "").strip().lower().split())
    for prefix, method in _METHOD_MAP.items():
        if key.startswith(prefix[:18]):
            return method
    return TemperatureMethod.UNKNOWN


class SourceNotFoundError(FileNotFoundError):
    """A configured source file is not present in the data directory."""


class SourceReadError(Exception):
    """A source file is present but could not be read or parsed.

    Carries the source identity (``file``, ``table``) and the underlying
    exception's type and message, which is the diagnostic an operator needs.
    """

    def __init__(self, path: Path, table: str, cause: BaseException | str) -> None:
        self.file = path.name
        self.path = str(path)
        self.table = table
        if isinstance(cause, BaseException):
            self.reason = f"{type(cause).__name__}: {cause}"
        else:
            self.reason = cause
        super().__init__(f"cannot read {self.file} ({table}): {self.reason}")


def _xml_parse_errors() -> tuple[type[BaseException], ...]:
    """XML parse errors openpyxl can raise, for whichever parser it uses."""
    errors: tuple[type[BaseException], ...] = (ParseError,)
    try:
        from lxml.etree import XMLSyntaxError
    except ImportError:
        return errors
    return errors + (XMLSyntaxError,)


#: Expected failures while opening or parsing an .xlsx: a corrupt or truncated
#: ZIP container (BadZipFile, zlib.error, EOFError), malformed workbook XML,
#: openpyxl's own refusal, and I/O errors. Deliberately not ``Exception``.
_XLSX_READ_ERRORS: tuple[type[BaseException], ...] = (
    OSError, zipfile.BadZipFile, zlib.error, EOFError, *_xml_parse_errors(),
)

#: Parts every .xlsx package has; openpyxl raises a bare KeyError without them,
#: which is checked for up front rather than caught (a KeyError is too broad).
_XLSX_REQUIRED_PARTS = ("[Content_Types].xml", "xl/workbook.xml")


@dataclass(frozen=True)
class SourceTable:
    """A table read from disk, as rows of raw cells plus its location."""

    file: str
    table: str
    header: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]

    def records(self) -> Iterator[tuple[int, dict[str, Any]]]:
        """Yield (1-based data row number, {column: cell})."""
        for i, row in enumerate(self.rows, start=2):
            yield i, {h: (row[j] if j < len(row) else None) for j, h in enumerate(self.header)}

    def ref(self, row: int | None = None, column: str | None = None) -> SourceRef:
        return SourceRef(file=self.file, table=self.table, row=row, column=column)


def _clean_header(cells: list[Any]) -> tuple[str, ...]:
    return tuple(" ".join(str(c).replace("\xa0", " ").split()) if c is not None else "" for c in cells)


def read_csv_table(path: Path, delimiter: str = ";", encoding: str = CSV_ENCODING) -> SourceTable:
    """Read a cp1252 CSV, finding the first row that looks like a header."""
    if not path.exists():
        raise SourceNotFoundError(f"source file not found: {path}")
    try:
        text = path.read_bytes().decode(encoding, errors="replace")
    except OSError as exc:
        raise SourceReadError(path, path.stem, exc) from exc
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    header: tuple[str, ...] | None = None
    rows: list[tuple[Any, ...]] = []
    try:
        for cells in reader:
            if header is None:
                if sum(1 for c in cells if str(c).strip()) >= 3:
                    header = _clean_header(cells)
                continue
            if any(str(c).strip() for c in cells):
                rows.append(tuple(cells))
    except csv.Error as exc:
        raise SourceReadError(path, path.stem, exc) from exc
    if header is None:
        raise SourceNotFoundError(f"no header row found in {path}")
    return SourceTable(file=path.name, table=path.stem, header=header, rows=tuple(rows))


def read_xlsx_sheet(path: Path, sheet: str) -> SourceTable:
    """Read one worksheet. Requires openpyxl, which is an ingest-only extra."""
    if not path.exists():
        raise SourceNotFoundError(f"source file not found: {path}")
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError(
            "reading GEOTHOPICA requires openpyxl; install with: pip install '.[ingest]'"
        ) from exc
    from openpyxl.utils.exceptions import InvalidFileException

    try:
        with zipfile.ZipFile(path) as archive:
            missing = [part for part in _XLSX_REQUIRED_PARTS if part not in archive.namelist()]
        if missing:
            raise SourceReadError(path, sheet, f"not an .xlsx workbook: missing {', '.join(missing)}")
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except (InvalidFileException, *_XLSX_READ_ERRORS) as exc:
        raise SourceReadError(path, sheet, exc) from exc
    try:
        if sheet not in wb.sheetnames:
            raise SourceNotFoundError(f"{path.name} has no sheet {sheet!r} (has: {wb.sheetnames})")
        # Read-only mode parses the sheet XML lazily, so parse errors surface
        # while iterating; materialize the rows inside the guard.
        it = wb[sheet].iter_rows(values_only=True)
        first = next(it, None)
        if first is None:
            raise SourceReadError(path, sheet, "sheet has no header row")
        header = _clean_header(list(first))
        rows = tuple(tuple(r) for r in it if r and any(c is not None and str(c).strip() for c in r))
    except SourceNotFoundError:
        raise  # an OSError subclass, but a missing sheet, not an unreadable one
    except _XLSX_READ_ERRORS as exc:
        raise SourceReadError(path, sheet, exc) from exc
    finally:
        wb.close()
    return SourceTable(file=path.name, table=sheet, header=header, rows=rows)


@dataclass(frozen=True)
class StructuredSources:
    """The pilot's source set, resolved against a data directory."""

    data_dir: Path

    def _p(self, name: str) -> Path:
        return self.data_dir / name

    @property
    def available(self) -> dict[str, bool]:
        return {
            GEOTHOPICA_FILE: self._p(GEOTHOPICA_FILE).exists(),
            POZZI_STORICI_FILE: self._p(POZZI_STORICI_FILE).exists(),
            PO_WELLS_FILE: self._p(PO_WELLS_FILE).exists(),
        }

    def geothopica(self, sheet: str) -> SourceTable:
        return read_xlsx_sheet(self._p(GEOTHOPICA_FILE), sheet)

    def pozzi_storici(self) -> SourceTable:
        return read_csv_table(self._p(POZZI_STORICI_FILE), delimiter=";")

    def po_wells(self) -> SourceTable:
        return read_csv_table(self._p(PO_WELLS_FILE), delimiter=",")
