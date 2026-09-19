"""Allow `python -m ccs_screen` to run the same CLI as the `ccs-screen` script."""

from ccs_screen.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
