#!/usr/bin/env bash
# One-shot installer for Linux / Raspberry Pi: venv + systemd service that starts on boot.
# Usage:  bash scripts/install-linux.sh
set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="$(whoami)"

[ -f "$DIR/.env" ] || { echo "❌ .env missing (copy .env.example)"; exit 1; }
{ [ -f "$DIR/token.json" ] || [ -f "$DIR/data/token.json" ]; } || { echo "❌ token.json missing (run 'python auth.py' on a machine with a browser, then copy it here)"; exit 1; }

echo "[1/3] python venv + dependencies"
python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install --upgrade pip -q
"$DIR/.venv/bin/pip" install -r "$DIR/app/requirements.txt" -q
mkdir -p "$DIR/logs"

echo "[2/3] systemd service"
sed -e "s|__DIR__|$DIR|g" -e "s|__USER__|$USER_NAME|g" "$DIR/scripts/calendar-bot.service" \
  | sudo tee /etc/systemd/system/calendar-bot.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable calendar-bot
sudo systemctl restart calendar-bot

echo "[3/3] done. Status:"
sudo systemctl --no-pager status calendar-bot | head -5
echo
echo "Logs:    tail -f $DIR/logs/bot.log"
echo "Stop:    sudo systemctl stop calendar-bot"
echo "Update:  git pull / copy files, then: sudo systemctl restart calendar-bot"
