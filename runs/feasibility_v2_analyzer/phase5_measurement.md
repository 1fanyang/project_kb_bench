# Analyzer v2 Phase 5 — Measurement-first report

Date: 2026-06-29
Scope: measurement only (no host-LLM tokens spent). The user-gated
decisions at the end of this doc determine whether to launch a real
Codex smoke50 + whether to wire `signal_dataflow` as a new axis.

## 1. Cross-project parity (Vortex + NVDLA, v1 vs v2 bundles)

NVDLA v2 bundle was built fresh in this phase:
`runs/nvdla_context_bundle_v2/` (1,440 sources, 52,729 entities,
166,458 relations, 191,184 signals; validator: 0 FAIL / 0 WARN).

### Stage-0 conditional_behavior rescue+drop counters (the load-bearing v2 fix)

| project | v1 cb_rescued | v2 cb_rescued | v1 cb_dropped | v2 cb_dropped |
|---|---|---|---|---|
| Vortex | 61 | **0** | 87 | **0** |
| NVDLA  | 23 | **0** | 125 | **0** |

The license-zone regression is gone on both projects. Total drops + rescues
went from 296 (v1) to 0 (v2).

### Distinct candidate sources per layer

| project | layer | v1 distinct | v2 distinct | delta |
|---|---|---|---|---|
| Vortex | L1 | 42 | 20 | -52% |
| Vortex | L2 | 278 | 326 | +17% |
| Vortex | L3 | 187 | 257 | +37% |
| NVDLA  | L1 | 20 | 20 | 0 |
| NVDLA  | L2 | 180 | 387 | +115% |
| NVDLA  | L3 | 120 | 241 | +101% |

L1 dipped on Vortex (the v1 bundle had richer macro/parameter entities
that L1 happily picked); L2 and L3 grew substantially on both projects.
The L3 growth on NVDLA is dramatic — the v2 extractor exposes
significantly more Verilog modules than v1's regex-fallback ever did.

## 2. L3 "signal-write" axis-coverage audit (the Phase 5 ask)

Question: do L3 rows whose anchor is on a Verilog signal-write site
have adequate axis-3 coverage in the current bundle, or do they need
`signal_dataflow` wired as a third axis-3 attribute?

Vortex v2 L3 rows (60 total):
- 39 are anchored on C++ code (sim/simx/core.h etc.) — not "signal
  write" rows, scope excluded.
- 21 are anchored on Verilog sources — the candidate set for
  signal-write style L3 questions.

Of those 21 Verilog L3 rows:
- **21/21 already have `conditional_behavior` as an axis-3 attribute**
- **21/21 have a write-site within ±5 lines of the row's anchor**
- 0/21 lack axis-3 coverage

### Implication for the wiring decision

**Wiring `signal_dataflow` as a third axis-3 attribute would NOT add
coverage to any row that currently lacks axis-3 coverage** — because no
Verilog L3 row in the current v2 bundle is missing axis-3 coverage. The
existing `conditional_behavior` attribute already lands on conditional
sites that sit adjacent to write sites, which is exactly the context a
signal-write L3 question needs.

The only thing wiring `signal_dataflow` would change is:
- Increase the axis-3 attribute pool from 4 to 5 (adds variety to
  `PREFERRED_ATTRIBUTE_GROUPS` rotation)
- Potentially crowd out `conditional_behavior` selection on rows where
  both are eligible (could regress query quality if the question
  authoring stage prefers control-flow context over write-site context)

**Recommendation:** keep `signal_dataflow` ignored unless an actual
Codex smoke50 produces L3 signal-write failures whose root cause is
"axis-3 missing." If failures show evidence/query/rubric issues
instead, Phase 1.5b (finer signal/parameter extraction → restoring
`kind=signal` / `kind=parameter` entity rows) is the better follow-up.

## 3. Diversity-warning growth (the Phase 5 ask)

Vortex v1 path:lines-over-cap warnings: 7
Vortex v2 path:lines-over-cap warnings: 14

### Concentration analysis

**v1 (7 warnings)** — concentrated in 4 RTL `.vh` define headers + 3 doc files:

| count | key |
|---|---|
| 62 | `hw/rtl/VX_define.vh:21-23` |
| 56 | `hw/rtl/VX_platform.vh:17-19` |
| 19 | `hw/rtl/fpu/VX_fpu_define.vh:19-21` |
| 17 | `hw/rtl/cache/VX_cache_define.vh:19-21` |
| 8  | `docs/continuous_integration.md:18-20` |
| 7  | `docs/cache_subsystem.md:3-5` |
| 6  | `README.md:19-21` |

**v2 (14 warnings)** — one major outlier + 13 broadly distributed:

| count | key |
|---|---|
| 61 | `hw/rtl/VX_cluster.sv:48-50` ← outlier |
| 12 | `sim/simx/types.h:32-34` |
| 11 | `sim/simx/core.h:38-40` |
| 10 | `sim/simx/instr_trace.h:24-26` |
| 9  | `runtime/common/nlohmann_json.hpp:99-101` |
| 7  | `sim/common/mem.h:31-33` |
| 7  | `sim/common/util.h:26-28` |
| 6  | `sim/common/simobject.h:27-29` |
| 5  | `tests/opencl/blackscholes/oclUtils.h:72-74` |
| 4  | `hw/unittest/common/vl_simulator.h:24-26` |
| 4  | `runtime/common/common.h:46-48` |
| 4  | `sim/simx/cluster.h:25-27` |
| 4  | `sim/simx/arch.h:23-25` |
| 4  | `sim/simx/emulator.h:30-32` |

**Verdict:** Mixed. v2 has 14 distinct (path, lines) anchors over the
cap of 3 — one per warning, so the "files concentrated?" measure is
"all 14 are distinct, plus one outlier." That outlier
(`VX_cluster.sv:48-50` at 61 reuses) is the v2 equivalent of v1's
`VX_define.vh` concentration — a single central file getting picked
for many rows. The other 13 warnings are sim/simx infrastructure
headers (4–12 reuses each), which IS a broader distribution than v1.

The shift from "RTL `.vh` define headers" (v1) to "C++ sim/simx
infrastructure" (v2) reflects what CodeGraph actually indexes: it
doesn't extract the regex-derived macro/parameter pseudo-entities
from `.vh` define headers, so those don't get picked as anchors any
more. Instead the picks land on real C++ entities in the sim layer.
**This is a candidate-distribution shift, not a regression.** Phase 6
might tighten the anchor-rotation logic for `VX_cluster.sv:48-50`
specifically (one anchor with 61 row-uses is too many), but it's not
blocking Phase 5.

## 4. What the structural audit cannot answer

Without an actual host-LLM smoke50 (M2-M9 + structural + adversarial
gate), I cannot measure:

- **Actual L3 row survival** under the strict adversarial gate
- **Real failure attribution** — query-quality issues, rubric
  contradictions, expected-answer drift, etc. only surface when a real
  LLM authors the rows
- **Whether the v2 candidate-set authors L3 rows that survive at a
  higher rate than v1** (the v2 acceptance bar of ≥15/60 in the
  original plan)

The structural audit predicts:
- The Stage-0 substantive filter should reject ~0 rows in v2 (vs v1's
  ~95 drops+rescues per project) → v2's M2-M9 pipeline starts from a
  cleaner candidate set.
- Verilog L3 rows have full axis-3 coverage → no row should fail the
  axis-claim check.
- C++ L3 rows are 39/60 — these are evidence-fact rows, and their
  survival depends on whether the L3 authoring stage can pose
  reasoning questions over C++ infrastructure code. v2 vs v1 affects
  this primarily through the L3 distinct-source count (187 → 257 =
  +37%).

## 5. Decision gates for the user

### Decision A — run a real Codex smoke50 now?

A real run requires:
- `scripts/run_v1_2_llm_bundle.py` invocation with `--project vortex`
  against the v2 bundle. The script calls `codex exec --model gpt-5.4-mini`
  per M-stage (M2/M3/M5/M6/M7). On Vortex 50-row smoke this is roughly
  5 stages × ~50-row batches → ~10-20 minutes wall-clock, $X in
  tokens (depends on your Codex billing).
- Followed by the structural gate
  (`skills/benchmark-validator/scripts/validate_benchmark.py`) and
  the adversarial gate
  (`skills/benchmark-validator/scripts/adversarial_gate.py`).

Recommendation: **YES, run it** — the structural audit predicts good
outcomes but the original v2 acceptance bar (L3 row survival ≥ 15/60)
needs a real number. I can run this if you give me the go-ahead on
token spend, OR you can run it yourself with the command I'll provide.

### Decision B — wire `signal_dataflow` as a third axis-3 attribute?

Based on Section 2, my recommendation is **NO, not yet**:
- 21/21 Verilog L3 rows already have axis-3 coverage via
  `conditional_behavior`
- 21/21 are within ±5 lines of a signal-write site (so the existing
  conditional_behavior context naturally covers write semantics)
- Wiring `signal_dataflow` would change rotation patterns without
  adding any "rescued" rows

Revisit ONLY if Decision A's Codex smoke50 produces L3 signal-write
failures whose root cause is "the row had no axis-3 attribute that
spoke to signal writes specifically."

### Decision C — promote v2 to canonical (the Phase 5.6 step)?

The original Phase 5 plan calls for `git mv runs/vortex_context_bundle/
runs/archive/vortex_context_bundle_v1/` and `git mv
runs/vortex_context_bundle_v2/ runs/vortex_context_bundle/` AFTER
Decision A's gate passes. I'm holding off until you sign off.

## 6. Non-blocking follow-ups (still filed)

- Phase 1.5a — macro extraction (`text_macro_definition` entities)
- Phase 1.5b — finer signal/parameter extraction
  (`net_declaration` → `kind=signal`, `parameter_declaration` →
  `kind=parameter`). This is the better lever for restoring v1's
  `kind=signal`/`kind=parameter` coverage than wiring signal_dataflow.
- Phase 3.5 — non-Verilog conditional_behavior anchors (C++/Python).
- Phase 5.5 — npm-audit of CodeGraph 1.1.1 dependencies (must
  complete BEFORE Decision C promotion).
- Phase 6 — Verible fallback for the 9 hard-error Vortex files.

## 7. Phase 5 progress

| step | status |
|---|---|
| 5.1 Re-index both projects with v2 | DONE (Vortex+NVDLA bundles built, validator clean) |
| 5.2 Candidate-stat parity report | DONE (this doc § 1) |
| 5.3 Real Codex smoke50 on Vortex | PENDING USER DECISION A |
| 5.4 Smoke50 v2 vs v1 comparison | PENDING DECISION A |
| 5.5 npm-audit security review | PENDING DECISION A |
| 5.6 Promote v2 to canonical | PENDING DECISION C |
| 5.7 Phase 5 acceptance report | PENDING (this doc is the measurement-first slice) |

Master plan tracker for Phase 5 is not flipped to "complete" yet —
this report covers the measurement subset the user requested.
