#!/usr/bin/env python3
"""殖民火星 CLI 入口

用法：
  python main.py                  # 1人 + 3 AI
  python main.py --solo            # 自己 vs 1 AI
  python main.py --auto            # 4 AI 自对弈（演示模式）
  python main.py --auto --seed 42  # 可重现
"""
from __future__ import annotations
import argparse
import random
import sys

from game.state import GameState, Player
from game.engine import Engine
from game.ai import make_ai_decision_fns
from game.cli import make_human_decision_fns


def main() -> int:
    ap = argparse.ArgumentParser(description="殖民火星 CLI")
    ap.add_argument("--auto", action="store_true", help="全 AI 自对弈")
    ap.add_argument("--solo", action="store_true", help="1人 vs 1AI")
    ap.add_argument("--players", type=int, default=4)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--max-gen", type=int, default=20)
    ap.add_argument("--quiet", action="store_true", help="不打印日志（仅终局）")
    args = ap.parse_args()

    rng = random.Random(args.seed)

    n = 2 if args.solo else args.players
    n = max(1, min(5, n))

    players = []
    decision_fns = {}

    if args.auto:
        for i in range(n):
            p = Player(idx=i, name=f"AI-{i}", is_ai=True)
            players.append(p)
            decision_fns[i] = make_ai_decision_fns(seed=(args.seed or 0) + i)
    else:
        # 第一人是人类
        try:
            name = input("请输入你的名字 (回车=Player): ").strip() or "Player"
        except EOFError:
            name = "Player"
        players.append(Player(idx=0, name=name, is_ai=False))
        decision_fns[0] = make_human_decision_fns()
        for i in range(1, n):
            players.append(Player(idx=i, name=f"AI-{i}", is_ai=True))
            decision_fns[i] = make_ai_decision_fns(seed=(args.seed or 0) + i)

    state = GameState(players=players)
    engine = Engine(state, decision_fns, rng=rng)

    print("═══ 殖民火星 (Colonize Mars) ═══")
    print(f"玩家数: {n}  种子: {args.seed}")
    result = engine.run(max_generations=args.max_gen)

    if args.quiet:
        # 只打最后排名
        print("\n=== 终局排名 ===")
        for idx, name, vp in result["ranking"]:
            print(f"  P{idx} {name}: {vp} VP")
    else:
        print("\n".join(state.log))

    return 0


if __name__ == "__main__":
    sys.exit(main())
