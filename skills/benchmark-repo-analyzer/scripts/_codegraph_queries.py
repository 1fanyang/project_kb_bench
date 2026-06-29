"""SQL query strings against CodeGraph's SQLite schema (frozen contract).

Schema source of truth:
    skills/benchmark-repo-analyzer/references/codegraph_schema.md
    (a copy of runs/feasibility_v2_analyzer/codegraph_schema.md from
    Phase 0 Task 6, dumped against CodeGraph v1.1.1 sha 4077ed1).

Tables this module reads:
    nodes              code symbols (functions, classes, modules, ...)
    edges              source -> target relations (kind, metadata, line, col)
    files              tracked source files
    unresolved_refs    references that didn't resolve to a node id; some
                       become relation evidence in the bundle (e.g. a
                       Verilog instantiation whose target module isn't
                       in the index yet)
    project_metadata   indexed_with_version, indexed_with_extraction_version

Tables this module does NOT touch:
    schema_versions    CodeGraph's own DDL versioning
    nodes_fts*         FTS5 virtual tables (search index, not source data)

Convention: every query is a module constant. The only Python-side
templating is parameter binding (`?` placeholders). Do not concatenate
user input into these strings.
"""
from __future__ import annotations

FILES_QUERY = """
SELECT path, content_hash, language, size, modified_at,
       indexed_at, node_count, errors
FROM files
ORDER BY path
"""

# Note: nodes.id is text like "class:abc123..." / "method:def456...".
# language is denormalized onto each node; the verilog-module remap in
# the entity exporter keys on (language='verilog' AND kind='class').
ENTITIES_QUERY = """
SELECT id, kind, name, qualified_name, file_path, language,
       start_line, end_line, start_column, end_column,
       docstring, signature, visibility, is_exported,
       is_async, is_static, is_abstract,
       decorators, type_parameters, return_type, updated_at
FROM nodes
ORDER BY id
"""

# edges.source and edges.target are text node ids (FK to nodes.id).
# The exporter joins back to nodes for file-path / name resolution
# rather than complicating the SQL here.
RELATIONS_QUERY = """
SELECT id, kind, source, target, metadata, line, col, provenance
FROM edges
ORDER BY id
"""

# Unresolved references — some (notably Verilog instantiations whose target
# module isn't in the indexed file set, and `include "foo.svh"` whose
# include file falls outside repo_sources/) end up as relation evidence
# in the bundle even though no edge could be drawn. The exporter emits
# these as relations with object.id="" plus a `resolution_status:
# "unresolved"` flag in evidence.
UNRESOLVED_REFS_QUERY = """
SELECT id, from_node_id, reference_name, reference_kind,
       line, col, candidates, file_path, language
FROM unresolved_refs
ORDER BY id
"""

# Two well-known keys live here: indexed_with_version (the CodeGraph
# package version that wrote the DB) and indexed_with_extraction_version
# (the extractor-protocol version, bumped when LanguageExtractor changes).
# Used by the manifest emitter.
PROJECT_METADATA_QUERY = """
SELECT key, value, updated_at
FROM project_metadata
ORDER BY key
"""

# Convenience: count rows per table for the analyzer_report.md summary
# and for the manifest's `counts` field. Keep this in lockstep with the
# tables the exporter actually reads.
COUNT_QUERIES = {
    "files": "SELECT COUNT(*) FROM files",
    "nodes": "SELECT COUNT(*) FROM nodes",
    "edges": "SELECT COUNT(*) FROM edges",
    "unresolved_refs": "SELECT COUNT(*) FROM unresolved_refs",
}
