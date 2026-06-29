#!/usr/bin/env python3
"""Generate deterministic v1.1 release benchmark corpora from context bundles."""

from __future__ import annotations

import argparse
import json
import re
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

PROJECT_LABELS = {
    "nvdla": "NVDLA",
    "vortex": "Vortex",
}

PATH_TOPIC_TRANSLATIONS = {
    "compilerfeatures": "编译器功能",
    "lowprecision": "低精度支持",
    "readme": "项目说明",
    "roadmap": "路线图",
    "makefile": "构建规则",
    "cmakelists": "CMake 构建规则",
    "vx_afu_ctrl": "AFU 控制逻辑",
    "vx_afu_wrap": "AFU 封装逻辑",
    "vortex_afu": "AFU 顶层逻辑",
    "vortex": "核心入口",
}

PATH_CONTEXT_TRANSLATIONS = {
    "apps": "应用示例",
    "ci": "CI",
    "compiler": "编译器",
    "docs": "文档",
    "driver": "驱动",
    "hw": "硬件设计",
    "rtl": "RTL",
    "runtime": "运行时",
    "sim": "仿真",
    "sw": "软件栈",
    "tests": "测试",
    "verif": "验证",
    "xrt": "XRT 集成",
}

LOW_QUALITY_PATH_MARKERS = (
    "external",
    "third_party",
    "gtest",
    "golden",
    "protobuf",
    "vendor",
    "node_modules",
    "traces/traceplayer",
)

LOW_QUALITY_PATH_SUFFIXES = (
    ".a",
    ".dat",
    ".dimg",
    ".gif",
    ".jpeg",
    ".jpg",
    ".md5",
    ".o",
    ".pdf",
    ".png",
    ".so",
)

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

MISSING_SCENARIOS = [
    "runtime API 的返回码是否区分队列已满和参数非法",
    "DMA 配置项缺省值在仿真和硬件路径是否一致",
    "某个 debug 开关是否会改变 trace 输出格式",
    "构建脚本是否支持增量清理单个 backend",
    "寄存器字段写 0 后是否会自动恢复默认值",
    "测试入口是否保证每次运行都重新生成输入数据",
    "命令行参数缺失时是否会回退到环境变量",
    "driver 初始化失败后是否会重试设备枚举",
    "配置文件中的 unknown key 是否会被忽略",
    "多核场景下统计计数器是否按 core 单独清零",
    "simulator 退出码是否能区分 timeout 和断言失败",
    "生成脚本是否会保留旧的中间文件",
    "缓存 flush 操作是否覆盖所有 memory bank",
    "FPGA backend 是否要求固定 toolchain 版本",
    "单元测试是否覆盖空输入 buffer",
    "日志级别切换是否影响性能计数输出",
    "编译选项是否会改变默认 ISA 扩展集合",
    "异常路径是否会释放已分配的 host buffer",
    "文档示例是否说明了交叉编译目标",
    "仿真脚本是否支持只运行指定 testcase",
    "reset 后 pending request 是否会被保留",
    "schema 版本不匹配时工具是否会自动迁移",
    "命令失败时是否写入 machine-readable error",
    "profiling 模式是否会改变 kernel launch 顺序",
    "外部依赖缺失时安装脚本是否会跳过该组件",
    "多线程提交任务时是否保证完成顺序",
    "配置覆盖项是否能针对单个模块生效",
    "文档中的 deprecated option 是否仍由代码接受",
    "硬件模型是否记录每个事务的 source id",
    "测试失败后是否自动收集波形和日志路径",
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


@dataclass(frozen=True)
class ProfileExpectations:
    target_count: int
    layer_counts: dict[str, int]
    answerability_counts: dict[str, int]
    version_fork_minimum: float | None


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


def path_label(path: str) -> str:
    parts = Path(path).parts
    if len(parts) >= 3 and parts[0] == "repo_sources":
        return "/".join(parts[2:])
    return path


def citation_chunks(evidence: list[dict[str, str]]) -> str:
    return "；".join(f"`{item['path']}:{item['lines']}`" for item in evidence)


def project_label(project: str) -> str:
    return PROJECT_LABELS.get(project, project)


def split_identifier(value: str) -> list[str]:
    normalized = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    normalized = re.sub(r"[_\-.]+", " ", normalized)
    return [part for part in normalized.split() if part]


def readable_identifier(value: str) -> str:
    parts = split_identifier(value)
    readable = []
    for part in parts[:4]:
        readable.append(part.upper() if part.isascii() and len(part) <= 4 else part)
    return " ".join(readable)


def join_context_topic(context: str, topic: str) -> str:
    connector = " 里的" if context and context[-1].isascii() else "里的"
    separator = " " if topic and topic[0].isascii() else ""
    return f"{context}{connector}{separator}{topic}"


def project_topic_phrase(display_project: str, topic: str) -> str:
    separator = " " if topic and topic[0].isascii() else ""
    return f"{display_project} 中{separator}{topic}"


def translated_path_topic(path: str) -> str:
    parts = list(Path(path).parts)
    if len(parts) >= 3 and parts[0] == "repo_sources":
        parts = parts[2:]
    stem = Path(path).stem.lower()
    context = ""
    for part in reversed(parts[:-1]):
        key = part.lower()
        if key in PATH_CONTEXT_TRANSLATIONS:
            context = PATH_CONTEXT_TRANSLATIONS[key]
            break
    topic = PATH_TOPIC_TRANSLATIONS.get(stem)
    if topic is None:
        topic = readable_identifier(Path(path).stem) or "相关逻辑"
        if topic.lower() in {"readme", "index", "main"}:
            topic = "项目入口"
        elif not topic.endswith(("逻辑", "规则", "说明", "流程", "入口")):
            topic = f"{topic} 相关逻辑"
    if context and context not in topic:
        return join_context_topic(context, topic)
    return topic


def evidence_topic(evidence: list[dict[str, str]], max_topics: int = 1) -> str:
    topics: list[str] = []
    seen: set[str] = set()
    for item in evidence:
        topic = translated_path_topic(item["path"])
        if topic not in seen:
            topics.append(topic)
            seen.add(topic)
        if len(topics) >= max_topics:
            break
    if not topics:
        return "相关行为"
    if len(topics) == 1:
        return topics[0]
    return "与".join(topics)


def parse_simple_profile(profile: Path) -> ProfileExpectations:
    text = profile.read_text(encoding="utf-8")
    target_match = re.search(r"benchmark:\n(?:  .+\n)*?  target_count:\s*(\d+)", text)
    if not target_match:
        raise ValueError(f"{profile} missing benchmark target_count")
    layer_counts: dict[str, int] = {}
    current_layer: str | None = None
    in_answerability = False
    answerability_mix: dict[str, float] = {}
    version_fork_minimum: float | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        layer_match = re.match(r"- code:\s*(L[123])$", line)
        if layer_match:
            current_layer = layer_match.group(1)
            continue
        target_count_match = re.match(r"target_count:\s*(\d+)$", line)
        if target_count_match and current_layer:
            layer_counts[current_layer] = int(target_count_match.group(1))
            current_layer = None
            continue
        if line == "answerability_mix:":
            in_answerability = True
            continue
        if in_answerability:
            mix_match = re.match(r"([a-z_]+):\s*([0-9.]+)$", line)
            if mix_match:
                answerability_mix[mix_match.group(1)] = float(mix_match.group(2))
                continue
            if line and not raw_line.startswith("  "):
                in_answerability = False
        version_match = re.match(r"version_fork:\s*([0-9.]+)$", line)
        if version_match:
            version_fork_minimum = float(version_match.group(1))
    target_count = int(target_match.group(1))
    answerability_counts = {
        answerability: int(round(target_count * mix))
        for answerability, mix in answerability_mix.items()
    }
    return ProfileExpectations(
        target_count=target_count,
        layer_counts=layer_counts,
        answerability_counts=answerability_counts,
        version_fork_minimum=version_fork_minimum,
    )


def validate_profile(project: str, profile: Path) -> ProfileExpectations:
    expectations = parse_simple_profile(profile)
    expected_layers = dict(Counter(LAYER_PLAN))
    expected_answerability = dict(Counter(ANSWERABILITY_PLAN))
    if expectations.target_count != len(LAYER_PLAN):
        raise ValueError(f"{profile} target_count does not match generator plan")
    if expectations.layer_counts != expected_layers:
        raise ValueError(f"{profile} layer counts do not match generator plan")
    if expectations.answerability_counts != expected_answerability:
        raise ValueError(f"{profile} answerability mix does not match generator plan")
    if project == "vortex" and expectations.version_fork_minimum not in (0, 0.0):
        raise ValueError(f"{profile} must keep Vortex version_fork at 0")
    return expectations


def parse_range(lines: str) -> tuple[int, int]:
    start = parse_line_start(lines)
    end = start
    if "-" in str(lines):
        try:
            end = max(start, int(str(lines).split("-", 1)[1]))
        except ValueError:
            end = start
    return start, end


def read_snippet(repo_root: Path, path: str, lines: str) -> str:
    source_path = repo_root / path
    start, end = parse_range(lines)
    try:
        source_lines = source_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    selected = source_lines[start - 1 : end]
    cleaned: list[str] = []
    for line in selected:
        normalized = " ".join(line.strip().split())
        if normalized:
            cleaned.append(normalized)
    text = " / ".join(cleaned)
    if len(text) > 180:
        text = text[:177].rstrip() + "..."
    return text or "(blank lines)"


def is_generation_source(row: dict[str, Any], repo_root: Path) -> bool:
    path = row.get("path")
    line_count = row.get("line_count")
    source_type = str(row.get("source_type") or "")
    if not isinstance(path, str) or not isinstance(line_count, int) or line_count <= 0:
        return False
    lowered = path.lower()
    if source_type.startswith("binary."):
        return False
    if any(marker in lowered for marker in LOW_QUALITY_PATH_MARKERS):
        return False
    if lowered.endswith(LOW_QUALITY_PATH_SUFFIXES):
        return False
    return (repo_root / path).exists()


def load_sources(bundle: Path, project: str, repo_root: Path) -> dict[str, Source]:
    sources: dict[str, Source] = {}
    for row in read_jsonl(bundle / "source_inventory.jsonl"):
        source_id = row.get("source_id")
        path = row.get("path")
        line_count = row.get("line_count")
        if (
            row.get("project") != project
            or not isinstance(source_id, str)
            or not is_generation_source(row, repo_root)
        ):
            continue
        assert isinstance(path, str)
        assert isinstance(line_count, int)
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


# Whitelist of signal attributes the L1-L3 selection logic knows how to
# rank. Unknown axis-2/axis-3 attributes (e.g. Phase 3's new
# `signal_dataflow` from verilog re-parse) are dropped at load time so
# they don't accidentally enter PREFERRED_ATTRIBUTE_GROUPS fallback
# selection. Phase 4 "ignore and ship" path: tolerate without wiring.
# To promote a new attribute to selection, add it here AND to
# PREFERRED_ATTRIBUTE_GROUPS in a single change.
KNOWN_AXIS_ATTRIBUTES: frozenset[str] = frozenset({
    "long_tail",
    "distracting_info",
    "non_code_anchor",
    "conditional_behavior",
    "implicit_domain_knowledge",
    "doc_code_divergence",
    "version_fork_diff",  # NVDLA-specific; emitted by future Phase 7 work
})


def load_signals(
    bundle: Path,
    project: str,
    sources: dict[str, Source],
    *,
    dropped_unknown_attributes: dict[str, int] | None = None,
) -> dict[str, list[Signal]]:
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
        if attribute not in KNOWN_AXIS_ATTRIBUTES:
            # Phase 4 "ignore and ship": new attributes (signal_dataflow
            # in Phase 3) are tolerated but don't enter the selection
            # pool. The drop counter exposes the count so the Stage-0
            # audit can record what was bypassed; Phase 5 measurement
            # tells us whether wiring any of them as a new axis would
            # improve L3 row survival.
            if dropped_unknown_attributes is not None:
                dropped_unknown_attributes[attribute] = (
                    dropped_unknown_attributes.get(attribute, 0) + 1
                )
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


def select_l1_signals(index: int, signals_by_attribute: dict[str, list[Signal]]) -> list[Signal]:
    by_source: dict[str, list[Signal]] = defaultdict(list)
    for signals in signals_by_attribute.values():
        for signal in signals:
            if signal.attribute == "conditional_behavior":
                continue
            by_source[signal.source_id].append(signal)
    candidates: list[tuple[str, list[Signal], list[Signal]]] = []
    for source_id, signals in by_source.items():
        axis2 = sorted(
            [signal for signal in signals if signal.axis == 2],
            key=lambda signal: (signal.path, signal.attribute, signal.signal_id),
        )
        axis3 = sorted(
            [signal for signal in signals if signal.axis == 3],
            key=lambda signal: (signal.path, signal.attribute, signal.signal_id),
        )
        if axis2 and axis3:
            candidates.append((source_id, axis2, axis3))
    if not candidates:
        raise ValueError("L1 generation requires same-source axis2 and axis3 signals")
    candidates.sort(key=lambda item: item[0])
    _, axis2, axis3 = candidates[index % len(candidates)]
    return [axis2[index % len(axis2)], axis3[(index // max(1, len(axis2))) % len(axis3)]]


def select_signals(
    index: int,
    layer: str,
    project: str,
    signals_by_attribute: dict[str, list[Signal]],
    answerability: str,
) -> list[Signal]:
    if layer == "L1":
        return select_l1_signals(index, signals_by_attribute)
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


def make_evidence(signals: list[Signal], sources: dict[str, Source], repo_root: Path, layer: str) -> list[dict[str, str]]:
    evidence: list[dict[str, str]] = []
    evidence_signals = signals[:1] if layer == "L1" else signals
    for index, signal in enumerate(evidence_signals, 1):
        source = sources[signal.source_id]
        role = "trigger_condition" if signal.attribute == "conditional_behavior" else "evidence_fact"
        if signal.attribute == "doc_code_divergence":
            role = "comparison_point"
        lines = line_window(source, signal.lines)
        snippet = read_snippet(repo_root, source.path, lines)
        evidence.append(
            {
                "evidence_id": f"E{index}",
                "source_id": source.source_id,
                "path": source.path,
                "lines": lines,
                "role": role,
                "statement": f"这些行显示：{snippet}",
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


def difficulty(layer: str, selected: list[Signal], answerability: str = "answerable") -> dict[str, Any]:
    axis2 = sorted({signal.attribute for signal in selected if signal.axis == 2})
    axis3 = sorted({signal.attribute for signal in selected if signal.axis == 3})
    sources = claim_sources(selected)
    # Missing-evidence rows have no real signal selection; the canonical
    # axis claim for that bucket is `negative_evidence`, matching what
    # prepare_module_inputs.py records in row_plan so M9 can run the
    # closed_book_llm baseline against them.
    if answerability == "unanswerable_missing_evidence":
        axis2 = []
        axis3 = ["negative_evidence"]
        sources = {"negative_evidence": []}
    return {
        "axis1_layer": layer,
        "axis2_retrieval": axis2,
        "axis3_reasoning": axis3,
        "claim_sources": sources,
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
            "statement": f"{path_label(item['path'])}:{item['lines']} 显示：{item['statement'].removeprefix('这些行显示：')}",
            "match_type": "path_or_symbol" if index == 1 else "semantic_fact",
            "evidence_ids": [item["evidence_id"]],
            "weight": 2 if index == 1 else 1,
        }
        if layer == "L3" and index > 1:
            atom["depends_on"] = [f"A{index - 1}"]
        atoms.append(atom)
    return atoms


def unique_references(selected: list[Signal], sources: dict[str, Source]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    seen: set[str] = set()
    for signal in selected:
        if signal.source_id in seen:
            continue
        seen.add(signal.source_id)
        refs.append(reference_for(sources[signal.source_id]))
    return refs


def answer_from_evidence(evidence: list[dict[str, str]]) -> str:
    parts = [
        f"`{item['path']}:{item['lines']}` 显示：{item['statement'].removeprefix('这些行显示：')}"
        for item in evidence
    ]
    return "；".join(parts)


def forbidden_atoms(
    answerability: str,
    answer_type_code: str,
    evidence: list[dict[str, str]],
) -> list[dict[str, str]]:
    if answerability != "unanswerable_false_premise" and answer_type_code not in {"yes_no", "fact_check"}:
        return []
    target = evidence[0]["path"] if evidence else "the cited source"
    return [
        {
            "id": "F1",
            "statement": f"答案声称 {target} 支持与引用证据相反的结论",
            "match_type": "semantic_contradiction",
            "severity": "fatal",
        }
    ]


def references_from_evidence(
    evidence: list[dict[str, str]],
    sources: dict[str, Source],
) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in evidence:
        sid = item.get("source_id")
        if not sid or sid in seen or sid not in sources:
            continue
        seen.add(sid)
        refs.append(reference_for(sources[sid]))
    return refs


# Stage → (filename suffix, jsonl-key-to-row-merge) declarations. Keeps
# load_module_outputs and the require-stages audit driven from one table.
_STAGE_FILES: dict[str, str] = {
    "M2": "curated_evidence.jsonl",
    "M3": "claims.jsonl",
    "M5": "queries.jsonl",
    "M6": "answers.jsonl",
    "M7": "rubrics.jsonl",
    "M8": "verifier.jsonl",
    "M9": "adversarial_gate.jsonl",
}

# Refusal-token detection for M8 status checks. Keep loose alignment with
# adversarial_gate_v2.REFUSAL_TOKENS so the two stages classify the same
# language as refusals.
_M8_REFUSAL_TOKENS = (
    "无法判断",
    "无法确认",
    "只能给出有限结论",
    "Cannot ",
    "cannot confirm",
    "no evidence",
    "refuse",
)


def _m8_is_refusal(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(token.lower() in lower for token in _M8_REFUSAL_TOKENS)


def _compute_m8_status(
    answerability: str,
    rederived_answer: str,
    rederived_confidence: str,
    rederived_citations: list[str],
    evidence_keys: set[str],
) -> str:
    """Coarse M8 verdict feeding the assembler's per-row metadata.

    Returns one of:
      - "not_run"               — no M8 entry for this case_id
      - "agrees"                — re-derivation lines up with the row's expectations
      - "disagrees"             — re-derivation refused on an answerable row OR
                                  gave a confident answer on a missing-evidence row
      - "confidence_mismatch"   — high confidence on an unanswerable row
      - "cite_fabricated"       — re-derivation cited a path not in M2 evidence
    """
    if not rederived_answer:
        return "not_run"
    for cite in rederived_citations or []:
        if isinstance(cite, str) and ":" in cite and cite not in evidence_keys:
            return "cite_fabricated"
    refused = _m8_is_refusal(rederived_answer)
    if answerability == "answerable" and refused:
        return "disagrees"
    if answerability == "unanswerable_missing_evidence" and not refused:
        return "disagrees"
    if answerability.startswith("unanswerable") and rederived_confidence == "high":
        return "confidence_mismatch"
    return "agrees"


def load_module_outputs(
    drafts_dir: Path | None,
    project: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Return (per_case_outputs, stages_audit).

    `per_case_outputs[case_id]` is the merged dict of fields the assembler
    splices into make_row. `stages_audit[stage]` is `{"present": bool,
    "covered_case_ids": set[str]}` so callers can enforce coverage.
    """
    stages_audit: dict[str, dict[str, Any]] = {
        stage: {"present": False, "path": None, "covered_case_ids": set()}
        for stage in _STAGE_FILES
    }
    if drafts_dir is None:
        return {}, stages_audit

    out: dict[str, dict[str, Any]] = {}

    def _consume(stage: str, merger: Any) -> None:
        path = drafts_dir / f"{project}.{_STAGE_FILES[stage]}"
        stages_audit[stage]["path"] = str(path)
        if not path.exists():
            return
        stages_audit[stage]["present"] = True
        covered: set[str] = stages_audit[stage]["covered_case_ids"]
        for row in read_jsonl(path):
            case_id = row.get("case_id")
            if not isinstance(case_id, str):
                continue
            covered.add(case_id)
            merger(out.setdefault(case_id, {}), row)

    _consume("M2", lambda dst, row: dst.update({
        "selected_evidence": row.get("selected_evidence") or [],
        "rejected_candidates": row.get("rejected_candidates") or [],
    }))
    _consume("M3", lambda dst, row: dst.update({
        "claims": row.get("claims") or [],
    }))
    _consume("M5", lambda dst, row: dst.update({
        "query": row.get("query"),
        "query_rewrite": row.get("query_rewrite"),
    }))
    _consume("M6", lambda dst, row: dst.update({
        "expected_answer": row.get("expected_answer"),
        "citation_paths": row.get("citation_paths") or [],
    }))
    _consume("M7", lambda dst, row: dst.update({
        "required_atoms": row.get("required_atoms") or [],
        "forbidden_atoms": row.get("forbidden_atoms") or [],
    }))
    _consume("M8", lambda dst, row: dst.update({
        "_m8_rederived_answer": row.get("rederived_answer") or "",
        "_m8_confidence": row.get("rederivation_confidence") or "",
        "_m8_citations": row.get("rederived_citations") or [],
    }))
    _consume("M9", lambda dst, row: dst.update({
        "adversarial_gate_passed": bool(row.get("passed")),
    }))
    return out, stages_audit


def _expected_case_ids_from_candidates(drafts_dir: Path, project: str) -> set[str]:
    candidates_path = drafts_dir / f"{project}.candidates.jsonl"
    if not candidates_path.exists():
        return set()
    case_ids: set[str] = set()
    for row in read_jsonl(candidates_path):
        case_id = row.get("case_id")
        if isinstance(case_id, str):
            case_ids.add(case_id)
    return case_ids


def _candidate_signal_overrides(
    drafts_dir: Path | None,
    project: str,
) -> dict[str, list[Signal]]:
    """Return signal-backed candidates keyed by case_id.

    Stage 0 may backfill candidates after the legacy `select_signals()` call
    has dropped a noisy conditional or a same-source companion. The assembler
    must use the signal-backed candidates M2 actually kept when computing
    difficulty claim_sources; otherwise final rows can cite valid evidence but
    lose the second difficulty attribute in validator lint.
    """
    if drafts_dir is None:
        return {}
    path = drafts_dir / f"{project}.candidates.jsonl"
    if not path.exists():
        return {}
    out: dict[str, list[Signal]] = {}
    for row in read_jsonl(path):
        case_id = row.get("case_id")
        if not isinstance(case_id, str):
            continue
        signals: list[Signal] = []
        seen: set[tuple[str, str]] = set()
        for cand in row.get("candidates") or []:
            if not isinstance(cand, dict):
                continue
            axis = cand.get("axis")
            attribute = cand.get("attribute")
            signal_id = cand.get("signal_id")
            source_id = cand.get("source_id")
            path_value = cand.get("path")
            if (
                axis not in (2, 3)
                or not isinstance(attribute, str)
                or not isinstance(signal_id, str)
                or not isinstance(source_id, str)
                or not isinstance(path_value, str)
            ):
                continue
            key = (attribute, source_id)
            if key in seen:
                continue
            seen.add(key)
            signals.append(
                Signal(
                    signal_id=signal_id,
                    project=project,
                    axis=int(axis),
                    attribute=attribute,
                    source_id=source_id,
                    path=path_value,
                    lines=str(cand.get("lines") or "1"),
                )
            )
        out[case_id] = signals
    return out


def check_required_stages(
    require_stages: list[str],
    stages_audit: dict[str, dict[str, Any]],
    expected_case_ids: set[str],
) -> list[str]:
    """Return a list of human-readable failure messages. Empty list means OK."""
    failures: list[str] = []
    for stage in require_stages:
        info = stages_audit.get(stage)
        if info is None:
            failures.append(f"{stage}: not a recognized pipeline stage")
            continue
        if not info["present"]:
            failures.append(f"{stage}: required file is missing ({info['path']})")
            continue
        missing = expected_case_ids - info["covered_case_ids"]
        if missing:
            shown = ", ".join(sorted(missing)[:5])
            extra = "" if len(missing) <= 5 else f", ...(+{len(missing) - 5})"
            failures.append(
                f"{stage}: file present but missing {len(missing)} case_id(s) ({shown}{extra})"
            )
    return failures


def make_row(
    project: str,
    seq: int,
    layer: str,
    answerability: str,
    selected: list[Signal],
    sources: dict[str, Source],
    repo_root: Path,
    module_override: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    case_id = f"{project}-v1_1-{layer}-{seq:03d}"
    cap = capability(seq - 1, project)
    atype = answer_type(answerability, seq - 1)
    tags = ["v1_1_release", cap["code"]]
    if answerability != "answerable":
        tags.append(answerability)

    override = module_override or {}
    override_evidence: list[dict[str, Any]] | None = override.get("selected_evidence") if override else None
    override_answer: str | None = override.get("expected_answer") if override else None
    override_query: str | None = override.get("query") if override else None
    override_rewrite: str | None = override.get("query_rewrite") if override else None
    override_required_atoms = override.get("required_atoms") if override else None
    override_forbidden_atoms = override.get("forbidden_atoms") if override else None
    m8_rederived = str(override.get("_m8_rederived_answer") or "") if override else ""
    m8_confidence = str(override.get("_m8_confidence") or "") if override else ""
    m8_citations = override.get("_m8_citations") or []

    display_project = project_label(project)
    if answerability == "unanswerable_missing_evidence":
        scenario = MISSING_SCENARIOS[(seq - 1) % len(MISSING_SCENARIOS)]
        query = f"{display_project} 中能确认 {scenario}吗？我没有看到可核验证据。"
        rewrite = f"判断 {display_project} 中是否有证据支持“{scenario}”。"
        expected = override_answer or (
            "无法判断；当前问题没有给出可核验的源码或文档片段，不能凭空确认这个行为或配置。需要补充对应文件、行号、日志或文档片段后才能回答。"
        )
        evidence: list[dict[str, str]] = []
        references: list[dict[str, str]] = []
        policy = citation_policy(evidence, required="never")
    else:
        if override_evidence is not None:
            if not override_evidence:
                # M2 dropped all candidates; the row cannot stand.
                return None
            evidence = [dict(item) for item in override_evidence]
            references = references_from_evidence(evidence, sources)
            # Keep the difficulty audit trail in sync with what M2 actually
            # kept. Filter the original signal selection down to signals
            # whose source survived M2 curation; difficulty axes and
            # claim_sources are then recomputed from the filtered set, so
            # we never claim an attribute whose underlying signal was
            # rejected.
            kept_source_ids = {str(span.get("source_id", "")) for span in evidence}
            selected = [s for s in selected if s.source_id in kept_source_ids]
        else:
            evidence = make_evidence(selected, sources, repo_root, layer)
            references = unique_references(selected, sources)
        topic = evidence_topic(evidence)
        visible_answer = answer_from_evidence(evidence)
        if answerability == "unanswerable_false_premise":
            query = f"有人说 {project_topic_phrase(display_project, topic)}没有提供任何可用信息，这个说法对吗？请给证据。"
            rewrite = f"核对 {project_topic_phrase(display_project, topic)} 的线索是否包含可用信息。"
            expected = override_answer or (
                f"不支持这个说法；{visible_answer}。引用：{citation_chunks(evidence)}。"
            )
        elif answerability == "unanswerable_ambiguous":
            query = f"{project_topic_phrase(display_project, topic)}这条线索能直接判断具体版本或执行路径吗？请说明能确认什么、不能确认什么。"
            rewrite = f"判断 {project_topic_phrase(display_project, topic)} 的证据是否足以区分版本或执行路径。"
            expected = override_answer or (
                f"只能给出有限结论；{visible_answer}。但问题没有明确版本或执行路径，不能进一步消除歧义。引用：{citation_chunks(evidence)}。"
            )
        else:
            query_styles = {
                "L1": (
                    f"{project_topic_phrase(display_project, topic)} 能确认什么行为或结论？请给证据。",
                    f"我想核对 {project_topic_phrase(display_project, topic)}，当前证据支持什么结论？",
                ),
                "L2": (
                    f"{project_topic_phrase(display_project, topic)} 的两类线索是否能互相印证？请给证据。",
                    f"围绕 {project_topic_phrase(display_project, topic)}，跨来源证据合起来说明了什么？",
                ),
                "L3": (
                    f"{project_topic_phrase(display_project, topic)} 的机制链路是什么？请按证据说明。",
                    f"如果追踪 {project_topic_phrase(display_project, topic)}，这些线索合起来说明了怎样的执行逻辑？",
                ),
            }[layer]
            query = query_styles[seq % len(query_styles)]
            rewrite = f"核对 {project_topic_phrase(display_project, topic)} 的证据结论。"
            expected = override_answer or (
                f"可以确认：{visible_answer}。引用：{citation_chunks(evidence)}。"
            )
        policy = citation_policy(evidence)

    if override_query is not None:
        query = override_query
    if override_rewrite is not None:
        rewrite = override_rewrite

    required = (
        [dict(a) for a in override_required_atoms]
        if override_required_atoms is not None
        else required_atoms(answerability, layer, evidence)
    )
    forbidden = (
        [dict(a) for a in override_forbidden_atoms]
        if override_forbidden_atoms is not None
        else forbidden_atoms(answerability, atype["code"], evidence)
    )

    rubric = {
        "answer_goal": "回答用户提出的可核验证据需求。",
        "required_atoms": required,
        "forbidden_atoms": forbidden,
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
        "difficulty": difficulty(layer, selected, answerability=answerability),
        "references": references,
        "evidence": evidence,
        "expected_answer": expected,
        "answer_rubric": rubric,
        "tags": tags,
        # Internal-only sidecar: assembler peels off into metadata; never
        # written to the final benchmark JSONL (see write_project_outputs).
        "_assembly_audit": {
            "m8_rederived_answer": m8_rederived,
            "m8_confidence": m8_confidence,
            "m8_citations": [c for c in m8_citations if isinstance(c, str)],
            "evidence_keys": [f"{span.get('path','')}:{span.get('lines','')}" for span in evidence],
        },
    }


def generate(
    project: str,
    bundle: Path,
    profile: Path,
    repo_root: Path,
    drafts_dir: Path | None = None,
    drop_log: dict[str, list[str]] | None = None,
    stages_audit_out: dict[str, dict[str, Any]] | None = None,
    strict_m8: bool = False,
    m8_status_out: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    validate_profile(project, profile)
    sources = load_sources(bundle, project, repo_root)
    signals_by_attribute = load_signals(bundle, project, sources)
    module_outputs, stages_audit = load_module_outputs(drafts_dir, project)
    candidate_signal_overrides = _candidate_signal_overrides(drafts_dir, project)
    if stages_audit_out is not None:
        # Convert set → sorted list for JSON-friendliness when callers
        # consume this for metadata. Keep `present` and `path` as-is.
        for stage, info in stages_audit.items():
            stages_audit_out[stage] = {
                "present": info["present"],
                "path": info["path"],
                "covered_count": len(info["covered_case_ids"]),
            }
    rows: list[dict[str, Any]] = []
    dropped: list[str] = []
    gate_dropped: list[str] = []
    m8_dropped: list[str] = []
    m8_status_by_case: dict[str, str] = {}
    for index, (layer, answerability) in enumerate(zip(LAYER_PLAN, ANSWERABILITY_PLAN), 1):
        selected = select_signals(index, layer, project, signals_by_attribute, answerability)
        case_id = f"{project}-v1_1-{layer}-{index:03d}"
        override = module_outputs.get(case_id)
        if override and override.get("selected_evidence") is not None:
            kept_source_ids = {
                str(span.get("source_id", ""))
                for span in override.get("selected_evidence") or []
                if isinstance(span, dict)
            }
            override_signals = [
                signal
                for signal in candidate_signal_overrides.get(case_id, [])
                if signal.source_id in kept_source_ids
            ]
            if override_signals:
                selected = override_signals
        if override and override.get("adversarial_gate_passed") is False:
            gate_dropped.append(case_id)
            continue
        row = make_row(
            project,
            index,
            layer,
            answerability,
            selected,
            sources,
            repo_root,
            module_override=override,
        )
        if row is None:
            dropped.append(case_id)
            continue
        # Peel the assembly audit off so it never lands in the final JSONL.
        audit = row.pop("_assembly_audit", {})
        m8_status = _compute_m8_status(
            answerability=answerability,
            rederived_answer=str(audit.get("m8_rederived_answer") or ""),
            rederived_confidence=str(audit.get("m8_confidence") or ""),
            rederived_citations=list(audit.get("m8_citations") or []),
            evidence_keys=set(audit.get("evidence_keys") or []),
        )
        m8_status_by_case[case_id] = m8_status
        if strict_m8 and m8_status in {"disagrees", "confidence_mismatch", "cite_fabricated"}:
            m8_dropped.append(case_id)
            continue
        rows.append(row)
    if dropped and drafts_dir is not None:
        print(f"{project}: dropped {len(dropped)} rows after M2 returned empty selected_evidence: {dropped[:5]}{'...' if len(dropped) > 5 else ''}")
    if gate_dropped:
        print(f"{project}: dropped {len(gate_dropped)} rows after adversarial gate: {gate_dropped[:5]}{'...' if len(gate_dropped) > 5 else ''}")
    if m8_dropped:
        print(f"{project}: dropped {len(m8_dropped)} rows due to M8 self-verifier disagreement: {m8_dropped[:5]}{'...' if len(m8_dropped) > 5 else ''}")
    if drop_log is not None:
        drop_log["m2_dropped"] = list(dropped)
        drop_log["gate_dropped"] = list(gate_dropped)
        drop_log["m8_dropped"] = list(m8_dropped)
    if m8_status_out is not None:
        m8_status_out.update(m8_status_by_case)
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


def report_markdown(
    project: str,
    rows: list[dict[str, Any]],
    profile: Path,
    bundle: Path,
    target_count: int | None = None,
    drop_log: dict[str, list[str]] | None = None,
) -> str:
    summary = summarize(rows)
    if target_count is None:
        target_count = len(LAYER_PLAN)
    drops = drop_log or {}
    gap = target_count - summary["rows"]
    target_line = (
        f"- Target rows: {target_count}; admitted: {summary['rows']}; gap: {gap}"
        + (" (under target — see drop log below)" if gap > 0 else "")
    )
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
        target_line,
        f"- Layers: `{json.dumps(summary['layers'], ensure_ascii=False, sort_keys=True)}`",
        f"- Answerability: `{json.dumps(summary['answerability'], ensure_ascii=False, sort_keys=True)}`",
        f"- Difficulty attributes: `{json.dumps(summary['attributes'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Drop log",
        "",
        f"- M2 (empty selected_evidence) dropped: {len(drops.get('m2_dropped', []))}",
        f"- M9 (adversarial gate failed) dropped: {len(drops.get('gate_dropped', []))}",
    ]
    for bucket in ("m2_dropped", "gate_dropped"):
        ids = drops.get(bucket) or []
        if ids:
            shown = ", ".join(ids[:10])
            extra = "" if len(ids) <= 10 else f", ...(+{len(ids) - 10})"
            lines.append(f"  - {bucket}: {shown}{extra}")
    lines.extend([
        "",
        "## Generation Notes",
        "",
        "- Rows were generated deterministically from source inventory and real signal_index IDs.",
        "- Rejected candidates file is present and empty because this deterministic pass emits only structurally valid candidates.",
        "- Quotas for attributes absent from the signal index are infeasible and therefore not emitted.",
        "- Vortex emits no `version_fork` rows.",
    ])
    return "\n".join(lines) + "\n"


def write_project_outputs(
    project: str,
    rows: list[dict[str, Any]],
    bundle: Path,
    profile: Path,
    output_dir: Path,
    target_count: int | None = None,
    drop_log: dict[str, list[str]] | None = None,
    stages_used: dict[str, dict[str, Any]] | None = None,
    m8_status: dict[str, str] | None = None,
) -> None:
    stem = f"{project}_benchmark_v1_1"
    write_jsonl(output_dir / f"{stem}.jsonl", rows)
    write_jsonl(output_dir / f"{stem}.rejected.jsonl", [])
    metadata: dict[str, Any] = {
        "benchmark_id": f"{project}_benchmark_v1_1",
        "schema_version": "v1.1",
        "generator": "scripts/generate_v1_1_release_corpora.py",
        "context_bundle": str(bundle),
        "profile": str(profile),
        "summary": summarize(rows),
        "target_count": target_count if target_count is not None else len(LAYER_PLAN),
        "actual_count": len(rows),
        "count_gap": (target_count if target_count is not None else len(LAYER_PLAN)) - len(rows),
    }
    if drop_log:
        metadata["drop_log"] = {k: list(v) for k, v in drop_log.items()}
    if stages_used is not None:
        metadata["stages_used"] = stages_used
    if m8_status:
        metadata["m8_status"] = m8_status
        metadata["m8_status_summary"] = dict(Counter(m8_status.values()))
    write_json(output_dir / f"{stem}.metadata.json", metadata)
    (output_dir / f"{project}_generation_report_v1_1.md").write_text(
        report_markdown(project, rows, profile, bundle, target_count=target_count, drop_log=drop_log),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, default=Path("runs"))
    parser.add_argument("--project", choices=["nvdla", "vortex", "all"], default="all")
    parser.add_argument(
        "--use-module-outputs",
        type=Path,
        default=None,
        help=(
            "Directory containing per-stage host-LLM outputs from the modular pipeline "
            "(<project>.curated_evidence.jsonl, <project>.answers.jsonl). When omitted, "
            "fall back to deterministic template generation."
        ),
    )
    parser.add_argument(
        "--enforce-target-count",
        action="store_true",
        help=(
            "Exit non-zero if the assembled row count is less than the profile's target "
            "after M2 and M9 drops. Use this for release builds to make silent shrinkage "
            "loud."
        ),
    )
    parser.add_argument(
        "--require-stages",
        default="",
        help=(
            "Comma-separated module stages whose draft files MUST exist and cover every "
            "candidate case_id. Choose from M2,M3,M5,M6,M7,M8,M9. Use this in release "
            "builds to prevent silent fallback to template generation for missing stages. "
            "Example: --require-stages M2,M5,M6,M7,M9"
        ),
    )
    parser.add_argument(
        "--bundle-path",
        type=Path,
        default=None,
        help=(
            "Directory holding source_inventory.jsonl / entity_index.jsonl "
            "/ relation_graph.jsonl / signal_index.jsonl. Defaults to "
            "`runs/<project>_context_bundle/`. Pass "
            "`runs/<project>_context_bundle_v2/` to assemble from the v2 "
            "analyzer-produced bundle (matches prepare_module_inputs.py)."
        ),
    )
    parser.add_argument(
        "--strict-m8",
        action="store_true",
        help=(
            "Drop rows where the M8 self-verifier disagreed with M6 (re-derivation "
            "refused on an answerable row, gave a confident answer on a missing-evidence "
            "row, or cited paths not in M2 evidence). Without this flag, the M8 status "
            "is still recorded in metadata for audit but rows are not dropped."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    projects = ["nvdla", "vortex"] if args.project == "all" else [args.project]
    target_count = len(LAYER_PLAN)
    total_gap = 0
    require_stages = [s.strip() for s in args.require_stages.split(",") if s.strip()]
    unknown = [s for s in require_stages if s not in _STAGE_FILES]
    if unknown:
        print(
            f"ERROR: --require-stages got unknown stage(s) {unknown}; valid: {sorted(_STAGE_FILES)}",
        )
        return 2
    stage_check_failures: list[str] = []
    for project in projects:
        if args.bundle_path is not None:
            if args.project == "all":
                print("ERROR: --bundle-path requires a specific --project; "
                      "the bundle path is project-specific.", flush=True)
                return 2
            bundle = args.bundle_path
        else:
            bundle = Path("runs") / f"{project}_context_bundle"
        profile = Path("runs") / f"{project}_generation_profile_v1_1.yaml"
        drop_log: dict[str, list[str]] = {}
        stages_used: dict[str, dict[str, Any]] = {}
        m8_status: dict[str, str] = {}
        rows = generate(
            project,
            bundle,
            profile,
            args.repo_root,
            drafts_dir=args.use_module_outputs,
            drop_log=drop_log,
            stages_audit_out=stages_used,
            strict_m8=args.strict_m8,
            m8_status_out=m8_status,
        )
        write_project_outputs(
            project,
            rows,
            bundle,
            profile,
            args.output_dir,
            target_count=target_count,
            drop_log=drop_log,
            stages_used=stages_used,
            m8_status=m8_status,
        )
        gap = target_count - len(rows)
        total_gap += max(gap, 0)
        print(
            f"{project}: wrote {len(rows)} rows (target {target_count}, gap {gap})"
        )
        if require_stages and args.use_module_outputs is not None:
            # Re-read the audit in the richer set-bearing form so the
            # coverage check can compare against expected case_ids.
            _, full_audit = load_module_outputs(args.use_module_outputs, project)
            expected = _expected_case_ids_from_candidates(args.use_module_outputs, project)
            failures = check_required_stages(require_stages, full_audit, expected)
            for msg in failures:
                stage_check_failures.append(f"{project}: {msg}")
    if stage_check_failures:
        print(
            "ERROR: --require-stages: the following stage(s) are incomplete:",
        )
        for msg in stage_check_failures:
            print(f"  - {msg}")
        return 1
    if args.enforce_target_count and total_gap > 0:
        print(
            f"ERROR: --enforce-target-count is set and the corpus is {total_gap} rows short "
            f"of target across {len(projects)} project(s). Refusing to release.",
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
