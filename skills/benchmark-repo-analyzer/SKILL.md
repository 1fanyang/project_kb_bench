---
name: benchmark-repo-analyzer
description: Use when preparing source repositories, documentation snapshots, issue exports, or release metadata for retrieval benchmark generation, especially when downstream benchmark cases need a standardized source inventory, entity index, and relation graph.
argument-hint: "<analyzer_request.yaml or source roots> -> <project_context_bundle>"
---

# Benchmark Repo Analyzer

## Boundary

Use this skill to turn target project sources into a reusable `project_context_bundle/`.

Do:
- read a thin `analyzer_request.yaml` or equivalent user-provided source-root list;
- inspect code, docs, scripts, configs, tests, issue exports, and release metadata;
- emit the five standard analyzer artifacts;
- validate the bundle before handing it to benchmark generation.

Do not:
- generate benchmark JSONL cases;
- write `query`, `expected_answer`, or scoring rubrics;
- hardcode project-specific taxonomies into this skill;
- require one orchestration mechanism. Codex, Claude, shell scripts, CI, or manual UI workflows may all connect the steps.

## Required Output

Write a directory containing:

```text
project_manifest.json
source_inventory.jsonl
entity_index.jsonl
relation_graph.jsonl
analyzer_report.md
```

Read `references/analyzer-contract.md` for field semantics. Read `references/codegraph-backend.md` when using CodeGraph for code analysis.

## Codex CLI Invocation

Invoke this skill from Codex CLI as a message, not as a shell command:

```text
$benchmark-repo-analyzer
Analyze repo_sources/nvdla/hw, repo_sources/nvdla/sw, and repo_sources/nvdla/doc as project nvdla.
Use CodeGraph for code structure when available.
Write the analyzer bundle to runs/nvdla_context_bundle with project_manifest.json, source_inventory.jsonl, entity_index.jsonl, relation_graph.jsonl, and analyzer_report.md.
Exclude .git, .omx, and prebuilt binaries.
Run the bundle validator before reporting completion.
```

```text
$benchmark-repo-analyzer
Analyze repo_sources/vortex/vortex as project vortex.
Use source role main_code_doc_repo and authority primary_source.
Write the analyzer bundle to runs/vortex_context_bundle.
Exclude .git, .omx, and hw/syn/synopsys/models.
Run the bundle validator before reporting completion.
```

## Validation

Run the deterministic bundle validator:

```bash
python3 skills/benchmark-repo-analyzer/scripts/validate_context_bundle.py \
  project_context_bundle \
  --repo-root .
```

Fix all `FAIL` findings before using the bundle with `benchmark-generator`.
