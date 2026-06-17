#!/usr/bin/env python3
"""Build deterministic analyzer signal_index.jsonl sidecars."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


NON_CODE_MODALITIES = {"script", "config"}
CONDITIONAL_PREDICATES = {"checks_condition", "reads", "writes"}
EXTRACTOR = "deterministic_signal_builder_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an analyzer signal_index.jsonl sidecar.")
    parser.add_argument("bundle", type=Path, help="Directory containing analyzer artifacts")
    parser.add_argument("--output", type=Path, required=True, help="Output signal_index.jsonl path")
    parser.add_argument(
        "--long-tail-threshold",
        type=int,
        default=1,
        help="Maximum relation endpoint count for long_tail entity signals",
    )
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            rows.append(value)
    return rows


def stable_suffix(value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
    readable = "".join(char if char.isalnum() else "-" for char in value.lower()).strip("-")
    readable = "-".join(part for part in readable.split("-") if part)
    if not readable:
        return digest
    return f"{readable[:80]}-{digest}"


def endpoint_id(endpoint: Any) -> str | None:
    if not isinstance(endpoint, dict):
        return None
    value = endpoint.get("id")
    return value if isinstance(value, str) and value else None


def endpoint_type(endpoint: Any) -> str | None:
    if not isinstance(endpoint, dict):
        return None
    value = endpoint.get("type")
    return value if isinstance(value, str) and value else None


def relation_endpoint_counts(relations: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for relation in relations:
        for endpoint_name in ("subject", "object"):
            endpoint = relation.get(endpoint_name)
            if endpoint_type(endpoint) == "entity":
                ref_id = endpoint_id(endpoint)
                if ref_id:
                    counts[ref_id] += 1
    return counts


def project_for_rows(*groups: list[dict[str, Any]]) -> str:
    for rows in groups:
        for row in rows:
            project = row.get("project")
            if isinstance(project, str) and project:
                return project
    return "unknown"


def make_signal(
    project: str,
    attribute: str,
    axis: int,
    anchor: dict[str, Any],
    evidence: dict[str, Any],
    confidence: float,
) -> dict[str, Any]:
    anchor_id = (
        anchor.get("entity_id")
        or anchor.get("source_id")
        or anchor.get("relation_id")
        or anchor.get("path")
        or json.dumps(anchor, sort_keys=True)
    )
    return {
        "signal_id": f"sig:{project}:{attribute}:{stable_suffix(str(anchor_id))}",
        "project": project,
        "axis": axis,
        "attribute": attribute,
        "anchor": anchor,
        "evidence": evidence,
        "extractor": EXTRACTOR,
        "confidence": confidence,
    }


def build_long_tail_signals(
    project: str,
    entities: list[dict[str, Any]],
    endpoint_counts: Counter[str],
    threshold: int,
) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for entity in entities:
        entity_id = entity.get("entity_id")
        if not isinstance(entity_id, str) or not entity_id:
            continue
        reference_count = endpoint_counts.get(entity_id, 0)
        if reference_count > threshold:
            continue
        anchor = {
            "kind": "entity",
            "entity_id": entity_id,
            "source_id": entity.get("source_id"),
            "path": entity.get("path"),
        }
        if entity.get("line_start"):
            anchor["lines"] = str(entity["line_start"])
        evidence = {
            "reference_count": reference_count,
            "threshold": threshold,
            "entity_name": entity.get("name"),
            "entity_kind": entity.get("kind"),
        }
        signals.append(make_signal(project, "long_tail", 2, anchor, evidence, 0.72))
    return signals


def build_non_code_anchor_signals(project: str, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for source in sources:
        source_id = source.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            continue
        modality = source.get("modality")
        if modality not in NON_CODE_MODALITIES:
            continue
        anchor = {
            "kind": "source",
            "source_id": source_id,
            "path": source.get("path"),
        }
        evidence = {
            "modality": modality,
            "source_type": source.get("source_type"),
            "language": source.get("language"),
            "relative_path": source.get("relative_path"),
        }
        signals.append(make_signal(project, "non_code_anchor", 2, anchor, evidence, 0.78))
    return signals


def build_distracting_info_signals(project: str, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entity in entities:
        name = entity.get("name")
        source_id = entity.get("source_id")
        if isinstance(name, str) and name and isinstance(source_id, str) and source_id:
            by_name[name].append(entity)

    signals: list[dict[str, Any]] = []
    for name in sorted(by_name):
        group = by_name[name]
        source_ids = sorted({str(entity.get("source_id")) for entity in group if entity.get("source_id")})
        if len(source_ids) < 2:
            continue
        for entity in group:
            entity_id = entity.get("entity_id")
            if not isinstance(entity_id, str) or not entity_id:
                continue
            anchor = {
                "kind": "entity",
                "entity_id": entity_id,
                "source_id": entity.get("source_id"),
                "path": entity.get("path"),
            }
            if entity.get("line_start"):
                anchor["lines"] = str(entity["line_start"])
            evidence = {
                "name": name,
                "collision_source_count": len(source_ids),
                "collision_sources": source_ids[:20],
                "total_entities_with_name": len(group),
            }
            signals.append(make_signal(project, "distracting_info", 3, anchor, evidence, 0.66))
    return signals


def first_evidence_item(relation: dict[str, Any]) -> dict[str, Any]:
    evidence = relation.get("evidence")
    if isinstance(evidence, list):
        for item in evidence:
            if isinstance(item, dict):
                return item
    return {}


def build_conditional_behavior_signals(project: str, relations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for relation in relations:
        predicate = relation.get("predicate")
        relation_id = relation.get("relation_id")
        if predicate not in CONDITIONAL_PREDICATES or not isinstance(relation_id, str) or not relation_id:
            continue
        evidence_item = first_evidence_item(relation)
        anchor = {
            "kind": "relation",
            "relation_id": relation_id,
            "source_id": evidence_item.get("source_id"),
            "path": evidence_item.get("path"),
            "lines": evidence_item.get("lines"),
        }
        evidence = {
            "predicate": predicate,
            "subject": relation.get("subject"),
            "object": relation.get("object"),
            "summary": evidence_item.get("summary"),
        }
        signals.append(make_signal(project, "conditional_behavior", 3, anchor, evidence, 0.74))
    return signals


def dedupe_signals(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for signal in signals:
        signal_id = signal["signal_id"]
        if signal_id not in by_id:
            by_id[signal_id] = signal
            continue
        anchor = signal["anchor"]
        disambiguator = anchor.get("entity_id") or anchor.get("source_id") or anchor.get("relation_id")
        signal["signal_id"] = f"{signal_id}:{stable_suffix(str(disambiguator))}"
        by_id[signal["signal_id"]] = signal
    return [by_id[signal_id] for signal_id in sorted(by_id)]


def build_signals(bundle: Path, long_tail_threshold: int) -> list[dict[str, Any]]:
    sources = load_jsonl(bundle / "source_inventory.jsonl")
    entities = load_jsonl(bundle / "entity_index.jsonl")
    relations = load_jsonl(bundle / "relation_graph.jsonl")
    project = project_for_rows(sources, entities, relations)
    endpoint_counts = relation_endpoint_counts(relations)

    signals: list[dict[str, Any]] = []
    signals.extend(build_long_tail_signals(project, entities, endpoint_counts, long_tail_threshold))
    signals.extend(build_non_code_anchor_signals(project, sources))
    signals.extend(build_distracting_info_signals(project, entities))
    signals.extend(build_conditional_behavior_signals(project, relations))
    return dedupe_signals(signals)


def main() -> int:
    args = parse_args()
    if args.long_tail_threshold < 0:
        print("--long-tail-threshold must be non-negative", file=sys.stderr)
        return 2
    signals = build_signals(args.bundle, args.long_tail_threshold)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(signal, ensure_ascii=False, sort_keys=True) + "\n" for signal in signals)
    args.output.write_text(text, encoding="utf-8")
    print(f"Wrote {len(signals)} signals to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
