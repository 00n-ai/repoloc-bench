#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 /path/to/state-estimation-traceability" >&2
  exit 1
fi

SOURCE_ROOT="$1"
python3 research/scripts/analyze_benchmark_package.py \
  --project-root "$SOURCE_ROOT" \
  --output-dir experiments/benchmark_package_review_100 \
  --iterations 100 \
  --seed 20260523
