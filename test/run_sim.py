
"""
Run this from the test/ folder:  python run_sim.py

Mirrors the official Makefile's simulation setup (TOPLEVEL = tb, via tb.v)
so local results match what GitHub Actions / TinyTapeout's own CI will see.
Internal signals are accessed as dut.user_project.<signal>, since tb.v
instantiates the accelerator as "user_project".
"""

from pathlib import Path
from cocotb_tools.runner import get_runner

def main():
    sim = "icarus"
    proj_path = Path(__file__).resolve().parent

    sources = [
        proj_path.parent / "src" / "tt_um_mac_accelerator.v",
        proj_path / "tb.v",
    ]

    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="tb",
        always=True,
    )

    runner.test(
        hdl_toplevel="tb",
        test_module="test",
    )

if __name__ == "__main__":
    main()