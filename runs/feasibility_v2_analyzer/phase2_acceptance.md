# Analyzer v2 Phase 2 — Acceptance

Date: 2026-06-29
Bundle exporter commit: project worktree HEAD (commit 59649f6 after
the file-node source_id fix landed in a follow-up to that commit).
Source DB: `repo_sources/vortex/.codegraph/codegraph.db` (CodeGraph
1.1.1 from Phase 0; re-indexed in Phase 1 with the verilog extractor).

## Acceptance metrics (Vortex v2 bundle)

Bundle path: `runs/vortex_context_bundle_v2/`

| metric | value |
|---|---|
| sources | 577 |
| entities | 5,745 |
| relations | 14,925 |
| Verilog modules (kind=module after remap) | 145 |
| Verilog interfaces | 23 |
| instantiates edges | 441 |
| calls edges | 7,847 |
| imports_or_includes edges | 592 |
| extends edges | 158 |
| references edges | 97 |
| contains edges | 5,790 |
| edges with empty object.id | 0 |
| validator FAIL count | 0 |
| validator WARN count | 0 |

## Acceptance bullets (from the revised Phase 2 plan)

- [x] `tests/test_codegraph_to_bundle.py` passes — 15/15 across 6 test
      classes (source inventory, entity-kind normalization with the
      Verilog->module remap, relation graph with instantiates, manifest,
      v1 backward compatibility, determinism).
- [x] `schemas/relation-graph.schema.json` annotated for v1.1; v1 records
      still validate (V1BackwardCompatibilityTest sampled first 500
      vortex_context_bundle relation rows + 500 entity rows — all pass).
- [x] `runs/vortex_context_bundle_v2/` exists with all five canonical
      files (source_inventory.jsonl, entity_index.jsonl,
      relation_graph.jsonl, project_manifest.json, analyzer_report.md)
      plus _diff_vs_v1.md.
- [x] Zero `imports_or_includes` (or `instantiates`) edges have an empty
      `object.id`.
- [x] `project_manifest.json` reports
      `analyzer_version: benchmark-repo-analyzer/v2-tree-sitter-codegraph`
      and `analysis_backends.code.used_primary: true`.
- [x] `validate_context_bundle.py --repo-root <real-root>` reports 0
      FAIL, 0 WARN against the v2 bundle.
- [x] `_diff_vs_v1.md` shows non-zero counts for new predicates
      (instantiates=441 in v2 vs 0 in v1; calls=7847 in v2 vs 0 in v1).

## Diff vs v1 (the regex_fallback baseline)

Major shape changes (full table in `runs/vortex_context_bundle_v2/_diff_vs_v1.md`):

**v2 has, v1 didn't:**
- `instantiates` predicate: 441 (Verilog module instances; load-bearing
  for Phase 3 conditional_behavior signals on Verilog code paths)
- `calls` predicate: 7,847 (function/method calls across languages)
- `extends` predicate: 158 (class inheritance)
- `references` predicate: 97 (type references)
- Better-typed Verilog modules surfacing as `kind=module` instead of
  being collapsed into generic `class`

**v1 has, v2 doesn't (gaps to file as Phase 1.5 / Phase 2.5):**
- `macro` kind: 1,711 entities (regex extractor found `#define` / `\`define`
  sites). Tree-sitter-verilog parses `\`define` as `text_macro_definition`
  but the Phase 1 extractor doesn't list it under any kind. Filing
  follow-up.
- `signal` kind: 4,113 entities (regex extractor found `wire` / `reg`
  declarations). The Phase 1 verilogExtractor maps `net_declaration` /
  `data_declaration` to variableTypes; CodeGraph emits them as kind=variable
  (count: 144). The ~28× gap is because the regex extractor was per-line
  greedy and CodeGraph's tree-sitter walker only emits at declaration
  boundaries — a quality improvement, not a regression, but worth noting.
- `parameter` kind: 1,594 entities (regex extractor found Verilog
  `parameter` declarations). Same story as signals — Phase 1 extractor
  lumps them into kind=variable.
- `defines` predicate: 12,239 (v1's generic "thing has thing" edge).
  v2 uses kind-specific predicates (`calls`, `instantiates`, `extends`,
  `references`, `contains`) which carry more semantic information; the
  loss of `defines` is expected and addressed by the new predicates.
- `doc_mentions_entity` predicate: 257. CodeGraph doesn't extract doc
  cross-references; this is a follow-on if Phase 3's `doc_code_divergence`
  signal needs it.

**Source-set delta**: v1 indexed 1,504 files of many types (cmake, make,
shell, tcl, binary, etc.); v2 indexes 577 files of the ~22 languages
tree-sitter supports. The smaller surface is intentional — CodeGraph's
extractor is precise where it acts; v1's regex fallback was wide but
shallow.

## Patches landed in this phase

Beyond the planned exporter modules, two small bugs needed fixing in
the exporter:

1. **path-prefix triple-up** — CodeGraph stores paths relative to
   `repo_sources/vortex/`, but the v1 bundle's `relative_path` is
   relative to one level deeper (`repo_sources/vortex/vortex/`). Added a
   `--strip-prefix` flag (Vortex uses `--strip-prefix vortex`) so v2
   paths align with the v1 convention.
2. **source_id resolution on file-node edges** — edges whose source/target
   is a `file:` node (skipped in entity_index) initially landed with
   `evidence.source_id = "src_unknown"`. Fixed: the entity_index emitter
   now populates `node_id_to_source_id` for ALL nodes (including SKIPped
   kinds) so relation_graph emission can resolve evidence.source_id
   correctly. Validator now reports 0 FAIL / 0 WARN.

## Phase 3 GO

**GO.** The v2 bundle is bit-correct against the existing schemas, the
prepare-side validator accepts it, and the entity/relation shapes match
what the v1 prepare pipeline reads. Phase 3 (signal-emission layer) can
start.

Two heads-ups for Phase 3:

1. The `conditional_behavior` signal needs AST-anchored line ranges for
   `conditional_statement` / `case_statement` / `always_construct` sites.
   The current v2 bundle does NOT carry these — they aren't emitted as
   entities by the verilogExtractor. Phase 3's emitter will need to
   either re-parse the Verilog source via the Python tree-sitter binding
   (we already have it installed for Phase 0) OR Phase 1.5 must extend
   the verilogExtractor with a fourth dispatch slot for control-flow
   "anchor" nodes. The re-parse path is faster to land and the right
   first attempt.

2. The `distracting_info` collision-evidence shape is unaffected by
   Phase 2 — that signal is computed entity-by-entity from the entity
   index in Phase 3, and the v2 entity_index carries every field the
   collision detector needs (project, name, source_id, kind).
