"""Render the final twelve-year Phase 2R event figures."""

from pathlib import Path

from research_workspace.phases.phase2.code.prep_phase2_smoothed_candidate_figures import draw_figures


DATABASE = Path("research_workspace/phases/phase2r/data/sqlite/swarm_a_phase2r_p2r_6_final_v1.sqlite")
OUTPUT = Path("research_workspace/phases/phase2r/figures/P2R.6")


def main() -> None:
    """Input: frozen P2R.6 SQLite. Output: one PNG per used storm."""
    print(f"saved {draw_figures(DATABASE, OUTPUT)} figures in {OUTPUT}")


if __name__ == "__main__":
    main()
