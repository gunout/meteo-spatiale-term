#!/usr/bin/env bash
# Raccourci : ./run.sh [--watch] [--json-only] ...
cd "$(dirname "$0")"
exec python3 spacewatch.py "$@"
