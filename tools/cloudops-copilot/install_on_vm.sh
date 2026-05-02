#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/azureuser/cloudops-copilot"
SERVICE_NAME="g4-cloudops-copilot.service"

echo "[1/6] Preparing app directory"
mkdir -p "${APP_DIR}"

echo "[2/6] Creating virtual environment"
python3 -m venv "${APP_DIR}/.venv"
source "${APP_DIR}/.venv/bin/activate"

echo "[3/6] Installing dependencies"
pip install --upgrade pip
pip install -r "${APP_DIR}/requirements.txt"

echo "[4/6] Installing systemd unit"
sudo cp "${APP_DIR}/systemd/${SERVICE_NAME}" "/etc/systemd/system/${SERVICE_NAME}"

echo "[5/6] Reloading systemd"
sudo systemctl daemon-reload

echo "[6/6] Enabling and starting service"
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"
sudo systemctl status "${SERVICE_NAME}" --no-pager || true
