"""One-command demo. Equivalent to `ccs-screen --samples 800 --seed 42`.

Kept as a script so the repo runs from a clone without an install step.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ccs_screen.cli import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or ["--samples", "800", "--seed", "42"]))
