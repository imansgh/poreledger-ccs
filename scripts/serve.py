"""Start the HTTP API with an explicit dataset choice.

    python scripts/serve.py --no-dataset           # user assessments only
    python scripts/serve.py --demo                 # plus the fictional demo wells (demo/data)
    python scripts/serve.py --data-dir data        # plus real structured sources

User assessments (the primary workflow) need no dataset. The optional existing
well dataset must be named explicitly: there is no default, so a missing real
dataset can never be silently replaced by the synthetic demo. Works from a clone without
installing the package (``src/`` is put on the path); needs ``.[web]``
dependencies (fastapi, uvicorn), plus ``openpyxl`` for real data.

Other settings come from the environment as usual (``CCS_CORS_ORIGINS``,
``CCS_MAX_BODY_BYTES``, ``CCS_WARM_CACHE``, ``CCS_DOCS``); ``--cors-origin``
is a shortcut for local development. See docs/deployment.md.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "demo" / "data"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--no-dataset", action="store_true",
                        help="no existing well dataset; user assessments only")
    source.add_argument("--demo", action="store_true",
                        help="serve the bundled SYNTHETIC demo dataset (demo/data)")
    source.add_argument("--data-dir", help="serve a real data directory")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--cors-origin", action="append", default=[],
                        help="allowed browser origin (repeatable), e.g. http://localhost:3000")
    parser.add_argument("--reload", action="store_true", help="auto-reload on code changes")
    args = parser.parse_args(argv)

    if args.no_dataset:
        data_dir = None
        os.environ["CCS_DATA_DIR"] = ""
    else:
        data_dir = DEMO_DIR if args.demo else Path(args.data_dir).resolve()
        if not data_dir.is_dir():
            parser.error(f"data directory not found: {data_dir}")
        os.environ["CCS_DATA_DIR"] = str(data_dir)
    if args.cors_origin:
        os.environ["CCS_CORS_ORIGINS"] = ",".join(args.cors_origin)

    sys.path.insert(0, str(ROOT / "src"))
    os.environ["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT / "src"), *filter(None, [os.environ.get("PYTHONPATH")])])
    try:
        import uvicorn
    except ImportError:
        print("uvicorn is not installed; run: python -m pip install -e \".[web]\"",
              file=sys.stderr)
        return 2

    label = ("no existing well dataset (user assessments only)" if data_dir is None
             else f"SYNTHETIC demo dataset: {data_dir}" if args.demo
             else f"real data directory: {data_dir}")
    print(f"Serving {label}", file=sys.stderr)
    uvicorn.run("ccs_screen.web.app:app", host=args.host, port=args.port, reload=args.reload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
