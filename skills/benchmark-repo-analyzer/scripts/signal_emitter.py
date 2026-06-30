#!/usr/bin/env python3
"""Emit signal_index.jsonl from a v2 bundle directory.

Reads the four bundle JSONLs + manifest, runs each emitter under
_signals/, dedupes by signal_id, and writes signal_index.jsonl in
place. Re-runs are idempotent.

Usage:
  uv run python skills/benchmark-repo-analyzer/scripts/signal_emitter.py \\
      --bundle runs/vortex_context_bundle_v2/ --project vortex \\
      --repo-sources-root /path/to/repo_sources/
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add scripts dir to path for sibling imports.
sys.path.insert(0, str(Path(__file__).parent))

from _signals import ALL_EMITTERS  # noqa: E402
from _signals._common import Bundle, dedupe  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True, type=Path)
    ap.add_argument("--project", required=True)
    ap.add_argument(
        "--repo-sources-root", type=Path, default=Path("repo_sources"),
        help="Filesystem root for repo_sources/ (verilog_anchors re-parses "
             "source files from disk). Defaults to ./repo_sources.",
    )
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    bundle = Bundle.load(args.bundle, args.project)
    all_signals: list[dict] = []
    per_emitter_counts: dict[str, int] = {}
    for emitter in ALL_EMITTERS:
        produced = list(emitter.emit(bundle, repo_sources_root=args.repo_sources_root))
        per_emitter_counts[emitter.__name__.split(".")[-1]] = len(produced)
        all_signals.extend(produced)

    signals = dedupe(all_signals)
    out = args.bundle / "signal_index.jsonl"
    with out.open("w") as f:
        for s in signals:
            f.write(json.dumps(s, sort_keys=True) + "\n")

    if not args.quiet:
        print(f"wrote {out} ({len(signals)} signals after dedup)")
        for name, n in per_emitter_counts.items():
            print(f"  {name:30s} {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
