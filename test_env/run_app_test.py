#!/usr/bin/env python3
"""Interactive full-app test launcher for StratOS Maneki Neko (PyQt6).

Defaults to `--dry-run` so you can safely test every Setup action, Stratum fetch,
and Package installation with live output in the embedded TerminalDrawer without
modifying your system. Pass `--live` if you want to test real command execution.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.main import main

if __name__ == "__main__":
    argv = list(sys.argv[1:])
    if "--live" in argv:
        argv.remove("--live")
    elif "--dry-run" not in argv:
        argv.append("--dry-run")
    raise SystemExit(main(argv))

