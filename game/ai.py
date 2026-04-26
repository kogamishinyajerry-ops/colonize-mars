"""AI 玩家 — 启发式贪心策略"""
from __future__ import annotations
import random
from typing import Optional

from .resources import CardType, Tag
from .state import GameState, Player
from .cards import Card
from .actions import Action
from .board import Hex, TileType


def make_ai_decision_fns(seed: Optional[int] = None) -> dict:
    rng = random.Random(seed)

    def choose_corp(state: GameState, player: Player, options: list[Card]) -> Card:
        # 简单：随机选；偏好 Helion / CrediCor
        prefs = {"Helion 氦能": 3, "CrediCor 信用公司": 3, "Inventrix 发明者公司": 2}
        weights = [prefs.get(c.name, 1) for c in options]
        return rng.choices(options, weights=weights, k=1)[0]

    def choose_keep(state: GameState, player: Player, drawn: list[Card]) -> list[Card]:
        # 倾向于多买，留一定 MC 给行动
        kept = []
        # 预算：当前MC的 60%，但每代至少买2张以建立动力
        budget = max(6, int(player.res.mc * 0.6))
        sorted_cards = sorted(drawn, key=lambda x: _card_value(x, state, player), reverse=True)
        for c in sorted_cards:
            if len(kept) * 3 + 3 <= budget and _card_value(c, state, player) > 0:
                kept.append(c)
        if not kept and drawn and player.res.mc >= 3:
            kept.append(sorted_cards[0])
        return kept

    def choose_action(state: GameState, player: Player, legal: list[Action]) -> Action:
        # 评估每个动作，挑分数最高的
        best, best_score = None, -1e9
        for a in legal:
            sc = _action_score(a, state, player)
            if sc > best_score:
                best, best_score = a, sc
        return best

    def choose_hex(state: GameState, player: Player, choices: list[Hex], kind: str) -> Hex:
        # 简单：邻接最多奖励 / 自己板块
        def score(h):
            s = 0
            adj_oc = state.board.adjacent_oceans(h)
            s += adj_oc * 2
            for n in state.board.neighbors(h):
                if n.owner == player.idx:
                    s += 1
            if h.bonus:
                s += {"steel": 2, "titanium": 3, "card": 2, "plant": 3, "heat": 1}.get(h.bonus[0], 0)
            return s
        return max(choices, key=score)

    return {
        "choose_corp": choose_corp,
        "choose_keep": choose_keep,
        "choose_action": choose_action,
        "choose_hex": choose_hex,
    }


def _card_value(c: Card, state: GameState, player: Player) -> float:
    """估算一张卡值不值得保留/打出"""
    if c.card_type == CardType.CORPORATION:
        return 0
    v = 0.0
    # 立即 VP
    v += c.vp * 4
    # 费用越高 → 越倾向于晚买（早期保守）
    v -= c.cost * 0.3
    # 资源/产能效果用名称粗估（简化：检查 description）
    desc = c.description
    if "TR+" in desc or "TR +" in desc:
        v += 8
    if "海洋" in desc or "ocean" in desc.lower():
        v += 6
    if "温度" in desc:
        v += 5
    if "氧气" in desc:
        v += 5
    if "产能+" in desc:
        # 取首个数字
        import re
        for m in re.finditer(r"产能\+(\d)", desc):
            v += int(m.group(1)) * 3
    # 标签同义性（自己已有同标签 → 奖励）
    for tag in c.tags:
        v += player.count_tag(tag) * 0.5
    # 资格不满足惩罚
    if c.can_play and not c.can_play(state, player):
        v -= 5
    return v


def _action_score(a: Action, state: GameState, player: Player) -> float:
    """评估动作的即时价值"""
    s = 0.0
    if a.kind == "play_card":
        c: Card = a.payload
        s = _card_value(c, state, player)
        # 鼓励花钱避免囤积
        if player.res.mc > 40 and c.cost > 15:
            s += 4
    elif a.kind == "std_project":
        sp = a.payload
        if sp.name.startswith("Greenery"):
            s = 10  # 1 VP + O2 → TR
        elif sp.name.startswith("City"):
            s = 6
        elif sp.name.startswith("Asteroid"):
            s = 7
        elif sp.name.startswith("Aquifer"):
            s = 8
        elif sp.name.startswith("Power"):
            s = 4
        elif sp.name.startswith("Sell"):
            s = 0.5
    elif a.kind == "blue_action":
        s = 4
    elif a.kind == "claim_milestone":
        s = 12
    elif a.kind == "fund_award":
        # 只有领先时才资助
        aw = a.payload
        my_score = aw.score(state, player)
        others = [aw.score(state, p) for p in state.players if p.idx != player.idx]
        if others and my_score > max(others):
            s = 9
        else:
            s = -1
    elif a.kind == "convert_plants":
        s = 11  # 绿地 +VP +O2
    elif a.kind == "convert_heat":
        s = 7
    # ─── DLC I 轨道战争 ───
    elif a.kind == "dlc_sabotage":
        # 后期更愿意攻击领跑者
        leader_vp = max((q.tr for q in state.players if q.idx != player.idx), default=0)
        s = 9 if leader_vp > player.tr + 3 else 4
    elif a.kind == "dlc_spy":
        s = 3   # 信息价值不直接，给低分
    elif a.kind == "dlc_nap":
        # 偏好与最强对手签约（防止被打）
        target_idx = a.payload.get("target_idx")
        target = state.players[target_idx] if target_idx is not None else None
        s = 6 if target and target.tr > player.tr else 3
    # ─── DLC III 红色风暴 ───
    elif a.kind == "dlc_aid":
        cs = state.dlc_state.get("crimson", {})
        threat = cs.get("threat", 0)
        threshold = cs.get("threshold", 30)
        ratio = threat / max(1, threshold)
        # 高威胁时援助变得非常有价值（共同失败>个人VP）
        if ratio > 0.7:
            s = 12
        elif ratio > 0.5:
            s = 7
        else:
            s = 3
    elif a.kind == "pass":
        # 没好动作时才 pass
        s = 1.5
    elif a.kind.startswith("dlc_"):
        s = 2  # 未知 DLC 动作的兜底
    return s
