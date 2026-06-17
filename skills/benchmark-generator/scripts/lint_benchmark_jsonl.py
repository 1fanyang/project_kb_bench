#!/usr/bin/env python3
"""Lint v1 benchmark JSONL rows produced from analyzer context bundles."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = {
    "case_id",
    "project",
    "layer",
    "query",
    "query_rewrite",
    "answer_type",
    "references",
    "evidence",
    "expected_answer",
    "answer_rubric",
}

ANSWER_TYPES = {
    "yes_no": "是否判断",
    "mechanism": "机制解释",
    "fact_check": "事实核查",
    "comparison": "对比分析",
    "location": "位置定位",
    "procedure": "操作流程",
    "negative": "无答案或证据不足",
    "synthesis": "综合归纳",
}
SCHEMA_VERSIONS = {"v1", "v1.1"}
CONDITIONAL_EVIDENCE_ROLES = {"trigger_condition", "branch", "guard", "predicate", "state"}
STRUCTURAL_REASON_MESSAGES = {
    "MISSING_DIFFICULTY": "`difficulty` is required in v1.1 mode",
    "DIFFICULTY_LAYER_MISMATCH": "`difficulty.axis1_layer` must match `layer.code`",
    "INSUFFICIENT_DIFFICULTY_SIGNALS": "v1.1 rows need at least two difficulty signals across axes",
    "L2_SINGLE_SOURCE": "L2 rows need evidence from at least two source_id values",
    "L3_SINGLE_SOURCE": "L3 rows need evidence from at least two source_id values",
    "L3_NO_ATOM_CHAIN": "L3 rows need at least one required atom with depends_on",
    "CONDITIONAL_BEHAVIOR_WITHOUT_ROLE": "`conditional_behavior` needs guard/branch/predicate/state evidence",
    "FORBIDDEN_ATOMS_REQUIRED": "yes_no, fact_check, and false_premise rows need forbidden_atoms",
    "FILE_ANCHOR_LEAK": "query names an evidence file without file_anchor_required tag",
}

ATOM_ROLES = {
    "conclusion",
    "evidence_fact",
    "reasoning",
    "boundary",
    "location",
    "procedure_step",
    "comparison_point",
}

MATCH_TYPES = {
    "semantic_yes_no",
    "semantic_fact",
    "semantic_reasoning",
    "path_or_symbol",
    "numeric_or_version",
    "list_set",
    "semantic_contradiction",
}

CITATION_REQUIRED_VALUES = {"always", "never", "when_query_requests_evidence"}
CITATION_GRANULARITY_VALUES = {"path_line", "path_only", "source_only"}
RUBRIC_LIKE_PATTERNS = (
    "应说明",
    "应把",
    "应围绕 query 指定的上下文",
    "检索并串联这些关键证据",
    "答案需要说明",
    "如何支持或修正用户的假设",
)
QUERY_REWRITE_FORBIDDEN_PATTERNS = (
    "检索并回答",
    "验证假设",
    "优先参考实体",
    "范围约束",
    "需要定位触发条件",
    "状态/数据更新",
    "后续调用或消费关系",
    "不能只做符号定位",
    "回答应服务后续推理",
)
CHATTY_QUERY_PATTERNS = (
    "帮我",
    "我想",
    "我知道",
    "我在看",
    "我已经知道",
    "想看",
    "到底",
    "顺便",
    "吧",
    "不用泛泛",
)
CITATION_TRIGGER_PATTERNS = (
    "证据",
    "代码证据",
    "行号",
    "片段",
    "引用",
    "cite",
    "citation",
    "line",
    "proof",
)

LINES_RE = re.compile(r"^(\d+)(?:-(\d+))?$")
CITATION_RE = re.compile(r"[\w./@+-]+:\d+(?:-\d+)?")
CODE_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_:.>\\/-]*")


@dataclass
class Finding:
    severity: str
    file: str
    line: int | None
    case_id: str | None
    message: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lint benchmark JSONL row schema, evidence, and atomized rubrics.")
    parser.add_argument("jsonl", nargs="+", type=Path, help="Benchmark JSONL file(s)")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Base path for relative source paths")
    parser.add_argument("--json-report", type=Path, help="Optional JSON report path")
    parser.add_argument("--fail-on-warn", action="store_true", help="Exit non-zero when WARN findings exist")
    parser.add_argument(
        "--schema-version",
        choices=sorted(SCHEMA_VERSIONS),
        default="v1",
        help="Lint rules to enforce. v1 keeps legacy compatibility; v1.1 enables structural gate checks.",
    )
    return parser.parse_args()


def add(findings: list[Finding], severity: str, file: str, line: int | None, case_id: str | None, message: str) -> None:
    findings.append(Finding(severity, file, line, case_id, message))


def is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def parse_line_range(value: Any) -> tuple[int, int] | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        return None
    match = LINES_RE.match(value)
    if not match:
        return None
    start = int(match.group(1))
    end = int(match.group(2) or start)
    if start <= 0 or end < start:
        return None
    return start, end


def resolve_path(value: str, repo_root: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return repo_root / path


def label_code(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("code", "<missing>"))
    return str(value)


def row_tags(row: dict[str, Any]) -> set[str]:
    tags = row.get("tags", [])
    return {str(item) for item in tags if isinstance(item, str)} if isinstance(tags, list) else set()


def difficulty_attributes(row: dict[str, Any]) -> list[str]:
    difficulty = row.get("difficulty")
    if not isinstance(difficulty, dict):
        return []
    attrs: list[str] = []
    for key in ("axis2_retrieval", "axis3_reasoning"):
        values = difficulty.get(key, [])
        if isinstance(values, list):
            attrs.extend(str(value) for value in values if isinstance(value, str))
    return attrs


def evidence_source_ids(row: dict[str, Any]) -> set[str]:
    evidence = row.get("evidence", [])
    if not isinstance(evidence, list):
        return set()
    return {
        str(item.get("source_id"))
        for item in evidence
        if isinstance(item, dict) and is_nonempty_string(item.get("source_id"))
    }


def has_atom_dependency(row: dict[str, Any]) -> bool:
    rubric = row.get("answer_rubric", {})
    atoms = rubric.get("required_atoms", []) if isinstance(rubric, dict) else []
    if not isinstance(atoms, list):
        return False
    for atom in atoms:
        if isinstance(atom, dict) and isinstance(atom.get("depends_on"), list) and atom["depends_on"]:
            return True
    return False


def has_conditional_evidence_role(row: dict[str, Any]) -> bool:
    evidence = row.get("evidence", [])
    if not isinstance(evidence, list):
        return False
    return any(
        isinstance(item, dict) and item.get("role") in CONDITIONAL_EVIDENCE_ROLES
        for item in evidence
    )


def query_mentions_evidence_file(row: dict[str, Any]) -> bool:
    query = str(row.get("query", ""))
    evidence = row.get("evidence", [])
    if not isinstance(evidence, list):
        return False
    for item in evidence:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", ""))
        if path and path in query:
            return True
        filename = Path(path).name
        if filename and "." in filename and filename in query:
            return True
    return False


def load_rows(path: Path, findings: list[Finding]) -> list[dict[str, Any]]:
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
        row["_file"] = str(path)
        row["_line"] = lineno
        rows.append(row)
    return rows


def validate_label_object(row: dict[str, Any], field: str, findings: list[Finding]) -> None:
    value = row.get(field)
    case_id = str(row.get("case_id", "<missing>"))
    if not isinstance(value, dict):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, f"`{field}` must be an object with code and zh")
        return
    if not is_nonempty_string(value.get("code")) or not is_nonempty_string(value.get("zh")):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, f"`{field}.code` and `{field}.zh` are required")


def validate_answer_type(row: dict[str, Any], findings: list[Finding]) -> None:
    validate_label_object(row, "answer_type", findings)
    answer_type = row.get("answer_type")
    if not isinstance(answer_type, dict):
        return
    code = answer_type.get("code")
    zh = answer_type.get("zh")
    if code not in ANSWER_TYPES:
        add(findings, "WARN", row["_file"], row["_line"], str(row.get("case_id")), f"non-standard answer_type.code: {code}")
    elif zh != ANSWER_TYPES[code]:
        add(findings, "WARN", row["_file"], row["_line"], str(row.get("case_id")), f"answer_type.zh should be {ANSWER_TYPES[code]!r}")


def contains_citation_trigger(query: str) -> bool:
    query_lower = query.lower()
    return any(pattern.lower() in query_lower for pattern in CITATION_TRIGGER_PATTERNS)


def is_chatty_query(query: str) -> bool:
    return any(pattern in query for pattern in CHATTY_QUERY_PATTERNS)


def validate_query_rewrite(row: dict[str, Any], findings: list[Finding]) -> None:
    case_id = str(row.get("case_id", "<missing>"))
    query = str(row.get("query", ""))
    rewrite = str(row.get("query_rewrite", ""))
    if not is_nonempty_string(query):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`query` must be a non-empty string")
        return
    if not is_nonempty_string(rewrite):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`query_rewrite` must be a non-empty string")
        return
    if query.strip() == rewrite.strip() and is_chatty_query(query):
        add(findings, "WARN", row["_file"], row["_line"], case_id, "`query_rewrite` duplicates a chatty query")
    for pattern in QUERY_REWRITE_FORBIDDEN_PATTERNS:
        if pattern in rewrite:
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"`query_rewrite` contains hidden-context marker: {pattern}")
    query_tokens = set(CODE_TOKEN_RE.findall(query))
    for token in CODE_TOKEN_RE.findall(rewrite):
        if len(token) < 4 or token in query_tokens:
            continue
        if token.isupper() or "_" in token or "::" in token or "." in token:
            add(findings, "WARN", row["_file"], row["_line"], case_id, f"`query_rewrite` introduces technical token absent from query: {token}")


def validate_references(row: dict[str, Any], findings: list[Finding], repo_root: Path) -> set[str]:
    case_id = str(row.get("case_id", "<missing>"))
    references = row.get("references")
    reference_paths: set[str] = set()
    if not isinstance(references, list) or not references:
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`references` must be a non-empty list")
        return reference_paths
    for index, ref in enumerate(references):
        if not isinstance(ref, dict):
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"references[{index}] must be an object")
            continue
        source_id = ref.get("source_id")
        path = ref.get("path")
        if not is_nonempty_string(source_id) and not is_nonempty_string(path):
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"references[{index}] needs source_id or path")
        if is_nonempty_string(path):
            reference_paths.add(path)
            if not resolve_path(path, repo_root).exists():
                add(findings, "WARN", row["_file"], row["_line"], case_id, f"reference path does not exist: {path}")
        for recommended in ("repo_name", "source_type", "authority"):
            if recommended not in ref:
                add(findings, "WARN", row["_file"], row["_line"], case_id, f"references[{index}] missing recommended `{recommended}`")
    return reference_paths


def validate_evidence(row: dict[str, Any], findings: list[Finding], repo_root: Path, reference_paths: set[str]) -> set[str]:
    case_id = str(row.get("case_id", "<missing>"))
    evidence = row.get("evidence")
    evidence_ids: set[str] = set()
    if not isinstance(evidence, list) or not evidence:
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`evidence` must be a non-empty list")
        return evidence_ids
    for index, item in enumerate(evidence):
        if not isinstance(item, dict):
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"evidence[{index}] must be an object")
            continue
        evidence_id = item.get("evidence_id")
        if not is_nonempty_string(evidence_id):
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"evidence[{index}].evidence_id is required")
        elif evidence_id in evidence_ids:
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"duplicate evidence_id: {evidence_id}")
        else:
            evidence_ids.add(evidence_id)
        for field in ("source_id", "path", "role", "statement"):
            if not is_nonempty_string(item.get(field)):
                add(findings, "FAIL", row["_file"], row["_line"], case_id, f"evidence[{index}].{field} is required")
        if "lines" in item and item.get("lines") not in ("", None) and parse_line_range(item.get("lines")) is None:
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"evidence[{index}].lines must be N or N-M")
        path = item.get("path")
        if is_nonempty_string(path):
            if not resolve_path(path, repo_root).exists():
                add(findings, "WARN", row["_file"], row["_line"], case_id, f"evidence path does not exist: {path}")
            if reference_paths and path not in reference_paths:
                add(findings, "WARN", row["_file"], row["_line"], case_id, f"evidence path is not covered by references: {path}")
    return evidence_ids


def validate_expected_answer(row: dict[str, Any], findings: list[Finding]) -> None:
    case_id = str(row.get("case_id", "<missing>"))
    answer = row.get("expected_answer")
    if not is_nonempty_string(answer):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`expected_answer` must be a non-empty string")
        return
    if any(pattern in answer for pattern in RUBRIC_LIKE_PATTERNS):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`expected_answer` is rubric-like, not a direct answer")
    if len(answer.strip()) < 40:
        add(findings, "WARN", row["_file"], row["_line"], case_id, "`expected_answer` is short for a standard reference answer")
    answer_type = row.get("answer_type")
    if isinstance(answer_type, dict) and answer_type.get("code") == "yes_no":
        first_sentence = re.split(r"[。.!?？]", answer.strip(), maxsplit=1)[0]
        if not any(token in first_sentence for token in ("会", "不会", "无法判断", "不能确认", "可以", "不可以", "支持", "不支持")):
            add(findings, "WARN", row["_file"], row["_line"], case_id, "yes_no expected_answer should answer directly in the first sentence")
    citation_required_by_query = contains_citation_trigger(str(row.get("query", "")))
    if citation_required_by_query and not CITATION_RE.search(answer):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "query asks for evidence/citation but expected_answer has no path:line citation")


def validate_rubric(row: dict[str, Any], findings: list[Finding], evidence_ids: set[str]) -> None:
    case_id = str(row.get("case_id", "<missing>"))
    rubric = row.get("answer_rubric")
    if not isinstance(rubric, dict):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`answer_rubric` must be an object")
        return
    if not is_nonempty_string(rubric.get("answer_goal")):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`answer_rubric.answer_goal` is required")
    atoms = rubric.get("required_atoms")
    if not isinstance(atoms, list) or not atoms:
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`answer_rubric.required_atoms` must be a non-empty list")
        atoms = []
    atom_ids: set[str] = set()
    conclusion_seen = False
    for index, atom in enumerate(atoms):
        if not isinstance(atom, dict):
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"required_atoms[{index}] must be an object")
            continue
        atom_id = atom.get("id")
        if not is_nonempty_string(atom_id):
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"required_atoms[{index}].id is required")
        elif atom_id in atom_ids:
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"duplicate atom id: {atom_id}")
        else:
            atom_ids.add(atom_id)
        role = atom.get("role")
        if role not in ATOM_ROLES:
            add(findings, "WARN", row["_file"], row["_line"], case_id, f"required_atoms[{index}] has non-standard role: {role}")
        if role == "conclusion":
            conclusion_seen = True
        if atom.get("match_type") not in MATCH_TYPES:
            add(findings, "WARN", row["_file"], row["_line"], case_id, f"required_atoms[{index}] has non-standard match_type: {atom.get('match_type')}")
        if not is_nonempty_string(atom.get("statement")):
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"required_atoms[{index}].statement is required")
        weight = atom.get("weight")
        if not isinstance(weight, (int, float)) or weight <= 0:
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"required_atoms[{index}].weight must be positive")
        atom_evidence = atom.get("evidence_ids", [])
        if not isinstance(atom_evidence, list):
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"required_atoms[{index}].evidence_ids must be a list")
            atom_evidence = []
        for evidence_id in atom_evidence:
            if evidence_id not in evidence_ids:
                add(findings, "FAIL", row["_file"], row["_line"], case_id, f"required_atoms[{index}] references unknown evidence_id: {evidence_id}")
    if not conclusion_seen:
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`required_atoms` must include at least one conclusion atom")

    for index, atom in enumerate(rubric.get("forbidden_atoms", []) or []):
        if not isinstance(atom, dict):
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"forbidden_atoms[{index}] must be an object")
            continue
        if not is_nonempty_string(atom.get("id")) or not is_nonempty_string(atom.get("statement")):
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"forbidden_atoms[{index}] needs id and statement")
        if atom.get("match_type") not in (None, "semantic_contradiction"):
            add(findings, "WARN", row["_file"], row["_line"], case_id, f"forbidden_atoms[{index}].match_type should be semantic_contradiction")
        if atom.get("severity") not in (None, "fatal", "major", "minor"):
            add(findings, "WARN", row["_file"], row["_line"], case_id, f"forbidden_atoms[{index}] has non-standard severity: {atom.get('severity')}")

    policy = rubric.get("citation_policy")
    if policy is None:
        return
    if not isinstance(policy, dict):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`citation_policy` must be an object")
        return
    if policy.get("required") not in CITATION_REQUIRED_VALUES:
        add(findings, "WARN", row["_file"], row["_line"], case_id, f"non-standard citation_policy.required: {policy.get('required')}")
    if policy.get("acceptable_granularity") not in CITATION_GRANULARITY_VALUES:
        add(findings, "WARN", row["_file"], row["_line"], case_id, f"non-standard citation granularity: {policy.get('acceptable_granularity')}")
    required_evidence = policy.get("required_evidence_ids", [])
    if not isinstance(required_evidence, list):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`citation_policy.required_evidence_ids` must be a list")
        return
    for evidence_id in required_evidence:
        if evidence_id not in evidence_ids:
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"citation_policy references unknown evidence_id: {evidence_id}")


def structural_gate_record(row: dict[str, Any]) -> dict[str, Any]:
    case_id = str(row.get("case_id", "<missing>"))
    layer = label_code(row.get("layer"))
    answer_type = label_code(row.get("answer_type"))
    answerability = str(row.get("answerability", "answerable"))
    difficulty = row.get("difficulty")
    reason_codes: list[str] = []

    if not isinstance(difficulty, dict):
        reason_codes.append("MISSING_DIFFICULTY")
        attrs: list[str] = []
    else:
        attrs = difficulty_attributes(row)
        if difficulty.get("axis1_layer") != layer:
            reason_codes.append("DIFFICULTY_LAYER_MISMATCH")

    if len(set(attrs + ([layer] if layer == "L3" else []))) < 2:
        reason_codes.append("INSUFFICIENT_DIFFICULTY_SIGNALS")

    source_ids = evidence_source_ids(row)
    if layer == "L2" and len(source_ids) < 2:
        reason_codes.append("L2_SINGLE_SOURCE")
    if layer == "L3":
        if len(source_ids) < 2:
            reason_codes.append("L3_SINGLE_SOURCE")
        if not has_atom_dependency(row):
            reason_codes.append("L3_NO_ATOM_CHAIN")

    if "conditional_behavior" in attrs and not has_conditional_evidence_role(row):
        reason_codes.append("CONDITIONAL_BEHAVIOR_WITHOUT_ROLE")

    rubric = row.get("answer_rubric", {})
    forbidden_atoms = rubric.get("forbidden_atoms", []) if isinstance(rubric, dict) else []
    if (
        answer_type in {"yes_no", "fact_check"}
        or answerability == "unanswerable_false_premise"
        or "false_premise" in attrs
    ) and not forbidden_atoms:
        reason_codes.append("FORBIDDEN_ATOMS_REQUIRED")

    if "file_anchor_required" not in row_tags(row) and query_mentions_evidence_file(row):
        reason_codes.append("FILE_ANCHOR_LEAK")

    return {
        "case_id": case_id,
        "pass": not reason_codes,
        "reason_codes": reason_codes,
        "reasons": [STRUCTURAL_REASON_MESSAGES[code] for code in reason_codes],
        "layer": layer,
        "answerability": answerability,
        "attributes": attrs,
    }


def validate_row(
    row: dict[str, Any],
    findings: list[Finding],
    repo_root: Path,
    seen_case_ids: set[str],
    schema_version: str = "v1",
) -> None:
    case_id = str(row.get("case_id", "<missing>"))
    missing = sorted(REQUIRED_FIELDS - set(row))
    if missing:
        add(findings, "FAIL", row["_file"], row["_line"], case_id, f"row missing fields: {', '.join(missing)}")
    if not is_nonempty_string(row.get("case_id")):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`case_id` is required")
    elif row["case_id"] in seen_case_ids:
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "duplicate case_id")
    else:
        seen_case_ids.add(row["case_id"])
    if not is_nonempty_string(row.get("project")):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`project` is required")
    validate_label_object(row, "layer", findings)
    if "capability" in row:
        validate_label_object(row, "capability", findings)
    validate_answer_type(row, findings)
    validate_query_rewrite(row, findings)
    reference_paths = validate_references(row, findings, repo_root)
    evidence_ids = validate_evidence(row, findings, repo_root, reference_paths)
    validate_expected_answer(row, findings)
    validate_rubric(row, findings, evidence_ids)
    if schema_version == "v1.1":
        record = structural_gate_record(row)
        for code in record["reason_codes"]:
            add(findings, "FAIL", row["_file"], row["_line"], case_id, STRUCTURAL_REASON_MESSAGES[code])


def main() -> int:
    args = parse_args()
    findings: list[Finding] = []
    seen_case_ids: set[str] = set()
    row_count = 0
    for path in args.jsonl:
        rows = load_rows(path, findings)
        row_count += len(rows)
        for row in rows:
            validate_row(row, findings, args.repo_root, seen_case_ids, schema_version=args.schema_version)

    fail_count = sum(1 for finding in findings if finding.severity == "FAIL")
    warn_count = sum(1 for finding in findings if finding.severity == "WARN")
    summary = {
        "files": [str(path) for path in args.jsonl],
        "rows": row_count,
        "fails": fail_count,
        "warnings": warn_count,
        "findings": [asdict(finding) for finding in findings],
    }

    print(f"Rows: {row_count}")
    print(f"FAIL: {fail_count}  WARN: {warn_count}")
    for finding in findings[:120]:
        loc = f"{finding.file}:{finding.line}" if finding.line else finding.file
        case = f" [{finding.case_id}]" if finding.case_id else ""
        print(f"{finding.severity} {loc}{case}: {finding.message}")
    if len(findings) > 120:
        print(f"... {len(findings) - 120} additional findings omitted")

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
