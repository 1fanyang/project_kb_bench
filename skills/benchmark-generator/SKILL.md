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

## Bundle source (v2 canonical as of 2026-06-30)

`runs/<project>_context_bundle/` is the v2 analyzer bundle (CodeGraph
+ tree-sitter-verilog + re-parse-derived signals). The legacy v1
regex-fallback bundle is archived at
`runs/archive/<project>_context_bundle_v1/` for reproducing historical
v1 benchmarks.

Default invocation reads from the canonical (v2) path:

```bash
uv run python skills/benchmark-generator/scripts/prepare_module_inputs.py \
    --project vortex \
    --repo-root /path/to/checkout
```

To explicitly target a non-default bundle (e.g. to compare against the
archived v1):

```bash
uv run python skills/benchmark-generator/scripts/prepare_module_inputs.py \
    --project vortex \
    --bundle-path runs/archive/vortex_context_bundle_v1/ \
    --repo-root /path/to/checkout
```

When prepare reads a v2 bundle, the `signal_dataflow` attribute
(produced by the analyzer's verilog re-parse) is dropped silently and
counted to stdout. Existing axis filters and `PREFERRED_ATTRIBUTE_GROUPS`
are unchanged. To wire `signal_dataflow` as a selectable axis
attribute, add it to both `KNOWN_AXIS_ATTRIBUTES` and the relevant
`PREFERRED_ATTRIBUTE_GROUPS` entry in
`scripts/generate_v1_1_release_corpora.py` — a coordinated change, not
a silent default flip. (Phase 5 smoke50 confirmed signal_dataflow is
not currently needed: 21/21 Verilog L3 rows already have
`conditional_behavior` axis-3 coverage.)

The release-corpora assembler (`scripts/generate_v1_1_release_corpora.py`)
mirrors the same `--bundle-path` flag — pass it through when reading
non-default bundles so M2/M5/M6/M7/M9 stages load signals from the same
bundle the candidates came from.

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

## v1.1 modular generation (Ship 2 + Ship 3)

When invoked inside Claude Code or Codex, run the host-LLM-augmented pipeline.
The host CLI *is* the LLM; the skill provides instructions and validators.

The pipeline runs eight stages (Stage 0 prepare + M2/M3/M5/M6/M7/M8/M9 +
assemble + lint). Each stage's output is a JSONL file at a known path and is
validated before the next stage runs.

```
Stage 0  prepare        ──► drafts/<project>.candidates.jsonl
                              (row_plan.style_hint; graph-walk neighbors;
                               negative_evidence axis on missing-evidence rows)
            │
            ▼  (host LLM — modules/M2_evidence_curator.md)
Stage 1  M2 curator     ──► drafts/<project>.curated_evidence.jsonl
            │
            ▼  (host LLM — modules/M3_claim_extractor.md)
Stage 2  M3 claims      ──► drafts/<project>.claims.jsonl
            │
            ├─► (host LLM — modules/M5_question_author.md)
            │   Stage 3  M5 query author     ──► drafts/<project>.queries.jsonl
            │
            └─► (host LLM — modules/M6_answer_drafter.md)
                Stage 4  M6 answer drafter   ──► drafts/<project>.answers.jsonl
                    │
                    ▼  (host LLM — modules/M7_rubric_atomizer.md)
                    Stage 5  M7 rubric       ──► drafts/<project>.rubrics.jsonl

(After M5/M6/M7 — M8 and M9 are quality gates, deferrable for smoke runs.)
            ▼  (host LLM — modules/M8_self_verifier.md)
Stage 6  M8 self-verify ──► drafts/<project>.verifier.jsonl
            │
            ▼  (host LLM via Stage 7a tasks — modules/M9_adversarial_gate.md)
Stage 7a M9 baselines   ──► drafts/<project>.baseline_tasks.jsonl
                            drafts/<project>.baseline_answers.jsonl
Stage 7b M9 judge       ──► drafts/<project>.adversarial_gate.jsonl
            │
            ▼
Stage 8  assemble       ──► runs/<project>_benchmark_v1_1.jsonl
                            runs/<project>_benchmark_v1_1.metadata.json
                            runs/<project>_generation_report_v1_1.md
            │
            ▼
Stage 9  lint           ──► runs/<project>_benchmark_v1_1.lint.json
```

M5 (queries) and the M6 → M7 chain are independent and may run in parallel.
M8 and M9 may also run in parallel with each other since they share inputs.
The assembler accepts any subset of stage outputs; missing files fall back to
the deterministic template path for that field, except the adversarial-gate
file, whose `passed: false` verdicts drop rows.

I/O contracts and the full validation-command catalog: `modules/contracts.md`.
Per-stage prompts and few-shot examples:
`modules/M2_evidence_curator.md` / `modules/M3_claim_extractor.md` /
`modules/M5_question_author.md` / `modules/M6_answer_drafter.md` /
`modules/M7_rubric_atomizer.md` / `modules/M8_self_verifier.md` /
`modules/M9_adversarial_gate.md`.

### Stage 0 — prepare (deterministic)

```bash
python skills/benchmark-generator/scripts/prepare_module_inputs.py \
  --project nvdla --output-dir drafts --repo-root .
```

Writes `drafts/nvdla.candidates.jsonl`: one line per planned row, holding the
anchor and 1-N candidate evidence spans. `unanswerable_missing_evidence` rows
have empty `candidates`.

### Stage 1 — M2 Evidence Curator (host LLM)

Read `modules/M2_evidence_curator.md` for the prompt + few-shot examples. For
each line of the candidates file, decide which candidates are substantive,
reject boilerplate, and write a one-sentence interpretive `statement` for
each kept span. Write `drafts/<project>.curated_evidence.jsonl`.

Validate before continuing:

```bash
python skills/benchmark-generator/scripts/validate_module_outputs.py \
  --module M2 --candidates drafts/<project>.candidates.jsonl \
  drafts/<project>.curated_evidence.jsonl
```

### Stage 2 — M3 Behavioral Claim Extractor (host LLM)

Read `modules/M3_claim_extractor.md`. Extract 1–3 propositional claims per
row from the M2 curated evidence. Write `drafts/<project>.claims.jsonl`.

```bash
python skills/benchmark-generator/scripts/validate_module_outputs.py \
  --module M3 --candidates drafts/<project>.candidates.jsonl \
  --curated drafts/<project>.curated_evidence.jsonl \
  drafts/<project>.claims.jsonl
```

### Stage 3 — M5 Question Author (host LLM)

Read `modules/M5_question_author.md`. Compose a realistic, axis-aware query
plus `query_rewrite` per row, respecting `row_plan.style_hint`. Write
`drafts/<project>.queries.jsonl`. The host LLM must not put any file path
or basename token from M2 evidence into the query (unless the row carries
the `file_anchor_required` tag).

```bash
python skills/benchmark-generator/scripts/validate_module_outputs.py \
  --module M5 --candidates drafts/<project>.candidates.jsonl \
  --curated drafts/<project>.curated_evidence.jsonl \
  drafts/<project>.queries.jsonl
```

### Stage 4 — M6 Answer Drafter (host LLM)

Read `modules/M6_answer_drafter.md`. Compose the expected_answer string per
row from the claims, with the required citations. Write
`drafts/<project>.answers.jsonl`.

```bash
python skills/benchmark-generator/scripts/validate_module_outputs.py \
  --module M6 --candidates drafts/<project>.candidates.jsonl \
  --curated drafts/<project>.curated_evidence.jsonl \
  --claims drafts/<project>.claims.jsonl \
  drafts/<project>.answers.jsonl
```

### Stage 5 — M7 Rubric Atomizer (host LLM)

Read `modules/M7_rubric_atomizer.md`. Decompose the M6 expected_answer into
propositional required_atoms plus named forbidden_atoms. Write
`drafts/<project>.rubrics.jsonl`.

```bash
python skills/benchmark-generator/scripts/validate_module_outputs.py \
  --module M7 --candidates drafts/<project>.candidates.jsonl \
  --curated drafts/<project>.curated_evidence.jsonl \
  --claims drafts/<project>.claims.jsonl \
  --answers drafts/<project>.answers.jsonl \
  drafts/<project>.rubrics.jsonl
```

### Stage 6 — M8 Self-Verifier (host LLM)

Read `modules/M8_self_verifier.md`. Blindly re-derive the answer from M2
evidence + M5 query (no access to M6 answer / M3 claims / M7 rubric).
Write `drafts/<project>.verifier.jsonl`.

```bash
python skills/benchmark-generator/scripts/validate_module_outputs.py \
  --module M8 --candidates drafts/<project>.candidates.jsonl \
  --curated drafts/<project>.curated_evidence.jsonl \
  --answers drafts/<project>.answers.jsonl \
  drafts/<project>.verifier.jsonl
```

### Stage 7 — M9 Adversarial Gate (deterministic dispatch + host LLM baselines)

Read `modules/M9_adversarial_gate.md`. Run in two sub-stages:

```bash
# 7a — emit baseline tasks for the host LLM to answer
python skills/benchmark-generator/scripts/adversarial_gate_v2.py prepare \
  --project <project> --drafts-dir drafts

# (host LLM answers each task in drafts/<project>.baseline_tasks.jsonl,
#  writes drafts/<project>.baseline_answers.jsonl)

# 7b — judge the answers and write per-row verdicts
python skills/benchmark-generator/scripts/adversarial_gate_v2.py judge \
  --project <project> --drafts-dir drafts
```

The verdict file `drafts/<project>.adversarial_gate.jsonl` is consumed by
the assembler. Rows with `passed: false` are dropped at assembly.

### Stage 8 — assemble (deterministic)

```bash
python scripts/generate_v1_1_release_corpora.py \
  --use-module-outputs drafts --project nvdla --output-dir runs \
  [--enforce-target-count]
```

When `--use-module-outputs` points at a directory, the generator splices in
whichever of `<project>.curated_evidence.jsonl`, `<project>.queries.jsonl`,
`<project>.answers.jsonl`, `<project>.rubrics.jsonl`,
`<project>.adversarial_gate.jsonl` exist. Anything missing falls back to
the deterministic template path for that field, except the
adversarial-gate file: its `passed: false` verdicts drop rows. Rows whose
M2 returned empty `selected_evidence` (and that aren't
`unanswerable_missing_evidence`) are also dropped — they failed the
substantive-span filter. When `--use-module-outputs` is omitted, the
existing template behavior runs unchanged.

With `--enforce-target-count`, the assembler exits non-zero if the actual
admitted row count is below the profile's target. The drop log (M2 +
adversarial gate) is recorded in both the metadata JSON and the
generation report so the gap is auditable.

### Stage 9 — lint (deterministic)

```bash
python skills/benchmark-generator/scripts/lint_benchmark_jsonl.py \
  runs/<project>_benchmark_v1_1.jsonl --repo-root . --schema-version v1.1 \
  --json-report runs/<project>_benchmark_v1_1.lint.json
```

The lint extensions from Ship 1 enforce: no anchor-token leak, no
unanswerable refusal cue, no boilerplate evidence, no pointer-style atoms,
no verbatim-reasoning implicit_domain_knowledge violation, no over-reused
filler paths, forbidden_atoms required where the design specifies them,
guard-token sanity warning for `conditional_behavior` rows. See
`skills/benchmark-generator/scripts/lint_benchmark_jsonl.py:STRUCTURAL_REASON_MESSAGES`
for the full list.

### When the host LLM is not available

Skip the host-LLM stages. The assembler with `--use-module-outputs` omitted
falls back to the original deterministic template generator. Useful for CI
smoke tests.

## Release-mode recipe

A production release should fail loudly on any silent degradation rather
than ship a corrupted corpus. The flag combination below turns every
hygiene check on:

```bash
# Stage 0 — refuse to spend host-LLM tokens on signal-concentrated candidates.
python skills/benchmark-generator/scripts/prepare_module_inputs.py \
  --project all --output-dir drafts --repo-root . \
  --strict-diversity

# (run M2/M3/M5/M6/M7/M8/M9 host-LLM stages; validators emit FAILs on
#  shape errors and the user fixes them before moving on)

# Stage 8 — assemble with every guarantee on.
python scripts/generate_v1_1_release_corpora.py \
  --use-module-outputs drafts \
  --project all --output-dir runs \
  --require-stages M2,M5,M6,M7,M9 \
  --strict-m8 \
  --enforce-target-count
```

Effects:

- `--strict-diversity` (Stage 0) — prepare exits non-zero when any
  `(path, lines)` is reused over `PATH_LINES_REUSE_CAP` times or any
  anchor `source_id` is used over `ANCHOR_REUSE_CAP` times. Catches the
  failure mode where most candidates share a small set of paths.
- `--require-stages` (assembler) — every named module-output file must
  exist AND cover every candidate `case_id`. No silent template
  fallback for missing stages.
- `--strict-m8` (assembler) — rows whose M8 self-verifier disagreed with
  M6 (refused on answerable, confident on missing-evidence, fabricated a
  citation) are dropped, like adversarial-gate failures.
- `--enforce-target-count` (assembler) — non-zero exit if the assembled
  row count is below the profile target after all drops.

Without these flags the same commands run in permissive dev mode: warnings
print, templates fill in, low counts are recorded but accepted. Per-row
audit data (stages_used, m8_status, drop_log, target/actual/gap) is
always written to `<project>_benchmark_v1_1.metadata.json` and the
generation report regardless of strictness.

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
