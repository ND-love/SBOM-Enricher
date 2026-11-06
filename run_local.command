#!/bin/bash
set -euo pipefail

cd -- "$(dirname -- "$0")"

if [[ ! -x .venv/bin/python ]]; then
    if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
        echo "Install Python 3.11 or newer from https://www.python.org/downloads/macos/"
        exit 1
    fi
    python3 -m venv .venv
fi

python=.venv/bin/python
"$python" -m pip install -e .
"$python" -m scripts.import_astra

port=${CERT_CHECKER_PORT:-8000}
echo "Open http://127.0.0.1:$port/sbom in your browser. Press Ctrl+C to stop."
exec "$python" -m uvicorn app.main:app --host 127.0.0.1 --port "$port"
