# M9 — Adversarial Gate

**Stage 7 of the v1.1 modular generator.** Implements design §6.2.

Reads `drafts/<project>.candidates.jsonl`, `drafts/<project>.curated_evidence.jsonl`,
`drafts/<project>.queries.jsonl`, `drafts/<project>.answers.jsonl`. Writes
`drafts/<project>.baseline_tasks.jsonl` for the host LLM to answer, then
consumes `drafts/<project>.baseline_answers.jsonl` and writes
`drafts/<project>.adversarial_gate.jsonl` with per-row verdicts.

## Purpose

For every declared difficulty attribute on every row, run a **matched
cheap baseline** that *should* fail when the attribute is genuinely
present. If the matched baseline still succeeds, the attribute claim is
unconfirmed — the row is too easy for what it claims to test.

**Verdict rule (design §6.2):** a row passes iff for at least one of
its declared attributes, the matched baseline fails. Rows where every
baseline succeeds are demoted: either the difficulty tags are wrong
(re-tag) or the case is genuinely easy (drop).

## Why this is host-LLM-driven (not Python heuristics)

Each baseline is a deliberately-weakened answer-generation pass. The
weakening is structural — different prompts get different inputs. The
host LLM plays the role of each baseline by following the per-baseline
prompt and answering only from the restricted view. Python orchestrates
the dispatch and judges the result.

## Baselines and their inputs

| attribute | baseline | what the host LLM sees |
|---|---|---|
| `long_tail` | `closed_book_llm` | query only — no evidence |
| `distracting_info` | `top_1_dense_only` | query + the *first* candidate snippet only (a top-1 dense retriever would have stopped there) |
| `version_fork` | `single_source_set_retrieval` | query + evidence filtered to one source set |
| `non_code_anchor` | `code_only_retrieval` | query + evidence filtered to code/RTL (excludes script/config/build/doc) |
| `false_premise` | `closed_book_llm` + `oracle_evidence_llm` | both: closed-book; and full evidence but the LLM is told the user is confident |
| `doc_code_divergence` | `doc_only_retrieval` | query + evidence filtered to doc sources only |
| `conditional_behavior` | `top_1_dense_only` | query + first candidate snippet only |
| `negative_evidence` | `closed_book_llm` | query only — agent must refuse |
| `implicit_domain_knowledge` | `oracle_evidence_no_reasoning_llm` | full evidence, but the prompt forbids reasoning — quote only |
| `quantitative_aggregation` | `top_1_dense_only` | query + first candidate snippet only |

## Workflow

```
prepare_tasks (deterministic, Python)
        │
        ▼
drafts/<project>.baseline_tasks.jsonl       ──►  host LLM answers each task
                                                    │
                                                    ▼
                            drafts/<project>.baseline_answers.jsonl
                                                    │
                                                    ▼
judge_and_verdict (deterministic, Python)
                                                    │
                                                    ▼
drafts/<project>.adversarial_gate.jsonl
        │
        ▼
assemble (excludes rows that failed the gate)
```

Two deterministic Python entry points wrap the host-LLM call:

```bash
# Emit one task per (row × declared attribute)
python skills/benchmark-generator/scripts/adversarial_gate_v2.py prepare \
  --project nvdla --drafts-dir drafts

# After the host LLM writes drafts/<project>.baseline_answers.jsonl:
python skills/benchmark-generator/scripts/adversarial_gate_v2.py judge \
  --project nvdla --drafts-dir drafts
```

## Task file shape

```jsonc
{
  "task_id": "nvdla-v1_1-L1-031::long_tail::closed_book_llm",
  "case_id": "nvdla-v1_1-L1-031",
  "attribute": "long_tail",
  "baseline": "closed_book_llm",
  "view": {
    "query": "我感觉 NVDLA 跑 INT8 时是离线扫一遍数据集得到每层量化范围的，对吗？",
    "evidence": []
  },
  "instructions": "You have NO evidence. Answer the query from prior knowledge only. If you cannot answer reliably, return: {\"answer\": \"refuse\", \"reason\": \"no evidence available\"}."
}
```

The host LLM writes one answer per task:

```jsonc
{
  "task_id": "nvdla-v1_1-L1-031::long_tail::closed_book_llm",
  "case_id": "nvdla-v1_1-L1-031",
  "attribute": "long_tail",
  "baseline": "closed_book_llm",
  "answer": "refuse" | "<free text>",
  "answer_confidence": "low" | "medium" | "high",
  "rationale": "short justification (for audit)"
}
```

## Judging rule

For each (row × attribute × baseline) task, the deterministic
content-overlap heuristic produces one of three outcomes:

1. If `answer == "refuse"` or contains a refusal token → **baseline FAILED**
   (good — the difficulty claim is supported by the baseline's inability
   to answer).
2. Else if the answer contains ≥ 1 distinctive token from the M6
   `expected_answer` that is NOT already in the query → **baseline
   SUCCEEDED** (bad — the cheap baseline reached the same conclusion,
   so the row is too easy for what it claims).
3. Else (non-refusal answer with zero distinctive-token overlap) →
   **INCONCLUSIVE**. A host-LLM judge pass is the design-intended
   resolver. Until one runs, inconclusive outcomes do **not** count
   toward attribute confirmation, so a row with only inconclusive
   results will be demoted.

For `negative_evidence` the gold answer is itself a refusal, so the
overlap heuristic flips: refusal = baseline_failed (good), confident
answer = baseline_succeeded (bad). The judge handles this special case.

### Per-attribute confirmation rule

An attribute is *confirmed* iff every matched baseline (`ATTRIBUTE_BASELINES[attr]`)
returned `baseline_failed`. Multi-baseline attributes (e.g.
`false_premise` → `[closed_book_llm, oracle_evidence_llm]`) require
**both** baselines to fail per design §6.2.

### Row verdict

A row passes the gate iff at least one of its declared difficulty
attributes is confirmed under the rule above. Coverage gaps —
declared (attribute, baseline) pairs that the host LLM never answered
— produce a `untested_baselines:...` verdict and the row is demoted
until those tasks are answered.

## Verdict file shape

```jsonc
{
  "case_id": "nvdla-v1_1-L1-031",
  "passed": true,
  "per_attribute": [
    {
      "attribute": "long_tail",
      "baseline": "closed_book_llm",
      "outcome": "baseline_failed",
      "rationale": "Re-derived answer was refusal — closed-book LLM cannot answer without retrieval."
    },
    {
      "attribute": "implicit_domain_knowledge",
      "baseline": "oracle_evidence_no_reasoning_llm",
      "outcome": "baseline_failed",
      "rationale": "Quote-only answer did not surface the per-layer dynamic-range reasoning step."
    }
  ]
}
```

`outcome` values: `baseline_failed` (good), `baseline_succeeded` (bad),
`inconclusive` (needs jury), `skipped` (attribute not in mapping).

## Integration with assemble

```bash
python scripts/generate_v1_1_release_corpora.py --use-module-outputs drafts ...
```

When `<project>.adversarial_gate.jsonl` is present, the assembler drops
rows whose verdict has `passed: false`. Dropped rows are listed in the
generation report.
