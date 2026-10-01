<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

This is a multiply-accumulate (MAC) accelerator, built as a RISC-V-style ISA extension (`MAC.ACC`, `MAC.RD`, `MAC.CLR`) implemented in Verilog. Instead of computing `acc += a * b` as two separate, data-dependent instructions (`MUL` then `ADD`) - which forces a pipeline hazard stall because the add has to wait for the multiply's result - this design fuses both steps into a single hardware instruction. An internal 3-state FSM (`IDLE -> MULT -> ACCUM -> IDLE`) performs the multiply and the accumulate over 2 clock cycles, entirely inside the accelerator. Because the intermediate product never leaves the unit or touches a register file, no external hazard detection is needed - the issuing core just sees one instruction with fixed, self-contained latency.

Since TinyTapeout only provides 16 input pins and 16 output pins, the two 8-bit operands can't be sent in a single cycle alongside the control signals, so they're loaded one at a time: `LOAD_A` latches operand A, and `LOAD_B` latches operand B and triggers the FSM. The 24-bit accumulator is read back using the bidirectional `uio` pins dynamically switched to output mode: each `READ` presents 16 bits at once (`uo_out` + `uio_out` together), so the full result comes out in 2 reads instead of 3.

The benefit is a relative, cycle-count improvement (not a wall-clock speed claim) that only shows up for a sequence of several MAC operations with one result read at the end - the exact pattern used in FIR filters, convolution, and dot products - not for a single isolated multiply-accumulate.

## How to test

The design is verified with a cocotb testbench (test/test.py) that drives the control protocol directly, simulating the instruction-issuing pattern a real RISC-V core would generate:

- **test_correctness** - runs a small, known sequence of MAC operations and checks the result against a Python golden model.
- **benchmark_mac_sequence** / **benchmark_n_sweep** - measure the real number of simulated clock cycles for sequences of different lengths (N), and compare them against the theoretical software (MUL+ADD) cycle count.
- **test_custom_sequence** - lets you edit a list of (a, b) pairs and watch the internal accumulator grow live, step by step.
- **test_fir_like_workload** - runs an 8-tap FIR-filter-style sequence with meaningful coefficients and sample values, instead of random data.

To issue an operation: set `uio_in[2:1]` to the opcode (00=LOAD_A, 01=LOAD_B, 10=READ, 11=CLR), set `uio_in[0]` (valid) high for one clock cycle, and place the operand byte on `ui_in` for LOAD_A/LOAD_B. LOAD_B also starts the multiply-accumulate FSM; wait for `uo_out[0]` (busy) to go low before issuing the next operation. Issue READ twice in a row to retrieve the full 24-bit accumulator as two 16-bit words.

Run the test suite locally with Icarus Verilog and cocotb from the test/ directory, using the command: make

## External hardware

None - this project only uses TinyTapeout's standard dedicated and bidirectional I/O pins.