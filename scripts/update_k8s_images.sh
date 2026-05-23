#!/usr/bin/env bash
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 <registry-prefix>"
  echo "Example: $0 ghcr.io/your-org"
  exit 1
fi

REGISTRY="$1"

for f in k8s/*.yaml; do
  echo "Updating images in $f"
  sed -i.bak -E "s|REGISTRY_PLACEHOLDER/|$REGISTRY/|g" "$f"
done

echo "Images updated. Backup files with .bak created for safety."
