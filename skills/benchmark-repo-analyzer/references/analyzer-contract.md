# Analyzer Contract v1

The analyzer owns project parsing. The generator owns benchmark case construction. Keep the boundary strict: downstream tools consume the analyzer artifacts and should not re-scan the original repository to discover basic source/entity/relationship facts.

## Input

The preferred input is a thin `analyzer_request.yaml` created by a human or agent:

```yaml
schema_version: analyzer-request/v1
project:
  id: nvdla
  display_name: NVDLA
source_roots:
  - id: nvdla_sw
    local_root: repo_sources/nvdla/sw
    repo_name: nvdla/sw
analysis_backends:
  code:
    primary: code_graph
    fallbacks: [ripgrep, tree_sitter, lsp]
include: ["**/*"]
exclude: ["**/.git/**"]
```

The request is not the shared downstream contract. The analyzer emits the shared project context bundle.

## Output Bundle

Required files:

```text
project_manifest.json
source_inventory.jsonl
entity_index.jsonl
relation_graph.jsonl
analyzer_report.md
```

Optional files:

```text
parse_diagnostics.jsonl
unresolved_sources.jsonl
graph_summary.json
signal_index.jsonl
```

## v1.1 optional file: signal_index.jsonl

`signal_index.jsonl` is optional for v1 bundles and recommended for v1.1 generation.
Each row records one analyzer-derived difficulty signal. The generator must use
this artifact for attribute-first sampling instead of rediscovering difficulty
from source files.

Required fields:

| Field | Meaning |
|---|---|
| `signal_id` | Stable signal id, unique inside the bundle. |
| `project` | Project id from manifest. |
| `axis` | Difficulty axis, currently `2` retrieval difficulty or `3` reasoning difficulty. |
| `attribute` | Difficulty attribute such as `long_tail` or `conditional_behavior`. |
| `anchor` | Entity or source anchor the signal applies to. |
| `evidence` | Extractor-specific evidence payload. |
| `extractor` | Tool or heuristic that produced the signal. |
| `confidence` | Number from `0.0` to `1.0`. |

## project_manifest.json

Generated bundle-level metadata. Store repo snapshot information once here instead of repeating it in every benchmark row.

Required fields:

| Field | Meaning |
|---|---|
| `schema_version` | Must be `project-manifest/v1`. |
| `project.id` | Stable project identifier used by generated cases. |
| `source_sets[]` | Source roots or imported source collections. |
| `created_at` | Bundle creation timestamp. |
| `analyzer_version` | Analyzer implementation or skill version. |

Each `source_sets[]` item requires:

| Field | Meaning |
|---|---|
| `id` | Stable source-set id. |
| `repo_name` | Human-readable repo or source collection name. |
| `local_root` | Local path used during analysis. |
| `source_role` | Project-specific role such as `main_code_repo`, `doc_snapshot`, or `issue_export`. |
| `authority` | Source authority, for example `primary_source`, `documentation`, `issue_derived_non_overriding`. |
| `available` | Boolean availability flag. |

Recommended optional fields: `branch`, `commit`, `snapshot_id`, `content_hash`, `warnings`.

## source_inventory.jsonl

One JSON object per source file, doc page, issue record, release record, or other retrievable source.

Required fields:

| Field | Meaning |
|---|---|
| `source_id` | Unique id, referenced by entities and relations. |
| `project` | Project id from manifest. |
| `source_set_id` | Source set id from manifest. |
| `repo_name` | Repo/source collection name. |
| `path` | Local path or stable exported path. |
| `relative_path` | Path relative to the source set root when available. |
| `modality` | Standard coarse modality. |
| `source_type` | Project-extensible source type. |
| `authority` | Authority level. |
| `language` | Language or format such as `python`, `cpp`, `markdown`, `json`. |
| `line_count` | Text line count; use `0` for non-text/binary sources. |
| `size_bytes` | Byte size if known. |
| `sha256` | Hex digest or `sha256:<hex>`. |
| `parse_status` | `parsed`, `partial`, `skipped`, or `failed`. |

Standard `modality` values:

```text
code doc script test config issue release binary data asset unknown
```

`source_type` remains project-extensible. Examples: `code.rtl`, `doc.readme`, `code.runtime`, `issue.troubleshooting`, `release.notes`.

## entity_index.jsonl

One JSON object per extracted entity. Entities should be concrete enough for generation and validation, not broad topic labels only.

Required fields:

| Field | Meaning |
|---|---|
| `entity_id` | Unique id. |
| `project` | Project id. |
| `source_id` | Source containing the entity. |
| `name` | Entity display name. |
| `kind` | Standard or project-extensible entity kind. |
| `path` | Local/stable path for the source span. |
| `line_start` | First line, 1-based. Use `0` if unavailable. |
| `line_end` | Last line, 1-based. Use `0` if unavailable. |
| `extractor` | Tool or heuristic that produced the entity. |
| `confidence` | Number from `0.0` to `1.0`. |

Common `kind` values:

```text
function method class module signal parameter macro struct enum type variable
doc_section heading claim term command flag env_var make_target config_key
test_case issue release artifact
```

Optional fields: `signature`, `parent_entity_id`, `namespace`, `aliases`, `normalized_name`, `domain_kind`, `summary`.

## relation_graph.jsonl

One JSON object per relation. Relations must be composable by id so generator can sample multi-hop cases without re-reading the whole repo.

Required fields:

| Field | Meaning |
|---|---|
| `relation_id` | Unique id. |
| `project` | Project id. |
| `subject` | Object with `type` plus `id` and/or `name`. |
| `predicate` | Relation predicate. |
| `object` | Object with `type` plus `id` and/or `name`. |
| `evidence` | Non-empty list of source anchors supporting the relation. |
| `extractor` | Tool or heuristic that produced the relation. |
| `confidence` | Number from `0.0` to `1.0`. |

Each relation evidence item requires:

| Field | Meaning |
|---|---|
| `source_id` | Source id from inventory. |
| `path` | Path for the supporting span. |
| `lines` | Line range such as `12` or `12-24`; optional only for line-less sources. |
| `summary` | Short fact supported by this span. |

Core predicates:

```text
defines contains calls imports_or_includes reads writes checks_condition
mentions documents doc_mentions_entity source_same_topic_as_source
script_invokes_target test_exercises_entity issue_mentions_entity
```

Project-specific predicates are allowed when the generator profile explains how to use them.

## analyzer_report.md

Human-facing report. Include:

- source sets and snapshot status;
- source count by modality, source type, and authority;
- entity count by kind and extractor;
- relation count by predicate and extractor;
- CodeGraph status when used;
- parse failures and low-confidence areas;
- example relation paths useful for multi-hop generation;
- recommended project-specific capability seeds for the generator profile.
