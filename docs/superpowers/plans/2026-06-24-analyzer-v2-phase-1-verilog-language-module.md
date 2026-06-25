# Analyzer v2 — Phase 1: Verilog Language Module for CodeGraph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Sketched plan — Phase 0 must ship first.** Several fields below are marked **PH0** and must be replaced with values from `runs/feasibility_v2_analyzer.md` before this plan can be executed. Do not start Task 1 until that report's § 6 GO line is filled.

**Goal:** Ship a working Verilog language module inside a project-owned fork of CodeGraph so that `codegraph index <repo>` parses `.sv` / `.v` / `.svh` / `.vh` files, emits the same kinds of entities and relations as CodeGraph's built-in languages, and resolves cross-file references (module instantiation, `\`include`, package import) where syntactically possible.

**Architecture:** Fork `colbymchenry/codegraph`, pin the base commit, add `tree-sitter-verilog` as a Node dependency, register file extensions, author three tree-sitter query files (`entities.scm`, `relations.scm`, optional `conditions.scm`) under the fork's `queries/verilog/` directory, and extend the resolver to map Verilog-specific references. The fork lives under `tools/codegraph/` (a project-local checkout, see Phase 0); changes are committed on a feature branch in that checkout and pushed to a project-owned remote.

**Tech Stack:** Node.js + CodeGraph (host runtime), `tree-sitter-verilog` (Node grammar package), tree-sitter S-expression query language (for `.scm` files), TypeScript or JavaScript (depending on CodeGraph's resolver language — confirm in Task 5).

## Global Constraints

- All changes happen inside the `tools/codegraph/` checkout from Phase 0. Do not edit anything under `skills/`, `schemas/`, or `runs/` in this phase.
- The base CodeGraph commit was pinned in Phase 0 (`runs/feasibility_v2_analyzer/_codegraph_commit.txt`). Branch off that exact sha.
- The project-owned fork remote URL is **PH0-D1** (locked during Phase 0 sign-off; defaults to a personal GitHub fork if no project remote exists yet).
- All node kind names in `.scm` query files must match what tree-sitter-verilog actually emits — pull the authoritative list from Phase 0 § 5 of the feasibility report.
- Per Phase 0 D7, regex fallback per-file is retained: a file that tree-sitter errors on must not block indexing. Verify this still holds after each query is added.
- License: CodeGraph upstream license + tree-sitter-verilog license. Phase 0 should have recorded both; if not, surface and resolve before Task 1.

---

## File Structure

All paths below are relative to `tools/codegraph/` (the fork checkout). For the project-side audit, see the Acceptance section.

Create (inside the fork):

- `queries/verilog/entities.scm` — tree-sitter query that captures module / parameter / function / task / interface / package / `\`define` / class entities.
- `queries/verilog/relations.scm` — module instantiation, function/task calls, `\`include`, `import pkg::*`.
- `queries/verilog/conditions.scm` — **optional**; only if Phase 3's `conditional_behavior` signal needs entity-level handles for `if_statement` / `case_statement` / `always_construct`. Skip this file if Phase 3 can read AST kind directly off the relation evidence.
- `src/languages/verilog.ts` (or `.js`, matching CodeGraph's existing pattern) — language registration: extensions, grammar import, query bindings, resolver hook.
- `test/languages/verilog/fixtures/` — small `.sv` and `.v` fixture files for unit tests (4–6 files).
- `test/languages/verilog/verilog.test.ts` (or matching test convention) — unit tests for the queries and resolver.

Modify (inside the fork):

- `package.json` — add `tree-sitter-verilog` as a dependency; bump the fork's own version.
- `src/languages/index.ts` (or the language registry the project actually uses) — register the new module.
- `src/resolver/index.ts` (or equivalent) — call into the new Verilog resolver hook.
- `README.md` — single line noting the fork adds Verilog support and pointing at the upstream PR or this plan.

Do not modify:

- Any file outside `tools/codegraph/` during Phase 1.
- Built-in language modules (C, C++, Python, …) — Phase 1 is additive only.

---

### Task 1: Fork the CodeGraph repo and create the Phase 1 feature branch

**Files:**
- Modify: `tools/codegraph/` (remote configuration only — no in-tree edits in this task).

**Interfaces:**
- Consumes: pinned base commit from `runs/feasibility_v2_analyzer/_codegraph_commit.txt` (Phase 0); project-owned remote URL **PH0-D1**.
- Produces: a `feat/verilog-language-module` branch in the fork checkout, tracked against the project-owned remote. All later tasks commit onto this branch.

- [ ] **Step 1: Confirm the fork remote**

```bash
cd tools/codegraph
git remote -v
```

If `origin` still points at `colbymchenry/codegraph`, rename it to `upstream` and add the project-owned fork as `origin`. The fork URL is recorded in the Phase 0 D1 decision.

- [ ] **Step 2: Branch from the pinned commit**

```bash
PIN=$(cat ../../runs/feasibility_v2_analyzer/_codegraph_commit.txt)
git checkout -b feat/verilog-language-module "$PIN"
```

Expected: HEAD now at `$PIN` on a new branch.

- [ ] **Step 3: Push the branch to the fork**

```bash
git push -u origin feat/verilog-language-module
```

Expected: branch tracked on the project-owned remote.

- [ ] **Step 4: Record the fork+branch in the project-side plan**

In `analyzer_v2_codegraph_treesitter_plan.md` § 9, annotate the Phase 1 row's `Notes` cell with `branch=<fork>/feat/verilog-language-module @ <pin sha>`. Commit on the project side (not the fork):

```bash
cd ../../
git add analyzer_v2_codegraph_treesitter_plan.md
git commit -m "docs(analyzer-v2/phase-1): record codegraph fork + branch pin"
```

---

### Task 2: Add `tree-sitter-verilog` Node dependency and register file extensions

**Files (in the fork):**
- Modify: `package.json`
- Modify: the language-registry file (likely `src/languages/index.ts` — confirm in Step 1)
- Create: `src/languages/verilog.ts` (or `.js`) — initial stub.

**Interfaces:**
- Consumes: nothing from Phase 0 directly; the registry file path is whatever the upstream pattern is.
- Produces: a `verilog` language id that CodeGraph recognises for `.sv` / `.v` / `.svh` / `.vh`. Tasks 3–6 attach queries and resolution to this id.

- [ ] **Step 1: Discover the registry pattern**

```bash
cd tools/codegraph
grep -rn "registerLanguage\|languages\s*=\s*\[" src/ | head
ls src/languages/
```

Expected: a registry file (often `src/languages/index.ts`) that lists each built-in language. Match its existing pattern exactly when adding Verilog — do not introduce a new abstraction.

- [ ] **Step 2: Add the npm dep**

```bash
npm install tree-sitter-verilog --save
```

Expected: `package.json` gains `"tree-sitter-verilog": "^<version>"` under `dependencies`. Record the resolved version in the Phase 1 commit body.

- [ ] **Step 3: Stub the language module**

Create `src/languages/verilog.ts` matching the shape of an existing built-in (e.g. read `src/languages/python.ts` and mirror it). Minimum stub:

```typescript
// PH1 — exact import name and class shape depend on CodeGraph's
// existing language interface; mirror src/languages/python.ts exactly.
import Verilog from "tree-sitter-verilog";
import { Language } from "../core/language";  // PH1 — confirm actual path

export const verilogLanguage: Language = {
  id: "verilog",
  extensions: [".sv", ".v", ".svh", ".vh"],
  grammar: Verilog,
  queries: {
    // Filled in Tasks 3 and 4.
    entities: "",
    relations: "",
  },
  resolve: undefined, // Wired in Task 5.
};
```

- [ ] **Step 4: Register the stub**

In the registry file from Step 1, add `verilogLanguage` to the exported list. Follow the file's existing style (no reformatting elsewhere).

- [ ] **Step 5: Build + smoke**

```bash
npm run build  # or whatever the upstream README prescribes
node -e 'console.log(require("./dist/languages").languages.map(l => l.id))'
```

Expected: the printed list includes `"verilog"`.

- [ ] **Step 6: Index a tiny RTL file and confirm the loader picks the language**

Create a 6-line fixture under `test/languages/verilog/fixtures/tiny.sv`:

```systemverilog
module tiny (input wire clk, output wire q);
  reg r;
  always @(posedge clk) r <= ~r;
  assign q = r;
endmodule
```

Then run an indexing pass scoped to that one file (use whatever CLI form CodeGraph supports; the Phase 0 transcript shows the verb):

```bash
./bin/codegraph index test/languages/verilog/fixtures/ 2>&1 | tee /tmp/_phase1_smoke.log
```

Expected: the log shows the file being processed as language `verilog` (or whatever upstream's per-file log format is). No queries have run yet — entity counts stay zero. That's fine; the gate here is *loader picks Verilog*.

- [ ] **Step 7: Commit (inside the fork)**

```bash
git add package.json package-lock.json src/languages/verilog.ts <registry-file> test/languages/verilog/fixtures/tiny.sv
git commit -m "feat(verilog): register language and tree-sitter-verilog grammar"
git push
```

---

### Task 3: Author `queries/verilog/entities.scm`

**Files (in the fork):**
- Create: `queries/verilog/entities.scm`
- Modify: `src/languages/verilog.ts` to load the query.

**Interfaces:**
- Consumes: the observed node-kind list from Phase 0 `runs/feasibility_v2_analyzer.md` § 5 (`module_declaration`, `parameter_declaration`, `function_declaration`, `task_declaration`, `interface_declaration`, `package_declaration`, `class_declaration`, plus the actual `\`define` node kind — **PH0**).
- Produces: a query file that, when run against parsed RTL, captures the entity kinds Phase 2's bundle exporter expects in `entity_index.jsonl`.

- [ ] **Step 1: Draft the query**

Author `queries/verilog/entities.scm`. The exact node kind names below are placeholders — replace with whatever Phase 0 observed.

```scheme
; PH0 — node-kind names must match what tree-sitter-verilog actually emits
; (Phase 0 observed list lives in runs/feasibility_v2_analyzer.md § 5).

(module_declaration
  name: (simple_identifier) @entity.name) @entity.module

(parameter_declaration
  (list_of_param_assignments
    (param_assignment
      name: (parameter_identifier) @entity.name))) @entity.parameter

(function_declaration
  name: (simple_identifier) @entity.name) @entity.function

(task_declaration
  name: (simple_identifier) @entity.name) @entity.task

(interface_declaration
  name: (simple_identifier) @entity.name) @entity.interface

(package_declaration
  name: (simple_identifier) @entity.name) @entity.package

; `define handling — node kind name TBD by Phase 0 inspection; common candidates:
; text_macro_definition, `define_directive, preprocessor_define
(text_macro_definition
  name: (simple_identifier) @entity.name) @entity.macro

(class_declaration
  name: (simple_identifier) @entity.name) @entity.class
```

- [ ] **Step 2: Wire the query file into the language module**

In `src/languages/verilog.ts`, replace the `entities: ""` line with a load from `queries/verilog/entities.scm` (mirror how the Python module loads `queries/python/entities.scm`).

- [ ] **Step 3: Add a unit test that asserts entity counts on a fixture**

Create `test/languages/verilog/fixtures/entities_fixture.sv`:

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

Create `test/languages/verilog/verilog.test.ts` (mirror the upstream test pattern; pseudocode below):

```typescript
// PH1 — exact test-harness API depends on CodeGraph; mirror python.test.ts.
import { indexSync } from "../../../src";
import { resolve } from "path";

test("entities query captures all entity kinds on fixture", () => {
  const result = indexSync(resolve(__dirname, "fixtures/entities_fixture.sv"));
  const kinds = result.entities.map(e => e.kind).sort();
  expect(kinds).toEqual(
    ["class", "function", "interface", "macro", "module",
     "package", "parameter", "task"].sort()
  );
});
```

- [ ] **Step 4: Run the test**

```bash
npm test -- verilog.test  # or whatever the upstream test runner is
```

Expected: PASS. If any entity kind is missing, the corresponding tree-sitter node kind name in `entities.scm` is wrong — check the actual node kind via:

```bash
node -e 'const Parser=require("tree-sitter");const V=require("tree-sitter-verilog");const p=new Parser();p.setLanguage(V);const t=p.parse(require("fs").readFileSync("test/languages/verilog/fixtures/entities_fixture.sv","utf8"));function w(n,d=0){console.log(" ".repeat(d)+n.type);for(const c of n.children)w(c,d+2);}w(t.rootNode);'
```

Adjust the `.scm` query and re-run.

- [ ] **Step 5: Commit**

```bash
git add queries/verilog/entities.scm src/languages/verilog.ts \
        test/languages/verilog/fixtures/entities_fixture.sv \
        test/languages/verilog/verilog.test.ts
git commit -m "feat(verilog): entities.scm covering module/param/func/task/intf/pkg/macro/class"
git push
```

---

### Task 4: Author `queries/verilog/relations.scm`

**Files (in the fork):**
- Create: `queries/verilog/relations.scm`
- Modify: `src/languages/verilog.ts` to load the query.
- Modify: `test/languages/verilog/verilog.test.ts` — add relation-capture assertions.

**Interfaces:**
- Consumes: `entities.scm` from Task 3 (relations reference the same entity kinds); Phase 0 node-kind observations.
- Produces: tree-sitter captures that, when run by CodeGraph's relation extractor, emit `instantiates`, `calls`, `imports` (for `\`include` and `import pkg::*`) edges. Phase 2's bundle exporter consumes these directly.

- [ ] **Step 1: Draft the query**

```scheme
; PH0 — node-kind names confirmed by Phase 0 inspection.

; Module instantiation:  my_module #(.W(8)) inst1 (.clk(clk), .q(q));
(module_instantiation
  module_name: (simple_identifier) @target
  instance_name: (simple_identifier) @instance) @relation.instantiates

; Function / task call (subroutine_call covers both in tree-sitter-verilog typically)
(subroutine_call
  subroutine_name: (_) @target) @relation.calls

; `include "foo.svh"
(include_directive
  filename: (_) @target) @relation.imports

; import pkg::*  /  import pkg::sym
(package_import_declaration
  (package_import_item
    package: (simple_identifier) @target)) @relation.imports
```

- [ ] **Step 2: Load + wire into the language module**

Same pattern as Task 3 Step 2.

- [ ] **Step 3: Extend the fixture set**

Add `test/languages/verilog/fixtures/relations_fixture.sv`:

```systemverilog
`include "stdlib.svh"
import my_pkg::*;

module instantiator;
  child u_child (.clk(clk));
  initial stim();
endmodule

module child (input wire clk); endmodule
```

- [ ] **Step 4: Extend the test**

Append to `verilog.test.ts`:

```typescript
test("relations query captures instantiates/calls/imports", () => {
  const result = indexSync(resolve(__dirname, "fixtures/relations_fixture.sv"));
  const predicates = new Set(result.relations.map(r => r.predicate));
  expect(predicates.has("instantiates")).toBe(true);
  expect(predicates.has("calls")).toBe(true);
  expect(predicates.has("imports")).toBe(true);
});
```

- [ ] **Step 5: Run + iterate**

```bash
npm test -- verilog.test
```

Expected: PASS. If a predicate is missing, dump the parse tree as in Task 3 Step 4 to find the actual node kind name.

- [ ] **Step 6: Commit**

```bash
git add queries/verilog/relations.scm src/languages/verilog.ts \
        test/languages/verilog/fixtures/relations_fixture.sv \
        test/languages/verilog/verilog.test.ts
git commit -m "feat(verilog): relations.scm for instantiates/calls/imports"
git push
```

---

### Task 5: Extend the resolver for Verilog cross-file references

**Files (in the fork):**
- Modify: `src/languages/verilog.ts` — add a `resolve` hook.
- Modify: `src/resolver/index.ts` (or whichever file dispatches per-language resolvers).
- Create: `test/languages/verilog/fixtures/cross_file/` — a two-file fixture (instantiator + child module) for resolver tests.
- Modify: `test/languages/verilog/verilog.test.ts` — cross-file resolution assertions.

**Interfaces:**
- Consumes: the entity and relation outputs from Tasks 3 and 4 (the resolver runs *after* the per-file extractor).
- Produces: relations whose `target` field is an `entity_id` (resolved) rather than a bare name, for the three cases below. Phase 2's bundle exporter relies on resolved ids for the `object.id` field in `imports_or_includes` edges.

The three resolution cases for Verilog:

1. **Module instantiation** — `instantiates` edge `target` = name of a module declared elsewhere in the project. Resolve by exact-name lookup in the `module` entity table.
2. **`\`include "foo.svh"`** — `imports` edge `target` = a filename string. Resolve by basename match against the file table; on ambiguity prefer same-directory, then same `vmod`/`rtl` parent.
3. **`import pkg::*`** — `imports` edge `target` = package name. Resolve by exact-name lookup in the `package` entity table.

- [ ] **Step 1: Inspect the upstream resolver pattern**

```bash
cd tools/codegraph
grep -rn "resolve\s*(" src/languages/ | head
cat src/languages/python.ts | grep -A 30 'resolve'
```

Use whatever signature the upstream pattern uses. Do not invent a new resolver contract.

- [ ] **Step 2: Implement the resolver hook**

In `src/languages/verilog.ts`, replace `resolve: undefined,` with a function that handles the three cases. Pseudocode (real shape depends on Step 1):

```typescript
resolve: (rel, ctx) => {
  switch (rel.predicate) {
    case "instantiates":
      return ctx.findEntity({ kind: "module", name: rel.target }) ?? rel;
    case "imports": {
      // Two sub-cases distinguished by relation source-node kind, which the
      // extractor should have stashed on rel.metadata.sourceKind in Task 4.
      if (rel.metadata?.sourceKind === "include_directive") {
        return ctx.findFileByBasename(stripQuotes(rel.target), {
          preferDir: ctx.dirOf(rel.sourceFile),
        }) ?? rel;
      }
      return ctx.findEntity({ kind: "package", name: rel.target }) ?? rel;
    }
    case "calls":
      // Phase 1 leaves `calls` unresolved unless trivial (same-module function).
      // Cross-module call resolution is deferred to a follow-on phase.
      return rel;
    default:
      return rel;
  }
};
```

If Task 4 did not stash `metadata.sourceKind` on the relation, add it now (re-open `queries/verilog/relations.scm` and the extraction wiring; do not silently change the resolver to guess).

- [ ] **Step 3: Cross-file fixture**

Create `test/languages/verilog/fixtures/cross_file/parent.sv`:

```systemverilog
`include "child.svh"
import shared_pkg::*;

module parent;
  child u (.clk(1'b0));
endmodule
```

Create `test/languages/verilog/fixtures/cross_file/child.svh`:

```systemverilog
package shared_pkg; endpackage

module child (input wire clk); endmodule
```

- [ ] **Step 4: Resolver tests**

Append to `verilog.test.ts`:

```typescript
test("resolver resolves instantiates/imports across files", () => {
  const result = indexSync(resolve(__dirname, "fixtures/cross_file/"));
  const rels = result.relations;

  const inst = rels.find(r => r.predicate === "instantiates");
  expect(inst?.targetEntityId).toBeDefined();
  expect(result.entitiesById[inst!.targetEntityId].kind).toBe("module");

  const inc = rels.find(r => r.predicate === "imports"
                          && r.metadata?.sourceKind === "include_directive");
  expect(inc?.targetFileId).toBeDefined();
  expect(result.filesById[inc!.targetFileId].path).toMatch(/child\.svh$/);

  const pkg = rels.find(r => r.predicate === "imports"
                          && r.metadata?.sourceKind === "package_import_declaration");
  expect(pkg?.targetEntityId).toBeDefined();
  expect(result.entitiesById[pkg!.targetEntityId].kind).toBe("package");
});
```

- [ ] **Step 5: Run + iterate**

```bash
npm test -- verilog.test
```

Expected: PASS. If `targetEntityId` is undefined, the resolver isn't being dispatched — re-check the registration in `src/resolver/index.ts`.

- [ ] **Step 6: Commit**

```bash
git add src/languages/verilog.ts src/resolver/index.ts \
        test/languages/verilog/fixtures/cross_file/ \
        test/languages/verilog/verilog.test.ts
git commit -m "feat(verilog): resolver for instantiates / include / package imports"
git push
```

---

### Task 6: (Conditional) Author `queries/verilog/conditions.scm` for `if`/`case`/`always`

**Skip if:** Phase 3's design lands first and shows that `conditional_behavior` can be computed from a per-relation `evidence.ast_kind` field instead of needing standalone entities for control-flow nodes. In that case this task is replaced by a one-line metadata addition inside `relations.scm`. Confirm before starting.

**Files (in the fork):**
- Create: `queries/verilog/conditions.scm`
- Modify: `src/languages/verilog.ts`
- Modify: `test/languages/verilog/verilog.test.ts`

**Interfaces:**
- Consumes: tree-sitter node kind names for `if_statement`, `case_statement`, `always_construct` from Phase 0.
- Produces: zero-cost entity records per control-flow site that Phase 3's `conditional_behavior` emitter can anchor on. These records carry the precise line range, eliminating the v1 license-header anchor bug.

- [ ] **Step 1: Draft the query**

```scheme
(if_statement)         @entity.condition.if
(case_statement)       @entity.condition.case
(always_construct)     @entity.condition.always
```

(Node kind name `always_construct` is PH0-confirmed; if Phase 0 observed `always_block` instead, substitute.)

- [ ] **Step 2: Wire + test (same pattern as prior tasks)**

Fixture `test/languages/verilog/fixtures/conditions_fixture.sv`:

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

Test:

```typescript
test("conditions query captures if/case/always anchors with real line ranges", () => {
  const result = indexSync(resolve(__dirname, "fixtures/conditions_fixture.sv"));
  const conds = result.entities.filter(e => e.kind.startsWith("condition."));
  expect(conds.length).toBeGreaterThanOrEqual(3);
  // The whole point: none of these anchors fall in the first 10 lines if file
  // started with a license block. (For this fixture, all rows are >= line 2.)
  for (const c of conds) expect(c.startLine).toBeGreaterThan(1);
});
```

- [ ] **Step 3: Commit**

```bash
git add queries/verilog/conditions.scm src/languages/verilog.ts \
        test/languages/verilog/fixtures/conditions_fixture.sv \
        test/languages/verilog/verilog.test.ts
git commit -m "feat(verilog): conditions.scm for if/case/always anchors"
git push
```

---

### Task 7: Acceptance sweep on full Vortex RTL

**Files:**
- Create (by running, on the project side, not the fork): `runs/feasibility_v2_analyzer/phase1_vortex_index.log` and `runs/feasibility_v2_analyzer/phase1_acceptance.md`.
- Modify: `analyzer_v2_codegraph_treesitter_plan.md` § 9 — flip Phase 1 row to `complete`.

**Interfaces:**
- Consumes: the fork's `feat/verilog-language-module` branch (built); the Vortex repo at `repo_sources/vortex/`.
- Produces: an acceptance report establishing the four success criteria from the source plan (index completes, `codegraph explore` returns useful module info, kind-filtered queries work, `instantiates` resolves across files). Phase 2 reads this before starting.

- [ ] **Step 1: Rebuild the fork**

```bash
cd tools/codegraph
git checkout feat/verilog-language-module
npm run build
cd -
```

- [ ] **Step 2: Index full Vortex (including RTL this time)**

```bash
"$CG_BIN" index repo_sources/vortex \
    2>&1 | tee runs/feasibility_v2_analyzer/phase1_vortex_index.log
```

Expected: exit 0. Per-file errors logged for any RTL file the grammar choked on are *not* fatal (Phase 0 D7: fallback retained). Count the failures:

```bash
grep -c '^ERROR' runs/feasibility_v2_analyzer/phase1_vortex_index.log || true
```

If the failure count exceeds the Phase 0-observed `error` bucket by more than 10%, regress investigation before declaring acceptance.

- [ ] **Step 3: Verify the four acceptance checks**

Pick a real Vortex module (e.g. `VX_cache_bypass` — substitute whatever exists in the source).

```bash
# Check 1: explore returns module + instantiations + parameters
"$CG_BIN" explore VX_cache_bypass | tee /tmp/_ph1_check1.txt

# Check 2: kind filter works
"$CG_BIN" query --kind module 'VX_cache_*' | tee /tmp/_ph1_check2.txt

# Check 3: spot-check 5 files for cross-file instantiates resolution
"$CG_BIN" relations --predicate instantiates --limit 5 | tee /tmp/_ph1_check3.txt
```

For each, inspect the output and confirm it matches the source-plan acceptance bullet (module definition + instantiations + parameters; expected module names; resolved targets).

- [ ] **Step 4: Write the acceptance report**

Create `runs/feasibility_v2_analyzer/phase1_acceptance.md` with:

```markdown
# Analyzer v2 Phase 1 — Acceptance

Fork SHA on `feat/verilog-language-module`: <sha>

## Indexing
- Total RTL files indexed: <N>
- Parse-error files: <n> (vs Phase 0 baseline <m>; delta <±x%>)

## Acceptance checks
- [x|✗] `codegraph explore <module>` returns definition + instantiations + parameters.
- [x|✗] `codegraph query --kind module <pattern>` returns expected modules.
- [x|✗] 5 sampled `instantiates` edges resolve to correct target modules cross-file.
- [x|✗] At least one new predicate (`instantiates`) present in the graph.

## Notes / observed grammar gaps
- <construct>: errors on <n> files. Disposition: <harden in Phase 1.5 | accept and document | defer to Phase 6>.

## Sign-off
- Phase 2 GO / NO-GO: <…>
```

- [ ] **Step 5: Update the master plan tracker + commit**

```bash
# In analyzer_v2_codegraph_treesitter_plan.md § 9, replace the Phase 1 row's
# Status to `complete` and Notes to `branch=<fork>/feat/verilog-language-module @ <sha>`.

git add analyzer_v2_codegraph_treesitter_plan.md \
        runs/feasibility_v2_analyzer/phase1_acceptance.md \
        runs/feasibility_v2_analyzer/phase1_vortex_index.log  # may be gitignored; force-add if so
git commit -m "docs(analyzer-v2/phase-1): acceptance report; phase-2 GO"
```

---

## Acceptance for "Phase 1 is done"

All of the following must hold:

1. Fork `feat/verilog-language-module` branch is pushed to the project-owned remote and contains: `queries/verilog/entities.scm`, `queries/verilog/relations.scm`, (optionally) `queries/verilog/conditions.scm`, `src/languages/verilog.ts`, resolver hook, fixtures, and passing tests.
2. `npm test` inside the fork passes with the new Verilog test file enabled.
3. `runs/feasibility_v2_analyzer/phase1_acceptance.md` exists and all four acceptance checks are checked off; if any are `✗`, the Phase 2 GO line says `NO-GO` and a follow-on task is filed.
4. The fork's `package.json` records the resolved `tree-sitter-verilog` version; the version is repeated in the Phase 1 commit body for grep-ability.
5. `analyzer_v2_codegraph_treesitter_plan.md` § 9 Phase 1 row reads `complete | <date> | branch=…@<sha>`.
6. No file outside `tools/codegraph/`, `runs/feasibility_v2_analyzer/`, and `analyzer_v2_codegraph_treesitter_plan.md` was touched in this phase.
