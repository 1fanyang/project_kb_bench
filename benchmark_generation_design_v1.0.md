# Benchmark Toolkit Design v1.0

Status: first commit (66f2ef9).

Scope: documents what exists in `skills/`, `schemas/`, `scripts/`, `tests/`, `runs/`, and `predictions/`. Excludes `archive/` (legacy v0.x experiments) and `examples/` (self-test fixture only).

---

## 0. Reading guide

This doc is structured so each major component is documented twice: first as design intent, then as the concrete implementation. The two layers are kept close together (not in separate halves) so a reader can see, for each component, the answer to "what was it trying to do?" and "what does the code actually do today?" without page-flipping.

```
1. Purpose            (what the toolkit is for)
2. Architecture       (skill boundaries, artifact flow, schemas)
3. Analyzer           (design + implementation + outputs)
4. Generator          (design + implementation + outputs)
5. Validator          (design + implementation, lint and evaluate modes)
6. Baselines          (design + implementation + outputs)
7. Method evaluator   (design + implementation, retrieval + judge)
8. Diagnostics        (token-usage verifier)
9. Tests              (what is covered today)
10. Operational flows (end-to-end, NVDLA and Vortex)
11. Known limitations (what v1.0 does *not* do)
```

---

## 1. Purpose

The toolkit produces a retrieval-QA benchmark from a target project's source repository and provides the tooling to evaluate a knowledge-system run against it. It is split into three independent skills that communicate through file artifacts, plus a small set of helper scripts under `scripts/`.

```
benchmark-repo-analyzer  →  benchmark-generator  →  benchmark-validator
                                                      │
                       baselines (scripts/) ──────────┴──→  method evaluator (scripts/)
```

Design intent:

- **Independence.** Each skill can be invoked from Codex, Claude, shell, CI, or a manual review process. None calls another directly; they share data via well-defined JSONL/JSON files.
- **Re-use across projects.** The analyzer is project-agnostic; the generator is parameterized by a profile; the validator and evaluator know nothing about a specific project.
- **Separation of retrieval and answer scoring.** Retrieval is scored from `references` and `evidence` via deterministic path/line overlap. Answer correctness is scored separately, with two backends: a lexical heuristic baked into the validator (for offline triage) and an LLM judge in the method evaluator (for headline numbers).

---

## 2. Architecture

### 2.1 Skill layout

```
skills/
  benchmark-repo-analyzer/
    SKILL.md
    references/
      analyzer-contract.md
      codegraph-backend.md
    scripts/
      validate_context_bundle.py     # 376 lines, deterministic bundle validator
  benchmark-generator/
    SKILL.md
    references/
      generator-contract.md
      query-answer-rubric.md
    scripts/
      lint_benchmark_jsonl.py        # 457 lines, generator output lint
  benchmark-validator/
    SKILL.md
    references/
      validator-contract.md
      evaluation-logic.md
    scripts/
      validate_benchmark.py          # 970 lines, lint + evaluate subcommands
schemas/                             # 8 JSON Schema files (v1 contracts)
scripts/                             # helpers not inside any skill
  run_codex_baselines.py             # 493 lines, oracle + grep-agent baselines
  evaluate_methods.py                # 917 lines, method evaluator + LLM judge
  verify_codex_token_usage.py        # 314 lines, diagnostic
tests/                               # unittests for scripts/
runs/                                # generated artifacts (NVDLA, Vortex)
predictions/                         # baseline prediction + eval outputs
install.sh                           # copies skills into ~/.codex or ~/.claude
```

Skills install by *copy* via `install.sh`. There is no hot-reload; editing a skill requires re-running `sh install.sh codex` and restarting the Codex session.

### 2.2 Artifact flow

```
                       analyzer_request.yaml (thin, optional)
                                  │
                                  ▼
            ┌─────────────── benchmark-repo-analyzer ────────────────┐
            │  inputs:  repo_sources/<project>/                       │
            │  outputs: project_context_bundle/                       │
            │    ├─ project_manifest.json                             │
            │    ├─ source_inventory.jsonl                            │
            │    ├─ entity_index.jsonl                                │
            │    ├─ relation_graph.jsonl                              │
            │    └─ analyzer_report.md                                │
            └─────────────────────────────────────────────────────────┘
                                  │
                generation_profile.yaml (target counts, capability seeds)
                                  │
                                  ▼
            ┌─────────────── benchmark-generator ─────────────────────┐
            │  inputs:  project_context_bundle/ + generation_profile  │
            │  outputs:                                               │
            │    ├─ benchmark.jsonl                                   │
            │    ├─ benchmark_metadata.json                           │
            │    └─ generation_report.md                              │
            │  lint:    lint_benchmark_jsonl.py                       │
            └─────────────────────────────────────────────────────────┘
                                  │
                                  ▼
            ┌────────────── benchmark-validator (lint) ───────────────┐
            │  inputs:  benchmark.jsonl (+ context bundle, optional)  │
            │  outputs: validation_report.md / .json                  │
            └─────────────────────────────────────────────────────────┘
                                  │
            ┌─────────────────────┴─────────────────────┐
            ▼                                            ▼
    scripts/run_codex_baselines.py             a real knowledge system
        oracle | grep-agent                             │
            │                                            │
            ▼                                            ▼
    predictions/*.jsonl  ─────────────────►   run_results.jsonl
                                                      │
                              ┌───────────────────────┴───────────────────────┐
                              ▼                                                ▼
            benchmark-validator (evaluate)               scripts/evaluate_methods.py
            deterministic + lexical                       deterministic + LLM judge
            outputs: validation_report.md/.json           outputs: method_eval.md/.json
```

### 2.3 Schemas (v1 contracts)

All eight schemas under `schemas/` are versioned `*/v1`. Every JSONL file emitted by the toolkit (or expected as input) must validate against the matching schema.

| Schema | Title | Required fields (top-level) |
|---|---|---|
| `project-manifest.schema.json` | Benchmark Project Manifest | `schema_version`, `project`, `source_sets`, `created_at`, `analyzer_version` |
| `source-inventory.schema.json` | Analyzer Source Inventory Row | 14 fields incl. `source_id`, `modality`, `source_type`, `authority`, `parse_status`, `sha256`, `line_count` |
| `entity-index.schema.json` | Analyzer Entity Index Row | `entity_id`, `project`, `source_id`, `name`, `kind`, `path`, `line_start`, `line_end`, `extractor`, `confidence` |
| `relation-graph.schema.json` | Analyzer Relation Graph Row | `relation_id`, `project`, `subject`, `predicate`, `object`, `evidence[]`, `extractor`, `confidence` |
| `generation-profile.schema.json` | Benchmark Generation Profile | `schema_version`, `benchmark`, `input`, `projects`, `layers`; optional `capability_seeds` |
| `benchmark-row.schema.json` | Benchmark JSONL Row v1 | 10 fields incl. `case_id`, `layer`, `query`, `query_rewrite`, `references[≥1]`, `evidence[≥1]`, `expected_answer`, `answer_rubric` |
| `run-result.schema.json` | Benchmark Run Result Row | `case_id`, `answer` (+ optional `retrieved_contexts`/`retrieved`/`contexts`, `evidence`, `baseline`, `model`, `token_usage`) |
| `baseline-prediction.schema.json` | Codex Baseline Prediction | `case_id`, `pred_answer`, `evidence` |

All schemas set `additionalProperties: true` at the row level: extension fields are tolerated, but the required fields are enforced. This is what lets v1.1 (and beyond) add new attributes without breaking v1.0 artifacts.

---

## 3. Analyzer (`benchmark-repo-analyzer`)

### 3.1 Design

The analyzer owns project parsing. Downstream tools (generator, validator) consume its artifacts and **must not** re-scan the original repo for basic source/entity/relation discovery. The intent is to localize all source-knowledge to one stage so future analyzer improvements (CodeGraph, AST, LSP) do not ripple through generation logic.

Inputs: a thin `analyzer_request.yaml` (or equivalent) that lists source roots and analysis backends.

Outputs (the **project context bundle**):
- `project_manifest.json` — bundle-level metadata: project id, list of source sets with role/authority/commit/branch, analyzer version, warnings.
- `source_inventory.jsonl` — one row per retrievable source (code file, doc page, script, issue, release record). Includes `modality`, `source_type`, `authority`, `parse_status`, `sha256`, `line_count`.
- `entity_index.jsonl` — one row per extracted entity (function, macro, module, parameter, heading, flag, class, make_target, …). Each entity ties back to a `source_id` and a line range.
- `relation_graph.jsonl` — one row per relation (`defines`, `contains`, `calls`, `imports_or_includes`, `reads`, `writes`, `checks_condition`, `mentions`, `documents`, …). Each relation carries `evidence` anchors (source_id + line range + summary).
- `analyzer_report.md` — human-facing report: source-set status, counts by modality/source_type/authority, entity counts by kind/extractor, relation counts by predicate, parse failures, recommended capability seeds.
- Optional: `parse_diagnostics.jsonl`, `unresolved_sources.jsonl`, `graph_summary.json`.

The bundle is project-agnostic. Project-specific extensions (extra `source_type` values, project predicates) are allowed; the analyzer must document them in `analyzer_report.md`.

### 3.2 Backend strategy

`references/codegraph-backend.md` declares CodeGraph as the preferred v1 code backend with `ripgrep`, `tree_sitter`, and `lsp` as documented fallbacks. The `extractor` field on each entity/relation row records which backend produced it (`code_graph`, `code_graph+ripgrep_fallback`, `regex_c_family_parser`, etc.) and the `confidence` field reflects backend reliability.

A standard predicate vocabulary is defined for code structure:

| CodeGraph fact | Analyzer predicate |
|---|---|
| symbol definition | `defines` |
| caller/callee edge | `calls` |
| file containment | `contains` |
| import/include | `imports_or_includes` |
| condition around symbol | `checks_condition` |
| assignment / write | `writes` |
| read / reference | `reads` |

Doc/issue/release predicates (`doc_mentions_entity`, `documents`, `source_same_topic_as_source`, `script_invokes_target`, `test_exercises_entity`, `issue_mentions_entity`) round out the vocabulary.

### 3.3 Analyzer backends

The analyzer supports two interchangeable code backends. Each emits the same bundle shape (§3.1) and the same predicate vocabulary (§3.2); they differ in *what they can resolve* and *how trustworthy each row is*. The `extractor` and `confidence` fields on every entity/relation row identify which backend produced the fact, so downstream tools can weight by source.

#### 3.3.1 `code_graph` — semantic backend

A pre-built code graph index (functions, classes, modules, call edges, read/write sites, condition checks) is queried by the analyzer. Each fact is rooted in AST-level information, so call/callee and dataflow questions can be answered structurally.

- **Strengths.** Resolves `calls`, `reads`, `writes`, `checks_condition`, `imports_or_includes` predicates from real symbol-resolution rather than text match. Handles function overloading, scope, macros expanded at use sites, and cross-file references. Emits high-confidence (`confidence ≥ 0.9`) entity spans because line ranges come from the parser.
- **Weaknesses.** Requires the project's code graph index to exist and be reachable at analyzer run time. Coverage outside code (docs, scripts, configs, issue exports) is limited; non-code sources still rely on heuristic parsers.
- **`extractor` values.** `code_graph` when used standalone, `code_graph+ripgrep_fallback` when CodeGraph resolved the entity but text-matching produced the surrounding evidence span.

#### 3.3.2 `regex_parser` — text-pattern backend

The fallback / always-available backend. A family of language-specific regex parsers (`regex_hdl_parser`, `regex_c_family_parser`, `regex_python_parser`, `regex_cli_flag_parser`, `regex_make_parser`) plus `doc_heading_parser` walk the filesystem inventory and extract entities by pattern. Relations are produced from co-occurrence and structural pattern rules.

- **Strengths.** No external dependency. Deterministic, idempotent, easy to run in CI on any repo. Covers heading structure, CLI flags, make targets, and macro/function/class definitions across many languages — useful for doc-side and surface-symbol questions.
- **Weaknesses.** Cannot follow symbol references reliably across files; cannot emit `calls`/`reads`/`writes`/`checks_condition` without false positives, so the analyzer prefers to omit them. Macro-heavy codebases (NVDLA RTL/KMD) inflate the entity count with low-information macros. Confidence is calibrated downward (`0.7 – 0.85`) to reflect text-match uncertainty.
- **`extractor` values.** `regex_hdl_parser`, `regex_c_family_parser`, `regex_python_parser`, `doc_heading_parser`, `regex_cli_flag_parser`, `regex_make_parser`.

#### 3.3.3 Backend selection and fallback

The analyzer reads `analysis_backends.code` from `analyzer_request.yaml`:

```yaml
analysis_backends:
  code:
    primary: code_graph
    fallbacks: [ripgrep, tree_sitter, lsp]
```

If `code_graph` is unavailable at run time, the analyzer falls back to `regex_parser` and records the fact in two places: `project_manifest.json.warnings` (machine-readable) and `analyzer_report.md` under "Backend Status" (human-readable). Downstream tools can read `warnings` to gate behavior — e.g., the generator can down-weight call/callee questions when only the regex backend ran.

#### 3.3.4 NVDLA as a worked example

The NVDLA bundle shipped today (`runs/nvdla_context_bundle/`) was produced by the **regex_parser** backend. The manifest carries:

```
warnings: ["CodeGraph was requested but not initialized for this project;
            used filesystem inventory and regex/parser fallback extractors."]
```

Resulting bundle sizes:

| Dimension | Count | Notes |
|---|---:|---|
| Sources | 2 085 | 1 504 parsed, 581 skipped (binaries, assets, unknown encodings) |
| Entities | 25 436 | `macro` 14 132, `function` 7 913, `module` 1 443, `parameter` 878, `heading` 423, `flag` 364, `class` 184, `make_target` 99 |
| Relations | 25 442 | `defines` 25 013, `contains` 423, `doc_mentions_entity` 6 |

The 98 %-`defines` skew is the direct fingerprint of the regex backend's limits: it can locate symbol definitions reliably but cannot emit `calls`/`reads`/`writes`/`checks_condition` with high precision, so it omits them. Concretely, what NVDLA loses without `code_graph`:

- Caller/callee questions ("which functions invoke `dla_enable_operation`?") — not generatable.
- Dataflow questions ("where is `roi_array_addr` written before it's read?") — not generatable.
- Guard / condition questions at scale — possible only for the handful of cases where the regex `checks_condition` heuristic fires, which today is zero on NVDLA.

What NVDLA retains with `regex_parser`:

- Doc-side fact questions (over `doc_heading_parser` entities).
- Symbol-location and "what's in this directory" questions (over `defines`/`contains` plus `source_inventory.jsonl`).
- Build/CLI questions (over `regex_make_parser` and `regex_cli_flag_parser` entities).
- Macro and parameter lookup (over `regex_hdl_parser` and `regex_c_family_parser` extractors).

The NVDLA generation profile records the gap as a `known_limits` entry: "CodeGraph was unavailable in the analyzer bundle, so call/callee and dataflow-heavy questions are down-weighted." This is the v1.0 escape hatch for downstream tools to know they are running on the weaker backend.

A future NVDLA bundle produced with `code_graph` enabled should populate `calls`, `reads`, `writes`, and `checks_condition` non-trivially, allowing the generator to honor `mechanism_trace` capability seeds with structural evidence rather than the text-quote evidence used today.

### 3.4 Bundle validator (`validate_context_bundle.py`)

Deterministic, dependency-free. Verifies:

- Presence of the five required bundle files.
- `project_manifest.json` has `schema_version == project-manifest/v1`, non-empty `source_sets`, unique source-set ids, boolean `available`.
- Each source inventory row has all 14 required fields; modality and `parse_status` against standard sets (warn-only for non-standard); duplicate `source_id` is a hard fail; `source_set_id` not in manifest is a hard fail; line/size are non-negative integers; existence of the source path on disk is a warning, not a fail.
- Each entity row has all required fields; `source_id` resolves into the source inventory; line ranges are non-negative and `line_end >= line_start`; `confidence ∈ [0,1]`.
- Each relation row has well-formed `subject`/`object` endpoints; non-empty `evidence`; `source_id` in each evidence anchor resolves into inventory.

Output: `FAIL` and `WARN` findings with file/line/item_id locations. CLI flag `--fail-on-warn` raises warnings to exit-non-zero (used in CI).

---

## 4. Generator (`benchmark-generator`)

### 4.1 Design

The generator consumes the analyzer bundle and a profile, then emits benchmark cases. It must not re-scan source repos for discovery — all source/entity/relation facts come from the bundle.

Inputs:
- `project_context_bundle/` (the analyzer's outputs).
- `generation_profile.yaml` — declares benchmark id, output name, target case count, per-project counts, per-layer counts, capability seeds, sampling style mix, answer-policy hints.

Outputs:
- `benchmark.jsonl` — one row per case, matching `benchmark-row/v1`.
- `benchmark_metadata.json` — benchmark-level metadata: id, generator version, context bundle path, source snapshots (re-copied from manifest for self-containment), per-axis counts, lint summary.
- `generation_report.md` — sampling strategy, capability expansion, rejected candidate classes, lint status, known limits.

### 4.2 Capability seeds and expansion

The profile declares seed capabilities (e.g. `mechanism_trace`, `doc_code_cross_check`, `repo_structure_location`). Each seed has an `expanded_from` description and may declare `graph_patterns` (triples over the relation graph: `["entity", "checks_condition|writes|calls", "entity"]`).

Recommended generator flow:
1. Read `analyzer_report.md` and graph distributions.
2. Start from profile capability seeds.
3. Expand or split capabilities when the actual graph shows meaningful project-specific structure (e.g., `mechanism_trace` → `bdma_zero_transfer`, `dependency_update`, `event_handling`, `isr_mapping`).
4. Record expanded capability coverage in `generation_report.md`.
5. Stamp `capability` in the JSONL rows.

### 4.3 Row contract

The required row shape is the v1 schema (§2.3). Roles and conventions:

- `case_id` — pattern declared in profile (`{project}-v1-{layer}-{seq:03d}`).
- `layer` — `{code: L1|L2|L3, zh: …}`. L1 = single-source retrieval; L2 = cross-source verification; L3 = multi-hop mechanism.
- `query` — realistic user-style question. Mixed Chinese/English allowed when natural.
- `query_rewrite` — normalized information need; allowed to remove filler and normalize yes/no phrasing; forbidden to introduce technical entities absent from the query, retrieved facts, answer conclusions, or hidden construction notes.
- `answer_type` — one of `yes_no`, `mechanism`, `fact_check`, `comparison`, `location`, `procedure`, `negative`, `synthesis`. Each has a fixed Chinese label.
- `references` — broader retrieval targets (≥ 1). Each must include `source_id` or `path`; `repo_name`/`source_type`/`authority` recommended.
- `evidence` — minimal answer-grounding spans (≥ 1). Each requires `evidence_id`, `source_id`, `path`, `role`, `statement`, plus `lines` when the source has a line concept. Evidence ids must be unique within a row.
- `expected_answer` — human-readable direct reference answer with `path:line` citations when the query asks for them. The first sentence answers the target unknown directly. Rubric-like language (e.g. "应说明...") is explicitly forbidden.
- `answer_rubric` — structured decomposition: `answer_goal`, `required_atoms` (≥ 1, ≥ 1 with role `conclusion`), optional `forbidden_atoms`, optional `citation_policy`.
- `capability`, `tags` — optional.

### 4.4 Atom model

An atom is the smallest independently scoreable proposition. Each required atom carries `id`, `role`, `statement`, `match_type`, `evidence_ids`, `weight` (positive), and optional `depends_on`. The lint-enforced atom roles and match types are:

```
roles:        conclusion, evidence_fact, reasoning, boundary, location, procedure_step, comparison_point
match_types:  semantic_yes_no, semantic_fact, semantic_reasoning, path_or_symbol,
              numeric_or_version, list_set, semantic_contradiction
```

Forbidden atoms carry `id`, `statement`, optional `match_type`, `severity` (default `fatal`).

Citation policy: `required ∈ {always, never, when_query_requests_evidence}`; `acceptable_granularity ∈ {path_line, path_only, source_only}`; optional `required_evidence_ids`.

### 4.5 Lint (`lint_benchmark_jsonl.py`)

457 lines. Lint-mode checks (FAIL vs. WARN):

Hard failures (FAIL):
- Schema-level: invalid JSONL, missing required v1 fields, duplicate `case_id`, label objects malformed, empty `references`/`evidence`/`required_atoms`.
- Evidence: duplicate `evidence_id`, malformed `lines` (must match `N` or `N-M`), missing required evidence fields.
- Rubric: atom referencing unknown evidence id, no `conclusion` atom, weight ≤ 0, non-standard `role`/`match_type` (WARN currently, see below), missing atom fields.
- `expected_answer` is rubric-like (matches forbidden patterns "应说明…" / "答案需要…" / "检索并串联…").
- Citation required by query but no `path:line` citation in `expected_answer`.

Warnings (WARN):
- Reference/evidence path missing on local disk.
- Reference path not covered by `references` (evidence path leak).
- `query_rewrite` duplicates a chatty query (matches `CHATTY_QUERY_PATTERNS`: 帮我, 我想, 到底, 顺便, …).
- `query_rewrite` introduces a technical token absent from `query`.
- Non-standard `answer_type.code`, atom `role`, or `match_type`.
- `expected_answer` shorter than ~20 chars.
- `yes_no` expected_answer doesn't begin with a yes/no equivalent.

Hidden-context markers banned in `query_rewrite`:
```
验证假设, 检索并回答, 优先参考实体, 范围约束, 需要定位触发条件,
状态/数据更新, 后续调用或消费关系, 不能只做符号定位, 回答应服务后续推理
```

CLI: `lint_benchmark_jsonl.py <benchmark.jsonl> [--repo-root .] [--fail-on-warn] [--json-report .json]`.

### 4.6 NVDLA generation output

- 50 cases, layer distribution `L1=19, L2=24, L3=7`.
- Answer types: `mechanism=13, fact_check=12, yes_no=12, procedure=5, synthesis=3, comparison=3, location=2`.
- Capabilities: `software_stack_path=20, mechanism_trace=18, doc_code_cross_check=6, build_sim_verif_flow=3, rtl_symbol_location=2, repo_structure_location=1`.
- Lint: `FAIL=0, WARN=0` with `--fail-on-warn`.

Vortex is the same shape, 50 cases.

---

## 5. Validator (`benchmark-validator`)

Single Python script with two subcommands: `lint` and `evaluate`.

### 5.1 `lint` mode — design and implementation

Design intent: deterministic audit of benchmark data quality before any system is run against it.

Inputs:
- Required: `benchmark.jsonl`.
- Recommended: `project_context_bundle/` (so references/evidence paths can be cross-checked against `source_inventory.jsonl`), `benchmark_metadata.json`.

Checks (hard failures unless marked W):
- All checks listed in §4.5 plus:
- Evidence path **must exist** in the source inventory when bundle is provided (otherwise W when bundle absent).
- Line range outside the known `line_count` of the inventoried source (FAIL).
- `references` and `evidence` paths cross-referenced against `source_inventory.jsonl`.
- Sampled-cases section samples diverse rows across project/layer/capability for human review, preferring rows with findings first.

Report shape (Markdown):

```
Verdict
Summary counts
Coverage by project/layer/capability/answer_type
Findings (FAIL then WARN, with file:line:case_id)
Sampled cases with query, references, evidence, snippets
Next actions
```

JSON report mirrors the same content for CI consumption.

### 5.2 `evaluate` mode — design

Scores a knowledge-system run against benchmark rows.

Inputs:
- Benchmark JSONL.
- Run results JSONL (one row per case). Run row required fields: `case_id`, `answer`. Optional/aliased: `retrieved_contexts` (or `retrieved`/`contexts`), `evidence`, `baseline`, `model`, `prompt_chars`, `token_usage`.
- Optional: project context bundle.

Three independent measurements:

**Retrieval.** Reference recall and evidence recall, computed against the run's retrieved contexts.
```
reference_recall@k = matched references / total references
evidence_recall@k  = matched evidence spans / total evidence spans
```
A reference matches when a retrieved context has the same `source_id` or `path`. An evidence span matches when source/path match AND line ranges overlap (or either side has no line range).

**Citation.** Triggered only when `citation_policy.required == always`, or `when_query_requests_evidence` and the query contains a citation trigger (`证据, 行号, 引用, cite, line, proof, …`). Granularity values `path_line | path_only | source_only` drive what must appear in the predicted answer.

**Answer atom scoring** (lexical heuristic — explicitly labeled as triage, not definitive):
- For each required atom: `lexical_match(statement, answer)` with default threshold 0.35. Code tokens (symbols/paths) must overlap strongly; Chinese text is compared as character bigrams.
- `atom_coverage = matched_weight / total_weight`.
- `conclusion_atoms_matched` = all atoms with `role == conclusion` are matched.
- `fatal_forbidden_matched` = any forbidden atom with `severity == fatal` matches at threshold 0.65.

**Case verdict** (default thresholds):
```
retrieval_pass       = evidence_recall@k == 1.0
answer_pass_heuristic= conclusion_atoms_matched
                        AND atom_coverage >= answer_threshold (default 0.5)
                        AND NOT fatal_forbidden_matched
citation_pass        = citation_policy not triggered, OR triggered checks pass

PASS  iff retrieval_pass AND answer_pass_heuristic AND citation_pass
FAIL  iff evidence_recall@k == 0 OR fatal_forbidden_matched
WARN  otherwise
```

### 5.3 Implementation notes

`skills/benchmark-validator/scripts/validate_benchmark.py` is 970 lines, single-file, dependency-free. Notable functions:

- `score_atoms(row, answer, lexical_threshold=0.35)` — returns `(coverage, conclusions_ok, fatal_forbidden, atom_matches)`.
- `answer_citation_pass(row, answer)` — parses `path:line` tokens in the candidate answer, matches against required evidence ids, honors granularity.
- `lexical_match` — significant-token overlap; for Chinese, character bigrams.
- `selected_samples` — diversifies sampled cases by `(project, layer, capability)`, prioritizes rows with findings.

The script is the only piece of v1.0 that does *answer scoring* without an LLM. The README and contracts explicitly state: **treat lexical atom scores as triage unless connected to a semantic judge** (which lives in `scripts/evaluate_methods.py`, §7).

---

## 6. Baselines (`scripts/run_codex_baselines.py`)

### 6.1 Design

Two baseline predictors used to bracket the difficulty of the benchmark and stress-test the evaluator. Both are invoked via Codex.

**Oracle baseline.** The agent receives the *gold evidence* for the case (path, lines, statement, optionally the file snippet) and must answer using only that evidence. This produces an upper bound on answer quality if retrieval were perfect.

**Grep-agent baseline.** The agent receives only repository roots and may use a restricted shell (`rg`, `sed -n`, `head`, `tail`, `wc`, optionally `nl -ba`) to inspect them. This produces a lower bound: how well does a simple retrieve-by-grep agent do?

Both baselines emit JSONL matching `baseline-prediction/v1`: `case_id`, `pred_answer`, `evidence` (rank-ordered).

### 6.2 Implementation

`scripts/run_codex_baselines.py`, 493 lines, two subcommands.

Common flags: `benchmark` (path), `--output`, `--repo-root`, `--model`, `--limit`, `--case-id` (repeatable), `--resume`, `--dry-run-prompts-dir`, `--schema`.

**Oracle** subcommand: `--snippet-context N` to add N lines of context around each gold evidence range.

**Grep-agent** subcommand: `--repo-path` (repeatable, required), `--allow-nl` (allow `nl -ba` for line-numbered inspection).

Prompts are deliberately terse (see `build_oracle_prompt`, `build_grep_agent_prompt`). The oracle prompt forbids external knowledge and citations not supported by the evidence. The grep-agent prompt forbids reading gold evidence, expected answer, rubric, metadata, or validation reports, and confines the agent to the listed shell commands.

Each prediction row records Codex token usage (`token_usage`) extracted from the `--json` event stream, which makes per-method cost reporting possible downstream.

`--resume` makes the runner idempotent: rows whose `case_id` already exists in the output JSONL are skipped, so cancelled runs can be continued in place.

### 6.3 Current artifacts (`predictions/`)

Both projects have oracle and grep-agent predictions, plus evaluator outputs:

```
nvdla_baseline_oracle_codex_predictions.jsonl
nvdla_baseline_grep_agent_predictions.jsonl
nvdla_baseline_oracle_eval.deepseek.{json,md}            # judged
nvdla_baseline_grep_eval.deepseek.{json,md}              # judged
nvdla_baseline_grep_agent_eval_no_judge.{json,md}        # heuristic-only
nvdla_baseline_oracle_codex_eval_no_judge.{json,md}      # heuristic-only
vortex_baseline_oracle_codex_predictions.jsonl
vortex_baseline_grep_agent_predictions.jsonl
vortex_baseline_oracle_codex_eval_no_judge.{json,md}
vortex_baseline_grep_agent_eval_no_judge.{json,md}
vortex_grep_parts/                                       # partial outputs
```

Headline (NVDLA, DeepSeek judge):

| Baseline | Strict E2E pass | Retrieval pass | Citation pass | Mean judge score |
|---|---:|---:|---:|---:|
| Oracle | 0.860 | 1.000 | 1.000 | 0.949 |
| Grep-agent | 0.820 | 0.980 | 0.960 | 0.940 |

The narrow gap between oracle and grep-agent (4 percentage points) is direct evidence that today's queries do not require deep search — a finding that motivates the v1.1 difficulty model.

---

## 7. Method evaluator (`scripts/evaluate_methods.py`)

### 7.1 Design

The headline evaluator. Distinct from the validator's `evaluate` mode in that it supports a **provider-backed LLM judge** for answer semantics while keeping retrieval and citation scoring deterministic.

The split mirrors the toolkit's overall philosophy: retrieval quality is path/line overlap (cheap, reproducible, runs in CI without API access); answer correctness goes through a model judge with a structured prompt and a strict JSON response contract.

### 7.2 Implementation

917 lines, single-file. CLI:

```
evaluate_methods.py <benchmark.jsonl> <predictions.jsonl>
  --top-k 10
  --judge-threshold 0.8
  --llm-judge-provider {command|deepseek}
  --llm-judge-api-key-env DEEPSEEK_API_KEY
  --llm-judge-base-url https://api.deepseek.com
  --llm-judge-model deepseek-v4-pro
  --llm-judge-temperature 0.0
  --llm-judge-thinking {enabled|disabled}
  --llm-judge-reasoning-effort low|medium|high
  --judge-timeout 60
  --require-llm-judge
  --output-json runs/eval.json
  --output-md runs/eval.md
```

Key implementation details:

- **API key handling.** `--llm-judge-api-key-env` takes the *name* of an environment variable (e.g., `DEEPSEEK_API_KEY`). The script validates the env name format, never logs the secret, and never writes it into report outputs.
- **DeepSeek client.** Direct `urllib.request` POST to `<base_url>/chat/completions` with `response_format: {"type":"json_object"}`, optional `thinking` and `reasoning_effort` payloads. No `openai` SDK dependency.
- **Generic command judge.** `--llm-judge-command "<cmd>"` lets users plug any binary that reads JSON from stdin and prints `{score, verdict, rationale}` JSON.
- **Judge payload** (`build_judge_payload`): `case_id`, `query`, `expected_answer`, `pred_answer`, full `gold_evidence`, normalized `pred_evidence` (top 50), `answer_rubric`, plus a hard-coded `judge_instruction` string asking for semantic-only scoring with no retrieval/citation gymnastics.
- **Judge response normalization** (`parse_judge_response`, `normalize_verdict`): tolerates `correct|pass|yes|true → correct`, `partial|warn → partial`, `incorrect|fail|no|false → incorrect`, `not_run|error` preserved.

### 7.3 Per-case verdict logic

```
retrieval_pass = evidence_recall@k == 1.0
answer_pass    = judge.score != None
                  AND judge.score >= --judge-threshold (default 0.8)
                  AND judge.verdict == "correct"
citation_pass  = unchanged from §5.2
strict_e2e_pass = retrieval_pass AND answer_pass AND citation_pass
```

Reported aggregate metrics (`summarize`):

```
cases, missing_predictions,
retrieval_pass_rate, strict_e2e_pass_rate, answer_pass_rate, citation_pass_rate,
mean_reference_recall_at_k, mean_evidence_recall_at_k,
mean_evidence_precision_at_k, mean_evidence_f1_at_k,
llm_judge_coverage, mean_llm_judge_score,
llm_judge_verdict_counts, llm_judge_error_counts
```

Stratified slices (`by_slice`) report the same metrics by `layer`, `capability`, and `answer_type` — this is what produces the breakdowns shown in `predictions/*_eval.*.md`.

### 7.4 Operational notes

- The validator's `evaluate` mode and `evaluate_methods.py` overlap in retrieval / citation scoring. The toolkit's intent is: the validator is for *benchmark authors* doing quick triage on a draft run; `evaluate_methods.py` is for *method developers* producing the official numbers.
- `--require-llm-judge` makes missing/failed judge calls cause non-zero exit, suitable for CI gates.

---

## 8. Diagnostics (`scripts/verify_codex_token_usage.py`)

A small (314-line) diagnostic that runs one benchmark case through both the oracle and grep-agent prompts with Codex's `--json` event stream enabled, then compares token usage between the two formats Codex has emitted in practice (`token_count` event vs. `turn.completed.usage` event). It is **not** part of the formal evaluation path; it exists because Codex's usage accounting changed across versions and the toolkit needs to reconcile both shapes.

Outputs: `token_usage_verification.<sample>.json` and `.md`. Sample artifact lives at `runs/token_usage_verification.sample.json`.

---

## 9. Tests (`tests/`)

Three unittest files target the `scripts/` helpers:

- `test_evaluate_methods.py` — exercises retrieval scoring (path + line overlap), citation pass logic, judge response parsing/normalization, DeepSeek client argument validation, and report writer plumbing. Uses `urllib.request.urlopen` mocking and `tempfile` for isolation.
- `test_run_codex_baselines.py` — exercises prompt builders, evidence snippet reader, line-range parsing, Codex usage extraction, and prediction-row construction.
- `test_verify_codex_token_usage.py` — exercises usage-event counting and report formation.

The skills' own scripts (`validate_context_bundle.py`, `lint_benchmark_jsonl.py`, `validate_benchmark.py`) do not yet have a parallel unittest suite. Their primary "test" is the bundled self-test under `examples/chip-kb-v1/` (out of scope per project policy).

---

## 10. Operational flows

### 10.1 NVDLA (multi-source-set example)

Sources: `repo_sources/nvdla/{hw, sw, doc}`, three source sets with distinct authority (`primary_source`, `primary_source`, `documentation`) and branches (`nvdlav1`, `master`, `master`).

End-to-end run:

```
# 1. Analyzer
$benchmark-repo-analyzer
   Analyze repo_sources/nvdla/{hw,sw,doc} as project nvdla.
   Use CodeGraph for code structure when available.
   Write the analyzer bundle to runs/nvdla_context_bundle.
   Exclude .git, .omx, prebuilt binaries.
   Run the bundle validator before reporting completion.

# 2. Generator
$benchmark-generator
   Use runs/nvdla_context_bundle as the analyzer bundle.
   Create or use runs/nvdla_generation_profile.yaml for a 50-case NVDLA benchmark.
   Expand capability seeds from analyzer_report.md and relation_graph.jsonl.
   Generate runs/nvdla_benchmark_v1.jsonl, metadata, generation report.
   Run the generator lint before reporting completion.

# 3. Validator (lint)
$benchmark-validator
   Lint runs/nvdla_benchmark_v1.jsonl using context bundle runs/nvdla_context_bundle.
   Select 10 diverse sample cases for the report.
   Write runs/nvdla_validation_report.{md,json}.

# 4. Baselines
python3 scripts/run_codex_baselines.py oracle \
   runs/nvdla_benchmark_v1.jsonl \
   --output predictions/nvdla_baseline_oracle_codex_predictions.jsonl \
   --repo-root .
python3 scripts/run_codex_baselines.py grep-agent \
   runs/nvdla_benchmark_v1.jsonl \
   --output predictions/nvdla_baseline_grep_agent_predictions.jsonl \
   --repo-root . --repo-path repo_sources/nvdla --allow-nl

# 5. Method evaluation with DeepSeek judge
export DEEPSEEK_API_KEY=...
python3 scripts/evaluate_methods.py \
   runs/nvdla_benchmark_v1.jsonl \
   predictions/nvdla_baseline_oracle_codex_predictions.jsonl \
   --top-k 10 \
   --llm-judge-provider deepseek \
   --llm-judge-model deepseek-v4-pro \
   --llm-judge-api-key-env DEEPSEEK_API_KEY \
   --output-json runs/nvdla_method_eval.deepseek.json \
   --output-md  runs/nvdla_method_eval.deepseek.md
```

### 10.2 Vortex (single-source example)

Same flow as NVDLA but with a single source set (`vortex_main`, `repo_sources/vortex/vortex`, `main_code_doc_repo`, `primary_source`). The benchmark is 50 cases at `L1=24, L2=21, L3=5` (approx); reference counts are higher than NVDLA's because the Vortex generator produced more cross-source cases.

### 10.3 Convention: snapshot reproducibility

The `project_manifest.json` records commit hashes for each source set. Re-running the analyzer on the same commits should produce bit-identical entity/relation rows (modulo timestamp differences in `project_manifest.created_at`), because the regex extractors are deterministic. CodeGraph-backed runs do not yet have this guarantee.

The `benchmark_metadata.json` re-records the same source snapshots, making each `benchmark.jsonl` self-contained even without the analyzer bundle alongside.

---

## 11. Known limitations of v1.0

These are not bugs; they are conscious scope cuts. Each motivates a v1.1 item or a future deferred decision.

### 11.1 Difficulty is structural, not enforced

The current `layer` axis encodes retrieval breadth but the lint **does not enforce** that L2 cases span ≥ 2 source ids or that L3 cases form a chain. NVDLA inspection shows all 50 cases have exactly 1 reference path, including the 24 labeled L2 and 7 labeled L3. The labels are aspirational; the evidence does not honor them.

### 11.2 Capability is descriptive, not enforced

The `capability` field names the *kind* of question (e.g., `doc_code_cross_check`) but is never enforced. The 6 NVDLA cases tagged `doc_code_cross_check` all cite only `.rst`/`.md` evidence — they perform doc fact lookup, not doc-vs-code reconciliation.

### 11.3 No adversarial gate

The lint is structural only. There is no per-case probe that asks "does this case actually require deep search, or can a single grep solve it?" The narrow 4-point oracle-vs-grep gap reported in §6.3 quantifies the impact.

### 11.4 No unanswerable cases

Schema requires `references.minItems >= 1` and `evidence.minItems >= 1` on every row. There is no representation for "the answer is: this snapshot does not contain that information." Predictions cannot be scored for appropriate refusal.

### 11.5 No information-seeking efficiency metrics

The toolkit reports `evidence_recall@k`, `evidence_precision@k`, `evidence_f1@k`, but not information-utilization metrics that catch over-retrieval (e.g., InfoDeepSeek's `EEU = max_k IA@k / ACC`, `IC = |pred_evidence@k| / |gold_evidence|`).

### 11.6 LLM judge is single-model, single-prompt

`evaluate_methods.py` calls one provider (DeepSeek) with one prompt template (`build_judge_payload`). There is no jury, no arbiter, no specialized prompt for false-premise / unanswerable cases. InfoDeepSeek's reported 95.57% → 99.29% gain from prompt-splitting is unrealized here.

### 11.7 CodeGraph fallback skew

When CodeGraph is unavailable, the regex-fallback relation graph is overwhelmingly `defines` (≈ 98% on NVDLA), with almost no `calls`/`reads`/`writes`/`checks_condition`. This bottlenecks the generator into doc-style and surface-symbol questions and explains why "mechanism-trace" cases in NVDLA fall back to literal evidence quotation rather than true control-flow tracing.

### 11.8 Single-pass generation, no second-look auditing

Generated cases are produced by the agent in one pass. There is no inter-annotator or second-judge verification step. The intent (per `references/query-answer-rubric.md` and `generator-contract.md`) is to lean on lint discipline for correctness. The cost is that subtle quality issues (capability/label drift in §11.1–§11.2) slip through.

### 11.9 Generator does not consume signal-level analyzer outputs

The analyzer emits source/entity/relation rows. The generator currently uses these as a coarse pool ("which files exist? which entities? which doc headings?") rather than driving sampling by structural signals (entity reference count, name collisions, doc-code alignment, branch density). Difficulty falls out implicitly rather than being steered.

### 11.10 Single-language target

All benchmark rows assume Chinese-with-English-tech-tokens phrasing. Localization to other annotation languages would require updating lint patterns (`CHATTY_QUERY_PATTERNS`, `RUBRIC_LIKE_PATTERNS`, `CITATION_TRIGGER_PATTERNS`, `QUERY_REWRITE_FORBIDDEN_PATTERNS`).

---

## 12. Glossary (v1.0)

| Term | Meaning |
|---|---|
| Project context bundle | The analyzer's output directory: manifest + inventory + entity index + relation graph + report |
| Source set | A named source root within a project (e.g., `nvdla_hw`, `nvdla_sw`, `nvdla_doc`) |
| Modality | Coarse content type (`code, doc, script, test, config, issue, release, binary, data, asset, unknown`) |
| Source type | Project-extensible subdivision of modality (e.g., `code.rtl`, `doc.source_rst`) |
| Authority | `primary_source | documentation | issue_derived_non_overriding | …` |
| Layer | Retrieval breadth (L1/L2/L3) |
| Capability | Descriptive question kind (`mechanism_trace`, `doc_code_cross_check`, …) |
| Evidence span | A `(source_id, path, lines, role, statement)` tuple used to ground the answer |
| Reference | A broader retrieval target list; superset of evidence |
| Atom | Smallest independently scoreable rubric proposition |
| Citation policy | Triggers under which the answer must include `path:line` citations |
| Strict E2E pass | `retrieval_pass AND answer_pass AND citation_pass` |
| Heuristic vs. judge | Validator uses lexical-bigram atom matching; method evaluator uses an LLM judge |
| Oracle baseline | Predicts using only gold evidence; upper-bound retrieval |
| Grep-agent baseline | Predicts using `rg/sed/head/tail/wc/nl` over repo roots; lower-bound retrieval |
