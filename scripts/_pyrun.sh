#!/usr/bin/env bash
# Cross-platform Python launcher for AI log hooks.
# Prefers the project's own .venv, then tries python3 → python → py -3 on
# PATH, then falls back to common Windows install locations because Git Bash
# launched by some hooks gets a stripped PATH that omits the Python directory.
# Designed to be sourced or called as: bash scripts/_pyrun.sh <script> [args...]
#
# Exits 0 silently if no Python is found — hooks must never block the AI tool.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# On Windows, `python`/`python3`/`py` on PATH can resolve to the Microsoft
# Store "app execution alias" stub, which `command -v` reports as present but
# which does nothing but print an install nag and exit non-zero. Verify a
# candidate actually runs before trusting it.
is_real_python() {
  "$1" --version >/dev/null 2>&1
}

# The project's virtualenv, when usable, is preferred because it contains the
# project's optional dependencies.
PY=""
for cand in "$PROJECT_ROOT/.venv/Scripts/python.exe" "$PROJECT_ROOT/.venv/bin/python"; do
  if [ -x "$cand" ] && is_real_python "$cand"; then PY="$cand"; break; fi
done
if [ -n "$PY" ]; then
  exec "$PY" "$@"
fi

# Codex desktop may provide a bundled Python runtime outside PATH.
shopt -s nullglob 2>/dev/null || true
for cand in /c/Users/*/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe; do
  if [ -x "$cand" ] && is_real_python "$cand"; then PY="$cand"; break; fi
done
shopt -u nullglob 2>/dev/null || true
if [ -n "$PY" ]; then
  exec "$PY" "$@"
fi

if command -v python3 >/dev/null 2>&1 && is_real_python python3; then
  PY=python3
elif command -v python >/dev/null 2>&1 && is_real_python python; then
  PY=python
elif command -v py >/dev/null 2>&1 && is_real_python "py -3"; then
  PY="py -3"
else
  # PATH lookup failed — probe standard Windows install locations.
  PY=""
  shopt -s nullglob 2>/dev/null || true
  for cand in \
    /c/Users/*/AppData/Local/Programs/Python/Python*/python.exe \
    "/c/Program Files/Python"*/python.exe \
    "/c/Program Files (x86)/Python"*/python.exe \
    /c/Python*/python.exe; do
    if [ -x "$cand" ] && is_real_python "$cand"; then PY="$cand"; break; fi
  done
  shopt -u nullglob 2>/dev/null || true
  [ -n "$PY" ] || exit 0
fi

# shellcheck disable=SC2086
exec $PY "$@"
