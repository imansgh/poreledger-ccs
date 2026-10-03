"""A present but unreadable dataset is reported, never a 500.

Before this, a corrupt ``Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx`` made
``/health`` and ``/ready`` answer 500 (``zipfile.BadZipFile`` escaped the
normalizer), and with startup warming enabled the application would not start.

Expected source-reading failures -- corrupt ZIP, malformed workbook XML, an
inaccessible file -- become ``SourceReadError`` at the reader, an
``unreadable`` source status in the normalizer, and ``DatasetNotReadyError``
(HTTP 503) at the API. Programming errors are not translated.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from ccs_screen import api
from ccs_screen.ingest import sources
from ccs_screen.ingest.normalize import WellNormalizer
from ccs_screen.ingest.sources import SourceReadError, read_xlsx_sheet

from test_ingest_pipeline import PO_WELLS, POZZI_STORICI, _write_xlsx

openpyxl = pytest.importorskip("openpyxl")
pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from ccs_screen.web.app import create_app  # noqa: E402
from ccs_screen.web.settings import Settings  # noqa: E402

WORKBOOK = "Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx"
REQUIRED = {"GEOTHOPICA:Anagrafica", "GEOTHOPICA:Temperature", "GEOTHOPICA:Lito-Stratigrafie"}
APPROVED = {"area_m2": 8.0e7, "z_top": 1400.0, "z_base": 1527.0}


@pytest.fixture(autouse=True)
def _fresh_cache():
    api.clear_cache()
    yield
    api.clear_cache()


def _complete(d: Path) -> Path:
    _write_xlsx(d / WORKBOOK)
    (d / "pozzi-storici.csv").write_bytes(POZZI_STORICI.encode("cp1252"))
    (d / "po_wells_clean.csv").write_bytes(PO_WELLS.encode("cp1252"))
    return d


def _rewrite_member(path: Path, member: str, data: bytes) -> None:
    """Replace one part of a valid .xlsx package, keeping the rest intact."""
    original = path.read_bytes()
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(original)) as zin, zipfile.ZipFile(out, "w") as zout:
        for info in zin.infolist():
            zout.writestr(info, data if info.filename == member else zin.read(info.filename))
    path.write_bytes(out.getvalue())


def _client(data_dir: Path, warm: bool) -> TestClient:
    app = create_app(Settings(data_dir=str(data_dir), warm_cache_on_startup=warm))
    return TestClient(app, raise_server_exceptions=False)


def _assert_unusable(client: TestClient, data_dir: Path, reason: str | tuple[str, ...]) -> None:
    """Liveness 200, readiness 503, data endpoints a controlled 503."""
    reasons = (reason,) if isinstance(reason, str) else reason
    health = client.get("/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok" and body["data_ready"] is False
    assert body["wells_loaded"] == 0 and body["data_dir"] == str(data_dir)
    assert body["scenario_default"] == api.DEFAULT_SCENARIO
    assert body["limits"] == api.REQUEST_LIMITS

    ready = client.get("/ready/existing-data")
    assert ready.status_code == 503
    payload = ready.json()
    assert payload["status"] == "not_ready" and payload["wells_loaded"] == 0
    failed = {s["source"]: s for s in payload["sources"] if s["status"] != "loaded"}
    assert set(failed) >= REQUIRED
    for name in REQUIRED:
        assert failed[name]["status"] == "unreadable"
        assert failed[name]["file"] == WORKBOOK
        assert any(expected in failed[name]["detail"] for expected in reasons)
    assert len(payload["problems"]) == 3
    assert all(any(expected in problem for expected in reasons) for problem in payload["problems"])

    for response in (client.get("/wells"),
                     client.get("/wells/SALUZZO|1"),
                     client.post("/wells/SALUZZO|1/screen", json={"user_inputs": APPROVED})):
        assert response.status_code == 503
        error = response.json()
        assert set(error) == {"error", "type", "detail"}
        assert error["type"] == "DatasetNotReadyError"
        assert {s["source"] for s in error["detail"]} == REQUIRED
        assert "Traceback" not in error["error"]


# -- 1, 2. corrupted .xlsx -----------------------------------------------------


@pytest.mark.parametrize("warm", [False, True], ids=["warming-off", "warming-on"])
def test_corrupted_workbook_is_reported_not_a_500(tmp_path, warm):
    (tmp_path / WORKBOOK).write_bytes(b"corrupted workbook")
    # Entering the context runs the lifespan: with warming on, the app must
    # still start and serve these endpoints.
    with _client(tmp_path, warm) as client:
        _assert_unusable(client, tmp_path, "BadZipFile")


def test_failed_load_is_not_cached_and_a_repair_is_picked_up(tmp_path):
    (tmp_path / WORKBOOK).write_bytes(b"corrupted workbook")
    with _client(tmp_path, warm=True) as client:
        assert client.get("/ready/existing-data").status_code == 503
        assert str(tmp_path.resolve()) not in api._CACHE

        _complete(tmp_path)  # repaired on disk; no restart
        ready = client.get("/ready/existing-data")
        assert ready.status_code == 200 and ready.json()["status"] == "ready"
        assert client.get("/wells").status_code == 200


def test_failed_refresh_evicts_previously_cached_records(tmp_path):
    _complete(tmp_path)
    assert api.load_records(tmp_path)
    (tmp_path / WORKBOOK).write_bytes(b"corrupted workbook")
    with pytest.raises(api.DatasetNotReadyError):
        api.load_records(tmp_path, refresh=True)
    assert str(tmp_path.resolve()) not in api._CACHE
    assert api.data_readiness(tmp_path)["ready"] is False


# -- 3. malformed workbook XML ---------------------------------------------------


def test_malformed_workbook_xml_is_unreadable(tmp_path):
    _write_xlsx(tmp_path / WORKBOOK)
    _rewrite_member(tmp_path / WORKBOOK, "xl/workbook.xml", b"<workbook><sheets>")
    with _client(tmp_path, warm=True) as client:
        # openpyxl uses lxml when available, otherwise ElementTree.
        _assert_unusable(client, tmp_path, ("ParseError", "XMLSyntaxError"))


def test_malformed_sheet_xml_is_unreadable(tmp_path):
    """Read-only openpyxl parses sheet XML lazily, while rows are iterated."""
    _write_xlsx(tmp_path / WORKBOOK)
    _rewrite_member(tmp_path / WORKBOOK, "xl/worksheets/sheet1.xml", b"<worksheet><sheetData><row>")
    normalizer = WellNormalizer(tmp_path)
    normalizer.run()
    status = {s.source: s for s in normalizer.source_status}
    assert status["GEOTHOPICA:Anagrafica"].status == "unreadable"
    assert any(reason in status["GEOTHOPICA:Anagrafica"].detail
               for reason in ("ParseError", "XMLSyntaxError"))
    assert api.data_readiness(tmp_path)["ready"] is False


def test_zip_without_workbook_parts_is_unreadable(tmp_path):
    with zipfile.ZipFile(tmp_path / WORKBOOK, "w") as archive:
        archive.writestr("readme.txt", "not a workbook")
    with pytest.raises(SourceReadError, match=r"missing \[Content_Types\].xml, xl/workbook.xml"):
        read_xlsx_sheet(tmp_path / WORKBOOK, "Anagrafica")


# -- 4. inaccessible required source ---------------------------------------------


def test_inaccessible_required_source_is_unreadable(tmp_path, monkeypatch):
    """Injected deterministically rather than via OS permissions."""
    _complete(tmp_path)
    real_zipfile = zipfile.ZipFile

    def deny(path, *args, **kwargs):
        if Path(path).name == WORKBOOK:
            raise PermissionError(13, "Permission denied", str(path))
        return real_zipfile(path, *args, **kwargs)

    monkeypatch.setattr(sources.zipfile, "ZipFile", deny)
    with _client(tmp_path, warm=True) as client:
        _assert_unusable(client, tmp_path, "PermissionError")


def test_source_read_error_keeps_identity_and_cause(tmp_path):
    (tmp_path / WORKBOOK).write_bytes(b"corrupted workbook")
    with pytest.raises(SourceReadError) as excinfo:
        read_xlsx_sheet(tmp_path / WORKBOOK, "Temperature")
    error = excinfo.value
    assert (error.file, error.table) == (WORKBOOK, "Temperature")
    assert error.reason.startswith("BadZipFile")
    assert isinstance(error.__cause__, zipfile.BadZipFile)


# -- 5. valid data ---------------------------------------------------------------


def test_valid_dataset_remains_ready(tmp_path):
    _complete(tmp_path)
    with _client(tmp_path, warm=True) as client:
        ready = client.get("/ready/existing-data")
        assert ready.status_code == 200
        assert {s["status"] for s in ready.json()["sources"]} == {"loaded"}
        assert client.get("/health").json()["data_ready"] is True
        assert client.get("/wells").status_code == 200


# -- 6. optional sources ---------------------------------------------------------


def test_missing_optional_sources_keep_the_dataset_ready(tmp_path):
    _write_xlsx(tmp_path / WORKBOOK)
    with _client(tmp_path, warm=True) as client:
        ready = client.get("/ready/existing-data")
        assert ready.status_code == 200
        optional = {s["source"]: s["status"] for s in ready.json()["sources"] if not s["required"]}
        assert optional == {"pozzi-storici": "missing", "po_wells": "missing"}
        assert client.get("/wells").status_code == 200


def test_unreadable_optional_source_is_reported_but_not_blocking(tmp_path, monkeypatch):
    _complete(tmp_path)
    real_read_bytes = Path.read_bytes

    def deny(self):
        if self.name == "pozzi-storici.csv":
            raise PermissionError(13, "Permission denied", str(self))
        return real_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", deny)
    readiness = api.data_readiness(tmp_path)
    assert readiness["ready"] is True
    status = {s["source"]: s for s in readiness["sources"]}
    assert status["pozzi-storici"]["status"] == "unreadable"
    assert "PermissionError" in status["pozzi-storici"]["detail"]


# -- 7. programming errors stay visible ------------------------------------------


@pytest.mark.parametrize("error", [TypeError("bug"), KeyError("bug"), ValueError("bug")])
def test_reader_does_not_translate_programming_errors(tmp_path, monkeypatch, error):
    _write_xlsx(tmp_path / WORKBOOK)

    def broken(*args, **kwargs):
        raise error

    monkeypatch.setattr(openpyxl, "load_workbook", broken)
    with pytest.raises(type(error)):
        read_xlsx_sheet(tmp_path / WORKBOOK, "Anagrafica")


def test_normalizer_bug_propagates_through_readiness_and_http(tmp_path, monkeypatch):
    _complete(tmp_path)

    def broken(self):
        raise RuntimeError("programming error in a loader")

    monkeypatch.setattr(WellNormalizer, "load_geothopica_anagrafica", broken)
    with pytest.raises(RuntimeError, match="programming error"):
        api.data_readiness(tmp_path)

    app = create_app(Settings(data_dir=str(tmp_path), warm_cache_on_startup=False))
    with TestClient(app, raise_server_exceptions=True) as client:
        with pytest.raises(RuntimeError, match="programming error"):
            client.get("/ready/existing-data")
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/ready/existing-data")
        assert response.status_code == 500
        assert response.json()["type"] == "InternalServerError"
