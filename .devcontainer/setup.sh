#!/usr/bin/env bash
# Runs once when the Codespace is created: installs backend and frontend dependencies.
# No credentials are created here.
set -euo pipefail
cd "$(dirname "$0")/.."
python -m venv api/.venv
api/.venv/bin/pip install --quiet --upgrade pip
api/.venv/bin/pip install --quiet -r api/requirements-dev.txt
(cd web && npm ci --no-audit --no-fund)
[ -f api/.env ] || cp .env.example api/.env
echo
echo "Setup finished. Start the site with:  bash .devcontainer/start.sh"
