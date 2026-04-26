"""人类 CLI 决策接口"""
from __future__ import annotations
from typing import Optional

from .resources import CardType, Tag
from .state import GameState, Player
from .cards import Card
from .actions import Action
from .board import Hex


def _input(prompt: str, default: Optional[str] = None) -> str:
    try:
        s = input(prompt).strip()
    except EOFError:
        return default or ""
    return s or (default or "")


def render_player(p: Player) -> str:
    r = p.res
    return (
        f"╭─ P{p.idx} {p.name} [{p.corp_name}]  TR={p.tr}\n"
        f"│  💰{r.mc}({r.mc_prod:+})  ⛏{r.steel}({r.steel_prod:+})  "
        f"💎{r.titanium}({r.titanium_prod:+})\n"
        f"│  🌿{r.plants}({r.plants_prod:+})  ⚡{r.energy}({r.energy_prod:+})  "
        f"🔥{r.heat}({r.heat_prod:+})\n"
        f"│  手牌:{len(p.hand)} 已打出:{len(p.played)}  "
        f"VP预估:{p.total_vp()}\n"
        f"╰─"
    )


def render_state_header(s: GameState) -> str:
    return (
        f"━━━━ 世代 {s.generation}  "
        f"🌡 {s.temperature}°C  🌫 {s.oxygen}%  🌊 {s.oceans}/9 ━━━━"
    )


def make_human_decision_fns() -> dict:
    def choose_corp(state: GameState, player: Player, options: list[Card]) -> Card:
        print(f"\n[P{player.idx} {player.name}] 选择公司:")
        for i, c in enumerate(options):
            print(f"  {i+1}. {c.name} — {c.description}")
        while True:
            ans = _input("请输入序号 (1/2): ", "1")
            try:
                k = int(ans) - 1
                if 0 <= k < len(options):
                    return options[k]
            except ValueError:
                pass

    def choose_keep(state: GameState, player: Player, drawn: list[Card]) -> list[Card]:
        print(f"\n[P{player.idx}] 研究阶段：4选N (每张3MC, 当前 {player.res.mc}MC)")
        for i, c in enumerate(drawn):
            print(f"  {i+1}. [{c.cost}M$ {c.card_type.value[:1]}] {c.name} — {c.description[:60]}")
        ans = _input("输入要保留的序号(空格分隔, 留空=都不留): ", "")
        if not ans:
            return []
        kept = []
        for tok in ans.split():
            try:
                k = int(tok) - 1
                if 0 <= k < len(drawn):
                    kept.append(drawn[k])
            except ValueError:
                pass
        return kept

    def choose_action(state: GameState, player: Player, legal: list[Action]) -> Action:
        print(f"\n{render_state_header(state)}")
        print(render_player(player))
        print("─ 可选动作 ─")
        for i, a in enumerate(legal):
            print(f"  {i+1:>2}. {a.label}")
        # 也提供 ?h 看手牌, ?b 看棋盘
        while True:
            ans = _input("选择动作 (序号 / ?h手牌 / ?b棋盘 / ?p所有玩家): ", "")
            if ans == "?h":
                for c in player.hand:
                    print(f"   - [{c.cost}M$] {c.name} ({','.join(t.value for t in c.tags)})")
                    print(f"      {c.description}")
                continue
            if ans == "?b":
                print(state.board.render())
                continue
            if ans == "?p":
                for pp in state.players:
                    print(render_player(pp))
                continue
            try:
                k = int(ans) - 1
                if 0 <= k < len(legal):
                    return legal[k]
            except ValueError:
                pass

    def choose_hex(state: GameState, player: Player, choices: list[Hex], kind: str) -> Hex:
        print(f"\n[P{player.idx}] 选择放置位置 ({kind}):")
        # 先列前 12 个
        print(state.board.render())
        for i, h in enumerate(choices[:20]):
            adj = state.board.adjacent_oceans(h)
            bn = f" 奖励:{h.bonus}" if h.bonus else ""
            print(f"  {i+1}. ({h.row},{h.col})  邻接海洋:{adj}{bn}")
        if len(choices) > 20:
            print(f"  ... 还有 {len(choices)-20} 个，输入坐标 r,c 直接指定")
        while True:
            ans = _input("选择 (序号 或 r,c): ", "1")
            if "," in ans:
                try:
                    r, c = map(int, ans.split(","))
                    h = next((x for x in choices if x.row == r and x.col == c), None)
                    if h:
                        return h
                except ValueError:
                    pass
            else:
                try:
                    k = int(ans) - 1
                    if 0 <= k < len(choices):
                        return choices[k]
                except ValueError:
                    pass

    return {
        "choose_corp": choose_corp,
        "choose_keep": choose_keep,
        "choose_action": choose_action,
        "choose_hex": choose_hex,
    }
