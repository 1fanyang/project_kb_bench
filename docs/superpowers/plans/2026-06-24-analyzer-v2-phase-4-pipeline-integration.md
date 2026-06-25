# Analyzer v2 — Phase 4: Pipeline Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Sketched plan — Phase 3 must ship first.** This phase reads from `runs/{vortex,nvdla}_context_bundle_v2/` and stops short of promoting v2 to the canonical bundle path (that's Phase 5). All work in this phase happens *behind* an opt-in `--bundle-path` flag so the existing pipeline is not disturbed.

**Goal:** Wire the v2 bundle into `prepare_module_inputs.py`, run the full Vortex and NVDLA prepare passes against it, and verify the downstream Python tooling (M2-M9, lint, validator, generator tests) still works without modification. The success bar is the v2-bundle Stage-0 audit showing the conditional_behavior-rescue counter drops to near zero — direct evidence that the analyzer-side fix worked.

**Architecture:** `prepare_module_inputs.py` currently reads the bundle from a hard-coded path. Phase 4 introduces a single new CLI flag (`--bundle-path` default `runs/<project>_context_bundle/`) so the script can point at the v2 bundle without renaming directories. No other prepare code changes; the v2 bundle's record shape is already compatible (Phase 2 acceptance verified this). Stage-0 workarounds stay in place as defense-in-depth — Phase 4 measures whether they become no-ops, but does not remove them (deletion is a separate cleanup once two consecutive prepare runs show zero rescues).

**Tech Stack:** existing Python `prepare_module_inputs.py`, existing pytest suite, no new dependencies.

## Global Constraints

- Do not delete or rename v1 bundle directories. v2 lives at `runs/{vortex,nvdla}_context_bundle_v2/` for this phase; Phase 5 owns the swap.
- Do not remove the Stage-0 workarounds (`conditional_behavior_substantive_span`, `_find_first_substantive_line`, `graph_walk_neighbors`) in this phase. Measure their hit-rate first; removal is a separate task after two clean runs.
- The existing `tests/` suite must pass unchanged. Any change to a test (other than adding new ones) is a regression to be debugged, not a test update.
- All prepare invocations against the v2 bundle log to `runs/v2_prepare_logs/` so the audit data survives a re-run.

---

## File Structure

Create:

- `runs/v2_prepare_logs/` — output directory for the Stage-0 audit JSONs and prepare stdout/stderr captures.
- `tests/test_prepare_v2_bundle_smoke.py` — a lightweight test that asserts prepare-against-v2-bundle exits 0 on a fixture mini-bundle.

Modify:

- `skills/benchmark-generator/scripts/prepare_module_inputs.py` — add `--bundle-path` (default `runs/<project>_context_bundle/`) so the script can be pointed at the v2 dir without renaming.
- `skills/benchmark-generator/SKILL.md` — reference the v2 bundle invocation example (right after the existing v1 example).
- `skills/benchmark-generator/references/generator-contract.md` — note v2 bundle compatibility.
- `analyzer_v2_codegraph_treesitter_plan.md` § 9 — flip Phase 4 row to `complete`.

Do not modify:

- Any other prepare/M2-M9/lint/validator scripts. Phase 2 verified the bundle shape; if a consumer doesn't understand a v2 record, that's a Phase 2 bug to fix in the exporter, not a Phase 4 patch in the consumer.
- The Stage-0 workaround functions inside `prepare_module_inputs.py`.

---

### Task 1: Add `--bundle-path` to prepare_module_inputs.py

**Files:**
- Modify: `skills/benchmark-generator/scripts/prepare_module_inputs.py`
- Create: `tests/test_prepare_v2_bundle_smoke.py`
- Create: `tests/fixtures/prepare_v2_bundle_mini/` — a 2-source, 2-entity, 2-relation, 1-signal hand-built v2 bundle.

**Interfaces:**
- Consumes: existing prepare CLI; the fixture mini-bundle.
- Produces: prepare can read from any directory matching the v2 bundle shape. Tasks 2 and 3 use this flag.

- [ ] **Step 1: Locate the hard-coded bundle path in prepare**

```bash
grep -n 'context_bundle' skills/benchmark-generator/scripts/prepare_module_inputs.py | head
```

Expected: one or two lines hard-coding `runs/<project>_context_bundle/`. Note the variable / constant name.

- [ ] **Step 2: Add the flag (no behaviour change yet)**

Edit the script to introduce an `argparse` flag:

```python
ap.add_argument(
    "--bundle-path",
    default=None,
    help="Path to context bundle dir; defaults to runs/<project>_context_bundle/",
)
# ... later, where the path is constructed:
bundle_path = Path(args.bundle_path) if args.bundle_path \
              else Path(f"runs/{args.project}_context_bundle")
```

Do not touch the rest of the script.

- [ ] **Step 3: Build the fixture mini-bundle**

`tests/fixtures/prepare_v2_bundle_mini/` containing:

- `source_inventory.jsonl` (2 lines: one cpp, one verilog)
- `entity_index.jsonl` (2 lines: one cpp function, one verilog module)
- `relation_graph.jsonl` (2 lines: one `defines`, one `instantiates`)
- `signal_index.jsonl` (1 line: a `conditional_behavior` signal anchored at line 42 — well outside the file-header zone)
- `project_manifest.json` (with `analyzer_version: benchmark-repo-analyzer/v2-tree-sitter-codegraph`)

Hand-author each file.

- [ ] **Step 4: TDD: smoke test**

```python
# tests/test_prepare_v2_bundle_smoke.py
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/benchmark-generator/scripts/prepare_module_inputs.py"
FIX = ROOT / "tests/fixtures/prepare_v2_bundle_mini"


def test_prepare_accepts_v2_bundle_path(tmp_path):
    out = tmp_path / "prepare_out"
    r = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--project", "fixture",
         "--bundle-path", str(FIX),
         "--out-dir", str(out)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
```

Run, watch fail (flag doesn't exist OR prepare expects more fields).

- [ ] **Step 5: Iterate the fixture until prepare exits 0**

If prepare errors on a missing required field, add it to the fixture rather than weakening the schema. Each missing field is a real Phase 2 gap to record in `runs/feasibility_v2_analyzer/phase4_acceptance.md`.

- [ ] **Step 6: Commit**

```bash
git add skills/benchmark-generator/scripts/prepare_module_inputs.py \
        tests/fixtures/prepare_v2_bundle_mini/ \
        tests/test_prepare_v2_bundle_smoke.py
git commit -m "feat(analyzer-v2/phase-4): prepare --bundle-path flag for v2 opt-in"
```

---

### Task 2: Run prepare against Vortex v2 bundle and capture Stage-0 audit

**Files:**
- Create (by running): `runs/v2_prepare_logs/vortex_prepare.log`, `runs/v2_prepare_logs/vortex_stage0_audit.json`, and whatever prepare normally writes to the per-project out-dir, redirected to `runs/v2_prepare_logs/vortex_prepare_out/`.

**Interfaces:**
- Consumes: `runs/vortex_context_bundle_v2/` (Phase 2/3 output); the `--bundle-path` flag from Task 1.
- Produces: a prepare audit JSON showing per-axis Stage-0 drop counts. Task 6 reads these.

- [ ] **Step 1: Run prepare**

```bash
mkdir -p runs/v2_prepare_logs/vortex_prepare_out
uv run python skills/benchmark-generator/scripts/prepare_module_inputs.py \
    --project vortex \
    --bundle-path runs/vortex_context_bundle_v2/ \
    --out-dir runs/v2_prepare_logs/vortex_prepare_out/ \
    2>&1 | tee runs/v2_prepare_logs/vortex_prepare.log
```

Expected: exit 0; the out-dir contains the same per-module input files prepare normally writes.

- [ ] **Step 2: Locate / extract the Stage-0 audit**

prepare writes an audit (look for `_dropped_at_prepare` or similar in the source). Confirm the path:

```bash
grep -rn '_dropped_at_prepare\|stage0\|stage_0' \
    skills/benchmark-generator/scripts/prepare_module_inputs.py | head
ls runs/v2_prepare_logs/vortex_prepare_out/ | grep -i audit
```

Copy the audit (or grep the log) to a stable path:

```bash
cp runs/v2_prepare_logs/vortex_prepare_out/<audit-file> \
   runs/v2_prepare_logs/vortex_stage0_audit.json
```

- [ ] **Step 3: Read the rescue counters**

```bash
jq '._dropped_at_prepare // .stage0 // .' runs/v2_prepare_logs/vortex_stage0_audit.json
```

Record the `conditional_behavior_*` counters. Expected: near zero. The acceptance bullet from the source plan is: "Stage-0 candidate substantive-coverage ratio for L2/L3 is maintained or improved vs the post-Stage-0 baseline (L1: 20/20, L2: 60/60 all-substantive; L3: ≥45/60 with ≥3 distinct substantive sources)."

If the counter is > 5% of candidates, the v2 bundle is still producing license-anchored conditional_behavior signals — go back to Phase 3 Task 4 with the failing audit attached.

- [ ] **Step 4: Commit logs (audit only — full prepare_out dir is gitignored)**

```bash
git add runs/v2_prepare_logs/vortex_stage0_audit.json
git commit -m "chore(analyzer-v2/phase-4): record vortex prepare-v2 stage-0 audit"
```

---

### Task 3: Same for NVDLA

**Files:**
- Create (by running): `runs/v2_prepare_logs/nvdla_*`.

**Interfaces:** identical to Task 2 with `--project nvdla` and `--bundle-path runs/nvdla_context_bundle_v2/`.

- [ ] **Step 1: Run prepare on NVDLA v2 bundle, same invocation pattern**

```bash
mkdir -p runs/v2_prepare_logs/nvdla_prepare_out
uv run python skills/benchmark-generator/scripts/prepare_module_inputs.py \
    --project nvdla \
    --bundle-path runs/nvdla_context_bundle_v2/ \
    --out-dir runs/v2_prepare_logs/nvdla_prepare_out/ \
    2>&1 | tee runs/v2_prepare_logs/nvdla_prepare.log
```

Same audit extraction and acceptance bar.

If Phase 0 / Phase 1 / Phase 2 chose to skip NVDLA (RTL surface not present in `repo_sources/nvdla/`), document the skip here and move on. Phase 5 will need a populated NVDLA bundle for full rollout, so the skip propagates.

- [ ] **Step 2: Commit the audit**

```bash
git add runs/v2_prepare_logs/nvdla_stage0_audit.json
git commit -m "chore(analyzer-v2/phase-4): record nvdla prepare-v2 stage-0 audit"
```

---

### Task 4: Run the existing test suite against the v2-aware prepare

**Files:**
- Modify: none (this is verification only).

**Interfaces:**
- Consumes: the modified prepare; the existing test suite.
- Produces: a green test run that proves the `--bundle-path` flag default preserves v1 behaviour bit-for-bit.

- [ ] **Step 1: Run the full suite**

```bash
uv run pytest -q
```

Expected: all tests pass. If any pre-existing test changes outcome, that means Task 1's flag default isn't truly backwards-compatible — fix the default-handling code path, not the test.

- [ ] **Step 2: Spot-check the v1-default branch**

```bash
uv run python skills/benchmark-generator/scripts/prepare_module_inputs.py \
    --project vortex \
    --out-dir /tmp/_v1_default_prepare_out/ 2>&1 | tail -20
```

Expected: this still reads from `runs/vortex_context_bundle/` (the v1 path) — confirm by inspecting the log or grepping the output dir for bundle path references.

- [ ] **Step 3: Commit (nothing to add — gate task)**

If everything passed, move on. If anything failed, add a follow-up task and stop.

---

### Task 5: Update SKILL docs

**Files:**
- Modify: `skills/benchmark-generator/SKILL.md`
- Modify: `skills/benchmark-generator/references/generator-contract.md`

**Interfaces:**
- Consumes: the verified v2 path.
- Produces: documentation that names the v2 bundle invocation. Important for future readers reproducing the pipeline.

- [ ] **Step 1: Add a v2 invocation example to SKILL.md**

Right after the existing v1 example, append:

```markdown
## v2 bundle (opt-in during Phase 4)

```bash
uv run python skills/benchmark-generator/scripts/prepare_module_inputs.py \
    --project vortex \
    --bundle-path runs/vortex_context_bundle_v2/
```

When the v2 analyzer is promoted (Phase 5), the `--bundle-path` flag becomes
unnecessary because the canonical bundle directory is the v2 output.
```

- [ ] **Step 2: Note the contract in generator-contract.md**

Append a short paragraph: prepare accepts any directory matching the bundle schema; the v2 analyzer writes the same shape with `analyzer_version: benchmark-repo-analyzer/v2-tree-sitter-codegraph`.

- [ ] **Step 3: Commit**

```bash
git add skills/benchmark-generator/SKILL.md \
        skills/benchmark-generator/references/generator-contract.md
git commit -m "docs(analyzer-v2/phase-4): document v2 bundle prepare invocation"
```

---

### Task 6: Phase 4 acceptance report

**Files:**
- Create: `runs/feasibility_v2_analyzer/phase4_acceptance.md`
- Modify: `analyzer_v2_codegraph_treesitter_plan.md` § 9 — Phase 4 row to `complete`.

**Interfaces:**
- Consumes: Tasks 2, 3, 4 outputs.
- Produces: a one-page acceptance report referencing the audit JSONs and the test-suite green status. Phase 5 reads this.

- [ ] **Step 1: Draft the report**

```markdown
# Analyzer v2 Phase 4 — Acceptance

## Stage-0 audit summary (v2 bundle)

| Project | conditional_behavior rescued | L1 substantive | L2 substantive | L3 substantive |
|---|---|---|---|---|
| Vortex | <n> / <total> | <a>/20 | <b>/60 | <c>/60 |
| NVDLA  | <n> / <total> | <a>/20 | <b>/60 | <c>/60 |

Acceptance bar (source plan):
- L1 substantive == 20/20 [PASS / FAIL]
- L2 substantive == 60/60 [PASS / FAIL]
- L3 substantive ≥ 45/60 with ≥ 3 distinct substantive sources [PASS / FAIL]
- conditional_behavior rescue counter ≈ 0 [PASS / FAIL]

## Test suite

- `uv run pytest -q` result: PASS / FAIL on <date>.

## Notes

- Stage-0 workaround disposition: keep / queue for removal after one more clean run / remove now.
- Any v2 bundle records that prepare rejected (and why): <…>.

## Phase 5 GO / NO-GO

<…>
```

- [ ] **Step 2: Commit**

```bash
git add analyzer_v2_codegraph_treesitter_plan.md \
        runs/feasibility_v2_analyzer/phase4_acceptance.md
git commit -m "docs(analyzer-v2/phase-4): acceptance; phase-5 GO"
```

---

## Acceptance for "Phase 4 is done"

1. `prepare_module_inputs.py` accepts `--bundle-path`; default behaviour unchanged.
2. `tests/test_prepare_v2_bundle_smoke.py` passes.
3. `uv run pytest -q` passes on the full suite.
4. `runs/v2_prepare_logs/{vortex,nvdla}_stage0_audit.json` exist (NVDLA may be skipped if its v2 bundle isn't present yet — document).
5. Vortex Stage-0 conditional_behavior rescue counter ≤ 5% of candidates.
6. Substantive-coverage bars (L1 == 20/20, L2 == 60/60, L3 ≥ 45/60) are met for Vortex and (if NVDLA bundle exists) NVDLA.
7. `runs/feasibility_v2_analyzer/phase4_acceptance.md` ends with `Phase 5 GO`.
