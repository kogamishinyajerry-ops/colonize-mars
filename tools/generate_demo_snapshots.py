"""跑一局 4 玩家 AI 自对弈，分别在第 1/5/12 代抓棋盘 SVG。

用法：
    python3 tools/generate_demo_snapshots.py
    # → 输出到 docs/demos/snap_gen{N}.svg
"""
from __future__ import annotations
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from game.state import GameState, Player
from game.engine import Engine
from game.ai import make_ai_decision_fns
from tools.render_board_svg import render_state_svg


SNAPSHOT_GENS = [1, 5, 99]   # 99 = 终局
DEMOS_DIR = Path(__file__).resolve().parents[1] / "docs" / "demos"


class SnapshotEngine(Engine):
    """每代结束后保存 SVG 快照"""
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.saved: dict[int, str] = {}

    def play_generation(self):
        super().play_generation()
        if self.state.generation - 1 in SNAPSHOT_GENS:
            gen = self.state.generation - 1
            svg = render_state_svg(
                self.state,
                title=f"世代 {gen} · 4 玩家 AI 自对弈",
                subtitle=f"种子 42 · 温度 {self.state.temperature}°C "
                         f"氧气 {self.state.oxygen}% 海洋 {self.state.oceans}/9",
            )
            DEMOS_DIR.mkdir(parents=True, exist_ok=True)
            path = DEMOS_DIR / f"snap_gen{gen:02d}.svg"
            path.write_text(svg, encoding="utf-8")
            self.saved[gen] = str(path)
            print(f"  📸 保存快照 {path}")


def main():
    rng = random.Random(42)
    players = [Player(idx=i, name=f"AI-{i}", is_ai=True) for i in range(4)]
    fns = {i: make_ai_decision_fns(seed=i + 1) for i in range(4)}
    state = GameState(players=players)
    engine = SnapshotEngine(state, fns, rng=rng)
    result = engine.run(max_generations=20)

    # 终局快照
    final_gen = state.generation - 1
    svg = render_state_svg(
        state,
        title=f"终局 · 世代 {final_gen}",
        subtitle=f"胜者 P{result['ranking'][0][0]} ({result['ranking'][0][1]}) — {result['ranking'][0][2]} VP",
    )
    path = DEMOS_DIR / "snap_final.svg"
    path.write_text(svg, encoding="utf-8")
    print(f"  📸 终局快照 {path}")

    print(f"\n排名：")
    for idx, name, vp in result["ranking"]:
        print(f"  P{idx} {name}: {vp} VP")


if __name__ == "__main__":
    main()
