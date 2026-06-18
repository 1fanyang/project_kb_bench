import argparse
import copy
import json
from pathlib import Path


def load_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def row_source_ids(row):
    return {
        evidence["source_id"]
        for evidence in row.get("evidence", [])
        if isinstance(evidence, dict) and evidence.get("source_id")
    }


def row_paths(row):
    return {
        evidence["path"]
        for evidence in row.get("evidence", [])
        if isinstance(evidence, dict) and evidence.get("path")
    }


def matching_signals(row, signals):
    source_ids = row_source_ids(row)
    paths = row_paths(row)
    matches = []
    for signal in signals:
        anchor = signal.get("anchor", {}) if isinstance(signal, dict) else {}
        if not isinstance(anchor, dict):
            continue
        if anchor.get("source_id") in source_ids or anchor.get("path") in paths:
            matches.append(signal)
    return matches


def stamp_row(row, signals):
    stamped = copy.deepcopy(row)
    stamped.setdefault("answerability", "answerable")

    layer = stamped.get("layer", {})
    axis1_layer = layer.get("code", "L1") if isinstance(layer, dict) else "L1"
    axis2_attributes = set()
    axis3_attributes = set()
    claim_sources = {}

    for signal in matching_signals(row, signals):
        attribute = signal.get("attribute")
        if not attribute:
            continue
        axis = signal.get("axis")
        if axis == 2:
            axis2_attributes.add(attribute)
        elif axis == 3:
            axis3_attributes.add(attribute)
        else:
            continue

        signal_id = signal.get("signal_id")
        if signal_id:
            claim_sources.setdefault(attribute, set()).add(signal_id)

    stamped["difficulty"] = {
        "axis1_layer": axis1_layer,
        "axis2_retrieval": sorted(axis2_attributes),
        "axis3_reasoning": sorted(axis3_attributes),
        "claim_sources": {
            attribute: sorted(signal_ids)
            for attribute, signal_ids in sorted(claim_sources.items())
        },
    }
    return stamped


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Stamp v1 benchmark rows with v1.1 candidate difficulty metadata."
    )
    parser.add_argument("benchmark", type=Path)
    parser.add_argument("--context-bundle", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    rows = load_jsonl(args.benchmark)
    signals = load_jsonl(args.context_bundle / "signal_index.jsonl")
    stamped = [stamp_row(row, signals) for row in rows]
    write_jsonl(args.output, stamped)
    print(f"Wrote {len(stamped)} stamped rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
