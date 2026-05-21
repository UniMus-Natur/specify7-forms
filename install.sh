#!/usr/bin/env bash
# Bootstrap venv and install specli on PATH (editable).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found" >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  echo "Creating .venv …"
  python3 -m venv .venv
fi

PY="$ROOT/.venv/bin/python"
PIP="$ROOT/.venv/bin/pip"

# Repair venvs where pip is missing or ancient (common after failed installs).
"$PY" -m ensurepip --upgrade 2>/dev/null || true
"$PY" -m pip install --upgrade pip setuptools wheel

echo "Installing specli (editable) …"
"$PIP" install -e .

echo ""
echo "Done. Activate and verify:"
echo "  source .venv/bin/activate"
echo "  specli --version"
echo ""
echo "Without activate, use: $ROOT/bin/specli"
