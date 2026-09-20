`timescale 1ns / 1ps
`default_nettype none

// MAC accelerator for TinyTapeout
// Implements a multiply-accumulate ISA-extension-style accelerator:
//   OP_LOAD_A - latch operand A
//   OP_LOAD_B - latch operand B and start the MAC sequence (acc += a*b)
//   OP_READ   - present the next 16-bit chunk of the accumulator
//               (phase 0 = acc[15:0], phase 1 = acc[23:16] zero-padded)
//   OP_CLR    - reset the accumulator to zero
//
// FSM: IDLE -> MULT (multiply) -> ACCUM (add to acc) -> IDLE
//      IDLE -> PRESENT (drive uio as output for one cycle, 16-bit readout) -> IDLE
//
// uio_in/uio_out/uio_oe are used dynamically: uio is an input bus (carrying
// valid+op) in every state except PRESENT, where it switches to an output
// bus for one cycle so a 16-bit chunk of the accumulator can be read out on
// uo_out+uio_out together, instead of leaving uio_out/uio_oe unused.

module tt_um_mac_accelerator (
    input  wire [7:0] ui_in,    // operand data bus (A or B, one byte at a time)
    output wire [7:0] uo_out,   // low byte of a read, else {7'b0, busy}
    input  wire [7:0] uio_in,   // uio_in[0]=valid strobe, uio_in[2:1]=op select
    output wire [7:0] uio_out,  // high byte of a read (only valid during PRESENT)
    output wire [7:0] uio_oe,   // 0 = uio is input (control); 0xFF during PRESENT
    input  wire       ena,      // unused (no low-power gating in this design)
    input  wire       clk,
    input  wire       rst_n
);

    // ---- control decode ----
    wire       valid = uio_in[0];
    wire [1:0] op    = uio_in[2:1];

    localparam OP_LOAD_A = 2'b00;
    localparam OP_LOAD_B = 2'b01;
    localparam OP_READ   = 2'b10;
    localparam OP_CLR    = 2'b11;

    // ---- FSM states ----
    localparam S_IDLE    = 2'b00;
    localparam S_MULT    = 2'b01;
    localparam S_ACCUM   = 2'b10;
    localparam S_PRESENT = 2'b11;

    reg [1:0]  state;
    reg [7:0]  reg_a, reg_b;
    reg [15:0] product;
    reg [23:0] acc;
    reg        read_phase;  // 0 = present acc[15:0], 1 = present acc[23:16] (padded)
    reg        busy;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state      <= S_IDLE;
            reg_a      <= 8'd0;
            reg_b      <= 8'd0;
            product    <= 16'd0;
            acc        <= 24'd0;
            read_phase <= 1'b0;
            busy       <= 1'b0;
        end else begin
            case (state)

                S_IDLE: begin
                    busy <= 1'b0;
                    if (valid) begin
                        case (op)
                            OP_LOAD_A: reg_a <= ui_in;

                            OP_LOAD_B: begin
                                reg_b <= ui_in;
                                state <= S_MULT;
                                busy  <= 1'b1;
                            end

                            OP_CLR: begin
                                acc        <= 24'd0;
                                read_phase <= 1'b0;
                            end

                            OP_READ: state <= S_PRESENT;

                            default: ;
                        endcase
                    end
                end

                S_MULT: begin
                    product <= reg_a * reg_b;
                    state   <= S_ACCUM;
                end

                S_ACCUM: begin
                    acc   <= acc + {8'd0, product};
                    state <= S_IDLE;
                    busy  <= 1'b0;
                end

                S_PRESENT: begin
                    read_phase <= ~read_phase;
                    state      <= S_IDLE;
                end

                default: state <= S_IDLE;

            endcase
        end
    end

    reg [15:0] present_word;
    always @(*) begin
        case (read_phase)
            1'b0:    present_word = acc[15:0];
            1'b1:    present_word = {8'd0, acc[23:16]};
            default: present_word = 16'd0;
        endcase
    end

    wire presenting = (state == S_PRESENT);

    assign uo_out  = presenting ? present_word[7:0]  : {7'b0, busy};
    assign uio_out = presenting ? present_word[15:8] : 8'd0;
    assign uio_oe  = presenting ? 8'hFF              : 8'd0;

    wire _unused = &{ena, 1'b0};

endmodule

`default_nettype wire