#!/usr/bin/env bash
set -euo pipefail

DEFAULT_TARGET="/Volumes/Storage/kkupl/glinet-file-mcp/мама анализы"

usage() {
  cat <<'USAGE'
Usage:
  run-pdf-analysis-images.sh --mama-analizy
  run-pdf-analysis-images.sh /path/to/folder-or-file [...]

Copies the canonical ensure-pdf-images.sh script to a local temporary directory,
then runs it for each requested folder. File targets are resolved to their
parent directories so outputs are created beside the original files.

Environment:
  PDF_ANALYSIS_IMAGES_SOURCE  Override source ensure-pdf-images.sh path.
USAGE
}

candidate_sources() {
  if [ -n "${PDF_ANALYSIS_IMAGES_SOURCE:-}" ]; then
    printf '%s\n' "$PDF_ANALYSIS_IMAGES_SOURCE"
  fi

  printf '%s\n' \
    "/Users/kupl/dev/glinet-file-mcp/ensure-pdf-images.sh" \
    "/Volumes/Storage/kkupl/glinet-file-mcp/ensure-pdf-images.sh" \
    "/Users/kupl/Documents/Codex/2026-05-28/new-chat/ensure-pdf-images.sh"
}

find_source_script() {
  local source

  while IFS= read -r source; do
    if [ -f "$source" ] && [ -r "$source" ]; then
      printf '%s\n' "$source"
      return 0
    fi
  done < <(candidate_sources)

  echo "Error: could not find ensure-pdf-images.sh in known locations." >&2
  echo "Set PDF_ANALYSIS_IMAGES_SOURCE=/path/to/ensure-pdf-images.sh if needed." >&2
  return 1
}

append_unique_root() {
  local root="$1"
  local existing

  if [ "${#roots[@]}" -gt 0 ]; then
    for existing in "${roots[@]}"; do
      if [ "$existing" = "$root" ]; then
        return 0
      fi
    done
  fi

  roots+=("$root")
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  usage
  exit 0
fi

args=("$@")
if [ "${#args[@]}" -eq 0 ]; then
  args=("--mama-analizy")
fi

roots=()
for target in "${args[@]}"; do
  case "$target" in
    --mama-analizy|--mama-analysis)
      target="$DEFAULT_TARGET"
      ;;
  esac

  if [ -d "$target" ]; then
    append_unique_root "$target"
    continue
  fi

  if [ -f "$target" ]; then
    append_unique_root "$(dirname "$target")"
    continue
  fi

  echo "Error: target not found: $target" >&2
  exit 1
done

source_script="$(find_source_script)"
workdir="$(mktemp -d "${TMPDIR:-/tmp}/pdf-analysis-images.XXXXXX")"
trap 'rm -rf "$workdir"' EXIT

local_script="$workdir/ensure-pdf-images.sh"
cp "$source_script" "$local_script"
chmod +x "$local_script"

echo "Using source script: $source_script"
echo "Running local copy: $local_script"

for root in "${roots[@]}"; do
  echo "Processing: $root"
  "$local_script" "$root"
done
