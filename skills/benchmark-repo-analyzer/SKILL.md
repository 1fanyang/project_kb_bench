---
name: benchmark-repo-analyzer
description: Use when preparing source repositories, documentation snapshots, issue exports, or release metadata for retrieval benchmark generation, especially when downstream benchmark cases need a standardized source inventory, entity index, and relation graph.
argument-hint: "<analyzer_request.yaml or source roots> -> <project_context_bundle>"
---

# Benchmark Repo Analyzer

## Boundary

Use this skill to turn target project sources into a reusable `project_context_bundle/`.

Do:
- read a thin `analyzer_request.yaml` or equivalent user-provided source-root list;
- inspect code, docs, scripts, configs, tests, issue exports, and release metadata;
- emit the five standard analyzer artifacts;
- validate the bundle before handing it to benchmark generation.

Do not:
- generate benchmark JSONL cases;
- write `query`, `expected_answer`, or scoring rubrics;
- hardcode project-specific taxonomies into this skill;
- require one orchestration mechanism. Codex, Claude, shell scripts, CI, or manual UI workflows may all connect the steps.

## Required Output

Write a directory containing:

```text
project_manifest.json
source_inventory.jsonl
entity_index.jsonl
relation_graph.jsonl
signal_index.jsonl
analyzer_report.md
```

Read `references/analyzer-contract.md` for field semantics. Read
`references/codegraph_schema.md` for the frozen CodeGraph SQLite
contract the v2 exporter is written against. Read
`references/codegraph-backend.md` for backend selection rationale.

## v2 invocation (canonical as of 2026-06-30)

Two stages: (a) CodeGraph indexes the project into a SQLite DB;
(b) Python exporters read the DB and write the bundle JSONLs +
signals.

```bash
# Stage A — index. CodeGraph requires Node >= 22.5 for node:sqlite;
# on macOS that means /opt/homebrew/opt/node@22/bin/node.
/opt/homebrew/opt/node@22/bin/node \
    tools/codegraph/dist/bin/codegraph.js init \
    repo_sources/<project>

# Stage B1 — export the bundle from the .codegraph/codegraph.db that
# the indexer wrote. --strip-prefix is needed when the indexed root
# nests one level deeper than the actual git checkout (Vortex does;
# NVDLA doesn't).
uv run python skills/benchmark-repo-analyzer/scripts/codegraph_to_bundle.py \
    --db repo_sources/<project>/.codegraph/codegraph.db \
    --project <project> \
    --source-set-id <project>_main \
    --repo-name <project>/<project> \
    --strip-prefix <project> \
    --source-set-local-root repo_sources/<project>/<project> \
    --display-name <Project> \
    --out runs/<project>_context_bundle/ \
    --repo-sources-root /path/to/repo_sources

# Stage B2 — emit signals (axis-2 + axis-3 attribute signals,
# including AST-anchored conditional_behavior from a re-parse pass).
uv run python skills/benchmark-repo-analyzer/scripts/signal_emitter.py \
    --bundle runs/<project>_context_bundle/ \
    --project <project> \
    --repo-sources-root /path/to/repo_sources

# Stage C — validate before handing the bundle to the generator.
uv run --with jsonschema python \
    skills/benchmark-repo-analyzer/scripts/validate_context_bundle.py \
    --repo-root /path/to/checkout \
    runs/<project>_context_bundle/
```

## Architecture notes

- CodeGraph fork pinned at `colbymchenry/codegraph@4077ed1` (v1.1.1).
  Verilog support is a fork-local Verilog language module on branch
  `feat/verilog-language-module` inside `tools/codegraph/`. Tree-sitter
  grammar: tree-sitter-verilog v1.0.3 (commit 521b535), compiled to
  WASM via `scripts/build-verilog-wasm.sh` and bundled at
  `src/extraction/wasm/tree-sitter-verilog.wasm`.
- Verilog modules surface as NodeKind `class` in the CodeGraph DB
  (the LanguageExtractor framework has no `module` slot). The
  exporter remaps `(language='verilog' AND kind='class')` -> entity
  kind `module` for downstream consumers.
- `conditional_behavior` signal anchors come from a Python tree-sitter
  re-parse of Verilog source (`scripts/_verilog_reparse.py`), NOT
  from the CodeGraph index. Re-parse anchors carry
  `extractor: "verilog_tree_sitter_reparse_v2"` and
  `evidence.provenance: "tree_sitter_verilog_reparse_v2"`.

## Troubleshooting

- `"imports_or_includes" target.id empty` — earlier than Phase 2;
  re-run with the pinned fork.
- `"conditional_behavior" anchored in license block (lines 1-10)` —
  earlier than Phase 3; re-run with the v2 signal emitter (re-parse
  path).
- `"line_count must be > 0" from prepare's is_generation_source` —
  exporter needs `--repo-sources-root` pointing at the actual on-disk
  source tree so line counts can be computed from files.
- `node:sqlite missing` — CodeGraph requires Node >= 22.5. Use
  `/opt/homebrew/opt/node@22/bin/node` explicitly on the dev box.
- `"signal_dataflow" warning from prepare` (Phase 4 ignore-and-ship) —
  expected; the new signal_dataflow attribute is tolerated but not
  wired as a selection axis. The count is informational.

## Phase 1.5 / Phase 6 follow-ups (not yet implemented)

- `text_macro_definition` not yet routed in `verilogExtractor` -> v1's
  `kind=macro` row count (~1700 on Vortex) not yet recovered.
- `net_declaration` and `parameter_declaration` lumped into
  `kind=variable` -> v1's `kind=signal` (4113) and `kind=parameter`
  (1594) not yet differentiated.
- 9 hard-error Vortex files (DPI headers, VX_trace_pkg.sv, AFU wrap,
  VX_uop_sequencer.sv, interface files) -> Phase 6 schedules a
  Verible fallback for these.
- `VX_cluster.sv:48-50` anchor reuse (61× in Phase 5 smoke50) -> Phase 6
  also caps anchor-rotation.

## Codex CLI Invocation

Invoke this skill from Codex CLI as a message, not as a shell command:

```text
$benchmark-repo-analyzer
Analyze repo_sources/nvdla/hw, repo_sources/nvdla/sw, and repo_sources/nvdla/doc as project nvdla.
Use CodeGraph for code structure when available.
Write the analyzer bundle to runs/nvdla_context_bundle with project_manifest.json, source_inventory.jsonl, entity_index.jsonl, relation_graph.jsonl, and analyzer_report.md.
Exclude .git, .omx, and prebuilt binaries.
Run the bundle validator before reporting completion.
```

```text
$benchmark-repo-analyzer
Analyze repo_sources/vortex/vortex as project vortex.
Use source role main_code_doc_repo and authority primary_source.
Write the analyzer bundle to runs/vortex_context_bundle.
Exclude .git, .omx, and hw/syn/synopsys/models.
Run the bundle validator before reporting completion.
```

## Validation

Run the deterministic bundle validator:

```bash
python3 skills/benchmark-repo-analyzer/scripts/validate_context_bundle.py \
  project_context_bundle \
  --repo-root .
```

Fix all `FAIL` findings before using the bundle with `benchmark-generator`.
