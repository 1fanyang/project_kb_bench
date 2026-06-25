# M8 — Self-Verifier

**Stage 6 of the v1.1 modular generator.** Reads
`drafts/<project>.candidates.jsonl` (for `row_plan`),
`drafts/<project>.curated_evidence.jsonl` (M2),
`drafts/<project>.queries.jsonl` (M5),
`drafts/<project>.answers.jsonl` (M6). Writes
`drafts/<project>.verifier.jsonl`.

Optional but strongly recommended before adversarial gating. This is the
cross-LLM-IAA proxy the v1.1 design names in §3.

## Purpose

A different LLM run re-derives the expected_answer using only the M2
curated evidence and the M5 query. The validator then compares the
re-derived answer to the M6 expected_answer and flags any of these
quality leaks:

- Anchor / refusal cue leaks the M5 spec missed.
- Re-derived answer materially disagrees with the M6 answer — the M6
  answer may be over-claiming or the evidence may not support it.
- Re-derived answer wanders into facts the evidence does not support —
  the row is unstable.
- For unanswerable rows: re-derived answer fails to refuse, meaning the
  query is not actually unanswerable from the published evidence.

## Why this is a host-LLM step

Self-IAA needs an LLM that reads the row "cold" — no privileged access
to the gold answer. Rules can't do this; they would either re-quote the
evidence (trivially agree) or do nothing (provide no signal).

The cheap two-judge proxy is to run M8 under a different model family
than M2/M3/M5/M6 (e.g. M2-6 on DeepSeek, M8 on Claude). When the same
model runs both, M8 still catches anchor leak / refusal leak / evidence-
not-supporting-claim that the same model authored, because the prompt
is structurally different: M8 has no access to the M6 answer.

## Inputs the host LLM receives per row

- `row_plan` from candidates.jsonl
- `query` from queries.jsonl
- `selected_evidence` from curated_evidence.jsonl (statement + path + lines)

The host LLM **must NOT see**:

- The M6 expected_answer
- The M3 claims
- The M7 rubric

The orchestrator writes `drafts/<project>.verifier_inputs.jsonl` that
excludes those fields and presents only what an oracle-evidence-LLM
baseline would see. The host LLM produces
`drafts/<project>.verifier.jsonl` with the re-derived answer.

## Output shape

```jsonc
{
  "case_id": "nvdla-v1_1-L1-001",
  "rederived_answer": "无法判断。当前快照里没有给出 runtime API 返回码的可核验定义；需要补充对应实现或文档后才能回答。",
  "rederived_citations": [],
  "rederivation_confidence": "low | medium | high",
  "rederivation_notes": "Evidence is empty for this case; cannot answer concretely."
}
```

`rederivation_confidence` is the host LLM's self-report of how solidly
the evidence supports the re-derived answer. The validator surfaces
mismatches between confidence and the row's answerability (e.g.,
`high` confidence on an `unanswerable_missing_evidence` row is a leak).

## How to compose the re-derived answer

1. Look at the row's query and the curated evidence only.
2. If the evidence is empty: answer "无法判断" (or "Cannot confirm" for
   English-anchored rows). `rederivation_confidence: low`.
3. Otherwise: write the answer as you would for a real user, citing
   the evidence path:lines that materially backs each claim.
4. Do not invent symbols, file paths, or numerical values that are not
   in the evidence statements.

## Validation

```bash
python skills/benchmark-generator/scripts/validate_module_outputs.py \
  --module M8 \
  --candidates drafts/<project>.candidates.jsonl \
  --curated drafts/<project>.curated_evidence.jsonl \
  --answers drafts/<project>.answers.jsonl \
  drafts/<project>.verifier.jsonl
```

FAIL on:
- Re-derived answer refuses (`无法判断` / `Cannot`) but row is `answerable`.
- Re-derived answer is confident but row is `unanswerable_missing_evidence`
  (the gap is real; if the agent can answer from evidence alone, the row
  is mislabeled).
- Re-derivation cites a `path:lines` not in M2 curated_evidence (the
  agent fabricated a citation).
- Re-derived answer is empty.
- `rederivation_confidence` invalid value.

WARN on:
- Re-derived answer length differs from M6 answer by > 2× (often a sign
  of over-claiming or under-claiming).
- Re-derived citation set is disjoint from M6 citation_paths.
- `rederivation_confidence: high` paired with an `unanswerable_*` row.
- M6 answer mentions a token not present in re-derived answer or evidence
  statements (heuristic for content the M6 drafter inferred without
  explicit support).
