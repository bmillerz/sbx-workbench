#!/bin/sh
# Build and push every kit, multi-arch, tagged with its own `version:`.
#   ./publish.sh                  everything, in dependency order
#   ./publish.sh claude-config    just the named kits
# Sets pin their components by digest at build, so components push first.
# Run on the Mac (needs `docker login`); a docker-container builder handles
# multi-platform pushes if the default one refuses:
#   docker buildx create --name kits --driver docker-container --use
set -eu
cd "$(dirname "$0")/kits"
NS=docker.io/bmillerz
KITS=${*:-workbench-laravel-base workbench-wordpress-base claude-config workbench-laravel workbench-wordpress}

for k in $KITS; do
  v=$(sed -n 's/^version: "\(.*\)"$/\1/p' "$k/$k.yaml")
  [ -n "$v" ] || { echo "$k: no version: in $k/$k.yaml" >&2; exit 1; }
  if docker buildx imagetools inspect "$NS/$k:$v" >/dev/null 2>&1; then
    echo "$k:$v already published — bump version: in $k/$k.yaml" >&2
    exit 1
  fi
  echo "==> $NS/$k:$v"
  docker buildx build "$k" -f "$k/$k.yaml" \
    --platform linux/amd64,linux/arm64 \
    -t "$NS/$k:$v" --push
done
