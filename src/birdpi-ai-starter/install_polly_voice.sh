#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p voices
(cd voices && ../.venv/bin/python -m piper.download_voices en_GB-semaine-medium)
echo "Installed Polly voice. Restart server.py to use it."
