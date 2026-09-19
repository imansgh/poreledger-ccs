"""Guards on the packaging metadata itself.

``pyproject.toml`` declares ``readme = "README.md"``, and setuptools reads that
file as strict UTF-8 while building. A single stray byte from a cp1252-encoded
write makes `pip install .` fail outright with a UnicodeDecodeError, which no
other test in this suite would notice -- the source tree still imports fine.
"""

from __future__ import annotations

from pathlib import Path

import pytest

try:  # tomllib is stdlib from 3.11; the backport covers 3.10
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - version dependent
    import tomli as tomllib


def load_pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

ROOT = Path(__file__).resolve().parents[1]

TEXT_FILES = [
    ROOT / "README.md",
    ROOT / "pyproject.toml",
    ROOT / "requirements.txt",
    ROOT / ".gitignore",
    ROOT / ".github" / "workflows" / "ci.yml",
    *sorted((ROOT / "docs").glob("*.md")),
    *sorted((ROOT / "examples").glob("*.json")),
    *sorted((ROOT / "src" / "ccs_screen").rglob("*.py")),
    *sorted((ROOT / "tests").glob("*.py")),
    *sorted((ROOT / "tests" / "fixtures").glob("*.json")),
    *sorted((ROOT / "scripts").glob("*.py")),
]


@pytest.mark.parametrize("path", TEXT_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_text_files_are_valid_utf8(path: Path):
    """Every text file must decode as UTF-8, or the wheel build breaks."""
    try:
        path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AssertionError(
            f"{path.relative_to(ROOT)} is not valid UTF-8: {exc}. "
            "On Windows, Path.write_text() defaults to cp1252 -- pass encoding='utf-8'."
        ) from None


def test_readme_is_pure_ascii():
    """The project writes rho/phi/dP rather than Unicode; keep the README in step.

    This also removes any chance of an encoding mismatch in the packaged
    long-description.
    """
    raw = (ROOT / "README.md").read_bytes()
    offenders = {byte for byte in raw if byte > 127}
    assert not offenders, f"non-ASCII bytes in README.md: {sorted(hex(b) for b in offenders)}"


def test_declared_readme_exists_and_is_readable():
    """Whatever pyproject points at must be loadable the way setuptools loads it."""
    readme = load_pyproject()["project"]["readme"]
    assert (ROOT / readme).read_text(encoding="utf-8").strip()


def test_console_script_target_is_importable():
    import importlib

    module_name, _, func_name = load_pyproject()["project"]["scripts"]["ccs-screen"].partition(":")
    module = importlib.import_module(module_name)
    assert callable(getattr(module, func_name))


def test_every_source_module_is_covered_by_the_packages_find():
    """A module in src/ccs_screen must actually ship; __main__.py was once missing."""
    import ccs_screen

    package_dir = Path(ccs_screen.__file__).parent
    on_disk = {p.name for p in (ROOT / "src" / "ccs_screen").glob("*.py")}
    importable = {p.name for p in package_dir.glob("*.py")}
    assert on_disk == importable


def test_ingest_subpackage_ships_every_module():
    """Subpackages need their own check: packages.find must discover them."""
    import ccs_screen.ingest

    package_dir = Path(ccs_screen.ingest.__file__).parent
    on_disk = {p.name for p in (ROOT / "src" / "ccs_screen" / "ingest").glob("*.py")}
    assert on_disk == {p.name for p in package_dir.glob("*.py")}


def test_both_console_scripts_resolve():
    import importlib

    scripts = load_pyproject()["project"]["scripts"]
    assert {"ccs-screen", "ccs-ingest"} <= set(scripts)
    for target in scripts.values():
        module_name, _, func_name = target.partition(":")
        assert callable(getattr(importlib.import_module(module_name), func_name))


def test_ingest_public_api_is_importable_from_the_package_root():
    """Every name in ccs_screen.ingest.__all__ must actually be reachable.

    A symbol added to a submodule but not re-exported still passes every test
    that imports the submodule directly, and fails only for a real consumer.
    """
    import ccs_screen.ingest as ingest

    missing = [name for name in ingest.__all__ if not hasattr(ingest, name)]
    assert not missing, f"declared in __all__ but not importable: {missing}"


def test_key_scenario_symbols_are_public():
    from ccs_screen.ingest import (  # noqa: F401
        AREA_POLICY_STATEMENT,
        Citation,
        EvidenceClass,
        LITERATURE_SCREENING_V1,
        NET_THICKNESS_POLICY_STATEMENT,
    )
