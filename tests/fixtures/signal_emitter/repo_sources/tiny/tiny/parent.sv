// License header line 1
// License header line 2
// License header line 3
// License header line 4
// License header line 5

module parent (input wire clk, input wire en, input wire d, output reg q);
  wire b;
  assign b = d;
  always_ff @(posedge clk) begin
    if (en) q <= b;
    else    q <= 1'b0;
  end
endmodule
