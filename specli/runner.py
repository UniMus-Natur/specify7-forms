"""Load and run legacy scripts from specify7-forms/scripts/."""

from __future__ import annotations

import importlib.util
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"


@contextmanager
def _patched_argv(argv: list[str]) -> Iterator[None]:
    old = sys.argv[:]
    sys.argv = argv
    try:
        yield
    finally:
        sys.argv = old


def _ensure_scripts_path() -> None:
    scripts = str(SCRIPTS_DIR)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)


def run_script(script_stem: str, argv_tail: list[str]) -> None:
    """Run scripts/<script_stem>.py main() with patched sys.argv."""
    _ensure_scripts_path()
    script_path = SCRIPTS_DIR / f"{script_stem}.py"
    if not script_path.exists():
        raise SystemExit(f"Script not found: {script_path}")

    module_name = f"specli_scripts.{script_stem}"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Unable to load {script_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "main"):
        raise SystemExit(f"{script_path} does not expose main()")
    with _patched_argv([script_stem, *argv_tail]):
        mod.main()


def load_repo_dotenv() -> None:
    _ensure_scripts_path()
    from _specify_client import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
