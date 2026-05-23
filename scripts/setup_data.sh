#!/usr/bin/env bash
set -euo pipefail

echo "Setup data from DVC remote"

DEFAULT_LOCAL_REMOTE="./data/dvc"
if [ -z "${DVC_REMOTE_URL:-}" ]; then
  echo "DVC_REMOTE_URL not set — using local test remote: $DEFAULT_LOCAL_REMOTE"
  DVC_REMOTE_URL="$DEFAULT_LOCAL_REMOTE"
fi

if ! command -v dvc >/dev/null 2>&1; then
  echo "dvc not installed. Install it with: pip install 'dvc[s3]'" >&2
  exit 1
fi

# Configure remote (force overwrite) and pull
dvc remote add -f storage "$DVC_REMOTE_URL" || true
dvc pull -r storage || true

echo "Data sync attempted. If you used the default local remote, ensure the folder '$DEFAULT_LOCAL_REMOTE' contains DVC-tracked files or put your CSVs into ./data/ and run 'dvc add'."
