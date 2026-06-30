# Benchmark Generation Design v1.3

Status: implemented (2026-06-30)
Reads from: `benchmark_generation_design_v1.2.md`,
`analyzer_v2_codegraph_treesitter_plan.md`,
`runs/feasibility_v2_analyzer/phase5_acceptance.md`

v1.3 is the **analyzer rebuild** release. The host-LLM M2-M9 pipeline
from v1.2 stays intact; what changed is the **bundle producer** that
feeds Stage 0 + M2 with sources, entities, relations, and signals.

The v1 regex-fallback analyzer is replaced by a CodeGraph-backed
indexer with a Verilog/SystemVerilog language module added in a
project-owned fork. Pipeline integration is "ignore and ship" — the
v2 bundle is drop-in compatible with v1.2's prepare/generate path,
with one new soft-cap on anchor reuse to keep candidate diversity from
collapsing on hub modules.

---

## 1. Motivation

### 1.1 What v1.2 still could not do well

v1.2 fixed authoring quality (host-LLM modules with deterministic
validators around them), but the analyzer feeding it was unchanged:

1. **Regex extraction misanchors `conditional_behavior` signals.**
   The v1 builder's "first conditional-keyword match" landed in
   license headers, include guards, and CI YAML triggers — the
   anchors that should drive L3 reasoning questions about real RTL
   guards instead pointed at boilerplate. On Vortex, 87 such anchors
   had to be dropped at Stage 0 and 61 more required rescue from the
   nearest substantive line; on NVDLA, 125 dropped + 23 rescued.

2. **`imports_or_includes` edges had unresolved `object.id`.** Cross-
   file resolution was approximate, so prepare's graph-walk could not
   reliably hop from an anchor into its included files.

3. **No edge predicate for module instantiation.** Verilog modules
   instantiate each other via `child u_inst (.clk(clk));` — the v1
   graph had `defines` / `imports_or_includes` / `contains` /
   `doc_mentions_entity` and nothing to express structural
   hierarchy. L3 rows that needed to ask about cross-module wiring
   had no graph evidence to point at.

4. **`distracting_info` collision evidence was captured but not
   semantically rich.** The shape was usable; the data wasn't
   reliable on regex-extracted entities (license-header words got
   counted as colliding entities).

### 1.2 Mapping v1.2 limitations to v1.3 responses

| v1.2 limitation | v1.3 response |
|---|---|
| Regex misanchors `conditional_behavior` | Tree-sitter re-parse path anchors signals at real `conditional_statement` / `case_statement` / `always_construct` AST nodes (§ 4.3). |
| Unresolved `object.id` on imports edges | Bundle exporter resolves every edge endpoint to a bundle entity_id or source_id (§ 4.2). Vortex now has 0 empty-object.id rows. |
| No module-instantiation predicate | New `instantiates` predicate emitted for Verilog module/checker/UDP instantiation sites (§ 4.2). |
| Regex-noisy `distracting_info` collisions | AST-derived entities produce cleaner name-collision sets; v1 evidence shape preserved for backward compat (§ 4.3). |

What v1.2 did right and v1.3 keeps untouched: the M2-M9 host-LLM
authoring pipeline, the structural gate, the schemas, the layer plan
(50 L1 + 90 L2 + 60 L3), and the answerability/difficulty contracts.

---

## 2. Goals and non-goals

### 2.1 Goals

1. Replace the regex-fallback analyzer with an AST-anchored
   extractor for all non-RTL code/doc/config languages (via
   CodeGraph) and for RTL (via a Verilog language module added to
   CodeGraph).
2. Preserve the v1.2 bundle shape so `prepare_module_inputs.py` and
   the rest of the M2-M9 pipeline run unchanged.
3. Eliminate the Stage-0 license-zone rescue workaround as a
   measured outcome — not as a feature flag.
4. Maintain L1=50, L2=90, L3=60 layer coverage on both projects.

### 2.2 Non-goals

1. Reworking M2-M9 prompts. Authoring-quality tuning is filed as a
   follow-up in `docs/follow-ups.md` § 4.
2. Replacing the structural or adversarial gate. Both stay
   identical; the adversarial gate remains a stub (Phase 7
   follow-up) — v1.3 does not depend on it.
3. Adding new attribute axes to the difficulty contract.
   `signal_dataflow` is emitted by the new analyzer but is
   explicitly NOT wired into selection (§ 5.2).
4. Indexing source files outside the languages CodeGraph supports.
   The v1 regex extractor reached `shell`/`tcl`/`cmake`/`make`/
   binary; v1.3 indexes the ~22 languages tree-sitter covers.

---

## 3. Definitions

- **Bundle**: the `runs/<project>_context_bundle/` directory holding
  `project_manifest.json`, `source_inventory.jsonl`,
  `entity_index.jsonl`, `relation_graph.jsonl`, `signal_index.jsonl`,
  and `analyzer_report.md`. Schema is unchanged from v1.2.
- **Fork**: the project-vendored CodeGraph at `tools/codegraph/`,
  pinned at upstream `colbymchenry/codegraph@4077ed1` (v1.1.1) with
  three Verilog-support commits on top (saved as patches under
  `tools/codegraph/_patches/`).
- **Re-parse path**: Phase 3's `_verilog_reparse.py`, which uses the
  Python `tree-sitter-verilog` 1.0.3 binding to recover signal
  anchors the CodeGraph extractor does not surface as entities.
- **KNOWN_AXIS_ATTRIBUTES**: the whitelist in
  `scripts/generate_v1_1_release_corpora.py` that gates which
  `attribute` strings enter signal selection.

---

## 4. Bundle producer changes

### 4.1 Backend swap (CodeGraph 1.1.1 + Verilog language module)

Two-stage producer replaces the v1 single-pass regex emitter:

1. **CodeGraph index** — `codegraph init <project>` writes a SQLite
   knowledge graph at `repo_sources/<project>/.codegraph/codegraph.db`.
2. **Python exporter** — `scripts/codegraph_to_bundle.py` reads that
   DB and writes the canonical bundle JSONLs, plus a manifest pinning
   the CodeGraph commit.

The fork's Verilog module lives at
`tools/codegraph/src/extraction/languages/verilog.ts`. It registers
file extensions `.sv` / `.svh` / `.v` / `.vh` and routes the AST node
kinds tree-sitter-verilog produces:

| concept | node kind(s) |
|---|---|
| module declaration | `module_declaration` (surfaces as NodeKind `class`; remapped to entity kind `module` in the bundle) |
| function / task | `function_declaration`, `task_declaration` |
| interface / package / class | `interface_declaration`, `package_declaration`, `class_declaration` |
| `\`include` / `import pkg::*` | `include_directive`, `package_import_declaration` |
| module instance | `module_instantiation` + `checker_instantiation` + `udp_instantiation` (the grammar can't disambiguate without semantic context, so all three are routed) |
| control flow | `conditional_statement`, `case_statement`, `always_construct` — but tree-sitter doesn't surface these as entities; see § 4.3 |
| variables (nets, parameters, data) | `net_declaration`, `parameter_declaration`, `data_declaration` (all collapse to entity kind `variable` today; finer kinds filed as Phase 1.5b follow-up) |

CodeGraph has no `moduleTypes` slot in its `LanguageExtractor`
framework, so Verilog modules surface as `kind=class` at index time.
The bundle exporter remaps `(language='verilog' AND kind='class')` →
entity kind `module` for downstream consumers.

### 4.2 Bundle shape — what's new, what's preserved

Schema files unchanged. Additive payload changes:

- **`entity_index.jsonl`** — new kinds: `module` (Verilog modules),
  `interface` (Verilog interfaces), plus the existing kinds CodeGraph
  emits for C++/Python/etc.
- **`relation_graph.jsonl`** — new predicates: `instantiates` (Verilog
  module instances), `calls` (function calls), `extends` (class
  inheritance), `references` (type references). Existing v1
  predicates (`defines`, `imports_or_includes`, `doc_mentions_entity`,
  `contains`) are preserved. CodeGraph's `imports` is remapped to
  `imports_or_includes` so the existing prepare filter keeps matching.
- **`signal_index.jsonl`** — new attribute: `signal_dataflow` (per-
  Verilog-assignment write site with RHS dependency list). Existing
  axis-2 / axis-3 attributes (`long_tail`, `distracting_info`,
  `non_code_anchor`, `conditional_behavior`,
  `implicit_domain_knowledge`, `doc_code_divergence`) all preserved.
  The `evidence` shape for `distracting_info` carries the v1 keys
  (`collision_sources`, `collision_source_count`,
  `total_entities_with_name`) so prepare's consumers don't break.
- **`project_manifest.json`** — `analyzer_version:
  "benchmark-repo-analyzer/v2-tree-sitter-codegraph"`,
  `analysis_backends.code.used_primary: true`, plus an
  `analyzer_pin` block recording the CodeGraph commit + extraction
  version. v1's `schema_version: "project-manifest/v1"` preserved.

Schema validators run unchanged against v1.3 bundles. All 13,259 v1.3
signal records on Vortex validate against `schemas/signal-index.schema.json`.

### 4.3 Signal anchors — the re-parse path

The `conditional_behavior` signal is the load-bearing case. v1
anchored it at the first regex match for `if|case|when|where`, which
frequently fell inside license blocks. v1.3 takes a different path
because CodeGraph's `LanguageExtractor` framework doesn't surface
`conditional_statement` / `case_statement` / `always_construct` as
entities at index time.

Rather than extending the framework (Phase 3 ask #1: "don't extend
the extractor framework yet"), the `signal_emitter.py` re-parses each
Verilog source file via the Python `tree-sitter-verilog` 1.0.3 binding
and walks the AST for control-flow nodes. Anchors land at the real
node positions — license-block lines never participate.

Each anchor carries explicit provenance:

```json
"extractor": "verilog_tree_sitter_reparse_v2",
"evidence": {
  "provenance": "tree_sitter_verilog_reparse_v2",
  "ast_kind": "conditional_statement",
  ...
}
```

The same re-parse walk emits `signal_dataflow` anchors at every
assignment site with the LHS signal + RHS identifier list. These are
included in the bundle but deliberately NOT routed into selection
(§ 5.2).

---

## 5. Pipeline integration

### 5.1 `--bundle-path` flag

Both `prepare_module_inputs.py` and `generate_v1_1_release_corpora.py`
now accept `--bundle-path <dir>`, defaulting to
`runs/<project>_context_bundle/` for backward compatibility. Phase 5
promoted the v2 bundle to that canonical path, so the default
invocation reads v2 transparently. To compare against the archived
v1 bundle:

```bash
uv run python skills/benchmark-generator/scripts/prepare_module_inputs.py \
    --project vortex \
    --bundle-path runs/archive/vortex_context_bundle_v1/ \
    --repo-root /path/to/checkout
```

### 5.2 `KNOWN_AXIS_ATTRIBUTES` whitelist — "ignore and ship"

`load_signals` filters incoming signal records by attribute name.
Only attributes the selection logic knows how to rank are accepted:

```python
KNOWN_AXIS_ATTRIBUTES = frozenset({
    "long_tail", "distracting_info", "non_code_anchor",
    "conditional_behavior", "implicit_domain_knowledge",
    "doc_code_divergence", "version_fork_diff",
})
```

`signal_dataflow` is NOT in the whitelist. It's dropped silently at
load time; a one-line stdout audit reports the drop count so future
runs surface the volume.

This is the "ignore and ship" decision from Phase 4. Adding a new
attribute to PREFERRED_ATTRIBUTE_GROUPS requires a coordinated edit
to both `KNOWN_AXIS_ATTRIBUTES` and a `PREFERRED_ATTRIBUTE_GROUPS`
entry — never a silent default flip.

The Phase 5 smoke50 measurement confirmed `signal_dataflow` wiring is
unnecessary: 21/21 Verilog-anchored L3 rows already have
`conditional_behavior` axis-3 coverage adjacent to real write sites.
Wiring `signal_dataflow` would rescue zero rows.

### 5.3 `ANCHOR_ROTATION_CAP` — anchor diversity guard

Phase 5 surfaced a candidate-concentration outlier:
`VX_cluster.sv:48-50` was picked as the row anchor 61 times because
the highest-edge-degree sort always lifted the same hub-module
candidate to position 0.

v1.3 adds a soft cap in `prepare_module_inputs.py`:

```python
ANCHOR_ROTATION_CAP = PATH_LINES_REUSE_CAP  # = 3
```

The anchor sort key is now three-tier: `(over_cap, -edge_degree,
path, lines)`. Candidates whose (path, lines) tally hits the cap are
demoted behind uncapped ones. If every candidate is over-capped, the
original highest-edge-degree wins — rows always get an anchor.

Measured effect on Vortex v1.3 prepare:

- `VX_cluster.sv:48-50` as anchor: 61 → 3 (95% reduction)
- L2 distinct candidate sources: unchanged (326)
- L3 distinct candidate sources: unchanged (257)

A per-project audit print after diversity warnings shows the top-5
anchor (path, lines) reuse counts each run.

### 5.4 Stage-0 conditional_behavior workaround — dormant

The Stage-0 `conditional_behavior_substantive_span` /
`_find_first_substantive_line` rescue helpers in
`prepare_module_inputs.py` remain in the code as defense-in-depth.
On v1.3 bundles they never fire — measured 0/0 rescue+drop on both
Vortex and NVDLA. Removal is a separate cleanup PR scoped to "two
consecutive smoke50 runs with zero rescues."

---

## 6. Acceptance evidence

### 6.1 Bundle quality

| metric | Vortex | NVDLA |
|---|---|---|
| sources | 577 | 1,440 |
| entities | 5,745 | 52,729 |
| relations | 14,925 | 166,458 |
| signals | 13,259 | 191,184 |
| `instantiates` edges | 441 | n/a (computed at re-index) |
| validator FAIL / WARN | 0 / 0 | 0 / 0 |
| Stage-0 `conditional_behavior` rescues | 0 (was 61 on v1) | 0 (was 23 on v1) |
| Stage-0 `conditional_behavior` drops | 0 (was 87 on v1) | 0 (was 125 on v1) |

### 6.2 Smoke50 (Vortex, full M2-M9 pipeline + structural gate)

| metric | v1.3 | acceptance bar |
|---|---|---|
| candidate rows written | 198 (2 dropped at M2) | — |
| L1 substantive rows | 20/50 (= v1) | — |
| L2 with candidates | 88/90 | — |
| **L3 row survival under structural gate** | **60/60 (100%)** | ≥ 15/60 |
| L3 signal-write rows with axis-3 coverage | 21/21 | — |
| L2 distinct candidate sources | 326 (+17% vs v1) | — |
| L3 distinct candidate sources | 257 (+37% vs v1) | — |

### 6.3 Caveat — the adversarial gate

`skills/benchmark-validator/scripts/adversarial_gate.py` emits
`status: "skipped_no_provider"` for every row regardless of
`--judge-provider`. The original v2 plan named "L3 row survival ≥
15/60 under the strict adversarial gate" as the acceptance bar; in
practice the adversarial gate is a stub, so v1.3 acceptance was
measured against the structural gate. A real LLM-judged adversarial
gate is filed as Phase 7 in `docs/follow-ups.md`.

**v1.3 is sign-off for the analyzer/codegraph infrastructure, NOT
for benchmark-authoring quality at adversarial-gate strictness.**

---

## 7. Current constraints and follow-ups

These do not block v1.3 release. Detailed scope + triggers in
`docs/follow-ups.md`.

| # | item | trigger to revisit |
|---|---|---|
| 1.5a | `text_macro_definition` not routed → v1 `kind=macro` (~1,700 rows on Vortex) not recovered | downstream consumer explicitly filtering on `kind=macro` and finding none |
| 1.5b | `net_declaration` / `parameter_declaration` collapse into `kind=variable` → v1 `kind=signal` (4,113) and `kind=parameter` (1,594) not differentiated | consumer filtering on `kind=signal` or `kind=parameter` |
| 3.5 | `conditional_behavior` re-parse covers Verilog only — C++/Python conditional sites missing | L3 quality bar tightens for non-Verilog rows |
| 6A.5 | `graph_walk_neighbors` still surfaces VX_cluster.sv:48-50 in 58 rows as a neighbor (only anchor position is capped today) | M2-M9 authoring quality regressions trace to neighbor concentration |
| 6B | Verible fallback for 9 hard-error Vortex files (`VX_trace_pkg.sv`, AFU wrap, DPI headers, `VX_uop_sequencer.sv`, interface files) | smoke50 attributes L2/L3 failures to those files, OR explicit coverage-completeness decision |
| 7 | `adversarial_gate.py` stub | release-grade benchmark quality claim needed |
| L2 prompts | M2/M5/M6 prompt tuning for INSUFFICIENT_DIFFICULTY_SIGNALS (53) and CONDITIONAL_BEHAVIOR_WITHOUT_ROLE (20) failures | L2 pass rate ≥ 80% required |

---

## 8. Implementation checklist

Shipped:

- [x] CodeGraph fork vendored at `tools/codegraph/` with Verilog
      language module + `tree-sitter-verilog.wasm` (Phase 1)
- [x] `scripts/codegraph_to_bundle.py` exporter (Phase 2)
- [x] `scripts/signal_emitter.py` + `_verilog_reparse.py` (Phase 3)
- [x] `--bundle-path` flag + `KNOWN_AXIS_ATTRIBUTES` whitelist (Phase 4)
- [x] v2 bundle promoted to canonical path (Phase 5)
- [x] `ANCHOR_ROTATION_CAP` soft cap in prepare (Phase 6A)
- [x] `tools/codegraph/` vendored into git with `_patches/` for the
      three Verilog commits

Gated / scheduled (see § 7):

- [ ] Phase 1.5a — macro extraction
- [ ] Phase 1.5b — finer signal/parameter extraction
- [ ] Phase 3.5 — non-Verilog conditional_behavior
- [ ] Phase 6A.5 — neighbor-pick concentration
- [ ] Phase 6B — Verible fallback
- [ ] Phase 7 — real LLM-judged adversarial gate
- [ ] L2 prompt tuning

---

## 9. Reference artifacts

| concern | artifact |
|---|---|
| Original v1.3 plan + phase tracker | `analyzer_v2_codegraph_treesitter_plan.md` |
| Per-phase acceptance reports | `runs/feasibility_v2_analyzer/phase{1,2,3,4,5}_acceptance.md` |
| npm-audit clearance | `runs/feasibility_v2_analyzer/phase5_npm_audit.md` |
| Phase 0 feasibility (full Verilog grammar measurement + CodeGraph schema dump) | `runs/feasibility_v2_analyzer.md`, `runs/feasibility_v2_analyzer/codegraph_schema.md`, `runs/feasibility_v2_analyzer/_observed_node_kinds.md` |
| Fork provenance + how-to-rebuild | `tools/codegraph/NOTES_kb_benchmark.md` |
| Three Verilog commits (as patches) | `tools/codegraph/_patches/000{1,2,3}-*.patch` |
| Non-blocking follow-ups | `docs/follow-ups.md` |
| Per-phase implementation plans (under `docs/superpowers/plans/`) | `2026-06-24-analyzer-v2-phase-{0..6}-*.md` |
