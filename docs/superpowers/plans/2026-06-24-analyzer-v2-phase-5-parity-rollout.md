# Analyzer v2 — Phase 5: Parity + Rollout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Sketched plan — Phase 4 must ship first.** Revised 2026-06-26: added Task 5a (npm-audit security review of the CodeGraph 1.1.1 dependency tree) as a hard gate on Task 6 promotion, per Phase 0 risk R5 (`npm audit` reported 8 vulnerabilities: 4 moderate, 3 high, 1 critical).
>
> This phase makes irreversible changes (bundle directory promotion, archive moves). Every directory rename must be guarded by a `git mv` so the operation shows up reviewably in diff. Do not run rollout steps before (a) the smoke50 comparison shows L3 survival ≥ 15/60 AND (b) the npm-audit gate is green.

**Goal:** Prove end-to-end that v2 improves benchmark quality (Vortex L3 row survival after the strict adversarial gate ≥ 15/60, up from the prior smoke50 baseline of 2/60), then promote `runs/{vortex,nvdla}_context_bundle_v2/` to canonical and archive v1.

**Architecture:** Three measurement steps (index → prepare → smoke50 generate+gate), one documentation step (skills/benchmark-repo-analyzer/SKILL.md), one rollout step (directory rename), one acceptance report. The rollout step is the only irreversible action; everything before it is recomputable.

**Tech Stack:** CodeGraph fork from Phase 1; Python exporter from Phase 2; signal emitter from Phase 3; v2-aware prepare from Phase 4; existing host-LLM authoring pipeline (M2-M9) + adversarial gate.

## Global Constraints

- Bundle directory swap (Task 6) is gated on Task 4 acceptance. Do not promote v2 if Vortex L3 row survival is < 15/60.
- All directory moves use `git mv` (not `mv` + `git add`/`rm`) so the rename is reviewable in `git log --follow`.
- The archive path is `runs/archive/{vortex,nvdla}_context_bundle_v1/`. Create `runs/archive/` if absent.
- Smoke50 runs are stochastic: pick a fixed seed (per the existing pipeline's seed convention) and record it in the acceptance report so the comparison is reproducible.
- If smoke50 fails the L3 gate (< 15/60), do *not* roll back any earlier-phase code — file follow-ups against Phase 3 or Phase 1 instead. The earlier phases shipped under their own gates.

---

## File Structure

Create:

- `skills/benchmark-repo-analyzer/SKILL.md` — the analyzer's first-class SKILL doc (today only `references/` exists). Mentioned by the source plan as a Phase 5 deliverable.
- `runs/v2_parity/` — bucket for all Phase 5 measurement artifacts (gitignored bulk; the markdown summaries are tracked).
- `runs/v2_parity/vortex_smoke50_v2.{jsonl,structural_gate.json,adversarial_gate.jsonl}` — smoke50 outputs.
- `runs/v2_parity/parity_report.md` — Vortex+NVDLA candidate stat comparison (Task 2 output).
- `runs/v2_parity/smoke50_v2_vs_v1.md` — smoke50 comparison report (Task 4 output).
- `runs/archive/` — destination for archived v1 bundles.
- `runs/feasibility_v2_analyzer/phase5_acceptance.md` — final acceptance report.

Modify:

- `runs/vortex_context_bundle/` and `runs/nvdla_context_bundle/` — *renamed* to `runs/archive/{vortex,nvdla}_context_bundle_v1/` via `git mv` (Task 6).
- `runs/vortex_context_bundle_v2/` and `runs/nvdla_context_bundle_v2/` — *renamed* to `runs/{vortex,nvdla}_context_bundle/` via `git mv` (Task 6).
- `skills/benchmark-generator/scripts/prepare_module_inputs.py` — once the canonical directory IS the v2 bundle, the `--bundle-path` default no longer needs to disambiguate. Verify the default still works (no behavior change required — Phase 4 already made the path overridable).
- `analyzer_v2_codegraph_treesitter_plan.md` § 9 — Phase 5 row to `complete`; § 10 acceptance checklist updated to reflect rollout.

Do not modify:

- The Stage-0 workaround functions in `prepare_module_inputs.py`. They become near-no-ops but stay in place as defense-in-depth; deletion is a separate cleanup PR.

---

### Task 1: Re-index both projects with the v2 analyzer

**Files:**
- Refresh (by running): `runs/{vortex,nvdla}_context_bundle_v2/` and the CodeGraph DBs.

**Interfaces:**
- Consumes: the Phase 1 fork (built); the Phase 2 exporter; the Phase 3 signal emitter.
- Produces: a clean, deterministic v2 bundle for both projects. Tasks 2–4 read these.

- [ ] **Step 1: Re-index Vortex**

```bash
source <(grep '^CG_' runs/feasibility_v2_analyzer/_codegraph_paths.md | sed 's/^/export /')
"$CG_BIN" index repo_sources/vortex 2>&1 | tee runs/v2_parity/codegraph_index_vortex.log
```

- [ ] **Step 2: Re-export Vortex v2 bundle**

```bash
uv run python skills/benchmark-repo-analyzer/scripts/codegraph_to_bundle.py \
    --db "$CG_DB" --project vortex --source-set-id vortex_main \
    --repo-name vortex/vortex \
    --out runs/vortex_context_bundle_v2/ \
    --diff-against runs/vortex_context_bundle/
uv run python skills/benchmark-repo-analyzer/scripts/signal_emitter.py \
    --bundle runs/vortex_context_bundle_v2/ --project vortex
```

Expected: same files as Phase 2/3 acceptance, freshly regenerated.

- [ ] **Step 3: Same for NVDLA (skip if NVDLA RTL unavailable — document)**

```bash
"$CG_BIN" index repo_sources/nvdla 2>&1 | tee runs/v2_parity/codegraph_index_nvdla.log
# Update CG_DB if NVDLA uses a different DB path.
uv run python skills/benchmark-repo-analyzer/scripts/codegraph_to_bundle.py \
    --db "$CG_DB" --project nvdla --source-set-id nvdla_main \
    --repo-name nvdla/nvdla \
    --out runs/nvdla_context_bundle_v2/ \
    --diff-against runs/nvdla_context_bundle/
uv run python skills/benchmark-repo-analyzer/scripts/signal_emitter.py \
    --bundle runs/nvdla_context_bundle_v2/ --project nvdla
```

- [ ] **Step 4: Re-run the bundle validator on both v2 dirs**

```bash
for p in vortex nvdla; do
  uv run python skills/benchmark-repo-analyzer/scripts/validate_context_bundle.py \
      --bundle runs/${p}_context_bundle_v2/ \
    || echo "VALIDATION FAILED: $p"
done
```

Expected: both PASS. If not, this is a Phase 2 / Phase 3 regression — stop and fix.

- [ ] **Step 5: Commit (logs gitignored; tiny manifest delta committed)**

```bash
git add runs/vortex_context_bundle_v2/project_manifest.json \
        runs/nvdla_context_bundle_v2/project_manifest.json
git commit -m "chore(analyzer-v2/phase-5): re-index both projects with v2"
```

---

### Task 2: Candidate-stat parity report (prepare against v1 vs v2)

**Files:**
- Create: `runs/v2_parity/parity_report.md`
- Create (by running): per-project prepare outputs into `runs/v2_parity/prepare_{v1,v2}_{vortex,nvdla}/`.

**Interfaces:**
- Consumes: v1 and v2 bundles for both projects; `prepare_module_inputs.py` with the Phase 4 `--bundle-path` flag.
- Produces: a markdown report showing candidate-substance metrics side-by-side (L1/L2/L3 row counts, distinct-substantive-source counts, attribute distributions, rescue counters). Task 4 references this.

- [ ] **Step 1: Run prepare four times (v1 and v2 × Vortex and NVDLA)**

```bash
for project in vortex nvdla; do
  for bundle in "${project}_context_bundle" "${project}_context_bundle_v2"; do
    suffix=$(echo "$bundle" | sed 's/^.*context_bundle/v1/;s/^.*v2$/v2/')
    out="runs/v2_parity/prepare_${suffix}_${project}"
    mkdir -p "$out"
    uv run python skills/benchmark-generator/scripts/prepare_module_inputs.py \
        --project "$project" --bundle-path "runs/${bundle}/" \
        --out-dir "$out/" 2>&1 | tee "$out/_prepare.log"
  done
done
```

(If NVDLA v2 was skipped in Task 1, skip the NVDLA loop here too.)

- [ ] **Step 2: Extract metrics**

Write a tiny one-shot script `runs/v2_parity/_extract_parity.py` (committed; reproducibility matters here):

```python
"""Read the four prepare audits and emit a parity markdown table."""
import json, sys
from pathlib import Path

ROOT = Path("runs/v2_parity")
ROWS = []
for project in ("vortex", "nvdla"):
    for variant in ("v1", "v2"):
        audit = ROOT / f"prepare_{variant}_{project}/_stage0_audit.json"
        if not audit.exists():
            continue
        d = json.loads(audit.read_text())
        ROWS.append({
            "project": project, "variant": variant,
            "l1_substantive": d.get("l1_substantive_count"),
            "l2_substantive": d.get("l2_substantive_count"),
            "l3_substantive": d.get("l3_substantive_count"),
            "rescues_conditional_behavior":
                d.get("rescues", {}).get("conditional_behavior", 0),
        })
print("| project | variant | L1 subst | L2 subst | L3 subst | cond_beh rescues |")
print("|---|---|---|---|---|---|")
for r in ROWS:
    print(f"| {r['project']} | {r['variant']} | {r['l1_substantive']} | "
          f"{r['l2_substantive']} | {r['l3_substantive']} | "
          f"{r['rescues_conditional_behavior']} |")
```

The exact audit-field names depend on what prepare actually writes — adjust to match Phase 4's observed audit shape.

```bash
uv run python runs/v2_parity/_extract_parity.py > runs/v2_parity/parity_report.md
```

- [ ] **Step 3: Review the table by eye and add commentary**

Append a "## Commentary" section to `parity_report.md` with one paragraph per project explaining the deltas (where v2 helped, where it didn't, any regression).

- [ ] **Step 4: Commit**

```bash
git add runs/v2_parity/_extract_parity.py runs/v2_parity/parity_report.md
git commit -m "docs(analyzer-v2/phase-5): prepare-stage parity report v1 vs v2"
```

---

### Task 3: Run the smoke50 host-LLM pipeline on Vortex with the v2 bundle

**Files:**
- Create (by running): `runs/v2_parity/vortex_smoke50_v2.jsonl`, `runs/v2_parity/vortex_smoke50_v2.structural_gate.json`, `runs/v2_parity/vortex_smoke50_v2.adversarial_gate.jsonl`.

**Interfaces:**
- Consumes: Vortex v2 prepare output (Task 2); existing M2-M9 + structural-gate + adversarial-gate scripts; the existing 50-row smoke profile.
- Produces: a smoke50 benchmark JSONL + gate outputs. Task 4 compares these to the prior smoke50_v1.

The pipeline command surface here mirrors whatever the team has been using for prior smoke50 runs (`runs/smoke50_vortex/` and `runs/smoke50_vortex_run50/` exist in the repo as references). Do not invent new flags; copy the prior invocation.

- [ ] **Step 1: Locate the prior smoke50 invocation**

```bash
ls runs/ | grep -i smoke50
find scripts/ -name '*smoke*'
grep -rln 'smoke50' README.md scripts/ skills/ | head
```

Expected: a script or README section showing how the prior smoke50 was generated. Reuse that invocation, substituting:

- the bundle path → `runs/vortex_context_bundle_v2/`
- the output prefix → `runs/v2_parity/vortex_smoke50_v2`
- the seed → record whatever seed the prior smoke50 used (or, if missing, pick `42` and write it into the acceptance report)

- [ ] **Step 2: Run M2-M9**

(Concrete command depends on Step 1. Sketch:)

```bash
uv run python scripts/run_v1_2_llm_bundle.py \
    --project vortex \
    --bundle-path runs/vortex_context_bundle_v2/ \
    --rows 50 \
    --seed 42 \
    --out runs/v2_parity/vortex_smoke50_v2.jsonl \
    2>&1 | tee runs/v2_parity/vortex_smoke50_v2.log
```

Expected: a 50-line JSONL. If the run partially fails on individual rows, that's data — do not retry to a clean 50; the comparison is honest only if the pipeline runs apples-to-apples.

- [ ] **Step 3: Structural gate**

```bash
uv run python skills/benchmark-validator/scripts/validate_benchmark.py \
    --schema-version v1.1 \
    --rows runs/v2_parity/vortex_smoke50_v2.jsonl \
    --structural-gate-json runs/v2_parity/vortex_smoke50_v2.structural_gate.json
```

- [ ] **Step 4: Adversarial gate**

```bash
uv run python skills/benchmark-validator/scripts/adversarial_gate.py \
    --rows runs/v2_parity/vortex_smoke50_v2.jsonl \
    --out runs/v2_parity/vortex_smoke50_v2.adversarial_gate.jsonl
```

- [ ] **Step 5: Commit metadata**

```bash
git add runs/v2_parity/vortex_smoke50_v2.structural_gate.json \
        runs/v2_parity/vortex_smoke50_v2.adversarial_gate.jsonl
git commit -m "chore(analyzer-v2/phase-5): vortex smoke50 v2 outputs"
```

(`vortex_smoke50_v2.jsonl` may be gitignored as large output; the gate JSONs are tracked.)

---

### Task 4: Smoke50 v2 vs v1 comparison

**Files:**
- Create: `runs/v2_parity/smoke50_v2_vs_v1.md`
- (Optional) Create: `runs/v2_parity/_extract_smoke50_compare.py`

**Interfaces:**
- Consumes: Task 3 outputs; the prior smoke50_v1 artifacts under `runs/smoke50_vortex/` (or equivalent — confirm the path from the existing repo layout).
- Produces: a comparison report whose load-bearing line is `L3 row survival after strict adversarial gate: v1=<x>/60, v2=<y>/60`. Task 6 reads this report's GO/NO-GO line before promoting v2 to canonical.

The four success criteria from the source plan Phase 5 acceptance:

- L3 row survival ≥ 15/60 on Vortex (was 2/60).
- `conditional_behavior` axis repopulates with anchors at real guard tokens.
- `distracting_info` evidence usable end-to-end by M5/M9.
- (Implicit) Per-row substance is up vs v1.

- [ ] **Step 1: Locate the v1 smoke50 baseline**

```bash
ls runs/smoke50_vortex* 2>/dev/null
find runs/ -name '*smoke50*adversarial*' | head
```

Pick the most recent prior smoke50 v1 adversarial gate file. Record its path in the report.

- [ ] **Step 2: Extract the side-by-side numbers**

Hand-compute (or script):

```bash
v1_l3_survival=$(jq -s 'map(select(.level==3 and .gate_result=="pass")) | length' \
    runs/smoke50_vortex/<v1-adversarial-gate>.jsonl)
v2_l3_survival=$(jq -s 'map(select(.level==3 and .gate_result=="pass")) | length' \
    runs/v2_parity/vortex_smoke50_v2.adversarial_gate.jsonl)
echo "v1 L3 survival: $v1_l3_survival / 20"   # L3 quota in 50-row smoke is 20; adjust if profile differs
echo "v2 L3 survival: $v2_l3_survival / 20"
```

(Adjust field names — `level`, `gate_result` — to match the actual adversarial-gate output schema.)

- [ ] **Step 3: Draft the comparison report**

```markdown
# Smoke50 Vortex — v2 vs v1

Seed: <…>
v1 baseline path: <…>
v2 path: runs/v2_parity/vortex_smoke50_v2.jsonl

## L3 row survival after strict adversarial gate

| variant | L3 pass / quota | conditional_behavior anchors in license zone | distracting_info usable evidence |
|---|---|---|---|
| v1 | <a>/<q> | <n> | <…> |
| v2 | <b>/<q> | 0 | <…> |

Acceptance bar from source plan: v2 L3 survival ≥ 15 (was 2 in prior smoke50).

## Per-axis attribute distribution

<table or paragraph showing where v2 changed the mix>

## Sign-off

Phase 5 promotion GO / NO-GO: <…>
```

- [ ] **Step 4: Commit**

```bash
git add runs/v2_parity/smoke50_v2_vs_v1.md
git commit -m "docs(analyzer-v2/phase-5): smoke50 v2-vs-v1 comparison"
```

---

### Task 5: Write `skills/benchmark-repo-analyzer/SKILL.md`

**Files:**
- Create: `skills/benchmark-repo-analyzer/SKILL.md`

**Interfaces:**
- Consumes: the established invocation patterns from Phases 1–3.
- Produces: a first-class SKILL doc for the analyzer (mirroring `skills/benchmark-generator/SKILL.md` and `skills/benchmark-validator/SKILL.md`).

- [ ] **Step 1: Inspect the existing SKILL.md style**

```bash
sed -n '1,60p' skills/benchmark-generator/SKILL.md
sed -n '1,60p' skills/benchmark-validator/SKILL.md
```

Match the existing structure: one-paragraph purpose, invocation, inputs/outputs, references list, troubleshooting.

- [ ] **Step 2: Draft `skills/benchmark-repo-analyzer/SKILL.md`**

```markdown
# benchmark-repo-analyzer

Indexes a project repo and produces the context bundle that the benchmark
generator consumes: `source_inventory.jsonl`, `entity_index.jsonl`,
`relation_graph.jsonl`, `signal_index.jsonl`, `project_manifest.json`,
`analyzer_report.md`.

## Invocation

Two stages: (a) CodeGraph indexes the repo into a SQLite DB; (b) Python
exporters read the DB and write the bundle JSONLs.

```bash
# Stage A: index (uses the project-pinned CodeGraph fork from tools/codegraph/)
"$CG_BIN" index repo_sources/<project>/

# Stage B: export bundle + emit signals
uv run python skills/benchmark-repo-analyzer/scripts/codegraph_to_bundle.py \
    --db <codegraph.db> --project <project> --source-set-id <sset> \
    --repo-name <owner/repo> --out runs/<project>_context_bundle/
uv run python skills/benchmark-repo-analyzer/scripts/signal_emitter.py \
    --bundle runs/<project>_context_bundle/ --project <project>
```

## Outputs

(table of files + brief description)

## Troubleshooting

- "imports_or_includes target.id empty" → re-run with the Phase 1 fork at the
  pinned commit (`runs/feasibility_v2_analyzer/_codegraph_commit.txt`); upstream
  CodeGraph does not include Verilog cross-file resolution.
- "conditional_behavior anchors in license block" → signal emitter regression;
  see `runs/feasibility_v2_analyzer/phase3_acceptance.md`.
- "ERROR while indexing .sv file" → Phase 6 (Verible fallback) may be needed;
  see `analyzer_v2_codegraph_treesitter_plan.md` § 4 Phase 6.

## References

- `references/analyzer-contract.md`
- `references/codegraph_schema.md` (Phase 0 schema dump, the exporter contract)
- `../../analyzer_v2_codegraph_treesitter_plan.md`
```

- [ ] **Step 3: Commit**

```bash
git add skills/benchmark-repo-analyzer/SKILL.md
git commit -m "docs(analyzer-v2/phase-5): first-class SKILL.md for the analyzer"
```

---

### Task 5a: npm-audit security review of the CodeGraph fork (added 2026-06-26)

**Files:**
- Create: `runs/feasibility_v2_analyzer/phase5_npm_audit.md`

**Interfaces:**
- Consumes: `tools/codegraph/` on `feat/verilog-language-module`.
- Produces: a markdown record of `npm audit --production` output, a per-CVE disposition, and a `gate: pass | fail` line. Task 6 reads `gate:` and refuses to promote on `fail`.

Phase 0 R5 found 8 vulnerabilities in the CodeGraph 1.1.1 dependency tree
(4 moderate, 3 high, 1 critical). Until those are triaged we are NOT
allowed to promote v2 to canonical. The triage may resolve via `npm audit
fix`, by upgrading an indirect dep, by ignoring with explicit
justification (e.g. dev-only CVE that never reaches production), or by
pinning to a patched version.

- [ ] **Step 1: Capture the current state**

```bash
cd tools/codegraph
npm audit --production --json > /tmp/_npm_audit.json
npm audit --production 2>&1 | tee /tmp/_npm_audit.txt
```

- [ ] **Step 2: Try the safe automatic fix**

```bash
npm audit fix --production         # no --force; force is opt-in below
npm audit --production --json > /tmp/_npm_audit_after.json
```

- [ ] **Step 3: Per-CVE triage**

For each remaining advisory, pick exactly one disposition: `fixed`,
`upgraded`, `ignored-with-justification`, or `accepted-risk-needs-review`.
Anything left in `accepted-risk-needs-review` means the gate fails.

- [ ] **Step 4: Write the report**

`runs/feasibility_v2_analyzer/phase5_npm_audit.md`:

```markdown
# Phase 5 — npm audit security review

Date: <date>
Fork branch: feat/verilog-language-module @ <sha>
CodeGraph upstream: 1.1.1

## Phase 0 baseline (R5)

8 vulnerabilities: 4 moderate, 3 high, 1 critical.

## After `npm audit fix --production`

| advisory id | severity | package | disposition | notes |
|---|---|---|---|---|
| <…> | <…> | <…> | fixed/upgraded/ignored/accepted | <…> |

## Gate

gate: pass | fail
```

- [ ] **Step 5: Commit + push back to the fork**

```bash
cd tools/codegraph
git add package.json package-lock.json
git commit -m "chore(security): npm audit fix (phase-5 prereq)" || true
git push  # if remote configured
cd -
git add runs/feasibility_v2_analyzer/phase5_npm_audit.md
git commit -m "docs(analyzer-v2/phase-5): npm-audit security review"
```

---

### Task 6: Promote v2 to canonical, archive v1 (the irreversible step)

**Files:**
- Modify (by `git mv`): `runs/vortex_context_bundle/` → `runs/archive/vortex_context_bundle_v1/`.
- Modify (by `git mv`): `runs/nvdla_context_bundle/` → `runs/archive/nvdla_context_bundle_v1/`.
- Modify (by `git mv`): `runs/vortex_context_bundle_v2/` → `runs/vortex_context_bundle/`.
- Modify (by `git mv`): `runs/nvdla_context_bundle_v2/` → `runs/nvdla_context_bundle/`.
- Modify: `analyzer_v2_codegraph_treesitter_plan.md` § 10 — flip rollout items.

**Interfaces:**
- Consumes: Task 4 sign-off (`Phase 5 promotion GO`); Task 5 docs.
- Produces: the canonical bundle path is now v2. All downstream consumers (prepare default, M2-M9, lint) get v2 with no flag change.

**Gate**: do not run this task until `runs/v2_parity/smoke50_v2_vs_v1.md` ends with `Phase 5 promotion GO`. If it ends with `NO-GO`, file follow-ups against the relevant earlier phase and stop here.

- [ ] **Step 1: Pre-flight — confirm v1 archive directory exists**

```bash
mkdir -p runs/archive
ls runs/archive/  # should be empty or only contain prior archives
```

- [ ] **Step 2: Pre-flight — confirm no in-flight work depends on the v1 path**

```bash
grep -rn 'runs/vortex_context_bundle\b\|runs/nvdla_context_bundle\b' \
    scripts/ skills/ tests/ docs/ \
    | grep -v _v1 | grep -v _v2 | grep -v archive
```

Expected: only generic references (default paths in `prepare_module_inputs.py`, README docs). None should hard-code a v1-only assumption that would break after the swap. If any do, fix them before the swap.

- [ ] **Step 3: Archive v1**

```bash
git mv runs/vortex_context_bundle runs/archive/vortex_context_bundle_v1
git mv runs/nvdla_context_bundle  runs/archive/nvdla_context_bundle_v1
```

- [ ] **Step 4: Promote v2**

```bash
git mv runs/vortex_context_bundle_v2 runs/vortex_context_bundle
git mv runs/nvdla_context_bundle_v2  runs/nvdla_context_bundle
```

- [ ] **Step 5: Sanity check**

```bash
jq -r '.analyzer_version' runs/vortex_context_bundle/project_manifest.json
jq -r '.analyzer_version' runs/nvdla_context_bundle/project_manifest.json
# both should print: benchmark-repo-analyzer/v2-tree-sitter-codegraph
jq -r '.analyzer_version' runs/archive/vortex_context_bundle_v1/project_manifest.json
# should print the v1 analyzer version
```

- [ ] **Step 6: Re-run the full test suite as a final regression gate**

```bash
uv run pytest -q
```

Expected: PASS. If a test now fails because it was reading v1-shaped data from the v1 path, that's a Phase 4 oversight — fix it before declaring the rollout complete.

- [ ] **Step 7: Commit the swap as a single revertible commit**

```bash
git commit -m "feat(analyzer-v2/phase-5): promote v2 bundles to canonical; archive v1"
```

---

### Task 7: Phase 5 acceptance report + master plan completion

**Files:**
- Create: `runs/feasibility_v2_analyzer/phase5_acceptance.md`
- Modify: `analyzer_v2_codegraph_treesitter_plan.md` — § 9 Phase 5 row to `complete`; § 10 acceptance checklist to "all six conditions met".

**Interfaces:**
- Consumes: every prior phase's acceptance report; Tasks 4 and 6 outputs.
- Produces: the final Phase 5 acceptance doc + the master plan flips to "implemented".

- [ ] **Step 1: Draft `phase5_acceptance.md`**

```markdown
# Analyzer v2 Phase 5 — Acceptance

## Source-plan acceptance bullets

- [x|✗] Vortex L3 row survival ≥ 15/60 (actual: <n>/60).
- [x|✗] conditional_behavior axis repopulates with real guard-token anchors.
- [x|✗] distracting_info evidence usable end-to-end by M5/M9.

## Rollout

- v1 bundles archived to:
  - runs/archive/vortex_context_bundle_v1/
  - runs/archive/nvdla_context_bundle_v1/
- Canonical bundles now v2 (analyzer_version verified per manifest).
- pytest -q: PASS / FAIL on <date>.

## Source-plan § 10 final acceptance ("v2 is done")

- [x] (1) Vortex project_manifest reports v2 analyzer + used_primary: true.
- [x] (2) Same for NVDLA.
- [x] (3) prepare_module_inputs.py reports zero Stage-0 conditional_behavior rescues.
- [x] (4) 50-row smoke produces ≥ 15 L3 rows surviving strict adversarial gate.
- [x] (5) Existing test suite passes against new bundles unmodified.
- [x] (6) skills/benchmark-repo-analyzer/SKILL.md documents v2 invocation.

## Open follow-ups

- Remove Stage-0 workarounds in prepare_module_inputs.py (after two more clean runs).
- Content-level doc_code_divergence detection (deferred per source plan § 7).
- version_fork_diff signal emission for NVDLA (deferred per source plan § 7).
- Phase 6 (Verible secondary parser) if Phase 0 bucket required it.
```

- [ ] **Step 2: Flip the master plan**

In `analyzer_v2_codegraph_treesitter_plan.md`:
- § 9 Phase 5 row → `complete | <date> | promotion sha=<short>`.
- Document header `Status: implemented`.
- § 10 final-acceptance — leave the list as-is but add a closing line: `Plan transitioned to "implemented" on <date>; phase tracker frozen.`

- [ ] **Step 3: Commit**

```bash
git add analyzer_v2_codegraph_treesitter_plan.md \
        runs/feasibility_v2_analyzer/phase5_acceptance.md
git commit -m "docs(analyzer-v2/phase-5): v2 implemented; plan transitioned to implemented status"
```

---

## Acceptance for "Phase 5 is done"

1. v2 has been indexed, exported, and signaled freshly on both Vortex and NVDLA (Task 1).
2. `runs/v2_parity/parity_report.md` shows side-by-side prepare metrics for v1 and v2 (Task 2).
3. `runs/v2_parity/smoke50_v2_vs_v1.md` shows Vortex L3 row survival ≥ 15/60 with seed recorded (Task 4).
4. `skills/benchmark-repo-analyzer/SKILL.md` exists (Task 5).
5. v1 bundles live under `runs/archive/`, v2 bundles at the canonical path (Task 6).
6. `uv run pytest -q` PASSES with the canonical path now pointing at v2 (Task 6 Step 6).
7. `analyzer_v2_codegraph_treesitter_plan.md` § 9 reads all phases `complete` and the document header is `Status: implemented` (Task 7).
