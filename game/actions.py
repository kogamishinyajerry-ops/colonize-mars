"""玩家动作 — 枚举、合法性检查、执行"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from .resources import CardType, Tag
from .cards import Card
from .projects import StandardProject
from .milestones import Milestone, Award, AWARD_COSTS
from .board import TileType, Hex, HexKind

if TYPE_CHECKING:
    from .state import GameState, Player


@dataclass
class Action:
    kind: str               # play_card / std_project / blue_action / claim_milestone / fund_award / convert_plants / convert_heat / pass
    payload: Any = None     # 视 kind 而定
    label: str = ""

    def __repr__(self) -> str:
        return f"<Action {self.kind}: {self.label}>"


# ─────────────────── 资格检查 ───────────────────

def can_play_card(state: "GameState", player: "Player", card: Card) -> bool:
    """是否能打出某张项目卡（含费用、需求）"""
    if card not in player.hand:
        return False
    if card.card_type == CardType.CORPORATION:
        return False
    cost = card.play_cost_after_discounts(player)
    # 钢/钛抵扣
    max_steel = player.res.steel if Tag.BUILDING in card.tags else 0
    max_ti = player.res.titanium if Tag.SPACE in card.tags else 0
    coverage = max_steel * 2 + max_ti * 3
    affordable = (player.res.mc + coverage) >= cost
    # Helion 热抵 MC
    if not affordable and getattr(player, "can_use_heat_as_mc", False):
        affordable = (player.res.mc + coverage + player.res.heat) >= cost
    if not affordable:
        return False
    if card.can_play and not card.can_play(state, player):
        return False
    return True


def list_legal_actions(state: "GameState", player: "Player",
                       std_projects: list[StandardProject],
                       milestones: list[Milestone],
                       awards: list[Award]) -> list[Action]:
    out: list[Action] = []

    # 1. 打出手牌
    for c in player.hand:
        if can_play_card(state, player, c):
            out.append(Action("play_card", c, f"打出「{c.name}」({c.cost}M$)"))

    # 2. 标准项目
    for sp in std_projects:
        if sp.can_do(state, player):
            out.append(Action("std_project", sp, f"标准项目: {sp.name} ({sp.cost}M$)"))

    # 3. 蓝卡行动
    for c in player.played:
        if c.card_type == CardType.ACTIVE and c.action and c.id not in player.blue_actions_used:
            out.append(Action("blue_action", c, f"行动: {c.name}"))

    # 4. 认领里程碑
    if len(state.claimed_milestones) < 3 and player.res.mc >= 8:
        for m in milestones:
            if m.name not in state.claimed_milestones and m.requirement(state, player):
                out.append(Action("claim_milestone", m, f"认领里程碑: {m.name} (8M$ → 5VP)"))

    # 5. 资助奖励
    n_funded = len(state.funded_awards)
    if n_funded < 3:
        cost = AWARD_COSTS[n_funded]
        if player.res.mc >= cost:
            for aw in awards:
                if aw.name not in state.funded_awards:
                    out.append(Action("fund_award", aw, f"资助奖励: {aw.name} ({cost}M$)"))

    # 6. 植物 → 绿地（8 植物）
    if player.res.plants >= 8:
        out.append(Action("convert_plants", None, "用8植物造绿地（氧气+1）"))

    # 7. 热 → 温度（8 热）
    if player.res.heat >= 8 and state.temperature < 8:
        out.append(Action("convert_heat", None, "用8热提升温度1档"))

    # 8. 跳过 (pass)
    out.append(Action("pass", None, "跳过本代余下回合"))

    return out


# ─────────────────── 执行 ───────────────────

def execute(state: "GameState", player: "Player", action: Action,
            std_projects: list[StandardProject],
            milestones: list[Milestone],
            awards: list[Award]) -> None:
    if action.kind == "play_card":
        _execute_play_card(state, player, action.payload)
    elif action.kind == "std_project":
        sp: StandardProject = action.payload
        sp.execute(state, player)
        state.emit(f"  ▶ P{player.idx} 标准项目: {sp.name}")
    elif action.kind == "blue_action":
        c: Card = action.payload
        c.action(state, player)
        player.blue_actions_used.add(c.id)
        state.emit(f"  ▶ P{player.idx} 蓝卡行动: {c.name}")
    elif action.kind == "claim_milestone":
        m: Milestone = action.payload
        player.res.mc -= 8
        state.claimed_milestones[m.name] = player.idx
        player.vp_from_milestones += m.vp
        state.emit(f"  🏆 P{player.idx} 认领里程碑「{m.name}」 (+5VP)")
    elif action.kind == "fund_award":
        aw: Award = action.payload
        n_funded = len(state.funded_awards)
        cost = AWARD_COSTS[n_funded]
        player.res.mc -= cost
        state.funded_awards[aw.name] = player.idx
        state.emit(f"  🏅 P{player.idx} 资助奖励「{aw.name}」 ({cost}M$)")
    elif action.kind == "convert_plants":
        player.res.plants -= 8
        state.queue_greenery_placement(player)
        state.emit(f"  🌿 P{player.idx} 用8植物建造绿地")
    elif action.kind == "convert_heat":
        player.res.heat -= 8
        state.raise_temperature(player)
        state.emit(f"  🔥 P{player.idx} 用8热提升温度")
    elif action.kind == "pass":
        player.passed = True
        state.emit(f"  ⏸ P{player.idx} 跳过 (本代结束)")
    else:
        raise ValueError(f"未知动作: {action.kind}")


def _execute_play_card(state: "GameState", player: "Player", card: Card) -> None:
    cost = card.play_cost_after_discounts(player)

    # 优先用钢/钛抵扣
    use_steel = 0
    use_ti = 0
    if Tag.BUILDING in card.tags and player.res.steel > 0:
        # 用尽可能多的钢但不超过费用
        use_steel = min(player.res.steel, (cost + 1) // 2)
    if Tag.SPACE in card.tags and player.res.titanium > 0:
        remaining = cost - use_steel * 2
        if remaining > 0:
            use_ti = min(player.res.titanium, (remaining + 2) // 3)

    coverage = use_steel * 2 + use_ti * 3
    mc_needed = max(0, cost - coverage)

    # Helion 热抵 MC（不足 MC 时启用）
    use_heat = 0
    if mc_needed > player.res.mc and getattr(player, "can_use_heat_as_mc", False):
        use_heat = min(player.res.heat, mc_needed - player.res.mc)
        mc_needed -= use_heat

    player.res.steel -= use_steel
    player.res.titanium -= use_ti
    player.res.heat -= use_heat
    player.res.mc -= mc_needed

    # 移到 played
    player.hand.remove(card)
    if card.card_type == CardType.EVENT:
        # 事件卡也放到 played 区便于标签计数（按规则也可以；这里保留以便 VP/科学奖等）
        player.played.append(card)
    else:
        player.played.append(card)

    state.emit(
        f"  ▶ P{player.idx} 打出「{card.name}」 "
        f"(花费 {mc_needed}M$ + {use_steel}钢 + {use_ti}钛"
        + (f" + {use_heat}热" if use_heat else "") + ")"
    )

    if card.on_play:
        card.on_play(state, player)

    # 公司 hook（CrediCor 等）
    if player.on_card_played_fn:
        player.on_card_played_fn(state, player, card)
