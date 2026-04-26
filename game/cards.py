"""卡牌系统 — 基础类型与效果原语"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Optional, TYPE_CHECKING

from .resources import Tag, CardType

if TYPE_CHECKING:
    from .state import GameState, Player


# 效果签名：(state, player) -> None
# 检查签名：(state, player) -> bool
EffectFn = Callable[["GameState", "Player"], None]
CheckFn = Callable[["GameState", "Player"], bool]


@dataclass
class Card:
    id: int
    name: str
    cost: int
    card_type: CardType
    tags: tuple[Tag, ...] = ()
    vp: int = 0                     # 固定 VP（动态 VP 用 vp_fn）
    vp_fn: Optional[Callable[["GameState", "Player", "Card"], int]] = None
    can_play: Optional[CheckFn] = None    # 额外资格检查（除费用外）
    on_play: Optional[EffectFn] = None    # 立即效果
    action: Optional[EffectFn] = None     # 蓝卡 action
    action_used_each_gen: bool = False    # 是否每代限一次
    description: str = ""

    # 资源标记（如蓝卡上的微生物/动物计数器）
    resources_on_card: int = 0
    resource_kind: Optional[str] = None   # "microbe", "animal", "science", ...

    def play_cost_after_discounts(self, player: "Player") -> int:
        cost = self.cost
        # 公司能力打折
        if player.discount_fn:
            cost = player.discount_fn(self, cost)
        # 持续效果累计（蓝卡播种的属性）
        if getattr(player, "_space_discount", False) and Tag.SPACE in self.tags:
            cost -= 2
        if getattr(player, "_earth_discount", False) and Tag.EARTH in self.tags:
            cost -= 3
        if getattr(player, "_antigravity", False) and self.card_type != CardType.EVENT:
            cost -= 2
        return max(0, cost)

    def has_tag(self, tag: Tag) -> bool:
        return tag in self.tags

    def __repr__(self) -> str:
        return f"<Card #{self.id} {self.name} ({self.cost}M$ {self.card_type.value})>"


# ─────────────────── 效果工具 ───────────────────

def gain(resource: str, amount: int) -> EffectFn:
    """立即获得资源"""
    def fn(state, player):
        setattr(player.res, resource, getattr(player.res, resource) + amount)
    return fn


def lose(resource: str, amount: int, *, allow_partial: bool = False) -> EffectFn:
    def fn(state, player):
        cur = getattr(player.res, resource)
        if cur < amount and not allow_partial:
            return
        setattr(player.res, resource, max(0, cur - amount))
    return fn


def gain_prod(resource: str, amount: int) -> EffectFn:
    def fn(state, player):
        attr = f"{resource}_prod"
        # MC 产能可低至 -5；其他不能低于 0（这里只加正值，跳过校验）
        setattr(player.res, attr, getattr(player.res, attr) + amount)
    return fn


def lose_prod(resource: str, amount: int) -> EffectFn:
    """降低自己/对手产能 — 校验：mc≥-5, 其他≥0"""
    def fn(state, player):
        attr = f"{resource}_prod"
        cur = getattr(player.res, attr)
        floor = -5 if resource == "mc" else 0
        if cur - amount < floor:
            return  # 静默失败（卡牌实际应防止打出，这里兜底）
        setattr(player.res, attr, cur - amount)
    return fn


def raise_temperature(steps: int = 1) -> EffectFn:
    def fn(state, player):
        for _ in range(steps):
            state.raise_temperature(player)
    return fn


def raise_oxygen(steps: int = 1) -> EffectFn:
    def fn(state, player):
        for _ in range(steps):
            state.raise_oxygen(player)
    return fn


def place_ocean() -> EffectFn:
    def fn(state, player):
        state.queue_ocean_placement(player)
    return fn


def place_greenery() -> EffectFn:
    def fn(state, player):
        state.queue_greenery_placement(player)
    return fn


def place_city() -> EffectFn:
    def fn(state, player):
        state.queue_city_placement(player)
    return fn


def draw_cards(n: int) -> EffectFn:
    def fn(state, player):
        for _ in range(n):
            c = state.draw_card()
            if c is None:
                break
            player.hand.append(c)
    return fn


def add_resource_to_self(kind: str, amount: int) -> EffectFn:
    """给本牌（蓝卡）加自己的资源标记。需在 play 时通过 closure 引用"""
    def fn(state, player):
        # 由调用方在 play_card 中处理 — 这里是默认占位
        pass
    return fn


def combine(*fns: EffectFn) -> EffectFn:
    def fn(state, player):
        for f in fns:
            if f:
                f(state, player)
    return fn


# ─────────────────── 资格检查工具 ───────────────────

def require_temp_min(t: int) -> CheckFn:
    return lambda s, p: s.temperature >= t


def require_temp_max(t: int) -> CheckFn:
    return lambda s, p: s.temperature <= t


def require_oxygen_min(o: int) -> CheckFn:
    return lambda s, p: s.oxygen >= o


def require_oceans_min(n: int) -> CheckFn:
    return lambda s, p: s.oceans >= n


def require_oxygen_max(o: int) -> CheckFn:
    return lambda s, p: s.oxygen <= o


def require_tag_count(tag: Tag, n: int) -> CheckFn:
    return lambda s, p: p.count_tag(tag) >= n


def require_production_min(resource: str, n: int) -> CheckFn:
    return lambda s, p: getattr(p.res, f"{resource}_prod") >= n


def all_of(*checks: CheckFn) -> CheckFn:
    def fn(s, p):
        return all(c(s, p) for c in checks if c)
    return fn
