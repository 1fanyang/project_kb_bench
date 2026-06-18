#!/usr/bin/env python3
"""Validate a benchmark analyzer project context bundle."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


REQUIRED_FILES = (
    "project_manifest.json",
    "source_inventory.jsonl",
    "entity_index.jsonl",
    "relation_graph.jsonl",
    "analyzer_report.md",
)

SOURCE_REQUIRED = {
    "source_id",
    "project",
    "source_set_id",
    "repo_name",
    "path",
    "relative_path",
    "modality",
    "source_type",
    "authority",
    "language",
    "line_count",
    "size_bytes",
    "sha256",
    "parse_status",
}

ENTITY_REQUIRED = {
    "entity_id",
    "project",
    "source_id",
    "name",
    "kind",
    "path",
    "line_start",
    "line_end",
    "extractor",
    "confidence",
}

RELATION_REQUIRED = {
    "relation_id",
    "project",
    "subject",
    "predicate",
    "object",
    "evidence",
    "extractor",
    "confidence",
}

SIGNAL_REQUIRED = {
    "signal_id",
    "project",
    "axis",
    "attribute",
    "anchor",
    "evidence",
    "extractor",
    "confidence",
}

MODALITIES = {
    "code",
    "doc",
    "script",
    "test",
    "config",
    "issue",
    "release",
    "binary",
    "data",
    "asset",
    "unknown",
}

PARSE_STATUSES = {"parsed", "partial", "skipped", "failed"}
LINE_RANGE_RE = re.compile(r"^(\d+)(?:-(\d+))?$")


@dataclass
class Finding:
    severity: str
    file: str
    line: int | None
    item_id: str | None
    message: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate analyzer project_context_bundle artifacts.")
    parser.add_argument("bundle", type=Path, help="Directory containing analyzer artifacts")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Base path for relative source paths")
    parser.add_argument("--json-report", type=Path, help="Optional JSON report path")
    parser.add_argument("--fail-on-warn", action="store_true", help="Exit non-zero when WARN findings exist")
    return parser.parse_args()


def add(findings: list[Finding], severity: str, file: str, line: int | None, item_id: str | None, message: str) -> None:
    findings.append(Finding(severity, file, line, item_id, message))


def load_json(path: Path, findings: list[Finding]) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        add(findings, "FAIL", str(path), None, None, f"cannot read file: {exc}")
        return None
    except json.JSONDecodeError as exc:
        add(findings, "FAIL", str(path), None, None, f"JSON parse error: {exc}")
        return None
    if not isinstance(value, dict):
        add(findings, "FAIL", str(path), None, None, "JSON root must be an object")
        return None
    return value


def load_jsonl(path: Path, findings: list[Finding]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        add(findings, "FAIL", str(path), None, None, f"cannot read file: {exc}")
        return rows
    for lineno, line in enumerate(lines, 1):
        if not line.strip():
            add(findings, "WARN", str(path), lineno, None, "blank JSONL line")
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            add(findings, "FAIL", str(path), lineno, None, f"JSON parse error: {exc}")
            continue
        if not isinstance(row, dict):
            add(findings, "FAIL", str(path), lineno, None, "JSONL row must be an object")
            continue
        row["_line"] = lineno
        rows.append(row)
    return rows


def is_number_0_to_1(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and 0 <= float(value) <= 1


def resolve_path(path_value: str, repo_root: Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return repo_root / path


def parse_line_range(value: Any) -> tuple[int, int] | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        return None
    match = LINE_RANGE_RE.match(value)
    if not match:
        return None
    start = int(match.group(1))
    end = int(match.group(2) or start)
    if start <= 0 or end < start:
        return None
    return start, end


def validate_manifest(path: Path, manifest: dict[str, Any] | None, findings: list[Finding]) -> set[str]:
    source_set_ids: set[str] = set()
    if manifest is None:
        return source_set_ids
    if manifest.get("schema_version") != "project-manifest/v1":
        add(findings, "FAIL", str(path), None, None, "`schema_version` must be project-manifest/v1")
    project = manifest.get("project")
    if not isinstance(project, dict) or not project.get("id"):
        add(findings, "FAIL", str(path), None, None, "`project.id` is required")
    source_sets = manifest.get("source_sets")
    if not isinstance(source_sets, list) or not source_sets:
        add(findings, "FAIL", str(path), None, None, "`source_sets` must be a non-empty list")
        return source_set_ids
    required = {"id", "repo_name", "local_root", "source_role", "authority", "available"}
    for index, source_set in enumerate(source_sets):
        item_id = source_set.get("id") if isinstance(source_set, dict) else f"source_sets[{index}]"
        if not isinstance(source_set, dict):
            add(findings, "FAIL", str(path), None, item_id, "source set must be an object")
            continue
        missing = sorted(required - set(source_set))
        if missing:
            add(findings, "FAIL", str(path), None, item_id, f"source set missing fields: {', '.join(missing)}")
        if source_set.get("id") in source_set_ids:
            add(findings, "FAIL", str(path), None, item_id, "duplicate source set id")
        if isinstance(source_set.get("id"), str):
            source_set_ids.add(source_set["id"])
        if not isinstance(source_set.get("available"), bool):
            add(findings, "FAIL", str(path), None, item_id, "`available` must be boolean")
    return source_set_ids


def validate_sources(rows: list[dict[str, Any]], path: Path, repo_root: Path, source_set_ids: set[str], findings: list[Finding]) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        line = row.get("_line")
        source_id = str(row.get("source_id", "<missing>"))
        missing = sorted(SOURCE_REQUIRED - set(row))
        if missing:
            add(findings, "FAIL", str(path), line, source_id, f"source missing fields: {', '.join(missing)}")
        if source_id in by_id:
            add(findings, "FAIL", str(path), line, source_id, "duplicate source_id")
        elif source_id != "<missing>":
            by_id[source_id] = row
        if row.get("source_set_id") not in source_set_ids:
            add(findings, "FAIL", str(path), line, source_id, "`source_set_id` not present in manifest")
        if row.get("modality") not in MODALITIES:
            add(findings, "WARN", str(path), line, source_id, f"non-standard modality: {row.get('modality')}")
        if row.get("parse_status") not in PARSE_STATUSES:
            add(findings, "WARN", str(path), line, source_id, f"non-standard parse_status: {row.get('parse_status')}")
        for numeric in ("line_count", "size_bytes"):
            if not isinstance(row.get(numeric), int) or row.get(numeric) < 0:
                add(findings, "FAIL", str(path), line, source_id, f"`{numeric}` must be a non-negative integer")
        source_path = row.get("path")
        if isinstance(source_path, str) and row.get("modality") not in {"issue", "release"}:
            resolved = resolve_path(source_path, repo_root)
            if not resolved.exists():
                add(findings, "WARN", str(path), line, source_id, f"source path does not exist under repo root: {source_path}")
    return by_id


def validate_entities(rows: list[dict[str, Any]], path: Path, sources: dict[str, dict[str, Any]], findings: list[Finding]) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        line = row.get("_line")
        entity_id = str(row.get("entity_id", "<missing>"))
        missing = sorted(ENTITY_REQUIRED - set(row))
        if missing:
            add(findings, "FAIL", str(path), line, entity_id, f"entity missing fields: {', '.join(missing)}")
        if entity_id in by_id:
            add(findings, "FAIL", str(path), line, entity_id, "duplicate entity_id")
        elif entity_id != "<missing>":
            by_id[entity_id] = row
        if row.get("source_id") not in sources:
            add(findings, "FAIL", str(path), line, entity_id, "`source_id` not present in source inventory")
        for field in ("line_start", "line_end"):
            if not isinstance(row.get(field), int) or row.get(field) < 0:
                add(findings, "FAIL", str(path), line, entity_id, f"`{field}` must be a non-negative integer")
        if isinstance(row.get("line_start"), int) and isinstance(row.get("line_end"), int):
            if row["line_start"] and row["line_end"] and row["line_end"] < row["line_start"]:
                add(findings, "FAIL", str(path), line, entity_id, "`line_end` must be >= `line_start`")
        if not is_number_0_to_1(row.get("confidence")):
            add(findings, "FAIL", str(path), line, entity_id, "`confidence` must be a number from 0 to 1")
    return by_id


def endpoint_id(endpoint: Any) -> str | None:
    if not isinstance(endpoint, dict):
        return None
    value = endpoint.get("id")
    return value if isinstance(value, str) and value else None


def validate_relations(
    rows: list[dict[str, Any]],
    path: Path,
    sources: dict[str, dict[str, Any]],
    entities: dict[str, dict[str, Any]],
    findings: list[Finding],
) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        line = row.get("_line")
        relation_id = str(row.get("relation_id", "<missing>"))
        missing = sorted(RELATION_REQUIRED - set(row))
        if missing:
            add(findings, "FAIL", str(path), line, relation_id, f"relation missing fields: {', '.join(missing)}")
        if relation_id in by_id:
            add(findings, "FAIL", str(path), line, relation_id, "duplicate relation_id")
        elif relation_id != "<missing>":
            by_id[relation_id] = row
        if not isinstance(row.get("subject"), dict):
            add(findings, "FAIL", str(path), line, relation_id, "`subject` must be an object")
        if not isinstance(row.get("object"), dict):
            add(findings, "FAIL", str(path), line, relation_id, "`object` must be an object")
        for endpoint_name in ("subject", "object"):
            ref_id = endpoint_id(row.get(endpoint_name))
            endpoint_type = row.get(endpoint_name, {}).get("type") if isinstance(row.get(endpoint_name), dict) else None
            if endpoint_type == "entity" and ref_id and ref_id not in entities:
                add(findings, "WARN", str(path), line, relation_id, f"{endpoint_name}.id not present in entity index: {ref_id}")
            if endpoint_type == "source" and ref_id and ref_id not in sources:
                add(findings, "WARN", str(path), line, relation_id, f"{endpoint_name}.id not present in source inventory: {ref_id}")
        evidence = row.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            add(findings, "FAIL", str(path), line, relation_id, "`evidence` must be a non-empty list")
            continue
        for index, item in enumerate(evidence):
            if not isinstance(item, dict):
                add(findings, "FAIL", str(path), line, relation_id, f"evidence[{index}] must be an object")
                continue
            source_id = item.get("source_id")
            if source_id not in sources:
                add(findings, "FAIL", str(path), line, relation_id, f"evidence[{index}].source_id not present in source inventory")
            if not isinstance(item.get("path"), str) or not item.get("path"):
                add(findings, "FAIL", str(path), line, relation_id, f"evidence[{index}].path is required")
            if "lines" in item and item.get("lines") not in ("", None) and parse_line_range(item.get("lines")) is None:
                add(findings, "FAIL", str(path), line, relation_id, f"evidence[{index}].lines must be N or N-M")
            if not isinstance(item.get("summary"), str) or not item.get("summary").strip():
                add(findings, "WARN", str(path), line, relation_id, f"evidence[{index}].summary should be non-empty")
        if not is_number_0_to_1(row.get("confidence")):
            add(findings, "FAIL", str(path), line, relation_id, "`confidence` must be a number from 0 to 1")
    return by_id


def validate_signals(
    rows: list[dict[str, Any]],
    path: Path,
    project_id: str | None,
    sources: dict[str, dict[str, Any]],
    entities: dict[str, dict[str, Any]],
    findings: list[Finding],
    relations: dict[str, dict[str, Any]] | None = None,
) -> dict[str, int]:
    relations = relations or {}
    by_id: set[str] = set()
    by_attribute: dict[str, int] = {}
    for row in rows:
        line = row.get("_line")
        signal_id_value = row.get("signal_id")
        signal_id = signal_id_value if isinstance(signal_id_value, str) and signal_id_value else "<missing>"
        missing = sorted(SIGNAL_REQUIRED - set(row))
        if missing:
            add(findings, "FAIL", str(path), line, signal_id, f"signal missing fields: {', '.join(missing)}")
        for field in ("signal_id", "project", "attribute", "extractor"):
            if not isinstance(row.get(field), str) or not row.get(field):
                add(findings, "FAIL", str(path), line, signal_id, f"`{field}` must be a non-empty string")
        if signal_id != "<missing>" and signal_id in by_id:
            add(findings, "FAIL", str(path), line, signal_id, "duplicate signal_id")
        elif signal_id != "<missing>":
            by_id.add(signal_id)
        if project_id and row.get("project") != project_id:
            add(findings, "FAIL", str(path), line, signal_id, "`project` does not match manifest project.id")
        axis = row.get("axis")
        if not isinstance(axis, int) or isinstance(axis, bool) or axis not in {2, 3}:
            add(findings, "FAIL", str(path), line, signal_id, "`axis` must be integer 2 or 3")
        if not is_number_0_to_1(row.get("confidence")):
            add(findings, "FAIL", str(path), line, signal_id, "`confidence` must be a number from 0 to 1")
        if not isinstance(row.get("evidence"), dict):
            add(findings, "FAIL", str(path), line, signal_id, "`evidence` must be an object")
        anchor = row.get("anchor")
        if not isinstance(anchor, dict):
            add(findings, "FAIL", str(path), line, signal_id, "`anchor` must be an object")
            continue
        source_id = anchor.get("source_id")
        entity_id = anchor.get("entity_id")
        relation_id = anchor.get("relation_id")
        if source_id not in (None, ""):
            if not isinstance(source_id, str):
                add(findings, "FAIL", str(path), line, signal_id, "anchor.source_id must be a string")
            elif source_id not in sources:
                add(findings, "FAIL", str(path), line, signal_id, "anchor.source_id not present in source inventory")
        if entity_id not in (None, ""):
            if not isinstance(entity_id, str):
                add(findings, "FAIL", str(path), line, signal_id, "anchor.entity_id must be a string")
            elif entity_id not in entities:
                add(findings, "FAIL", str(path), line, signal_id, "anchor.entity_id not present in entity index")
        if relation_id not in (None, ""):
            if not isinstance(relation_id, str):
                add(findings, "FAIL", str(path), line, signal_id, "anchor.relation_id must be a string")
            elif relation_id not in relations:
                add(findings, "FAIL", str(path), line, signal_id, "anchor.relation_id not present in relation graph")
        attribute = str(row.get("attribute", "<missing>"))
        by_attribute[attribute] = by_attribute.get(attribute, 0) + 1
    return by_attribute


def main() -> int:
    args = parse_args()
    bundle = args.bundle
    findings: list[Finding] = []

    if not bundle.exists() or not bundle.is_dir():
        add(findings, "FAIL", str(bundle), None, None, "bundle directory does not exist")
    for filename in REQUIRED_FILES:
        if not (bundle / filename).exists():
            add(findings, "FAIL", str(bundle / filename), None, None, "required analyzer artifact is missing")

    manifest_path = bundle / "project_manifest.json"
    source_path = bundle / "source_inventory.jsonl"
    entity_path = bundle / "entity_index.jsonl"
    relation_path = bundle / "relation_graph.jsonl"
    report_path = bundle / "analyzer_report.md"

    manifest = load_json(manifest_path, findings) if manifest_path.exists() else None
    source_set_ids = validate_manifest(manifest_path, manifest, findings)
    project_id = None
    if isinstance(manifest, dict) and isinstance(manifest.get("project"), dict):
        project_id = manifest["project"].get("id")
    source_rows = load_jsonl(source_path, findings) if source_path.exists() else []
    entity_rows = load_jsonl(entity_path, findings) if entity_path.exists() else []
    relation_rows = load_jsonl(relation_path, findings) if relation_path.exists() else []

    sources = validate_sources(source_rows, source_path, args.repo_root, source_set_ids, findings)
    entities = validate_entities(entity_rows, entity_path, sources, findings)
    relations = validate_relations(relation_rows, relation_path, sources, entities, findings)
    signal_path = bundle / "signal_index.jsonl"
    signal_rows = load_jsonl(signal_path, findings) if signal_path.exists() else []
    signal_counts = (
        validate_signals(signal_rows, signal_path, project_id, sources, entities, findings, relations=relations)
        if signal_path.exists()
        else {}
    )

    if report_path.exists() and len(report_path.read_text(encoding="utf-8", errors="replace").strip()) < 80:
        add(findings, "WARN", str(report_path), None, None, "analyzer_report.md is very short")

    fail_count = sum(1 for finding in findings if finding.severity == "FAIL")
    warn_count = sum(1 for finding in findings if finding.severity == "WARN")
    summary = {
        "bundle": str(bundle),
        "sources": len(sources),
        "entities": len(entities),
        "relations": len(relations),
        "signals": len(signal_rows),
        "signal_counts": dict(sorted(signal_counts.items())),
        "fails": fail_count,
        "warnings": warn_count,
        "findings": [asdict(finding) for finding in findings],
    }

    print(f"Bundle: {bundle}")
    print(f"Sources: {len(sources)}  Entities: {len(entities)}  Relations: {len(relations)}")
    if signal_path.exists():
        print(f"Signals: {len(signal_rows)}  Attributes: {dict(sorted(signal_counts.items()))}")
    print(f"FAIL: {fail_count}  WARN: {warn_count}")
    for finding in findings[:100]:
        loc = f"{finding.file}:{finding.line}" if finding.line else finding.file
        item = f" [{finding.item_id}]" if finding.item_id else ""
        print(f"{finding.severity} {loc}{item}: {finding.message}")
    if len(findings) > 100:
        print(f"... {len(findings) - 100} additional findings omitted")

    if args.json_report:
        args.json_report.parent.mkdir(parents=True, exist_ok=True)
        args.json_report.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if fail_count:
        return 1
    if args.fail_on_warn and warn_count:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
