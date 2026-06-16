# Evaluation Logic v1

Keep retrieval, answer semantics, and citation formatting separate.

## Retrieval

References are broader retrieval targets. Evidence is the minimum answer proof.

```text
reference_recall@k = matched references / total references
evidence_recall@k = matched evidence spans / total evidence spans
```

A reference matches when a retrieved context has the same `source_id` or `path`.

An evidence span matches when a retrieved context has the same `source_id` or `path` and either:

- both have line ranges that overlap; or
- one side has no line range and the source/path matches.

## Citation

Citation checks only run when required by row policy:

- `citation_policy.required == "always"`;
- or `citation_policy.required == "when_query_requests_evidence"` and the query asks for evidence, code evidence, citations, line numbers, snippets, or proof.

Granularity:

```text
path_line   answer must include path:line or path:line-range for required evidence
path_only   answer must mention the evidence path
source_only answer must mention source id or path
```

## Answer Atom Scoring

`required_atoms` are scored separately from retrieval.

Recommended future semantic judge prompt should ask whether the answer semantically entails each atom, contradicts forbidden atoms, and cites required evidence.

The bundled script provides a deterministic lexical heuristic:

- code/path/symbol tokens must overlap strongly;
- Chinese text is compared with character bigrams;
- each required atom receives a matched/unmatched flag;
- weighted atom coverage is reported;
- fatal forbidden atom matches fail the answer heuristic.

This is useful for regression triage, not a replacement for semantic review.

## Optional LLM Judge

An LLM judge may replace or supplement the answer heuristic for answer semantics only.

The judge input should include:

- user `query`;
- `expected_answer`;
- predicted answer;
- gold `evidence`;
- predicted/retrieved evidence;
- `answer_rubric`.

The judge output must be one JSON object:

```json
{
  "score": 0.0,
  "verdict": "correct | partial | incorrect",
  "rationale": "short reason"
}
```

Do not use the judge to override deterministic retrieval or citation scores. Retrieval recall still comes from source/path/line overlap; citation pass still comes from citation policy.

DeepSeek should be called through an OpenAI-compatible chat completions request. API keys must be supplied through an environment variable such as `DEEPSEEK_API_KEY`, never stored in JSONL rows or reports.

## Token Efficiency

When prediction rows include `token_usage.total_token_usage`, the method evaluator reports:

```text
token_usage_coverage = rows with total_tokens / total rows
mean_total_tokens = average total_tokens over rows with token usage
sum_total_tokens = sum total_tokens over rows with token usage
```

Token efficiency is reported beside retrieval and answer quality, but it does not affect `retrieval_pass`, `answer_pass`, `citation_pass`, or `strict_e2e_pass`.

## Case Verdict

Default pass policy:

```text
retrieval_pass = evidence_recall@k == 1.0
answer_pass_heuristic = all conclusion atoms matched && weighted atom coverage >= threshold && no fatal forbidden match
citation_pass = citation not required or citation condition satisfied
case_pass_heuristic = retrieval_pass && answer_pass_heuristic && citation_pass
```

Use the sampled report to audit borderline cases.

When an LLM judge is configured, the method evaluator uses:

```text
answer_pass = llm_judge_score >= judge_threshold && llm_judge_verdict == correct
strict_e2e_pass = retrieval_pass && answer_pass && citation_pass
```
