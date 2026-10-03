"""The frontend tests render backend responses from a fixture file; it must
be exactly what the backend returns today (frontend/backend agreement)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_frontend_assessment_fixtures_match_the_backend():
    spec = importlib.util.spec_from_file_location(
        "build_frontend_fixtures", ROOT / "scripts" / "build_frontend_fixtures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    stored = json.loads(module.TARGET.read_text(encoding="utf-8"))
    fresh = json.loads(json.dumps(module.build()))
    assert stored == fresh, ("frontend/tests/assessment-fixtures.json is stale; run "
                             "python scripts/build_frontend_fixtures.py")
