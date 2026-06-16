# CodeGraph Backend Guidance

CodeGraph is the preferred v1 code backend when it is available for the target repo.

Use it for:

- file and symbol discovery;
- function/method/class/module definitions;
- callers/callees and call relations;
- impact or neighborhood exploration when constructing relation candidates;
- code-oriented entity spans with line numbers.

Do not use CodeGraph for:

- replacing the analyzer bundle contract;
- parsing docs, issue exports, or release metadata;
- generating benchmark questions or answers.

## Backend Abstraction

Record the backend in generated rows:

```json
{
  "extractor": "code_graph",
  "confidence": 0.95
}
```

If fallback logic is used, make it explicit:

```json
{
  "extractor": "code_graph+ripgrep_fallback",
  "confidence": 0.72
}
```

Recommended analyzer request shape:

```yaml
analysis_backends:
  code:
    primary: code_graph
    fallbacks: [ripgrep, tree_sitter, lsp]
```

## Relation Mapping

Map structural facts into standard predicates where possible:

| CodeGraph fact | Analyzer relation |
|---|---|
| symbol definition | `defines` |
| caller/callee edge | `calls` |
| file containment | `contains` |
| import/include edge | `imports_or_includes` |
| condition check found around symbol | `checks_condition` |
| assignment/write | `writes` |
| read/reference | `reads` |

When no standard predicate fits, use a project predicate and document it in `analyzer_report.md`.
