#!/usr/bin/env python3
"""Generate deterministic v1.1 release benchmark corpora from context bundles."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ANSWER_TYPE_ZH = {
    "yes_no": "是否判断",
    "mechanism": "机制解释",
    "fact_check": "事实核查",
    "comparison": "对比分析",
    "location": "位置定位",
    "procedure": "操作流程",
    "negative": "无答案或证据不足",
    "synthesis": "综合归纳",
}

LAYER_ZH = {
    "L1": "单源检索",
    "L2": "跨源核对",
    "L3": "多跳机制",
}

CAPABILITIES = [
    ("repo_structure_location", "项目结构定位"),
    ("doc_code_cross_check", "文档代码核对"),
    ("build_sim_verif_flow", "构建仿真验证流程"),
    ("mechanism_trace", "机制链路解释"),
    ("tests_debug_evidence", "测试与调试证据"),
    ("negative_insufficient_evidence", "负面与证据不足"),
]

ANSWERABILITY_PLAN = (
    ["unanswerable_missing_evidence"] * 30
    + ["answerable"] * 40
    + ["unanswerable_false_premise"] * 20
    + ["unanswerable_ambiguous"] * 10
    + ["answerable"] * 100
)

LAYER_PLAN = ["L1"] * 50 + ["L2"] * 90 + ["L3"] * 60

PREFERRED_ATTRIBUTE_GROUPS = [
    ("long_tail", "implicit_domain_knowledge"),
    ("distracting_info", "conditional_behavior"),
    ("non_code_anchor", "implicit_domain_knowledge"),
    ("long_tail", "doc_code_divergence"),
    ("distracting_info", "implicit_domain_knowledge"),
    ("long_tail", "conditional_behavior"),
]


@dataclass(frozen=True)
class Source:
    source_id: str
    project: str
    repo_name: str
    path: str
    source_type: str
    authority: str
    line_count: int


@dataclass(frozen=True)
class Signal:
    signal_id: str
    project: str
    axis: int
    attribute: str
    source_id: str
    path: str
    lines: str


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_line_start(lines: Any) -> int:
    text = str(lines or "1").strip()
    head = text.split("-", 1)[0]
    try:
        return max(1, int(head))
    except ValueError:
        return 1


def line_window(source: Source, preferred: Any, width: int = 3) -> str:
    if source.line_count <= 0:
        return "1"
    start = min(parse_line_start(preferred), source.line_count)
    end = min(source.line_count, start + width - 1)
    return str(start) if start == end else f"{start}-{end}"


def load_sources(bundle: Path, project: str, repo_root: Path) -> dict[str, Source]:
    sources: dict[str, Source] = {}
    for row in read_jsonl(bundle / "source_inventory.jsonl"):
        source_id = row.get("source_id")
        path = row.get("path")
        line_count = row.get("line_count")
        if (
            row.get("project") != project
            or not isinstance(source_id, str)
            or not isinstance(path, str)
            or not isinstance(line_count, int)
            or line_count <= 0
            or not (repo_root / path).exists()
        ):
            continue
        sources[source_id] = Source(
            source_id=source_id,
            project=project,
            repo_name=str(row.get("repo_name") or project),
            path=path,
            source_type=str(row.get("source_type") or "unknown"),
            authority=str(row.get("authority") or "primary_source"),
            line_count=line_count,
        )
    return sources


def load_signals(bundle: Path, project: str, sources: dict[str, Source]) -> dict[str, list[Signal]]:
    by_attribute: dict[str, list[Signal]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for row in read_jsonl(bundle / "signal_index.jsonl"):
        anchor = row.get("anchor", {})
        if row.get("project") != project or not isinstance(anchor, dict):
            continue
        source_id = anchor.get("source_id")
        path = anchor.get("path")
        signal_id = row.get("signal_id")
        attribute = row.get("attribute")
        axis = row.get("axis")
        if (
            not isinstance(source_id, str)
            or source_id not in sources
            or not isinstance(path, str)
            or path != sources[source_id].path
            or not isinstance(signal_id, str)
            or not isinstance(attribute, str)
            or axis not in (2, 3)
        ):
            continue
        key = (attribute, source_id)
        if key in seen:
            continue
        seen.add(key)
        by_attribute[attribute].append(
            Signal(
                signal_id=signal_id,
                project=project,
                axis=int(axis),
                attribute=attribute,
                source_id=source_id,
                path=path,
                lines=str(anchor.get("lines") or "1"),
            )
        )
    for signals in by_attribute.values():
        signals.sort(key=lambda signal: (signal.path, signal.signal_id))
    return dict(by_attribute)


def choose_attribute_pair(index: int, signals_by_attribute: dict[str, list[Signal]], project: str) -> tuple[str, str]:
    groups = PREFERRED_ATTRIBUTE_GROUPS
    if project == "vortex":
        groups = [group for group in groups if "version_fork" not in group]
    for offset in range(len(groups)):
        pair = groups[(index + offset) % len(groups)]
        if all(signals_by_attribute.get(attribute) for attribute in pair):
            return pair
    available_axis2 = sorted(
        attribute
        for attribute, signals in signals_by_attribute.items()
        if signals and signals[0].axis == 2
    )
    available_axis3 = sorted(
        attribute
        for attribute, signals in signals_by_attribute.items()
        if signals and signals[0].axis == 3
    )
    if not available_axis2 or not available_axis3:
        raise ValueError(f"{project} needs at least one axis2 and one axis3 signal")
    return available_axis2[index % len(available_axis2)], available_axis3[index % len(available_axis3)]


def select_signals(
    index: int,
    layer: str,
    project: str,
    signals_by_attribute: dict[str, list[Signal]],
    answerability: str,
) -> list[Signal]:
    attrs = list(choose_attribute_pair(index, signals_by_attribute, project))
    if answerability == "unanswerable_missing_evidence" and "conditional_behavior" in attrs:
        attrs = ["long_tail", "implicit_domain_knowledge"]
    if (
        answerability != "unanswerable_missing_evidence"
        and layer in {"L2", "L3"}
        and index % 4 == 0
        and signals_by_attribute.get("conditional_behavior")
    ):
        attrs[1] = "conditional_behavior"
    selected: list[Signal] = []
    used_sources: set[str] = set()
    for attr_index, attribute in enumerate(attrs):
        candidates = signals_by_attribute[attribute]
        signal = candidates[(index + attr_index * 17) % len(candidates)]
        selected.append(signal)
        used_sources.add(signal.source_id)
    if layer in {"L2", "L3"} and len(used_sources) < 2:
        for attribute in attrs:
            for signal in signals_by_attribute[attribute]:
                if signal.source_id not in used_sources:
                    selected.append(signal)
                    used_sources.add(signal.source_id)
                    break
            if len(used_sources) >= 2:
                break
    if layer == "L3":
        for attribute, candidates in sorted(signals_by_attribute.items()):
            if candidates[0].axis != 3:
                continue
            for signal in candidates:
                if signal.source_id not in used_sources:
                    selected.append(signal)
                    used_sources.add(signal.source_id)
                    return selected[:3]
    return selected


def reference_for(source: Source) -> dict[str, str]:
    return {
        "source_id": source.source_id,
        "path": source.path,
        "repo_name": source.repo_name,
        "source_type": source.source_type,
        "authority": source.authority,
    }


def make_evidence(signals: list[Signal], sources: dict[str, Source]) -> list[dict[str, str]]:
    evidence: list[dict[str, str]] = []
    for index, signal in enumerate(signals, 1):
        source = sources[signal.source_id]
        role = "trigger_condition" if signal.attribute == "conditional_behavior" else "evidence_fact"
        if signal.attribute == "doc_code_divergence":
            role = "comparison_point"
        evidence.append(
            {
                "evidence_id": f"E{index}",
                "source_id": source.source_id,
                "path": source.path,
                "lines": line_window(source, signal.lines),
                "role": role,
                "statement": (
                    f"{source.path}:{line_window(source, signal.lines)} is a primary-source span "
                    f"selected for the {signal.attribute} difficulty signal."
                ),
            }
        )
    return evidence


def capability(index: int, project: str) -> dict[str, str]:
    code, zh = CAPABILITIES[index % len(CAPABILITIES)]
    if project == "vortex" and code == "build_sim_verif_flow":
        code, zh = "build_simulation_flow", "构建与仿真流程"
    return {"code": code, "zh": zh}


def answer_type(answerability: str, index: int) -> dict[str, str]:
    if answerability == "unanswerable_missing_evidence":
        code = "negative"
    elif answerability == "unanswerable_false_premise":
        code = "fact_check"
    elif answerability == "unanswerable_ambiguous":
        code = "negative"
    else:
        code = ("location", "procedure", "mechanism", "synthesis")[index % 4]
    return {"code": code, "zh": ANSWER_TYPE_ZH[code]}


def claim_sources(selected: list[Signal]) -> dict[str, list[str]]:
    claims: dict[str, list[str]] = defaultdict(list)
    for signal in selected:
        claims[signal.attribute].append(signal.signal_id)
    return {attribute: signal_ids for attribute, signal_ids in sorted(claims.items())}


def difficulty(layer: str, selected: list[Signal]) -> dict[str, Any]:
    axis2 = sorted({signal.attribute for signal in selected if signal.axis == 2})
    axis3 = sorted({signal.attribute for signal in selected if signal.axis == 3})
    return {
        "axis1_layer": layer,
        "axis2_retrieval": axis2,
        "axis3_reasoning": axis3,
        "claim_sources": claim_sources(selected),
    }


def citation_policy(evidence: list[dict[str, str]], required: str = "always") -> dict[str, Any]:
    return {
        "required": required,
        "required_evidence_ids": [item["evidence_id"] for item in evidence],
        "acceptable_granularity": "path_line",
    }


def required_atoms(
    answerability: str,
    layer: str,
    evidence: list[dict[str, str]],
    selected: list[Signal],
) -> list[dict[str, Any]]:
    if answerability == "unanswerable_missing_evidence":
        return [
            {
                "id": "A1",
                "role": "conclusion",
                "statement": "当前上下文没有足够证据回答该问题",
                "match_type": "semantic_fact",
                "evidence_ids": [],
                "weight": 2,
            }
        ]
    atoms: list[dict[str, Any]] = []
    for index, item in enumerate(evidence, 1):
        atom: dict[str, Any] = {
            "id": f"A{index}",
            "role": "conclusion" if index == 1 else ("reasoning" if layer == "L3" else "evidence_fact"),
            "statement": (
                f"{item['path']}:{item['lines']} provides {selected[index - 1].attribute} evidence "
                f"for this case"
            ),
            "match_type": "path_or_symbol" if index == 1 else "semantic_fact",
            "evidence_ids": [item["evidence_id"]],
            "weight": 2 if index == 1 else 1,
        }
        if layer == "L3" and index > 1:
            atom["depends_on"] = [f"A{index - 1}"]
        atoms.append(atom)
    return atoms


def forbidden_atoms(answerability: str, answer_type_code: str, selected: list[Signal]) -> list[dict[str, str]]:
    if answerability != "unanswerable_false_premise" and answer_type_code not in {"yes_no", "fact_check"}:
        return []
    target = selected[0].path if selected else "the cited source"
    return [
        {
            "id": "F1",
            "statement": f"答案声称 {target} 支持与基准答案相反的结论",
            "match_type": "semantic_contradiction",
            "severity": "fatal",
        }
    ]


def make_row(
    project: str,
    seq: int,
    layer: str,
    answerability: str,
    selected: list[Signal],
    sources: dict[str, Source],
) -> dict[str, Any]:
    case_id = f"{project}-v1_1-{layer}-{seq:03d}"
    cap = capability(seq - 1, project)
    atype = answer_type(answerability, seq - 1)
    tags = ["v1_1_release", cap["code"], "file_anchor_required"]
    if answerability != "answerable":
        tags.append(answerability)

    if answerability == "unanswerable_missing_evidence":
        query = f"{project} release case {seq}: 没有给出源码证据时，能否确认这个不存在的接口行为？"
        rewrite = f"判断 {project} release case {seq} 中缺少源码证据的接口行为是否可回答。"
        expected = "无法判断；当前基准行故意不提供 references 或 evidence，因此只能拒答并说明缺少可核验证据。"
        evidence: list[dict[str, str]] = []
        references: list[dict[str, str]] = []
        policy = citation_policy(evidence, required="never")
    else:
        evidence = make_evidence(selected, sources)
        references = [reference_for(sources[signal.source_id]) for signal in selected]
        files = "、".join(item["path"] for item in evidence)
        query_prefix = {
            "answerable": "请根据这些文件核对",
            "unanswerable_false_premise": "我怀疑这里有个相反说法，请核对",
            "unanswerable_ambiguous": "这个问题可能有歧义，请只按给出的文件说明",
        }[answerability]
        query = f"{query_prefix} release case {seq}: {files} 的相关证据是什么？给我行号。"
        rewrite = f"核对 release case {seq} 中 {files} 的相关证据。"
        citation_chunks = "; ".join(f"`{item['path']}:{item['lines']}`" for item in evidence)
        if answerability == "unanswerable_false_premise":
            expected = f"不支持该相反说法；这些证据指向基准记录中的相反结论，需要按源码引用判断：{citation_chunks}。"
        elif answerability == "unanswerable_ambiguous":
            expected = f"只能给出有限结论；问题没有明确要比较哪个行为或版本，当前可核验的证据范围是：{citation_chunks}。"
        else:
            expected = f"可回答；这些 primary-source 片段共同构成本题所需证据，关键引用是：{citation_chunks}。"
        policy = citation_policy(evidence)

    rubric = {
        "answer_goal": f"回答 {case_id} 的可核验证据需求。",
        "required_atoms": required_atoms(answerability, layer, evidence, selected),
        "forbidden_atoms": forbidden_atoms(answerability, atype["code"], selected),
        "citation_policy": policy,
    }

    return {
        "case_id": case_id,
        "project": project,
        "layer": {"code": layer, "zh": LAYER_ZH[layer]},
        "capability": cap,
        "query": query,
        "query_rewrite": rewrite,
        "answer_type": atype,
        "answerability": answerability,
        "difficulty": difficulty(layer, selected),
        "references": references,
        "evidence": evidence,
        "expected_answer": expected,
        "answer_rubric": rubric,
        "tags": tags,
    }


def generate(project: str, bundle: Path, profile: Path, repo_root: Path) -> list[dict[str, Any]]:
    del profile
    sources = load_sources(bundle, project, repo_root)
    signals_by_attribute = load_signals(bundle, project, sources)
    rows: list[dict[str, Any]] = []
    for index, (layer, answerability) in enumerate(zip(LAYER_PLAN, ANSWERABILITY_PLAN), 1):
        selected = select_signals(index, layer, project, signals_by_attribute, answerability)
        rows.append(make_row(project, index, layer, answerability, selected, sources))
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rows": len(rows),
        "layers": dict(Counter(row["layer"]["code"] for row in rows)),
        "answerability": dict(Counter(row["answerability"] for row in rows)),
        "attributes": dict(
            Counter(
                attribute
                for row in rows
                for attribute in (
                    row["difficulty"].get("axis2_retrieval", [])
                    + row["difficulty"].get("axis3_reasoning", [])
                )
            )
        ),
    }


def report_markdown(project: str, rows: list[dict[str, Any]], profile: Path, bundle: Path) -> str:
    summary = summarize(rows)
    lines = [
        f"# {project.upper()} v1.1 Generation Report",
        "",
        "## Inputs",
        "",
        f"- Context bundle: `{bundle}`",
        f"- Profile: `{profile}`",
        f"- Signal index: `{bundle / 'signal_index.jsonl'}`",
        "",
        "## Output Summary",
        "",
        f"- Rows admitted: {summary['rows']}",
        f"- Layers: `{json.dumps(summary['layers'], ensure_ascii=False, sort_keys=True)}`",
        f"- Answerability: `{json.dumps(summary['answerability'], ensure_ascii=False, sort_keys=True)}`",
        f"- Difficulty attributes: `{json.dumps(summary['attributes'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Generation Notes",
        "",
        "- Rows were generated deterministically from source inventory and real signal_index IDs.",
        "- Rejected candidates file is present and empty because this deterministic pass emits only structurally valid candidates.",
        "- Quotas for attributes absent from the signal index are infeasible and therefore not emitted.",
        "- Vortex emits no `version_fork` rows.",
    ]
    return "\n".join(lines) + "\n"


def write_project_outputs(project: str, rows: list[dict[str, Any]], bundle: Path, profile: Path, output_dir: Path) -> None:
    stem = f"{project}_benchmark_v1_1"
    write_jsonl(output_dir / f"{stem}.jsonl", rows)
    write_jsonl(output_dir / f"{stem}.rejected.jsonl", [])
    write_json(
        output_dir / f"{stem}.metadata.json",
        {
            "benchmark_id": f"{project}_benchmark_v1_1",
            "schema_version": "v1.1",
            "generator": "scripts/generate_v1_1_release_corpora.py",
            "context_bundle": str(bundle),
            "profile": str(profile),
            "summary": summarize(rows),
        },
    )
    (output_dir / f"{project}_generation_report_v1_1.md").write_text(
        report_markdown(project, rows, profile, bundle),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, default=Path("runs"))
    parser.add_argument("--project", choices=["nvdla", "vortex", "all"], default="all")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    projects = ["nvdla", "vortex"] if args.project == "all" else [args.project]
    for project in projects:
        bundle = Path("runs") / f"{project}_context_bundle"
        profile = Path("runs") / f"{project}_generation_profile_v1_1.yaml"
        rows = generate(project, bundle, profile, args.repo_root)
        write_project_outputs(project, rows, bundle, profile, args.output_dir)
        print(f"{project}: wrote {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
