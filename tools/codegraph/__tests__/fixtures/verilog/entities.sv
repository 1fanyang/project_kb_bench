package my_pkg; endpackage
`define MY_MACRO 1

interface my_if; endinterface

module sample #(parameter int W = 8) (input wire clk);
  function int double(int x); return x * 2; endfunction
  task automatic stim(); endtask
endmodule

class my_class; endclass
