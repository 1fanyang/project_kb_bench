"""Re-parse Verilog source via tree-sitter-verilog to recover anchors that
the Phase 1 LanguageExtractor doesn't surface as entities.

Why re-parse instead of extending the extractor framework: per Phase 3
direction, the extractor stays untouched for this version. The Phase 0
tree-sitter-verilog Python binding (PyPI tree-sitter-verilog 1.0.3) is
reused here so the anchors come from the exact same grammar that
generated the v2 bundle.

Two anchor families this module returns:

1. ControlAnchor — `conditional_statement` / `case_statement` /
   `always_construct` site, with start/end line, the predicate text
   (best-effort), and the AST kind. These feed the
   `conditional_behavior` signal.

2. DataflowAnchor — per Verilog assignment site, the LHS signal name,
   the RHS identifier list (what's read), and the enclosing-construct
   kind (e.g. "always_construct" or "continuous_assign"). These feed
   the `signal_dataflow` signal.

Both anchors carry `provenance: "tree_sitter_verilog_reparse_v2"` so
downstream consumers can tell them apart from anchors derived from the
CodeGraph entity_index / relation_graph.

Iterative walk only (recursive walks hit Python's default recursion
limit on NVDLA's DesignWare leaf cells — see Phase 0 Task 3 fix).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

from tree_sitter import Language, Node, Parser
import tree_sitter_verilog as tsv


# Lazy-initialize one parser per process. Construction does the WASM-
# style language binding setup; we don't want to repeat it per file.
_PARSER: Parser | None = None


def _parser() -> Parser:
    global _PARSER
    if _PARSER is None:
        _PARSER = Parser(Language(tsv.language()))
    return _PARSER


CONTROL_KINDS: frozenset[str] = frozenset({
    "conditional_statement",
    "case_statement",
    "always_construct",
})

ASSIGNMENT_KINDS: frozenset[str] = frozenset({
    "nonblocking_assignment",
    "blocking_assignment",
    "net_assignment",  # body of a continuous_assign's list_of_net_assignments
})

LVALUE_KINDS: frozenset[str] = frozenset({
    "variable_lvalue",
    "net_lvalue",
})


# ---------------------------------------------------------------------------
# Anchor records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ControlAnchor:
    kind: str                 # conditional_statement / case_statement / always_construct
    start_line: int           # 1-based
    end_line: int             # 1-based
    predicate_text: str       # the if-condition / case-selector / always-keyword (best-effort, truncated)
    contained_writes: tuple[str, ...]  # signal names written inside this construct (LHS of nested assignments)
    enclosing_construct: str | None    # parent construct kind, if any (e.g. "always_construct" for nested if)


@dataclass(frozen=True)
class DataflowAnchor:
    line: int                 # 1-based; the assignment line
    op: str                   # "write" — the row IS the write site; reads are listed in rhs_signals
    signal_name: str          # LHS signal identifier
    rhs_signals: tuple[str, ...]  # identifiers referenced on the RHS (i.e. signals read)
    in_construct_type: str    # "always_construct" / "continuous_assign" / "<root>"
    assignment_kind: str      # nonblocking_assignment / blocking_assignment / net_assignment


# ---------------------------------------------------------------------------
# AST helpers (iterative; safe for deeply-nested grammars)
# ---------------------------------------------------------------------------

def _walk(node: Node) -> Iterator[Node]:
    """Iterative pre-order walk."""
    stack: list[Node] = [node]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(reversed(n.children))


def _find_first(node: Node, kinds: frozenset[str]) -> Node | None:
    """First descendant whose .type is in `kinds` (BFS, depth-bounded)."""
    queue: list[Node] = [node]
    while queue:
        n = queue.pop(0)
        if n is not node and n.type in kinds:
            return n
        queue.extend(n.children)
    return None


def _identifiers_in(node: Node) -> list[str]:
    """All `simple_identifier` text descendants in source order."""
    out: list[str] = []
    for n in _walk(node):
        if n.type == "simple_identifier":
            t = n.text
            if t:
                out.append(t.decode(errors="replace"))
    return out


def _lvalue_name(assignment: Node) -> str | None:
    """LHS signal name from an assignment node."""
    lhs = _find_first(assignment, LVALUE_KINDS)
    if not lhs:
        return None
    ident = _find_first(lhs, frozenset({"simple_identifier"}))
    if ident and ident.text:
        return ident.text.decode(errors="replace")
    return None


def _rhs_identifiers(assignment: Node) -> list[str]:
    """RHS identifiers from an assignment node. The RHS is everything after the LHS.

    Strategy: find the LHS lvalue node, then collect simple_identifiers
    from siblings to its right that are inside an `expression` subtree.
    """
    lhs = _find_first(assignment, LVALUE_KINDS)
    if not lhs:
        return []
    seen: list[str] = []
    deduped: set[str] = set()
    # Walk siblings of the LHS that come after it; collect identifiers.
    parent = lhs.parent
    if not parent:
        return []
    past_lhs = False
    for child in parent.children:
        if child == lhs:
            past_lhs = True
            continue
        if not past_lhs:
            continue
        for ident in _identifiers_in(child):
            if ident not in deduped:
                deduped.add(ident)
                seen.append(ident)
    return seen


def _writes_inside(node: Node) -> list[str]:
    """Distinct LHS signal names of assignments anywhere under `node`."""
    found: list[str] = []
    deduped: set[str] = set()
    for n in _walk(node):
        if n.type in ASSIGNMENT_KINDS:
            name = _lvalue_name(n)
            if name and name not in deduped:
                deduped.add(name)
                found.append(name)
    return found


def _enclosing_kind(node: Node, kinds: frozenset[str]) -> str | None:
    """Walk up `parent` chain until we hit a node whose .type is in `kinds`."""
    p = node.parent
    while p is not None:
        if p.type in kinds:
            return p.type
        p = p.parent
    return None


def _predicate_text(control_node: Node) -> str:
    """Best-effort one-line text of the controlling expression.

    - conditional_statement: the `cond_predicate` child
    - case_statement: the `case_expression` child
    - always_construct: the always_keyword text (e.g. "always_ff") plus any
      event_control
    """
    target_kinds = {
        "conditional_statement": ("cond_predicate",),
        "case_statement": ("case_expression",),
        "always_construct": ("always_keyword", "event_control"),
    }
    targets = target_kinds.get(control_node.type, ())
    parts: list[str] = []
    for child in control_node.children:
        if child.type in targets and child.text:
            parts.append(child.text.decode(errors="replace").strip())
    text = " ".join(parts) or (
        control_node.text or b""
    ).decode(errors="replace").splitlines()[0]
    return text[:120]


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def reparse(source_path: Path) -> tuple[list[ControlAnchor], list[DataflowAnchor]]:
    """Re-parse a Verilog source file and return both anchor families."""
    try:
        data = source_path.read_bytes()
    except OSError:
        return [], []
    return reparse_bytes(data)


def reparse_bytes(data: bytes) -> tuple[list[ControlAnchor], list[DataflowAnchor]]:
    """Re-parse Verilog source bytes; same return shape as reparse()."""
    tree = _parser().parse(data)
    root = tree.root_node

    controls: list[ControlAnchor] = []
    dataflow: list[DataflowAnchor] = []

    for node in _walk(root):
        nt = node.type
        if nt in CONTROL_KINDS:
            controls.append(ControlAnchor(
                kind=nt,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                predicate_text=_predicate_text(node),
                contained_writes=tuple(_writes_inside(node)),
                enclosing_construct=_enclosing_kind(node, CONTROL_KINDS),
            ))
        elif nt in ASSIGNMENT_KINDS:
            name = _lvalue_name(node)
            if not name:
                continue
            # `net_assignment` lives under `continuous_assign`; tag accordingly.
            in_construct = "continuous_assign" if nt == "net_assignment" else (
                _enclosing_kind(node, frozenset({"always_construct"})) or "<root>"
            )
            dataflow.append(DataflowAnchor(
                line=node.start_point[0] + 1,
                op="write",
                signal_name=name,
                rhs_signals=tuple(_rhs_identifiers(node)),
                in_construct_type=in_construct,
                assignment_kind=nt,
            ))

    return controls, dataflow
