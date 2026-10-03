"""Walk through the synthetic demo dataset without starting a server.

    python scripts/run_public_demo.py

Runs the four example requests in ``demo/requests`` against the fictional wells
in ``demo/data`` through the same Python API the HTTP service uses, and prints
each named water-level scenario's validation status. Needs only the core
dependencies (numpy, scipy); no openpyxl, no web stack, no local datasets.

Everything printed is computed from SYNTHETIC inputs. It shows how the software
behaves; it is not a capacity estimate for any real site.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ccs_screen import api  # noqa: E402

DEMO_DIR = ROOT / "demo" / "data"
REQUESTS = ROOT / "demo" / "requests"

#: (request file, well, what it demonstrates)
EXAMPLES = (
    ("approved-validated.json", "SYNTH ALPHA|1",
     "established ground-level datum, eligible temperature -> VALIDATED"),
    ("approved-unavailable.json", "SYNTH BETA|1",
     "no depth datum stated -> UNAVAILABLE (as for every current real well)"),
    ("approved-outside-envelope.json", "SYNTH GAMMA|1",
     "deep and hot -> OUTSIDE_VALIDATED_ENVELOPE (diagnostic capacity only)"),
    ("legacy-not-validated.json", "SYNTH ALPHA|1",
     "legacy placeholder scenario -> NOT_VALIDATED"),
)


def _mt(capacity: dict | None) -> str:
    if not capacity:
        return "no capacity"
    return f"P10/P50/P90 = {capacity['p10']:.2f} / {capacity['p50']:.2f} / {capacity['p90']:.2f} Mt"


def main() -> int:
    readiness = api.data_readiness(DEMO_DIR)
    dataset = readiness["dataset"]
    if not readiness["ready"]:
        print(f"demo dataset not ready: {readiness['problems']}", file=sys.stderr)
        return 1
    print(f"Dataset: {dataset['name']} (synthetic: {dataset['synthetic']})")
    print("All wells and values are FICTIONAL. Nothing below describes a real site.\n")

    for filename, well, purpose in EXAMPLES:
        body = json.loads((REQUESTS / filename).read_text(encoding="utf-8"))
        result = api.screen_well(well, user_inputs=body["user_inputs"],
                                 scenario=body["scenario"], data_dir=DEMO_DIR,
                                 samples=body["samples"], seed=body["seed"])
        print(f"{well}  [{filename}]")
        print(f"  {purpose}")
        if result.get("model_path") == "APPROVED_MODEL":
            for scenario in result["water_level_scenarios"]:
                codes = ", ".join(d["code"] for d in scenario["diagnostics"]) or "none"
                print(f"  {scenario['name']:<22} {scenario['validation_status']:<27} "
                      f"{_mt(scenario['capacity_mt'])}  (diagnostics: {codes})")
        else:
            print(f"  legacy path               {result['validation_status']:<27} "
                  f"{_mt(result.get('scenario_based_capacity_mt'))}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
