# tree-sitter-verilog observed node kinds

Captured during Phase 0 Task 1 smoke. tree-sitter-verilog version: 1.0.3.

## Root + container kinds

| concept                | observed node kind          | notes |
|---|---|---|
| translation unit       | `source_file`               | root of every parse |
| module                 | `module_declaration`        | with `module_header` and `module_ansi_header` children |
| parameter              | `parameter_declaration`     | inside the header or body |
| always block           | `always_construct`          | **not** `always_block` (which is the SystemVerilog *keyword* name); the AST kind is `always_construct` for `always`, `always_ff`, `always_comb`, `always_latch` alike |

## Control-flow kinds (used by `conditional_behavior` in Phase 3)

| concept                | observed node kind          | notes |
|---|---|---|
| if statement           | `conditional_statement`     | **not** `if_statement`. Update Phase 1 conditions.scm and Phase 3 emitter accordingly. |
| case statement         | `case_statement`            | as documented in the plan |
| always (catch-all)     | `always_construct`          | as above |

## Instantiation kinds (used by `instantiates` predicate in Phase 1)

tree-sitter-verilog cannot disambiguate `child u_child (.clk(clk));` between a
module instance and a SystemVerilog checker/UDP instance purely syntactically.
Empirically:

| fixture syntax                                  | observed instantiation kind | notes |
|---|---|---|
| `child #(.W(8)) u (.clk(clk));`                 | `module_instantiation`      | parametric override forces the right disambiguation |
| `child u (clk, reset);` (positional ports)      | `udp_instantiation`         | grammar prefers UDP for positional |
| `child u (.clk(clk));` (no params, named ports) | `checker_instantiation`     | grammar prefers checker |
| `(* keep = "true" *) child u (.clk(clk));`      | `checker_instantiation`     | same as above with attribute |

**Implication for Phase 1:** `queries/verilog/relations.scm`'s
`instantiates` predicate must match **all three** of
`module_instantiation`, `checker_instantiation`, `udp_instantiation`. The
resolver then disambiguates by checking whether the target identifier
resolves to a `module_declaration`, `checker_declaration`, or
`udp_declaration`. Phase 0 cannot fix this in the grammar; the dispatch
must live in the resolver.

## Kinds not yet observed (need fuller fixtures or real RTL)

- `text_macro_definition` — Phase 0 Task 2 will reveal whether this is the
  actual ``define` node name when parsing real Vortex source.
- `package_import_declaration`
- `include_directive`
- `function_declaration`, `task_declaration`, `interface_declaration`,
  `package_declaration`, `class_declaration`

These weren't in the smoke fixture; record presence/counts in the Task 2
real-data sweep summary.

## Parse-rate bucket

| project | total RTL files | clean_pct (strict) | usable_pct (clean+partial, excl. foundry models) | bucket | Phase 6 disposition |
|---|---|---|---|---|---|
| vortex  | 215 (201 non-foundry) | 26.05% | 95.5% | borderline-needed | recommended |
| nvdla   | 427 (321 non-generated) | 26.0% | 100.0% | safe-skip | optional |

NVDLA's "non-generated" exclusion drops 106 files under
`hw/vmod/rams/synth/` (RAM macro models) and `hw/vmod/vlibs/`
(DesignWare leaf cells). Both groups are auto-generated standard-cell
libraries with deep nesting that hits Python's recursion limit when
walked recursively (Task 2 was patched to use an iterative stack).

On the 321 hand-written NVDLA files, tree-sitter-verilog has zero hard
errors — Phase 6 (Verible secondary parser) is genuinely optional for
NVDLA, and only a "nice to have" for the 9 Vortex hard-error files.

**Reading these numbers:** The "clean_pct" column applies the strict
zero-ERROR-nodes definition the original plan used. The "usable_pct"
column counts files where the tree-sitter parse tree is still walkable
for entity extraction (clean OR partial = ≤5% ERROR nodes), excluding
the 14 Synopsys foundry memory-cell models that no analyzer should ever
have to read (`vortex/hw/syn/synopsys/models/`).

For analyzer-v2 purposes, **usable_pct is the load-bearing number**:
Phase 1's tree-sitter queries walk whatever AST tree-sitter gives back,
and a sub-tree ERROR doesn't invalidate the surrounding module's entity
extraction. At 95.5% usable, Phase 6 (Verible secondary parser) is
**recommended but not blocking** — there are 9 hard-error files (4.5%)
that need Verible to be reachable at all:

- `vortex/hw/dpi/float_dpi.vh` (171 errors) — DPI-C function imports
- `vortex/hw/dpi/util_dpi.vh` (25 errors) — DPI-C function imports
- `vortex/hw/rtl/VX_trace_pkg.sv` (459 errors) — likely heavy parameter/typedef constructs
- `vortex/hw/rtl/afu/xrt/VX_afu_wrap.sv` (282 errors)
- `vortex/hw/rtl/afu/xrt/vortex_afu.v` (64 errors)
- `vortex/hw/rtl/core/VX_uop_sequencer.sv` (33 errors)
- `vortex/hw/rtl/interfaces/VX_decode_if.sv` (10 errors)
- `vortex/hw/rtl/interfaces/VX_fetch_if.sv` (10 errors)
- `vortex/sim/xrtsim/vortex_afu_shim.sv` (62 errors)

This is exactly the 80–95% bucket from the original plan's decision
table (interpreted via `usable_pct`), so Phase 6 is in scope unless we
discover at Phase 1 that the 9 hard-error files are non-load-bearing
for the benchmark.
