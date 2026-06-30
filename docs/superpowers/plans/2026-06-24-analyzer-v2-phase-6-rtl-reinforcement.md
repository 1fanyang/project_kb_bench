# Analyzer v2 — Phase 6: RTL Accuracy Reinforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **SCHEDULED** (was "conditional" in the original draft; promoted 2026-06-26). Phase 0 measured Vortex's `usable_pct` at 95.5% with 9 hard-error hand-written files — exactly the bucket that triggers this phase. The 9 files are:
>
> 1. `vortex/hw/rtl/VX_trace_pkg.sv` (459 ERROR nodes — highest)
> 2. `vortex/hw/rtl/afu/xrt/VX_afu_wrap.sv` (282)
> 3. `vortex/hw/dpi/float_dpi.vh` (171)
> 4. `vortex/hw/rtl/afu/xrt/vortex_afu.v` (64)
> 5. `vortex/sim/xrtsim/vortex_afu_shim.sv` (62)
> 6. `vortex/hw/rtl/core/VX_uop_sequencer.sv` (33)
> 7. `vortex/hw/dpi/util_dpi.vh` (25)
> 8. `vortex/hw/rtl/interfaces/VX_decode_if.sv` (10)
> 9. `vortex/hw/rtl/interfaces/VX_fetch_if.sv` (10)
>
> NVDLA has zero hard errors on hand-written RTL, so the fallback fires for Vortex only.

> **Sketched plan — Phase 1 must ship first.** The fallback hook lives inside the CodeGraph fork's Verilog language module from Phase 1, so this phase only makes sense after that module exists.

**Goal:** Bring per-file RTL parse-error rate below 1% across Vortex by falling back to Verible (`verible-verilog-syntax`) for files that tree-sitter-verilog cannot parse cleanly, and merging Verible's parse-tree output into CodeGraph's graph so downstream consumers see a unified view.

**Architecture:** Per-file fallback — for each `.sv` / `.v` / `.svh` / `.vh` file CodeGraph tries to index, the Verilog language module first runs tree-sitter; if tree-sitter reports errors above a threshold, it shells out to `verible-verilog-syntax --export_json` and converts the result into the same internal graph records (entity + relation) the tree-sitter path would have produced. Both paths feed the same resolver and the same SQLite tables. Confidence on Verible-derived records is `0.85` (between AST `0.95` and regex `0.7`) so downstream signal emitters can weight accordingly.

**Tech Stack:** Verible (`verible-verilog-syntax` binary), shelled out from CodeGraph's Verilog module (Node.js child_process); fork from Phase 1.

## Global Constraints

- Verible is a single binary; vendor a known-good version into `tools/verible/` (project-local, mirrors `tools/codegraph/`).
- Per-file fallback only. Do not replace the tree-sitter path globally — the source plan explicitly says "secondary parser."
- Verible-derived records must be tagged so they can be distinguished from tree-sitter-derived records in the bundle. Use `extractor: "codegraph_verible_fallback_v2"` on entities and relations originating from Verible.
- Verible's JSON output shape is documented but version-dependent. Pin the Verible version in `tools/verible/VERSION.txt` and re-test if the version bumps.
- Phase 5 has already promoted v2 to canonical by the time Phase 6 runs (since Phase 6 is conditional and follows Phase 5 in the tracker). This means the bundle path is `runs/{vortex,nvdla}_context_bundle/` (no `_v2` suffix). Plan tasks reference the canonical path.

---

## File Structure

Create:

- `tools/verible/` — vendored Verible binary directory (gitignored except `VERSION.txt`).
- `tools/verible/VERSION.txt` — recorded Verible version (e.g. `v0.0-3623-g8b7f3f1d`).
- Inside the fork (`tools/codegraph/`):
  - `src/languages/verilog_verible_fallback.ts` — fallback adapter; shells out to verible, parses JSON, emits entity / relation records in the same shape as the tree-sitter path.
  - `test/languages/verilog/verible_fallback.test.ts` — fixture-based test asserting the fallback fires on a deliberately-broken `.sv` file.
  - `test/languages/verilog/fixtures/breakage.sv` — small fixture using a construct tree-sitter-verilog is known to choke on (record which one in Phase 0 § 4).

Modify (inside the fork):

- `src/languages/verilog.ts` — add the fallback hook in the per-file extractor.
- `package.json` (fork) — bump fork version; record the Verible version requirement in README.

Modify (project side):

- `analyzer_v2_codegraph_treesitter_plan.md` § 9 — Phase 6 row to `complete` after acceptance.
- `skills/benchmark-repo-analyzer/SKILL.md` — note Verible as a runtime dependency under "Troubleshooting".

Do not modify:

- The tree-sitter path (Phase 1). The fallback is additive; tree-sitter remains the primary parser.

---

### Task 1: Vendor Verible and verify

**Files:**
- Create: `tools/verible/` (downloaded binary + VERSION.txt).
- Modify: `.gitignore` — add `tools/verible/bin/` etc., keep `tools/verible/VERSION.txt` tracked.

**Interfaces:**
- Consumes: nothing.
- Produces: `tools/verible/bin/verible-verilog-syntax` (or the platform-equivalent path) and a recorded version. Task 2 invokes this binary.

- [ ] **Step 1: Pick a release**

Verible releases are at `https://github.com/chipsalliance/verible/releases`. Pick the latest stable release tag and record it: `echo <tag> > tools/verible/VERSION.txt`.

- [ ] **Step 2: Download for the dev platform**

```bash
mkdir -p tools/verible
# Replace <tag> and <asset> with the values matching tools/verible/VERSION.txt
curl -L -o /tmp/verible.tar.gz \
    "https://github.com/chipsalliance/verible/releases/download/<tag>/<asset>.tar.gz"
tar -xzf /tmp/verible.tar.gz -C tools/verible --strip-components=1
```

Expected: `tools/verible/bin/verible-verilog-syntax` exists and is executable. Confirm:

```bash
tools/verible/bin/verible-verilog-syntax --version
```

- [ ] **Step 3: Smoke parse a known-good file**

```bash
tools/verible/bin/verible-verilog-syntax \
    --export_json \
    repo_sources/vortex/<any-clean-rtl-file> > /tmp/_verible_smoke.json
jq '.tree | type' /tmp/_verible_smoke.json
```

Expected: `"object"` (or at minimum non-null JSON). If the binary refuses the file but tree-sitter-verilog accepted it earlier, investigate before proceeding — the fallback only helps if Verible is *strictly more lenient*.

- [ ] **Step 4: .gitignore + VERSION.txt commit**

Add to `.gitignore`:

```
tools/verible/bin/
tools/verible/share/
tools/verible/lib/
```

Track only `tools/verible/VERSION.txt`:

```bash
git add .gitignore tools/verible/VERSION.txt
git commit -m "feat(analyzer-v2/phase-6): vendor verible binary; pin version"
```

---

### Task 2: Implement the per-file Verible fallback adapter (in the fork)

**Files (in `tools/codegraph/`):**
- Create: `src/languages/verilog_verible_fallback.ts`
- Create: `test/languages/verilog/fixtures/breakage.sv`
- Create: `test/languages/verilog/verible_fallback.test.ts`
- Modify: `src/languages/verilog.ts`

**Interfaces:**
- Consumes: the Verible binary path (configurable via env var `VERIBLE_BIN`, default `tools/verible/bin/verible-verilog-syntax`); a file path to parse.
- Produces: the same `{entities, relations}` shape the tree-sitter path emits — same field names, same id derivation rules. The only differentiator is `extractor`.

The fallback fires when tree-sitter reports `>N` errors (suggest `N = 5` initially; tune from data). If both parsers fail, the file is logged and skipped (preserves Phase 0 D7 fallback policy).

- [ ] **Step 1: Pick the breakage fixture**

Use `vortex/hw/rtl/VX_trace_pkg.sv` as the source — it has the most ERROR nodes (459) and is the largest single contributor to Vortex's hard-error count. Copy a small representative slice (one parameterized typedef block, the trace-record encoding macros) into `test/languages/verilog/fixtures/breakage.sv`. Confirm tree-sitter still errors on it after Phase 1 (re-run the parse via Phase 1 dump):

```bash
cd tools/codegraph
node -e 'const Parser=require("tree-sitter");const V=require("tree-sitter-verilog");
         const p=new Parser();p.setLanguage(V);
         const t=p.parse(require("fs").readFileSync("test/languages/verilog/fixtures/breakage.sv","utf8"));
         console.log("has_error=", t.rootNode.hasError);'
```

Expected: `has_error= true`. If false, pick a different construct.

- [ ] **Step 2: Implement the fallback adapter (skeleton)**

```typescript
// src/languages/verilog_verible_fallback.ts
import { execFileSync } from "child_process";

interface FallbackResult {
  entities: Array<{ kind: string; name: string; startLine: number; endLine: number;
                    extractor: "codegraph_verible_fallback_v2" }>;
  relations: Array<{ predicate: string; target: string; startLine: number;
                     extractor: "codegraph_verible_fallback_v2" }>;
}

const VERIBLE_BIN = process.env.VERIBLE_BIN ?? "tools/verible/bin/verible-verilog-syntax";


export function parseWithVerible(filePath: string): FallbackResult | null {
  let raw: string;
  try {
    raw = execFileSync(VERIBLE_BIN, ["--export_json", filePath],
                       { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
  } catch (e) {
    return null; // Verible also failed; fall through to skip
  }
  const tree = JSON.parse(raw);
  return convertVeribleTreeToRecords(tree, filePath);
}


// PH6 — convertVeribleTreeToRecords walks Verible's JSON parse tree and
// emits the same kinds we capture in queries/verilog/entities.scm +
// relations.scm. The exact JSON node naming differs from tree-sitter's;
// derive the mapping from Verible's --export_json output on the breakage.sv
// fixture during Step 3.
function convertVeribleTreeToRecords(tree: unknown, _filePath: string): FallbackResult {
  // TODO: implement walker. See test for expected outputs.
  return { entities: [], relations: [] };
}
```

- [ ] **Step 3: Author the test (failing) for the breakage fixture**

```typescript
// test/languages/verilog/verible_fallback.test.ts
import { parseWithVerible } from "../../../src/languages/verilog_verible_fallback";
import { resolve } from "path";

test("verible fallback parses tree-sitter breakage fixture", () => {
  const result = parseWithVerible(resolve(__dirname, "fixtures/breakage.sv"));
  expect(result).not.toBeNull();
  expect(result!.entities.length).toBeGreaterThan(0);
  expect(result!.entities.every(e => e.extractor === "codegraph_verible_fallback_v2"))
    .toBe(true);
});
```

Run:

```bash
npm test -- verible_fallback
```

Expected: FAIL (because `convertVeribleTreeToRecords` returns empty).

- [ ] **Step 4: Iterate `convertVeribleTreeToRecords` against the real Verible JSON**

Print the JSON for `breakage.sv` once:

```bash
tools/verible/bin/verible-verilog-syntax --export_json \
    tools/codegraph/test/languages/verilog/fixtures/breakage.sv | jq . | head -200
```

Walk the tree, mapping the node kinds Verible emits to the entity/relation kinds Phase 1 already established (module / parameter / function / task / interface / package / macro / class / instantiates / calls / imports). Confidence: `0.85`. Implement the walker until the test passes.

- [ ] **Step 5: Wire the fallback into `src/languages/verilog.ts`**

```typescript
// In the per-file extractor, after tree-sitter parse:
if (tree.rootNode.hasError && errorCount(tree.rootNode) > 5) {
  const fallback = parseWithVerible(filePath);
  if (fallback) {
    return mergeFallbackRecords(fallback, treeSitterPartial);
  }
}
```

`mergeFallbackRecords` should *append* Verible records to whatever tree-sitter produced cleanly — don't discard partial tree-sitter results. Conflicts (same entity, both parsers): prefer Verible.

- [ ] **Step 6: Run + commit**

```bash
cd tools/codegraph
npm test -- verilog
git add src/languages/verilog.ts src/languages/verilog_verible_fallback.ts \
        test/languages/verilog/verible_fallback.test.ts \
        test/languages/verilog/fixtures/breakage.sv
git commit -m "feat(verilog): verible fallback for tree-sitter parse errors"
git push
cd -
```

---

### Task 3: Merge Verible-derived records into the SQLite path

**Files (in the fork):**
- Modify: `src/extractors/persist.ts` (or whichever file the upstream uses to write entity/relation rows into SQLite).
- Modify: existing tests if the persistence path is unit-tested.

**Interfaces:**
- Consumes: the merged `{entities, relations}` from Task 2.
- Produces: SQLite rows tagged with the fallback `extractor` value. Phase 2's bundle exporter reads `extractor` directly into the bundle's `extractor` field; no exporter changes needed (verify in Task 4 acceptance).

- [ ] **Step 1: Confirm the persistence path treats `extractor` as opaque**

```bash
grep -rn 'extractor' tools/codegraph/src/extractors/ tools/codegraph/src/storage/ | head
```

If `extractor` is hard-coded somewhere (e.g. always `"tree_sitter"`), patch that file to pass through the value from the language module. If it's already plumbed through, no change required.

- [ ] **Step 2: Add a SQLite-level assertion test**

(If the upstream test harness allows.) Assert that after indexing `breakage.sv`, the `symbols` table contains at least one row whose `extractor` column equals `codegraph_verible_fallback_v2`.

- [ ] **Step 3: Commit any persistence-path patch**

```bash
git add tools/codegraph/src/...
git commit -m "feat(verilog): persist extractor tag for fallback records"
git push
```

(Skip if no patch was needed.)

---

### Task 4: Re-index Vortex, re-measure error rate, acceptance

**Files:**
- Create (by running): `runs/v2_parity/codegraph_index_vortex_phase6.log` and a follow-up parse-coverage measurement via `scripts/feasibility/measure_rtl_parse_coverage.py` re-run.
- Create: `runs/feasibility_v2_analyzer/phase6_acceptance.md`
- Modify: `analyzer_v2_codegraph_treesitter_plan.md` § 9 — Phase 6 row to `complete`.

**Interfaces:**
- Consumes: the fork with Phase 6 fallback installed; Vortex repo.
- Produces: a re-measured per-file error rate. Acceptance bar: < 1% across Vortex RTL.

The re-measurement uses CodeGraph's *combined* (tree-sitter + Verible) outcome, not tree-sitter alone. Modify the measurement to read from CodeGraph's index log rather than re-parsing with raw tree-sitter:

- [ ] **Step 1: Re-index**

```bash
cd tools/codegraph && npm run build && cd -
"$CG_BIN" index repo_sources/vortex 2>&1 | tee runs/v2_parity/codegraph_index_vortex_phase6.log
```

- [ ] **Step 2: Count files that failed both parsers**

CodeGraph's per-file log line format depends on the upstream; grep for the failure marker. Sketch:

```bash
grep -c '^FAILED\|^ERROR.*both' runs/v2_parity/codegraph_index_vortex_phase6.log || true
total=$(find repo_sources/vortex \( -name '*.sv' -o -name '*.v' \
        -o -name '*.svh' -o -name '*.vh' \) -type f | wc -l)
echo "Both-parser failures: <count>; total RTL files: $total"
```

Compute the rate: `failures / total < 0.01`?

- [ ] **Step 3: Re-export + re-emit signals**

```bash
uv run python skills/benchmark-repo-analyzer/scripts/codegraph_to_bundle.py \
    --db "$CG_DB" --project vortex --source-set-id vortex_main \
    --repo-name vortex/vortex \
    --out runs/vortex_context_bundle/
uv run python skills/benchmark-repo-analyzer/scripts/signal_emitter.py \
    --bundle runs/vortex_context_bundle/ --project vortex
```

(Phase 5 has already made `runs/vortex_context_bundle/` the canonical path.)

- [ ] **Step 4: Confirm Phase 5 acceptance still holds**

```bash
# Re-run smoke50 and the strict gate, then confirm L3 survival ≥ 15/60.
# (Reuse the Phase 5 Task 3 invocation; output to runs/v2_parity/vortex_smoke50_phase6.*)
```

If L3 survival regressed after Phase 6, the fallback is introducing noise — tighten its trigger threshold (raise the error-count cutoff in Task 2 Step 5) or improve the Verible-to-record mapping.

- [ ] **Step 5: Acceptance report**

```markdown
# Analyzer v2 Phase 6 — Acceptance

Verible version: <from VERSION.txt>
Phase 0 bucket triggering this phase: <80-95%>

## Per-file error rate (Vortex)

- Tree-sitter only (Phase 0 measurement): <a>%
- Tree-sitter + Verible fallback (after Phase 6): <b>%
- Acceptance bar: < 1%. [PASS / FAIL]

## Phase 5 acceptance regression check

- Vortex L3 row survival after re-run smoke50: <n>/60 (Phase 5 was <m>/60). [PASS / FAIL]
- conditional_behavior anchors in license zone: 0 (must remain 0). [PASS / FAIL]

## Notes

- Fallback fired on <n> files; <list of top-5 fixtures>.
- Tree-sitter-only files: <count>.
- Both-parser failures: <count> (these become Phase 1.5 follow-ups).
```

- [ ] **Step 6: Update tracker + commit**

```bash
# Flip § 9 Phase 6 row to complete (or to `skipped` with note if Phase 0 didn't trigger it).
git add analyzer_v2_codegraph_treesitter_plan.md \
        runs/feasibility_v2_analyzer/phase6_acceptance.md
git commit -m "docs(analyzer-v2/phase-6): verible fallback acceptance; error rate < 1%"
```

---

## Acceptance for "Phase 6 is done"

1. `tools/verible/VERSION.txt` records a pinned Verible version; the binary works on the dev machine.
2. The fork's `verible_fallback.test.ts` passes — the breakage fixture is parsed via Verible.
3. After re-indexing Vortex with the fallback enabled, the per-file error rate is < 1%.
4. Phase 5 acceptance still holds — smoke50 L3 survival did not regress.
5. `runs/feasibility_v2_analyzer/phase6_acceptance.md` exists with PASS on all bullets.
6. `analyzer_v2_codegraph_treesitter_plan.md` § 9 Phase 6 row reads `complete` (or `skipped`, if Phase 0's bucket said Phase 6 wasn't needed).
