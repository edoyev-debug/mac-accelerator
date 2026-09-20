"""
Run this from the test/ folder:  python run_sim.py

Bypasses the Makefile (which assumes a Unix `make` toolchain) and drives
Icarus Verilog + cocotb directly through cocotb's runner API instead.
"""

from pathlib import Path
from cocotb_tools.runner import get_runner

def main():
    sim = "icarus"
    proj_path = Path(__file__).resolve().parent

    sources = [proj_path.parent / "src" / "tt_um_mac_accelerator.v"]

    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="tt_um_mac_accelerator",
        always=True,
    )

    runner.test(
        hdl_toplevel="tt_um_mac_accelerator",
        test_module="test",  # runs test.py in this folder
    )

if __name__ == "__main__":
    main()