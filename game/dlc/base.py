"""DLC 基类与管理器 — 所有 DLC 通过这套钩子接入引擎"""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Any

if TYPE_CHECKING:
    from ..state import GameState, Player
    from ..cards import Card
    from ..actions import Action


class DLC:
    """所有 DLC 的抽象基类。仅实现需要的钩子。"""
    name: str = "base"
    display_name: str = "Base DLC"
    description: str = ""

    # ─── 生命周期 ───
    def on_register(self, state: "GameState") -> None: pass
    def on_setup_finished(self, state: "GameState") -> None: pass
    def on_player_setup(self, state: "GameState", player: "Player") -> None: pass
    def on_generation_start(self, state: "GameState") -> None: pass
    def on_generation_end(self, state: "GameState") -> None: pass
    def on_action_phase_start(self, state: "GameState") -> None: pass
    def on_player_turn_start(self, state: "GameState", player: "Player") -> None: pass
    def on_card_played(self, state: "GameState", player: "Player", card: "Card") -> None: pass
    def on_action_executed(self, state: "GameState", player: "Player", action: "Action") -> None: pass
    def on_game_over(self, state: "GameState", result: dict) -> None: pass

    # ─── 内容贡献 ───
    def get_extra_card_pool(self) -> list["Card"]:
        return []

    def get_extra_corps(self) -> list["Card"]:
        return []

    def extra_actions(self, state: "GameState", player: "Player") -> list["Action"]:
        return []

    # ─── 规则覆盖 ───
    def override_corp_selection(self, state: "GameState", player: "Player",
                                 default_options: list["Card"]) -> Optional[dict]:
        """返回 None=用默认; 返回 dict=新的选项流（含 prompt 与 options）"""
        return None

    def check_game_over(self, state: "GameState") -> Optional[bool]:
        """None=不干涉; True=立即结束; False=阻止结束"""
        return None

    def starting_hand_count(self, state: "GameState", player: "Player") -> Optional[int]:
        """覆盖起始手牌池（默认 10）"""
        return None

    # ─── 序列化（暴露给前端） ───
    def serialize(self, state: "GameState") -> dict:
        return {"name": self.name, "display_name": self.display_name}


class DLCManager:
    """聚合多个 DLC 的钩子；引擎只跟它打交道。"""
    def __init__(self) -> None:
        self.dlcs: list[DLC] = []

    def add(self, dlc: DLC) -> None:
        self.dlcs.append(dlc)

    def has(self, name: str) -> bool:
        return any(d.name == name for d in self.dlcs)

    def get(self, name: str) -> Optional[DLC]:
        return next((d for d in self.dlcs if d.name == name), None)

    # 多 DLC 串行触发
    def fire(self, hook: str, *args, **kwargs) -> None:
        for d in self.dlcs:
            fn = getattr(d, hook, None)
            if fn:
                fn(*args, **kwargs)

    def collect(self, hook: str, *args, **kwargs) -> list:
        out = []
        for d in self.dlcs:
            fn = getattr(d, hook, None)
            if fn:
                r = fn(*args, **kwargs)
                if r:
                    out.extend(r)
        return out

    def first_truthy(self, hook: str, *args, **kwargs) -> Optional[Any]:
        """取第一个返回真值的 DLC 结果（用于 override 类钩子）"""
        for d in self.dlcs:
            fn = getattr(d, hook, None)
            if fn:
                r = fn(*args, **kwargs)
                if r is not None:
                    return r
        return None

    def serialize(self, state: "GameState") -> list[dict]:
        return [d.serialize(state) for d in self.dlcs]
