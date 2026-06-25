# v1.1 Corpus Generation Pipeline

This document explains the deterministic generation flow implemented in
`scripts/generate_v1_1_release_corpora.py`.

The script does not call an LLM and does not load external prompt files. It is a
template-based generator: it reads analyzer artifacts from a project context
bundle, selects real source/signal anchors, and deterministically writes
benchmark rows with `query`, `query_rewrite`, `expected_answer`, `evidence`, and
`answer_rubric`.

## Inputs

For each project, the generator reads:

- `runs/{project}_context_bundle/source_inventory.jsonl`
- `runs/{project}_context_bundle/signal_index.jsonl`
- `runs/{project}_generation_profile_v1_1.yaml`

The CLI entry point supports:

```bash
uv run python scripts/generate_v1_1_release_corpora.py \
  --repo-root . \
  --output-dir runs \
  --project all
```

`--project` can be `nvdla`, `vortex`, or `all`.

## Fixed Quotas

The script uses fixed release quotas.

Answerability:

- `unanswerable_missing_evidence`: 30
- `answerable`: 140
- `unanswerable_false_premise`: 20
- `unanswerable_ambiguous`: 10

Layer:

- `L1`: 50
- `L2`: 90
- `L3`: 60

`validate_profile()` checks that the generation profile agrees with these fixed
counts before generation proceeds. For Vortex, the script also requires
`version_fork` to remain disabled.

## Source Filtering

`load_sources()` reads `source_inventory.jsonl` and keeps only usable generation
sources.

A source is admitted only when:

- the row belongs to the requested project;
- `source_id` is present;
- `path` is a string;
- `line_count` is a positive integer;
- the referenced file exists under `--repo-root`;
- `source_type` is not `binary.*`;
- the path is not a low-quality artifact path.

Low-quality path markers are filtered out:

- `external`
- `third_party`
- `gtest`
- `golden`
- `protobuf`
- `vendor`
- `node_modules`
- `traces/traceplayer`

Low-quality suffixes are also filtered out:

- `.a`
- `.dat`
- `.dimg`
- `.gif`
- `.jpeg`
- `.jpg`
- `.md5`
- `.o`
- `.pdf`
- `.png`
- `.so`

This prevents release questions from being anchored on generated artifacts,
vendor code, regression golden files, binary blobs, or external dependencies.

## Signal Loading

`load_signals()` reads `signal_index.jsonl` and keeps only signals whose anchors
survive source filtering.

A signal is admitted only when:

- `project` matches;
- `anchor.source_id` exists in the admitted source map;
- `anchor.path` exactly matches the admitted source path;
- `signal_id` and `attribute` are strings;
- `axis` is either `2` or `3`.

The generator deduplicates by `(attribute, source_id)` and sorts signals by
`path` and `signal_id`. This makes row generation deterministic.

## Difficulty Attribute Selection

For L2/L3 rows, the generator prefers these attribute pairs:

- `long_tail` + `implicit_domain_knowledge`
- `distracting_info` + `conditional_behavior`
- `non_code_anchor` + `implicit_domain_knowledge`
- `long_tail` + `doc_code_divergence`
- `distracting_info` + `implicit_domain_knowledge`
- `long_tail` + `conditional_behavior`

If a preferred pair is unavailable, the script falls back to any available
axis-2 attribute plus any available axis-3 attribute.

L1 selection is stricter: it chooses axis-2 and axis-3 signals from the same
source and excludes `conditional_behavior`.

L2/L3 selection ensures at least two source IDs when possible. L3 additionally
tries to add a third axis-3 signal from a new source to support a multi-hop
atom chain.

## Evidence Construction

`make_evidence()` converts selected signals into evidence rows.

Rules:

- L1 keeps only the first selected signal.
- L2 and L3 keep all selected signals.
- Each evidence span uses up to a three-line window beginning at the signal
  anchor.
- Snippets are whitespace-normalized and truncated to 180 characters.
- `conditional_behavior` evidence gets role `trigger_condition`.
- `doc_code_divergence` evidence gets role `comparison_point`.
- Other evidence gets role `evidence_fact`.

Evidence keeps exact `path` and `lines`. This is intentional: evidence and
expected answers are evaluation artifacts. The user-facing `query` should not
expose these target files by default.

## Topic Derivation

The generator turns evidence paths into user-facing topics before writing
queries.

Examples of specific filename mappings:

- `LowPrecision.md` -> `低精度支持`
- `CompilerFeatures.md` -> `编译器功能`
- `VX_afu_ctrl` -> `AFU 控制逻辑`
- `VX_afu_wrap` -> `AFU 封装逻辑`

Directory context mappings include:

- `hw` -> `硬件设计`
- `rtl` -> `RTL`
- `sw` -> `软件栈`
- `verif` -> `验证`
- `runtime` -> `运行时`
- `xrt` -> `XRT 集成`

If no explicit mapping exists, the filename stem is split into readable tokens
and suffixed with `相关逻辑`.

Only the first evidence topic is used in the query. This keeps L2/L3 questions
from becoming long lists of internal files or multiple low-level symbols.

## Query Template Rules

The script uses deterministic templates rather than LLM prompts.

### Missing Evidence

Missing-evidence rows do not include `references` or `evidence`.

The scenario is selected from `MISSING_SCENARIOS`, then inserted into:

```text
{PROJECT} 中能确认 {scenario}吗？我没有看到可核验证据。
```

`query_rewrite` becomes:

```text
判断 {PROJECT} 中是否有证据支持“{scenario}”。
```

The expected answer must refuse to fabricate and explain that current evidence
is insufficient.

### Answerable L1

L1 asks for a single-source evidence conclusion without naming the target file.

Templates:

```text
{PROJECT_TOPIC} 能确认什么行为或结论？请给证据。
我想核对 {PROJECT_TOPIC}，当前证据支持什么结论？
```

### Answerable L2

L2 asks for cross-source corroboration without naming the target files.

Templates:

```text
{PROJECT_TOPIC} 的两类线索是否能互相印证？请给证据。
围绕 {PROJECT_TOPIC}，跨来源证据合起来说明了什么？
```

### Answerable L3

L3 asks for a mechanism chain or execution logic.

Templates:

```text
{PROJECT_TOPIC} 的机制链路是什么？请按证据说明。
如果追踪 {PROJECT_TOPIC}，这些线索合起来说明了怎样的执行逻辑？
```

### False Premise

False-premise rows assert a wrong claim and require the answer to reject it.

Template:

```text
有人说 {PROJECT_TOPIC}没有提供任何可用信息，这个说法对吗？请给证据。
```

The expected answer starts with a rejection such as `不支持这个说法`, then cites
the evidence.

### Ambiguous

Ambiguous rows ask whether the evidence is enough to disambiguate a version or
execution path.

Template:

```text
{PROJECT_TOPIC}这条线索能直接判断具体版本或执行路径吗？请说明能确认什么、不能确认什么。
```

The expected answer must state the limited conclusion and explain that the
evidence cannot fully resolve the ambiguity.

## Answer and Rubric Construction

`expected_answer` preserves exact `path:line` citations because it is the
evaluation target, not the user query.

`answer_rubric` contains:

- `answer_goal`: fixed as `回答用户提出的可核验证据需求。`
- `required_atoms`
- `forbidden_atoms`
- `citation_policy`

Required atom rules:

- Missing-evidence rows get one conclusion atom with no `evidence_ids`.
- Answerable, false-premise, and ambiguous rows get one atom per evidence item.
- The first evidence atom is the conclusion.
- For L3, later atoms are `reasoning` atoms with `depends_on` links, creating a
  chain.

Forbidden atom rules:

- `unanswerable_false_premise`, `yes_no`, and `fact_check` rows get a fatal
  contradiction forbidden atom.
- Other rows do not get forbidden atoms by default.

Citation policy:

- Missing-evidence rows: `required = never`
- Other rows: `required = always`, `acceptable_granularity = path_line`

## Row Assembly

`make_row()` assembles the final JSONL row:

- `case_id`
- `project`
- `layer`
- `capability`
- `query`
- `query_rewrite`
- `answer_type`
- `answerability`
- `difficulty`
- `references`
- `evidence`
- `expected_answer`
- `answer_rubric`
- `tags`

`tags` include `v1_1_release` and the capability code. Non-answerable rows also
include their answerability tag. The generator no longer adds
`file_anchor_required` by default.

## Output Artifacts

For each project, `write_project_outputs()` writes:

- `runs/{project}_benchmark_v1_1.jsonl`
- `runs/{project}_benchmark_v1_1.rejected.jsonl`
- `runs/{project}_benchmark_v1_1.metadata.json`
- `runs/{project}_generation_report_v1_1.md`

The rejected file is currently empty because this deterministic release pass
only emits candidates that the script expects to be structurally valid.

## Post-Generation Validation

This generator does not run validator checks by itself. After generation, run
the v1.1 validator:

```bash
uv run python skills/benchmark-validator/scripts/validate_benchmark.py lint \
  runs/nvdla_benchmark_v1_1.jsonl \
  --context-bundle runs/nvdla_context_bundle \
  --repo-root . \
  --schema-version v1.1 \
  --structural-gate-json runs/nvdla_benchmark_v1_1.structural_gate.json
```

Repeat for Vortex with the corresponding benchmark and context bundle.

The validator is responsible for enforcing structural quality gates, including
the corpus-level file-anchor ratio limit.
