# Phase 1 smoke — Vortex re-index with verilog extractor enabled

## Index run

(Output captured ~2026-06-29 from `codegraph index /Users/.../repo_sources/vortex`)

Indexed 577 files (was 366 in Phase 0; +211 Verilog).
Totals: 8283 nodes, 16927 edges.

## Per-language file counts

cpp     228
verilog 211
c       122
python   13
yaml      2
php       1

## Verilog node-kind distribution

file       211
class      145   # module/package/class declarations
import     111   # include_directive + package_import_declaration sites
function    50   # top-level function/task
interface   23   # interface_declaration
method      16   # function/task declared inside a module

## Verilog edge-kind distribution (edges originating in verilog source)

instantiates 373   # module/checker/udp instantiation sites
contains     345   # structural file→entity / class→method

## Generic-resolver probes (D5 driver)

$ codegraph callers VX_pipe_register --json --limit 5
=> 5 real cross-file callers (VX_commit, VX_wctl_unit, VX_fcvt_unit,
   VX_fncp_unit, …), all from VX_pipe_register being instantiated from
   sibling modules. Generic resolver works.

$ codegraph node VX_cache
=> Full module body rendered with line numbers; module parameters and
   header preserved. No Verilog-specific resolution needed.

## D5 decision

DEFER Phase 1.5. The generic resolver returns plausible cross-file
callers/callees on Verilog modules without any Verilog-specific
sub-resolver. The `instantiates` references emitted by the new
`instantiationTypes` dispatch path resolve via name-matching to the
target module's `class` node.
