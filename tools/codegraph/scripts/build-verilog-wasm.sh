#!/usr/bin/env bash
# Reproducible build of tree-sitter-verilog.wasm from upstream grammar source.
#
# Required tools (assumed on PATH or in node_modules/.bin):
#   - tree-sitter (CLI; installed via `npm install --no-save tree-sitter-cli`)
#   - docker (for `tree-sitter build --wasm --docker` — emcc avoided)
#
# Pin the grammar commit via VERILOG_GRAMMAR_PIN to make the build reproducible.
set -euo pipefail

GRAMMAR_REPO="${VERILOG_GRAMMAR_REPO:-https://github.com/tree-sitter/tree-sitter-verilog}"
GRAMMAR_PIN="${VERILOG_GRAMMAR_PIN:-}"
WORK="$(mktemp -d)"
DEST_DIR="$(cd "$(dirname "$0")/.." && pwd)/src/extraction/wasm"
DEST_FILE="$DEST_DIR/tree-sitter-verilog.wasm"
SHA_FILE="$DEST_DIR/tree-sitter-verilog.wasm.sha256.txt"
TSCMD="${TSCMD:-$(cd "$(dirname "$0")/.." && pwd)/node_modules/.bin/tree-sitter}"

mkdir -p "$DEST_DIR"
git clone --quiet "$GRAMMAR_REPO" "$WORK/src"
cd "$WORK/src"
[ -n "$GRAMMAR_PIN" ] && git checkout --quiet "$GRAMMAR_PIN"
ACTUAL_PIN="$(git rev-parse HEAD)"

# Grammar's own JS deps (e.g. nan, prebuildify) may be needed for generate.
npm install --no-audit --no-fund --silent >/dev/null 2>&1 || true

"$TSCMD" generate >/dev/null
if command -v emcc >/dev/null 2>&1; then
  "$TSCMD" build --wasm --output "$DEST_FILE"
elif command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  "$TSCMD" build --wasm --docker --output "$DEST_FILE"
else
  echo "ERROR: need either emcc or a running docker daemon" >&2
  exit 1
fi

cd - >/dev/null
sha="$(shasum -a 256 "$DEST_FILE" | awk '{print $1}')"
{
  echo "wasm_sha256: $sha"
  echo "grammar_repo: $GRAMMAR_REPO"
  echo "grammar_commit: $ACTUAL_PIN"
  echo "built_at: $(date -u +%FT%TZ)"
} > "$SHA_FILE"
rm -rf "$WORK"
echo "Wrote $DEST_FILE ($(du -h "$DEST_FILE" | awk '{print $1}'))"
echo "Wrote $SHA_FILE"
