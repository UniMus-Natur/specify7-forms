#!/usr/bin/env python3
"""Backward-compatible wrapper — prefer: specli schema …"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from specli.main import main

if __name__ == "__main__":
    raise SystemExit(main(["schema", *sys.argv[1:]]))
