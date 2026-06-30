#!/usr/bin/env python3
"""Dump CodeGraph's SQLite schema to JSON + markdown.

For each table, capture: column names/types, PK, FKs, indexes, and row count.
FTS5 virtual tables don't always support COUNT(*); we record `null` there.

Usage:
  uv run python scripts/feasibility/dump_codegraph_schema.py \\
      --db /path/to/.codegraph/codegraph.db \\
      --out-json runs/feasibility_v2_analyzer/codegraph_schema.json \\
      --out-md   runs/feasibility_v2_analyzer/codegraph_schema.md
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out-json", required=True, type=Path)
    ap.add_argument("--out-md", required=True, type=Path)
    args = ap.parse_args()

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(args.db)
    # Include all tables (real + FTS virtual); exclude sqlite_% internals.
    tables = [
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )
    ]

    schema: list[dict] = []
    for t in tables:
        # PRAGMA table_info works on virtual tables too (returns logical cols).
        cols = list(conn.execute(f"PRAGMA table_info('{t}')"))
        fks = list(conn.execute(f"PRAGMA foreign_key_list('{t}')"))
        idxs = list(conn.execute(f"PRAGMA index_list('{t}')"))
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM '{t}'").fetchone()[0]
        except sqlite3.OperationalError:
            count = None  # FTS5 backing tables sometimes refuse COUNT

        # Find the CREATE TABLE / CREATE VIRTUAL TABLE statement (drops PRAGMA
        # values for virtual tables but is the source of truth for their kind).
        ddl_row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name = ?",
            (t,),
        ).fetchone()
        ddl = (ddl_row[0] if ddl_row else None) or ""

        schema.append({
            "table": t,
            "is_virtual": "VIRTUAL TABLE" in ddl.upper(),
            "row_count": count,
            "ddl": ddl,
            "columns": [
                {
                    "name": c[1], "type": c[2], "notnull": bool(c[3]),
                    "default": c[4], "pk": bool(c[5]),
                }
                for c in cols
            ],
            "foreign_keys": [
                {"from": f[3], "to_table": f[2], "to": f[4]} for f in fks
            ],
            "indexes": [{"name": i[1], "unique": bool(i[2])} for i in idxs],
        })

    args.out_json.write_text(json.dumps(schema, indent=2))

    md_lines = [
        "# CodeGraph SQLite schema",
        "",
        f"DB: `{args.db}`",
        f"CodeGraph version: 1.1.1 (commit `{Path('runs/feasibility_v2_analyzer/_codegraph_commit.txt').read_text().strip() if Path('runs/feasibility_v2_analyzer/_codegraph_commit.txt').exists() else 'unknown'}`)",
        "",
        "Table summary:",
        "",
        "| table | rows | virtual |",
        "|---|---|---|",
    ]
    for s in schema:
        rc = s["row_count"] if s["row_count"] is not None else "n/a"
        md_lines.append(f"| `{s['table']}` | {rc} | {'yes' if s['is_virtual'] else ''} |")
    md_lines.append("")

    for s in schema:
        md_lines.append(f"\n## `{s['table']}`")
        if s["is_virtual"]:
            md_lines.append("\nVirtual table (FTS5).")
        if s["row_count"] is not None:
            md_lines.append(f"\nRow count: {s['row_count']}")
        if s["columns"]:
            md_lines.append("\n| column | type | pk | notnull | default |")
            md_lines.append("|---|---|---|---|---|")
            for c in s["columns"]:
                md_lines.append(
                    f"| {c['name']} | {c['type'] or ''} | "
                    f"{'Y' if c['pk'] else ''} | "
                    f"{'Y' if c['notnull'] else ''} | "
                    f"{c['default'] if c['default'] is not None else ''} |"
                )
        if s["foreign_keys"]:
            md_lines.append("\nForeign keys:")
            for f in s["foreign_keys"]:
                md_lines.append(f"- `{f['from']}` → `{f['to_table']}.{f['to']}`")
        if s["indexes"]:
            md_lines.append("\nIndexes:")
            for i in s["indexes"]:
                md_lines.append(f"- `{i['name']}`{' (unique)' if i['unique'] else ''}")
        if s["ddl"]:
            md_lines.append("\n```sql\n" + s["ddl"].strip() + "\n```")

    args.out_md.write_text("\n".join(md_lines) + "\n")
    print(f"wrote {args.out_json} and {args.out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
