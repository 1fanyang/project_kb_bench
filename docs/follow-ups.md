# Analyzer v2 — Non-blocking follow-ups

Recorded at the Phase 5 merge sign-off (commit `44f94f0`, 2026-06-30).
All four items are scoped after the analyzer-v2 infrastructure shipped
to canonical (`runs/<project>_context_bundle/` now serves the v2
bundle). None of them block downstream consumers; each is a quality
or scope expansion.

## Scope note from the merge

The merge that landed analyzer-v2 was sign-off for the
**analyzer/codegraph v2 infrastructure**, NOT for benchmark authoring
quality. The current adversarial gate is still a stub
(`skills/benchmark-validator/scripts/adversarial_gate.py` emits
`status: skipped_no_provider` for every row regardless of
`--judge-provider`). Real LLM-judged quality validation remains
deferred to Phase 7.

## 1. Phase 1.5b — restore finer Verilog entity kinds

Today the Verilog extractor maps `net_declaration` /
`parameter_declaration` / `data_declaration` all to
`variableTypes`, so the v2 bundle's `entity_index.jsonl` has 144
`kind=variable` entities for Vortex Verilog sources. The v1
regex-fallback bundle had:
- `kind=signal`: 4,113
- `kind=parameter`: 1,594

Both v1 kinds collapse into v2's single `kind=variable`. Downstream
consumers that filtered on `kind=signal` or `kind=parameter` see less.

Fix scope:
- Differentiate `net_declaration` -> `kind=signal`
- Differentiate `parameter_declaration` -> `kind=parameter`
- Keep `data_declaration` -> `kind=variable`

Implementation likely requires extending CodeGraph's `LanguageExtractor`
interface with `signalTypes` / `parameterTypes` slots (analogous to
the `instantiationTypes` slot added in Phase 1) so the framework can
dispatch by node-type to a non-`variable` kind without forking the
core extraction logic. Patch is bounded to:

- `tools/codegraph/src/extraction/tree-sitter-types.ts` (interface)
- `tools/codegraph/src/extraction/tree-sitter.ts` (dispatcher)
- `tools/codegraph/src/extraction/languages/verilog.ts` (move two
  node types out of `variableTypes` into the new slots)

After landing: Phase 2 bundle exporter's `remap_kind` may need a
small extension for the new CodeGraph kinds; tests should be
extended to cover both new mappings.

Trigger to actually do this: a downstream consumer (M2/M5 prompt,
linter, dashboard) explicitly filtering on `kind=signal` or
`kind=parameter` and finding zero matches. Currently no such
consumer surfaces this requirement.

## 2. Phase 3.5 — non-Verilog conditional_behavior anchors

Today's `_signals/verilog_anchors.py` re-parses Verilog source only.
C++ and Python conditional sites (`if_statement`, `switch_statement`,
etc.) are not surfaced as `conditional_behavior` signals — the v2
bundle's `signal_index.jsonl` has zero C++/Python conditional anchors.

This was a design choice: tree-sitter-verilog was already installed
for Phase 0, so reusing it via Python binding was zero-cost. Adding
C++/Python anchors requires installing more tree-sitter Python
bindings AND deciding which AST node kinds in each grammar map to
`conditional_behavior`.

Three implementation options when this becomes needed:
- Install `tree-sitter-cpp` / `tree-sitter-python` Python bindings;
  add a `_cpp_reparse.py` / `_python_reparse.py` module
  mirroring `_verilog_reparse.py`; expand the emitter dispatch.
- Extend CodeGraph's extractor with a control-flow anchor slot so
  conditional sites surface as entities at index time. More
  invasive than option 1.
- Use CodeGraph's existing `calls` edge density as a heuristic
  proxy for "conditional behavior" — coarsest, but free.

Trigger: Phase 5 measurement found 39/60 Vortex L3 rows are
C++-anchored. None failed the structural gate (all 60 L3 rows
passed), so the gap isn't currently visible in survival metrics.
Re-evaluate if the L3 query-quality bar tightens in a future release.

## 3. Phase 7 — replace adversarial_gate.py stub with a real LLM-judged gate

`skills/benchmark-validator/scripts/adversarial_gate.py` currently
unconditionally emits `dry_run_record` entries with
`status: "skipped_no_provider"`. Even passing `--judge-provider deepseek`
or `--judge-provider command` doesn't change behavior — the script
lacks any judge-call code path.

What "real adversarial gate" means here:
- For each row's claimed difficulty attribute (axis2 + axis3),
  build a baseline (closed-book LLM, oracle-evidence LLM, top-1
  dense retrieval, etc. per `ATTRIBUTE_BASELINES` in the stub).
- Run the baseline against the row's question; capture the answer.
- Ask an LLM judge whether the baseline's answer is materially
  worse than the row's authored expected_answer (with rubric).
- If yes: the attribute claim is "confirmed" — the row is a real
  axis-3 question, the baseline can't shortcut it.
- If no: the claim is "rejected" — the question is too easy for
  the baseline and the row should be dropped or relabeled.

Implementation scope:
- Add baseline executor for each baseline type (closed_book_llm,
  oracle_evidence_no_reasoning_llm, top_1_dense_only, etc.).
- Add judge-call code path (likely Codex `exec` with a strict JSON
  output schema, similar to scripts/run_v1_2_llm_bundle.py's
  per-stage prompt pattern).
- Wire `--judge-provider` to actually select between the available
  judge backends.
- Cache verdicts by `cache_key` so re-runs don't re-spend tokens.

Trigger: any consumer demanding the original v2 acceptance bar of
"L3 row survival ≥ 15/60 under the strict adversarial gate." The
Phase 5 sign-off used the structural gate as a proxy (60/60 pass);
that's adequate for analyzer infrastructure sign-off but not for a
release-grade benchmark quality claim.

## 4. L2 authoring quality — M2/M5/M6 prompt tuning

The Phase 5 smoke50 on Vortex produced 88 L2 rows (2 dropped at M2
for empty selected_evidence). The structural gate failed 72/88
across two reason codes:

| reason | count | meaning |
|---|---|---|
| INSUFFICIENT_DIFFICULTY_SIGNALS | 53 | row claimed only 1 difficulty signal across axes; v1.1 requires ≥ 2 |
| CONDITIONAL_BEHAVIOR_WITHOUT_ROLE | 20 | row claimed `conditional_behavior` attribute but its evidence atoms lacked the `role: trigger_condition` tag |

Neither is a v2 bundle defect — both are M2/M5/M6 LLM-authoring
quality issues. The release v1 benchmark on disk has 200/200 pass,
but it was tuned to that via manual review; a fresh v1 smoke50
likely shows similar L2 attrition.

Fix scope (LLM prompt edits, no schema changes):
- M2 prompt — emphasize that the row must select at least one
  axis-2 AND at least one axis-3 candidate; show a positive example.
- M5 prompt — when conditional_behavior is in the row's attribute
  set, require at least one evidence atom to carry
  `role: trigger_condition`.
- M6 prompt — same check from the rubric side; flag rows where the
  rubric doesn't reference a guard/branch/predicate when
  conditional_behavior is claimed.

Trigger: any release-quality smoke50 where L2 pass rate is below
~80%. Today's 18% (16/88) would benefit, but L2 isn't load-bearing
for the v2 acceptance bar.

## Cross-cutting: other follow-ups previously filed

These are recorded elsewhere but worth surfacing:

- **Phase 1.5a** — `text_macro_definition` not yet routed in
  `verilogExtractor`. v1's `kind=macro` row count (~1,700 on Vortex)
  not yet recovered. Same fix-shape as Phase 1.5b: a new dispatch
  slot in the framework + extractor edit.
- **Phase 6** — Verible fallback for 9 hard-error Vortex files
  (DPI headers, `VX_trace_pkg.sv`, AFU wrap, `VX_uop_sequencer.sv`,
  interface files) + anchor-rotation cap for `VX_cluster.sv:48-50`
  (which the smoke50 reused 61×). Already SCHEDULED in the master
  plan § 9; this is the next slice of work.
