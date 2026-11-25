#!/bin/bash
# Run the job: start the metering proxy, then Harbor with the codeaf adapter.
# Needs: Harbor 0.24.0 (pip install harbor==0.24.0 aiohttp), Docker, the Terminal-Bench 2.1
# tasks at commit d49e28f checked out at ./terminal-bench-2-1, a codeaf build (README: Reproduce) in $CODEAF_BIN_DIR
# (codeaf-amd64 / codeaf-arm64), and an OpenRouter key in the file $OR_KEY_FILE.
set -euo pipefail
cd "$(dirname "$0")/.."
export EFFORT=high METER_PORT=18788 METER_LOG=$PWD/runs/calls.jsonl PYTHONPATH=$PWD/harness
mkdir -p runs
python3 harness/meter.py > runs/meter.log 2>&1 &
trap 'kill %1' EXIT
harbor run -c configs/job-config.json -a codeaf_agent:CodeafSeniorDev \
  -m deepseek/deepseek-v4.1-flash -e docker | tee runs/harbor.log
python3 scripts/score.py
