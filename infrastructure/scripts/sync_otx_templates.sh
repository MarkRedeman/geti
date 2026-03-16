#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OTX_RELEASE_TAG="${OTX_RELEASE_TAG:-2.4.2}"
SRC_DIR="$REPO_ROOT/infrastructure/data/otx-model-templates/src/training_extensions"
DEST_DIR="$REPO_ROOT/infrastructure/data/otx-model-templates/model_templates"

echo "Syncing OTX templates (tag: ${OTX_RELEASE_TAG})"
mkdir -p "$(dirname "$SRC_DIR")" "$DEST_DIR"

if [ ! -d "$SRC_DIR/.git" ]; then
	git clone --branch "$OTX_RELEASE_TAG" --single-branch \
		https://github.com/open-edge-platform/training_extensions.git "$SRC_DIR"
else
	git -C "$SRC_DIR" fetch --tags --prune
	git -C "$SRC_DIR" checkout "$OTX_RELEASE_TAG"
	git -C "$SRC_DIR" pull --ff-only origin "$OTX_RELEASE_TAG"
fi

rm -rf "$DEST_DIR"
mkdir -p "$DEST_DIR"
cp -a "$SRC_DIR/src/otx/tools/templates/." "$DEST_DIR/"

echo "OTX templates synced to: $DEST_DIR"
