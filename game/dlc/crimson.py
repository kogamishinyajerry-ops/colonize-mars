"""DLC III — 红色风暴 (Crimson Storm)

危机协作模式。火星本身（灾害引擎）是不可被说服的对手。

核心机制：
- 威胁条 (0 → THRESHOLD)：到顶则全员失败
- 每代抽 1 张灾害卡，效果立即结算或延迟
- 援助行动：无损耗送资源给队友（消耗 1 行动）
- 难度档位：决定威胁阈值与灾害频率
- 协作胜利：基础三参数全满 + 威胁<阈值
- 失败：威胁达阈值
"""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Optional

from .base import DLC
from ..cards import Card
from ..resources import CardType, Tag
from ..actions import Action

if TYPE_CHECKING:
    from ..state import GameState, Player


# ─────────────────── 难度档位 ───────────────────

DIFFICULTIES = {
    "easy":   {"threshold": 50, "disasters_per_gen": 1, "freq_mult": 0.5},
    "normal": {"threshold": 30, "disasters_per_gen": 1, "freq_mult": 1.0},
    "hard":   {"threshold": 25, "disasters_per_gen": 1, "freq_mult": 1.3},
    "doom":   {"threshold": 20, "disasters_per_gen": 2, "freq_mult": 1.5},
}


# ─────────────────── 灾害卡 ───────────────────

@dataclass
class Disaster:
    key: str
    name: str
    threat_increase: int
    description: str
    apply: Callable          # (state) -> None
    severity: str = "normal" # mild / normal / severe


def _all_players(state):
    return state.players


def _d_dust_storm(state):
    for p in _all_players(state):
        p.res.plants_prod = max(0, p.res.plants_prod - 1)
    state.emit("  🌪 沙尘暴：全员植物产能 -1")


def _d_solar_flare(state):
    for p in _all_players(state):
        loss = p.res.energy
        p.res.energy = 0
        if loss:
            state.emit(f"    ⚡ P{p.idx} 失去 {loss} 能源")
    state.emit("  ☀ 太阳耀斑：全员能源清零")


def _d_meteor_shower(state):
    """随机砸 3 块未占用陆地，标记为不可用"""
    from ..board import HexKind
    candidates = [h for h in state.board.empty_land() if h.kind == HexKind.LAND]
    if not candidates:
        return
    rng = random.Random(state.generation * 17 + len(state.log))
    n = min(3, len(candidates))
    for h in rng.sample(candidates, n):
        h.kind = HexKind.VOLCANIC
    state.emit(f"  ☄ 陨石雨：{n} 块陆地变为废墟")


def _d_plague(state):
    for p in _all_players(state):
        for c in p.played:
            if Tag.MICROBE in c.tags or Tag.ANIMAL in c.tags:
                c.resources_on_card = max(0, c.resources_on_card - 1)
    state.emit("  🦠 瘟疫：所有微生物/动物标记 -1")


def _d_market_crash(state):
    for p in _all_players(state):
        loss = min(p.res.mc, 8)
        p.res.mc -= loss
        if loss:
            state.emit(f"    💸 P{p.idx} 失去 {loss}MC")
    state.emit("  📉 地球市场崩盘：全员 -8MC（不足者全清）")


def _d_reactor_meltdown(state):
    for p in _all_players(state):
        if p.res.energy_prod >= 2:
            p.res.energy_prod -= 2
            state.emit(f"    ☢ P{p.idx} 能源产能 -2")
    state.emit("  ☢ 反应堆熔毁：≥2能源产能玩家 -2")


def _d_dam_breach(state):
    if state.oceans > 0:
        # 找一个海洋退化
        from ..board import TileType
        for h in state.board.all_hexes():
            if h.tile == TileType.OCEAN:
                h.tile = None
                state.oceans -= 1
                state.emit(f"  💧 大坝崩塌：海洋退化于 ({h.row},{h.col})")
                return
    state.emit("  💧 大坝崩塌（无海洋可退化）")


def _d_supply_freighter_lost(state):
    for p in _all_players(state):
        loss = min(p.res.steel + p.res.titanium, 5)
        steel_loss = min(p.res.steel, loss)
        p.res.steel -= steel_loss
        loss -= steel_loss
        p.res.titanium -= loss
    state.emit("  🚀 补给船失踪：全员钢/钛合计 -5")


def _d_solar_panel_failure(state):
    for p in _all_players(state):
        if p.res.energy_prod >= 1:
            p.res.energy_prod -= 1
    state.emit("  🔋 太阳能阵列故障：全员能源产能 -1")


def _d_phobos_drift(state):
    for p in _all_players(state):
        p.tr = max(0, p.tr - 2)
    state.emit("  🌑 Phobos 偏离：全员 TR -2")


def _d_microbe_mutation(state):
    """微生物标签效果反转一代（vp_fn 减半）"""
    state.emit("  🧬 微生物变异：动物/微生物 VP 暂时减半（终局结算）")
    state.dlc_state.setdefault("crimson", {})["microbe_penalty"] = True


def _d_civil_unrest(state):
    """随机一名玩家失去 3MC + 弃 1 张牌"""
    rng = random.Random(state.generation + 31)
    p = rng.choice(state.players)
    p.res.mc = max(0, p.res.mc - 3)
    if p.hand:
        p.hand.pop(0)
    state.emit(f"  ✊ 殖民地暴动：P{p.idx} -3MC -1 手牌")


DISASTERS = [
    Disaster("dust_storm", "沙尘暴", 2, "全员植物产能-1", _d_dust_storm, "mild"),
    Disaster("solar_flare", "太阳耀斑", 3, "全员能源清零", _d_solar_flare, "normal"),
    Disaster("meteor_shower", "陨石雨", 4, "3 块陆地变废墟", _d_meteor_shower, "severe"),
    Disaster("plague", "瘟疫", 2, "微生物/动物标记 -1", _d_plague, "mild"),
    Disaster("market_crash", "市场崩盘", 3, "全员 -8MC", _d_market_crash, "normal"),
    Disaster("reactor_meltdown", "反应堆熔毁", 4, "高能源产能玩家 -2", _d_reactor_meltdown, "severe"),
    Disaster("dam_breach", "大坝崩塌", 3, "海洋退化", _d_dam_breach, "normal"),
    Disaster("supply_lost", "补给船失踪", 2, "全员钢/钛 -5", _d_supply_freighter_lost, "mild"),
    Disaster("solar_failure", "太阳能故障", 2, "全员能源产能-1", _d_solar_panel_failure, "mild"),
    Disaster("phobos_drift", "Phobos 偏离", 5, "全员 -2 TR", _d_phobos_drift, "severe"),
    Disaster("microbe_mutation", "微生物变异", 3, "动物/微生物 VP 减半", _d_microbe_mutation, "normal"),
    Disaster("civil_unrest", "殖民地暴动", 2, "随机玩家 -3MC -1 手牌", _d_civil_unrest, "mild"),
]


# ─────────────────── 协作工具卡 ───────────────────

def _build_coop_cards() -> list[Card]:
    out: list[Card] = []
    out.append(Card(
        id=400, name="联合指挥塔", cost=12, card_type=CardType.ACTIVE,
        tags=(Tag.BUILDING, Tag.EARTH),
        vp=2,
        description="行动：援助队友时对方多收 50%（按下取整）。",
    ))
    out.append(Card(
        id=401, name="灾难响应小组", cost=15, card_type=CardType.ACTIVE,
        tags=(Tag.SCIENCE, Tag.EARTH),
        vp=2,
        action=lambda s, p: _emergency_response(s, p),
        action_used_each_gen=True,
        description="行动：威胁条 -3。",
    ))
    out.append(Card(
        id=402, name="应急共享协议", cost=8, card_type=CardType.AUTOMATED,
        tags=(Tag.EARTH,),
        on_play=lambda s, p: s.dlc_state.setdefault("crimson", {}).update({"shared_pool": True}),
        description="启用全员公共植物池（生产阶段汇总分配）。",
    ))
    out.append(Card(
        id=403, name="预警卫星", cost=6, card_type=CardType.AUTOMATED,
        tags=(Tag.SPACE, Tag.SCIENCE),
        on_play=lambda s, p: s.dlc_state.setdefault("crimson", {}).update({"forecast": True}),
        description="灾害将在抽出前一代预告。",
    ))
    return out


def _emergency_response(state, player):
    cs = state.dlc_state.setdefault("crimson", {"threat": 0})
    cs["threat"] = max(0, cs["threat"] - 3)
    state.emit(f"  🚒 P{player.idx} 应急响应：威胁 -3 → {cs['threat']}")


# ─────────────────── DLC 主类 ───────────────────

class CrimsonStorm(DLC):
    name = "crimson"
    display_name = "红色风暴"
    description = "协作模式：火星灾害是共同的敌人。威胁条满 = 全员失败。"

    def __init__(self, difficulty: str = "normal") -> None:
        self.difficulty = difficulty
        self.cfg = DIFFICULTIES.get(difficulty, DIFFICULTIES["normal"])
        self._next_disaster: Optional[Disaster] = None  # 预警的下一个灾害

    def get_extra_card_pool(self) -> list[Card]:
        return _build_coop_cards()

    def on_register(self, state) -> None:
        state.dlc_state.setdefault("crimson", {
            "threat": 0,
            "threshold": self.cfg["threshold"],
            "difficulty": self.difficulty,
            "disasters_log": [],
            "next_preview": None,
            "failed": False,
        })

    def on_generation_start(self, state) -> None:
        cs = state.dlc_state["crimson"]
        # 触发上一代预告的 / 或新抽取
        for _ in range(self.cfg["disasters_per_gen"]):
            if self._next_disaster:
                d = self._next_disaster
                self._next_disaster = None
            else:
                d = self._draw_disaster(state)
            if d is None:
                continue
            state.emit(f"\n  🚨 灾害降临：{d.name}「{d.description}」 (+{d.threat_increase} 威胁)")
            d.apply(state)
            cs["threat"] += d.threat_increase
            cs["disasters_log"].append({"gen": state.generation, "key": d.key, "name": d.name})
            # 失败检查
            if cs["threat"] >= cs["threshold"]:
                cs["failed"] = True
                state.emit(f"  💀 威胁达上限 {cs['threshold']}！火星殖民失败！")
                state.game_over = True
            # 预警下一代
            if cs.get("forecast"):
                self._next_disaster = self._draw_disaster(state)
                cs["next_preview"] = self._next_disaster.name if self._next_disaster else None
        # 自然衰减
        cs["threat"] = max(0, cs["threat"] - 1)

    def _draw_disaster(self, state) -> Optional[Disaster]:
        rng = random.Random(state.generation * 13 + len(state.log))
        # 灾害严重度按当前威胁条加权（越接近阈值越温和的减少）
        cs = state.dlc_state["crimson"]
        ratio = cs["threat"] / cs["threshold"]
        if ratio < 0.4:
            pool = [d for d in DISASTERS if d.severity in ("normal", "severe")]
        elif ratio > 0.7:
            pool = [d for d in DISASTERS if d.severity in ("mild", "normal")]
        else:
            pool = DISASTERS[:]
        return rng.choice(pool) if pool else None

    def extra_actions(self, state, player) -> list[Action]:
        out: list[Action] = []
        # 援助：把资源送给指定队友（每代每玩家最多 1 次）
        cs = state.dlc_state.get("crimson", {})
        sent = cs.setdefault("aided_this_gen", set())
        if player.idx in sent:
            return out
        for q in state.players:
            if q.idx == player.idx:
                continue
            for res, amount in [("mc", 5), ("plants", 2), ("steel", 2), ("titanium", 1)]:
                if getattr(player.res, res) >= amount:
                    out.append(Action(
                        kind="dlc_aid",
                        payload={"to": q.idx, "res": res, "amount": amount},
                        label=f"🤝 援助 P{q.idx}: {amount} {res}"
                    ))
                    break  # 每个目标只列一种避免菜单膨胀
        return out

    def execute_action(self, state, player, action) -> bool:
        if action.kind == "dlc_aid":
            cs = state.dlc_state.setdefault("crimson", {})
            cs.setdefault("aided_this_gen", set()).add(player.idx)
            to_idx = action.payload["to"]
            res = action.payload["res"]
            amount = action.payload["amount"]
            target = state.players[to_idx]
            # 联合指挥塔加成
            bonus = 1.5 if any(c.id == 400 for c in player.played) else 1.0
            actual = int(amount * bonus)
            setattr(player.res, res, getattr(player.res, res) - amount)
            setattr(target.res, res, getattr(target.res, res) + actual)
            state.emit(f"  🤝 P{player.idx} → P{to_idx} : {amount} {res} (实际 +{actual})")
            return True
        return False

    def on_generation_end(self, state) -> None:
        cs = state.dlc_state.get("crimson", {})
        cs["aided_this_gen"] = set()

    def check_game_over(self, state) -> Optional[bool]:
        cs = state.dlc_state.get("crimson", {})
        if cs.get("failed"):
            return True
        return None

    def on_game_over(self, state, result) -> None:
        cs = state.dlc_state.get("crimson", {})
        if cs.get("failed"):
            state.emit("\n  💀 协作失败：火星拒绝了你们")
            return
        # 协作胜利：基础参数全满
        if state.parameters_complete():
            score = sum(p.total_vp(state) for p in state.players) - cs["threat"] * 2
            grade = "S" if cs["threat"] < cs["threshold"] * 0.3 else \
                    "A" if cs["threat"] < cs["threshold"] * 0.5 else \
                    "B" if cs["threat"] < cs["threshold"] * 0.7 else "C"
            state.emit(f"\n  🏆 协作胜利！总评 [{grade}]  团队总分 {score}（剩余威胁 {cs['threat']}/{cs['threshold']}）")

    def serialize(self, state) -> dict:
        cs = state.dlc_state.get("crimson", {})
        return {
            "name": self.name,
            "display_name": self.display_name,
            "difficulty": self.difficulty,
            "threat": cs.get("threat", 0),
            "threshold": cs.get("threshold", 30),
            "failed": cs.get("failed", False),
            "next_preview": cs.get("next_preview"),
            "disasters_log": cs.get("disasters_log", [])[-8:],
            "co_op": True,
        }
