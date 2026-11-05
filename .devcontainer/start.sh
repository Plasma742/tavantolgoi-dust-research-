#!/usr/bin/env bash
# Starts the research site inside this Codespace:
#   backend  -> 127.0.0.1:8000 (internal; never forward it publicly)
#   dashboard-> port 5173 (opened in your browser through Codespaces' PRIVATE port forwarding)
# Earth Engine credentials are stored in this Codespace's home directory, never in git.
set -euo pipefail
cd "$(dirname "$0")/.."
ENV_FILE=api/.env
[ -f "$ENV_FILE" ] || cp .env.example "$ENV_FILE"
[ -x api/.venv/bin/uvicorn ] || bash .devcontainer/setup.sh

project=$(grep -E '^EE_PROJECT_ID=' "$ENV_FILE" | cut -d= -f2- || true)
if [ -z "$project" ]; then
  echo "Earth Engine project ID is not set (the Google Cloud project registered for Earth Engine)."
  echo "Press Enter without typing to start in NOT_CONFIGURED mode (the site runs but shows no data)."
  read -r -p "EE_PROJECT_ID: " project
  if [ -n "$project" ]; then
    if [[ ! "$project" =~ ^[a-z][a-z0-9-]{4,29}$ ]]; then
      echo "That does not look like a Google Cloud project ID (lowercase letters, digits, hyphens)." >&2
      exit 1
    fi
    sed -i "s/^EE_PROJECT_ID=.*/EE_PROJECT_ID=${project}/" "$ENV_FILE"
  fi
fi

if [ -n "$project" ] && [ ! -f "$HOME/.config/earthengine/credentials" ]; then
  echo
  echo "Sign in to Earth Engine: open the link below, sign in with the Google account that owns"
  echo "project '$project', then paste the code back here. Credentials stay inside this Codespace."
  api/.venv/bin/earthengine authenticate --auth_mode=notebook
fi

echo
echo "Starting backend (127.0.0.1:8000) and dashboard (port 5173)..."
(cd api && exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --env-file .env) &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT INT TERM
cd web
echo "Open the 'Dashboard (keep PRIVATE)' entry in the PORTS tab if the browser does not open by itself."
npm run dev
