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
  "answer": "不会 launch 硬件。...",
  "token_usage": {
    "source": "codex_exec_json",
    "events_seen": 1,
    "total_token_usage": {
      "input_tokens": 31710,
      "cached_input_tokens": 23424,
      "output_tokens": 233,
      "reasoning_output_tokens": 101,
      "total_tokens": 31943
    },
    "last_token_usage": {"total_tokens": 31943}
  }
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

## v1.1 Validation Mode

Use `--schema-version v1.1` to enable v1.1 checks. The default remains `v1`
so existing benchmarks continue to lint unchanged.

Structural gate reports are written with:

```bash
python3 skills/benchmark-validator/scripts/validate_benchmark.py lint benchmark.jsonl \
  --schema-version v1.1 \
  --structural-gate-json benchmark.structural_gate.json
```

Adversarial dry-run reports are written with:

```bash
python3 skills/benchmark-validator/scripts/adversarial_gate.py benchmark.jsonl \
  --dry-run \
  --output-jsonl benchmark.adversarial_gate.jsonl
```

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
- optional `token_usage_coverage`, `mean_total_tokens`, and `sum_total_tokens` when run rows include token accounting;
- per-case pass/warn/fail verdict;
- sampled reasoning evidence for manual review.

Answer atom scoring is heuristic unless connected to a semantic judge. Retrieval and citation checks are deterministic.
Token usage is cost/efficiency metadata; it must not change retrieval, citation, or answer correctness scores.

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
