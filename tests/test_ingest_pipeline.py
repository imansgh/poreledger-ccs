"""End-to-end ingestion against a synthetic pilot dataset.

The fixtures below are built in a temp directory rather than read from ``data/``:
the real 11 GB corpus is git-ignored and absent in CI, and a test suite that
depends on it would be unrunnable for anyone else.

The synthetic sources deliberately reproduce the defects reconnaissance found in
the real ones: decimal commas beside decimal points, a feet-labelled depth, a
rotary-table datum, disagreeing depths, alternate well spellings and competing
temperature methods.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ccs_screen.config import REQUIRED_FIELDS, ScreeningConfig
from ccs_screen.ingest import (
    NO_ASSUMPTIONS,
    Assumption,
    AssumptionError,
    AssumptionSet,
    IncompleteWellError,
    Provenance,
    TemperatureMethod,
    WellNormalizer,
    assess,
    build_report,
    build_screening_config,
)

openpyxl = pytest.importorskip("openpyxl", reason="GEOTHOPICA fixtures need openpyxl")


ANAGRAFICA = [
    ("nome", "lat", "lon", "quota", "regione", "provincia", "tipo",
     "proprietario", "datacomp", "profondita", "esito", "scopo"),
    # Normal well, decimal point depth.
    ("SALUZZO 1", "451457", "40222.28", "310", "PIEMONTE", "CN", "ESPLORAZIONE",
     "AGIP", "00/11/1957", "1527.5", "STERILE", "IDROCARBURI"),
    # Decimal comma in both elevation and depth.
    ("MALOSSA 15", "452953", "25415.5", "111,00", "LOMBARDIA", "BG", "ESPLORAZIONE",
     "AGIP", "00/04/1979", "5491,0", "PETROLIO", "IDROCARBURI"),
    # Well with temperature but no stratigraphy.
    ("ASTI 1", "445703", "41349.28", "132", "PIEMONTE", "AT", "ESPLORAZIONE",
     "AGIP", "00/10/1958", "1247", "IDROCARBURI GASSOSI", "IDROCARBURI"),
    # Well whose only temperature is a surface air mean.
    ("ASIGLIANO 1", "451457", "40222.28", "125", "PIEMONTE", "VC", "ESPLORAZIONE",
     "AGIP", "00/02/1960", "1706", "STERILE", "IDROCARBURI"),
]

STRATIGRAPHY = [
    ("nome", "nomeunita1", "nomeunita2", "top", "bottom", "litologia", "rango",
     "da eta relativa", "a eta relativa"),
    ("SALUZZO 1", "", "", "0", "176.8", "SABBIE,CIOTTOLI,ARGILLE", "", "QUATERNARIO", ""),
    ("SALUZZO 1", "", "", "176.8", "422.8", "ARGILLE,SABBIE", "", "PLIOCENE", ""),
    ("SALUZZO 1", "", "", "422.8", "1527.5", "CIOTTOLI E SABBIE", "", "MIOCENE", ""),
    ("MALOSSA 15", "", "", "5136", "5491", "CALCARI", "", "GIURASSICO", ""),
    ("ASIGLIANO 1", "", "", "0", "1706", "SABBIE", "", "QUATERNARIO", ""),
]

TEMPERATURES = [
    ("nome", "data", "profondita", "temperatura", "tempo circolazione",
     "tempo stop", "tipo di misura"),
    # SALUZZO: surface air, a shallow modelled point, then two competing
    # methods at the same depth -- the real pattern.
    ("SALUZZO 1", "00/00/0000", "0", "12", "0", "0", "temp.atmosferica media annuale"),
    ("SALUZZO 1", "00/00/0000", "300", "19", "0", "0", "estrap.metodo Squarci-Taffi"),
    ("SALUZZO 1", "00/00/0000", "1522.6", "39", "0", "6", "non stabilizzata"),
    ("SALUZZO 1", "00/00/0000", "1522.6", "45", "0", "0", "estrap.metodo Squarci-Taffi"),
    # MALOSSA: Fertl-Wichmann outranks the unstabilized reading.
    ("MALOSSA 15", "00/00/0000", "5387", "125", "0", "13", "non stabilizzata"),
    ("MALOSSA 15", "00/00/0000", "5387", "143", "0", "0", "estrap.metodo Fertl-Wichmann"),
    ("ASTI 1", "00/00/0000", "1244", "45", "0", "0", "estrap.metodo Squarci-Taffi"),
    # ASIGLIANO: surface air only -- not a reservoir temperature.
    ("ASIGLIANO 1", "00/00/0000", "0", "13", "0", "0", "temp.atmosferica media annuale"),
]

#: Alternate spellings plus a deliberately disagreeing depth for SALUZZO.
POZZI_STORICI = """Codice;Nome pozzo;Anno;Scopo;Esito;Prof;Tipo titolo;Operatore
1547;SALUZZO 001;1957;E;ST;1531;P;AGIP MINERARIA
3784;MALOSSA 015;1979;E;OL;5497;P;AGIP SPA
9001;S.BENIGNO CANAVESE 001;1961;E;ST;2696;P;AGIP
"""

PO_WELLS = """Codice,Well_name,Anno,Scopo,Esito,Depth_m,Operatore,Province,Lat_WGS84_approx,Lon_WGS84_approx,Pdf
1547,SALUZZO 001,1957,E,ST,1527.5,AGIP,CN,44.66811,7.90878,Yes
"""


def _write_xlsx(path: Path) -> None:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for sheet, rows in (("Anagrafica", ANAGRAFICA),
                        ("Lito-Stratigrafie", STRATIGRAPHY),
                        ("Temperature", TEMPERATURES)):
        ws = wb.create_sheet(sheet)
        for row in rows:
            ws.append(list(row))
    wb.save(path)


@pytest.fixture(scope="module")
def pilot_dir(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("pilot_data")
    _write_xlsx(d / "Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx")
    (d / "pozzi-storici.csv").write_bytes(POZZI_STORICI.encode("cp1252"))
    (d / "po_wells_clean.csv").write_bytes(PO_WELLS.encode("cp1252"))
    return d


@pytest.fixture(scope="module")
def records(pilot_dir):
    return {r.canonical_id: r for r in WellNormalizer(pilot_dir).run()}


@pytest.fixture(scope="module")
def full_assumptions() -> AssumptionSet:
    common = dict(author="Test Engineer", rationale="pilot placeholder", date="2026-09-19")
    return AssumptionSet(
        name="test-pilot",
        assumptions=(
            Assumption(parameter="area_m2", value=(5e7, 1.5e8), **common),
            Assumption(parameter="thickness_m", value=(25.0, 55.0), **common),
            Assumption(parameter="porosity", value=(0.12, 0.24), **common),
            Assumption(parameter="pressure_pa", value=(12e6, 20e6), **common),
            Assumption(parameter="storage_efficiency", value=(0.02, 0.07), **common),
        ),
    )


# -- normal well -----------------------------------------------------------


def test_normal_well_is_normalized(records):
    rec = records["SALUZZO|1"]
    assert rec.depth_m.value == pytest.approx(1527.5)
    assert rec.depth_m.provenance is Provenance.EXTRACTED
    assert rec.temperature_k.provenance is Provenance.DERIVED
    assert rec.gross_thickness_m.provenance is Provenance.DERIVED


def test_raw_records_stay_traceable(records):
    rec = records["SALUZZO|1"]
    assert rec.raw_records
    depth_raws = [r for r in rec.raw_records if r.field_name == "depth_m"]
    assert depth_raws
    raw = depth_raws[0]
    assert raw.original_value  # verbatim source text kept
    assert raw.source.file
    assert raw.source.row is not None
    assert raw.original_name in ("SALUZZO 1", "SALUZZO 001")


def test_alternate_spellings_merge_into_one_record(records):
    """GEOTHOPICA says SALUZZO 1, the registry says SALUZZO 001."""
    rec = records["SALUZZO|1"]
    names = {r.original_name for r in rec.raw_records}
    assert {"SALUZZO 1", "SALUZZO 001"} <= names
    assert "SALUZZO|1" in records and "SALUZZO|001" not in records


def test_coordinates_are_normalized(records):
    rec = records["SALUZZO|1"]
    assert rec.latitude_deg.value == pytest.approx(44.66811)
    assert rec.longitude_deg.value == pytest.approx(7.90878)


# -- decimal separators / units --------------------------------------------


def test_decimal_comma_depth_is_parsed(records):
    """MALOSSA depth is written 5491,0 and elevation 111,00."""
    rec = records["MALOSSA|15"]
    assert rec.depth_m.value == pytest.approx(5491.0)
    assert rec.surface_elevation_m.value == pytest.approx(111.0)


def test_decimal_point_depth_is_parsed(records):
    assert records["SALUZZO|1"].depth_m.value == pytest.approx(1527.5)


# -- datum -----------------------------------------------------------------


def test_depth_without_a_stated_datum_is_not_reported_as_sub_sea(records):
    """No source states a datum, so no MSL depth may be claimed."""
    rec = records["SALUZZO|1"]
    assert not rec.depth_msl_m.is_present
    assert "datum" in rec.depth_msl_m.notes[0]


# -- conflicts -------------------------------------------------------------


def test_conflicting_depths_are_recorded_not_silently_resolved(records):
    """GEOTHOPICA 1527.5 vs registry 1531 for the same well."""
    rec = records["SALUZZO|1"]
    depth_conflicts = [c for c in rec.conflicts if c.field_name == "depth_m"]
    assert depth_conflicts, "the 3.5 m disagreement must be recorded"
    conflict = depth_conflicts[0]
    assert conflict.chosen == pytest.approx(1527.5)
    assert any(v == pytest.approx(1531.0) for v, _ in conflict.alternatives)


def test_agreeing_depths_produce_no_conflict(records):
    """po_wells repeats 1527.5, which must not be logged as a disagreement."""
    rec = records["SALUZZO|1"]
    assert len([c for c in rec.conflicts if c.field_name == "depth_m"]) == 1


# -- temperature provenance -------------------------------------------------


def test_temperature_method_is_preserved(records):
    rec = records["SALUZZO|1"]
    assert rec.temperature_k.method == TemperatureMethod.SQUARCI_TAFFI.value
    assert "45" in (rec.temperature_k.derivation or "")


def test_competing_temperature_methods_are_recorded(records):
    """39 degC unstabilized vs 45 degC extrapolated at the same depth."""
    rec = records["SALUZZO|1"]
    conflicts = [c for c in rec.conflicts if c.field_name == "temperature_k"]
    assert conflicts
    assert conflicts[0].chosen == pytest.approx(318.15)
    assert any(v == pytest.approx(312.15) for v, _ in conflicts[0].alternatives)


def test_better_ranked_method_wins(records):
    """Fertl-Wichmann outranks a non-stabilized reading at the same depth."""
    rec = records["MALOSSA|15"]
    assert rec.temperature_k.method == TemperatureMethod.FERTL_WICHMANN.value
    assert rec.temperature_k.value == pytest.approx(143 + 273.15)


def test_surface_air_temperature_is_never_a_reservoir_temperature(records):
    """ASIGLIANO has only an annual air mean; that is not a reservoir value."""
    rec = records["ASIGLIANO|1"]
    assert not rec.temperature_k.is_present
    assert "surface air" in rec.temperature_k.notes[0]


def test_shallow_modelled_points_are_not_selected(records):
    """The 300 m grid point must not be preferred over the TD reading."""
    rec = records["SALUZZO|1"]
    assert rec.temperature_k.value == pytest.approx(318.15)


def test_all_temperature_observations_are_retained(records):
    assert len(records["SALUZZO|1"].temperatures) == 4


# -- thickness --------------------------------------------------------------


def test_gross_thickness_is_the_deepest_interval(records):
    """Miocene 422.8-1527.5 = 1104.7 m."""
    rec = records["SALUZZO|1"]
    assert rec.gross_thickness_m.value == pytest.approx(1104.7)
    assert "GROSS" in " ".join(rec.gross_thickness_m.notes)


def test_net_storage_thickness_is_never_fabricated(records):
    """Gross is 1104.7 m; the engine wants tens of metres. No conversion exists."""
    rec = records["SALUZZO|1"]
    assert not rec.net_storage_thickness_m.is_present
    assert "net-to-gross" in rec.net_storage_thickness_m.notes[0]


def test_aquifer_thickness_is_distinct_and_missing(records):
    rec = records["SALUZZO|1"]
    assert not rec.aquifer_thickness_m.is_present
    assert rec.aquifer_thickness_m is not rec.net_storage_thickness_m


# -- fields with no source --------------------------------------------------


@pytest.mark.parametrize("field_name", ["porosity", "pressure_pa", "area_m2", "storage_efficiency"])
def test_unavailable_fields_are_reported_missing_with_a_reason(records, field_name):
    fv = getattr(records["SALUZZO|1"], field_name)
    assert not fv.is_present
    assert fv.provenance is Provenance.MISSING
    assert fv.notes and fv.notes[0]


def test_ingestion_populates_no_assumptions_by_default(records):
    for rec in records.values():
        for fv in rec.field_values().values():
            assert fv.provenance is not Provenance.ASSUMED


# -- completeness -----------------------------------------------------------


def test_incomplete_well_is_reported_with_reasons(records):
    status = assess(records["SALUZZO|1"], NO_ASSUMPTIONS)
    assert status.screening_config_buildable is False
    assert set(status.missing_required) == {
        "area_m2", "thickness_m", "porosity", "pressure_pa", "storage_efficiency"
    }
    rendered = status.render()
    assert "SALUZZO|1" in rendered
    assert "screening_config_buildable = false" in rendered


def test_report_counts_missing_fields(records):
    report = build_report(records.values(), NO_ASSUMPTIONS, sources=("test",))
    assert len(report.wells) == len(records)
    assert report.buildable == ()
    counts = report.missing_field_counts()
    assert counts["area_m2"] == len(records)
    assert counts["temperature_k"] == 1  # ASIGLIANO only
    assert "wells normalized" in report.render_summary()


# -- ScreeningConfig gate ---------------------------------------------------


def test_incomplete_well_cannot_build_a_config(records):
    with pytest.raises(IncompleteWellError) as excinfo:
        build_screening_config(records["SALUZZO|1"], NO_ASSUMPTIONS)
    assert "area_m2" in str(excinfo.value)
    assert set(excinfo.value.missing) >= {"area_m2", "porosity", "pressure_pa"}


def test_complete_record_builds_after_explicit_assumptions(records, full_assumptions):
    config = build_screening_config(records["SALUZZO|1"], full_assumptions)
    assert isinstance(config, ScreeningConfig)
    assert config.well_id == "SALUZZO|1"
    assert config.porosity == (0.12, 0.24)
    assert config.depth_m == pytest.approx(1527.5)


def test_derived_temperature_survives_into_the_config(records, full_assumptions):
    """An assumption fills holes; it never overwrites a derived measurement."""
    config = build_screening_config(records["SALUZZO|1"], full_assumptions)
    assert config.temperature_k == (318.15, 318.15)


def test_assumption_cannot_overwrite_extracted_data(records, full_assumptions):
    extended = AssumptionSet(
        name="tries-to-overwrite",
        assumptions=full_assumptions.assumptions,
    )
    config = build_screening_config(records["SALUZZO|1"], extended)
    assert config.temperature_k[0] == pytest.approx(318.15)


def test_well_without_temperature_still_cannot_build(records, full_assumptions):
    """ASIGLIANO has no reservoir temperature, and temperature is not assumable."""
    with pytest.raises(IncompleteWellError) as excinfo:
        build_screening_config(records["ASIGLIANO|1"], full_assumptions)
    assert "temperature_k" in str(excinfo.value)


def test_config_from_pipeline_runs_through_the_engine(records, full_assumptions):
    """The whole point: a built config must actually drive the screening engine."""
    from ccs_screen.monte_carlo import UniformPriors, run_capacity_mc

    config = build_screening_config(records["SALUZZO|1"], full_assumptions)
    result = run_capacity_mc(UniformPriors(**config.prior_ranges()).sample(200, seed=1))
    assert result.p10_mt < result.p50_mt < result.p90_mt


def test_every_required_field_is_accounted_for(records, full_assumptions):
    status = assess(records["SALUZZO|1"], full_assumptions)
    covered = {s.name for s in status.statuses}
    assert set(REQUIRED_FIELDS) <= covered
