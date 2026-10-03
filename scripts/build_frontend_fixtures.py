"""Regenerate frontend/tests/assessment-fixtures.json from the real backend.

    python scripts/build_frontend_fixtures.py

The frontend tests render these responses, so they must be exactly what the
backend returns; tests/test_frontend_fixtures.py fails if they drift.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ccs_screen import assessment as A  # noqa: E402

TARGET = ROOT / "frontend" / "tests" / "assessment-fixtures.json"


def build() -> dict:
    examples = A.examples_document()
    user = json.loads(json.dumps(examples["assessments"][0]))
    user.update(id="MY-SITE-1", name="My site")
    for key in ("example", "synthetic", "notes", "stratigraphy"):
        user.pop(key)
    for key in ("storage_area", "storage_interval", "depth_reference", "surface_elevation",
                "total_depth"):
        user[key].pop("source")
    for obs in user["temperature_observations"]:
        obs["source"] = "my well report"
    user_doc = {"schema_version": A.SCHEMA_VERSION, "assessments": [user]}
    unavailable = json.loads(json.dumps(user_doc))
    unavailable["assessments"][0]["depth_reference"]["datum"] = "unknown"
    two_reasons = json.loads(json.dumps(user_doc))
    for key in ("total_depth", "surface_elevation"):
        two_reasons["assessments"][0].pop(key)
    md = json.loads(json.dumps(user_doc))
    md["assessments"][0]["depth_reference"]["convention"] = "MD"
    invalid = json.loads(json.dumps(user_doc))
    invalid["assessments"][0]["storage_area"]["value"] = -1
    invalid["assessments"][0]["storage_interval"]["top"] = 1600
    _, invalid_problems = A.validate_document(invalid)
    csv_text = A.data_file("synthetic-examples.csv")
    bad_csv = csv_text.replace("SYNTH BETA|1,20,km2,1400,1500", "SYNTH BETA|1,20,km2,1600,1500")
    assert bad_csv != csv_text
    # ALPHA's second observation row says 999 km2, the others 20 km2: a parser conflict.
    lines = csv_text.splitlines(keepends=True)
    alpha = [i for i, line in enumerate(lines) if line.startswith("1,SYNTH ALPHA|1,20,")]
    lines[alpha[1]] = lines[alpha[1]].replace("1,SYNTH ALPHA|1,20,", "1,SYNTH ALPHA|1,999,", 1)
    conflicting_csv = "".join(lines)
    return {
        "examples": examples,
        "user_document": user_doc,
        "user_result": A.evaluate_document(user_doc, samples=200, seed=42),
        "unavailable_result": A.evaluate_document(unavailable, samples=200, seed=42),
        "two_reasons_result": A.evaluate_document(two_reasons, samples=200, seed=42),
        "md_result": A.evaluate_document(md, samples=200, seed=42),
        # The complete example and the outside-envelope example.
        "example_results": A.evaluate_document(
            {**examples, "assessments": [examples["assessments"][0], examples["assessments"][2]]},
            samples=200, seed=42),
        "invalid_problems": invalid_problems,
        "csv_parse": A.parse_upload("csv", csv_text),
        "bad_csv_parse": A.parse_upload("csv", bad_csv),
        "blocked_csv_parse": A.parse_upload("csv", conflicting_csv),
    }


if __name__ == "__main__":
    TARGET.write_text(json.dumps(build(), indent=1, allow_nan=False) + "\n", encoding="utf-8")
    print(TARGET)
