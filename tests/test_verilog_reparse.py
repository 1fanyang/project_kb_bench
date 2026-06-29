"""Tests for the Verilog tree-sitter re-parser used by the Phase 3
signal emitter.

Coverage (Phase 3 ask):
- always-if            -> AlwaysIfTest
- nested if/else       -> NestedIfElseTest
- case statements      -> CaseStatementTest
- signal read/write    -> SignalDataflowTest
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "benchmark-repo-analyzer" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _verilog_reparse as vr  # noqa: E402


def parse(src: str):
    return vr.reparse_bytes(src.encode("utf-8"))


class AlwaysIfTest(unittest.TestCase):
    def test_always_ff_with_if_yields_two_control_anchors_and_dataflow(self):
        src = """
module m (input wire clk, input wire en, input wire d, output reg q);
  always_ff @(posedge clk) begin
    if (en) q <= d;
    else    q <= 1'b0;
  end
endmodule
"""
        controls, dataflow = parse(src)
        kinds = sorted(c.kind for c in controls)
        # one always_construct + one conditional_statement
        self.assertEqual(kinds, ["always_construct", "conditional_statement"])
        # The if's contained_writes lists `q` (LHS of both branches).
        cond = [c for c in controls if c.kind == "conditional_statement"][0]
        self.assertIn("q", cond.contained_writes)
        # The if anchor lines inside the file (not line 1, which is the
        # blank line before module — this is the bug the v1 builder had).
        self.assertGreater(cond.start_line, 1)
        # dataflow: 2 writes to q
        write_signals = [d.signal_name for d in dataflow]
        self.assertEqual(write_signals.count("q"), 2)
        # The first write reads `d` on the RHS.
        d_write = next(d for d in dataflow
                       if d.signal_name == "q" and "d" in d.rhs_signals)
        self.assertEqual(d_write.in_construct_type, "always_construct")


class NestedIfElseTest(unittest.TestCase):
    def test_nested_conditionals_each_emit_their_own_anchor(self):
        src = """
module m (input wire clk, input wire a, input wire b, output reg q);
  always_ff @(posedge clk) begin
    if (a) begin
      if (b) q <= 1'b1;
      else   q <= 1'b0;
    end else begin
      q <= q;
    end
  end
endmodule
"""
        controls, dataflow = parse(src)
        conds = [c for c in controls if c.kind == "conditional_statement"]
        # outer if + inner if = 2 anchors
        self.assertEqual(len(conds), 2)
        # Exactly one of them has an enclosing always_construct AND no
        # enclosing conditional (the outer); the other has both.
        outer = [c for c in conds if c.enclosing_construct == "always_construct"]
        inner = [c for c in conds
                 if c.enclosing_construct == "conditional_statement"]
        self.assertEqual(len(outer), 1)
        self.assertEqual(len(inner), 1)
        # Each anchor's start_line falls inside the module body.
        for c in conds:
            self.assertGreater(c.start_line, 1)
            self.assertLessEqual(c.start_line, c.end_line)

    def test_anchor_lines_skip_the_license_header_zone(self):
        # The v1 builder regressed by anchoring conditional_behavior at
        # license-block lines 1-10 ("if you ..." / "where applicable").
        # Re-parse should never anchor there because license blocks
        # aren't AST conditional_statement nodes.
        src = (
            "// Copyright 2024 SomeOrg. Licensed under Apache 2.0.\n"
            "// You may not use this file except in compliance.\n"
            "// See the License for the specific language governing\n"
            "// permissions and limitations under the License.\n"
            "//\n"
            "// where applicable, unless required by applicable law\n"
            "//\n"
            + "\n" * 5
            + "module m (input wire a, output reg q);\n"
            "  always_comb begin\n"
            "    if (a) q = 1'b1; else q = 1'b0;\n"
            "  end\n"
            "endmodule\n"
        )
        controls, _ = parse(src)
        for c in controls:
            self.assertGreater(
                c.start_line, 10,
                f"{c.kind} anchored at line {c.start_line} (license-zone bug regressed)"
            )


class CaseStatementTest(unittest.TestCase):
    def test_case_with_three_arms_yields_one_case_anchor_and_three_writes(self):
        src = """
module m (input wire [1:0] sel, input wire a, input wire b, input wire c,
          output reg q);
  always_comb begin
    case (sel)
      2'b00:   q = a;
      2'b01:   q = b;
      default: q = c;
    endcase
  end
endmodule
"""
        controls, dataflow = parse(src)
        cases = [c for c in controls if c.kind == "case_statement"]
        self.assertEqual(len(cases), 1)
        case = cases[0]
        # All three case arms write to `q`.
        self.assertEqual(set(case.contained_writes), {"q"})
        # And the predicate text shows the selector.
        self.assertIn("sel", case.predicate_text)
        # 3 dataflow rows, each reading a distinct input.
        case_writes = [d for d in dataflow
                       if d.signal_name == "q"
                       and d.in_construct_type == "always_construct"]
        self.assertEqual(len(case_writes), 3)
        rhs_seen = {tuple(d.rhs_signals) for d in case_writes}
        self.assertEqual(rhs_seen, {("a",), ("b",), ("c",)})


class SignalDataflowTest(unittest.TestCase):
    def test_continuous_assign_yields_dataflow_anchor(self):
        # The simplest write site: `assign x = y;`
        src = """
module m (input wire y, output wire x);
  assign x = y;
endmodule
"""
        controls, dataflow = parse(src)
        self.assertEqual(controls, [])
        # net_assignment under continuous_assign produces a write to `x`
        # reading `y`.
        self.assertEqual(len(dataflow), 1)
        d = dataflow[0]
        self.assertEqual(d.op, "write")
        self.assertEqual(d.signal_name, "x")
        self.assertEqual(d.rhs_signals, ("y",))
        self.assertEqual(d.in_construct_type, "continuous_assign")
        self.assertEqual(d.assignment_kind, "net_assignment")

    def test_multiple_rhs_signals_are_deduped_in_source_order(self):
        # `assign out = a + b + a;` should report a, b (deduped, a-first).
        src = """
module m (input wire a, input wire b, output wire out);
  assign out = a + b + a;
endmodule
"""
        _, dataflow = parse(src)
        self.assertEqual(len(dataflow), 1)
        self.assertEqual(dataflow[0].rhs_signals, ("a", "b"))

    def test_blocking_and_nonblocking_classify_correctly(self):
        src = """
module m (input wire clk, output reg q, output reg r);
  always_comb r = q;                   // blocking
  always_ff @(posedge clk) q <= r;     // nonblocking
endmodule
"""
        _, dataflow = parse(src)
        by_kind = {d.signal_name: d.assignment_kind for d in dataflow}
        self.assertEqual(by_kind.get("r"), "blocking_assignment")
        self.assertEqual(by_kind.get("q"), "nonblocking_assignment")

    def test_all_anchors_provenance_implicit_in_extractor_tag(self):
        # The provenance string lives on the signal_index records
        # (verilog_anchors emitter), not on the dataclass — this test
        # documents the contract the emitter must hold.
        src = "module m; endmodule"
        controls, dataflow = parse(src)
        # No anchors expected (module body is empty); test just confirms
        # parse doesn't crash on minimal input.
        self.assertEqual(controls, [])
        self.assertEqual(dataflow, [])


if __name__ == "__main__":
    unittest.main()
