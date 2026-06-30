# Analyzer v2 Phase 4 — Acceptance

Date: 2026-06-29
Phase 4 path: "ignore and ship" — `signal_dataflow` records from
Phase 3 are accepted at load time but dropped silently before
selection, so no axis-filter logic changes.

## Acceptance metrics (live Vortex)

prepare runs end-to-end against `runs/vortex_context_bundle_v2/`:

| metric                                          | v1 baseline | v2 bundle | delta |
|---|---|---|---|
| candidate rows written                          | 200 | 200 | 0 |
| L1 rows with candidates                         | 20/50 | 20/50 | 0 |
| L2 rows with candidates                         | 90/90 | 90/90 | 0 |
| L3 rows with candidates                         | 60/60 | 60/60 | 0 |
| L2 distinct candidate sources                   | 278 | 326 | +17% |
| L3 distinct candidate sources                   | 187 | 257 | +37% |
| Stage-0 `conditional_behavior_rescued` count    | 61 | **0** | -100% |
| Stage-0 `conditional_behavior_dropped` count    | 87 | **0** | -100% |
| Rows with any Stage-0 audit entry               | 113 | **0** | -100% |
| `signal_dataflow` records dropped at load       | n/a | 3,781 | tolerated |
| Diversity warnings (path:lines over cap 3)      | 7  | 14  | +7 |
| Diversity warnings (anchors over cap 5)         | 7  | 8   | +1 |

Two load-bearing acceptance bars from the Phase 4 plan are met:
**Stage-0 conditional_behavior rescue counter dropped from 61 → 0**,
**Stage-0 conditional_behavior drop counter dropped from 87 → 0**.

These two zero numbers are the headline acceptance: the v2 bundle's
AST-anchored conditional_behavior signals never land in the
license-zone, so the Stage-0 workaround (re-reading source spans to
escape from license blocks) never has to fire. The workaround code in
`prepare_module_inputs.py` is still in place — it's now dormant
defense-in-depth.

## Acceptance bullets (Phase 4 plan + user direction)

- [x] `prepare_module_inputs.py` accepts `--bundle-path`; default
      behaviour preserved (no flag => same as before).
- [x] `tests/test_prepare_v2_bundle_smoke.py` passes — 6 tests covering
      bundle-path acceptance, unknown-attribute tolerance, group
      stability, and zero rescues on v2.
- [x] Vortex Stage-0 conditional_behavior rescue counter == 0 (was 61).
- [x] Vortex Stage-0 conditional_behavior drop counter == 0 (was 87).
- [x] L1=20/50, L2=90/90, L3=60/60 substantive coverage maintained.
- [x] `signal_dataflow` (3,781 records) tolerated at load time and
      dropped silently to stdout under "Phase 4 ignore-and-ship" tag —
      no axis-filter logic changes (the user's ask #1).
- [x] `PREFERRED_ATTRIBUTE_GROUPS` content bit-stable. Asserted by
      `PreferredAttributeGroupsStableTest` (the user's ask #2).

## What changed in this phase

`scripts/generate_v1_1_release_corpora.py`:
- New `KNOWN_AXIS_ATTRIBUTES` frozenset (7 entries) gating
  `load_signals`. Unknown attributes silently drop and (optionally)
  increment a counter.

`skills/benchmark-generator/scripts/prepare_module_inputs.py`:
- New `--bundle-path` CLI flag (default: previous v1 path).
- Threads a drop-counter dict into `load_signals`; prints a
  per-attribute summary to stdout when any drops occurred.

`skills/benchmark-repo-analyzer/scripts/codegraph_to_bundle.py`
(Phase 2 follow-up that surfaced here):
- `_line_count` now reads files from disk to emit real line counts.
  Old `line_count: 0` failed prepare's `is_generation_source` filter
  (which rejects rows with `line_count <= 0`).

`skills/benchmark-generator/SKILL.md`:
- New "v2 bundle invocation (opt-in)" subsection documenting the
  `--bundle-path` flag and the `signal_dataflow` ignore behavior.

## Phase 5 measurement requests (per Phase 4 user direction)

When the smoke50 host-LLM run lands in Phase 5, please measure
explicitly:

1. **L3 "signal write" row survival under the strict adversarial
   gate.** Identify rows whose generated query is about a Verilog
   signal write (e.g. "what condition triggers a write to `q`?"). For
   each, note whether it survived the gate, and if not, attribute the
   failure cause.

2. **Failure attribution to axis-coverage gaps.** For any L3 failures,
   inspect whether the row had access only to entity-anchored signals
   (long_tail / distracting_info) and missed the source-anchored
   conditional_behavior signal it needed. If yes, that's evidence to
   wire `signal_dataflow` as a third axis-3 attribute. If no
   (failures are due to query quality, evidence sparsity, or other),
   keep `signal_dataflow` ignored — Phase 1.5b (finer
   signal/parameter extraction) will likely close the gap better than
   adding a new axis.

3. **Diversity-warning growth.** The v2 prepare doubled the
   path:lines-over-cap count (7 → 14). Spot-check 3 of the new
   warnings; if they all come from one or two prolific Verilog files
   (e.g. `VX_trace_pkg.sv`), this is a known concentration not a
   regression. If they spread across many files, the v2 entity-set
   has materially shifted the candidate distribution; document for
   Phase 6.

## Phase 5 GO

**GO.** The full pipeline runs against the v2 bundle end-to-end. The
license-zone regression is fixed. Phase 5 (parity + rollout) can
proceed.

## Non-blocking follow-ups still filed

- Phase 1.5a — macro extraction
- Phase 1.5b — finer signal/parameter extraction
- Phase 3.5 — non-Verilog conditional_behavior anchors (C++/Python)
