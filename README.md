# KB Benchmark Skills

This repository contains reusable Codex/Claude-style skills for building and validating retrieval QA benchmarks from source repositories, documentation, issue exports, and release metadata.

The v1 design is intentionally split into three independent skills:

```text
benchmark-repo-analyzer -> benchmark-generator -> benchmark-validator
```

Each skill communicates through file artifacts instead of calling the next skill directly. This keeps the workflow usable from Codex, Claude, shell scripts, CI, or a manual review process.

## Repository Layout

```text
skills/
  benchmark-repo-analyzer/   # Parse target repositories into source/entity/relation artifacts
  benchmark-generator/       # Generate benchmark JSONL from analyzer artifacts
  benchmark-validator/       # Lint benchmark data and evaluate retrieval/answer runs
schemas/                     # JSON schemas for the shared v1 contracts
examples/chip-kb-v1/          # Minimal self-test fixture
repo_sources/                 # Local sample source snapshots, e.g. NVDLA and Vortex
archive/legacy-v0-experiments/ # Older experimental plans and generated artifacts
install.sh                    # Install skills into Codex or Claude skill directories
```

`repo_sources/` is sample input data, not part of the skill implementation. It can be replaced with any target project source tree.

## Install

Install into Codex:

```bash
sh install.sh codex
```

Install into Claude:

```bash
sh install.sh claude
```

By default this copies the three skills into:

```text
~/.codex/skills/
```

or:

```text
~/.claude/skills/
```

After installing into Codex, restart the Codex session before expecting `/skills` to show the new skills. Current sessions usually do not hot-reload newly copied skill directories.

## Codex CLI Usage

Use these commands as messages inside Codex CLI after installation and session restart. They are skill invocations, not shell commands.

Analyze NVDLA source snapshots:

```text
$benchmark-repo-analyzer
Analyze repo_sources/nvdla/hw, repo_sources/nvdla/sw, and repo_sources/nvdla/doc as project nvdla.
Use CodeGraph for code structure when available.
Write the analyzer bundle to runs/nvdla_context_bundle with project_manifest.json, source_inventory.jsonl, entity_index.jsonl, relation_graph.jsonl, and analyzer_report.md.
Exclude .git, .omx, and prebuilt binaries.
Run the bundle validator before reporting completion.
```

Generate an NVDLA benchmark:

```text
$benchmark-generator
Use runs/nvdla_context_bundle as the analyzer bundle.
Create or use runs/nvdla_generation_profile.yaml for a 50-case NVDLA benchmark.
Expand capability seeds from analyzer_report.md and relation_graph.jsonl.
Generate runs/nvdla_benchmark_v1.jsonl, runs/nvdla_benchmark_v1.metadata.json, and runs/nvdla_generation_report.md.
Make queries realistic and varied; keep query_rewrite free of hidden evidence-derived facts.
Run the generator lint before reporting completion.
```

Validate the generated NVDLA benchmark:

```text
$benchmark-validator
Lint runs/nvdla_benchmark_v1.jsonl using context bundle runs/nvdla_context_bundle.
Select 10 diverse sample cases for the report.
Write a markdown report to runs/nvdla_validation_report.md and a JSON report to runs/nvdla_validation_report.json.
Explain hard failures, warnings, retrieval/evidence relevance, expected-answer quality, and atom rubric quality.
```

Analyze Vortex source snapshots:

```text
$benchmark-repo-analyzer
Analyze repo_sources/vortex/vortex as project vortex.
Use source role main_code_doc_repo and authority primary_source.
Write the analyzer bundle to runs/vortex_context_bundle.
Exclude .git, .omx, and hw/syn/synopsys/models.
Run the bundle validator before reporting completion.
```

Generate and validate a Vortex benchmark:

```text
$benchmark-generator
Use runs/vortex_context_bundle as the analyzer bundle.
Create or use runs/vortex_generation_profile.yaml for a 50-case Vortex benchmark.
Cover documentation/code cross-checks, mechanism traces, build/simulation flows, tests/debug evidence, and negative or insufficient-evidence cases when supported by the bundle.
Generate runs/vortex_benchmark_v1.jsonl, metadata, and generation report.
Run the generator lint before reporting completion.
```

```text
$benchmark-validator
Lint runs/vortex_benchmark_v1.jsonl using context bundle runs/vortex_context_bundle.
Select 10 diverse sample cases for the report.
Write reports to runs/vortex_validation_report.md and runs/vortex_validation_report.json.
```

Evaluate a knowledge-system run:

```text
$benchmark-validator
Evaluate run results runs/nvdla_run_results.jsonl against runs/nvdla_benchmark_v1.jsonl using context bundle runs/nvdla_context_bundle.
Score reference recall, evidence recall, citation compliance, and answer atom coverage.
Write reports to runs/nvdla_run_evaluation.md and runs/nvdla_run_evaluation.json.
Flag lexical atom scores as heuristic unless a semantic judge is used.
```

Evaluate method predictions with a DeepSeek LLM judge:

```bash
export DEEPSEEK_API_KEY="..."

python3 scripts/evaluate_methods.py \
  runs/nvdla_benchmark_v1.jsonl \
  predictions/nvdla_baseline_oracle_codex_predictions.jsonl \
  --top-k 10 \
  --llm-judge-provider deepseek \
  --llm-judge-model deepseek-v4-pro \
  --llm-judge-api-key-env DEEPSEEK_API_KEY \
  --output-json runs/nvdla_method_eval.deepseek.json \
  --output-md runs/nvdla_method_eval.deepseek.md
```

The API key is read only from the named environment variable and is not written into reports. Pass `--llm-judge-api-key-env DEEPSEEK_API_KEY`, not the key value itself. Retrieval recall and citation compliance remain deterministic; the LLM judge only scores answer semantics against `expected_answer`, `evidence`, and `answer_rubric`.

Codex baseline predictions generated by `scripts/run_codex_baselines.py` include token accounting from `codex exec --json`:

```json
{
  "baseline": "grep-agent",
  "model": "gpt-5.4-mini",
  "prompt_chars": 905,
  "token_usage": {
    "source": "codex_exec_json",
    "events_seen": 1,
    "total_token_usage": {
      "input_tokens": 128525,
      "cached_input_tokens": 89600,
      "output_tokens": 999,
      "reasoning_output_tokens": 516,
      "total_tokens": 129524
    },
    "last_token_usage": {"total_tokens": 129524},
    "model_context_window": null
  }
}
```

`scripts/evaluate_methods.py` aggregates these fields as `token_usage_coverage`, `mean_total_tokens`, and `sum_total_tokens`, so retrieval/answer quality can be compared with token cost.

## v1.1 Release Artifacts

The v1.1 benchmarks are separate from v1:

```text
runs/nvdla_benchmark_v1_1.jsonl
runs/vortex_benchmark_v1_1.jsonl
```

Each release corpus contains 200 admitted rows with explicit `answerability`,
`difficulty`, and signal-backed `difficulty.claim_sources`. Validate them with
explicit v1.1 rules:

```bash
python3 skills/benchmark-validator/scripts/validate_benchmark.py lint \
  runs/nvdla_benchmark_v1_1.jsonl \
  --context-bundle runs/nvdla_context_bundle \
  --repo-root . \
  --schema-version v1.1 \
  --structural-gate-json runs/nvdla_benchmark_v1_1.structural_gate.json
```

Run deterministic baseline evaluation after the matching v1.1 prediction JSONL
has been generated:

```bash
python3 scripts/run_codex_baselines.py grep-agent \
  runs/nvdla_benchmark_v1_1.jsonl \
  --repo-root . \
  --repo-path repo_sources/nvdla \
  --output predictions/nvdla_baseline_grep_agent_predictions_v1_1.jsonl \
  --workers 4 \
  --resume

python3 scripts/evaluate_methods.py \
  runs/nvdla_benchmark_v1_1.jsonl \
  predictions/nvdla_baseline_grep_agent_predictions_v1_1.jsonl \
  --top-k 10 \
  --output-json predictions/nvdla_baseline_grep_agent_eval_v1_1.json \
  --output-md predictions/nvdla_baseline_grep_agent_eval_v1_1.md
```

## v1.1 Development Workflow

v1.1 keeps v1 artifacts valid by default. Use explicit v1.1 mode for stricter
answerability and difficulty checks:

```bash
python3 skills/benchmark-validator/scripts/validate_benchmark.py lint \
  runs/nvdla_benchmark_v1_1.jsonl \
  --context-bundle runs/nvdla_context_bundle \
  --repo-root . \
  --schema-version v1.1 \
  --structural-gate-json runs/nvdla_benchmark_v1_1.structural_gate.json
```

Build analyzer signals before v1.1 generation:

```bash
python3 skills/benchmark-repo-analyzer/scripts/build_signal_index.py \
  runs/nvdla_context_bundle \
  --output runs/nvdla_context_bundle/signal_index.jsonl
```

Run the adversarial gate in dry-run mode when no judge provider is configured:

```bash
python3 skills/benchmark-validator/scripts/adversarial_gate.py \
  runs/nvdla_benchmark_v1_1.jsonl \
  --dry-run \
  --output-jsonl runs/nvdla_benchmark_v1_1.adversarial_gate.jsonl
```

## Skill Overview

### benchmark-repo-analyzer

Use this first. It turns target source roots into a `project_context_bundle/`:

```text
project_manifest.json
source_inventory.jsonl
entity_index.jsonl
relation_graph.jsonl
analyzer_report.md
```

The analyzer owns source parsing, source classification, entity extraction, and relation graph construction. It should use CodeGraph for code structure when available, and parsers or heuristics for docs, scripts, configs, issues, and releases.

### benchmark-generator

Use this after analyzer output exists. It consumes:

```text
project_context_bundle/
generation_profile.yaml
```

It outputs:

```text
benchmark.jsonl
benchmark_metadata.json
generation_report.md
```

The generator owns capability expansion, sampling, realistic `query` generation, `query_rewrite`, `references`, `evidence`, direct `expected_answer`, and atomized `answer_rubric`.

### benchmark-validator

Use this after benchmark generation, or after a knowledge-system run.

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

Retrieval quality is scored from `references` and `evidence`. Answer quality is scored from atomized `answer_rubric.required_atoms` using a deterministic lexical heuristic by default. Treat that answer score as triage unless you add a semantic judge.

For provider-backed semantic answer judging, use the method evaluator:

```bash
export DEEPSEEK_API_KEY="..."

python3 scripts/evaluate_methods.py \
  examples/chip-kb-v1/sample_benchmark.jsonl \
  examples/chip-kb-v1/sample_run_results.jsonl \
  --llm-judge-provider deepseek \
  --llm-judge-model deepseek-v4-pro \
  --output-json method_eval.json \
  --output-md method_eval.md
```

Use `--llm-judge-model deepseek-v4-flash` for a cheaper judge, or add `--llm-judge-thinking disabled` when you want non-thinking mode. Use `--require-llm-judge` in CI if missing or failed judge calls should fail the run.

Probe Codex token usage for one benchmark case:

```bash
python3 scripts/verify_codex_token_usage.py \
  examples/chip-kb-v1/sample_benchmark.jsonl \
  --repo-root . \
  --repo-path examples/chip-kb-v1/sample_source \
  --output-json runs/token_usage_verification.sample.json \
  --output-md runs/token_usage_verification.sample.md
```

This diagnostic script runs the same case with the oracle and grep-agent prompts, enables `codex exec --json`, and compares usage from either `token_count` events or the current `turn.completed.usage` event format. It does not write the formal baseline prediction JSONL.

## Quick Self-Test

Run the bundled fixture checks:

```bash
python3 skills/benchmark-repo-analyzer/scripts/validate_context_bundle.py \
  examples/chip-kb-v1/project_context_bundle \
  --repo-root . \
  --fail-on-warn

python3 skills/benchmark-generator/scripts/lint_benchmark_jsonl.py \
  examples/chip-kb-v1/sample_benchmark.jsonl \
  --repo-root . \
  --fail-on-warn

python3 skills/benchmark-validator/scripts/validate_benchmark.py evaluate \
  examples/chip-kb-v1/sample_benchmark.jsonl \
  examples/chip-kb-v1/sample_run_results.jsonl \
  --context-bundle examples/chip-kb-v1/project_context_bundle \
  --repo-root .
```

Expected result:

```text
FAIL: 0
WARN: 0
Run PASS: 1
```

## Using NVDLA and Vortex as Sample Inputs

This repository can use the local source snapshots under `repo_sources/` as realistic analyzer inputs.

Example analyzer request for NVDLA:

```yaml
schema_version: analyzer-request/v1
project:
  id: nvdla
  display_name: NVDLA
source_roots:
  - id: nvdla_hw
    local_root: repo_sources/nvdla/hw
    repo_name: nvdla/hw
    source_role: main_hw_repo
    authority: primary_source
  - id: nvdla_sw
    local_root: repo_sources/nvdla/sw
    repo_name: nvdla/sw
    source_role: main_sw_repo
    authority: primary_source
  - id: nvdla_doc
    local_root: repo_sources/nvdla/doc
    repo_name: nvdla/doc
    source_role: doc_source_repo
    authority: documentation
analysis_backends:
  code:
    primary: code_graph
    fallbacks: [ripgrep, tree_sitter, lsp]
include: ["**/*"]
exclude: ["**/.git/**", "**/.omx/**", "**/prebuilt/**"]
```

Example analyzer request for Vortex:

```yaml
schema_version: analyzer-request/v1
project:
  id: vortex
  display_name: Vortex
source_roots:
  - id: vortex_main
    local_root: repo_sources/vortex/vortex
    repo_name: vortexgpgpu/vortex
    source_role: main_code_doc_repo
    authority: primary_source
analysis_backends:
  code:
    primary: code_graph
    fallbacks: [ripgrep, tree_sitter, lsp]
include: ["**/*"]
exclude: ["**/.git/**", "**/.omx/**", "hw/syn/synopsys/models/**"]
```

The analyzer should turn either request into a `project_context_bundle/`. The generator should then consume that bundle plus a `generation_profile.yaml`; it should not directly scan `repo_sources/`.

## Generated Benchmark Row Shape

Each benchmark JSONL row uses the v1 shape:

```json
{
  "case_id": "project-v1-L3-001",
  "project": "project",
  "layer": {"code": "L3", "zh": "交叉验证"},
  "capability": {"code": "mechanism_trace", "zh": "机制链路解释"},
  "query": "真实用户风格问题",
  "query_rewrite": "只基于 query 可见语义的标准化检索意图",
  "answer_type": {"code": "yes_no", "zh": "是否判断"},
  "references": [],
  "evidence": [],
  "expected_answer": "直接回答问题，并在需要时嵌入 path:line 证据。",
  "answer_rubric": {
    "answer_goal": "...",
    "required_atoms": [],
    "forbidden_atoms": [],
    "citation_policy": {}
  }
}
```

Keep these boundaries strict:

- `references`: validates retrieval.
- `evidence`: validates answer grounding.
- `expected_answer`: human-readable standard answer.
- `answer_rubric.required_atoms`: structured answer scoring units.
- `query_rewrite`: must not include hidden assumptions or facts discovered after retrieval.

## Notes

- `archive/legacy-v0-experiments/` preserves earlier experimental plans, generated JSONL files, and old local skills. The v1 skills do not depend on those files.
- `repo_sources/` may contain large source snapshots and local runtime state such as `.omx/`; exclude runtime state from analyzer inputs.
- Current skill installation is copy-based. Re-run `sh install.sh codex` after editing files under `skills/`.
