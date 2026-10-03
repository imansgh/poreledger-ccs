"""Write a small, deterministic synthetic dataset for the frontend integration suite.

    python scripts/make_integration_fixture.py OUT_DIR

The real ``data/`` directory is git-ignored and absent in CI. This writes the
three structured sources the normalizer reads (GEOTHOPICA workbook, registry
CSVs) with just the wells ``frontend/tests/integration.test.ts`` exercises:

* ``SALUZZO 1`` -- total depth, stratigraphy and competing temperature methods
  near total depth, so the legacy path has a source-derived temperature;
* ``CRESCENTINO 1`` -- a total depth but no temperature at all, so a legacy
  screen is blocked on ``temperature_k``.

Like the real sources, no depth datum is stated, so on the approved model both
wells' depth reference is not established and results are ``UNAVAILABLE``.
The values are synthetic; nothing here is a measurement. Requires openpyxl.
"""

from __future__ import annotations

import sys
from pathlib import Path

ANAGRAFICA = [
    ("nome", "lat", "lon", "quota", "regione", "provincia", "tipo",
     "proprietario", "datacomp", "profondita", "esito", "scopo"),
    ("SALUZZO 1", "451457", "40222.28", "310", "PIEMONTE", "CN", "ESPLORAZIONE",
     "AGIP", "00/11/1957", "1527.5", "STERILE", "IDROCARBURI"),
    ("CRESCENTINO 1", "451100", "40500.00", "160", "PIEMONTE", "VC", "ESPLORAZIONE",
     "AGIP", "00/05/1962", "2210", "STERILE", "IDROCARBURI"),
]

STRATIGRAPHY = [
    ("nome", "nomeunita1", "nomeunita2", "top", "bottom", "litologia", "rango",
     "da eta relativa", "a eta relativa"),
    ("SALUZZO 1", "", "", "0", "176.8", "SABBIE,CIOTTOLI,ARGILLE", "", "QUATERNARIO", ""),
    ("SALUZZO 1", "", "", "422.8", "1527.5", "CIOTTOLI E SABBIE", "", "MIOCENE", ""),
    ("CRESCENTINO 1", "", "", "0", "2210", "ARGILLE E SABBIE", "", "PLIOCENE", ""),
]

TEMPERATURES = [
    ("nome", "data", "profondita", "temperatura", "tempo circolazione",
     "tempo stop", "tipo di misura"),
    ("SALUZZO 1", "00/00/0000", "0", "12", "0", "0", "temp.atmosferica media annuale"),
    ("SALUZZO 1", "00/00/0000", "1522.6", "39", "0", "6", "non stabilizzata"),
    ("SALUZZO 1", "00/00/0000", "1522.6", "45", "0", "0", "estrap.metodo Squarci-Taffi"),
]

POZZI_STORICI = """Codice;Nome pozzo;Anno;Scopo;Esito;Prof;Tipo titolo;Operatore
1547;SALUZZO 001;1957;E;ST;1527.5;P;AGIP MINERARIA
2001;CRESCENTINO 001;1962;E;ST;2210;P;AGIP
"""

PO_WELLS = """Codice,Well_name,Anno,Scopo,Esito,Depth_m,Operatore,Province,Lat_WGS84_approx,Lon_WGS84_approx,Pdf
1547,SALUZZO 001,1957,E,ST,1527.5,AGIP,CN,44.66811,7.90878,Yes
"""


def write_fixture(out_dir: Path) -> Path:
    import openpyxl

    out_dir.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for sheet, rows in (("Anagrafica", ANAGRAFICA),
                        ("Lito-Stratigrafie", STRATIGRAPHY),
                        ("Temperature", TEMPERATURES)):
        ws = wb.create_sheet(sheet)
        for row in rows:
            ws.append(list(row))
    wb.save(out_dir / "Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx")
    (out_dir / "pozzi-storici.csv").write_bytes(POZZI_STORICI.encode("cp1252"))
    (out_dir / "po_wells_clean.csv").write_bytes(PO_WELLS.encode("cp1252"))
    return out_dir


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: make_integration_fixture.py OUT_DIR", file=sys.stderr)
        return 2
    print(write_fixture(Path(args[0])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
