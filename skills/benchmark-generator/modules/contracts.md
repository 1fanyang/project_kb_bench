# Module contracts (Ships 2-4)

Seven host-LLM stages (M2/M3/M5/M6/M7/M8/M9) run between the deterministic
`prepare_module_inputs.py` and the deterministic
`generate_v1_1_release_corpora.py` assembler. Each stage consumes a JSONL
file produced by an earlier stage and writes a JSONL file consumed by a
later one. One JSONL line per `case_id`. M2-M3 are serial; M5 and M6→M7
run in parallel after M3; M8 and M9 are quality gates that run after the
authoring stages and may also run in parallel.

```
prepare_module_inputs.py
  └─► drafts/<project>.candidates.jsonl
        │  (row_plan, anchor, candidates, graph-walk neighbors,
        │   negative_evidence axis on missing-evidence rows)
        ▼
M2 evidence curator  (host LLM)
  └─► drafts/<project>.curated_evidence.jsonl
        │
        ▼
M3 claim extractor  (host LLM)
  └─► drafts/<project>.claims.jsonl
        │
        ├─► M5 question author     ──► drafts/<project>.queries.jsonl
        │
        └─► M6 answer drafter      ──► drafts/<project>.answers.jsonl
                │
                ▼  M7 rubric atomizer  ──► drafts/<project>.rubrics.jsonl

  (Stages 6-7 — quality gates)
M8 self-verifier         ──► drafts/<project>.verifier.jsonl
M9a adversarial gate prep ──► drafts/<project>.baseline_tasks.jsonl
M9b adversarial gate judge ──► drafts/<project>.adversarial_gate.jsonl
                                (host LLM writes drafts/<project>.baseline_answers.jsonl in between)

  (Stage 8 — assemble)
generate_v1_1_release_corpora.py --use-module-outputs drafts/
  └─► runs/<project>_benchmark_v1_1.jsonl
       + runs/<project>_benchmark_v1_1.metadata.json (target/actual/gap, drop_log)
       + runs/<project>_generation_report_v1_1.md
```

## Validator commands (cheat sheet)

Run after each stage; non-zero exit on any FAIL finding.

```bash
# After M2
python skills/benchmark-generator/scripts/validate_module_outputs.py \
  --module M2 --candidates drafts/<p>.candidates.jsonl \
  drafts/<p>.curated_evidence.jsonl

# After M3
python skills/benchmark-generator/scripts/validate_module_outputs.py \
  --module M3 --candidates drafts/<p>.candidates.jsonl \
  --curated drafts/<p>.curated_evidence.jsonl \
  drafts/<p>.claims.jsonl

# After M5
python skills/benchmark-generator/scripts/validate_module_outputs.py \
  --module M5 --candidates drafts/<p>.candidates.jsonl \
  --curated drafts/<p>.curated_evidence.jsonl \
  drafts/<p>.queries.jsonl

# After M6
python skills/benchmark-generator/scripts/validate_module_outputs.py \
  --module M6 --candidates drafts/<p>.candidates.jsonl \
  --curated drafts/<p>.curated_evidence.jsonl \
  --claims drafts/<p>.claims.jsonl \
  drafts/<p>.answers.jsonl

# After M7
python skills/benchmark-generator/scripts/validate_module_outputs.py \
  --module M7 --candidates drafts/<p>.candidates.jsonl \
  --curated drafts/<p>.curated_evidence.jsonl \
  --claims drafts/<p>.claims.jsonl \
  --answers drafts/<p>.answers.jsonl \
  drafts/<p>.rubrics.jsonl

# After M8
python skills/benchmark-generator/scripts/validate_module_outputs.py \
  --module M8 --candidates drafts/<p>.candidates.jsonl \
  --curated drafts/<p>.curated_evidence.jsonl \
  --answers drafts/<p>.answers.jsonl \
  drafts/<p>.verifier.jsonl

# M9 — prepare tasks, host LLM answers, then judge
python skills/benchmark-generator/scripts/adversarial_gate_v2.py prepare \
  --project <p> --drafts-dir drafts
# (host LLM produces drafts/<p>.baseline_answers.jsonl)
python skills/benchmark-generator/scripts/adversarial_gate_v2.py judge \
  --project <p> --drafts-dir drafts
```

## Resilience notes

- M2-M7 outputs may be omitted; the assembler falls back to the
  deterministic template path for any missing per-stage file.
- M9's `adversarial_gate.jsonl` is consumed by the assembler — rows with
  `passed: false` are dropped. Use `--enforce-target-count` in release
  builds to make silent under-target shrinkage non-silent.
- The metadata JSON and generation report always carry
  `target_count` / `actual_count` / `count_gap` and the drop log.

---

## Stage 0 — candidates (produced by `prepare_module_inputs.py`)

Path: `drafts/<project>.candidates.jsonl`. One line per row the generator
would emit, in generation order.

```jsonc
{
  "case_id": "nvdla-v1_1-L1-001",
  "project": "nvdla",
  "row_plan": {
    "layer": "L1",
    "answerability": "answerable",
    "axis2_retrieval": ["long_tail"],
    "axis3_reasoning": ["implicit_domain_knowledge"],
    "capability": {"code": "mechanism_trace", "zh": "机制链路解释"},
    "answer_type": {"code": "mechanism", "zh": "机制解释"}
  },
  "anchor": {
    "source_id": "src:nvdla_sw:engine.c",
    "path": "repo_sources/nvdla/sw/kmd/firmware/engine.c",
    "lines": "172-180",
    "raw_snippet": "<verbatim text from those lines>"
  },
  "candidates": [
    {
      "candidate_id": "C1",
      "source_id": "src:nvdla_sw:engine.c",
      "path": "repo_sources/nvdla/sw/kmd/firmware/engine.c",
      "lines": "172-180",
      "raw_snippet": "<verbatim text>",
      "attribute": "long_tail",
      "axis": 2,
      "role_hint": "evidence_fact"
    },
    {
      "candidate_id": "C2",
      "source_id": "src:nvdla_doc:bdma.rst",
      "path": "repo_sources/nvdla/doc/doc/hw/bdma.rst",
      "lines": "1-3",
      "raw_snippet": "BDMA / ====",
      "attribute": "implicit_domain_knowledge",
      "axis": 3,
      "role_hint": "evidence_fact"
    }
  ]
}
```

Notes:
- `raw_snippet` is the text the analyzer extracted verbatim. Whitespace is
  preserved.
- `candidates` always contains every signal that contributed to this row's
  difficulty claim, plus up to 3 graph-walk neighbors per anchor (for L2/L3).
- For `unanswerable_missing_evidence` rows, `candidates` is empty and the
  downstream M2/M3 stages skip the row (emit only `case_id`).

---

## Stage 1 — M2 Evidence Curator (host LLM produces)

Path: `drafts/<project>.curated_evidence.jsonl`. One line per candidate row.

```jsonc
{
  "case_id": "nvdla-v1_1-L1-001",
  "selected_evidence": [
    {
      "evidence_id": "E1",
      "source_id": "src:nvdla_sw:engine.c",
      "path": "repo_sources/nvdla/sw/kmd/firmware/engine.c",
      "lines": "172-180",
      "role": "evidence_fact",
      "statement": "engine_dispatch returns -EINVAL when the request descriptor pointer is null, gating subsequent register writes."
    }
  ],
  "rejected_candidates": [
    {"candidate_id": "C2", "reason": "rst_heading_only"}
  ]
}
```

Rules the host LLM must follow when producing this stage:
- `selected_evidence` is the minimum set of spans that supports an answer to
  the row's `row_plan`. L1: 1 span. L2: ≥2 distinct `source_id` values. L3:
  ≥2 distinct `source_id` values, plus at least one that builds on another
  in the chain.
- Each `statement` is a single declarative sentence that names what the span
  *shows*. It must not be a verbatim quote of `raw_snippet`. It must be
  English or Chinese, matching the project's documentation language.
- Reject a candidate (move it to `rejected_candidates`) when its
  `raw_snippet` is license boilerplate, RST heading underline, Sphinx config
  preamble, a CI YAML workflow header alone, an `ASSERT_RESET` macro fence,
  or otherwise carries no behavioral content. Use one of these `reason`
  codes:
  - `license_header`
  - `copyright_continuation`
  - `rst_heading_only`
  - `sphinx_config_boilerplate`
  - `ci_workflow_header`
  - `assertion_macro_fence`
  - `blank_or_separator`
  - `other_boilerplate`
- For `unanswerable_missing_evidence` rows the line is
  `{"case_id": "...", "selected_evidence": [], "rejected_candidates": []}`.

---

## Stage 2 — M3 Behavioral Claim Extractor (host LLM produces)

Path: `drafts/<project>.claims.jsonl`. One line per row.

```jsonc
{
  "case_id": "nvdla-v1_1-L1-001",
  "claims": [
    {
      "id": "C1",
      "text": "engine_dispatch returns -EINVAL when the request descriptor pointer is null.",
      "evidence_ids": ["E1"],
      "kind": "behavior"
    }
  ]
}
```

`kind` values:
- `behavior` — a procedure step or function-level behavior.
- `state` — a register / variable / data-structure state assertion.
- `invariant` — a constraint that must always hold.
- `negative` — explicit absence of a behavior (e.g., for
  `unanswerable_missing_evidence` rows).
- `comparison` — a fact specifically about how two artifacts compare
  (for `doc_code_divergence` / L2 cross-source).

Rules:
- Every claim's `evidence_ids` must reference at least one `evidence_id`
  emitted by M2 for the same case_id.
- Claim `text` must be a complete declarative sentence. It must not be a
  verbatim substring of any evidence `statement` from M2.
- Number of claims: usually 1–3. L3 rows typically have 2–3 claims tied
  together by the chain.
- For `unanswerable_missing_evidence` rows: one claim of `kind: "negative"`
  with text like "Current corpus does not contain a span that confirms or
  refutes <topic>." Evidence_ids is `[]`.

---

## Stage 3 — M6 Answer Drafter (host LLM produces)

Path: `drafts/<project>.answers.jsonl`. One line per row.

```jsonc
{
  "case_id": "nvdla-v1_1-L1-001",
  "expected_answer": "engine_dispatch returns -EINVAL when the request descriptor pointer is null, preventing subsequent register writes (引用：`repo_sources/nvdla/sw/kmd/firmware/engine.c:172-180`).",
  "citation_paths": [
    "repo_sources/nvdla/sw/kmd/firmware/engine.c:172-180"
  ]
}
```

Rules:
- First sentence directly answers the row's target unknown. For yes/no
  rows the first sentence begins with `会` / `不会` / `无法判断` (or English
  equivalent for English-anchored docs).
- The body interprets the claim — it does not paste evidence text verbatim.
- If the row's `answer_type` is `yes_no` / `fact_check` / `false_premise`,
  the answer must explicitly affirm or reject the premise.
- Every `citation_paths` entry must match a `path:lines` from the row's
  M2 `selected_evidence`. The expected_answer text must contain those
  citations in backtick form.
- Do not emit rubric-style language (`应说明…`, `答案需要…`, etc.).
- For `unanswerable_missing_evidence` rows: the first sentence is
  `无法判断` (or `Cannot confirm` if the doc is English); the body names
  the gap. `citation_paths` is `[]`.

---

## Validator behavior

`validate_module_outputs.py` enforces:
- JSONL shape and required fields for the requested `--module`.
- evidence_ids on M3 claims actually resolve to M2 evidence_ids in the
  matching curated_evidence.jsonl (when both files are passed).
- citation_paths on M6 answers actually resolve to M2 selected_evidence
  path:lines.
- M6 expected_answer contains each citation_path in backtick form.
- M6 first-sentence direct-answer rule for yes_no rows.
- M2 boilerplate-rejection sanity: rejected_candidates whose `reason` is
  `other_boilerplate` get a warning (over-use of the escape hatch).

The validator returns 0 on pass, 1 on FAIL findings. Pass `--fail-on-warn`
to also fail on warnings. The validator is deterministic and can be run
in CI.
