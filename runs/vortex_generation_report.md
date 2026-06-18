# Vortex Benchmark v1 Generation Report

## Inputs

- Analyzer bundle: `runs/vortex_context_bundle`
- Generation profile: `runs/vortex_generation_profile.yaml`
- Generator skill: `benchmark-generator`

## Sampling Strategy

- Target count: 50 cases.
- Queries use realistic Chinese phrasing with English technical tokens where users would likely name files, APIs, flags, or modules.
- `query_rewrite` normalizes only the visible query semantics and does not add hidden evidence-derived facts.
- CodeGraph was unavailable in the analyzer bundle, so deep callgraph/dataflow candidates were rejected unless directly answerable from cited source spans.

## Coverage

### Layers
- `L1`: 15
- `L2`: 30
- `L3`: 5

### Capabilities
- `build_simulation_flow`: 6
- `cache_and_perf`: 5
- `doc_code_cross_check`: 6
- `mechanism_trace`: 3
- `negative_insufficient_evidence`: 3
- `repo_structure_location`: 2
- `rtl_hierarchy_trace`: 4
- `runtime_api_trace`: 9
- `software_test_path`: 4
- `tests_debug_evidence`: 8

### Answer Types
- `comparison`: 5
- `fact_check`: 9
- `location`: 2
- `mechanism`: 10
- `negative`: 3
- `procedure`: 6
- `synthesis`: 4
- `yes_no`: 11

## Capability Expansion

- `doc_code_cross_check`: expanded into README/docs versus runtime/script/test source consistency checks.
- `mechanism_trace`: expanded into runtime API forwarding, simulator start/wait, SIMT/pipeline, and cache/deadlock mechanisms.
- `build_simulation_flow`: expanded into configure/build, blackbox parameter mapping, Makefile generation, and perf/debug flows.
- `tests_debug_evidence`: expanded into OpenCL vecadd, hostless kernel vecadd, GDB/RBB debug, trace CSV comparison, and FPGA scope flows.
- `negative_insufficient_evidence`: expanded into sparse docs and doc/code mismatches where the bundle supports a bounded negative answer.
- `rtl_hierarchy_trace`: expanded into Vortex -> VX_cluster -> VX_socket -> VX_core and L1/L2/L3 cache RTL mapping.
- `runtime_api_trace`: expanded into stub dynamic loading, callbacks, simx/rtlsim/opae/xrt driver execution paths.
- `cache_and_perf`: expanded into cache hierarchy, MSHR/MREQ evidence, blackbox perf, and `vx_dump_perf` output.

## Rejected Candidate Classes

- Broad questions requiring current external Vortex release status or hardware availability outside the bundle.
- Precise callgraph/dataflow questions unsupported by analyzer relations because CodeGraph was not initialized.
- Questions that would require assuming undocumented OpenCL/runtime behavior instead of citing source spans.

## Outputs

- Benchmark JSONL: `runs/vortex_benchmark_v1.jsonl`
- Metadata: `runs/vortex_benchmark_v1.metadata.json`
- Lint JSON: `runs/vortex_benchmark_v1.lint.json`
- Report: `runs/vortex_generation_report.md`

## Lint Status

- Passed with `Rows: 50`, `FAIL: 0`, `WARN: 0` using `--fail-on-warn`.

## v1.1 Migration Audit

The v1 benchmark rows were stamped into a sidecar v1.1 candidate file and
audited with `--schema-version v1.1`. The original v1 JSONL file was not
modified. Rows that fail the structural gate are inputs for rewrite, relabel,
or archive decisions during v1.1 corpus construction.
