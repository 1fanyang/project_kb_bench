#!/usr/bin/env python3
"""Export a CodeGraph SQLite DB into the canonical analyzer bundle.

Usage:
  uv run python skills/benchmark-repo-analyzer/scripts/codegraph_to_bundle.py \\
      --db <codegraph.db> \\
      --project vortex --source-set-id vortex_main \\
      --repo-name vortex/vortex \\
      --out runs/vortex_context_bundle_v2/ \\
      [--diff-against runs/vortex_context_bundle/]

Output files (in --out):
  source_inventory.jsonl   one row per file
  entity_index.jsonl       one row per symbol (modules, classes, fns, ...)
  relation_graph.jsonl     one row per edge (contains, calls, imports,
                                              instantiates, extends, ...)
  project_manifest.json    analyzer_version + counts + backend pin
  analyzer_report.md       human-readable summary
  _diff_vs_v1.md           (only if --diff-against given) v2 vs v1 deltas

Determinism: the script is pure read-from-SQLite + write-JSONL. Sorting
is on path (source_inventory), id (entity_index, relation_graph). Re-running
with the same DB produces byte-identical output.

The exporter never calls `codegraph index` — that's a prerequisite. It
also never reads from `repo_sources/` except via the
`included_first_substantive_line` enrichment on `imports_or_includes`
edges, which requires the included file to be in the project tree.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

# Add the script directory to sys.path so sibling modules import cleanly when
# invoked via `uv run python skills/.../codegraph_to_bundle.py`.
sys.path.insert(0, str(Path(__file__).parent))

import _bundle_writer as bw
import _codegraph_queries as q


# ---------------------------------------------------------------------------
# source_inventory.jsonl
# ---------------------------------------------------------------------------

def _strip_prefix(cg_path: str, prefix: str) -> str:
    """CodeGraph stores paths relative to the dir it was indexed in. The v1
    bundle's `relative_path` is relative to one level deeper (the actual
    git checkout under `repo_sources/<project>/<inner>/`). --strip-prefix
    drops that leading inner dir so the two bundle layouts align.

    Example: cg path `vortex/hw/rtl/foo.sv` + `--strip-prefix vortex` ->
             relative_path `hw/rtl/foo.sv`.
    """
    if not prefix:
        return cg_path
    p = prefix.rstrip("/") + "/"
    return cg_path[len(p):] if cg_path.startswith(p) else cg_path


def emit_source_inventory(conn, args, out_dir: Path) -> dict:
    """Returns {'path_to_source_id': {cg_path: source_id},
                'path_to_relative': {cg_path: stripped_relative_path},
                'source_inventory_count': int}.
    """
    path_to_source_id: dict[str, str] = {}
    path_to_relative: dict[str, str] = {}
    records = []
    for ordinal, row in enumerate(conn.execute(q.FILES_QUERY), start=1):
        sid = bw.source_id(args.project, ordinal)
        path_to_source_id[row["path"]] = sid
        relative = _strip_prefix(row["path"], args.strip_prefix)
        path_to_relative[row["path"]] = relative
        modality = bw.derive_modality(row["language"])
        records.append({
            "authority": "primary_source",
            "language": row["language"] or "unknown",
            "line_count": _line_count(row["size"], row["node_count"]),
            "modality": modality,
            "parse_status": "parsed" if row["errors"] in (None, "[]") else "errors",
            "path": _full_path(args.repo_name, relative),
            "project": args.project,
            "relative_path": relative,
            "repo_name": args.repo_name,
            "sha256": f"sha256:{row['content_hash']}",
            "size_bytes": row["size"] or 0,
            "source_id": sid,
            "source_set_id": args.source_set_id,
            "source_type": bw.derive_source_type(modality),
        })
    count = bw.write_jsonl(out_dir / "source_inventory.jsonl", records)
    return {"path_to_source_id": path_to_source_id,
            "path_to_relative": path_to_relative,
            "source_inventory_count": count}


def _line_count(size_bytes: int | None, node_count: int | None) -> int:
    """CodeGraph doesn't store line counts directly. We don't either; emit 0
    when unknown. (Phase 4 doesn't read this field; Stage-0 prepare uses
    size_bytes instead.)"""
    return 0


def _full_path(repo_name: str, relative: str) -> str:
    """Match the v1 bundle convention: repo_sources/<repo>/<relative>."""
    return f"repo_sources/{repo_name}/{relative}"


# ---------------------------------------------------------------------------
# entity_index.jsonl
# ---------------------------------------------------------------------------

def emit_entity_index(conn, args, out_dir: Path, ctx: dict) -> dict:
    """Returns {'node_id_to_entity_id': {cg_node_id: bundle_entity_id},
                'node_id_to_source_id': {cg_node_id: source_id},
                'node_id_to_name': {cg_node_id: name},
                'node_id_to_kind': {cg_node_id: v1_kind},
                'entity_index_count': int}."""
    path_to_source_id = ctx["path_to_source_id"]
    node_id_to_entity_id: dict[str, str] = {}
    node_id_to_source_id: dict[str, str] = {}
    node_id_to_name: dict[str, str] = {}
    node_id_to_kind: dict[str, str] = {}
    records = []

    for row in conn.execute(q.ENTITIES_QUERY):
        sid = path_to_source_id.get(row["file_path"])
        if not sid:
            continue  # node references a file CodeGraph didn't track (shouldn't happen)
        # Always thread the source_id for ANY node (so relations whose
        # source/target is a SKIPped node — file:, import: — can still
        # locate their evidence path). Only emit an entity_index ROW for
        # non-skipped kinds.
        node_id_to_source_id[row["id"]] = sid
        node_id_to_name[row["id"]] = row["name"]

        v1_kind = bw.remap_kind(row["kind"], row["language"])
        if v1_kind is None:
            continue  # SKIP_CG_KINDS (file, import)
        eid = bw.entity_id(args.project, row["name"], v1_kind, sid,
                           row["start_line"] or 1)
        node_id_to_entity_id[row["id"]] = eid
        node_id_to_kind[row["id"]] = v1_kind
        relative = ctx["path_to_relative"].get(row["file_path"], row["file_path"])
        records.append({
            "confidence": 0.95,
            "entity_id": eid,
            "extractor": "codegraph_tree_sitter_v2",
            "kind": v1_kind,
            "line_end": row["end_line"] or row["start_line"] or 1,
            "line_start": row["start_line"] or 1,
            "name": row["name"],
            "path": _full_path(args.repo_name, relative),
            "project": args.project,
            "source_id": sid,
            **({"qualified_name": row["qualified_name"]}
               if row["qualified_name"] and row["qualified_name"] != row["name"]
               else {}),
            **({"signature": row["signature"]} if row["signature"] else {}),
        })
    count = bw.write_jsonl(out_dir / "entity_index.jsonl", records)
    return {
        "node_id_to_entity_id": node_id_to_entity_id,
        "node_id_to_source_id": node_id_to_source_id,
        "node_id_to_name": node_id_to_name,
        "node_id_to_kind": node_id_to_kind,
        "entity_index_count": count,
    }


# ---------------------------------------------------------------------------
# relation_graph.jsonl
# ---------------------------------------------------------------------------

def emit_relation_graph(conn, args, out_dir: Path, ctx: dict,
                        repo_sources_root: Path | None) -> dict:
    """Emit one relation row per CodeGraph edge.

    Each edge's source/target is a node id. We map to either an entity_id
    (if the node survived entity_index emission — i.e. its kind wasn't
    SKIPped) or a source_id (for file:* nodes).
    """
    n2e = ctx["node_id_to_entity_id"]
    n2s = ctx["node_id_to_source_id"]
    n2n = ctx["node_id_to_name"]
    n2k = ctx["node_id_to_kind"]

    # Build a quick lookup for file: nodes (which got skipped in entity_index
    # but still appear as edge endpoints; map them to source_id).
    file_node_to_source: dict[str, str] = {}
    for row in conn.execute(q.ENTITIES_QUERY):
        if row["kind"] == "file":
            sid = ctx["path_to_source_id"].get(row["file_path"])
            if sid:
                file_node_to_source[row["id"]] = sid

    # path lookup for evidence — use stripped relative paths so the
    # bundle's evidence.path matches source_inventory.path conventions.
    source_to_relative: dict[str, str] = {}
    for row in conn.execute(q.FILES_QUERY):
        sid = ctx["path_to_source_id"].get(row["path"])
        if sid:
            source_to_relative[sid] = ctx["path_to_relative"].get(
                row["path"], row["path"]
            )
    source_to_path = source_to_relative  # alias for the helpers below

    records = []
    predicate_counts: Counter = Counter()
    dropped_pred_counts: Counter = Counter()
    ordinal = 0

    for row in conn.execute(q.RELATIONS_QUERY):
        v1_pred = bw.remap_predicate(row["kind"])
        if v1_pred is None:
            dropped_pred_counts[row["kind"]] += 1
            continue

        subj = _endpoint(row["source"], n2e, n2s, n2n, n2k, file_node_to_source)
        obj = _endpoint(row["target"], n2e, n2s, n2n, n2k, file_node_to_source)
        if subj is None or obj is None:
            # an endpoint refers to a node we skipped (file/import); drop the edge
            continue

        evidence = _evidence_for(row, v1_pred, ctx, source_to_path,
                                 args, repo_sources_root, obj)
        ordinal += 1
        records.append({
            "confidence": 0.95,
            "evidence": evidence,
            "extractor": "codegraph_tree_sitter_v2",
            "object": obj,
            "predicate": v1_pred,
            "project": args.project,
            "relation_id": bw.relation_id(args.project, ordinal),
            "subject": subj,
        })
        predicate_counts[v1_pred] += 1

    count = bw.write_jsonl(out_dir / "relation_graph.jsonl", records)
    return {
        "relation_graph_count": count,
        "predicate_counts": dict(predicate_counts),
        "dropped_predicate_counts": dict(dropped_pred_counts),
    }


def _endpoint(node_id: str | None, n2e, n2s, n2n, n2k, file_node_to_source):
    """Build a {type, id, name} endpoint dict from a CodeGraph node id.

    Returns None if the node id refers to something we couldn't resolve
    (typically an `import:*` node we skipped at entity_index time).
    """
    if not node_id:
        return None
    if node_id in n2e:
        return {"type": "entity", "id": n2e[node_id], "name": n2n.get(node_id, "")}
    if node_id in file_node_to_source:
        sid = file_node_to_source[node_id]
        # Source-typed endpoints carry the file's source_id and basename name.
        return {"type": "source", "id": sid, "name": node_id.split("file:", 1)[-1]}
    if node_id.startswith("file:"):
        # File node that didn't make it into our maps (sub-pruned file
        # entity); still resolve by stripping the prefix and looking up.
        path = node_id.split("file:", 1)[-1]
        return None  # safer to drop than emit incomplete
    return None


def _evidence_for(row, v1_pred, ctx, source_to_path, args, repo_sources_root, obj):
    """Build the `evidence` array for a relation row.

    For `imports_or_includes`, enrich with `included_first_substantive_line`
    when the included file lives under repo_sources_root.
    """
    n2s = ctx["node_id_to_source_id"]
    # Subject's source_id (preferred for evidence path)
    subj_sid = n2s.get(row["source"])
    subj_path = source_to_path.get(subj_sid) if subj_sid else None
    line = row["line"]
    lines_field = str(line) if line is not None else "1"

    base = {
        "source_id": subj_sid or "src_unknown",
        "path": _full_path(args.repo_name, subj_path) if subj_path else f"<{row['source']}>",
        "lines": lines_field,
        "summary": _summary_for(row, v1_pred, ctx, obj),
    }
    if v1_pred == "imports_or_includes" and repo_sources_root is not None:
        # The "included" file is the target — try to locate it on disk.
        n2k = ctx["node_id_to_kind"]
        target_id = row["target"]
        target_path_rel = source_to_path.get(n2s.get(target_id))
        if target_path_rel:
            abs_path = repo_sources_root / args.repo_name / target_path_rel
            base["included_first_substantive_line"] = bw.first_substantive_line(abs_path)
    return [base]


def _summary_for(row, v1_pred, ctx, obj):
    n2n = ctx["node_id_to_name"]
    subj_name = n2n.get(row["source"], row["source"])
    obj_name = obj.get("name", "")
    return f"{subj_name} {v1_pred} {obj_name}".strip()


# ---------------------------------------------------------------------------
# project_manifest.json
# ---------------------------------------------------------------------------

def emit_project_manifest(conn, args, out_dir: Path, ctx: dict,
                          rel_ctx: dict, cg_pin: str) -> None:
    cg_meta = {row["key"]: row["value"]
               for row in conn.execute(q.PROJECT_METADATA_QUERY)}
    counts = {
        "sources": ctx["source_inventory_count"],
        "entities": ctx["entity_index_count"],
        "relations": rel_ctx["relation_graph_count"],
        "relations_by_predicate": rel_ctx["predicate_counts"],
        "dropped_relations_by_predicate": rel_ctx["dropped_predicate_counts"],
    }
    now = (datetime.datetime.now(datetime.UTC)
                   .replace(microsecond=0)
                   .isoformat()
                   .replace("+00:00", "Z"))
    manifest = {
        # schema-required top-level
        "schema_version": "project-manifest/v1",
        "analyzer_version": "benchmark-repo-analyzer/v2-tree-sitter-codegraph",
        "created_at": now,
        "project": {
            "id": args.project,
            "display_name": args.display_name or args.project.title(),
        },
        # one source_set entry (the indexed root); add multiple if a later
        # exporter version handles cross-set indexing.
        "source_sets": [{
            "id": args.source_set_id,
            "repo_name": args.repo_name,
            "local_root": str(args.source_set_local_root or
                              f"repo_sources/{args.repo_name}"),
            "source_role": args.source_set_role,
            "authority": "primary_source",
            "available": True,
        }],
        "analysis_backends": {
            "code": {
                "requested_primary": "code_graph",
                "used_primary": True,
            },
        },
        "analyzer_pin": {
            "codegraph_commit": cg_pin,
            "codegraph_indexed_with_version":
                cg_meta.get("indexed_with_version"),
            "codegraph_extraction_version":
                cg_meta.get("indexed_with_extraction_version"),
        },
        "counts": counts,
        "generated_at": now,
    }
    (out_dir / "project_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )


# ---------------------------------------------------------------------------
# analyzer_report.md
# ---------------------------------------------------------------------------

def emit_analyzer_report(conn, args, out_dir: Path, ctx: dict,
                         rel_ctx: dict) -> None:
    # Top-5 entity kinds and top-5 inbound entities
    kind_counts = Counter(ctx["node_id_to_kind"].values())
    inbound = Counter()
    for row in conn.execute(q.RELATIONS_QUERY):
        if row["target"] in ctx["node_id_to_entity_id"]:
            inbound[row["target"]] += 1
    top_inbound = [
        (ctx["node_id_to_name"].get(nid, nid), n)
        for nid, n in inbound.most_common(5)
    ]
    lines = [
        f"# Analyzer report — {args.project}\n",
        f"- analyzer: `benchmark-repo-analyzer/v2-tree-sitter-codegraph`",
        f"- repo: `{args.repo_name}`",
        f"- sources: {ctx['source_inventory_count']}",
        f"- entities: {ctx['entity_index_count']}",
        f"- relations: {rel_ctx['relation_graph_count']}",
        "",
        "## Top entity kinds",
        "",
        "| kind | count |",
        "|---|---|",
    ] + [f"| {k} | {n} |" for k, n in kind_counts.most_common(8)] + [
        "",
        "## Top inbound-edge entities (most referenced)",
        "",
    ] + [f"- `{name}` ({n} inbound)" for name, n in top_inbound] + [
        "",
        "## Relations by predicate",
        "",
        "| predicate | count |",
        "|---|---|",
    ] + [f"| {p} | {n} |" for p, n in
         sorted(rel_ctx["predicate_counts"].items(), key=lambda kv: -kv[1])]
    (out_dir / "analyzer_report.md").write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--source-set-id", required=True)
    ap.add_argument("--repo-name", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument(
        "--repo-sources-root",
        type=Path,
        default=Path("repo_sources"),
        help="Root of the on-disk repo sources tree; used to enrich "
             "imports_or_includes evidence with included_first_substantive_line. "
             "Set to a path that exists; defaults to ./repo_sources.",
    )
    ap.add_argument(
        "--codegraph-pin",
        default="4077ed19b7d8a88eba93601c0c308e59c8640f8c",
        help="CodeGraph commit sha recorded in project_manifest.json.",
    )
    ap.add_argument(
        "--strip-prefix",
        default="",
        help="Leading path component to strip from CodeGraph's stored paths "
             "before treating them as relative_path. Use when codegraph "
             "index was run one level above the actual git checkout "
             "(e.g. --strip-prefix vortex for repo_sources/vortex/vortex/).",
    )
    ap.add_argument(
        "--source-set-local-root",
        default=None,
        help="Filesystem path of the source-set's local root (used in "
             "project_manifest.source_sets[].local_root). Defaults to "
             "repo_sources/<repo-name>.",
    )
    ap.add_argument(
        "--source-set-role",
        default="primary_source",
        help="source_role for the source_set entry in project_manifest.",
    )
    ap.add_argument(
        "--display-name",
        default=None,
        help="Human-readable project display name for project_manifest. "
             "Defaults to title-cased --project.",
    )
    ap.add_argument(
        "--diff-against",
        type=Path,
        default=None,
        help="If set, also write _diff_vs_v1.md comparing the v2 output "
             "to this v1 bundle directory.",
    )
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    args.out.mkdir(parents=True, exist_ok=True)

    repo_sources_root = (args.repo_sources_root
                         if args.repo_sources_root.exists() else None)

    src_ctx = emit_source_inventory(conn, args, args.out)
    ent_ctx = emit_entity_index(conn, args, args.out, src_ctx)
    ctx = {**src_ctx, **ent_ctx}
    rel_ctx = emit_relation_graph(conn, args, args.out, ctx, repo_sources_root)
    emit_project_manifest(conn, args, args.out, ctx, rel_ctx, args.codegraph_pin)
    emit_analyzer_report(conn, args, args.out, ctx, rel_ctx)

    if args.diff_against:
        from _diff import diff as _diff_fn
        diff_md = _diff_fn(args.out, args.diff_against)
        (args.out / "_diff_vs_v1.md").write_text(diff_md)

    print(f"wrote v2 bundle to {args.out}")
    print(f"  sources:   {src_ctx['source_inventory_count']}")
    print(f"  entities:  {ent_ctx['entity_index_count']}")
    print(f"  relations: {rel_ctx['relation_graph_count']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
