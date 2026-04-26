"""游戏引擎 — 世代循环、板块放置、终局结算"""
from __future__ import annotations
import random
from typing import Callable, Optional

from .resources import CardType, Tag
from .state import GameState, Player, OXY_MAX, TEMP_MAX, OCEAN_MAX
from .board import TileType, Hex, HexKind
from .cards import Card
from .card_library import build_card_library, build_corporations
from .projects import build_standard_projects
from .milestones import build_milestones, build_awards, settle_award
from .actions import Action, list_legal_actions, execute


# 决策回调签名
# choose_action(state, player, legal_actions) -> Action
# choose_corp(state, player, options) -> Card
# choose_keep(state, player, drawn) -> list[Card]    （研究阶段：4选N，每张3MC）
# choose_hex(state, player, choices, kind) -> Hex
DecisionFn = Callable


class Engine:
    def __init__(self, state: GameState,
                 decision_fns: dict[int, dict[str, DecisionFn]],
                 rng: Optional[random.Random] = None) -> None:
        self.state = state
        self.fns = decision_fns
        self.rng = rng or random.Random()
        self.std_projects = build_standard_projects()
        self.milestones = build_milestones()
        self.awards = build_awards()

    # ─────────── 设置 ───────────
    def setup(self) -> None:
        s = self.state
        # 注入 rng 给 state（用于洗牌）
        s.rng = self.rng
        # DLC 注册 (on_register)
        if s.dlc_manager:
            s.dlc_manager.fire("on_register", s)

        # 卡库 = 基础 + DLC 贡献
        s.deck = build_card_library()
        if s.dlc_manager:
            for extra in s.dlc_manager.collect("get_extra_card_pool"):
                s.deck.append(extra)
        self.rng.shuffle(s.deck)

        # 公司池 = 基础 + DLC 贡献
        corps = build_corporations()
        if s.dlc_manager:
            for extra in s.dlc_manager.collect("get_extra_corps"):
                corps.append(extra)
        self.rng.shuffle(corps)
        while len(corps) < 2 * len(s.players):
            extra = build_corporations()
            self.rng.shuffle(extra)
            corps.extend(extra)

        for p in s.players:
            # DLC 可覆盖公司选择（如派系系统）
            override = None
            if s.dlc_manager:
                override = s.dlc_manager.first_truthy("override_corp_selection", s, p, corps)
            if override:
                # DLC 提供的派系选项流：仍然用 choose_corp 回调让前端选
                corp_choices = override["options"]
                chosen = self.fns[p.idx]["choose_corp"](s, p, corp_choices)
                p.corp_name = chosen.name
                chosen.on_play(s, p)
                s.emit(f"⚙ P{p.idx} ({p.name}) 选择派系「{chosen.name}」")
            else:
                corp_choices = [corps.pop(), corps.pop()]
                chosen = self.fns[p.idx]["choose_corp"](s, p, corp_choices)
                p.corp_name = chosen.name
                chosen.on_play(s, p)
                s.emit(f"⚙ P{p.idx} ({p.name}) 选择公司「{chosen.name}」 → {p.res.mc}MC")

            # 起始手牌张数（DLC 可改）
            hand_count = 10
            if s.dlc_manager:
                for d in s.dlc_manager.dlcs:
                    n = d.starting_hand_count(s, p)
                    if n is not None:
                        hand_count = n
                        break

            drawn = s.draw_cards_n(hand_count)
            kept = self.fns[p.idx]["choose_keep"](s, p, drawn)
            cost = len(kept) * 3
            if p.res.mc < cost:
                kept = kept[: max(0, p.res.mc // 3)]
                cost = len(kept) * 3
            p.res.mc -= cost
            p.hand.extend(kept)
            for c in drawn:
                if c not in kept:
                    s.discard.append(c)
            s.emit(f"⚙ P{p.idx} 起始手牌: {len(kept)}张, 花费{cost}M$, 余{p.res.mc}M$")

            # DLC 玩家级初始化（如派系起始资源）
            if s.dlc_manager:
                s.dlc_manager.fire("on_player_setup", s, p)

        if s.dlc_manager:
            s.dlc_manager.fire("on_setup_finished", s)

    # ─────────── 世代循环 ───────────
    def play_generation(self) -> None:
        s = self.state
        s.emit(f"\n═══ 世代 {s.generation} 开始 ═══")

        if s.dlc_manager:
            s.dlc_manager.fire("on_generation_start", s)

        # 1. 研究阶段（除第一代，因为已经在 setup 里发牌）
        if s.generation > 1:
            self._research_phase()

        # 2. 行动阶段
        if s.dlc_manager:
            s.dlc_manager.fire("on_action_phase_start", s)
        self._action_phase()

        # 3. 生产阶段
        self._production_phase()

        if s.dlc_manager:
            s.dlc_manager.fire("on_generation_end", s)
            # DLC 可阻止/触发结束
            for d in s.dlc_manager.dlcs:
                r = d.check_game_over(s)
                if r is True:
                    s.game_over = True
                    s.emit(f"  🛑 DLC「{d.display_name}」触发游戏结束")

        # 重置：blue actions, passed
        for p in s.players:
            p.blue_actions_used.clear()
            p.passed = False

        # 推进 first_player
        s.first_player_idx = (s.first_player_idx + 1) % len(s.players)
        s.current_player_idx = s.first_player_idx
        s.generation += 1

    def _research_phase(self) -> None:
        s = self.state
        s.emit("\n📚 研究阶段")
        for p in s.players:
            drawn = s.draw_cards_n(4)
            if not drawn:
                continue
            kept = self.fns[p.idx]["choose_keep"](s, p, drawn)
            cost = len(kept) * 3
            if p.res.mc < cost:
                kept = kept[: max(0, p.res.mc // 3)]
                cost = len(kept) * 3
            p.res.mc -= cost
            p.hand.extend(kept)
            for c in drawn:
                if c not in kept:
                    s.discard.append(c)
            s.emit(f"  📥 P{p.idx} 留 {len(kept)}/{len(drawn)} 张 (-{cost}M$)")

    def _action_phase(self) -> None:
        s = self.state
        s.emit("\n🎮 行动阶段")
        # 转一圈直到全员 pass
        idx = s.first_player_idx
        n = len(s.players)
        max_turns = n * 100   # 兜底防死循环
        turns = 0
        # 每玩家 1 回合内可执行 1 个动作；全员 pass 或 game_over 即出
        while not s.all_passed() and not s.game_over and turns < max_turns:
            p = s.players[idx]
            if not p.passed:
                self._take_turn(p)
                self._resolve_placements()
                if s.parameters_complete():
                    s.emit("\n🌍 三大全球参数已达上限！本代结束后终局。")
                    s.game_over = True
            idx = (idx + 1) % n
            turns += 1
        # 终局结束本代

    def _take_turn(self, player: Player) -> None:
        s = self.state
        if s.dlc_manager:
            s.dlc_manager.fire("on_player_turn_start", s, player)
        legal = list_legal_actions(s, player, self.std_projects, self.milestones, self.awards)
        # DLC 追加合法动作
        if s.dlc_manager:
            extra = s.dlc_manager.collect("extra_actions", s, player)
            # 把 pass 移到末尾保持习惯
            if extra:
                pass_idx = next((i for i, a in enumerate(legal) if a.kind == "pass"), -1)
                if pass_idx >= 0:
                    pass_action = legal.pop(pass_idx)
                    legal.extend(extra)
                    legal.append(pass_action)
                else:
                    legal.extend(extra)
        action = self.fns[player.idx]["choose_action"](s, player, legal)
        # DLC 自定义动作走自己的执行（kind 以 "dlc_" 开头）
        if action.kind.startswith("dlc_"):
            handled = False
            for d in s.dlc_manager.dlcs if s.dlc_manager else []:
                fn = getattr(d, "execute_action", None)
                if fn:
                    if fn(s, player, action):
                        handled = True
                        break
            if not handled:
                s.emit(f"  ⚠ 未处理的 DLC 动作: {action.kind}")
        else:
            execute(s, player, action, self.std_projects, self.milestones, self.awards)
        # DLC 后置钩子
        if s.dlc_manager:
            s.dlc_manager.fire("on_action_executed", s, player, action)
            if action.kind == "play_card":
                s.dlc_manager.fire("on_card_played", s, player, action.payload)

    def _resolve_placements(self) -> None:
        s = self.state
        while s.pending_placements:
            pi, kind = s.pending_placements.pop(0)
            player = s.players[pi]
            if kind == "ocean":
                if s.oceans >= OCEAN_MAX:
                    continue
                choices = s.board.empty_ocean()
                if not choices:
                    continue
                h = self.fns[pi]["choose_hex"](s, player, choices, "ocean")
                bonuses = s.board.place(h, TileType.OCEAN, owner=None)
                s.oceans += 1
                player.tr += 1
                s.emit(f"  🌊 P{pi} 放置海洋于 ({h.row},{h.col})  TR+1, 海洋 {s.oceans}/9")
                self._apply_hex_bonuses(player, h, bonuses)
            elif kind == "greenery":
                choices = [h for h in s.board.empty_land()
                           if h.kind != HexKind.OCEAN_RESERVED]
                # 优先放在自己绿地/城市相邻处
                owned_adj = [h for h in choices if any(
                    n.owner == pi for n in s.board.neighbors(h))]
                pool = owned_adj if owned_adj else choices
                if not pool:
                    continue
                h = self.fns[pi]["choose_hex"](s, player, pool, "greenery")
                bonuses = s.board.place(h, TileType.GREENERY, owner=pi)
                player.vp_from_tiles += 1
                s.emit(f"  🌱 P{pi} 放置绿地于 ({h.row},{h.col})  +1VP")
                self._apply_hex_bonuses(player, h, bonuses)
                # 绿地提升氧气
                if s.oxygen < OXY_MAX:
                    s.raise_oxygen(player)
            elif kind == "city":
                choices = [h for h in s.board.empty_land()
                           if h.kind != HexKind.OCEAN_RESERVED
                           and not any(n.tile == TileType.CITY for n in s.board.neighbors(h))]
                if not choices:
                    continue
                h = self.fns[pi]["choose_hex"](s, player, choices, "city")
                bonuses = s.board.place(h, TileType.CITY, owner=pi)
                s.emit(f"  🏙 P{pi} 放置城市于 ({h.row},{h.col})")
                self._apply_hex_bonuses(player, h, bonuses)

    def _apply_hex_bonuses(self, player: Player, h: Hex, bonuses) -> None:
        s = self.state
        # 海洋邻接：每相邻 1 个海洋 → +2MC
        adj_oceans = s.board.adjacent_oceans(h)
        if adj_oceans > 0:
            player.res.mc += 2 * adj_oceans
            s.emit(f"    💧 邻接 {adj_oceans} 海洋 → +{2*adj_oceans}MC")
        # 地块奖励
        for kind, amount in bonuses:
            if kind == "steel":
                player.res.steel += amount
                s.emit(f"    ⛏ 地块奖励 +{amount}钢")
            elif kind == "titanium":
                player.res.titanium += amount
                s.emit(f"    ⛏ 地块奖励 +{amount}钛")
            elif kind == "plant":
                player.res.plants += amount
                s.emit(f"    🌿 地块奖励 +{amount}植物")
            elif kind == "card":
                c = s.draw_card()
                if c:
                    player.hand.append(c)
                    s.emit(f"    🃏 地块奖励 +{amount}牌")
            elif kind == "heat":
                player.res.heat += amount

    def _production_phase(self) -> None:
        s = self.state
        s.emit("\n🏭 生产阶段")
        for p in s.players:
            before_mc = p.res.mc
            p.res.production_phase(p.tr)
            s.emit(
                f"  P{p.idx}: TR={p.tr} → MC {before_mc}→{p.res.mc} | "
                f"Stl={p.res.steel} Ti={p.res.titanium} Pl={p.res.plants} "
                f"En={p.res.energy} Ht={p.res.heat}"
            )

    # ─────────── 终局 ───────────
    def finalize(self) -> dict:
        s = self.state
        s.emit("\n═════════ 游戏结束 · 终局结算 ═════════")
        # 最后一代结束后：每位玩家可以把剩余植物转绿地（连锁氧气直到 14%）
        for p in s.players:
            while p.res.plants >= 8:
                p.res.plants -= 8
                s.queue_greenery_placement(p)
            self._resolve_placements()

        # 奖励结算
        for name, _funder_idx in s.funded_awards.items():
            aw = next(a for a in self.awards if a.name == name)
            results = settle_award(s, aw)
            for pi, vp in results.items():
                s.players[pi].vp_from_awards += vp
                s.emit(f"  🏅 奖励「{name}」: P{pi} +{vp}VP")

        # VP 汇总
        ranking = []
        for p in s.players:
            vp = p.total_vp(s)
            ranking.append((vp, p))
            s.emit(
                f"  P{p.idx} ({p.name}) [{p.corp_name}]: TR={p.tr} | "
                f"卡VP={sum(c.vp + (c.vp_fn(s,p,c) if c.vp_fn else 0) for c in p.played)} | "
                f"板块={p.vp_from_tiles} | 里程碑={p.vp_from_milestones} | "
                f"奖励={p.vp_from_awards} | 总分={vp}"
            )
        ranking.sort(key=lambda x: -x[0])
        s.emit(f"\n🏆 胜者: P{ranking[0][1].idx} ({ranking[0][1].name}) — {ranking[0][0]}VP")
        return {"ranking": [(p.idx, p.name, vp) for vp, p in ranking]}

    # ─────────── 主循环 ───────────
    def run(self, max_generations: int = 30) -> dict:
        self.setup()
        while not self.state.game_over and self.state.generation <= max_generations:
            self.play_generation()
        return self.finalize()
