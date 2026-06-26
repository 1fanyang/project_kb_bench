# Analyzer v2 — Phase 1: Verilog Language Module for CodeGraph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Rewritten 2026-06-26** after Phase 0 found that the original plan's architectural assumptions were wrong. CodeGraph 1.1.1 uses WASM tree-sitter grammars + TypeScript `LanguageExtractor` objects (lists of tree-sitter node-type strings), **not** `.scm` query files. The earlier draft of this plan called for `queries/verilog/entities.scm` and a per-language resolver hook — neither exists in CodeGraph's actual architecture.

**Goal:** Teach CodeGraph 1.1.1 to index `.sv` / `.v` / `.svh` / `.vh` files so that `codegraph index` walks the Vortex (and NVDLA) RTL surface and populates the same `nodes` / `edges` tables it already populates for C++/Python. The Phase 0 acceptance verified that tree-sitter-verilog (Python binding) extracts useful AST shape from these files; this phase wires the equivalent path into CodeGraph's Node/WASM runtime.

**Architecture:** CodeGraph runs `web-tree-sitter` (WASM) and dispatches per language to a `LanguageExtractor` object that lists node-type names for functions, classes, methods, imports, calls, etc. To add Verilog:

1. Vendor `tree-sitter-verilog.wasm` into `tools/codegraph/src/extraction/wasm/` (the build copies it to `dist/extraction/wasm/`).
2. Register `'verilog'` in `Language` (`src/types.ts`), in `WASM_GRAMMAR_FILES` and `EXTENSION_MAP` (`src/extraction/grammars.ts`), and in the `EXTRACTORS` map (`src/extraction/languages/index.ts`).
3. Author `src/extraction/languages/verilog.ts` exporting `verilogExtractor: LanguageExtractor` with the node-type lists Phase 0 measured against real RTL.

Cross-file resolution is **not** part of Phase 1. CodeGraph's resolver (`src/resolution/`) is language-agnostic and infers references from the extractor's `importTypes` / `callTypes` plus standard name-matching. If Verilog needs special resolution (e.g. `\`include "foo.svh"` → file lookup, `module child` instantiation → module declaration), that's a Phase 1.5 follow-on we file *after* measuring what CodeGraph's generic resolver does on its own.

**Tech Stack:** Node.js ≥ 22.5 (CodeGraph requires `node:sqlite`; use `/opt/homebrew/opt/node@22/bin/node` on the dev box), TypeScript, `web-tree-sitter` (already a CodeGraph dep), tree-sitter-verilog grammar source (build target: WASM via `tree-sitter build --wasm`).

## Global Constraints

- All in-fork changes happen inside `tools/codegraph/` (cloned in Phase 0 at `colbymchenry/codegraph@4077ed1`, v1.1.1). Do not edit anything under `skills/`, `schemas/`, `runs/`, or `scripts/` in this phase.
- Branch off the Phase 0-pinned sha (`4077ed1`) on a `feat/verilog-language-module` branch; do not rebase onto upstream `main` mid-phase.
- All Verilog node-type names used in `verilogExtractor` must come from the Phase 0 measurement (`runs/feasibility_v2_analyzer/_observed_node_kinds.md`). Notably:
  - control flow: `conditional_statement` (NOT `if_statement`), `case_statement`, `always_construct` (NOT `always_block`)
  - instantiation: all three of `module_instantiation` / `checker_instantiation` / `udp_instantiation` (tree-sitter-verilog cannot disambiguate without semantic context, so the extractor lists all three under "function call"-equivalent roles)
- The fork remote URL is **PH1-D1** below — locked at fork creation. Default: personal GitHub fork until a project-owned remote is provisioned.
- Per Phase 0 D7: per-file regex fallback is retained. A file CodeGraph's Verilog extractor errors on must not block indexing.

## Open decisions to lock before Task 1

| # | Decision | Default | Locks at |
|---|---|---|---|
| D1 | Fork remote URL for `tools/codegraph/` | Personal GitHub fork (push deferred until Phase 5) | Task 1 |
| D2 | WASM acquisition: pre-built from `tree-sitter-wasms@1.x` vs. build-from-source via `tree-sitter generate` | Build-from-source — `tree-sitter-wasms` does not currently ship Verilog | Task 2 |
| D3 | Should `verilogExtractor.classTypes` include `module_declaration`? | Yes (modules are the closest analogue to "container of state + behavior") | Task 4 |
| D4 | Should `interface_declaration` map to `classTypes` or to a new `interfaceTypes`? | `interfaceTypes` (matches the LanguageExtractor's `interface/protocol/trait` slot) | Task 4 |
| D5 | Phase 1.5 cross-file resolution: ship in Phase 1 or defer | Defer; measure generic resolver behavior in Task 6 first | Task 6 |

---

## File Structure

All paths relative to `tools/codegraph/` (the fork checkout).

Create:

- `src/extraction/languages/verilog.ts` — exports `verilogExtractor: LanguageExtractor` with node-type arrays for module/parameter/function/task/interface/package, the three instantiation kinds, and `conditional_statement` / `case_statement` / `always_construct`.
- `src/extraction/wasm/tree-sitter-verilog.wasm` — vendored grammar binary. Build script `scripts/build-verilog-wasm.sh` (also new) clones tree-sitter-verilog source, runs `tree-sitter generate && tree-sitter build --wasm`, and drops the output here.
- `scripts/build-verilog-wasm.sh` — reproducible WASM build. Records the grammar source commit sha in `src/extraction/wasm/tree-sitter-verilog.wasm.sha256.txt`.
- `__tests__/languages/verilog.test.ts` — vitest unit test with small `.sv` / `.v` fixtures verifying entity/edge extraction. Mirrors `__tests__/languages/python.test.ts` (or whichever existing language test matches the project's convention; confirm in Task 4 Step 1).
- `__tests__/languages/fixtures/verilog/{entities.sv, relations.sv, conditions.sv}` — three fixture files exercising the extractor's three input shapes.

Modify:

- `src/types.ts` — add `'verilog'` to the `LANGUAGES` tuple.
- `src/extraction/grammars.ts` — add `verilog: 'tree-sitter-verilog.wasm'` to `WASM_GRAMMAR_FILES`; add `'.sv'`, `'.v'`, `'.svh'`, `'.vh'` → `'verilog'` to `EXTENSION_MAP`. Note: the existing `GrammarLanguage` exclusion list (`Exclude<Language, 'svelte' | ...>`) must NOT exclude `'verilog'`, so the bare addition above is sufficient.
- `src/extraction/languages/index.ts` — import `verilogExtractor` and add `verilog: verilogExtractor` to the `EXTRACTORS` map.
- `package.json` — bump fork version to `1.1.1-verilog-phase-1` (or similar — pick a recognizable suffix). Do not add `tree-sitter-verilog` as an npm dep; we use WASM only.
- `README.md` — single-paragraph note that this fork adds Verilog/SystemVerilog support.

Do not modify:

- Any file outside `tools/codegraph/`.
- Any other language's extractor or grammar registration.
- The resolver (`src/resolution/`). Phase 1 measures generic resolver behavior on Verilog and files follow-ons; it does not change the resolver.

---

### Task 1: Branch the fork and lock fork-remote decision (D1)

**Files:**
- Modify: `tools/codegraph/` (remote/branch config only — no in-tree edits in this task).

**Interfaces:**
- Consumes: Phase 0's pinned sha `4077ed1` (`runs/feasibility_v2_analyzer/_codegraph_commit.txt`).
- Produces: a `feat/verilog-language-module` branch in the fork checkout. All later tasks commit on it.

- [ ] **Step 1: Lock D1 — fork remote URL**

Ask the operator: where does the project-owned CodeGraph fork live? Until a project-org remote is provisioned, default to local-only (no push to a remote until Phase 5). Record the chosen remote URL — or the explicit "local-only" choice — in `runs/feasibility_v2_analyzer/_codegraph_paths.md` under a new "Fork remote" heading. Phase 5 sign-off requires this to be project-owned and pushed before promoting v2 to canonical.

- [ ] **Step 2: Branch from the Phase 0 pin**

```bash
cd tools/codegraph
PIN=$(cat ../../runs/feasibility_v2_analyzer/_codegraph_commit.txt)
# The Phase 0 clone was shallow; unshallow first so we can branch off the pin sha.
git fetch --unshallow origin || true
git checkout -b feat/verilog-language-module "$PIN"
git remote rename origin upstream
# Skip the next two lines if D1 was locked to "local-only".
git remote add origin <fork-url-from-D1>
git push -u origin feat/verilog-language-module
```

Expected: branch at `$PIN`. `git remote -v` lists `upstream` (colbymchenry), and `origin` only if D1 picked a remote.

- [ ] **Step 3: Record branch + remote in the project-side feasibility paths file**

Append to `runs/feasibility_v2_analyzer/_codegraph_paths.md`:

```markdown
## Fork (Phase 1+)

- Remote: `<fork-url or "local-only">`
- Branch: `feat/verilog-language-module`
- Branch base sha: `4077ed1` (matches `_codegraph_commit.txt`)
```

Commit on the project side:

```bash
cd /Users/yangyifan/projects/work/kb_benchmark/.claude/worktrees/dev-v1.3-analyzer-codegraph-phase0
git add runs/feasibility_v2_analyzer/_codegraph_paths.md
git commit -m "docs(analyzer-v2/phase-1): record codegraph fork remote + branch"
```

---

### Task 2: Acquire the tree-sitter-verilog WASM grammar (D2)

**Files (in the fork):**
- Create: `scripts/build-verilog-wasm.sh` — reproducible build script.
- Create: `src/extraction/wasm/tree-sitter-verilog.wasm` — the built artifact.
- Create: `src/extraction/wasm/tree-sitter-verilog.wasm.sha256.txt` — sha256 + source commit pin.

**Interfaces:**
- Consumes: nothing in CodeGraph; pulls tree-sitter-verilog grammar source from `https://github.com/tree-sitter/tree-sitter-verilog`.
- Produces: a WASM binary that CodeGraph's `grammars.ts` loader can `Parser.Language.load()`. Task 3 references its filename.

CodeGraph's existing bundled WASMs (csharp/lua/luau/pascal/r/scala) follow this pattern: vendored binary in `src/extraction/wasm/`, copied to `dist/extraction/wasm/` by the `copy-assets` build step. The other ~15 languages come from the `tree-sitter-wasms` npm package; that package does NOT currently include Verilog, so we build our own.

- [ ] **Step 1: Verify tree-sitter CLI is available**

```bash
which tree-sitter || npm i -g tree-sitter-cli
tree-sitter --version
```

Expected: tree-sitter ≥ 0.22. The `tree-sitter build --wasm` command needs Emscripten available on PATH (or Docker for the `--docker` variant). On macOS, `brew install emscripten` provides `emcc`.

- [ ] **Step 2: Author the build script**

```bash
#!/usr/bin/env bash
# scripts/build-verilog-wasm.sh
# Reproducible build of tree-sitter-verilog.wasm from the upstream grammar source.
set -euo pipefail

GRAMMAR_REPO="https://github.com/tree-sitter/tree-sitter-verilog"
# Pin a specific commit so re-running gives byte-identical output.
GRAMMAR_PIN="${VERILOG_GRAMMAR_PIN:-}"  # Filled by Step 3
WORK="$(mktemp -d)"
DEST_DIR="$(cd "$(dirname "$0")/.." && pwd)/src/extraction/wasm"
DEST_FILE="$DEST_DIR/tree-sitter-verilog.wasm"
SHA_FILE="$DEST_DIR/tree-sitter-verilog.wasm.sha256.txt"

git clone "$GRAMMAR_REPO" "$WORK/src"
cd "$WORK/src"
[ -n "$GRAMMAR_PIN" ] && git checkout "$GRAMMAR_PIN"
ACTUAL_PIN="$(git rev-parse HEAD)"

# Verilog is a JS-defined grammar; we may need `npm install` to pull dependencies
# of grammar.js (e.g. tree-sitter version it pins) before generate.
npm install --no-audit --no-fund --silent || true

tree-sitter generate
tree-sitter build --wasm --output "$DEST_FILE"

cd -
sha="$(shasum -a 256 "$DEST_FILE" | awk '{print $1}')"
{
  echo "wasm_sha256: $sha"
  echo "grammar_repo: $GRAMMAR_REPO"
  echo "grammar_commit: $ACTUAL_PIN"
  echo "built_at: $(date -u +%FT%TZ)"
} > "$SHA_FILE"
rm -rf "$WORK"
echo "Wrote $DEST_FILE and $SHA_FILE"
```

Make executable and commit.

- [ ] **Step 3: Pick a grammar pin and build**

Visit `https://github.com/tree-sitter/tree-sitter-verilog`. Pick the latest tagged release or commit on `master`. Record the sha you intend to use as `GRAMMAR_PIN`.

```bash
export VERILOG_GRAMMAR_PIN=<sha>
./scripts/build-verilog-wasm.sh
```

Expected: `src/extraction/wasm/tree-sitter-verilog.wasm` exists; `tree-sitter-verilog.wasm.sha256.txt` records sha + grammar pin. If `tree-sitter build --wasm` fails because emscripten is missing, install it (`brew install emscripten`) or use `tree-sitter build --wasm --docker` (Docker fallback).

- [ ] **Step 4: Verify the WASM loads under web-tree-sitter**

```bash
cd tools/codegraph
/opt/homebrew/opt/node@22/bin/node -e "
const { Parser, Language } = require('web-tree-sitter');
(async () => {
  await Parser.init();
  const lang = await Language.load('./src/extraction/wasm/tree-sitter-verilog.wasm');
  const p = new Parser();
  p.setLanguage(lang);
  const tree = p.parse('module m; endmodule');
  console.log('root.type=', tree.rootNode.type, 'has_error=', tree.rootNode.hasError);
})();
"
```

Expected: `root.type= source_file has_error= false`. If the WASM loads but parses with error, the grammar build mismatched the runtime ABI — rebuild after `npm i web-tree-sitter@<matching-version>`.

- [ ] **Step 5: Commit**

```bash
cd tools/codegraph
git add scripts/build-verilog-wasm.sh \
        src/extraction/wasm/tree-sitter-verilog.wasm \
        src/extraction/wasm/tree-sitter-verilog.wasm.sha256.txt
git commit -m "feat(verilog): vendor tree-sitter-verilog.wasm grammar"
git push  # only if D1 locked to a remote
```

---

### Task 3: Register `'verilog'` in the type system + grammars registry

**Files (in the fork):**
- Modify: `src/types.ts` (add `'verilog'` to the `LANGUAGES` tuple)
- Modify: `src/extraction/grammars.ts` (add to `WASM_GRAMMAR_FILES` + `EXTENSION_MAP` + the language-display-name map at the bottom of the file)

**Interfaces:**
- Consumes: the WASM filename from Task 2.
- Produces: TypeScript-level recognition of `'verilog'` as a `Language`. Task 4's extractor and Task 5's registration consume it.

- [ ] **Step 1: Add to the `LANGUAGES` tuple**

In `src/types.ts`, find the `LANGUAGES = [...]` constant. Add `'verilog',` in the appropriate alphabetical or grouping position (the file lists ~30 entries; place near `pascal` / `scala` / similar tier-2 languages).

- [ ] **Step 2: Add to `WASM_GRAMMAR_FILES`**

In `src/extraction/grammars.ts`:

```typescript
const WASM_GRAMMAR_FILES: Record<GrammarLanguage, string> = {
  // ... existing entries ...
  verilog: 'tree-sitter-verilog.wasm',
};
```

Verify the `GrammarLanguage = Exclude<Language, 'svelte' | 'vue' | ...>` type does NOT exclude `'verilog'`. If TypeScript complains that `verilog` isn't a valid `GrammarLanguage`, the exclusion list needs no change — verilog is parseable via WASM (unlike svelte/yaml/etc which use special-case paths).

- [ ] **Step 3: Add extension entries to `EXTENSION_MAP`**

```typescript
export const EXTENSION_MAP: Record<string, Language> = {
  // ... existing entries ...
  '.sv': 'verilog',
  '.svh': 'verilog',
  '.v': 'verilog',
  '.vh': 'verilog',
};
```

Note `.v` overlaps with V (the language) if/when V is added. Phase 1 takes the slot — file a follow-up if V is later requested.

- [ ] **Step 4: Update the display-name map at the bottom of grammars.ts**

There's a map near the bottom that maps language id → human display name (e.g. `cpp: 'C++'`). Add `verilog: 'Verilog/SystemVerilog'`.

- [ ] **Step 5: Build to catch type errors**

```bash
cd tools/codegraph
npm run build 2>&1 | tail -20
```

Expected: clean build (no TS errors). If `GrammarLanguage` excludes `verilog`, fix the exclusion list. If `EXTRACTORS` map errors because it expects an entry for every `Language`, ignore that — Task 5 wires the extractor.

- [ ] **Step 6: Commit**

```bash
git add src/types.ts src/extraction/grammars.ts
git commit -m "feat(verilog): register verilog as a Language; map .sv/.v/.svh/.vh to it"
```

---

### Task 4: Author `verilogExtractor: LanguageExtractor`

**Files (in the fork):**
- Create: `src/extraction/languages/verilog.ts`
- Create: `__tests__/languages/fixtures/verilog/entities.sv` (and `relations.sv`, `conditions.sv`)

**Interfaces:**
- Consumes: `LanguageExtractor` type from `src/extraction/tree-sitter-types.ts`; corrected node-type names from Phase 0 § 5.
- Produces: an extractor object Task 5 registers in the `EXTRACTORS` map.

- [ ] **Step 1: Mirror an existing tier-2 extractor**

```bash
cd tools/codegraph
sed -n '1,80p' src/extraction/languages/python.ts
sed -n '1,80p' src/extraction/languages/scala.ts
```

Pick the simpler one to mirror (probably `scala.ts`). Note the field shape: arrays of node-type strings (`functionTypes`, `classTypes`, `methodTypes`, `importTypes`, `callTypes`, etc.) plus optional helper fns (`getSignature`, `isAsync`, `preParse`, …).

- [ ] **Step 2: Author the extractor**

`src/extraction/languages/verilog.ts`:

```typescript
import type { LanguageExtractor } from '../tree-sitter-types';

/**
 * Verilog / SystemVerilog extractor.
 *
 * Node-type names verified against tree-sitter-verilog (Phase 0 measurement,
 * see runs/feasibility_v2_analyzer/_observed_node_kinds.md). Key quirks:
 *
 * - if / else uses `conditional_statement`, NOT `if_statement`.
 * - always blocks use `always_construct` (covers `always`, `always_ff`,
 *   `always_comb`, `always_latch`).
 * - module instances disambiguate ambiguously: `child #(.W(8)) u(...)` →
 *   `module_instantiation`, `child u(.clk(clk))` → `checker_instantiation`,
 *   `child u(clk, reset)` → `udp_instantiation`. We list all three as
 *   callTypes; downstream resolution treats the target identifier as the
 *   instantiated entity name.
 */
export const verilogExtractor: LanguageExtractor = {
  functionTypes: ['function_declaration', 'task_declaration'],
  // A Verilog module is the closest analogue to a class — container of
  // state + behavior. Treat package_declaration the same way.
  classTypes: [
    'module_declaration',
    'package_declaration',
    'class_declaration',
  ],
  methodTypes: ['function_declaration', 'task_declaration'],
  interfaceTypes: ['interface_declaration'],
  structTypes: [],         // No native struct kind at this level
  enumTypes: [],
  typeAliasTypes: [],
  importTypes: [
    'include_directive',
    'package_import_declaration',
  ],
  callTypes: [
    // Module / UDP / checker instantiation — all three are how the grammar
    // disambiguates a `name u_instance(...)` site.
    'module_instantiation',
    'checker_instantiation',
    'udp_instantiation',
    // Subroutine (function/task) calls.
    'subroutine_call',
  ],
  variableTypes: ['parameter_declaration', 'net_declaration', 'data_declaration'],
  nameField: 'name',
  bodyField: 'body',
  paramsField: 'parameters',
  returnField: 'return_type',
  getSignature: () => undefined, // No SV-specific signature shape in Phase 1
};
```

- [ ] **Step 3: Author fixtures**

Three small fixtures under `__tests__/languages/fixtures/verilog/`:

`entities.sv`:

```systemverilog
package my_pkg; endpackage
`define MY_MACRO 1

interface my_if; endinterface

module sample #(parameter int W = 8) (input wire clk);
  function int double(int x); return x * 2; endfunction
  task automatic stim(); endtask
endmodule

class my_class; endclass
```

`relations.sv`:

```systemverilog
`include "stdlib.svh"
import shared_pkg::*;

module parent;
  child #(.W(8)) u_param (.clk(clk));   // module_instantiation
  child         u_named (.clk(clk));   // checker_instantiation
  child         u_pos   (clk);          // udp_instantiation
endmodule

module child (input wire clk); endmodule
```

`conditions.sv`:

```systemverilog
module m (input wire clk, input wire [1:0] sel, output reg q);
  always_ff @(posedge clk) begin
    if (sel == 2'b00) q <= 1'b0;
    else case (sel)
      2'b01: q <= 1'b1;
      default: q <= q;
    endcase
  end
endmodule
```

- [ ] **Step 4: Vitest unit test**

`__tests__/languages/verilog.test.ts` (mirror an existing language test such as `python.test.ts`):

```typescript
import { describe, it, expect } from 'vitest';
import { extractFromSource } from '../../src/extraction/parse-worker'; // confirm actual export
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const FIX = (name: string) =>
  readFileSync(resolve(__dirname, `languages/fixtures/verilog/${name}`), 'utf8');

describe('verilog extractor', () => {
  it('captures module / package / interface / class / function / task', async () => {
    const result = await extractFromSource(FIX('entities.sv'), 'verilog');
    const kinds = result.nodes.map(n => n.kind).sort();
    expect(kinds).toEqual(expect.arrayContaining([
      'class', 'function', 'interface', 'method', 'variable',
    ]));
    const names = result.nodes.map(n => n.name);
    expect(names).toContain('sample');     // module
    expect(names).toContain('my_pkg');     // package
    expect(names).toContain('my_if');      // interface
    expect(names).toContain('my_class');   // class
    expect(names).toContain('double');     // function
    expect(names).toContain('stim');       // task
  });

  it('captures all three instantiation kinds as call edges', async () => {
    const result = await extractFromSource(FIX('relations.sv'), 'verilog');
    const callTargets = result.edges
      .filter(e => e.kind === 'calls')
      .map(e => e.targetName);
    expect(callTargets.filter(t => t === 'child').length).toBeGreaterThanOrEqual(3);
  });
});
```

(The exact import paths `extractFromSource` / `parse-worker` are placeholders — Task 4 Step 1 confirms the real test-side entry point by reading an existing language test.)

- [ ] **Step 5: Commit (pre-build; Task 5 wires + tests)**

```bash
git add src/extraction/languages/verilog.ts \
        __tests__/languages/fixtures/verilog/ \
        __tests__/languages/verilog.test.ts
git commit -m "feat(verilog): verilogExtractor and fixtures (not yet registered)"
```

---

### Task 5: Register `verilogExtractor` in the `EXTRACTORS` map

**Files (in the fork):**
- Modify: `src/extraction/languages/index.ts`

**Interfaces:**
- Consumes: `verilogExtractor` from Task 4.
- Produces: a fully wired Verilog path. Tasks 6 and 7 verify it end-to-end.

- [ ] **Step 1: Add the import and map entry**

```typescript
// At the top of src/extraction/languages/index.ts, alongside other imports:
import { verilogExtractor } from './verilog';

// In the EXTRACTORS map, add:
export const EXTRACTORS: Partial<Record<Language, LanguageExtractor>> = {
  // ... existing entries ...
  verilog: verilogExtractor,
};
```

- [ ] **Step 2: Build + run the Verilog test**

```bash
cd tools/codegraph
npm run build 2>&1 | tail -5
npm test -- verilog 2>&1 | tail -30
```

Expected: build is clean; verilog.test.ts passes. If a test fails, dump the actual AST node kinds via the Phase 0 probe pattern, then update `verilogExtractor` arrays (these node-type names are the load-bearing knob — adjust them, not the test expectations).

- [ ] **Step 3: Commit**

```bash
git add src/extraction/languages/index.ts
git commit -m "feat(verilog): register verilogExtractor in EXTRACTORS map"
```

---

### Task 6: Smoke index a single RTL file and observe generic-resolver behaviour (locks D5)

**Files:**
- Create (by running): `runs/feasibility_v2_analyzer/phase1_smoke.log`
- Refresh (by running, inside `repo_sources/vortex`): `.codegraph/codegraph.db`

**Interfaces:**
- Consumes: the fork built with Verilog support; the existing Vortex Phase 0 install at `repo_sources/vortex/.codegraph/`.
- Produces: an indexed graph that includes Verilog `nodes` + `edges`. Inspecting it tells us whether the **generic** resolver already handles enough Verilog cross-file resolution to skip Phase 1.5, or whether a Verilog-specific resolver patch is needed (D5).

- [ ] **Step 1: Refresh the Vortex index with Verilog enabled**

```bash
cd /Users/yangyifan/projects/work/kb_benchmark/.claude/worktrees/dev-v1.3-analyzer-codegraph-phase0
# Ensure fresh fork build:
( cd tools/codegraph && npm run build > /dev/null )
# Re-index Vortex; the old DB will be wiped because `index` does a full rebuild.
/opt/homebrew/opt/node@22/bin/node tools/codegraph/dist/bin/codegraph.js index \
    /Users/yangyifan/projects/work/kb_benchmark/repo_sources/vortex \
    2>&1 | tee runs/feasibility_v2_analyzer/phase1_smoke.log
```

Expected: indexed file count increases vs Phase 0 by roughly the count of usable RTL files (~192 for Vortex per Phase 0). Hard-error files log per-file errors but do not abort.

- [ ] **Step 2: Sanity SQL — Verilog nodes show up**

```bash
DB=/Users/yangyifan/projects/work/kb_benchmark/repo_sources/vortex/.codegraph/codegraph.db
sqlite3 "$DB" "SELECT kind, COUNT(*) FROM nodes WHERE language='verilog' GROUP BY kind ORDER BY 2 DESC;"
sqlite3 "$DB" "SELECT kind, COUNT(*) FROM edges
               WHERE source IN (SELECT id FROM nodes WHERE language='verilog')
               GROUP BY kind ORDER BY 2 DESC;"
```

Expected: non-zero counts for `class` / `method` / `function` / `variable` (on the node side) and `calls` / `contains` / `imports` (on the edge side). If all zero, the extractor never ran — re-check Task 5's registration + Task 3's `EXTENSION_MAP` entries.

- [ ] **Step 3: Probe cross-file resolution on a real Vortex module name**

```bash
# Pick a Vortex module name from the SQL above (e.g. VX_cache_bypass):
/opt/homebrew/opt/node@22/bin/node tools/codegraph/dist/bin/codegraph.js node VX_cache_bypass \
    --path /Users/yangyifan/projects/work/kb_benchmark/repo_sources/vortex
/opt/homebrew/opt/node@22/bin/node tools/codegraph/dist/bin/codegraph.js callers VX_cache_bypass \
    --path /Users/yangyifan/projects/work/kb_benchmark/repo_sources/vortex --json
```

Read the results. **Lock D5 here:**

- If the generic resolver returns plausible cross-file callers (a parent module instantiating `VX_cache_bypass`), Phase 1.5 is **deferred** — generic resolution is good enough.
- If it returns empty / nonsensical results, file a Phase 1.5 task: a Verilog-aware sub-resolver in `src/resolution/` that maps module-instantiation target names → module-declaration entities by exact-name lookup.

- [ ] **Step 4: Commit the smoke log**

```bash
git add runs/feasibility_v2_analyzer/phase1_smoke.log
git commit -m "chore(analyzer-v2/phase-1): vortex smoke-index with verilog extractor"
```

---

### Task 7: Acceptance sweep + Phase 1 sign-off

**Files:**
- Create: `runs/feasibility_v2_analyzer/phase1_acceptance.md`
- Modify: `analyzer_v2_codegraph_treesitter_plan.md` § 9 — flip Phase 1 row to `complete`.

**Interfaces:**
- Consumes: the indexed Vortex DB from Task 6; the smoke-log + probe output from Task 6 Step 3.
- Produces: an acceptance report. Phase 2 reads its sign-off line.

- [ ] **Step 1: Acceptance metrics**

```bash
DB=/Users/yangyifan/projects/work/kb_benchmark/repo_sources/vortex/.codegraph/codegraph.db
echo "files (all languages):     $(sqlite3 $DB 'SELECT COUNT(*) FROM files;')"
echo "files (verilog):           $(sqlite3 $DB \"SELECT COUNT(*) FROM files WHERE language='verilog';\")"
echo "nodes (verilog):           $(sqlite3 $DB \"SELECT COUNT(*) FROM nodes WHERE language='verilog';\")"
echo "edges (verilog source):    $(sqlite3 $DB \"SELECT COUNT(*) FROM edges WHERE source IN (SELECT id FROM nodes WHERE language='verilog');\")"
echo "modules (class kind):      $(sqlite3 $DB \"SELECT COUNT(*) FROM nodes WHERE language='verilog' AND kind='class';\")"
echo "tasks/functions:           $(sqlite3 $DB \"SELECT COUNT(*) FROM nodes WHERE language='verilog' AND kind IN ('function','method');\")"
echo "instantiation edges:       $(sqlite3 $DB \"SELECT COUNT(*) FROM edges WHERE kind='calls' AND source IN (SELECT id FROM nodes WHERE language='verilog');\")"
echo "import edges:              $(sqlite3 $DB \"SELECT COUNT(*) FROM edges WHERE kind='imports' AND source IN (SELECT id FROM nodes WHERE language='verilog');\")"
```

Expected (rough order-of-magnitude, given Phase 0 found 128 modules in Vortex):

- verilog files: ~190 (Phase 0 usable count)
- verilog nodes: ≥ 500 (modules + parameters + tasks + functions + nets)
- modules (class): ≥ 100
- instantiation edges: ≥ 50

- [ ] **Step 2: Write acceptance report**

`runs/feasibility_v2_analyzer/phase1_acceptance.md`:

```markdown
# Analyzer v2 Phase 1 — Acceptance

Fork: `tools/codegraph/` on `feat/verilog-language-module` @ <sha>
Verilog grammar pin: <from src/extraction/wasm/tree-sitter-verilog.wasm.sha256.txt>

## Acceptance metrics (Vortex)

(numbers from Task 7 Step 1)

## Acceptance bullets

- [x|✗] CodeGraph index completes on full Vortex (RTL included) without aborting.
- [x|✗] Verilog `nodes` count > 0; distribution looks plausible.
- [x|✗] At least one instantiation edge present in `edges` for Vortex Verilog sources.
- [x|✗] `npm test -- verilog` passes inside the fork.
- [x|✗] Generic resolver behaviour on Verilog observed; D5 decision locked.

## D5 decision

<defer Phase 1.5 | file Phase 1.5 follow-up with task list>

## Notes / observed gaps

- <files that errored at extraction time, count and example paths>
- <any extractor-list adjustments made during Task 5 iteration>

## Phase 2 GO / NO-GO

<…>
```

- [ ] **Step 3: Flip the master plan tracker**

In `analyzer_v2_codegraph_treesitter_plan.md` § 9, set the Phase 1 row to:

```
| 1 — Verilog language module | complete | <YYYY-MM-DD> | branch=fork/feat/verilog-language-module @ <sha>; D5=<defer|follow-up> |
```

- [ ] **Step 4: Commit**

```bash
git add runs/feasibility_v2_analyzer/phase1_acceptance.md \
        analyzer_v2_codegraph_treesitter_plan.md
git commit -m "docs(analyzer-v2/phase-1): acceptance; phase-2 GO"
```

---

## Acceptance for "Phase 1 is done"

1. Fork branch `feat/verilog-language-module` exists with: vendored WASM grammar, language-registry entries, `verilogExtractor`, fixtures, passing vitest.
2. `npm test -- verilog` passes inside the fork.
3. `codegraph index repo_sources/vortex` completes without abort and populates `nodes` and `edges` with `language='verilog'` rows.
4. Verilog instantiation edges (`kind='calls'`) are non-zero for Vortex.
5. `runs/feasibility_v2_analyzer/phase1_acceptance.md` exists with all bullets checked and D5 explicitly locked.
6. `analyzer_v2_codegraph_treesitter_plan.md` § 9 Phase 1 row reads `complete`.
