#!/usr/bin/env sh
set -eu

usage() {
  echo "Usage: sh install.sh codex|claude [destination]"
  echo "  codex  -> install into \${CODEX_HOME:-$HOME/.codex}/skills"
  echo "  claude -> install into \${CLAUDE_HOME:-$HOME/.claude}/skills"
}

if [ "$#" -lt 1 ]; then
  usage
  exit 2
fi

target="$1"
custom_dest="${2:-}"
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

case "$target" in
  codex)
    dest="${custom_dest:-${CODEX_HOME:-$HOME/.codex}/skills}"
    ;;
  claude)
    dest="${custom_dest:-${CLAUDE_HOME:-$HOME/.claude}/skills}"
    ;;
  *)
    usage
    exit 2
    ;;
esac

mkdir -p "$dest"
for skill in benchmark-repo-analyzer benchmark-generator benchmark-validator; do
  rm -rf "$dest/$skill"
  cp -R "$repo_dir/skills/$skill" "$dest/$skill"
done

echo "Installed benchmark skills to $dest"
