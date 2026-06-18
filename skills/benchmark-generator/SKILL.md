---
name: benchmark-generator
description: Use when generating or repairing retrieval QA benchmark JSONL from an analyzer project context bundle, especially when cases need realistic queries, normalized query rewrites, evidence-grounded expected answers, and atomized answer rubrics.
argument-hint: "<project_context_bundle> + <generation_profile.yaml> -> <benchmark.jsonl>"
---

# Benchmark Generator

## Boundary

Use this skill after `benchmark-repo-analyzer` has produced a validated `project_context_bundle/`.

Do:
- read `project_manifest.json`, `source_inventory.jsonl`, `entity_index.jsonl`, and `relation_graph.jsonl`;
- use `generation_profile.yaml` or equivalent profile data to choose coverage goals, capability seeds, query style mix, and output size;
- generate benchmark JSONL rows plus benchmark-level metadata and a generation report;
- lint the output before delivery.

Do not:
- re-scan target repositories for basic source/entity/relation discovery;
- call CodeGraph directly for generation-time discovery;
- put analyzer internals, hidden construction notes, or evidence-derived conclusions into `query_rewrite`;
- write rubric-like `expected_answer` text such as `应说明...`.

## Required Inputs

```text
project_context_bundle/
generation_profile.yaml
```

Read `references/generator-contract.md` for the profile and output contract. Read `references/query-answer-rubric.md` before writing `query_rewrite`, `expected_answer`, or `answer_rubric`.

## Required Outputs

```text
benchmark.jsonl
benchmark_metadata.json
generation_report.md
```

## v1.1 generation mode

When the request names v1.1 or the profile contains `attribute_quotas`, use
attribute-first generation:

1. Read `signal_index.jsonl` from the configured context bundle.
2. Choose target difficulty attributes from quota deficits.
3. Select anchors whose signals satisfy the selected attributes.
4. Write `answerability` and `difficulty` into every row.
5. Run validator lint with `--schema-version v1.1`.
6. Write structural gate, adversarial dry-run, rejected rows, and generation report artifacts.

Do not overwrite v1 benchmark files. Use `_v1_1` or `_v1_1_smoke` output names.

## Codex CLI Invocation

Invoke this skill from Codex CLI as a message, not as a shell command:

```text
$benchmark-generator
Use runs/nvdla_context_bundle as the analyzer bundle.
Create or use runs/nvdla_generation_profile.yaml for a 50-case NVDLA benchmark.
Expand capability seeds from analyzer_report.md and relation_graph.jsonl.
Generate runs/nvdla_benchmark_v1.jsonl, runs/nvdla_benchmark_v1.metadata.json, and runs/nvdla_generation_report.md.
Make queries realistic and varied; keep query_rewrite free of hidden evidence-derived facts.
Run the generator lint before reporting completion.
```

```text
$benchmark-generator
Use runs/vortex_context_bundle as the analyzer bundle.
Create or use runs/vortex_generation_profile.yaml for a 50-case Vortex benchmark.
Cover documentation/code cross-checks, mechanism traces, build/simulation flows, tests/debug evidence, and negative or insufficient-evidence cases when supported by the bundle.
Generate runs/vortex_benchmark_v1.jsonl, metadata, and generation report.
Run the generator lint before reporting completion.
```

## Validation

Run:

```bash
python3 skills/benchmark-generator/scripts/lint_benchmark_jsonl.py \
  benchmark.jsonl \
  --repo-root . \
  --fail-on-warn
```

Fix all `FAIL` findings. Treat `WARN` findings as review queues unless the user explicitly accepts them.
