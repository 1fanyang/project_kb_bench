#!/usr/bin/env python3
"""Run five canned codegraph CLI queries and write a markdown transcript.

The five probes target capabilities we depend on for Phase 1+:
  1. Symbol lookup by name (any-language)             — `query`
  2. File listing / structure dump                    — `files`
  3. Symbol detail with caller/callee trail           — `node`
  4. Callers resolution (cross-file)                  — `callers`
  5. Callees resolution (cross-file)                  — `callees`

Treat any non-zero exit or empty payload as a failure; the transcript
records both. CodeGraph 1.1.1's CLI verbs differ slightly from the
Phase 0 plan's placeholders — the script uses the real verbs verified
via `--help` in Task 4.

Usage:
  uv run python scripts/feasibility/probe_codegraph_resolution.py \\
      --cg-bin "/opt/homebrew/opt/node@22/bin/node \\
                /Users/.../tools/codegraph/dist/bin/codegraph.js" \\
      --cg-project /Users/.../repo_sources/vortex \\
      --symbol Core \\
      --out runs/feasibility_v2_analyzer/codegraph_probe_transcript.md
"""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path


def _probes(symbol: str, project: str) -> list[tuple[str, list[str]]]:
    """Each probe returns its argv suffix (excluding the cg binary).

    CodeGraph's CLI takes the project path via `-p` / `--path`, not as a
    positional argument; the `query <search>` etc. surface treats the
    name as the *only* positional and is strict about arg count.
    """
    p = ["--path", project]
    return [
        ("query-symbol-by-name",   ["query",   *p, "--limit", "5", "--json", symbol]),
        ("files-listing",          ["files",   *p]),
        ("node-detail-with-trail", ["node",    *p, symbol]),
        ("callers-cross-file",     ["callers", *p, "--limit", "10", "--json", symbol]),
        ("callees-cross-file",     ["callees", *p, "--limit", "10", "--json", symbol]),
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--cg-bin", required=True,
        help='Full CodeGraph invocation (may contain spaces, e.g. '
             '"/opt/homebrew/opt/node@22/bin/node /path/to/codegraph.js")',
    )
    ap.add_argument(
        "--cg-project", required=True,
        help="Path to the indexed project (the dir containing .codegraph/).",
    )
    ap.add_argument("--symbol", required=True,
                    help="A real symbol present in the index, e.g. 'Core'.")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    bin_argv = shlex.split(args.cg_bin)
    lines: list[str] = [
        "# CodeGraph resolution probe transcript\n",
        f"\nProject: `{args.cg_project}`\n",
        f"Symbol probed: `{args.symbol}`\n",
        f"Binary: `{args.cg_bin}`\n",
    ]

    for label, suffix in _probes(args.symbol, args.cg_project):
        cmd = [*bin_argv, *suffix]
        printable = " ".join(shlex.quote(c) for c in cmd)
        lines.append(f"\n## {label}\n\n```\n$ {printable}\n")
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60,
                env={**os.environ},
            )
            stdout = r.stdout.strip() or "(no stdout)"
            # Cap each probe at 2 KB stdout so the transcript stays readable.
            if len(stdout) > 2000:
                stdout = stdout[:2000] + "\n[…stdout truncated…]"
            lines.append(stdout + "\n")
            if r.stderr.strip():
                stderr = r.stderr.strip()
                if len(stderr) > 1000:
                    stderr = stderr[:1000] + "\n[…stderr truncated…]"
                lines.append(f"\n--- stderr ---\n{stderr}\n")
            lines.append(f"\nexit_code={r.returncode}\n```\n")
        except subprocess.TimeoutExpired:
            lines.append("TIMEOUT after 60s\n```\n")
        except FileNotFoundError as e:
            lines.append(f"FileNotFoundError: {e}\n```\n")

    args.out.write_text("".join(lines))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
