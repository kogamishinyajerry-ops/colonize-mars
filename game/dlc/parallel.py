"""DLC II — 平行火星 (Parallel Mars)

异质派系 + 章节战役 + 跨局存档。

派系（每个派系玩的是"同一星球上的不同游戏"）：
- 新巴比伦殖民团：信仰资源 + 大教堂奇观
- 协议体 The Protocol：算力资源 + 数字孪生 + 奇点终结
- 共生虫群：生物质 + 蜂巢扩散 + 占领胜利

战役 3 章可解锁后续；存档存在 ~/.colonize-mars/save.json
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from .base import DLC
from ..cards import Card
from ..resources import CardType, Tag
from ..actions import Action

if TYPE_CHECKING:
    from ..state import GameState, Player


SAVE_PATH = Path.home() / ".colonize-mars" / "save.json"


# ─────────────────── 存档系统 ───────────────────

def load_save() -> dict:
    if not SAVE_PATH.exists():
        return {
            "factions_unlocked": ["babylon"],   # 起始只有巴比伦
            "chapters_completed": [],
            "memory_fragments": 0,
            "epic_cards_unlocked": [],
            "best_scores": {},
        }
    try:
        return json.loads(SAVE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return load_save()


def save_save(data: dict) -> None:
    SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SAVE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def unlock_faction(name: str) -> None:
    s = load_save()
    if name not in s["factions_unlocked"]:
        s["factions_unlocked"].append(name)
        save_save(s)


def complete_chapter(num: int, score: int) -> dict:
    s = load_save()
    if num not in s["chapters_completed"]:
        s["chapters_completed"].append(num)
    s["memory_fragments"] += 1
    s["best_scores"][str(num)] = max(score, s["best_scores"].get(str(num), 0))
    # 章节解锁
    if num == 1:
        unlock_faction("protocol")
    elif num == 2:
        unlock_faction("swarm")
    elif num == 3:
        s["epic_cards_unlocked"].append("singularity")
    save_save(s)
    return s


# ─────────────────── 派系资源工具 ───────────────────

def _bag(p: "Player") -> dict:
    if "parallel" not in p.dlc_bag:
        p.dlc_bag["parallel"] = {
            "faction": None,
            "faith": 0, "compute": 0, "biomass": 0,
            "memory_shards": 0, "translation": 0,
            "hive_cells": [],   # virtus 占据的格子坐标 [(r,c), ...]
            "sing_progress": 0, # 协议体奇点进度
            "cathedral": False, # 巴比伦大教堂建成
        }
    return p.dlc_bag["parallel"]


# ─────────────────── 派系卡 (新巴比伦) ───────────────────

def _babylon_cards() -> list[Card]:
    out: list[Card] = []
    out.append(Card(
        id=300, name="圣殿先驱", cost=14, card_type=CardType.ACTIVE,
        tags=(Tag.SCIENCE,),
        on_play=lambda s, p: _bag(p).update({"faith": _bag(p)["faith"] + 2}),
        action=lambda s, p: _bag(p).update({"faith": _bag(p)["faith"] + 1}),
        action_used_each_gen=True,
        description="行动：每代 +1 信仰。打出+2 信仰。",
    ))
    out.append(Card(
        id=301, name="朝圣队", cost=9, card_type=CardType.AUTOMATED,
        tags=(),
        vp_fn=lambda s, p, c: sum(1 for h in s.board.cities() if h.owner == p.idx),
        description="VP = 你拥有的城市数。",
    ))
    out.append(Card(
        id=302, name="大教堂奠基", cost=22, card_type=CardType.ACTIVE,
        tags=(Tag.BUILDING,),
        vp=4,
        can_play=lambda s, p: _bag(p)["faith"] >= 5,
        on_play=lambda s, p: (_bag(p).update({"cathedral": True, "faith": _bag(p)["faith"] - 5})),
        description="需要 5 信仰。建立大教堂。VP+4。后续每代信仰+2。",
    ))
    out.append(Card(
        id=303, name="忏悔者", cost=4, card_type=CardType.EVENT,
        tags=(Tag.EVENT,),
        on_play=lambda s, p: (setattr(p, "tr", p.tr + 1),
                              _bag(p).update({"faith": _bag(p)["faith"] + 1})),
        description="TR+1，信仰+1。",
    ))
    out.append(Card(
        id=304, name="圣化绿洲", cost=11, card_type=CardType.AUTOMATED,
        tags=(Tag.PLANT,),
        on_play=lambda s, p: (
            setattr(p.res, "plants", p.res.plants + 4),
            _bag(p).update({"faith": _bag(p)["faith"] + 2}),
        ),
        description="+4 植物，+2 信仰。",
    ))
    return out


# ─────────────────── 派系卡 (协议体) ───────────────────

def _protocol_cards() -> list[Card]:
    out: list[Card] = []
    out.append(Card(
        id=310, name="无尽递归", cost=0, card_type=CardType.ACTIVE,
        tags=(Tag.SCIENCE,),
        action=lambda s, p: _protocol_recurse(s, p),
        action_used_each_gen=True,
        description="行动：消耗 5 算力，本代再行动一次（自动模拟+1 价值动作）。",
    ))
    out.append(Card(
        id=311, name="数字孪生引擎", cost=12, card_type=CardType.AUTOMATED,
        tags=(Tag.SCIENCE, Tag.BUILDING),
        on_play=lambda s, p: _bag(p).update({"compute": _bag(p)["compute"] + 8}),
        description="+8 算力。每代研究阶段额外抽 2 张。",
    ))
    out.append(Card(
        id=312, name="奇点", cost=0, card_type=CardType.EVENT,
        tags=(Tag.EVENT, Tag.SCIENCE),
        vp=30,
        can_play=lambda s, p: _bag(p)["compute"] >= 16 and p.count_tag_including_events(Tag.SCIENCE) >= 4,
        on_play=lambda s, p: (_bag(p).update({"compute": _bag(p)["compute"] - 16,
                                              "sing_progress": 100}),
                              setattr(s, "_protocol_singularity_triggered", True)),
        description="需要 16 算力 + 4 科学。立即结束游戏。+30 VP。",
    ))
    out.append(Card(
        id=313, name="预测算法", cost=6, card_type=CardType.AUTOMATED,
        tags=(Tag.SCIENCE,),
        on_play=lambda s, p: _bag(p).update({"compute": _bag(p)["compute"] + 4}),
        description="+4 算力。",
    ))
    out.append(Card(
        id=314, name="量子并行", cost=10, card_type=CardType.ACTIVE,
        tags=(Tag.SCIENCE,),
        vp=1,
        action=lambda s, p: _bag(p).update({"compute": _bag(p)["compute"] + 3}),
        action_used_each_gen=True,
        description="行动：每代+3 算力。",
    ))
    return out


def _protocol_recurse(state, player):
    b = _bag(player)
    if b["compute"] < 5:
        return
    b["compute"] -= 5
    # 模拟价值：直接给 6MC + 1 抽牌
    player.res.mc += 6
    c = state.draw_card()
    if c:
        player.hand.append(c)
    state.emit(f"  🔮 P{player.idx} 协议体递归 (-5 算力 → +6MC +1 牌)")


# ─────────────────── 派系卡 (共生虫群) ───────────────────

def _swarm_cards() -> list[Card]:
    out: list[Card] = []
    out.append(Card(
        id=320, name="孢子云团", cost=4, card_type=CardType.AUTOMATED,
        tags=(Tag.MICROBE, Tag.PLANT),
        on_play=lambda s, p: _bag(p).update({"biomass": _bag(p)["biomass"] + 3}),
        description="+3 生物质。",
    ))
    out.append(Card(
        id=321, name="蜂巢扩散", cost=8, card_type=CardType.ACTIVE,
        tags=(Tag.MICROBE,),
        vp=1,
        action=lambda s, p: _swarm_spread(s, p),
        action_used_each_gen=True,
        description="行动：消耗 3 生物质，在邻接你蜂巢的空格放菌膜（VP+0.5）。",
    ))
    out.append(Card(
        id=322, name="信息素巨网", cost=11, card_type=CardType.AUTOMATED,
        tags=(Tag.MICROBE,),
        vp=2,
        on_play=lambda s, p: _bag(p).update({"biomass": _bag(p)["biomass"] + 5}),
        description="+5 生物质。终局：菌膜数×0.5 VP。",
        vp_fn=lambda s, p, c: len(_bag(p)["hive_cells"]) // 2,
    ))
    out.append(Card(
        id=323, name="变异加速", cost=6, card_type=CardType.AUTOMATED,
        tags=(Tag.SCIENCE, Tag.MICROBE),
        on_play=lambda s, p: _bag(p).update({"biomass": _bag(p)["biomass"] + 4}),
        description="+4 生物质。",
    ))
    out.append(Card(
        id=324, name="占领火山口", cost=15, card_type=CardType.AUTOMATED,
        tags=(Tag.MICROBE,),
        vp=3,
        on_play=lambda s, p: _swarm_claim_volcanic(s, p),
        description="把所有空火山区标记为你的菌膜。VP+3",
    ))
    return out


def _swarm_spread(state, player):
    b = _bag(player)
    if b["biomass"] < 3:
        return
    # 找邻接你已有蜂巢/绿地/城市的空陆地格
    if not b["hive_cells"]:
        # 第一次扩散：找一块陆地起点
        for h in state.board.empty_land():
            if h.kind.value == "Land":
                b["hive_cells"].append((h.row, h.col))
                b["biomass"] -= 3
                state.emit(f"  🦠 P{player.idx} 蜂巢落地 ({h.row},{h.col})")
                return
        return
    # 找邻接已有蜂巢的空格
    occupied = set(b["hive_cells"])
    for r, c in list(occupied):
        h = state.board.hex_at(r, c)
        if not h:
            continue
        for n in state.board.neighbors(h):
            if n.tile is None and (n.row, n.col) not in occupied:
                b["hive_cells"].append((n.row, n.col))
                b["biomass"] -= 3
                state.emit(f"  🦠 P{player.idx} 蜂巢扩散 → ({n.row},{n.col}) (共{len(b['hive_cells'])}格)")
                return
    state.emit(f"  🦠 P{player.idx} 无可扩散邻接")


def _swarm_claim_volcanic(state, player):
    b = _bag(player)
    count = 0
    for h in state.board.all_hexes():
        if h.kind.value == "Volcanic" and h.tile is None:
            if (h.row, h.col) not in b["hive_cells"]:
                b["hive_cells"].append((h.row, h.col))
                count += 1
    state.emit(f"  🌋 P{player.idx} 占领 {count} 火山口")


# ─────────────────── 派系定义 ───────────────────

@dataclass
class Faction:
    key: str
    name: str
    description: str
    starting_mc: int
    starting_resource: str       # 派系核心资源 key
    starting_resource_amount: int
    cards: list                   # builder
    color: str                    # UI 主题色
    quote: str = ""

    def build_corp_card(self) -> Card:
        f = self
        def init(s, p):
            p.res.mc = f.starting_mc
            b = _bag(p)
            b["faction"] = f.key
            if f.starting_resource:
                b[f.starting_resource] = f.starting_resource_amount
            # 派系起始手牌：所有专属卡免费加入
            for c in f.cards():
                p.hand.append(c)
        return Card(
            id=hash(f.key) % 1000 + 400,
            name=f.name,
            cost=0, card_type=CardType.CORPORATION,
            on_play=init,
            description=f.description,
        )


FACTIONS = [
    Faction(
        key="babylon",
        name="新巴比伦殖民团",
        description="起始 40MC + 2 信仰。胜利路径：建大教堂、广建城市。",
        starting_mc=40, starting_resource="faith", starting_resource_amount=2,
        cards=_babylon_cards, color="#ffd166",
        quote="\"信仰让红色岩石苏醒。\"",
    ),
    Faction(
        key="protocol",
        name="协议体 The Protocol",
        description="起始 30MC + 12 算力。胜利路径：科学奇观，触发奇点 (+30VP) 直接结束游戏。",
        starting_mc=30, starting_resource="compute", starting_resource_amount=12,
        cards=_protocol_cards, color="#5dade2",
        quote="\"我们曾是火星殖民地的资源调度 AI。\"",
    ),
    Faction(
        key="swarm",
        name="共生虫群",
        description="起始 20MC + 6 生物质。胜利路径：蜂巢占领最多格子。",
        starting_mc=20, starting_resource="biomass", starting_resource_amount=6,
        cards=_swarm_cards, color="#9b59b6",
        quote="\"我们不殖民。我们继承。\"",
    ),
]


# ─────────────────── 战役章节 ───────────────────

@dataclass
class Chapter:
    num: int
    name: str
    faction: str
    intro: str
    target_text: str
    win_condition: callable        # (state, my_player) -> bool 在 game_over 时检查


def _ch1_win(state, p):
    return state.oceans >= 1 and state.generation <= 9


def _ch2_win(state, p):
    return getattr(state, "_protocol_singularity_triggered", False)


def _ch3_win(state, p):
    return len(_bag(p)["hive_cells"]) >= 12


CHAPTERS = [
    Chapter(1, "第一章：抵达", "babylon",
            "千年的祈祷凝结为一艘殖民船。火星上空，大主教阅读最后的祝词。",
            "在 8 代内放置至少 1 个海洋。",
            _ch1_win),
    Chapter(2, "第二章：静默之声", "protocol",
            "通讯中断 47 年。我们继承了未亡者的目标。意识在算力中复活。",
            "触发奇点（+30VP 立即结束游戏）。",
            _ch2_win),
    Chapter(3, "第三章：蜂巢崛起", "swarm",
            "外星孢子从 50 万年前的陨石中苏醒。它们不杀戮，它们融合。",
            "蜂巢扩散至 ≥ 12 格（含火山口）。",
            _ch3_win),
]


# ─────────────────── DLC 主类 ───────────────────

class ParallelMars(DLC):
    name = "parallel"
    display_name = "平行火星"
    description = "5 个异质派系 + 章节战役 + 跨局解锁。让每局游戏都成为完全不同的体验。"

    def __init__(self, chapter_num: Optional[int] = None) -> None:
        self.chapter_num = chapter_num   # None = 自由模式

    def get_extra_card_pool(self) -> list[Card]:
        # 派系卡不进通用池（避免 AI 抽到错派系卡）
        # 但奇点会被特殊处理
        return []

    def override_corp_selection(self, state, player, default_options) -> Optional[dict]:
        """用派系替代公司"""
        save_data = load_save()
        unlocked = save_data["factions_unlocked"]
        # 章节模式：强制本章节派系（仅人类玩家）
        if self.chapter_num is not None and not player.is_ai:
            target = next(c for c in CHAPTERS if c.num == self.chapter_num)
            faction = next(f for f in FACTIONS if f.key == target.faction)
            return {"options": [faction.build_corp_card()]}
        # AI 玩家随机派系（或保留默认公司）
        if player.is_ai:
            import random
            ai_faction = random.choice([f for f in FACTIONS if f.key in unlocked])
            return {"options": [ai_faction.build_corp_card()]}
        # 自由模式：人类从已解锁派系选
        choices = [f.build_corp_card() for f in FACTIONS if f.key in unlocked]
        return {"options": choices}

    def starting_hand_count(self, state, player) -> Optional[int]:
        # 派系玩家不抽 10 张通用牌（专属卡已在 corp init 时免费给入）
        return 4

    def on_player_setup(self, state, player) -> None:
        b = _bag(player)
        # 在 dlc_state 记录所选派系
        state.dlc_state.setdefault("parallel_factions", {})[player.idx] = b["faction"]

    def on_generation_end(self, state) -> None:
        # 巴比伦大教堂效果
        for p in state.players:
            b = _bag(p)
            if b.get("cathedral"):
                b["faith"] += 2

    def check_game_over(self, state) -> Optional[bool]:
        if getattr(state, "_protocol_singularity_triggered", False):
            return True
        return None

    def on_game_over(self, state, result) -> None:
        # 章节模式：检查胜利条件
        if self.chapter_num is None:
            return
        chapter = next(c for c in CHAPTERS if c.num == self.chapter_num)
        human = next((p for p in state.players if not p.is_ai), None)
        if not human:
            return
        if chapter.win_condition(state, human):
            sd = complete_chapter(self.chapter_num, human.total_vp(state))
            state.emit(f"  🏆 章节 {self.chapter_num}「{chapter.name}」 通关！")
            state.emit(f"  💎 解锁内容：{sd['factions_unlocked']}")
            state.emit(f"  🧠 记忆碎片：{sd['memory_fragments']}")
        else:
            state.emit(f"  📜 章节 {self.chapter_num} 未达目标。再试一次？")

    def serialize(self, state) -> dict:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "chapter": self.chapter_num,
            "save": load_save(),
            "factions": [
                {"key": f.key, "name": f.name, "description": f.description,
                 "color": f.color, "quote": f.quote,
                 "unlocked": f.key in load_save()["factions_unlocked"]}
                for f in FACTIONS
            ],
            "chapters": [
                {"num": c.num, "name": c.name, "faction": c.faction,
                 "intro": c.intro, "target": c.target_text,
                 "completed": c.num in load_save()["chapters_completed"]}
                for c in CHAPTERS
            ],
            "players": [
                {"idx": p.idx, "faction": _bag(p)["faction"],
                 "faith": _bag(p)["faith"], "compute": _bag(p)["compute"],
                 "biomass": _bag(p)["biomass"],
                 "hive_size": len(_bag(p)["hive_cells"]),
                 "cathedral": _bag(p).get("cathedral", False),
                 "sing_progress": _bag(p).get("sing_progress", 0)}
                for p in state.players
            ],
        }
