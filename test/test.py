import random
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles

CLK_PERIOD_NS = 10  # 100 MHz simulation clock

OP_LOAD_A = 0b00
OP_LOAD_B = 0b01
OP_READ   = 0b10
OP_CLR    = 0b11


async def reset(dut):
    dut.rst_n.value = 0
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


async def send_op(dut, op, data=0):
    """Issue one control op for one clock cycle (valid=1), then deassert."""
    dut.ui_in.value = data
    dut.uio_in.value = (op << 1) | 1  # op[1:0] on bits [2:1], valid on bit 0
    await RisingEdge(dut.clk)
    dut.uio_in.value = 0
    await RisingEdge(dut.clk)


async def do_mac(dut, a, b):
    """LOAD_A, LOAD_B (starts FSM), then wait for busy to clear."""
    await send_op(dut, OP_LOAD_A, a)
    await send_op(dut, OP_LOAD_B, b)
    while int(dut.uo_out.value) & 1:  # busy is uo_out[0] outside of READ/PRESENT
        await RisingEdge(dut.clk)


async def read_acc(dut):
    """
    Two 16-bit reads reconstruct the 24-bit accumulator:
      phase 0 -> acc[15:0]  (uo_out = low byte, uio_out = high byte of this word)
      phase 1 -> acc[23:16], zero-padded to 16 bits
    """
    result = 0
    for phase in range(2):
        dut.ui_in.value = 0
        dut.uio_in.value = (OP_READ << 1) | 1
        await RisingEdge(dut.clk)      # command latched, device enters PRESENT
        dut.uio_in.value = 0
        await RisingEdge(dut.clk)      # PRESENT output is valid during this cycle
        word = int(dut.uo_out.value) | (int(dut.uio_out.value) << 8)
        result |= (word << (16 * phase))
    return result & 0xFFFFFF


@cocotb.test()
async def test_correctness(dut):
    """Golden-model check: small known MAC sequence."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)
    await send_op(dut, OP_CLR)

    pairs = [(2, 5), (3, 1), (4, 2)]
    expected = sum(a * b for a, b in pairs)

    for a, b in pairs:
        await do_mac(dut, a, b)

    result = await read_acc(dut)
    assert result == expected, f"expected {expected}, got {result}"


@cocotb.test()
async def benchmark_mac_sequence(dut):
    """
    Measures actual simulated clock cycles for a sequence of N MAC operations,
    using the 16-bit-wide read protocol (2 reads instead of 3).
    """
    from cocotb.utils import get_sim_time

    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)
    await send_op(dut, OP_CLR)

    random.seed(0)
    N = 20
    pairs = [(random.randint(0, 255), random.randint(0, 255)) for _ in range(N)]
    expected = sum(a * b for a, b in pairs) & 0xFFFFFF

    t_start = get_sim_time(unit="ns")
    for a, b in pairs:
        await do_mac(dut, a, b)
    result = await read_acc(dut)
    t_end = get_sim_time(unit="ns")

    assert result == expected, f"expected {expected}, got {result}"

    accel_cycles = round((t_end - t_start) / CLK_PERIOD_NS)
    dut._log.info(f"N = {N} MAC operations")
    dut._log.info(f"Accelerator (measured, cocotb): {accel_cycles} cycles")
    dut._log.info("Read protocol: 2 x 16-bit reads (was 3 x 8-bit reads)")
    
@cocotb.test()
async def benchmark_n_sweep(dut):
    """
    Measures REAL simulated clock cycles across a range of sequence lengths N,
    to compare against the theoretical model (sw_cycles = 7N) used in the
    project write-up. Replaces the earlier projected-model chart with actual
    measured data.
    """
    from cocotb.utils import get_sim_time

    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())

    n_values = [1, 5, 10, 20, 50, 100]
    results = []

    for n in n_values:
        await reset(dut)
        await send_op(dut, OP_CLR)

        random.seed(0)
        pairs = [(random.randint(0, 255), random.randint(0, 255)) for _ in range(n)]
        expected = sum(a * b for a, b in pairs) & 0xFFFFFF

        t_start = get_sim_time(unit="ns")
        for a, b in pairs:
            await do_mac(dut, a, b)
        result = await read_acc(dut)
        t_end = get_sim_time(unit="ns")

        assert result == expected, f"N={n}: expected {expected}, got {result}"

        accel_cycles = round((t_end - t_start) / CLK_PERIOD_NS)
        sw_cycles = 7 * n
        improvement = (sw_cycles - accel_cycles) / sw_cycles * 100
        results.append((n, accel_cycles, sw_cycles, improvement))

    dut._log.info("")
    dut._log.info(f"{'N':>5} | {'accel (measured)':>17} | {'sw (theoretical)':>17} | {'improvement %':>14}")
    dut._log.info("-" * 62)
    for n, acc, sw, imp in results:
        dut._log.info(f"{n:>5} | {acc:>17} | {sw:>17} | {imp:>13.1f}%")


@cocotb.test()
async def test_custom_sequence(dut):
    """
    Feed in your own list of (a, b) pairs and watch the accumulator grow
    after each one, using direct internal signal visibility (dut.acc) rather
    than the READ protocol. Edit the `pairs` list below to try your own numbers.
    """
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)
    await send_op(dut, OP_CLR)

    pairs = [(3, 4), (10, 2), (7, 7), (1, 1), (255, 255)]  # <-- edit this list

    running = 0
    for a, b in pairs:
        await do_mac(dut, a, b)
        running += a * b
        internal_acc = int(dut.acc.value)
        dut._log.info(
            f"a={a:3d} b={b:3d} -> a*b={a*b:5d} | "
            f"acc (internal, live) = {internal_acc:6d} | "
            f"expected so far = {running & 0xFFFFFF:6d}"
        )

    final = await read_acc(dut)
    dut._log.info(f"Final result via READ protocol: {final}")
    assert final == (running & 0xFFFFFF), f"expected {running & 0xFFFFFF}, got {final}"