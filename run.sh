#!/usr/bin/env bash
# Start the Outlook-to-PDF Converter web app
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

mkdir -p uploads output

echo "Starting Outlook-to-PDF Converter at http://localhost:5000"
python3 app.py
