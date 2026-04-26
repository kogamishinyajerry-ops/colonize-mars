"""里程碑 (Milestones) 与 奖励 (Awards)"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, TYPE_CHECKING

from .resources import Tag

if TYPE_CHECKING:
    from .state import GameState, Player


@dataclass
class Milestone:
    name: str
    description: str
    requirement: Callable[["GameState", "Player"], bool]   # 是否达标
    cost: int = 8                                           # 标准 8MC
    vp: int = 5


@dataclass
class Award:
    name: str
    description: str
    score: Callable[["GameState", "Player"], int]          # 玩家得分（按此排名）


# ─────────────────── 里程碑（最多3个被认领） ───────────────────

def build_milestones() -> list[Milestone]:
    return [
        Milestone(
            "Terraformer 改造者", "TR ≥ 35",
            lambda s, p: p.tr >= 35,
        ),
        Milestone(
            "Mayor 市长", "拥有 ≥ 3 座城市",
            lambda s, p: sum(1 for h in s.board.cities() if h.owner == p.idx) >= 3,
        ),
        Milestone(
            "Gardener 园丁", "拥有 ≥ 3 块绿地",
            lambda s, p: sum(1 for h in s.board.greeneries() if h.owner == p.idx) >= 3,
        ),
        Milestone(
            "Builder 建造者", "拥有 ≥ 8 个建筑标签",
            lambda s, p: p.count_tag_including_events(Tag.BUILDING) >= 8,
        ),
        Milestone(
            "Planner 谋划者", "手牌 ≥ 16 张",
            lambda s, p: len(p.hand) >= 16,
        ),
    ]


# ─────────────────── 奖励（最多3个被资助；终局结算） ───────────────────

def build_awards() -> list[Award]:
    return [
        Award(
            "Landlord 大地主", "拥有最多板块（绿地+城市）",
            lambda s, p: sum(1 for h in s.board.all_hexes() if h.owner == p.idx),
        ),
        Award(
            "Banker 银行家", "MC 产能最高",
            lambda s, p: p.res.mc_prod,
        ),
        Award(
            "Scientist 科学家", "科学标签最多",
            lambda s, p: p.count_tag_including_events(Tag.SCIENCE),
        ),
        Award(
            "Thermalist 热能学家", "热资源最多",
            lambda s, p: p.res.heat,
        ),
        Award(
            "Miner 矿工", "钢+钛资源最多",
            lambda s, p: p.res.steel + p.res.titanium,
        ),
    ]


# 资助奖励的 MC 成本（依次为 8, 14, 20）
AWARD_COSTS = (8, 14, 20)


def settle_award(state: "GameState", award: Award) -> dict:
    """终局结算单个奖励：返回 {player_idx: vp}"""
    scored = sorted(state.players, key=lambda p: award.score(state, p), reverse=True)
    if not scored:
        return {}
    out: dict[int, int] = {}
    # 第一名 5VP，第二名 2VP（4人模式标准）
    top_score = award.score(state, scored[0])
    firsts = [p for p in scored if award.score(state, p) == top_score]
    if len(firsts) == 1:
        out[scored[0].idx] = 5
        # 第二名（不并列）
        if len(scored) > 1:
            second_score = max(
                (award.score(state, p) for p in scored if p.idx != scored[0].idx),
                default=None,
            )
            if second_score is not None:
                seconds = [p for p in scored if award.score(state, p) == second_score and p.idx != scored[0].idx]
                if len(seconds) == 1:
                    out[seconds[0].idx] = 2
                else:
                    for p in seconds:
                        out[p.idx] = 1   # 并列第二
    else:
        # 并列第一：每人 5VP，无第二名
        for p in firsts:
            out[p.idx] = 5
    return out
