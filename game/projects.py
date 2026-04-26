"""标准项目 (Standard Projects) — 不需要卡牌的固定行动"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .state import GameState, Player


@dataclass
class StandardProject:
    name: str
    cost: int
    can_do: Callable[["GameState", "Player"], bool]
    execute: Callable[["GameState", "Player"], None]
    description: str = ""


def build_standard_projects() -> list[StandardProject]:
    return [
        StandardProject(
            "Sell Patents 出售专利", 0,
            lambda s, p: len(p.hand) > 0,
            _sell_patents,
            "弃任意张手牌，每张得1MC。",
        ),
        StandardProject(
            "Power Plant 发电站", 11,
            lambda s, p: p.res.mc >= 11,
            lambda s, p: (
                _spend_mc(p, 11),
                _add_prod(p, "energy", 1),
                s.emit(f"  ⚡ P{p.idx} 发电站：能源产能+1"),
            ),
            "付11MC，能源产能+1。",
        ),
        StandardProject(
            "Asteroid 小行星", 14,
            lambda s, p: p.res.mc >= 14 and s.temperature < 8,
            lambda s, p: (
                _spend_mc(p, 14),
                s.raise_temperature(p),
            ),
            "付14MC，温度+1档。",
        ),
        StandardProject(
            "Aquifer 含水层", 18,
            lambda s, p: p.res.mc >= 18 and s.oceans < 9,
            lambda s, p: (
                _spend_mc(p, 18),
                s.queue_ocean_placement(p),
            ),
            "付18MC，放置1海洋。",
        ),
        StandardProject(
            "Greenery 绿地", 23,
            lambda s, p: p.res.mc >= 23,
            lambda s, p: (
                _spend_mc(p, 23),
                s.queue_greenery_placement(p),
            ),
            "付23MC，放1块绿地（提升氧气）。",
        ),
        StandardProject(
            "City 城市", 25,
            lambda s, p: p.res.mc >= 25,
            lambda s, p: (
                _spend_mc(p, 25),
                _add_prod(p, "mc", 1),
                s.queue_city_placement(p),
            ),
            "付25MC，放置1城市，MC产能+1。",
        ),
    ]


def _sell_patents(state, player) -> None:
    n = len(player.hand)
    if n == 0:
        return
    # 简化：弃所有手牌
    state.discard.extend(player.hand)
    player.res.mc += n
    state.emit(f"  📜 P{player.idx} 出售{n}张专利 → +{n}MC")
    player.hand.clear()


def _spend_mc(player, cost: int) -> None:
    """标准项目支付，含 Standard Technology 折扣（-3）"""
    discount = 3 if getattr(player, "_std_discount", False) else 0
    player.res.mc -= max(0, cost - discount)


def _add_prod(player, resource: str, amount: int) -> None:
    attr = f"{resource}_prod"
    setattr(player.res, attr, getattr(player.res, attr) + amount)
