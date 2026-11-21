#!/usr/bin/env bash
# Run on the Pi from the repo dir: ./install.sh
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"

sudo apt-get update
sudo apt-get install -y python3-venv libportaudio2 alsa-utils ffmpeg

python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install -r "$DIR/requirements.txt"

sed -e "s|__USER__|$USER|g" -e "s|__DIR__|$DIR|g" \
  "$DIR/systemd/noise-trigger.service" | sudo tee /etc/systemd/system/noise-trigger.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable noise-trigger

echo "Installed. Add clips/lay_down.wav, calibrate, then: sudo systemctl start noise-trigger"
