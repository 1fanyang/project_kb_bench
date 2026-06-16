# NVDLA Benchmark v1 Generation Report

## Inputs

- Analyzer bundle: `runs/nvdla_context_bundle`
- Generation profile: `runs/nvdla_generation_profile.yaml`
- Generator skill: `benchmark-generator`

## Sampling Strategy

- Target count: 50 cases.
- Queries mix Chinese natural phrasing with English technical tokens when users would likely name files, symbols, APIs, or registers.
- `query_rewrite` removes filler and normalizes the information need, but does not add answer facts or evidence-derived entities absent from the query.
- CodeGraph was unavailable in analyzer output, so deep call/dataflow questions were rejected unless directly supported by cited source spans.

## Coverage

### Layers
- `L1`: 19
- `L2`: 24
- `L3`: 7

### Capabilities
- `build_sim_verif_flow`: 3
- `doc_code_cross_check`: 6
- `mechanism_trace`: 18
- `repo_structure_location`: 1
- `rtl_symbol_location`: 2
- `software_stack_path`: 20

### Answer Types
- `comparison`: 3
- `fact_check`: 12
- `location`: 2
- `mechanism`: 13
- `procedure`: 5
- `synthesis`: 3
- `yes_no`: 12

## Capability Expansion

- `repo_structure_location`: expanded into hardware repo layout, build commands, and source file localization cases.
- `rtl_symbol_location`: expanded into top-level RTL and BDMA module localization with interface signal checks.
- `software_stack_path`: expanded into KMD scheduler, Linux GEM/DRM, UMD runtime API, Runtime.cpp load/submit, and test application flows.
- `doc_code_cross_check`: expanded into README/RST architecture and software documentation fact checks.
- `build_sim_verif_flow`: expanded into hardware build, C-model install target, compiler/runtime test app command flows.
- `mechanism_trace`: restricted to evidence-grounded local mechanisms such as BDMA zero-transfer, dependency update, event handling, ISR mapping, and DMA address paths.

## Rejected Candidate Classes

- Precise caller/callee trace questions that require CodeGraph or AST call edges unavailable in `runs/nvdla_context_bundle`.
- Broad performance tuning questions whose answer would require external interpretation beyond the cited NVDLA sources.
- Questions whose expected answer would be rubric-like instead of a direct evidence-grounded answer.

## Outputs

- Benchmark JSONL: `runs/nvdla_benchmark_v1.jsonl`
- Metadata: `runs/nvdla_benchmark_v1.metadata.json`
- Report: `runs/nvdla_generation_report.md`

## Lint Status

- Passed with `Rows: 50`, `FAIL: 0`, `WARN: 0` using `--fail-on-warn`. JSON report: `runs/nvdla_benchmark_v1.lint.json`.
