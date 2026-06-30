# Analyzer v2 Phase 0 — Feasibility report

Date: 2026-06-25
Author: Claude Opus 4.7 (executing Phase 0 plan)
Plan reference: `docs/superpowers/plans/2026-06-24-analyzer-v2-phase-0-feasibility.md`
Worktree / branch: `.claude/worktrees/dev-v1.3-analyzer-codegraph-phase0` on
`worktree-dev-v1.3-analyzer-codegraph-phase0` (branched from `main` at v1.2).

## 1. Decision summary

- **Phase 6 (Verible secondary parser):** **RECOMMENDED for Vortex, OPTIONAL for NVDLA.**
  - Vortex strict clean rate: 26.05% (95.5% usable on non-foundry files).
  - NVDLA strict clean rate: 26.0% (100.0% usable on non-generated files).
  - Bucket: 80-95% (`usable_pct` metric) → Phase 6 in scope.
  - Driver: 9 hand-written Vortex files have hard errors (DPI headers,
    `VX_trace_pkg.sv`, AFU wrappers, `VX_uop_sequencer.sv`, interface
    files). NVDLA has zero hard errors on hand-written RTL.
- **CodeGraph fork pin:** `colbymchenry/codegraph@4077ed1` (v1.1.1; full
  sha in `_codegraph_commit.txt`).
- **Observed RTL root node kind:** `source_file` (matches plan default).
- **Observed always-block node kind:** `always_construct` (matches plan).
- **Major plan correction — control flow:** `conditional_statement`, **not**
  `if_statement`. Phase 1 `conditions.scm` and Phase 3 emitter must use the
  correct name.
- **Major plan correction — instantiation:** tree-sitter-verilog cannot
  disambiguate `child u (.clk(clk));` from a checker or UDP instance.
  Empirically, only `child #(.W(8)) u(...)` parses as `module_instantiation`;
  plain named-port instances parse as `checker_instantiation`, positional
  instances as `udp_instantiation`. Phase 1 `relations.scm` must capture
  all three and let the resolver disambiguate by checking which kind the
  target identifier resolves to (`module_declaration` /
  `checker_declaration` / `udp_declaration`).

## 2. tree-sitter-verilog coverage

tree-sitter-verilog version: 1.0.3 (PyPI wheel; resolves on Python 3.14).

### Vortex

- Total RTL files measured: 215 (path: `repo_sources/vortex`).
- Excluding 14 Synopsys foundry memory models under
  `vortex/hw/syn/synopsys/models/` (auto-generated, never analyzed): 201.
- Parse status (full set / non-foundry):
  - clean: 56 / 48 (23.9% non-foundry)
  - partial (≤ 5% ERROR nodes): 150 / 144 (71.6%)
  - error: 9 / 9 (4.5%)
- Files containing expected node kinds (from
  `vortex_rtl_coverage.summary.json`):
  - `module_declaration`: 128
  - `parameter_declaration`: 161
  - `always_construct`: 101
  - `conditional_statement`: 81
  - `case_statement`: 26
  - `module_instantiation`: 92 *(parametric instances)*
  - `checker_instantiation`: 43 *(plain named-port instances)*
  - `udp_instantiation`: 25 *(positional instances)*
  - `package_import_declaration`: 107
  - `text_macro_definition`: 31
  - `function_declaration`: 7
  - `task_declaration`: 8
  - `interface_declaration`: 23
  - `package_declaration`: 6

- Top hard-error files (non-foundry; these gate Phase 6):
  - `vortex/hw/rtl/VX_trace_pkg.sv` (459 ERROR nodes)
  - `vortex/hw/rtl/afu/xrt/VX_afu_wrap.sv` (282)
  - `vortex/hw/dpi/float_dpi.vh` (171)
  - `vortex/hw/rtl/afu/xrt/vortex_afu.v` (64)
  - `vortex/sim/xrtsim/vortex_afu_shim.sv` (62)
  - `vortex/hw/rtl/core/VX_uop_sequencer.sv` (33)
  - `vortex/hw/dpi/util_dpi.vh` (25)
  - `vortex/hw/rtl/interfaces/VX_decode_if.sv` (10)
  - `vortex/hw/rtl/interfaces/VX_fetch_if.sv` (10)

### NVDLA

- Total RTL files measured: 427 (path: `repo_sources/nvdla`).
- Excluding 106 generated files under `hw/vmod/rams/synth/` and
  `hw/vmod/vlibs/`: 321.
- Parse status (non-generated only):
  - clean: 77 (24.0%)
  - partial: 244 (76.0%)
  - error: 0 (0.0%)
- Top expected kinds:
  - `module_declaration`: 389 (full set)
  - `module_instantiation`: 355
  - `conditional_statement`: 361
  - `always_construct`: 335
  - `text_macro_definition`: 257
  - `case_statement`: 152
  - `function_declaration`: 141

NVDLA's vlibs (DesignWare leaf cells) have AST depth > 1000; the
measurement script's `walk()` was converted from recursive to iterative
because the recursive form hit Python's default recursion limit.

## 3. CodeGraph behaviour

- Upstream: `colbymchenry/codegraph` v1.1.1, commit
  `4077ed19b7d8a88eba93601c0c308e59c8640f8c`.
- Runtime: requires **Node.js ≥ 22.5** for the built-in `node:sqlite`
  module. The dev box's system Node is 20.20.2; all CodeGraph invocations
  use the homebrew `node@22` directly (see `_codegraph_paths.md`).
- CLI path: `tools/codegraph/dist/bin/codegraph.js` (not
  `tools/codegraph/bin/codegraph` as the original plan assumed).
- DB path (Vortex): `repo_sources/vortex/.codegraph/codegraph.db` (CodeGraph
  creates `.codegraph/` inside the indexed project; the path is fixed).

### Vortex indexing pass

| metric           | value |
|---|---|
| files indexed    | 366 (out of all non-RTL files in `repo_sources/vortex`) |
| nodes            | 7,727 |
| edges            | 16,133 |
| init wall-clock  | ~3.3 s |
| DB size          | ~14 MB |

By language:

| language | files |
|---|---|
| cpp      | 228 |
| c        | 122 |
| python   | 13 |
| yaml     | 2 (file-level only) |
| php      | 1 |

Top node kinds: `function` (2035), `import` (1852), `method` (1773),
`enum_member` (458), `file` (364), `class` (363), `struct` (361),
`type_alias` (304), `variable` (144), `enum` (69).

Edge-kind distribution: `calls` (7752), `contains` (7408), `imports`
(650), `extends` (158), `references` (97), `instantiates` (68).

### Cross-file resolution probes

All 5 probes exit 0; 4 of 5 return non-empty payloads (exceeds the plan
bar of ≥ 3/5). Transcript: `runs/feasibility_v2_analyzer/codegraph_probe_transcript.md`.

| probe | result | notes |
|---|---|---|
| `query Core --json` | non-empty | 5 hits across `core.cpp`, `core.h`, `dispatcher.h`, `emulator.h`, `func_unit.h` |
| `files` | non-empty | full tree dump, 366 entries |
| `node Core` | non-empty | symbol detail rendered |
| `callers Core` | empty list | name-overload ambiguity (Core is both class and method); Phase 1 should probe with `qualifiedName` instead |
| `callees Core --json` | non-empty | 10 cross-file resolutions into `common/`, `runtime/`, `vpu/` |

### Schema (frozen contract for Phase 2)

Full dump: `runs/feasibility_v2_analyzer/codegraph_schema.md`.

| table | rows | role |
|---|---|---|
| `nodes` | 7727 | symbols (id `kind:hex`, kind, name, qualified_name, file_path, language, start/end line+col, etc.) |
| `edges` | 16133 | source → target relations (kind, metadata JSON, line/col, provenance) |
| `files` | 366 | tracked source files |
| `unresolved_refs` | 0 | references awaiting resolution |
| `project_metadata` | 2 | indexed_with_version, extraction_version |
| `schema_versions` | 2 | DDL version tracking |
| `nodes_fts*` | varies | FTS5 virtual + backing tables |

**Phase 2 plan correction:** the Phase 2 plan uses placeholder table names
`symbols` and `relations`. Real names are `nodes` and `edges`. Phase 2's
`_codegraph_queries.py` must be rewritten against the real schema in
`codegraph_schema.md` (already copied into the skill location for the
Phase 2 contract).

## 4. Risks observed in Phase 0 (feed into Phase 1+ risk register)

- **R1: tree-sitter-verilog grammar ambiguity on plain module instances.**
  73% of Vortex `instantiates` candidates (135 of 160) parse as
  `checker_instantiation` or `udp_instantiation`, not `module_instantiation`.
  Mitigation: Phase 1 relations.scm matches all three kinds; resolver
  disambiguates by target kind.
- **R2: 9 hard-error Vortex files.** `VX_trace_pkg.sv` alone has 459
  ERROR nodes (suggests heavy parameterized typedefs or unusual macros).
  Mitigation: Phase 6 (Verible secondary parser) for the failed files.
- **R3: Node 22.5 runtime requirement.** Operationally this means CI and
  fresh dev boxes need a separate Node install (homebrew `node@22` or the
  CodeGraph standalone installer that bundles Node). Document in
  `skills/benchmark-repo-analyzer/SKILL.md` during Phase 5.
- **R4: CodeGraph's `Core` callers returning empty.** Name disambiguation
  for cross-language overloaded symbols may need explicit qualifiedName
  threading. Re-validate during Phase 1 with the Verilog language module.
- **R5: NPM audit reports 8 vulnerabilities (4 moderate, 3 high, 1
  critical) in CodeGraph 1.1.1's dependency tree.** Not Phase 0's
  problem; flag for Phase 5 sign-off so security review happens before
  v2 promotion.

## 5. Required adjustments to later phases

### Phase 1 (`queries/verilog/entities.scm` and `relations.scm`)

- Use observed node-kind names (NOT the plan's defaults where they differ):
  `source_file`, `module_declaration`, `parameter_declaration`,
  `always_construct`, **`conditional_statement`** (not `if_statement`),
  `case_statement`, `function_declaration`, `task_declaration`,
  `interface_declaration`, `package_declaration`, `text_macro_definition`,
  `package_import_declaration`, `include_directive`.
- `instantiates` predicate must match the **union** of
  `module_instantiation` / `checker_instantiation` / `udp_instantiation`,
  with disambiguation deferred to the resolver.
- Integration points inside the fork:
  - `tools/codegraph/src/extraction/grammars.ts` — add `verilog:
    'tree-sitter-verilog.wasm'` to `WASM_GRAMMAR_FILES` and `.sv`/`.v`/
    `.svh`/`.vh` to `EXTENSION_MAP`.
  - `tools/codegraph/src/extraction/languages/` — add `verilog.ts`
    mirroring an existing built-in (e.g. `python.ts`).
- The plan's placeholder `src/languages/verilog.ts` path was wrong;
  CodeGraph 1.1.1's per-language extractors live at
  `src/extraction/languages/<lang>.ts`.

### Phase 2 (bundle exporter)

- Real CodeGraph table names: `nodes`, `edges`, `files`, `unresolved_refs`.
- Symbol id format: `<kind>:<32-hex>` (e.g. `class:4bde861b2aa61dbbe846e3813435230d`).
- `edges.kind` already includes `instantiates`, `imports`, `calls`,
  `extends`, `references`, `contains` — so Phase 2's `--diff-against v1`
  can map directly.
- Phase 2's `_codegraph_queries.py` placeholders (`SELECT * FROM symbols`,
  `SELECT * FROM relations`) need rewriting to `nodes` / `edges` against
  the real columns from `codegraph_schema.md`.

### Phase 3 (signal emitter)

- `conditional_behavior` AST kind name is `conditional_statement` (not
  `if_statement`). Update Phase 3 `TARGET_AST_KINDS = {"conditional_statement",
  "case_statement", "always_construct"}`.

### Phase 6 (RTL accuracy reinforcement)

- Triggered for Vortex (per § 1 bucket).
- The 9 hard-error files are concentrated in `hw/dpi/`, `hw/rtl/afu/xrt/`,
  and a few `hw/rtl/` modules. Phase 6 fixture (`breakage.sv`) can be
  derived from a slice of `VX_trace_pkg.sv` since that has the highest
  error count.

## 6. Sign-off

Phase 0 outputs reviewed by: (pending user review)
Phase 1 GO / NO-GO: **GO** — all four feasibility criteria met:

1. tree-sitter-verilog parses real RTL with > 95% usable rate on
   hand-written files.
2. CodeGraph 1.1.1 indexes Vortex's full non-RTL surface cleanly in 3.3 s.
3. SQLite schema is small (~6 real tables) and exports cleanly.
4. Cross-file resolution works for C++ (4/5 probes return useful
   payloads).

Conditions on the GO:

- Phase 1 begins by patching the plan's placeholder integration paths
  (`src/languages/verilog.ts` → `src/extraction/languages/verilog.ts`;
  add to `grammars.ts` registry) and the placeholder node-kind names
  (`if_statement` → `conditional_statement`; instantiation triple).
- Phase 2 freezes the contract against
  `runs/feasibility_v2_analyzer/codegraph_schema.md` before writing the
  exporter.
- Phase 6 is in scope (triggered by Vortex bucket); plan a minimum-viable
  Verible-fallback for the 9 hard-error files.
- Phase 5 must perform an npm-audit security review of CodeGraph 1.1.1's
  dependency tree before promoting v2 to canonical.
