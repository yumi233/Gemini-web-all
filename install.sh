#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RUNTIME=${GEMINI_WEB_ALL_RUNTIME:-"$HOME/.local/share/gemini-web-all"}
mkdir -p "$RUNTIME"
chmod 700 "$RUNTIME"
if [ ! -x "$RUNTIME/venv/bin/python" ]; then uv venv "$RUNTIME/venv" --python 3.12; fi
uv pip install --python "$RUNTIME/venv/bin/python" -r "$ROOT/python/requirements.txt"
/Applications/magpie.app/Contents/MacOS/magpie plugin add "$ROOT"
