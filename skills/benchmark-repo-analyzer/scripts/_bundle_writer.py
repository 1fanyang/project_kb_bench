"""Shared helpers for the codegraph_to_bundle.py exporter.

Serialization: deterministic JSON (sort_keys=True, no trailing whitespace).
Same DB in -> byte-identical JSONL out.

Kind/modality/source_type tables live here so they have one home.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Iterable, Mapping


# ---------------------------------------------------------------------------
# Deterministic id derivations
# ---------------------------------------------------------------------------

def source_id(project: str, ordinal: int) -> str:
    """Source id, zero-padded so sorted JSONL stays human-readable."""
    return f"src_{project}_{ordinal:05d}"


def entity_id(project: str, name: str, kind: str, source: str, start_line: int) -> str:
    """Stable across re-runs: hash of (project, source, kind, name, start_line).

    Matches the v1 bundle's `ent_<project>_<12hex>` naming so downstream
    consumers that prefix-match (`ent_vortex_*`) keep working.
    """
    h = hashlib.sha256(
        f"{project}|{source}|{kind}|{name}|{start_line}".encode()
    ).hexdigest()[:12]
    return f"ent_{project}_{h}"


def relation_id(project: str, ordinal: int) -> str:
    return f"rel_{project}_{ordinal:07d}"


# ---------------------------------------------------------------------------
# Modality + source-type derivation from CodeGraph's `language` column
# ---------------------------------------------------------------------------

# Maps CodeGraph's language string to the v1 bundle's `modality` value.
# Unknown languages fall through to `unknown` (matches the v1 regex fallback's
# behavior for binary blobs / unrecognized files).
_LANGUAGE_TO_MODALITY: dict[str, str] = {
    # code
    "cpp": "code", "c": "code", "python": "code", "typescript": "code",
    "javascript": "code", "tsx": "code", "jsx": "code", "java": "code",
    "go": "code", "rust": "code", "csharp": "code", "ruby": "code",
    "swift": "code", "kotlin": "code", "dart": "code", "scala": "code",
    "lua": "code", "luau": "code", "r": "code", "objc": "code",
    "pascal": "code", "php": "code", "verilog": "code",
    # config / data
    "yaml": "config", "xml": "config", "properties": "config",
    "twig": "config",
    # docs (CodeGraph doesn't index these natively; the regex bundle did)
    "rst": "doc", "markdown": "doc",
    # templates
    "razor": "code", "svelte": "code", "vue": "code", "astro": "code",
    "liquid": "code",
}

_MODALITY_TO_SOURCE_TYPE: dict[str, str] = {
    "code": "code.source",
    "config": "config.source",
    "doc": "doc.source",
    "build": "build.source",
    "script": "script.source",
    "unknown": "unknown",
}


def derive_modality(language: str | None) -> str:
    if not language:
        return "unknown"
    return _LANGUAGE_TO_MODALITY.get(language.lower(), "unknown")


def derive_source_type(modality: str) -> str:
    return _MODALITY_TO_SOURCE_TYPE.get(modality, "unknown")


# ---------------------------------------------------------------------------
# Kind normalization: CodeGraph NodeKind -> v1 bundle `kind` field
# ---------------------------------------------------------------------------

# CodeGraph's NodeKind enum (src/types.ts): file, module, class, struct,
# interface, trait, protocol, function, method, property, field, variable,
# constant, enum, enum_member, type_alias, namespace, parameter, import,
# export, route, component.
#
# v1 bundle's observed `kind` values (from runs/vortex_context_bundle):
# class, config_key, enum, env_var, flag, function, heading, macro,
# make_target, module, parameter, signal, struct.
#
# Mapping principles:
# 1. Pass through kinds that exist verbatim in v1 (class, function,
#    struct, enum, module, parameter).
# 2. Method -> function: v1 has no `method`; the regex extractor lumped
#    methods into functions. Preserve that lumping for compat.
# 3. trait / protocol -> interface: tree-sitter doesn't disambiguate
#    these as separate v1 kinds; closest semantic match.
# 4. enum_member -> constant: v1 had no enum_member; constants is the
#    closest kind a v1 consumer would group it with.
# 5. file and import are SKIPPED at the emitter (not in the dict): file
#    is already a row in source_inventory, and import edges are already
#    in relation_graph.
_CODEGRAPH_KIND_TO_V1_KIND: dict[str, str] = {
    "module": "module",
    "class": "class",
    "struct": "struct",
    "interface": "interface",
    "trait": "interface",
    "protocol": "interface",
    "function": "function",
    "method": "function",
    "property": "property",
    "field": "field",
    "variable": "variable",
    "constant": "constant",
    "enum": "enum",
    "enum_member": "constant",
    "type_alias": "type_alias",
    "namespace": "namespace",
    "parameter": "parameter",
    "export": "export",
    "route": "route",
    "component": "component",
}

# CodeGraph kinds we deliberately drop from the entity_index emitter.
SKIP_CG_KINDS: frozenset[str] = frozenset({"file", "import"})


def remap_kind(cg_kind: str, language: str | None) -> str | None:
    """CodeGraph kind -> v1 bundle kind. Returns None for skip kinds.

    The Verilog-module special case: tree-sitter-verilog's extractor maps
    module_declaration to classTypes (because the CodeGraph framework has
    no `moduleTypes` slot), so every Verilog module surfaces as
    `kind='class'`. Here we remap it back to `module` for downstream
    consumers that expect Verilog modules to be modules.
    """
    if cg_kind in SKIP_CG_KINDS:
        return None
    if cg_kind == "class" and (language or "").lower() == "verilog":
        return "module"
    return _CODEGRAPH_KIND_TO_V1_KIND.get(cg_kind, cg_kind)


# ---------------------------------------------------------------------------
# Relation predicate normalization: CodeGraph EdgeKind -> v1 predicate
# ---------------------------------------------------------------------------

# CodeGraph EdgeKind: contains, calls, imports, exports, extends, implements,
# references, type_of, returns, instantiates, overrides, decorates.
#
# v1 predicates: contains, defines, doc_mentions_entity, imports_or_includes.
#
# Mapping: pass through everything; rename `imports` -> `imports_or_includes`
# so the existing prepare_module_inputs.py filter keeps matching it.
# New predicates in v1.1: calls, extends, instantiates, references,
# implements, type_of, returns, overrides, decorates, exports.
_PREDICATE_REMAP: dict[str, str] = {
    "imports": "imports_or_includes",  # preserve v1 prepare filter compat
}

# CodeGraph edge kinds we drop at the emitter: `contains` edges are
# largely structural noise (file->entity, class->method) and the v1 bundle
# uses them sparingly; keep them, but expressly do not drop.
DROP_CG_PREDICATES: frozenset[str] = frozenset()


def remap_predicate(cg_predicate: str) -> str | None:
    if cg_predicate in DROP_CG_PREDICATES:
        return None
    return _PREDICATE_REMAP.get(cg_predicate, cg_predicate)


# ---------------------------------------------------------------------------
# First-substantive-line helper (for included-file evidence enrichment)
# ---------------------------------------------------------------------------

# Lines we consider non-substantive — license headers, include guards,
# bare comments. Matches the same heuristic used by Stage-0 prepare's
# _find_first_substantive_line so both layers agree on what "substantive"
# means.
_NONSUBSTANTIVE = re.compile(
    r"^\s*(//.*|/\*.*|\*.*|#.*|`(ifndef|ifdef|define|endif|include).*|$)"
)


def first_substantive_line(path: Path) -> int:
    try:
        for i, line in enumerate(
            path.read_text(errors="replace").splitlines(), start=1
        ):
            if not _NONSUBSTANTIVE.match(line):
                return i
    except OSError:
        pass
    return 1


# ---------------------------------------------------------------------------
# Deterministic JSONL writer
# ---------------------------------------------------------------------------

def write_jsonl(path: Path, records: Iterable[Mapping]) -> int:
    """Write records as JSONL with deterministic key ordering. Returns count."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w") as f:
        for rec in records:
            f.write(json.dumps(rec, sort_keys=True) + "\n")
            count += 1
    return count
