# Generator Contract v1

The generator consumes analyzer output and writes benchmark cases. It should not rediscover the project structure by scanning the source repos directly.

## Inputs

Required:

```text
project_context_bundle/project_manifest.json
project_context_bundle/source_inventory.jsonl
project_context_bundle/entity_index.jsonl
project_context_bundle/relation_graph.jsonl
generation_profile.yaml
```

`generation_profile.yaml` is benchmark configuration. It may be authored manually or by an agent after reading the analyzer report.

Minimal profile shape:

```yaml
schema_version: generation-profile/v1
benchmark:
  id: chip_kb_v1
  output_name: benchmark.jsonl
  target_count: 100
  case_id_pattern: "{project}-v1-{layer_short}-{seq:03d}"
input:
  context_bundle: project_context_bundle
projects:
  - id: nvdla
    target_count: 50
layers:
  - code: L1
    zh: 单源检索
capability_seeds:
  - code: mechanism_trace
    zh: 机制链路解释
    graph_patterns:
      - ["entity", "checks_condition|writes|calls", "entity"]
sampling:
  query_style_mix:
    colloquial: 0.4
    contextual: 0.3
    fact_check: 0.2
    followup: 0.1
answer_policy:
  require_direct_answer_first: true
  citation_format: "`path:line-range`"
```

## Capability Seeds

Capabilities are project-related and should be expanded from analyzer output. The skill defines the seed mechanism, not a fixed taxonomy.

Recommended flow:

1. Read `analyzer_report.md` and graph distributions.
2. Start from profile `capability_seeds`.
3. Expand or split capabilities when the actual source/entity/relation graph shows meaningful project structure.
4. Record expanded capability coverage in `generation_report.md`.
5. Store `capability` in JSONL rows when it helps coverage analysis.

Example expansion:

```text
seed: mechanism_trace
expanded from graph: code_condition_branch, producer_consumer_state, script_to_runtime_flow
```

## Output Files

`benchmark.jsonl`: one benchmark case per line.

`benchmark_metadata.json`: shared metadata such as benchmark id, generator version, context bundle manifest path, and source snapshots.

`generation_report.md`: human-readable report with sampling strategy, capability expansion, rejected candidates, lint status, and known gaps.

## Row Schema

Required row fields:

| Field | Meaning |
|---|---|
| `case_id` | Unique case id. |
| `project` | Project id from analyzer manifest. |
| `layer` | Object with `code` and `zh`. |
| `query` | Realistic user-style question. |
| `query_rewrite` | Normalized information need based only on visible query semantics. |
| `answer_type` | Object with `code` and `zh`. |
| `references` | Retrieval validation source list, broader than evidence. |
| `evidence` | Minimal evidence spans needed to answer. |
| `expected_answer` | Direct evidence-grounded answer. |
| `answer_rubric` | Atomized answer scoring structure. |

Optional row fields:

| Field | Meaning |
|---|---|
| `capability` | Object with `code` and `zh`, generated from profile seeds plus analyzer graph. |
| `tags` | Short labels for reports and sampling audits. |

Do not emit `question`, `oracle`, per-row snapshot blobs, hidden `user_context`, or generation-only chain notes in v1 rows.

## Reference and Evidence

`references` validate retrieval. Each item should include at least `source_id` or `path`, plus `repo_name`, `source_type`, and `authority` when available from analyzer inventory.

`evidence` validates answer grounding. Each item requires:

```json
{
  "evidence_id": "E1",
  "source_id": "src:...",
  "path": "repo_sources/project/file.c",
  "lines": "12-24",
  "role": "trigger_condition",
  "statement": "This span states the condition or fact used in the answer."
}
```

Evidence id values must be unique within a row. Rubric atoms cite evidence by these ids.

## Generation Order

For each candidate case:

1. Choose project, layer, capability, answer type, and graph pattern.
2. Select retrieval references from source inventory and relation graph.
3. Select minimal evidence spans.
4. Define the target unknown.
5. Write natural `query`.
6. Write `query_rewrite` only from visible query semantics.
7. Write direct `expected_answer` with citations when required.
8. Decompose the expected answer into rubric atoms.
9. Lint the row; repair or reject failures.

Prefer rejecting weak candidates over padding the benchmark.
