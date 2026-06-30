# Analyzer v2 Phase 3 — Acceptance

Date: 2026-06-29
Bundle: `runs/vortex_context_bundle_v2/` (Phase 2 output)
Emitter: `skills/benchmark-repo-analyzer/scripts/signal_emitter.py`
Re-parser: `skills/benchmark-repo-analyzer/scripts/_verilog_reparse.py`
(uses the Phase 0 PyPI `tree-sitter-verilog==1.0.3` binding)

## Acceptance metrics (live Vortex run)

Total signals after dedup: **13,259** — all schema-valid.

| attribute                     | count | extractor                          | confidence |
|---|---|---|---|
| long_tail                     | 5,119 | bundle_inbound_count_v2            | 0.95 |
| signal_dataflow               | 3,781 | verilog_tree_sitter_reparse_v2     | 0.95 |
| distracting_info              | 2,618 | bundle_name_collision_v2           | 0.95 |
| conditional_behavior          | 1,530 | verilog_tree_sitter_reparse_v2     | 0.95 |
| implicit_domain_knowledge     | 211   | rtl_or_hls_language_heuristic_v2   | 0.7  |
| non_code_anchor               | 0     | bundle_modality_filter_v2          | 0.95 |
| doc_code_divergence           | 0     | bundle_doc_mention_v2              | 0.7  |

(`non_code_anchor` and `doc_code_divergence` produce 0 because the v2
bundle has no script/config/build-modality entities and no
`doc_mentions_entity` relations — both gaps inherited from CodeGraph's
extraction scope. Documented further down.)

## Acceptance bullets (from the Phase 3 ask + plan)

- [x] **Zero `conditional_behavior` anchors in lines 1–10** (the v1
      license-zone bug). Counted across all 1,530 records: 0 found in
      the file-header zone. This is THE load-bearing regression fix.
- [x] **All `conditional_behavior` and `signal_dataflow` records carry
      both `extractor: verilog_tree_sitter_reparse_v2` AND
      `evidence.provenance: tree_sitter_verilog_reparse_v2`** so
      downstream consumers can distinguish them from bundle-derived
      signals (Phase 3 ask #2).
- [x] **v2 bundle schema unchanged.** All 13,259 records validate
      against the existing `schemas/signal-index.schema.json`. No
      schema files were modified in Phase 3 (Phase 3 ask #3).
- [x] **Tests cover all four ask categories** (Phase 3 ask #4):
      `test_verilog_reparse.py` has unit tests for always-if, nested
      if/else, case statements, and signal R/W; plus a dedicated
      `test_anchor_lines_skip_the_license_header_zone` regression test.
      `test_signal_emitter.py` adds 5 integration tests including
      provenance marking and schema stability.
- [x] **`distracting_info` evidence shape preserved.** All
      `distracting_info` records carry `collision_sources`,
      `collision_source_count`, `total_entities_with_name` — the v1
      shape that `prepare_module_inputs.py`'s `graph_walk_neighbors`
      and M9's prompt assembler read.
- [x] **Extractor framework was not extended** (Phase 3 ask #1). The
      Verilog re-parser is a standalone Python module; the CodeGraph
      Verilog extractor in `tools/codegraph/` was not touched.

## Test results

`tests/test_verilog_reparse.py` — 8 unit tests, all pass:
- AlwaysIfTest (1)
- NestedIfElseTest (2 — including the license-zone regression test)
- CaseStatementTest (1)
- SignalDataflowTest (4 — continuous_assign, RHS dedup, blocking vs
  nonblocking classification, empty-input safety)

`tests/test_signal_emitter.py` — 5 integration tests, all pass:
- AlwaysIfIntegrationTest (asserts >5-line anchors)
- SignalDataflowIntegrationTest (3 assignments expected; LHS/RHS shape)
- ProvenanceMarkingTest (extractor + evidence.provenance tags)
- SchemaStabilityTest (signal-index.schema.json validation)
- DistractingInfoEvidenceShapeTest (collision_sources et al.)

Full project test suite: 166 passed, same 4 pre-existing failures in
`tests/test_modular_generator.py` (untouched by Phase 3).

## Signal coverage by code path

### Verilog (load-bearing, the conditional_behavior bug-fix path)

- 1,530 conditional_behavior anchors across 211 Verilog files —
  average 7 anchors per file.
- 3,781 signal_dataflow anchors — average 18 write sites per file.
- 0 of either category anchored in the file-header / license-block
  zone. (Sample inspection: anchors land at lines like 48-51,
  409-415, etc. — real RTL line ranges.)
- Provenance: every record carries
  `extractor: verilog_tree_sitter_reparse_v2` and
  `evidence.provenance: tree_sitter_verilog_reparse_v2`.

### Bundle-derived signals (work as designed)

- `long_tail`: 5,119 — entities with ≤3 inbound edges. Confidence 0.95
  (inbound count is exact from the relation graph).
- `distracting_info`: 2,618 — name collisions across sources, with
  full evidence shape for downstream consumers.
- `implicit_domain_knowledge`: 211 — one per Verilog source.

### Gaps inherited from the v2 bundle scope (NOT Phase 3 bugs)

- **`non_code_anchor: 0`** — the v2 bundle's entity_index has no
  entities anchored in non-code modalities (script/config/build).
  CodeGraph only file-level-tracks YAML and skips shell / tcl /
  cmake / makefile entirely. For now this signal is dormant on
  CodeGraph-indexed projects. Downstream consumers should not assume
  parity with v1 here.
- **`doc_code_divergence: 0`** — CodeGraph doesn't emit a
  `doc_mentions_entity` predicate. The Phase 3 emitter listens for it
  exactly so the day a doc extractor lands (Phase 7+ work,
  out-of-scope here) the signals flow through unchanged.

These two zero-count signals are NOT defects in the Phase 3 emitter —
they are accurate "no input data" results, and the emitter is wired
correctly to emit when the inputs arrive.

## Documented reduced coverage (carry forward to Phase 4 docs)

Per the Phase 3 brief, downstream consumers must be told that
`kind=signal` and `kind=parameter` coverage is currently reduced
relative to v1. The v2 bundle (from Phase 2) has:

- v1 had 4,113 `kind=signal` entities (regex-extracted from Verilog
  `wire`/`reg` declarations). v2 has 0 — they're lumped into
  `kind=variable` (144 records). Phase 1.5b will recover this.
- v1 had 1,594 `kind=parameter` entities. v2 has 0 — same reason.
  Phase 1.5b.
- v1 had 1,711 `kind=macro` entities. v2 has 0 — `text_macro_definition`
  isn't routed by the Phase 1 extractor. Phase 1.5a.

The Phase 3 `signal_dataflow` records partially compensate for the
missing `kind=signal` entities by surfacing the signal *names* at
assignment sites — a more behavioral view than the v1 declaration-site
view. Downstream consumers writing benchmark questions about Verilog
signals should prefer the new `signal_dataflow` records for write-site
identity over the missing `kind=signal` entities.

## Non-blocking follow-ups (filed, not blocking Phase 4)

- **Phase 1.5a — macro extraction.** Wire `text_macro_definition` into
  the Verilog extractor as a new entity kind. Will recover the v1
  `kind=macro` row count (~1,700 entities on Vortex).
- **Phase 1.5b — finer signal/parameter extraction.** Differentiate
  `net_declaration` (`kind=signal`), `data_declaration` (`kind=variable`),
  and `parameter_declaration` (`kind=parameter`) in the extractor.
  Will restore v1 entity-kind names that downstream consumers may filter on.
- **Phase 3.5 — non-Verilog conditional_behavior.** Today's
  conditional_behavior is Verilog-only (re-parse path). C++/Python
  conditional sites are not anchored. Three options when this becomes
  needed: (a) add tree-sitter Python bindings for those languages and
  re-parse, (b) extend CodeGraph's extractor with a control-flow slot,
  (c) use CodeGraph's existing `calls` edge density as a heuristic
  proxy. Defer until measurement shows the gap matters.

## Phase 4 GO

**GO.** The signal index is bit-correct against the existing schema,
the load-bearing conditional_behavior regression is fixed, and the
distracting_info evidence shape preserves backward compatibility.
Phase 4 (pipeline integration — wire the v2 bundle into
`prepare_module_inputs.py`, measure Stage-0 audit, confirm L1/L2/L3
substantive coverage) can start.

Heads-up for Phase 4: when `prepare_module_inputs.py` reads the
`signal_index.jsonl`, it should treat
`extractor: verilog_tree_sitter_reparse_v2` records as AST-derived
(confidence floor 0.95). Records with other extractors are
heuristic/bundle-derived (confidence floors apply per emitter). The
`signal_dataflow` records are new — they may or may not be useful for
the existing Stage-0 selection logic, which currently does not key on
them. Either ignore them in Phase 4 and revisit, or wire them through
as a new axis for L3 signal-write-question rows.
