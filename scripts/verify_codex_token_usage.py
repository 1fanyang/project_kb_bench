#!/usr/bin/env python3
"""Verify Codex token usage accounting on one benchmark case.

This is a small diagnostic runner. It executes the same benchmark case with
the oracle and grep-agent baseline prompts, enables Codex's JSON event stream,
and compares the final token_count usage objects.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_codex_baselines as baselines  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run one benchmark case with oracle and grep-agent Codex baselines "
            "and compare token_count usage from codex exec --json."
        )
    )
    parser.add_argument("benchmark", type=Path)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root used as codex --cd and for oracle snippet reads.",
    )
    parser.add_argument(
        "--repo-path",
        action="append",
        required=True,
        help="Repository path visible to the grep-agent baseline. Repeat for multiple roots.",
    )
    parser.add_argument("--case-id", help="Benchmark case id. Defaults to the first row.")
    parser.add_argument("--model", default=None)
    parser.add_argument("--schema", type=Path, default=baselines.DEFAULT_SCHEMA)
    parser.add_argument("--snippet-context", type=int, default=0)
    parser.add_argument("--allow-nl", action="store_true", default=True)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument(
        "--allow-missing-usage",
        action="store_true",
        help="Exit 0 even if codex --json emits no token_count event.",
    )
    return parser.parse_args()


def select_case(rows: list[dict[str, Any]], case_id: str | None) -> dict[str, Any]:
    if not rows:
        raise ValueError("benchmark has no rows")
    if case_id is None:
        return rows[0]
    for row in rows:
        if str(row.get("case_id")) == case_id:
            return row
    raise ValueError(f"case id not found: {case_id}")


def usage_event_count(stdout: str) -> int:
    count = 0
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "turn.completed" and isinstance(
            event.get("usage"), dict
        ):
            count += 1
            continue
        payload = event.get("payload") if event.get("type") == "event_msg" else event
        if isinstance(payload, dict) and payload.get("type") == "token_count":
            count += 1
    return count


def token_value(usage: dict[str, Any], group: str, field: str) -> int | None:
    values = usage.get(group)
    if not isinstance(values, dict):
        return None
    value = values.get(field)
    return value if isinstance(value, int) else None


def summarize_run(
    baseline: str,
    prompt: str,
    usage: dict[str, Any],
    model_json: dict[str, Any],
    token_count_events_seen: int,
) -> dict[str, Any]:
    return {
        "baseline": baseline,
        "prompt_chars": len(prompt),
        "usage_events_seen": token_count_events_seen,
        "token_count_events_seen": token_count_events_seen,
        "total_tokens": token_value(usage, "total_token_usage", "total_tokens"),
        "input_tokens": token_value(usage, "total_token_usage", "input_tokens"),
        "cached_input_tokens": token_value(
            usage, "total_token_usage", "cached_input_tokens"
        ),
        "output_tokens": token_value(usage, "total_token_usage", "output_tokens"),
        "reasoning_output_tokens": token_value(
            usage, "total_token_usage", "reasoning_output_tokens"
        ),
        "last_total_tokens": token_value(usage, "last_token_usage", "total_tokens"),
        "model_context_window": usage.get("model_context_window"),
        "model_case_id": model_json.get("case_id"),
        "pred_answer_chars": len(str(model_json.get("pred_answer", ""))),
        "model_evidence_items": len(model_json.get("evidence", []))
        if isinstance(model_json.get("evidence"), list)
        else None,
        "raw_usage": usage,
    }


def build_comparison_report(
    benchmark: Path,
    case_id: str,
    model: str | None,
    repo_paths: list[str],
    oracle_run: dict[str, Any],
    grep_run: dict[str, Any],
) -> dict[str, Any]:
    oracle_total = oracle_run.get("total_tokens")
    grep_total = grep_run.get("total_tokens")
    if isinstance(oracle_total, int) and isinstance(grep_total, int):
        delta = grep_total - oracle_total
        ratio = round(grep_total / oracle_total, 3) if oracle_total else None
        oracle_less = oracle_total < grep_total
    else:
        delta = None
        ratio = None
        oracle_less = None

    return {
        "mode": "codex_token_usage_verification",
        "benchmark": str(benchmark),
        "case_id": case_id,
        "model": model,
        "repo_paths": repo_paths,
        "runs": {
            "oracle": oracle_run,
            "grep-agent": grep_run,
        },
        "comparison": {
            "oracle_total_tokens": oracle_total,
            "grep_agent_total_tokens": grep_total,
            "grep_minus_oracle_total_tokens": delta,
            "grep_to_oracle_total_token_ratio": ratio,
            "oracle_less_than_grep": oracle_less,
        },
    }


def run_codex_trial(
    baseline: str,
    prompt: str,
    args: argparse.Namespace,
    output_path: Path,
) -> dict[str, Any]:
    command = baselines.codex_command(
        cwd=args.repo_root,
        schema_path=args.schema,
        output_path=output_path,
        model=args.model,
        json_events=True,
    )
    completed = subprocess.run(
        command,
        input=prompt,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{baseline} codex exec failed with exit status "
            f"{completed.returncode}\n{completed.stderr}"
        )
    try:
        model_json = json.loads(output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{baseline} codex output was not valid JSON: {output_path}") from exc

    usage = baselines.extract_codex_usage(completed.stdout)
    return summarize_run(
        baseline=baseline,
        prompt=prompt,
        usage=usage,
        model_json=model_json,
        token_count_events_seen=usage_event_count(completed.stdout),
    )


def make_markdown(report: dict[str, Any]) -> str:
    comparison = report["comparison"]
    runs = report["runs"]
    lines = [
        "# Codex Token Usage Verification",
        "",
        f"- Case ID: `{report['case_id']}`",
        f"- Model: `{report['model'] or 'default'}`",
        f"- Oracle total tokens: {comparison['oracle_total_tokens']}",
        f"- Grep-agent total tokens: {comparison['grep_agent_total_tokens']}",
        f"- Delta: {comparison['grep_minus_oracle_total_tokens']}",
        f"- Ratio: {comparison['grep_to_oracle_total_token_ratio']}",
        f"- Oracle less than grep-agent: {comparison['oracle_less_than_grep']}",
        "",
        "## Runs",
        "",
    ]
    for label in ("oracle", "grep-agent"):
        run = runs[label]
        lines.extend(
            [
                f"### {label}",
                "",
                f"- Prompt chars: {run['prompt_chars']}",
                f"- Usage events seen: {run['usage_events_seen']}",
                f"- Total tokens: {run['total_tokens']}",
                f"- Input tokens: {run['input_tokens']}",
                f"- Cached input tokens: {run['cached_input_tokens']}",
                f"- Output tokens: {run['output_tokens']}",
                f"- Reasoning output tokens: {run['reasoning_output_tokens']}",
                f"- Last total tokens: {run['last_total_tokens']}",
                f"- Model context window: {run['model_context_window']}",
                "",
            ]
        )
    return "\n".join(lines)


def write_outputs(report: dict[str, Any], args: argparse.Namespace) -> None:
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(make_markdown(report), encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    row = select_case(baselines.load_jsonl(args.benchmark), args.case_id)
    case_id = str(row.get("case_id"))
    evidence = baselines.evidence_with_snippets(
        row, args.repo_root, context=args.snippet_context
    )
    oracle_prompt = baselines.build_oracle_prompt(row, evidence=evidence)
    grep_prompt = baselines.build_grep_agent_prompt(
        row, repo_paths=args.repo_path, allow_nl=args.allow_nl
    )

    with tempfile.TemporaryDirectory(prefix="codex-token-usage-") as tmp:
        tmpdir = Path(tmp)
        oracle_run = run_codex_trial(
            "oracle", oracle_prompt, args, tmpdir / f"{case_id}.oracle.json"
        )
        grep_run = run_codex_trial(
            "grep-agent", grep_prompt, args, tmpdir / f"{case_id}.grep-agent.json"
        )

    report = build_comparison_report(
        benchmark=args.benchmark,
        case_id=case_id,
        model=args.model,
        repo_paths=args.repo_path,
        oracle_run=oracle_run,
        grep_run=grep_run,
    )
    write_outputs(report, args)

    missing = [
        label
        for label, item in report["runs"].items()
        if item["usage_events_seen"] == 0 or item["total_tokens"] is None
    ]
    return 0 if args.allow_missing_usage or not missing else 2


def main() -> int:
    args = parse_args()
    try:
        return run(args)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
