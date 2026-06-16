---
name: benchmark-validator
description: Use when auditing retrieval QA benchmark JSONL files or evaluating a knowledge-system run against benchmark cases, especially when references, evidence spans, expected answers, and atomized answer rubrics need separate validation.
argument-hint: "lint <benchmark.jsonl> | evaluate <benchmark.jsonl> <run_results.jsonl>"
---

# Benchmark Validator

## Boundary

Use this skill after `benchmark-generator` has produced benchmark JSONL.

Modes:

- `lint benchmark`: validate benchmark data quality before using it.
- `evaluate run`: score a knowledge-system retrieval/answer output against benchmark rows.

Do not:
- generate or repair benchmark cases unless the user asks;
- re-run repository analysis;
- treat lexical answer matching as definitive semantic judgment;
- use legacy v0.x fields as the v1 contract.

## Inputs

Lint mode:

```text
benchmark.jsonl
project_context_bundle/   # optional but strongly recommended
benchmark_metadata.json   # optional
```

Evaluate mode:

```text
benchmark.jsonl
run_results.jsonl
project_context_bundle/   # optional but strongly recommended
```

Read `references/validator-contract.md` for the interfaces and `references/evaluation-logic.md` for scoring semantics.

For method-level answer judging with an external model, use `scripts/evaluate_methods.py`. Keep retrieval and citation checks deterministic; use the LLM judge only for semantic answer correctness.

## Codex CLI Invocation

Invoke this skill from Codex CLI as a message, not as a shell command:

```text
$benchmark-validator
Lint runs/nvdla_benchmark_v1.jsonl using context bundle runs/nvdla_context_bundle.
Select 10 diverse sample cases for the report.
Write a markdown report to runs/nvdla_validation_report.md and a JSON report to runs/nvdla_validation_report.json.
Explain hard failures, warnings, retrieval/evidence relevance, expected-answer quality, and atom rubric quality.
```

```text
$benchmark-validator
Evaluate run results runs/nvdla_run_results.jsonl against runs/nvdla_benchmark_v1.jsonl using context bundle runs/nvdla_context_bundle.
Score reference recall, evidence recall, citation compliance, and answer atom coverage.
Write reports to runs/nvdla_run_evaluation.md and runs/nvdla_run_evaluation.json.
Flag lexical atom scores as heuristic unless a semantic judge is used.
```

## Script Commands

Lint benchmark data:

```bash
python3 skills/benchmark-validator/scripts/validate_benchmark.py lint \
  examples/chip-kb-v1/sample_benchmark.jsonl \
  --context-bundle examples/chip-kb-v1/project_context_bundle \
  --repo-root . \
  --sample-size 5 \
  --markdown-report validation_report.md
```

Evaluate a run:

```bash
python3 skills/benchmark-validator/scripts/validate_benchmark.py evaluate \
  examples/chip-kb-v1/sample_benchmark.jsonl \
  examples/chip-kb-v1/sample_run_results.jsonl \
  --context-bundle examples/chip-kb-v1/project_context_bundle \
  --repo-root . \
  --markdown-report run_evaluation_report.md
```

Evaluate method predictions with DeepSeek as an LLM judge:

```bash
export DEEPSEEK_API_KEY="..."

python3 scripts/evaluate_methods.py \
  examples/chip-kb-v1/sample_benchmark.jsonl \
  examples/chip-kb-v1/sample_run_results.jsonl \
  --top-k 10 \
  --llm-judge-provider deepseek \
  --llm-judge-model deepseek-v4-pro \
  --llm-judge-api-key-env DEEPSEEK_API_KEY \
  --output-json method_eval.deepseek.json \
  --output-md method_eval.deepseek.md
```

Use `--llm-judge-model deepseek-v4-flash` for lower-cost judging, `--llm-judge-thinking disabled` for non-thinking mode, and `--require-llm-judge` when missing or failed judge calls should fail CI. `--llm-judge-api-key-env` takes an environment variable name such as `DEEPSEEK_API_KEY`, not the key value itself. Never write API keys into benchmark rows, run result rows, reports, or skill files.

Fix all `FAIL` findings before relying on a benchmark. Treat answer atom scores from `validate_benchmark.py evaluate` as reproducible heuristics unless an external semantic judge is added.
