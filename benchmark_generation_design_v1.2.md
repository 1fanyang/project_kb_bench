# Benchmark Generation Design v1.2

Status: draft for review
Reads from: `benchmark_generation_design_v1.0.md` and `benchmark_generation_design_v1.1.md`
Companion notes: `generation_corpora_v1_1_pipeline.md`, `skills/benchmark-generator/modules/contracts.md`

This document defines the semantic version after v1.1. The important
distinction is:

- **v1.1** is the rule-first generator: analyzer signals are sampled
  deterministically, rows are assembled by templates, and validation is mostly
  structural.
- **v1.2** is the module-first generator: deterministic candidate preparation
  is followed by host-LLM production and host-LLM judgment modules, with
  deterministic validators between modules and final release filtering.

Several implementation files still contain `v1_1` in their names because they
were introduced as the v1.1 release-corpus path. In this document, the modular
M2-M9 path is treated as the v1.2 semantic pipeline. The old deterministic
path remains v1.1.

---

## 1. Motivation

### 1.1 What v1.1 fixed

v1.1 added the right control surface:

1. Difficulty attributes are explicit rather than inferred from row labels.
2. Answerability is first-class, including missing, false-premise, and
   ambiguous cases.
3. The generator consumes `signal_index.jsonl`, so cases can be sampled from
   analyzer evidence instead of from broad graph patterns.
4. Structural gates can reject rows whose evidence shape does not match the
   declared difficulty claim.

Those remain the contract floor for v1.2.

### 1.2 What v1.1 still cannot do well

The v1.1 path is deliberately mechanical. That made it reproducible, but the
generated benchmark exposed four quality ceilings:

1. **Evidence quality depends on analyzer noise.** Regex fallback can mark
   license headers, include guards, CI workflow triggers, and doc headings as
   behavioral signals. A deterministic sampler cannot reliably know whether a
   span is substantive.
2. **Questions become templated.** Rule-authored queries tend to leak file
   names, use awkward phrasing, or ask for "the target file" rather than a
   natural task.
3. **Answers lack fact density.** Template answers can cite a span without
   explaining the behavior that makes the span relevant.
4. **Rubrics are too coarse.** Whole-answer rubric atoms do not give enough
   resolution to judge partial correctness or forbidden hallucinations.

v1.2 moves those semantic choices into bounded host-LLM modules while keeping
deterministic validation around every module boundary.

### 1.3 Mapping v1.1 limitations to v1.2 responses

| v1.1 limitation | v1.2 response | Module |
|---|---|---|
| Boilerplate spans survive candidate sampling. | Curate evidence, reject non-substantive spans, and write interpretive evidence statements. | M2 |
| Template queries are unnatural or leak target paths. | Author realistic user queries with explicit no-path/no-basename rules. | M5 |
| Answers cite evidence but do not synthesize enough facts. | Draft evidence-grounded expected answers from extracted claims. | M6 |
| Rubric atoms are broad and hard to score. | Atomize answers into small required and forbidden propositions. | M7 |
| The answer may not be recoverable from evidence. | Re-derive the answer blind from query + curated evidence. | M8 |
| Difficulty attributes are asserted but not stress-tested. | Run matched weak baselines and judge whether they fail as expected. | M9 |
| Release counts can silently shrink after filtering. | Select only validator-clean rows; repeat complete attempts up to two times if a project is under target. | Release gate |

---

## 2. Goals and non-goals

**Goals.**

1. Preserve the v1.1 difficulty and answerability schema.
2. Replace template authoring with host-LLM modules for evidence selection,
   query writing, answer drafting, rubric atomization, self-verification, and
   adversarial judgment.
3. Make module failures visible early through per-stage deterministic
   validators.
4. Release exactly 100 validator-clean rows per project for the v1.2 NVDLA and
   Vortex benchmark, if the available analyzer bundle can support them.
5. Keep every final row evidence-grounded and runnable by the existing
   benchmark-validator lint path.

**Non-goals for v1.2.**

- Replacing the analyzer backend. Regex fallback limitations are documented
  and partially masked, but not solved here.
- Renaming every implementation file from `v1_1` to `v1_2`. Version-stamped
  release artifacts should use v1.2 names, while compatibility scripts may
  retain their historical names.
- Running baseline performance evaluation as part of generation. v1.2 uses
  M9 adversarial generation gates, not full downstream retrieval benchmark
  scoring.
- Treating old root `drafts/` smoke files as release inputs. They are partial
  development artifacts and must be ignored.

---

## 3. Definitions

| Term | Definition |
|---|---|
| **Host LLM** | The Codex/Claude/Gemini host running the skill. The host reads a module prompt and writes the corresponding JSONL output. |
| **Module** | A bounded generation or judgment stage with a prompt, JSONL contract, and validator. v1.2 uses M2, M3, M5, M6, M7, M8, and M9. |
| **Candidate row** | A deterministic Stage 0 record containing `row_plan`, one anchor, and zero-or-more candidate evidence spans. |
| **Anchor** | The primary signal-derived source span chosen by Stage 0 as the row's starting point. |
| **Candidate evidence** | Stage 0 spans available to M2. They include the anchor and graph-walk or signal companions needed for L2/L3 and difficulty attributes. |
| **Release row** | A final benchmark row that passed module validation, assembly, generator lint, and benchmark-validator lint. |
| **Module validator** | `validate_module_outputs.py`, run after M2, M3, M5, M6, M7, and M8. |
| **Adversarial gate** | M9. It prepares weak-baseline tasks, consumes host-LLM baseline answers, then judges whether declared difficulty attributes are supported. |

---

## 4. Pipeline overview

v1.2 keeps deterministic preparation and deterministic validation, but all
semantic authoring happens inside modules.

```text
project_context_bundle/
  └─ signal_index.jsonl + source_inventory/entity_index/relation_graph
        │
        ▼
Stage 0 prepare (deterministic)
  └─ drafts/v1_2_attempt_<n>/<project>.candidates.jsonl
        │
        ▼
M2 evidence curator (host LLM)
  └─ <project>.curated_evidence.jsonl
        │
        ▼
M3 claim extractor (host LLM)
  └─ <project>.claims.jsonl
        │
        ├─► M5 question author (host LLM)
        │     └─ <project>.queries.jsonl
        │
        └─► M6 answer drafter (host LLM)
              └─ <project>.answers.jsonl
                    │
                    ▼
              M7 rubric atomizer (host LLM)
                └─ <project>.rubrics.jsonl

M8 self-verifier (host LLM, blind to M6/M7)
  └─ <project>.verifier.jsonl

M9 adversarial gate
  ├─ prepare tasks deterministically
  ├─ host LLM writes weak-baseline answers
  └─ judge deterministically
        │
        ▼
assemble with module outputs
        │
        ▼
generator lint + benchmark-validator lint
        │
        ▼
runs/v1_2/<project>_benchmark_v1_2.jsonl
```

M5 can run in parallel with the M6 -> M7 chain after M3. M8 and M9 can run in
parallel after authoring, because both consume completed module outputs and do
not depend on each other.

---

## 5. Stage details

### 5.1 Stage 0 prepare

Implementation: `skills/benchmark-generator/scripts/prepare_module_inputs.py`.

Inputs:

- `runs/<project>_context_bundle/project_manifest.json`
- `source_inventory.jsonl`
- `signal_index.jsonl`
- `entity_index.jsonl`
- `relation_graph.jsonl`

Responsibilities:

1. Build a planned row list from the project profile and signal index.
2. Choose one deterministic anchor per row from eligible analyzer signals.
3. Add candidate companions from graph-walk neighbors and signal companions.
4. Attach `row_plan`, including `layer`, `answerability`,
   `axis2_retrieval`, `axis3_reasoning`, `capability`, `answer_type`, and
   `style_hint`.
5. Apply prepare-side quality rescues for common analyzer fallback noise, such
   as conditional spans anchored at file headers or include edges pointing at
   guard lines.

Stage 0 is deterministic for reproducibility. Deterministic selection means
that, given the same bundle, profile, sorting keys, and attempt seed, the same
signals are chosen in the same order. It does not mean that every row is
accepted; M2 and downstream gates can still reject the row.

### 5.2 M2 evidence curator

Prompt: `skills/benchmark-generator/modules/M2_evidence_curator.md`.

M2 decides which Stage 0 candidate spans are substantive enough to support the
row plan.

Rules:

- L1 rows keep the minimum evidence set from one source.
- L2 rows require at least two distinct `source_id` values.
- L3 rows require at least two distinct `source_id` values whose statements can
  be read as a mechanism chain.
- Boilerplate must be rejected with explicit reason codes:
  `license_header`, `copyright_continuation`, `rst_heading_only`,
  `sphinx_config_boilerplate`, `ci_workflow_header`,
  `assertion_macro_fence`, `blank_or_separator`, `no_guard_token_available`,
  `layer_companion_missing`, or `other_boilerplate`.
- Each selected span gets a one-sentence `statement` explaining what the span
  shows. The statement must not be a raw quote.

Validator: M2 must pass `validate_module_outputs.py --module M2`.

### 5.3 M3 claim extractor

Prompt: `skills/benchmark-generator/modules/M3_claim_extractor.md`.

M3 turns curated evidence statements into 1-3 behavioral claims. Claims are the
bridge from evidence to query/answer/rubric.

Rules:

- Claims must be propositional, not instructions.
- Each claim must cite evidence ids selected by M2.
- Missing-evidence rows produce a negative claim explaining the absent support.

Validator: M3 must pass `validate_module_outputs.py --module M3`.

### 5.4 M5 question author

Prompt: `skills/benchmark-generator/modules/M5_question_author.md`.

M5 writes the user-facing query and normalized `query_rewrite`.

Rules:

- The query must be natural and task-shaped, not a path lookup.
- No explicit file path or basename may appear unless the row has an explicit
  `file_anchor_required` tag.
- The query should reflect `style_hint` and the declared answerability.
- False-premise rows should include the false premise naturally enough that a
  weak model may accept it, while the expected answer must reject it.

Validator: M5 must pass `validate_module_outputs.py --module M5`.

### 5.5 M6 answer drafter

Prompt: `skills/benchmark-generator/modules/M6_answer_drafter.md`.

M6 drafts `expected_answer` from M2 evidence and M3 claims.

Rules:

- The answer must be directly grounded in selected evidence.
- It must include the required citation paths in the expected format.
- For unanswerable rows, it must refuse with the specific reason: missing
  evidence, false premise, or ambiguity.
- It must avoid rubric-like meta phrasing such as "the answer should mention".

Validator: M6 must pass `validate_module_outputs.py --module M6`.

### 5.6 M7 rubric atomizer

Prompt: `skills/benchmark-generator/modules/M7_rubric_atomizer.md`.

M7 decomposes the M6 answer into small scoring atoms.

Rules:

- Required atoms must be independently checkable propositions.
- Each required atom cites supporting evidence or an earlier atom dependency.
- Forbidden atoms capture likely hallucinations, false premises, and wrong
  source choices.
- L3 rows must include at least one dependency between atoms.

Validator: M7 must pass `validate_module_outputs.py --module M7`.

### 5.7 M8 self-verifier

Prompt: `skills/benchmark-generator/modules/M8_self_verifier.md`.

M8 is a blind answerability check. It sees only the M5 query and M2 evidence,
not M3 claims, M6 answers, or M7 rubrics.

Rules:

- Re-derive the answer independently.
- Use `verdict: pass` only when the answer is recoverable from the curated
  evidence.
- Use refusal only when the row is actually unanswerable or the curated
  evidence is insufficient.
- Cite only M2-selected evidence.

Validator: M8 must pass `validate_module_outputs.py --module M8`. Release
assembly should use strict M8 so failed self-verification drops the row.

### 5.8 M9 adversarial gate

Prompt: `skills/benchmark-generator/modules/M9_adversarial_gate.md`.
Implementation: `skills/benchmark-generator/scripts/adversarial_gate_v2.py`.

M9 tests whether declared difficulty attributes have operational bite.

Flow:

1. Prepare weak-baseline tasks deterministically from queries, row plans, and
   curated evidence.
2. Host LLM answers each weak-baseline task under the restricted information
   view.
3. The deterministic judge maps baseline answers back to attribute verdicts.
4. Rows whose required gates fail are marked `passed: false` and dropped by the
   assembler.

M9 is not the same as full benchmark baseline evaluation. It is a generation
gate that prevents a row from claiming difficulty when the matched weak view
can still answer it.

---

## 6. Release policy

### 6.1 Required validation sequence

For each project and each attempt:

1. Run Stage 0 prepare.
2. Generate and validate M2.
3. Generate and validate M3.
4. Generate and validate M5, M6, and M7.
5. Generate and validate M8.
6. Run M9 prepare, baseline-answer generation, and judge.
7. Assemble with `--use-module-outputs`.
8. Run generator lint.
9. Run `benchmark-validator` lint.
10. Select exactly 100 validator-clean rows for release.

Rows may be dropped at M2, M8, M9, assembly, generator lint, or final
benchmark-validator lint. A row is release-eligible only after all gates.

### 6.2 Repeat policy

The v1.2 release target is:

- `nvdla`: 100 validator-clean rows.
- `vortex`: 100 validator-clean rows.

If a project has fewer than 100 release-eligible rows after one complete
attempt, run up to two additional complete attempts for that project. Each
attempt must re-run Stage 0 through final validator; do not mechanically pad,
duplicate, or repair rows outside the pipeline. If the project still has fewer
than 100 rows after three total attempts, stop and report the deficit with the
drop reasons.

### 6.3 Output contract

Final release artifacts live under `runs/v1_2/`:

```text
runs/v1_2/
  nvdla_benchmark_v1_2.jsonl
  nvdla_benchmark_v1_2.metadata.json
  nvdla_generation_report_v1_2.md
  nvdla_validation_report_v1_2.json
  nvdla_validation_report_v1_2.md
  vortex_benchmark_v1_2.jsonl
  vortex_benchmark_v1_2.metadata.json
  vortex_generation_report_v1_2.md
  vortex_validation_report_v1_2.json
  vortex_validation_report_v1_2.md
  v1_2_release_report.md
```

Working attempt artifacts live under `drafts/v1_2_attempt_<n>/` and
`runs/v1_2_attempt_<n>/`. Root `drafts/<project>.*` files are development
smoke artifacts and are not release inputs.

Metadata must record:

- source context bundle path and analyzer version;
- attempt count per project;
- module files used;
- module validation status;
- M8 pass counts;
- M9 pass/drop counts;
- assembled row counts;
- final validator-clean counts;
- selected case ids;
- known limitations.

---

## 7. Current constraints and risks

1. **Analyzer quality still bounds benchmark quality.** The current Vortex
   bundle was produced by regex fallback. Prepare and M2 can reject many bad
   spans, but they cannot invent semantic edges that the analyzer never found.
2. **L3 remains the hardest target.** Without `calls`, `instantiates`,
   `reads`, `writes`, `uses_type`, or `tested_by` edges, L3 candidates often
   rely on weak file-structure neighbors rather than true behavioral chains.
3. **`doc_code_divergence` is only as good as the analyzer signal.** If the
   analyzer emits doc mentions as divergence, M2/M8 should reject rows where no
   real disagreement can be stated.
4. **Implementation names lag semantic names.** `generate_v1_1_release_corpora.py`
   is currently the module-output assembler. v1.2 release artifacts should be
   named v1.2 even when this compatibility assembler is used.
5. **Root drafts are not authoritative.** Earlier small `drafts/nvdla.*` and
   `drafts/vortex.*` files were smoke tests and must not be counted as v1.2
   production data.

---

## 8. Implementation checklist

For a v1.2 benchmark production run:

1. Delete stale `runs/v1_2*` release artifacts from prior incorrect attempts.
2. Create a fresh attempt directory under `drafts/v1_2_attempt_<n>/`.
3. Run Stage 0 prepare for NVDLA and Vortex.
4. Produce host-LLM outputs for M2, M3, M5, M6, M7, M8, and M9.
5. Validate every module output before assembly.
6. Assemble with module outputs only; do not allow missing module stages to
   fall back silently to deterministic templates in release mode.
7. Rename/stamp final release artifacts as v1.2.
8. Run generator lint and benchmark-validator lint.
9. Select 100 validator-clean rows per project.
10. Write a release report with counts, attempts, drops, and residual risks.

