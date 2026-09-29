#!/usr/bin/env python3
"""Pair Desk entry point: `python desk.py serve`, `python desk.py list --project mygame`, ...

Also the `pair-desk` console script of the Python package (see pyproject.toml), and what
bin/pair-desk and bin/pair-desk.cmd run."""

import os
import sys

# abspath, not resolve(): keep the drive and path the user runs from (a subst drive or a
# symlinked folder stays as it is in the paths the installers write)
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from pair_desk.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
