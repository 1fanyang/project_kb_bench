#!/usr/bin/env python3
"""Run Codex-based baseline predictors for benchmark JSONL files.

Baselines:
- oracle: provide gold evidence snippets to Codex and copy that evidence into
  the prediction output.
- grep-agent: provide only the repository path(s); Codex must use basic shell
  search/read commands to find evidence and answer.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "schemas" / "baseline-prediction.schema.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Codex baseline predictors.")
    subparsers = parser.add_subparsers(dest="baseline", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("benchmark", type=Path)
    common.add_argument("--output", type=Path, required=True)
    common.add_argument("--repo-root", type=Path, default=Path.cwd())
    common.add_argument("--model", default=None)
    common.add_argument("--limit", type=int)
    common.add_argument("--case-id", action="append", dest="case_ids")
    common.add_argument("--resume", action="store_true")
    common.add_argument("--dry-run-prompts-dir", type=Path)
    common.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)

    oracle = subparsers.add_parser(
        "oracle",
        parents=[common],
        help="Gold evidence + Codex answer generation baseline.",
    )
    oracle.add_argument(
        "--snippet-context",
        type=int,
        default=0,
        help="Extra lines around each gold evidence range.",
    )

    grep = subparsers.add_parser(
        "grep-agent",
        parents=[common],
        help="Repository path + basic grep/sed/nl Codex agent baseline.",
    )
    grep.add_argument(
        "--repo-path",
        action="append",
        required=True,
        help="Repository path visible to the agent. Repeat for multiple roots.",
    )
    grep.add_argument(
        "--allow-nl",
        action="store_true",
        help="Mention nl -ba as an allowed line-number inspection command.",
    )

    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{lineno}: row must be an object")
        rows.append(row)
    return rows


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def existing_case_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        str(row.get("case_id"))
        for row in load_jsonl(path)
        if isinstance(row.get("case_id"), str)
    }


def parse_line_range(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, str) or not value:
        return None
    parts = value.split("-", 1)
    try:
        start = int(parts[0])
        end = int(parts[1]) if len(parts) == 2 else start
    except ValueError:
        return None
    if start <= 0 or end < start:
        return None
    return start, end


def read_snippet(repo_root: Path, path_value: str, lines_value: Any, context: int = 0) -> str:
    line_range = parse_line_range(lines_value)
    source_path = Path(path_value)
    if not source_path.is_absolute():
        source_path = repo_root / source_path
    if line_range is None or not source_path.exists():
        return ""
    lines = source_path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(1, line_range[0] - context)
    end = min(len(lines), line_range[1] + context)
    return "\n".join(lines[start - 1 : end])


def evidence_with_snippets(
    benchmark_row: dict[str, Any], repo_root: Path, context: int = 0
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for rank, item in enumerate(benchmark_row.get("evidence", []), 1):
        if not isinstance(item, dict):
            continue
        copied = {
            "rank": rank,
            "path": item.get("path", ""),
            "source_id": item.get("source_id", ""),
            "lines": item.get("lines", ""),
            "evidence_id": item.get("evidence_id", ""),
            "statement": item.get("statement", ""),
        }
        copied["text"] = read_snippet(
            repo_root, str(item.get("path", "")), item.get("lines"), context=context
        )
        evidence.append(copied)
    return evidence


def build_oracle_prompt(benchmark_row: dict[str, Any], evidence: list[dict[str, Any]] | None = None) -> str:
    evidence = evidence if evidence is not None else [
        item for item in benchmark_row.get("evidence", []) if isinstance(item, dict)
    ]
    evidence_blocks = []
    for item in evidence:
        citation = f"{item.get('path')}:{item.get('lines')}"
        evidence_blocks.append(
            "\n".join(
                [
                    f"- evidence_id: {item.get('evidence_id', '')}",
                    f"  citation: {citation}",
                    f"  statement: {item.get('statement', '')}",
                    "  text:",
                    "```text",
                    str(item.get("text", "")),
                    "```",
                ]
            )
        )

    return f"""You are generating a baseline prediction for a retrieval QA benchmark.

Case ID: {benchmark_row.get('case_id')}
Query: {benchmark_row.get('query')}

Use only the evidence below. Do not inspect the repository, do not use external
knowledge, and do not add citations that are not supported by the evidence.
Answer in Chinese unless the query strongly requires otherwise.

Evidence:
{chr(10).join(evidence_blocks)}

Return JSON only with:
- case_id: the exact case id
- pred_answer: concise final answer with path:line citations from the evidence
- evidence: an empty array; the runner will attach the oracle evidence
"""


def build_grep_agent_prompt(benchmark_row: dict[str, Any], repo_paths: list[str], allow_nl: bool = True) -> str:
    repo_text = "\n".join(f"- {path}" for path in repo_paths)
    allowed = "rg, sed -n, head, tail, wc"
    if allow_nl:
        allowed += ", nl -ba"
    return f"""You are generating a baseline prediction for a retrieval QA benchmark.

Case ID: {benchmark_row.get('case_id')}
Query: {benchmark_row.get('query')}

Repository roots you may inspect:
{repo_text}

Do not use the benchmark gold evidence, expected_answer, answer_rubric, metadata,
or validation reports. Use only the repository roots above and basic shell search
or file-reading commands: {allowed}. Prefer rg to locate files/symbols, then use
sed -n or nl -ba to capture exact evidence lines.

Return JSON only with:
- case_id: the exact case id
- pred_answer: concise final answer with path:line citations
- evidence: ranked evidence snippets you found. Each evidence item must include
  rank, path, source_id, lines, text, and score. Use an empty source_id if you
  cannot infer one, and score 0 if you do not have a numeric retrieval score.
"""


def codex_command(
    cwd: Path,
    schema_path: Path,
    output_path: Path,
    model: str | None = None,
    json_events: bool = False,
) -> list[str]:
    command = ["codex"]
    if model:
        command.extend(["--model", model])
    command.extend(
        [
        "--ask-for-approval",
        "never",
        "exec",
        ]
    )
    if json_events:
        command.append("--json")
    command.extend(
        [
        "--skip-git-repo-check",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--cd",
        str(cwd),
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(output_path),
        "-",
        ]
    )
    return command


def extract_codex_usage(stdout: str) -> dict[str, Any]:
    def normalize_direct_usage(raw_usage: dict[str, Any]) -> dict[str, Any]:
        usage = {
            key: value
            for key, value in raw_usage.items()
            if key
            in {
                "input_tokens",
                "cached_input_tokens",
                "output_tokens",
                "reasoning_output_tokens",
                "total_tokens",
            }
            and isinstance(value, int)
        }
        if "total_tokens" not in usage:
            input_tokens = usage.get("input_tokens")
            output_tokens = usage.get("output_tokens")
            if isinstance(input_tokens, int) and isinstance(output_tokens, int):
                usage["total_tokens"] = input_tokens + output_tokens
        return {
            "total_token_usage": usage,
            "last_token_usage": dict(usage),
        }

    latest: dict[str, Any] = {}
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
            latest = normalize_direct_usage(event["usage"])
            continue

        payload = event.get("payload") if event.get("type") == "event_msg" else event
        if not isinstance(payload, dict):
            continue

        if payload.get("type") != "token_count":
            continue
        info = payload.get("info")
        if not isinstance(info, dict):
            continue

        latest = dict(info)
        if payload.get("rate_limits") is not None:
            latest["rate_limits"] = payload.get("rate_limits")
    return latest


def run_codex(prompt: str, args: argparse.Namespace, output_path: Path) -> dict[str, Any]:
    command = codex_command(
        cwd=args.repo_root,
        schema_path=args.schema,
        output_path=output_path,
        model=args.model,
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
            f"codex exec failed with exit status {completed.returncode}\n{completed.stderr}"
        )
    try:
        return json.loads(output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"codex output was not valid JSON: {output_path}") from exc


def build_prediction_row(
    benchmark_row: dict[str, Any],
    model_json: dict[str, Any],
    evidence_source: str,
    repo_root: Path,
    snippet_context: int = 0,
) -> dict[str, Any]:
    prediction = {
        "case_id": benchmark_row.get("case_id"),
        "pred_answer": str(model_json.get("pred_answer", "")),
    }
    if evidence_source == "gold":
        prediction["evidence"] = evidence_with_snippets(
            benchmark_row, repo_root, context=snippet_context
        )
    else:
        evidence = model_json.get("evidence", [])
        prediction["evidence"] = evidence if isinstance(evidence, list) else []
    return prediction


def selected_rows(rows: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    wanted = set(args.case_ids or [])
    if wanted:
        rows = [row for row in rows if str(row.get("case_id")) in wanted]
    if args.limit is not None:
        rows = rows[: args.limit]
    return rows


def write_dry_run_prompt(directory: Path, benchmark_row: dict[str, Any], prompt: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    case_id = str(benchmark_row.get("case_id"))
    (directory / f"{case_id}.prompt.md").write_text(prompt, encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    rows = selected_rows(load_jsonl(args.benchmark), args)
    done = existing_case_ids(args.output) if args.resume else set()
    if args.output.exists() and not args.resume and not args.dry_run_prompts_dir:
        args.output.unlink()

    with tempfile.TemporaryDirectory(prefix="codex-baseline-") as tmp:
        tmpdir = Path(tmp)
        for row in rows:
            case_id = str(row.get("case_id"))
            if case_id in done:
                continue

            if args.baseline == "oracle":
                evidence = evidence_with_snippets(
                    row, args.repo_root, context=args.snippet_context
                )
                prompt = build_oracle_prompt(row, evidence=evidence)
                evidence_source = "gold"
            elif args.baseline == "grep-agent":
                prompt = build_grep_agent_prompt(
                    row,
                    repo_paths=args.repo_path,
                    allow_nl=args.allow_nl,
                )
                evidence_source = "model"
            else:
                raise AssertionError(f"unknown baseline: {args.baseline}")

            if args.dry_run_prompts_dir:
                write_dry_run_prompt(args.dry_run_prompts_dir, row, prompt)
                continue

            output_path = tmpdir / f"{case_id}.json"
            model_json = run_codex(prompt, args, output_path)
            prediction = build_prediction_row(
                benchmark_row=row,
                model_json=model_json,
                evidence_source=evidence_source,
                repo_root=args.repo_root,
                snippet_context=getattr(args, "snippet_context", 0),
            )
            append_jsonl(args.output, prediction)
            print(f"Wrote {case_id}", flush=True)
    return 0


def main() -> int:
    args = parse_args()
    try:
        return run(args)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
