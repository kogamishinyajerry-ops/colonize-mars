"""DLC I — 轨道战争 (Orbital Warfare)

引入冷战级威慑：Force / Intel 资源、轨道单位、霸权税、破坏/侦察行动、不结盟条约。

核心设计：
- Force 用于攻击（破坏卡牌、轨道打击）
- Intel 用于侦察（看手牌、避免霸权税）
- 霸权税：每代结束 TR 第一名付 5MC（除非 Intel ≥ 3 抵消）
- NAP：玩家间 3 代不结盟条约，违约扣 5 TR
- 攻击是公开的、可追溯的
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from .base import DLC
from ..cards import Card, gain, gain_prod, lose_prod, combine
from ..resources import CardType, Tag
from ..actions import Action

if TYPE_CHECKING:
    from ..state import GameState, Player


# ─────────────────── DLC 资源工具 ───────────────────

def _bag(p: "Player") -> dict:
    if "orbital" not in p.dlc_bag:
        p.dlc_bag["orbital"] = {"force": 0, "intel": 0, "satellites": 0,
                                "force_prod": 0, "intel_prod": 0,
                                "naps": {}}  # naps: {other_idx: gens_left}
    return p.dlc_bag["orbital"]


def _add_force(p: "Player", n: int) -> None:
    b = _bag(p)
    b["force"] = max(0, b["force"] + n)


def _add_intel(p: "Player", n: int) -> None:
    b = _bag(p)
    b["intel"] = max(0, b["intel"] + n)


def _add_force_prod(p: "Player", n: int) -> None:
    _bag(p)["force_prod"] += n


def _add_intel_prod(p: "Player", n: int) -> None:
    _bag(p)["intel_prod"] += n


# ─────────────────── 卡牌效果 ───────────────────

def _f(fn):
    """简单效果包装"""
    return fn


# ─────────────────── 卡库 ───────────────────

def _build_orbital_cards() -> list[Card]:
    """DLC 卡 ID 从 200 起，避免与基础冲突"""
    out: list[Card] = []

    out.append(Card(
        id=200, name="Hauschka 反卫星平台", cost=18,
        card_type=CardType.ACTIVE,
        tags=(Tag.SCIENCE, Tag.BUILDING),
        vp=1,
        on_play=lambda s, p: _add_force(p, 4),
        action=lambda s, p: _add_force(p, 2),
        action_used_each_gen=True,
        description="行动：每代+2 Force。打出+4 Force。VP=1",
    ))

    out.append(Card(
        id=201, name="量子加密阵列", cost=11,
        card_type=CardType.AUTOMATED,
        tags=(Tag.SCIENCE,),
        vp=1,
        on_play=combine(
            lambda s, p: _add_intel_prod(p, 2),
            lambda s, p: _bag(p).update({"shielded": True}),
        ),
        description="Intel 产能+2。免疫所有侦察动作。",
    ))

    out.append(Card(
        id=202, name="私掠者舰队", cost=14,
        card_type=CardType.ACTIVE,
        tags=(Tag.SPACE,),
        on_play=lambda s, p: _add_force_prod(p, 2),
        description="Force 产能+2。",
    ))

    out.append(Card(
        id=203, name="深空侦察网", cost=9,
        card_type=CardType.AUTOMATED,
        tags=(Tag.SCIENCE, Tag.SPACE),
        vp=1,
        on_play=combine(
            lambda s, p: _add_intel(p, 3),
            lambda s, p: _add_intel_prod(p, 1),
        ),
        description="立即+3 Intel；Intel 产能+1。",
    ))

    out.append(Card(
        id=204, name="轨道毁灭性打击", cost=25,
        card_type=CardType.EVENT,
        tags=(Tag.SPACE, Tag.EVENT),
        vp=-3,
        can_play=lambda s, p: _bag(p)["force"] >= 6,
        on_play=lambda s, p: _orbital_strike(s, p),
        description="消耗 6 Force：摧毁一座敌方城市；自己 -3 VP（罪行印记）。",
    ))

    out.append(Card(
        id=205, name="联合国安理会", cost=16,
        card_type=CardType.ACTIVE,
        tags=(Tag.EARTH,),
        vp=2,
        on_play=lambda s, p: _add_intel(p, 2),
        action=lambda s, p: _add_intel(p, 1),
        action_used_each_gen=True,
        description="行动：每代 +1 Intel。打出+2 Intel。VP=2",
    ))

    out.append(Card(
        id=206, name="军备竞赛", cost=8,
        card_type=CardType.AUTOMATED,
        tags=(),
        on_play=lambda s, p: _arms_race(s),
        description="所有玩家 Force 产能 +1（含自己）。",
    ))

    out.append(Card(
        id=207, name="电子干扰器", cost=4,
        card_type=CardType.EVENT,
        tags=(Tag.EVENT, Tag.SCIENCE),
        on_play=lambda s, p: _add_intel(p, 5),
        description="立即获得 5 Intel。",
    ))

    out.append(Card(
        id=208, name="导弹发射井", cost=10,
        card_type=CardType.AUTOMATED,
        tags=(Tag.BUILDING,),
        on_play=combine(
            lambda s, p: _add_force(p, 4),
            lambda s, p: _add_force_prod(p, 1),
        ),
        description="立即+4 Force, Force 产能+1。",
    ))

    out.append(Card(
        id=209, name="商业卫星网", cost=7,
        card_type=CardType.AUTOMATED,
        tags=(Tag.SPACE,),
        vp=1,
        on_play=combine(
            gain_prod("mc", 2),
            lambda s, p: _add_intel_prod(p, 1),
        ),
        description="MC 产能+2，Intel 产能+1。VP=1",
    ))

    out.append(Card(
        id=210, name="太空法庭", cost=14,
        card_type=CardType.ACTIVE,
        tags=(Tag.EARTH,),
        vp=2,
        description="效果：每当其他玩家违反 NAP，你 +3 VP（被动结算）。",
    ))

    out.append(Card(
        id=211, name="黑客突袭", cost=6,
        card_type=CardType.EVENT,
        tags=(Tag.SCIENCE, Tag.EVENT),
        can_play=lambda s, p: _bag(p)["intel"] >= 3,
        on_play=lambda s, p: _hack_steal(s, p),
        description="消耗 3 Intel：从 MC 最多的对手处偷 6 MC。",
    ))

    out.append(Card(
        id=212, name="反间谍特工", cost=5,
        card_type=CardType.AUTOMATED,
        tags=(),
        on_play=lambda s, p: _bag(p).update({"counter_espionage": True}),
        description="免疫黑客突袭/侦察类卡牌；签订过 NAP 仍生效。",
    ))

    return out


# ─────────────────── 实际效果实现 ───────────────────

def _orbital_strike(state: "GameState", attacker: "Player") -> None:
    """摧毁一座敌方城市（自动选 VP 最高玩家的随机城市）"""
    _bag(attacker)["force"] -= 6
    # 找目标：除自己外 VP 最高的有城市的玩家
    targets = []
    for p in state.players:
        if p.idx == attacker.idx:
            continue
        cities = [h for h in state.board.cities() if h.owner == p.idx]
        if cities:
            targets.append((p, cities))
    if not targets:
        state.emit(f"  💥 P{attacker.idx} 准备攻击但无目标")
        return
    targets.sort(key=lambda t: -t[0].total_vp(state))
    target, cities = targets[0]
    h = cities[0]
    h.tile = None
    h.owner = None
    target.vp_from_tiles -= 1
    state.emit(f"  💥 P{attacker.idx} 轨道打击 → P{target.idx} 失去 ({h.row},{h.col}) 城市！")
    # 战犯印记
    _bag(attacker)["war_crimes"] = _bag(attacker).get("war_crimes", 0) + 1
    # 检查 NAP
    naps = _bag(attacker)["naps"]
    if target.idx in naps and naps[target.idx] > 0:
        attacker.tr -= 5
        state.emit(f"  ⚖ P{attacker.idx} 违反 NAP → -5 TR")
        # 太空法庭奖励
        for p in state.players:
            if any(c.id == 210 for c in p.played):
                if p.idx != attacker.idx:
                    p.vp_from_milestones += 3
                    state.emit(f"  ⚖ P{p.idx} 太空法庭 +3VP")


def _hack_steal(state: "GameState", attacker: "Player") -> None:
    _bag(attacker)["intel"] -= 3
    targets = [p for p in state.players if p.idx != attacker.idx
               and not _bag(p).get("counter_espionage")]
    if not targets:
        state.emit(f"  🕵 黑客突袭无目标")
        return
    target = max(targets, key=lambda p: p.res.mc)
    stolen = min(6, target.res.mc)
    target.res.mc -= stolen
    attacker.res.mc += stolen
    state.emit(f"  🕵 P{attacker.idx} 黑客突袭 P{target.idx} → 偷 {stolen}MC")


def _arms_race(state: "GameState") -> None:
    for p in state.players:
        _add_force_prod(p, 1)
    state.emit(f"  🔫 军备竞赛：所有玩家 Force 产能 +1")


# ─────────────────── 公司（派系） ───────────────────

def _build_orbital_corps() -> list[Card]:
    out: list[Card] = []

    out.append(Card(
        id=290, name="Pentagon 五角大楼", cost=0,
        card_type=CardType.CORPORATION,
        on_play=lambda s, p: (
            setattr(p.res, "mc", 35),
            _add_force(p, 6),
            _add_force_prod(p, 2),
            _add_intel(p, 2),
        ),
        description="起始 35MC + 6 Force + 2 Force产能 + 2 Intel。专精军事压制。",
    ))

    out.append(Card(
        id=291, name="Magisterium 谍报集团", cost=0,
        card_type=CardType.CORPORATION,
        on_play=lambda s, p: (
            setattr(p.res, "mc", 38),
            _add_intel(p, 8),
            _add_intel_prod(p, 2),
            _bag(p).update({"shielded": True, "counter_espionage": True}),
        ),
        description="起始 38MC + 8 Intel + 2 Intel产能。免疫所有侦察类。",
    ))

    return out


# ─────────────────── DLC 主类 ───────────────────

class OrbitalWarfare(DLC):
    name = "orbital"
    display_name = "轨道战争"
    description = "引入 Force/Intel 资源、霸权税、破坏与侦察行动。让基础版的 multiplayer-solitaire 变成冷战博弈。"

    HEGEMONY_TAX = 5      # TR 第一名每代付 5MC
    INTEL_OFFSET = 3      # 用 3 Intel 抵消霸权税
    NAP_DURATION = 3      # 不结盟条约持续代数

    def get_extra_card_pool(self) -> list[Card]:
        return _build_orbital_cards()

    def get_extra_corps(self) -> list[Card]:
        return _build_orbital_corps()

    def on_player_setup(self, state, player) -> None:
        _bag(player)  # 初始化袋子

    def on_generation_end(self, state) -> None:
        # 1. Force / Intel 产能进账
        for p in state.players:
            b = _bag(p)
            b["force"] += b["force_prod"]
            b["intel"] += b["intel_prod"]

        # 2. 霸权税
        sorted_by_tr = sorted(state.players, key=lambda p: -p.tr)
        if len(sorted_by_tr) >= 2 and sorted_by_tr[0].tr > sorted_by_tr[1].tr:
            leader = sorted_by_tr[0]
            b = _bag(leader)
            if b["intel"] >= self.INTEL_OFFSET:
                b["intel"] -= self.INTEL_OFFSET
                state.emit(f"  💼 P{leader.idx} 用 {self.INTEL_OFFSET} Intel 规避霸权税")
            else:
                deduct = min(self.HEGEMONY_TAX, leader.res.mc)
                leader.res.mc -= deduct
                state.emit(f"  💼 P{leader.idx} 缴纳霸权税 -{deduct}MC")

        # 3. NAP 倒计时
        for p in state.players:
            naps = _bag(p)["naps"]
            for k in list(naps.keys()):
                naps[k] -= 1
                if naps[k] <= 0:
                    del naps[k]
                    state.emit(f"  📜 P{p.idx} 与 P{k} 的 NAP 到期")

    def extra_actions(self, state, player) -> list[Action]:
        out: list[Action] = []
        b = _bag(player)
        # 破坏：消耗 5 Force 弃对手 1 张已打出的事件卡（实际作用：使其不计 VP）
        if b["force"] >= 5:
            for q in state.players:
                if q.idx == player.idx:
                    continue
                # 找事件卡（红卡）作目标
                events_played = [c for c in q.played if c.card_type == CardType.EVENT and not getattr(c, "_sabotaged", False)]
                if events_played:
                    out.append(Action(
                        kind="dlc_sabotage",
                        payload={"target_idx": q.idx, "card_id": events_played[0].id},
                        label=f"⚔ 破坏 P{q.idx} 的「{events_played[0].name}」(5 Force)"
                    ))
                    break  # 每代只列一个目标避免菜单膨胀
        # 侦察：消耗 2 Intel 看对手手牌（仅对话框，不实际改变状态）
        if b["intel"] >= 2:
            for q in state.players:
                if q.idx == player.idx or _bag(q).get("shielded"):
                    continue
                if q.hand:
                    out.append(Action(
                        kind="dlc_spy",
                        payload={"target_idx": q.idx},
                        label=f"🕵 侦察 P{q.idx} 手牌 (2 Intel)"
                    ))
                    break
        # 签订 NAP
        for q in state.players:
            if q.idx == player.idx:
                continue
            if q.idx not in b["naps"]:
                out.append(Action(
                    kind="dlc_nap",
                    payload={"target_idx": q.idx},
                    label=f"📜 与 P{q.idx} 签订 NAP（3 代）"
                ))
                break
        return out

    def execute_action(self, state, player, action) -> bool:
        if action.kind == "dlc_sabotage":
            target = state.players[action.payload["target_idx"]]
            cid = action.payload["card_id"]
            target_card = next((c for c in target.played if c.id == cid), None)
            if not target_card:
                return True
            _bag(player)["force"] -= 5
            target_card._sabotaged = True
            target_card.vp = max(target_card.vp - 2, -3)
            state.emit(f"  ⚔ P{player.idx} 破坏 P{target.idx} 的「{target_card.name}」(VP 削减)")
            # NAP 检查
            if target.idx in _bag(player)["naps"]:
                player.tr -= 5
                state.emit(f"  ⚖ P{player.idx} 违反 NAP → -5 TR")
            return True
        if action.kind == "dlc_spy":
            target = state.players[action.payload["target_idx"]]
            _bag(player)["intel"] -= 2
            hand_summary = ", ".join(c.name for c in target.hand[:5])
            state.emit(f"  🕵 P{player.idx} 侦察 P{target.idx}：{hand_summary or '空手'}")
            return True
        if action.kind == "dlc_nap":
            target_idx = action.payload["target_idx"]
            _bag(player)["naps"][target_idx] = self.NAP_DURATION
            target = state.players[target_idx]
            _bag(target)["naps"][player.idx] = self.NAP_DURATION
            state.emit(f"  📜 P{player.idx} ⇄ P{target_idx} 签订 NAP（{self.NAP_DURATION} 代）")
            return True
        return False

    def serialize(self, state) -> dict:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "players": [
                {
                    "idx": p.idx,
                    "force": _bag(p)["force"],
                    "intel": _bag(p)["intel"],
                    "force_prod": _bag(p)["force_prod"],
                    "intel_prod": _bag(p)["intel_prod"],
                    "naps": {str(k): v for k, v in _bag(p)["naps"].items()},
                    "war_crimes": _bag(p).get("war_crimes", 0),
                }
                for p in state.players
            ],
        }
