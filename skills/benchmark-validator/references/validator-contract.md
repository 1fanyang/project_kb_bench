# Validator Contract v1

The validator has two surfaces:

1. `lint benchmark`: validate the benchmark artifact itself.
2. `evaluate run`: validate a knowledge-system run against a benchmark.

## Lint Inputs

Required:

```text
benchmark.jsonl
```

Recommended:

```text
project_context_bundle/
benchmark_metadata.json
```

When `project_context_bundle/` is provided, the validator checks benchmark references and evidence against `source_inventory.jsonl`.

## Evaluate Inputs

Required:

```text
benchmark.jsonl
run_results.jsonl
```

Recommended:

```text
project_context_bundle/
```

`run_results.jsonl` has one row per case:

```json
{
  "case_id": "chip_demo-v1-L3-001",
  "retrieved_contexts": [
    {
      "rank": 1,
      "source_id": "src:demo_sw:bdma.c",
      "path": "examples/chip-kb-v1/sample_source/bdma.c",
      "lines": "4-10",
      "text": "..."
    }
  ],
  "answer": "不会 launch 硬件。..."
}
```

Aliases:

- `retrieved` may be used instead of `retrieved_contexts`.
- `contexts` may be used instead of `retrieved_contexts`.

## Lint Checks

Hard failures:

- invalid JSONL;
- duplicate or missing `case_id`;
- missing required v1 row fields;
- empty `references`, `evidence`, `expected_answer`, or `answer_rubric.required_atoms`;
- duplicate `evidence_id`;
- rubric atoms that reference unknown evidence ids;
- missing conclusion atom;
- evidence line ranges outside known source line counts when context bundle is available;
- citation-required query with no citation in `expected_answer`;
- rubric-like `expected_answer`.

Warnings:

- reference/evidence path missing on local disk;
- reference path not present in source inventory;
- query rewrite duplicates a chatty query;
- query rewrite introduces technical tokens absent from query;
- non-standard answer type, atom role, or match type;
- short expected answer;
- weak coverage distribution.

## Report Shape

Markdown reports should include:

```text
Verdict
Summary counts
Coverage by project/layer/capability/answer_type
Findings
Sampled cases with query, references, evidence, and snippets
Next actions
```

Sampling should prefer cases with findings, then diversify by project/layer/capability.

## Evaluate Output

The evaluator reports:

- `reference_recall_at_k`;
- `evidence_recall_at_k`;
- `citation_pass`;
- `atom_coverage_heuristic`;
- `fatal_forbidden_heuristic`;
- optional `llm_judge_score`, `llm_judge_verdict`, and `llm_judge_rationale` when a semantic judge is configured;
- per-case pass/warn/fail verdict;
- sampled reasoning evidence for manual review.

Answer atom scoring is heuristic unless connected to a semantic judge. Retrieval and citation checks are deterministic.

## LLM Judge Configuration

Provider-backed semantic judging is optional and belongs to evaluation, not benchmark linting.

DeepSeek-compatible invocation:

```bash
export DEEPSEEK_API_KEY="..."

python3 scripts/evaluate_methods.py benchmark.jsonl predictions.jsonl \
  --llm-judge-provider deepseek \
  --llm-judge-model deepseek-v4-pro \
  --llm-judge-api-key-env DEEPSEEK_API_KEY \
  --output-json evaluation.json \
  --output-md evaluation.md
```

The judge receives `case_id`, `query`, `expected_answer`, prediction answer, gold evidence, predicted evidence, and `answer_rubric`. `--llm-judge-api-key-env` must be the name of an environment variable, not the API key value. Reports must include provider/model metadata but must not include API keys.
