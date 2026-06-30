#!/usr/bin/env python3
"""Walk an RTL directory, parse each .sv/.v/.svh/.vh file with
tree-sitter-verilog, and emit per-file + summary JSON.

Usage:
  uv run python scripts/feasibility/measure_rtl_parse_coverage.py \
      --root repo_sources/vortex \
      --out-jsonl runs/feasibility_v2_analyzer/vortex_rtl_coverage.jsonl \
      --out-summary runs/feasibility_v2_analyzer/vortex_rtl_coverage.summary.json

Exits 0 on success regardless of per-file parse outcomes (this is
measurement, not gating).

The expected-kind list reflects what tree-sitter-verilog 1.0.3 actually
emits (see runs/feasibility_v2_analyzer/_observed_node_kinds.md):

- `conditional_statement`         (not `if_statement`)
- `always_construct`              (not `always_block`)
- module instantiation is grammatically ambiguous; we track the union of
  `module_instantiation` / `checker_instantiation` / `udp_instantiation`.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from tree_sitter import Language, Parser
import tree_sitter_verilog as tsv

RTL_SUFFIXES = {".sv", ".v", ".svh", ".vh"}

EXPECTED_KINDS = {
    "module_declaration",
    "parameter_declaration",
    "always_construct",
    "conditional_statement",
    "case_statement",
    "module_instantiation",
    "checker_instantiation",
    "udp_instantiation",
    # additional kinds we want presence-counts for in real RTL:
    "function_declaration",
    "task_declaration",
    "interface_declaration",
    "package_declaration",
    "class_declaration",
    "package_import_declaration",
    "include_directive",
    "text_macro_definition",
}


def walk(node):
    """Iterative pre-order walk. Iterative because some NVDLA DesignWare
    files have AST depth >1000 and blow Python's recursion limit."""
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        # Push children right-to-left so we visit them left-to-right.
        stack.extend(reversed(n.children))


def classify(root) -> tuple[str, int, int]:
    err_count = 0
    total = 0
    for n in walk(root):
        total += 1
        if n.type == "ERROR" or n.is_missing:
            err_count += 1
    if err_count == 0:
        status = "clean"
    elif total > 0 and err_count / total < 0.05:
        status = "partial"
    else:
        status = "error"
    return status, err_count, total


def kind_counts(root) -> Counter:
    return Counter(n.type for n in walk(root))


def collect_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.suffix in RTL_SUFFIXES and p.is_file())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--out-jsonl", required=True, type=Path)
    ap.add_argument("--out-summary", required=True, type=Path)
    ap.add_argument(
        "--self-check",
        action="store_true",
        help="Only validate output schema by writing one synthetic record.",
    )
    args = ap.parse_args()

    args.out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    args.out_summary.parent.mkdir(parents=True, exist_ok=True)
    parser = Parser(Language(tsv.language()))

    if args.self_check:
        sample = {
            "path": "synthetic",
            "parse_status": "clean",
            "node_kind_counts": {"module_declaration": 1},
            "error_count": 0,
            "size_bytes": 0,
        }
        args.out_jsonl.write_text(json.dumps(sample) + "\n")
        args.out_summary.write_text(
            json.dumps(
                {
                    "total_files": 1,
                    "clean": 1,
                    "partial": 0,
                    "error": 0,
                    "files_with_kind": {"module_declaration": 1},
                    "parse_rate_pct": 100.0,
                },
                indent=2,
            )
        )
        return 0

    files = collect_files(args.root)
    by_status: Counter = Counter()
    files_with_kind: Counter = Counter()
    error_top: list[tuple[str, int]] = []

    with args.out_jsonl.open("w") as out:
        for p in files:
            try:
                data = p.read_bytes()
            except OSError as e:
                rec = {
                    "path": str(p.relative_to(args.root)),
                    "parse_status": "error",
                    "node_kind_counts": {},
                    "error_count": 1,
                    "size_bytes": 0,
                    "read_error": str(e),
                }
                out.write(json.dumps(rec) + "\n")
                by_status["error"] += 1
                continue
            tree = parser.parse(data)
            status, err_count, _total = classify(tree.root_node)
            by_status[status] += 1
            counts = kind_counts(tree.root_node)
            for k in EXPECTED_KINDS:
                if counts.get(k, 0) > 0:
                    files_with_kind[k] += 1
            rec = {
                "path": str(p.relative_to(args.root)),
                "parse_status": status,
                "node_kind_counts": {k: counts[k] for k in EXPECTED_KINDS if counts.get(k)},
                "error_count": err_count,
                "size_bytes": len(data),
            }
            out.write(json.dumps(rec) + "\n")
            if err_count > 0:
                error_top.append((str(p.relative_to(args.root)), err_count))

    error_top.sort(key=lambda x: x[1], reverse=True)
    total = len(files)
    summary = {
        "total_files": total,
        "clean": by_status["clean"],
        "partial": by_status["partial"],
        "error": by_status["error"],
        "files_with_kind": dict(files_with_kind),
        "parse_rate_pct": round(100.0 * by_status["clean"] / max(total, 1), 2),
        "top_error_files": error_top[:5],
    }
    args.out_summary.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
