module m (input wire clk, input wire [1:0] sel, output reg q);
  always_ff @(posedge clk) begin
    if (sel == 2'b00) q <= 1'b0;
    else case (sel)
      2'b01: q <= 1'b1;
      default: q <= q;
    endcase
  end
endmodule
