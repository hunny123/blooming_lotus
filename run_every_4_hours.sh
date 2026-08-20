#!/usr/bin/env bash

set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
INTERVAL_SECONDS=14400

cd "$ROOT_DIR"

trap 'echo "Stopping signal engine scheduler."; exit 0' INT TERM

while true; do
    echo "Starting signal engine session: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    RUN_ONCE=true "$PYTHON_BIN" main.py
    exit_code=$?

    echo "Signal engine session exited with status $exit_code."
    echo "Next session in 4 hours."
    sleep "$INTERVAL_SECONDS"
done