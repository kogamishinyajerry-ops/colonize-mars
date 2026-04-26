"""Web 会话 — 后台线程跑游戏引擎，决策回调阻塞式从队列取答"""
from __future__ import annotations
import queue
import random
import threading
import time
from typing import Any, Optional

from .state import GameState, Player
from .engine import Engine
from .ai import make_ai_decision_fns
from .cards import Card
from .actions import Action, list_legal_actions
from .projects import build_standard_projects
from .milestones import build_milestones, build_awards
from .resources import CardType, Tag
from .board import Hex


class WebSession:
    """单局游戏的会话状态。线程安全：HTTP 处理器和 engine 线程共享。"""

    def __init__(self, n_players: int, human_indices: list[int],
                 seed: Optional[int] = None,
                 dlcs: Optional[list[dict]] = None) -> None:
        self.n_players = n_players
        self.human_indices = set(human_indices)
        self.seed = seed
        self.dlcs = dlcs or []     # [{"name":"orbital"}, {"name":"crimson","difficulty":"hard"}]
        self.state: Optional[GameState] = None
        self.engine: Optional[Engine] = None
        self.thread: Optional[threading.Thread] = None
        self.input_queue: queue.Queue = queue.Queue()
        self.pending: Optional[dict] = None       # 当前等待人类输入的决策
        self.pending_lock = threading.Lock()
        self.done: bool = False
        self.result: Optional[dict] = None
        self.last_log_idx: int = 0                # 用于增量日志

    # ─────────────── 决策回调 ───────────────
    def _make_human_fns(self, idx: int) -> dict:
        """返回阻塞式决策函数 — 设置 pending，等待 input_queue"""
        sess = self

        def _ask(payload: dict):
            with sess.pending_lock:
                sess.pending = payload
            ans = sess.input_queue.get()    # 阻塞直到 /api/submit 投递
            with sess.pending_lock:
                sess.pending = None
            return ans

        def choose_corp(state, player, options: list[Card]):
            payload = {
                "type": "corp",
                "player_idx": player.idx,
                "options": [_card_to_dict(c) for c in options],
                "prompt": "选择你的公司",
            }
            ans = _ask(payload)
            return options[int(ans["index"])]

        def choose_keep(state, player, drawn: list[Card]):
            payload = {
                "type": "research",
                "player_idx": player.idx,
                "drawn": [_card_to_dict(c) for c in drawn],
                "mc": player.res.mc,
                "prompt": "研究阶段：4 张抽牌中保留几张？(每张 3MC)",
            }
            ans = _ask(payload)
            indices = ans.get("indices", [])
            return [drawn[i] for i in indices if 0 <= i < len(drawn)]

        def choose_action(state, player, legal: list[Action]):
            payload = {
                "type": "action",
                "player_idx": player.idx,
                "legal": [_action_to_dict(i, a) for i, a in enumerate(legal)],
                "prompt": "选择你的本回合动作",
            }
            ans = _ask(payload)
            return legal[int(ans["index"])]

        def choose_hex(state, player, choices: list[Hex], kind: str):
            payload = {
                "type": "hex",
                "player_idx": player.idx,
                "kind": kind,
                "choices": [{"row": h.row, "col": h.col,
                              "bonus": h.bonus,
                              "adjacent_oceans": state.board.adjacent_oceans(h)}
                             for h in choices],
                "prompt": f"选择放置位置 — {kind}",
            }
            ans = _ask(payload)
            r, c = int(ans["row"]), int(ans["col"])
            return next(h for h in choices if h.row == r and h.col == c)

        return {
            "choose_corp": choose_corp,
            "choose_keep": choose_keep,
            "choose_action": choose_action,
            "choose_hex": choose_hex,
        }

    # ─────────────── 启动 ───────────────
    def start(self) -> None:
        rng = random.Random(self.seed)
        players = []
        decision_fns = {}
        for i in range(self.n_players):
            is_human = i in self.human_indices
            p = Player(idx=i,
                       name=("Player" if is_human else f"AI-{i}"),
                       is_ai=not is_human)
            players.append(p)
            if is_human:
                decision_fns[i] = self._make_human_fns(i)
            else:
                decision_fns[i] = make_ai_decision_fns(seed=(self.seed or 0) + i + 1)

        self.state = GameState(players=players)

        # 注册 DLC
        if self.dlcs:
            from .dlc import DLCManager
            mgr = DLCManager()
            for d in self.dlcs:
                name = d["name"]
                if name == "orbital":
                    from .dlc.orbital import OrbitalWarfare
                    mgr.add(OrbitalWarfare())
                elif name == "parallel":
                    from .dlc.parallel import ParallelMars
                    mgr.add(ParallelMars(chapter_num=d.get("chapter")))
                elif name == "crimson":
                    from .dlc.crimson import CrimsonStorm
                    mgr.add(CrimsonStorm(difficulty=d.get("difficulty", "normal")))
            self.state.dlc_manager = mgr

        self.engine = Engine(self.state, decision_fns, rng=rng)

        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        try:
            self.result = self.engine.run(max_generations=25)
        except Exception as e:
            self.state.emit(f"❌ Engine error: {e}")
        finally:
            self.done = True

    # ─────────────── 投递人类回答 ───────────────
    def submit(self, answer: dict) -> bool:
        with self.pending_lock:
            if not self.pending:
                return False
        self.input_queue.put(answer)
        # 等一下让 engine 处理
        time.sleep(0.05)
        return True

    # ─────────────── 状态快照（HTTP 用） ───────────────
    def snapshot(self) -> dict:
        if not self.state:
            return {"started": False}
        s = self.state
        # 增量日志
        new_logs = s.log[self.last_log_idx:]
        self.last_log_idx = len(s.log)
        with self.pending_lock:
            pending = self.pending
        # DLC 状态序列化
        dlc_blob = {}
        if s.dlc_manager:
            for d in s.dlc_manager.dlcs:
                dlc_blob[d.name] = d.serialize(s)
        return {
            "started": True,
            "done": self.done,
            "result": self.result,
            "generation": s.generation,
            "temperature": s.temperature,
            "oxygen": s.oxygen,
            "oceans": s.oceans,
            "claimed_milestones": s.claimed_milestones,
            "funded_awards": s.funded_awards,
            "first_player_idx": s.first_player_idx,
            "current_player_idx": s.current_player_idx,
            "deck_size": len(s.deck),
            "players": [_player_to_dict(p, s) for p in s.players],
            "board": _board_to_dict(s),
            "logs_new": new_logs,
            "pending": pending,
            "dlcs": dlc_blob,
        }

    def full_snapshot(self) -> dict:
        """完整快照（含全部日志，用于初次加载）"""
        snap = self.snapshot()
        snap["logs_all"] = self.state.log if self.state else []
        return snap


# ─────────────── 序列化辅助 ───────────────

def _card_to_dict(c: Card) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "cost": c.cost,
        "type": c.card_type.value,
        "tags": [t.value for t in c.tags],
        "vp": c.vp,
        "description": c.description,
        "resources_on_card": c.resources_on_card,
        "resource_kind": c.resource_kind,
        "has_action": c.action is not None,
    }


def _action_to_dict(idx: int, a: Action) -> dict:
    """动作 → 前端可显示对象。payload 不直接序列化（含函数），用 label。"""
    out = {"index": idx, "kind": a.kind, "label": a.label}
    if a.kind == "play_card":
        out["card_id"] = a.payload.id
    elif a.kind == "blue_action":
        out["card_id"] = a.payload.id
    elif a.kind in ("std_project", "claim_milestone", "fund_award"):
        out["name"] = getattr(a.payload, "name", "")
    return out


def _player_to_dict(p: Player, state=None) -> dict:
    r = p.res
    return {
        "idx": p.idx,
        "name": p.name,
        "is_ai": p.is_ai,
        "corp_name": p.corp_name,
        "tr": p.tr,
        "passed": p.passed,
        "resources": {
            "mc": r.mc, "steel": r.steel, "titanium": r.titanium,
            "plants": r.plants, "energy": r.energy, "heat": r.heat,
        },
        "production": {
            "mc": r.mc_prod, "steel": r.steel_prod, "titanium": r.titanium_prod,
            "plants": r.plants_prod, "energy": r.energy_prod, "heat": r.heat_prod,
        },
        "hand": [_card_to_dict(c) for c in p.hand],
        "played": [_card_to_dict(c) for c in p.played],
        "vp_estimate": p.total_vp(state),
        "vp_breakdown": {
            "tr": p.tr,
            "tiles": p.vp_from_tiles,
            "milestones": p.vp_from_milestones,
            "awards": p.vp_from_awards,
        },
        "blue_actions_used": list(p.blue_actions_used),
        "tag_counts": _count_tags(p),
    }


def _count_tags(p: Player) -> dict:
    out = {t.value: 0 for t in Tag}
    for c in p.played:
        if c.card_type == CardType.EVENT:
            continue
        for t in c.tags:
            out[t.value] = out.get(t.value, 0) + 1
    return out


def _board_to_dict(s: GameState) -> dict:
    rows = []
    for r, row in enumerate(s.board.grid):
        cells = []
        for h in row:
            cells.append({
                "row": h.row,
                "col": h.col,
                "kind": h.kind.value,
                "bonus": list(h.bonus) if h.bonus else None,
                "tile": h.tile.value if h.tile else None,
                "owner": h.owner,
            })
        rows.append(cells)
    return {"rows": rows}
