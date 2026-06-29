"""Build the tiny.db SQLite fixture deterministically.

Re-run after schema changes; commit both this script and the resulting
tiny.db. Schema mirrors CodeGraph v1.1.1's real DDL (see
skills/benchmark-repo-analyzer/references/codegraph_schema.md).

The fixture is engineered to exercise four code paths in the exporter:

1. Multi-language sources (cpp, python, verilog) so language→modality
   derivation has multiple buckets.
2. A Verilog `class` entity so the Verilog-module remap test fires.
3. A CodeGraph `method` entity so the kind-normalization test confirms
   `method` -> `function`.
4. An `instantiates` edge so the v1.1 predicate emerges in the output.
5. An `import` node (which the exporter SKIPS) referenced as the target
   of an `imports` edge — so the edge's endpoint resolution drops it,
   confirming we don't emit broken-endpoint relations.
"""
import sqlite3
from pathlib import Path

DB = Path(__file__).parent / "tiny.db"
DB.unlink(missing_ok=True)
conn = sqlite3.connect(DB)
conn.executescript("""
CREATE TABLE files (
    path TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    language TEXT NOT NULL,
    size INTEGER NOT NULL,
    modified_at INTEGER NOT NULL,
    indexed_at INTEGER NOT NULL,
    node_count INTEGER DEFAULT 0,
    errors TEXT
);

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
    decorators TEXT,
    type_parameters TEXT,
    return_type TEXT,
    updated_at INTEGER NOT NULL
);

CREATE TABLE edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    kind TEXT NOT NULL,
    metadata TEXT,
    line INTEGER,
    col INTEGER,
    provenance TEXT,
    FOREIGN KEY (source) REFERENCES nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (target) REFERENCES nodes(id) ON DELETE CASCADE
);

CREATE TABLE unresolved_refs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_node_id TEXT NOT NULL,
    reference_name TEXT NOT NULL,
    reference_kind TEXT NOT NULL,
    line INTEGER NOT NULL,
    col INTEGER NOT NULL,
    candidates TEXT,
    file_path TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT 'unknown'
);

CREATE TABLE project_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE schema_versions (
    version INTEGER PRIMARY KEY,
    applied_at INTEGER NOT NULL,
    description TEXT
);
""")

# Files: cpp, python, verilog (one each).
conn.executemany(
    "INSERT INTO files VALUES (?,?,?,?,?,?,?,?)",
    [
        ("tiny/main.cpp",         "aaa", "cpp",     200, 0, 0, 2, None),
        ("tiny/helper.py",        "bbb", "python",   80, 0, 0, 1, None),
        ("tiny/parent.sv",        "ccc", "verilog", 150, 0, 0, 2, None),
        ("tiny/child.sv",         "ddd", "verilog", 100, 0, 0, 1, None),
    ],
)

# Nodes:
# - cpp: a class + a method on it
# - python: a function
# - verilog: a module (kind=class) per file; ONE function inside parent.sv
# - one `file:` node (the exporter SKIPs but edges still reference it)
# - one `import:` node (also SKIPped by the exporter)
conn.executemany(
    "INSERT INTO nodes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
    [
        # file nodes (one per file, in path order)
        ("file:tiny/main.cpp",       "file", "tiny/main.cpp", "tiny/main.cpp",
         "tiny/main.cpp", "cpp", 1, 12, 0, 0, None, None, None, 0, 0, 0, 0, None, None, None, 0),
        ("file:tiny/helper.py",      "file", "tiny/helper.py", "tiny/helper.py",
         "tiny/helper.py", "python", 1, 6, 0, 0, None, None, None, 0, 0, 0, 0, None, None, None, 0),
        ("file:tiny/parent.sv",      "file", "tiny/parent.sv", "tiny/parent.sv",
         "tiny/parent.sv", "verilog", 1, 10, 0, 0, None, None, None, 0, 0, 0, 0, None, None, None, 0),
        ("file:tiny/child.sv",       "file", "tiny/child.sv", "tiny/child.sv",
         "tiny/child.sv", "verilog", 1, 4, 0, 0, None, None, None, 0, 0, 0, 0, None, None, None, 0),

        # cpp class + method
        ("class:cpp-foo",            "class",  "Foo",    "Foo",
         "tiny/main.cpp", "cpp", 2, 10, 0, 1, None, None, None, 0, 0, 0, 0, None, None, None, 0),
        ("method:cpp-foo-bar",       "method", "bar",    "Foo::bar",
         "tiny/main.cpp", "cpp", 4, 8, 2, 3, None, "()", None, 0, 0, 0, 0, None, None, "void", 0),

        # python function
        ("function:py-greet",        "function", "greet", "greet",
         "tiny/helper.py", "python", 1, 3, 0, 1, None, "()", None, 0, 0, 0, 0, None, None, None, 0),

        # verilog module (parent) + function inside it
        ("class:sv-parent",          "class",    "parent", "parent",
         "tiny/parent.sv", "verilog", 1, 8, 0, 9, None, None, None, 0, 0, 0, 0, None, None, None, 0),
        ("method:sv-parent-helper",  "method",   "helper", "helper",
         "tiny/parent.sv", "verilog", 3, 5, 2, 16, None, None, None, 0, 0, 0, 0, None, None, None, 0),

        # verilog module (child)
        ("class:sv-child",           "class",    "child",  "child",
         "tiny/child.sv", "verilog", 1, 3, 0, 9, None, None, None, 0, 0, 0, 0, None, None, None, 0),

        # an import node (will be SKIPped at entity_index)
        ("import:py-os",             "import",   "os",     "os",
         "tiny/helper.py", "python", 1, 1, 0, 9, None, None, None, 0, 0, 0, 0, None, None, None, 0),
    ],
)

# Edges:
# - file -> entity contains edges
# - class -> method contains edge
# - cpp method -> cpp class extends? (no — use plain references)
# - py function -> py import imports edge (target is SKIPped node)
# - verilog parent class -> verilog child class instantiates edge (LOAD-BEARING)
# - verilog parent class -> python function calls edge (would be filtered by language; demonstrates the cross-lang path stays in graph)
conn.executemany(
    "INSERT INTO edges (source,target,kind,metadata,line,col,provenance) VALUES (?,?,?,?,?,?,?)",
    [
        ("file:tiny/main.cpp",  "class:cpp-foo",           "contains", None, 2, 0, None),
        ("class:cpp-foo",       "method:cpp-foo-bar",      "contains", None, 4, 2, None),
        ("file:tiny/helper.py", "function:py-greet",       "contains", None, 1, 0, None),
        ("file:tiny/parent.sv", "class:sv-parent",         "contains", None, 1, 0, None),
        ("class:sv-parent",     "method:sv-parent-helper", "contains", None, 3, 2, None),
        ("file:tiny/child.sv",  "class:sv-child",          "contains", None, 1, 0, None),
        ("function:py-greet",   "import:py-os",            "imports",  None, 1, 0, "tree_sitter"),
        ("class:sv-parent",     "class:sv-child",          "instantiates", None, 5, 2, "tree_sitter"),
    ],
)

conn.executemany(
    "INSERT INTO project_metadata VALUES (?,?,?)",
    [("indexed_with_version", "1.1.1", 0),
     ("indexed_with_extraction_version", "24", 0)],
)

conn.execute(
    "INSERT INTO schema_versions VALUES (?,?,?)",
    (1, 0, "Initial schema"),
)

conn.commit()
conn.close()
print(f"wrote {DB} ({DB.stat().st_size} bytes)")
