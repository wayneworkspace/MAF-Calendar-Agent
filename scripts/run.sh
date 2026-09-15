#!/usr/bin/env bash
# Start the bot WITHOUT Docker (creates venv on first run, restarts on crash).
cd "$(dirname "$0")/.."
if [ ! -d .venv ]; then
  echo "[setup] creating virtual environment..."
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -r app/requirements.txt
fi
while true; do
  .venv/bin/python app/main.py
  echo "[bot exited with code $?] restarting in 5s... (Ctrl+C to stop)"
  sleep 5
done
