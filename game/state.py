"""游戏状态：玩家 + GameState"""
from __future__ import annotations
import random as _random
from dataclasses import dataclass, field
from typing import Callable, Optional

from .resources import ResourcePool, Tag, CardType
from .board import Board, TileType, Hex, HexKind
from .cards import Card


# 全球参数边界
TEMP_MIN, TEMP_MAX, TEMP_STEP = -30, 8, 2
OXY_MIN, OXY_MAX = 0, 14
OCEAN_MAX = 9

STARTING_TR = 20
STARTING_HAND = 10  # 研究阶段每代 4 张


@dataclass
class Player:
    idx: int
    name: str
    is_ai: bool = False
    corp_name: str = ""
    res: ResourcePool = field(default_factory=ResourcePool)
    tr: int = STARTING_TR
    hand: list[Card] = field(default_factory=list)
    played: list[Card] = field(default_factory=list)
    blue_actions_used: set[int] = field(default_factory=set)  # card.id used this gen
    passed: bool = False
    vp_from_milestones: int = 0
    vp_from_awards: int = 0
    vp_from_tiles: int = 0    # 累计的板块 VP（绿地 + 城邻绿地）

    # 公司能力
    discount_fn: Optional[Callable[[Card, int], int]] = None
    on_card_played_fn: Optional[Callable] = None  # (state, player, card) -> None

    # DLC 自由字段（命名空间用前缀，如 "orbital_force", "parallel_faith"）
    dlc_bag: dict = field(default_factory=dict)

    def count_tag(self, tag: Tag) -> int:
        n = 0
        for c in self.played:
            if c.card_type == CardType.EVENT:
                continue  # 事件卡 (红卡) 标签不持续计数（除少数例外）
            n += sum(1 for t in c.tags if t == tag)
        return n

    def count_tag_including_events(self, tag: Tag) -> int:
        return sum(1 for c in self.played for t in c.tags if t == tag)

    def total_vp(self, state=None) -> int:
        v = self.tr
        v += self.vp_from_milestones + self.vp_from_awards + self.vp_from_tiles
        for c in self.played:
            v += c.vp
            if c.vp_fn:
                try:
                    v += c.vp_fn(state, self, c)
                except (AttributeError, TypeError):
                    pass   # vp_fn 需要 state 但未提供 — 估算时跳过
        return v


@dataclass
class GameState:
    players: list[Player]
    board: Board = field(default_factory=Board)
    generation: int = 1
    temperature: int = TEMP_MIN
    oxygen: int = OXY_MIN
    oceans: int = 0
    deck: list[Card] = field(default_factory=list)
    discard: list[Card] = field(default_factory=list)
    first_player_idx: int = 0
    current_player_idx: int = 0
    pending_placements: list[tuple] = field(default_factory=list)  # (player_idx, "ocean"/"greenery"/"city")
    claimed_milestones: dict = field(default_factory=dict)  # name -> player_idx
    funded_awards: dict = field(default_factory=dict)       # name -> player_idx
    log: list[str] = field(default_factory=list)
    game_over: bool = False

    # DLC 管理器（延迟初始化避免循环依赖）
    dlc_manager: Optional[object] = None
    dlc_state: dict = field(default_factory=dict)  # 各 DLC 自由读写

    # 牌堆 RNG（由 Engine 注入；用于洗牌）
    rng: Optional[_random.Random] = None
    _reshuffle_count: int = 0

    def draw_card(self) -> Optional[Card]:
        """安全抽 1 张：deck 空时自动把 discard 洗回。返回 None 表示彻底无牌。"""
        if not self.deck and self.discard:
            self.deck = self.discard[:]
            self.discard.clear()
            rng = self.rng or _random.Random(self._reshuffle_count + 7919)
            rng.shuffle(self.deck)
            self._reshuffle_count += 1
            self.emit(f"  🔁 弃牌堆洗回卡组 ({len(self.deck)} 张)")
        return self.deck.pop() if self.deck else None

    def draw_cards_n(self, n: int) -> list[Card]:
        """连抽 N 张，返回实际抽到的（可能少于 N）"""
        out = []
        for _ in range(n):
            c = self.draw_card()
            if c is None:
                break
            out.append(c)
        return out

    def emit(self, msg: str) -> None:
        self.log.append(msg)

    # ─────────── 全球参数提升（带 TR 与奖励） ───────────
    def raise_temperature(self, player: Player) -> bool:
        if self.temperature >= TEMP_MAX:
            return False
        # -24 → +1 热产能；-20 → +1 热产能；0 → 1 海洋
        self.temperature += TEMP_STEP
        player.tr += 1
        self.emit(f"  🌡 温度↑ → {self.temperature}°C  (TR+1, P{player.idx})")
        if self.temperature == -24 or self.temperature == -20:
            player.res.heat_prod += 1
            self.emit(f"  🌡 奖励：P{player.idx} 热产能+1")
        if self.temperature == 0:
            self.queue_ocean_placement(player)
        return True

    def raise_oxygen(self, player: Player) -> bool:
        if self.oxygen >= OXY_MAX:
            return False
        self.oxygen += 1
        player.tr += 1
        self.emit(f"  🌫 氧气↑ → {self.oxygen}%  (TR+1, P{player.idx})")
        # 氧气 8% 时，自动提升温度一档（如温度未满）
        if self.oxygen == 8 and self.temperature < TEMP_MAX:
            self.raise_temperature(player)
        return True

    def queue_ocean_placement(self, player: Player) -> None:
        if self.oceans >= OCEAN_MAX:
            return
        self.pending_placements.append((player.idx, "ocean"))

    def queue_greenery_placement(self, player: Player) -> None:
        self.pending_placements.append((player.idx, "greenery"))

    def queue_city_placement(self, player: Player) -> None:
        self.pending_placements.append((player.idx, "city"))

    def parameters_complete(self) -> bool:
        return (self.temperature >= TEMP_MAX
                and self.oxygen >= OXY_MAX
                and self.oceans >= OCEAN_MAX)

    def all_passed(self) -> bool:
        return all(p.passed for p in self.players)

    def active_players(self) -> list[Player]:
        return [p for p in self.players if not p.passed]
