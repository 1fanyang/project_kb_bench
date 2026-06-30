# CodeGraph SQLite schema — frozen contract for the v2 bundle exporter

This file is the contract that
`skills/benchmark-repo-analyzer/scripts/codegraph_to_bundle.py` is written
against. The upstream CodeGraph schema may evolve; when it does, do not
silently update this file — re-pin the CodeGraph commit, re-dump the
schema (Phase 0 Task 6 procedure), diff against this file, and ship an
exporter update in the same PR.

- CodeGraph version pinned at: 1.1.1
- Commit sha (in our fork): `4077ed19b7d8a88eba93601c0c308e59c8640f8c`
- Fork branch: `feat/verilog-language-module` (adds Verilog WASM + extractor on top of v1.1.1)
- Phase 0 raw dump source: `runs/feasibility_v2_analyzer/codegraph_schema.md`

# CodeGraph SQLite schema

DB: `/Users/yangyifan/projects/work/kb_benchmark/repo_sources/vortex/.codegraph/codegraph.db`
CodeGraph version: 1.1.1 (commit `4077ed19b7d8a88eba93601c0c308e59c8640f8c`)

Table summary:

| table | rows | virtual |
|---|---|---|
| `edges` | 16133 |  |
| `files` | 366 |  |
| `nodes` | 7727 |  |
| `nodes_fts` | 7727 | yes |
| `nodes_fts_config` | 1 |  |
| `nodes_fts_data` | 152 |  |
| `nodes_fts_docsize` | 7727 |  |
| `nodes_fts_idx` | 149 |  |
| `project_metadata` | 2 |  |
| `schema_versions` | 2 |  |
| `unresolved_refs` | 0 |  |


## `edges`

Row count: 16133

| column | type | pk | notnull | default |
|---|---|---|---|---|
| id | INTEGER | Y |  |  |
| source | TEXT |  | Y |  |
| target | TEXT |  | Y |  |
| kind | TEXT |  | Y |  |
| metadata | TEXT |  |  |  |
| line | INTEGER |  |  |  |
| col | INTEGER |  |  |  |
| provenance | TEXT |  |  | NULL |

Foreign keys:
- `target` → `nodes.id`
- `source` → `nodes.id`

Indexes:
- `idx_edges_provenance`
- `idx_edges_target_kind`
- `idx_edges_source_kind`
- `idx_edges_kind`

```sql
CREATE TABLE edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    kind TEXT NOT NULL,
    metadata TEXT, -- JSON object
    line INTEGER,
    col INTEGER,
    provenance TEXT DEFAULT NULL,
    FOREIGN KEY (source) REFERENCES nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (target) REFERENCES nodes(id) ON DELETE CASCADE
)
```

## `files`

Row count: 366

| column | type | pk | notnull | default |
|---|---|---|---|---|
| path | TEXT | Y |  |  |
| content_hash | TEXT |  | Y |  |
| language | TEXT |  | Y |  |
| size | INTEGER |  | Y |  |
| modified_at | INTEGER |  | Y |  |
| indexed_at | INTEGER |  | Y |  |
| node_count | INTEGER |  |  | 0 |
| errors | TEXT |  |  |  |

Indexes:
- `idx_files_modified_at`
- `idx_files_language`
- `sqlite_autoindex_files_1` (unique)

```sql
CREATE TABLE files (
    path TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    language TEXT NOT NULL,
    size INTEGER NOT NULL,
    modified_at INTEGER NOT NULL,
    indexed_at INTEGER NOT NULL,
    node_count INTEGER DEFAULT 0,
    errors TEXT -- JSON array
)
```

## `nodes`

Row count: 7727

| column | type | pk | notnull | default |
|---|---|---|---|---|
| id | TEXT | Y |  |  |
| kind | TEXT |  | Y |  |
| name | TEXT |  | Y |  |
| qualified_name | TEXT |  | Y |  |
| file_path | TEXT |  | Y |  |
| language | TEXT |  | Y |  |
| start_line | INTEGER |  | Y |  |
| end_line | INTEGER |  | Y |  |
| start_column | INTEGER |  | Y |  |
| end_column | INTEGER |  | Y |  |
| docstring | TEXT |  |  |  |
| signature | TEXT |  |  |  |
| visibility | TEXT |  |  |  |
| is_exported | INTEGER |  |  | 0 |
| is_async | INTEGER |  |  | 0 |
| is_static | INTEGER |  |  | 0 |
| is_abstract | INTEGER |  |  | 0 |
| decorators | TEXT |  |  |  |
| type_parameters | TEXT |  |  |  |
| return_type | TEXT |  |  |  |
| updated_at | INTEGER |  | Y |  |

Indexes:
- `idx_nodes_lower_name`
- `idx_nodes_file_line`
- `idx_nodes_language`
- `idx_nodes_file_path`
- `idx_nodes_qualified_name`
- `idx_nodes_name`
- `idx_nodes_kind`
- `sqlite_autoindex_nodes_1` (unique)

```sql
CREATE TABLE nodes (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    qualified_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    language TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    start_column INTEGER NOT NULL,
    end_column INTEGER NOT NULL,
    docstring TEXT,
    signature TEXT,
    visibility TEXT,
    is_exported INTEGER DEFAULT 0,
    is_async INTEGER DEFAULT 0,
    is_static INTEGER DEFAULT 0,
    is_abstract INTEGER DEFAULT 0,
    decorators TEXT, -- JSON array
    type_parameters TEXT, -- JSON array
    return_type TEXT, -- normalized return/result type name (e.g. C++ method return, for receiver-type inference)
    updated_at INTEGER NOT NULL
)
```

## `nodes_fts`

Virtual table (FTS5).

Row count: 7727

| column | type | pk | notnull | default |
|---|---|---|---|---|
| id |  |  |  |  |
| name |  |  |  |  |
| qualified_name |  |  |  |  |
| docstring |  |  |  |  |
| signature |  |  |  |  |

```sql
CREATE VIRTUAL TABLE nodes_fts USING fts5(
    id,
    name,
    qualified_name,
    docstring,
    signature,
    content='nodes',
    content_rowid='rowid'
)
```

## `nodes_fts_config`

Row count: 1

| column | type | pk | notnull | default |
|---|---|---|---|---|
| k |  | Y | Y |  |
| v |  |  |  |  |

Indexes:
- `sqlite_autoindex_nodes_fts_config_1` (unique)

```sql
CREATE TABLE 'nodes_fts_config'(k PRIMARY KEY, v) WITHOUT ROWID
```

## `nodes_fts_data`

Row count: 152

| column | type | pk | notnull | default |
|---|---|---|---|---|
| id | INTEGER | Y |  |  |
| block | BLOB |  |  |  |

```sql
CREATE TABLE 'nodes_fts_data'(id INTEGER PRIMARY KEY, block BLOB)
```

## `nodes_fts_docsize`

Row count: 7727

| column | type | pk | notnull | default |
|---|---|---|---|---|
| id | INTEGER | Y |  |  |
| sz | BLOB |  |  |  |

```sql
CREATE TABLE 'nodes_fts_docsize'(id INTEGER PRIMARY KEY, sz BLOB)
```

## `nodes_fts_idx`

Row count: 149

| column | type | pk | notnull | default |
|---|---|---|---|---|
| segid |  | Y | Y |  |
| term |  | Y | Y |  |
| pgno |  |  |  |  |

Indexes:
- `sqlite_autoindex_nodes_fts_idx_1` (unique)

```sql
CREATE TABLE 'nodes_fts_idx'(segid, term, pgno, PRIMARY KEY(segid, term)) WITHOUT ROWID
```

## `project_metadata`

Row count: 2

| column | type | pk | notnull | default |
|---|---|---|---|---|
| key | TEXT | Y |  |  |
| value | TEXT |  | Y |  |
| updated_at | INTEGER |  | Y |  |

Indexes:
- `sqlite_autoindex_project_metadata_1` (unique)

```sql
CREATE TABLE project_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at INTEGER NOT NULL
)
```

## `schema_versions`

Row count: 2

| column | type | pk | notnull | default |
|---|---|---|---|---|
| version | INTEGER | Y |  |  |
| applied_at | INTEGER |  | Y |  |
| description | TEXT |  |  |  |

```sql
CREATE TABLE schema_versions (
    version INTEGER PRIMARY KEY,
    applied_at INTEGER NOT NULL,
    description TEXT
)
```

## `unresolved_refs`

Row count: 0

| column | type | pk | notnull | default |
|---|---|---|---|---|
| id | INTEGER | Y |  |  |
| from_node_id | TEXT |  | Y |  |
| reference_name | TEXT |  | Y |  |
| reference_kind | TEXT |  | Y |  |
| line | INTEGER |  | Y |  |
| col | INTEGER |  | Y |  |
| candidates | TEXT |  |  |  |
| file_path | TEXT |  | Y | '' |
| language | TEXT |  | Y | 'unknown' |

Foreign keys:
- `from_node_id` → `nodes.id`

Indexes:
- `idx_unresolved_from_name`
- `idx_unresolved_file_path`
- `idx_unresolved_name`
- `idx_unresolved_from_node`

```sql
CREATE TABLE unresolved_refs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_node_id TEXT NOT NULL,
    reference_name TEXT NOT NULL,
    reference_kind TEXT NOT NULL,
    line INTEGER NOT NULL,
    col INTEGER NOT NULL,
    candidates TEXT, -- JSON array
    file_path TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT 'unknown',
    FOREIGN KEY (from_node_id) REFERENCES nodes(id) ON DELETE CASCADE
)
```
