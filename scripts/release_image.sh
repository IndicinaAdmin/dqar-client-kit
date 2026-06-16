#!/usr/bin/env bash
# Build the dqar-client-kit image and package it as an offline tarball for
# client delivery — no registry, no client-side credentials (see RELEASE.md).
#
# Usage:
#   scripts/release_image.sh [version]
#
# If [version] is omitted, it's read from pyproject.toml's [project].version.

set -euo pipefail
cd "$(dirname "$0")/.."

VERSION="${1:-$(grep -m1 '^version' pyproject.toml | sed -E 's/version = "(.*)"/\1/')}"
if [ -z "$VERSION" ]; then
  echo "Could not determine version. Pass it explicitly: scripts/release_image.sh 0.1.0" >&2
  exit 1
fi

CONTRACTS_DIR="../dqar-contracts"
if [ ! -d "$CONTRACTS_DIR" ]; then
  echo "Expected dqar-contracts checked out at $CONTRACTS_DIR (sibling repo) — not found." >&2
  exit 1
fi

IMAGE="dqar-client-kit:${VERSION}"
OUT_DIR="dist"
TARBALL="${OUT_DIR}/dqar-client-kit-${VERSION}.tar.gz"

mkdir -p "$OUT_DIR"

echo "Building ${IMAGE} ..."
DOCKER_BUILDKIT=1 docker build \
  --build-context contracts="$CONTRACTS_DIR" \
  -t "$IMAGE" \
  .

echo "Saving + compressing ${TARBALL} ..."
docker save "$IMAGE" | gzip > "$TARBALL"

echo "Checksumming ..."
shasum -a 256 "$TARBALL" > "${TARBALL}.sha256"

echo
echo "Release artifact ready:"
echo "  ${TARBALL}"
echo "  ${TARBALL}.sha256"
echo
echo "Client quick-start:"
echo "  docker load < $(basename "$TARBALL")"
echo "  cd docker && cp .env.example .env   # set VERSION=${VERSION}"
echo "  docker compose up"
