#!/usr/bin/env bash
# Start the SciHub dev server.
set -euo pipefail
cd "$(dirname "$0")"
exec ./.venv/bin/uvicorn app.main:app --reload --port 8000
