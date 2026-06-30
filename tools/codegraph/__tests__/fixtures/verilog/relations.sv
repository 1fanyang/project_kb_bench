`include "stdlib.svh"
import shared_pkg::*;

module parent;
  child #(.W(8)) u_param (.clk(clk));   // module_instantiation
  child         u_named (.clk(clk));    // checker_instantiation
  child         u_pos   (clk);          // udp_instantiation
endmodule

module child (input wire clk); endmodule
