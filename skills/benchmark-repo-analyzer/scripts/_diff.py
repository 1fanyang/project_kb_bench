"""Compare a v2 bundle dir against a v1 bundle dir; render markdown.

Phase 5 reads this side-by-side report. Never embedded in the manifest.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def _load_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def diff(v2_dir: Path, v1_dir: Path) -> str:
    v1_ents = _load_jsonl(v1_dir / "entity_index.jsonl")
    v2_ents = _load_jsonl(v2_dir / "entity_index.jsonl")
    v1_rels = _load_jsonl(v1_dir / "relation_graph.jsonl")
    v2_rels = _load_jsonl(v2_dir / "relation_graph.jsonl")
    v1_srcs = _load_jsonl(v1_dir / "source_inventory.jsonl")
    v2_srcs = _load_jsonl(v2_dir / "source_inventory.jsonl")

    v1_kind = Counter(e["kind"] for e in v1_ents)
    v2_kind = Counter(e["kind"] for e in v2_ents)
    v1_pred = Counter(r["predicate"] for r in v1_rels)
    v2_pred = Counter(r["predicate"] for r in v2_rels)
    v1_lang = Counter(s["language"] for s in v1_srcs)
    v2_lang = Counter(s["language"] for s in v2_srcs)

    out = [
        f"# v2 vs v1 bundle diff\n",
        f"- v1 dir: `{v1_dir}`",
        f"- v2 dir: `{v2_dir}`",
        "",
        "## Totals",
        "",
        "| metric | v1 | v2 | delta |",
        "|---|---|---|---|",
        f"| sources | {len(v1_srcs)} | {len(v2_srcs)} | {len(v2_srcs)-len(v1_srcs):+d} |",
        f"| entities | {len(v1_ents)} | {len(v2_ents)} | {len(v2_ents)-len(v1_ents):+d} |",
        f"| relations | {len(v1_rels)} | {len(v2_rels)} | {len(v2_rels)-len(v1_rels):+d} |",
        "",
        "## Languages",
        "",
        "| language | v1 | v2 |",
        "|---|---|---|",
    ]
    for k in sorted(set(v1_lang) | set(v2_lang)):
        out.append(f"| {k} | {v1_lang[k]} | {v2_lang[k]} |")
    out += ["", "## Entity kinds", "", "| kind | v1 | v2 |", "|---|---|---|"]
    for k in sorted(set(v1_kind) | set(v2_kind)):
        out.append(f"| {k} | {v1_kind[k]} | {v2_kind[k]} |")
    out += ["", "## Predicate distribution", "",
            "| predicate | v1 | v2 |", "|---|---|---|"]
    for k in sorted(set(v1_pred) | set(v2_pred)):
        out.append(f"| {k} | {v1_pred[k]} | {v2_pred[k]} |")
    return "\n".join(out) + "\n"
