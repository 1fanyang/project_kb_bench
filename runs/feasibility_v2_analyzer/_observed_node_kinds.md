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

Filled after Task 2 runs against `repo_sources/vortex`.

| project | total RTL files | parse_rate_pct | bucket | Phase 6 disposition |
|---|---|---|---|---|
| vortex  | _TBD_           | _TBD_          | _TBD_  | _TBD_ |
| nvdla   | _TBD_           | _TBD_          | _TBD_  | _TBD_ |
