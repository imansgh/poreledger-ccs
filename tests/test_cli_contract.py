"""End-to-end CLI contract for the things only a real subprocess can prove:
the ``python -m ccs_screen`` packaging entry point, process exit codes, and the
stdout/stderr split that the README's ``ccs-screen --json | jq`` usage needs.

Each test here costs a full interpreter start plus numpy/scipy import, so the
exhaustive error-message matrix lives in ``test_cli.py`` (in-process) instead.
Representative cases are kept here to pin the real process behaviour.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the CLI in a child process with src/ importable.

    The parent environment is inherited (rather than replaced) so this behaves
    the same on CI runners, where wiping PATH/SYSTEMROOT can break interpreter
    start-up. PYTHONPATH still pins the import to this working tree.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    return subprocess.run(
        [sys.executable, "-m", "ccs_screen", *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(SRC.parent),
    )


def test_module_execution_entry_point_works():
    """`python -m ccs_screen` requires a __main__.py in the package."""
    result = run_cli("--samples", "50")
    assert result.returncode == 0, result.stderr
    assert "CCS screening run" in result.stdout
    assert result.stderr == ""


def test_json_mode_emits_only_valid_json_on_stdout():
    """Nothing may pollute stdout in --json mode, or piping to jq breaks."""
    result = run_cli("--samples", "50", "--json")
    assert result.returncode == 0
    assert result.stderr == ""
    report = json.loads(result.stdout)  # raises if stdout is not pure JSON
    assert report["n_samples"] == 50


def test_help_exits_zero():
    result = run_cli("--help")
    assert result.returncode == 0
    assert "ccs-screen" in result.stdout


def test_semantic_error_exits_2_with_stderr_only():
    result = run_cli("--porosity", "0.4", "0.1")
    assert result.returncode == 2
    assert result.stdout == "", "errors must not write to stdout"
    assert result.stderr.startswith("ccs-screen:")


def test_argparse_error_exits_2_with_usage_on_stderr():
    result = run_cli("--nope")
    assert result.returncode == 2
    assert result.stdout == ""
    assert "usage:" in result.stderr
