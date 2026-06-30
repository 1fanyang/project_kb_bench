"""Phase 3 signal emitters.

Each module exports `emit(bundle: Bundle) -> Iterable[dict]`. `ALL_EMITTERS`
is the list of modules consumed by `signal_emitter.py`.

Order matters for determinism: deduper in _common keeps the FIRST record
for a given signal_id, so emitters with cleaner anchors come first.
"""
from . import verilog_anchors    # AST-anchored: conditional_behavior + signal_dataflow
from . import long_tail
from . import distracting_info
from . import non_code_anchor
from . import doc_code_divergence
from . import implicit_domain_knowledge

ALL_EMITTERS = [
    verilog_anchors,
    long_tail,
    distracting_info,
    non_code_anchor,
    doc_code_divergence,
    implicit_domain_knowledge,
]

__all__ = ["ALL_EMITTERS"]
