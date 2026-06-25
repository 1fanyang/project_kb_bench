# Analyzer v2 — CodeGraph + tree-sitter-Verilog plan

Status: planning
Owner: TBD
Date authored: 2026-06-24
Supersedes when implemented: `benchmark-repo-analyzer/v1-regex-fallback`

This document is the single source of truth for the v2 analyzer migration.
It exists so that work in flight across multiple phases does not drift from
the original design. Update this file when a phase ships or a decision
changes — do not change scope silently in code.

---

## 1. Goal

Replace the regex-fallback analyzer with an AST-anchored extractor that
covers:

- All non-RTL code/doc/config languages in the current Vortex/NVDLA bundles
  (C, C++, Python, Markdown, RST, YAML, Makefile, shell, …) via
  [`colbymchenry/codegraph`](https://github.com/colbymchenry/codegraph),
  which already uses tree-sitter for 20+ languages.
- RTL (SystemVerilog / Verilog), which CodeGraph does not natively support,
  via a **new Verilog language module added to CodeGraph** using
  `tree-sitter-verilog`.

The downstream bundle schema (`source_inventory.jsonl`, `entity_index.jsonl`,
`relation_graph.jsonl`, `signal_index.jsonl`) stays compatible. Changes are
additive (new edge predicates, richer signal evidence) and never remove
fields existing consumers depend on.

The success bar — measurable on the Vortex bundle — is:

1. **`conditional_behavior` signals never anchor at file-header / license
   lines.** Today 73% (466 / 637) do.
2. **`imports_or_includes` edges carry resolved `object.id` and the
   included file's first substantive line.** Today neither.
3. **At least one new edge predicate exists for module instantiation in
   Verilog** (today the graph has only `defines`, `imports_or_includes`,
   `doc_mentions_entity`, `contains`).
4. **`distracting_info` collision evidence is preserved end-to-end** for
   downstream pipeline consumers.
5. **L3 row survival after strict gate ≥ 15/60 on Vortex** (was 2/60 in the
   prior smoke50 run).

---

## 2. Context — what we are replacing and why

### 2.1 Current analyzer

- `benchmark-repo-analyzer/v1-regex-fallback`
- `project_manifest.json` declares `requested_primary: "code_graph"` but
  `used_primary: false`. Everything is regex_fallback today.
- Outputs four bundle artifacts: `source_inventory.jsonl`,
  `entity_index.jsonl`, `relation_graph.jsonl`, `signal_index.jsonl`.
- Known defects, documented in `improvement_suggestions.md` and surfaced
  in the smoke50 reviews:
  - 73% of `conditional_behavior` signals anchor at file-header lines 1-10
    (regex's first hit is in the license block or YAML header).
  - `doc_code_divergence` is "doc mentions entity" mislabeled — no actual
    divergence detection.
  - `imports_or_includes` edges store `object.name` only (no resolved id).
  - Include evidence lines point at the includer, not the included file.
  - Only 4 edge predicates; no call / instantiation / read / write edges.
  - `confidence` field always 0.7 (signal-builder default).
  - `distracting_info` collision evidence is captured but not consumed
    downstream.

### 2.2 Workarounds already implemented at the prepare layer

`skills/benchmark-generator/scripts/prepare_module_inputs.py` carries
Stage-0 patches that mask the analyzer's defects at candidate-emission
time. These should become no-ops once the v2 analyzer lands.

- `conditional_behavior_substantive_span()` — re-reads the source span and
  rescues / drops candidates whose lines are license blocks / include
  guards.
- `_find_first_substantive_line()` — for `imports_or_includes` neighbors,
  walks past `\`ifndef X / \`define X / // ...` to the first real
  declaration.
- `graph_walk_neighbors()` — hop-2 prefers `doc_mentions_entity` to fan
  out into doc sources; falls back to `defines` / `imports_or_includes`.
- Anchor reorder by edge-degree (highest-productivity candidate becomes
  `candidates[0]`).

These remain useful as defense-in-depth even after v2; they cost essentially
nothing if the underlying signals are already clean.

### 2.3 Why CodeGraph specifically

- It is itself tree-sitter-based, so the integration is "add a language
  module" rather than "build an external adapter."
- Storage is local SQLite + FTS5 — no server dependency.
- Already supports 20+ languages including all of our non-RTL surface.
- Provides cross-file resolution (call → definition, import → source,
  inheritance chains) that we would otherwise re-implement.
- Provides an MCP tool surface that may be useful for the host-LLM
  authoring stages later.
- License/maintainer: single-maintainer OSS project. We will **fork
  first** to move at our own pace; upstream PR is a follow-on, not a
  blocker.

### 2.4 Why NOT pure tree-sitter without CodeGraph

We considered authoring tree-sitter queries for every language ourselves.
The decision-driver was: the team plans to use CodeGraph beyond the
benchmark generator, so the RTL language module is a one-time investment
that benefits every CodeGraph consumer. If that assumption changes, this
plan should be revisited and pure-tree-sitter (Option A from the
comparison message) should be reconsidered as a simpler alternative.

---

## 3. Architecture

### 3.1 Layered view

```
                      repo_sources/ (the project being analyzed)
                                    │
                                    ▼
            ┌───────────────────────────────────────────┐
            │  CodeGraph (Node.js, tree-sitter-based)   │
            │                                           │
            │   ┌────────────┐   ┌────────────────┐    │
            │   │ Built-in   │   │ New Verilog    │    │
            │   │ languages  │   │ language module│    │
            │   │ (C/C++/Py/ │   │ (Phase 1)      │    │
            │   │ MD/YAML…)  │   │                │    │
            │   └─────┬──────┘   └────────┬───────┘    │
            │         └───────┬──────────┘            │
            │                 ▼                       │
            │         CodeGraph resolver              │
            │                 │                       │
            │                 ▼                       │
            │      .codegraph/codegraph.db (SQLite)   │
            └─────────────────┬──────────────────────┘
                              │
                              ▼  (Phase 2 exporter, Python)
        ┌──────────────────────────────────────────────┐
        │  runs/<project>_context_bundle/              │
        │     source_inventory.jsonl                   │
        │     entity_index.jsonl                       │
        │     relation_graph.jsonl                     │
        │     signal_index.jsonl  ← (Phase 3 emitter)  │
        │     project_manifest.json                    │
        │     analyzer_report.md                       │
        └────────────────────┬─────────────────────────┘
                             │
                             ▼  (existing pipeline; minor wiring updates)
              prepare_module_inputs.py → M2…M9 → assemble → lint
```

### 3.2 Where each fix from the analyzer-side review lands

| Review finding | Phase | How |
|---|---|---|
| A1 — `conditional_behavior` anchors at file headers | 1 | tree-sitter selects `if_statement` / `case_statement` / `always_block` AST nodes |
| A2 — `doc_code_divergence` mislabeled | 3 (partial) | tree-sitter cleans the doc claims; actual divergence detection deferred to a follow-on |
| A3 — `implicit_domain_knowledge` over-emitted | 3 | Heuristic on AST node kind; may be tightened or deferred |
| A4 — `distracting_info` collision data not consumed | downstream of 5 | Bundle exporter preserves collision_sources; prepare/M5/M9 consume |
| B1 — Missing semantic edges | 1 | Verilog language module emits `instantiates`, `calls` |
| B2 — Include `object.id` unresolved | 1 | CodeGraph resolver matches include basename to source_id |
| B3 — Include lines point at includer | 1 + 2 | Verilog language module records includee's first substantive line |
| B4 — `contains` edges are filesystem noise | 2 | Exporter drops them |
| C1 — `code_graph` backend not initialized | the whole plan | CodeGraph IS the new backend |
| C2 — `confidence` always 0.7 | 2 | Bundle exporter assigns 0.95 to AST-derived, 0.7 to regex fallback |
| D1 — `version_fork_diff` never emitted | follow-on after Phase 5 | Cross-source_set entity diff; NVDLA-specific |

---

## 4. Phase plan

Total estimated effort: **18–22 person-days**. Each phase is independently
shippable; the next phase need not block on the previous if a stable
intermediate exists.

### Phase 0 — Feasibility + scoping (4–8 hours)

**Goal:** determine whether tree-sitter-verilog alone suffices for Vortex
RTL, and confirm CodeGraph is stable on the non-RTL surface.

**Tasks:**

| ID | Task |
|---|---|
| 0.1 | Install `tree-sitter` + `tree-sitter-verilog` Python bindings. |
| 0.2 | Parse all 201 of Vortex's `code.rtl` files. For each, record: parse status (clean / partial / error), and presence of expected node kinds (`module_declaration`, `parameter_declaration`, `always_block`, `if_statement`, `case_statement`, `module_instantiation`). |
| 0.3 | Parse a sampled subset of NVDLA RTL (~50 files) the same way. |
| 0.4 | Install CodeGraph; run `codegraph index` on Vortex *excluding* RTL files; verify the SQLite database populates. |
| 0.5 | Sample 5 `codegraph explore` / `codegraph query` calls to confirm cross-file resolution works on C++ and Python. |
| 0.6 | Dump CodeGraph's SQLite schema; record table names and FK relationships. |
| 0.7 | Write `runs/feasibility_v2_analyzer.md` — 2–3 page report summarizing findings. |

**Decision triggered:**
- If Vortex parse rate ≥ 95% → tree-sitter-verilog alone is enough; skip Phase 6.
- If 80–95% → plan Phase 6 with Verible as secondary parser.
- If < 80% → reconsider scope; possibly Verible as primary RTL parser.

**Stop conditions:** Phase 0 result decides whether to commit to Phase 1.

### Phase 1 — Verilog language module for CodeGraph (5–7 days)

**Goal:** ship a working Verilog language module inside our CodeGraph
fork.

**Tasks:**

| ID | Task |
|---|---|
| 1.1 | Fork `colbymchenry/codegraph` to a project-owned Git remote. Pin the fork base commit. |
| 1.2 | Add `tree-sitter-verilog` as a Node dependency of CodeGraph. |
| 1.3 | Register file extensions `.sv`, `.v`, `.vh`, `.svh` → `verilog` language id. |
| 1.4 | Author `queries/verilog/entities.scm`: `module_declaration`, `parameter_declaration`, `function_declaration`, `task_declaration`, `interface_declaration`, `package_declaration`, `\`define`, top-level `class_declaration`. |
| 1.5 | Author `queries/verilog/relations.scm`: `module_instantiation` → `instantiates`; function/task call → `calls`; `\`include` → `imports`; `import pkg::*` → `imports`. |
| 1.6 | Extend CodeGraph's resolver for Verilog: module instantiation type → module declaration; include basename → file lookup; package import → package declaration. |
| 1.7 | (Optional) Author `queries/verilog/conditions.scm` for `if_statement` / `case_statement` / `always_block` if these need to surface as their own entities. |

**Acceptance:**

- `codegraph index <vortex>` completes without errors on the full Vortex
  source tree (including RTL).
- `codegraph explore VX_cache_bypass` returns the module definition + its
  instantiations + its parameters.
- `codegraph query --kind module VX_cache_*` returns the expected modules.
- A spot-check on 5 RTL files confirms `instantiates` edges resolve to
  the correct target module across files.

**Risk:** SystemVerilog constructs that tree-sitter-verilog handles
poorly (recursive `generate` blocks, advanced `genvar` arithmetic,
complex `class extends`, parameterized class methods). Mitigation: log
per-construct errors during indexing and decide on a per-construct
basis whether to harden the query or accept the gap and document.

### Phase 2 — Bundle exporter (3–4 days)

**Goal:** read CodeGraph's SQLite DB and write our existing bundle JSONL
artifacts. No new schema; additive predicate names only.

**Tasks:**

| ID | Task |
|---|---|
| 2.1 | Inspect CodeGraph SQLite schema in detail; document the relevant tables and queries in `references/codegraph_schema.md`. |
| 2.2 | Write `skills/benchmark-repo-analyzer/scripts/codegraph_to_bundle.py` (new skill directory). |
| 2.3 | Emit `source_inventory.jsonl` from CodeGraph's file table; preserve `source_type`, `modality`, `authority`, `repo_name`, `line_count`. |
| 2.4 | Emit `entity_index.jsonl` from CodeGraph's symbol/node table; map kinds to our existing kinds plus new ones (`module`, `parameter`, `task`, `interface`). |
| 2.5 | Emit `relation_graph.jsonl`. Predicates: keep existing four (`defines`, `imports_or_includes`, `doc_mentions_entity`, `contains` — though `contains` may be dropped) and add `instantiates`, `calls`, `imports` (Verilog-specific). |
| 2.6 | For `imports_or_includes` edges: emit `object.id` (resolved) plus a new `evidence.included_first_substantive_line` field. |
| 2.7 | Emit `project_manifest.json` with `analyzer_version: benchmark-repo-analyzer/v2-tree-sitter-codegraph` and `analysis_backends.code.used_primary: true`. |
| 2.8 | Emit `analyzer_report.md` with summary stats. |
| 2.9 | Add a `--diff-against` flag pointing at the v1 bundle for side-by-side comparison output. |

**Acceptance:**

- Bundle JSONL files validate under `schemas/*.json` (extending the relation-graph schema to accept new predicates).
- Vortex bundle's entity count ≥ regex_fallback baseline for shared kinds (function, module, parameter, signal, macro, class).
- All `imports_or_includes` edges carry a resolved `object.id`.
- No `conditional_behavior` (when computed in Phase 3) anchors at file lines 1-10 in license blocks.
- `--diff-against` produces a human-readable report.

### Phase 3 — Signal-emission layer (2–3 days)

**Goal:** compute axis-2 / axis-3 attribute signals from the CodeGraph
export. Signals are pipeline-specific, not CodeGraph-native, so this is
our own layer.

**Tasks:**

| ID | Task |
|---|---|
| 3.1 | Write `skills/benchmark-repo-analyzer/scripts/signal_emitter.py`. |
| 3.2 | `long_tail`: entities with inbound-edge count ≤ τ (default 3). |
| 3.3 | `distracting_info`: entities whose `name` is shared by ≥ 2 distinct sources. Emit `evidence.collision_sources` + `collision_source_count` + `total_entities_with_name` (preserving the existing data shape). |
| 3.4 | `non_code_anchor`: anchors in source_inventory modalities `script | config | build`. |
| 3.5 | `conditional_behavior`: anchors on entities/relations originating from `if_statement` / `case_statement` / `always_block` AST nodes (using a new CodeGraph metadata field added in Phase 1). |
| 3.6 | `doc_code_divergence`: keep the existing emission (doc source `doc_mentions_entity` a code entity) but mark the signal evidence honestly — note in the summary that this is a "mention" signal, not yet content-level divergence. Real divergence detection is deferred. |
| 3.7 | `implicit_domain_knowledge`: defer to a simple heuristic (RTL/HLS code files) or skip. Documented either way. |
| 3.8 | `version_fork_diff`: not emitted in this phase; tracked as follow-on. |
| 3.9 | Per-signal `confidence`: 0.95 for AST-derived; 0.7 for any heuristic / regex fallback. |

**Acceptance:**

- `conditional_behavior` signals' anchor lines never fall in license / file-header positions. Sweep verifies 0 such anchors on Vortex.
- `distracting_info` signals preserve the existing collision evidence shape so prepare/M9 consumers don't break.
- Signal count is comparable to or exceeds regex_fallback baseline.

### Phase 4 — Integration into existing pipeline (2 days)

**Goal:** wire the new bundle into `prepare_module_inputs.py` and verify the
downstream Python tooling still works without modification.

**Tasks:**

| ID | Task |
|---|---|
| 4.1 | Place the v2 bundle at `runs/<project>_context_bundle/` (replacing v1). Move the regex_fallback bundle to `runs/<project>_context_bundle_v1/` for parity comparison. |
| 4.2 | Run `prepare_module_inputs.py` against the v2 bundle. |
| 4.3 | Confirm that Stage-0 conditional_behavior rescues drop to ~0 (because the analyzer now anchors correctly). |
| 4.4 | Run the full test suite (`tests/test_modular_generator.py` + `tests/test_generator_lint_v1_1.py` + others). |
| 4.5 | Update `skills/benchmark-generator/SKILL.md` to reference the v2 bundle path. |

**Acceptance:**

- Stage-0 candidate substantive-coverage ratio for L2/L3 is maintained or improved vs the post-Stage-0 baseline (L1: 20/20, L2: 60/60 all-substantive; L3: ≥45/60 with ≥3 distinct substantive sources).
- All existing tests pass without modification.
- Stage-0 `_dropped_at_prepare.conditional_behavior_*` audit entries drop to near zero.

### Phase 5 — Parity + rollout (2 days)

**Goal:** demonstrate end-to-end improvement on Vortex and NVDLA, then
promote v2 to canonical.

**Tasks:**

| ID | Task |
|---|---|
| 5.1 | Run the bundle exporter on both Vortex and NVDLA. |
| 5.2 | Run prepare on both projects with the v2 bundle. Compare candidate stats (substantive coverage, L3 row count, attribute distribution) against v1. |
| 5.3 | Re-run the host-LLM authoring pipeline (M2-M9) on a 50-row Vortex smoke. Compare against the prior smoke50: did the template trap loosen? Did the per-row substance increase? |
| 5.4 | Document the new analyzer skill at `skills/benchmark-repo-analyzer/SKILL.md`. Include: invocation pattern, troubleshooting, fallback path. |
| 5.5 | Promote `runs/<project>_context_bundle/` to v2 as canonical; archive v1 to `runs/archive/<project>_context_bundle_v1/`. |

**Acceptance:**

- L3 row survival after the strict gate ≥ 15/60 on Vortex (was 2/60 in the prior smoke50).
- `conditional_behavior` axis repopulates (was 0 in the prior smoke50) with anchors at real guard tokens.
- `distracting_info` signal evidence usable end-to-end by M5/M9 (precondition for ever using the axis seriously).

### Phase 6 — RTL accuracy reinforcement (conditional, 2–4 days)

**Goal:** if Phase 0 showed tree-sitter-verilog parse rate < 95%, add
Verible as a secondary parser.

**Triggered when:** Phase 0 deliverable shows 80–95% parse rate. Skip
entirely if ≥ 95%; abort and re-plan if < 80%.

**Tasks:**

| ID | Task |
|---|---|
| 6.1 | Install Verible binary (single CLI tool). |
| 6.2 | Add a subprocess fallback inside the Verilog language module: `verible-verilog-syntax --export_json file.sv` for files tree-sitter errored on. |
| 6.3 | Merge Verible's parse-tree records into CodeGraph's graph for those files. |
| 6.4 | Per-file error rate measurement after the merge. |

**Acceptance:** per-file error rate < 1% across Vortex RTL.

---

## 5. Open decisions before kickoff

Each of these affects the plan and should be resolved before Phase 1
starts. Phase 0 can proceed with these still open.

| # | Decision | Default | When to lock |
|---|---|---|---|
| D1 | Fork CodeGraph (project-owned remote) vs work upstream from day one | Fork first; PR upstream after Phase 5 | Before Phase 1 |
| D2 | Where the analyzer skill lives in the repo | `skills/benchmark-repo-analyzer/` (parallel to `benchmark-generator/`, `benchmark-validator/`) | Before Phase 2 |
| D3 | Node.js as a build dependency for the analyzer | Acceptable (CodeGraph bundles its own runtime) | Before Phase 1 |
| D4 | CodeGraph version pinning strategy | Pin a specific commit of `colbymchenry/codegraph`; document in `analyzer-contract.md` | Before Phase 1 |
| D5 | Bundle schema versioning: extend in place vs bump to `v2.0` | Bump `relation-graph` schema to v1.1 (additive predicates); keep other schemas at v1 | Before Phase 2 |
| D6 | Whether to drop `contains` edges in the v2 bundle | Drop (they're filesystem noise) | Before Phase 2 |
| D7 | Whether to keep regex_fallback for files that tree-sitter errors on | Yes, per-file fallback retained | Before Phase 1 |

---

## 6. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| tree-sitter-verilog grammar gaps on Vortex/NVDLA | Medium | High | Phase 0 measures this. Phase 6 (Verible) handles overflow. |
| CodeGraph internal API changes during integration | Low–Medium | Medium | Pin a specific commit. Re-base from upstream periodically. |
| Verilog cross-file resolution non-trivial (dynamic `\`include` with macro args, package import via wildcard) | Medium | Medium | Document the gap; resolve what we can syntactically; flag the rest. |
| Bundle schema changes break existing prepare/M2-M9 | Low | High | Additive-only changes; bump `relation-graph` schema; keep predicate names backward-compatible. |
| Single-maintainer upstream stalls our improvements | Low | Low | Fork-first strategy. Optional upstream PR later. |
| Performance regression vs regex_fallback | Low | Low | CodeGraph indexes incrementally with FSEvents/inotify; full-rebuild on ~1500 files should be seconds. Measured in Phase 0. |
| Node.js dependency forces operational changes (CI, env setup) | Low | Medium | CodeGraph bundles its Node runtime. Confirm in Phase 0. |
| New edge predicates confuse existing consumers | Low | Low | Existing consumers iterate by predicate string; unknown predicates are simply skipped. Verified by running existing tests. |

---

## 7. Out of scope for v2

Tracked here so they don't get smuggled into the v2 effort.

- **Content-level `doc_code_divergence` detection.** Requires a comparator
  between doc claims and code behavior. Phase 3 keeps current shape with
  honest labeling. Real divergence is a follow-on analyzer feature.
- **`quantitative_aggregation` signal emission.** Likely host-LLM
  territory rather than analyzer territory. Skip.
- **`version_fork_diff` emission.** Tracked as a Phase 7 follow-on for
  NVDLA; not part of v2.
- **Test-graph extraction.** Test files are crawled but tests are not
  surfaced as candidates. Future work.
- **Multi-language `calls` edges across language boundaries** (e.g., a C
  call to a Python script through subprocess). Out of scope.

---

## 8. Cross-references

These are the artifacts in the repo that this plan depends on or
modifies. Keep these paths in sync when files move.

| Path | Role |
|---|---|
| `runs/<project>_context_bundle/` | Output location of v2 bundle (and current v1 bundle) |
| `schemas/source-inventory.schema.json` | Schema for source_inventory.jsonl |
| `schemas/entity-index.schema.json` | Schema for entity_index.jsonl |
| `schemas/relation-graph.schema.json` | Schema for relation_graph.jsonl (will bump to v1.1 in Phase 2) |
| `schemas/signal-index.schema.json` | Schema for signal_index.jsonl |
| `schemas/project-manifest.schema.json` | Schema for project_manifest.json |
| `skills/benchmark-generator/scripts/prepare_module_inputs.py` | Stage-0 consumer. Workarounds it carries (conditional_behavior_substantive_span, _find_first_substantive_line, graph_walk_neighbors) become near-no-ops after v2. |
| `benchmark_generation_design_v1.1.md` | v1.1 design that the analyzer was built against |
| `improvement_suggestions.md` | Original v1.0 → v1.1 critique that surfaced the analyzer issues |
| `doc_code_sync_evolving_rag_research.md` | Background research on doc-code consistency (context for `doc_code_divergence` follow-on) |

---

## 9. Phase status tracker

Update this section as each phase completes. Format: `phase | status | shipped-on | notes`.

| Phase | Status | Shipped on | Notes |
|---|---|---|---|
| 0 — Feasibility | not started | — | — |
| 1 — Verilog language module | not started | — | depends on Phase 0 |
| 2 — Bundle exporter | not started | — | depends on Phase 1 |
| 3 — Signal-emission layer | not started | — | depends on Phase 2 |
| 4 — Pipeline integration | not started | — | depends on Phase 3 |
| 5 — Parity + rollout | not started | — | depends on Phase 4 |
| 6 — RTL accuracy reinforcement | conditional | — | triggered only by Phase 0 result |

---

## 10. Acceptance for "v2 is done"

The migration is complete when all of the following hold simultaneously:

1. `runs/vortex_context_bundle/project_manifest.json` reports
   `analyzer_version: benchmark-repo-analyzer/v2-tree-sitter-codegraph`
   and `analysis_backends.code.used_primary: true`.
2. The same is true for NVDLA.
3. `prepare_module_inputs.py` runs without invoking Stage-0
   conditional_behavior rescues on the new bundles (rescue counter == 0
   for both projects).
4. A 50-row smoke run on Vortex (M2 through M9, host-LLM authored)
   produces ≥ 15 L3 rows that survive the strict adversarial gate.
5. The existing test suite passes against the new bundles without
   modification.
6. `skills/benchmark-repo-analyzer/SKILL.md` documents the new analyzer's
   invocation pattern and troubleshooting.

When all six are true, this plan transitions to "implemented" status and
its phase tracker is frozen for reference.
