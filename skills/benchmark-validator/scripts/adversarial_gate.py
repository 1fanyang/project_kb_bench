#!/usr/bin/env python3
"""Run or dry-run matched adversarial gates for v1.1 benchmark claims."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ATTRIBUTE_BASELINES = {
    "long_tail": "closed_book_llm",
    "distracting_info": "top_1_dense_only",
    "version_fork": "single_source_set_retrieval",
    "non_code_anchor": "code_only_retrieval",
    "false_premise": "closed_book_llm",
    "doc_code_divergence": "doc_only_retrieval",
    "conditional_behavior": "top_1_dense_only",
    "negative_evidence": "closed_book_llm",
    "implicit_domain_knowledge": "oracle_evidence_no_reasoning_llm",
    "quantitative_aggregation": "top_1_dense_only",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate v1.1 adversarial gate claims.")
    parser.add_argument("benchmark", type=Path)
    parser.add_argument("--output-jsonl", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--judge-provider", choices=["command", "deepseek"])
    parser.add_argument("--judge-model", default="deepseek-v4-pro")
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def row_claims(row: dict[str, Any]) -> list[str]:
    difficulty = row.get("difficulty")
    if not isinstance(difficulty, dict):
        return []
    claims: list[str] = []
    for field in ("axis2_retrieval", "axis3_reasoning"):
        values = difficulty.get(field, [])
        if isinstance(values, list):
            claims.extend(str(value) for value in values if isinstance(value, str))
    return claims


def dry_run_record(row: dict[str, Any], attribute: str, judge_model: str) -> dict[str, Any]:
    baseline = ATTRIBUTE_BASELINES.get(attribute, "closed_book_llm")
    return {
        "case_id": row.get("case_id"),
        "attribute": attribute,
        "baseline": baseline,
        "status": "skipped_no_provider",
        "confirmed": None,
        "judge_provider": None,
        "judge_model": judge_model,
        "cache_key": f"{row.get('case_id')}:{attribute}:{baseline}:{judge_model}:dry-run-v1",
        "rationale": "Dry run only; no adversarial baseline or judge was invoked.",
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def run(args: argparse.Namespace) -> int:
    benchmark_rows = load_jsonl(args.benchmark)
    records: list[dict[str, Any]] = []
    for row in benchmark_rows:
        for attribute in row_claims(row):
            records.append(dry_run_record(row, attribute, args.judge_model))
    write_jsonl(args.output_jsonl, records)
    print(f"Wrote {len(records)} adversarial gate records to {args.output_jsonl}")
    return 0


def main() -> int:
    args = parse_args()
    if not args.dry_run and not args.judge_provider:
        print("ERROR: non-dry-run mode requires --judge-provider", flush=True)
        return 2
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
