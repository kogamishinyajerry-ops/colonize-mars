"""DLC 集成测试 — 单独/混合启用各 DLC，AI 自对弈跑通"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import random
from game.state import GameState, Player
from game.engine import Engine
from game.ai import make_ai_decision_fns
from game.dlc import DLCManager, load_dlc


def _run_with_dlcs(dlc_names: list[str], seed: int = 1, n_players: int = 3,
                   max_gen: int = 10, **dlc_kwargs):
    rng = random.Random(seed)
    players = [Player(idx=i, name=f"AI-{i}", is_ai=True) for i in range(n_players)]
    fns = {i: make_ai_decision_fns(seed=seed + i) for i in range(n_players)}
    state = GameState(players=players)
    state.dlc_manager = DLCManager()
    for name in dlc_names:
        kw = dlc_kwargs.get(name, {})
        if name == "orbital":
            from game.dlc.orbital import OrbitalWarfare
            state.dlc_manager.add(OrbitalWarfare())
        elif name == "parallel":
            from game.dlc.parallel import ParallelMars
            state.dlc_manager.add(ParallelMars(**kw))
        elif name == "crimson":
            from game.dlc.crimson import CrimsonStorm
            state.dlc_manager.add(CrimsonStorm(**kw))
    engine = Engine(state, fns, rng=rng)
    result = engine.run(max_generations=max_gen)
    return state, result


# ─────────── DLC I ───────────

def test_orbital_runs_to_completion():
    state, result = _run_with_dlcs(["orbital"], seed=11)
    assert state.generation > 1
    assert "ranking" in result
    # 至少打出过 Force/Intel 卡的话产能 > 0
    has_orbital_action = any(
        "Force" in line or "Intel" in line or "霸权税" in line or "侦察" in line
        for line in state.log
    )
    assert has_orbital_action, "应有 orbital 卡或税触发"


def test_orbital_hegemony_tax_applies():
    state, _ = _run_with_dlcs(["orbital"], seed=22, max_gen=5)
    # 至少应有一条霸权税日志
    tax_lines = [l for l in state.log if "霸权税" in l or "Intel 规避" in l]
    assert tax_lines, "应触发霸权税"


# ─────────── DLC II ───────────

def test_parallel_factions_load():
    from game.dlc.parallel import FACTIONS, _bag
    assert len(FACTIONS) >= 3
    keys = [f.key for f in FACTIONS]
    assert "babylon" in keys
    assert "protocol" in keys
    assert "swarm" in keys


def test_parallel_freemode_runs():
    state, result = _run_with_dlcs(["parallel"], seed=33, max_gen=8)
    assert state.generation > 1
    # AI 玩家应被分配派系
    factions_picked = state.dlc_state.get("parallel_factions", {})
    assert len(factions_picked) > 0


def test_parallel_save_unlock():
    from game.dlc.parallel import load_save, unlock_faction, SAVE_PATH
    if SAVE_PATH.exists():
        SAVE_PATH.unlink()  # reset
    s = load_save()
    assert s["factions_unlocked"] == ["babylon"]
    unlock_faction("protocol")
    s2 = load_save()
    assert "protocol" in s2["factions_unlocked"]


# ─────────── DLC III ───────────

def test_crimson_normal_runs():
    state, result = _run_with_dlcs(["crimson"], seed=44, max_gen=10)
    cs = state.dlc_state["crimson"]
    assert "threat" in cs
    # 至少抽过几次灾害
    assert len(cs["disasters_log"]) >= 3


def test_crimson_easy_higher_threshold():
    state, _ = _run_with_dlcs(["crimson"], seed=55, max_gen=3,
                              crimson={"difficulty": "easy"})
    assert state.dlc_state["crimson"]["threshold"] == 50


def test_crimson_doom_can_fail():
    """跑足够长时间，doom 难度可能威胁条达上限 → game_over"""
    # 不一定每次失败，但 doom 阈值 20 + 灾害密度大，应该有相当概率
    failed_runs = 0
    for seed in range(10):
        state, _ = _run_with_dlcs(["crimson"], seed=seed * 7, max_gen=15,
                                  crimson={"difficulty": "doom"})
        if state.dlc_state["crimson"].get("failed"):
            failed_runs += 1
    # 10 次 doom 至少有 1 次失败
    assert failed_runs >= 1, f"doom 难度应有失败，实际 {failed_runs}/10"


# ─────────── 多 DLC 共存 ───────────

def test_orbital_plus_crimson_coexist():
    """轨道战争 + 红色风暴：玩家既要应对灾害又有 Force/Intel 资源"""
    state, result = _run_with_dlcs(["orbital", "crimson"], seed=66, max_gen=8)
    assert "ranking" in result
    assert "crimson" in state.dlc_state
    # 两个 DLC 的特征都出现过
    has_orbital = any("Force" in l or "霸权税" in l or "Intel" in l for l in state.log)
    has_crimson = any("灾害降临" in l for l in state.log)
    assert has_orbital and has_crimson


# ─────────── 基础不退化 ───────────

def test_no_dlc_still_works():
    """确认无 DLC 路径未退化"""
    state, result = _run_with_dlcs([], seed=77, max_gen=8)
    assert "ranking" in result
    assert state.dlc_manager is not None  # manager 存在但空


# ─────────── 修复回归 ───────────

def test_card_library_size():
    """卡库应充足支撑长局"""
    from game.card_library import build_card_library
    cards = build_card_library()
    # 4 玩家局: 起手 40 + 每代 16 张
    assert len(cards) >= 100, f"卡库太小: {len(cards)}"


def test_deck_reshuffle_when_empty():
    """deck 空时应自动从 discard 洗回"""
    from game.state import GameState, Player
    from game.cards import Card
    from game.resources import CardType
    import random
    state = GameState(players=[Player(idx=0, name="t")])
    state.rng = random.Random(1)
    state.deck = []
    state.discard = [Card(id=999, name=f"X{i}", cost=0, card_type=CardType.AUTOMATED)
                     for i in range(5)]
    c = state.draw_card()
    assert c is not None
    assert len(state.deck) == 4   # 抽走1, 4 张回炉
    assert len(state.discard) == 0


def test_long_game_4players_completes_naturally():
    """4 玩家长局可自然结束（参数全满）"""
    state, result = _run_with_dlcs([], seed=42, n_players=4, max_gen=30)
    # 应在 max_gen 之前就因参数全满结束 OR 最坏到 max_gen 也不崩
    assert state.parameters_complete() or state.generation >= 25
    # 必须有一次洗牌
    reshuffles = [l for l in state.log if "洗回卡组" in l]
    assert len(reshuffles) >= 1, "长局应触发至少 1 次洗牌"


def test_total_vp_with_state_no_crash():
    """parallel 朝圣队 vp_fn 需要 state，传 None 不应崩"""
    from game.state import GameState, Player
    from game.dlc.parallel import _babylon_cards
    p = Player(idx=0, name="t")
    pilgrim = next(c for c in _babylon_cards() if c.name.startswith("朝圣队"))
    p.played.append(pilgrim)
    # 传 None 应不崩（异常被吞）
    v_no_state = p.total_vp(None)
    assert v_no_state == p.tr  # tr + 0 (vp_fn 失败被跳过)
    # 传 state 应工作
    state = GameState(players=[p])
    v_with_state = p.total_vp(state)
    assert v_with_state == p.tr  # 0 城市


def test_ai_aids_under_high_threat():
    """高威胁时 AI 应优先援助队友"""
    from game.state import GameState, Player
    from game.actions import Action
    from game.ai import _action_score
    state = GameState(players=[Player(idx=0, name="A"), Player(idx=1, name="B")])
    state.dlc_state = {"crimson": {"threat": 25, "threshold": 30}}
    a_aid = Action("dlc_aid", {"to": 1, "res": "mc", "amount": 5}, "援助")
    a_pass = Action("pass", None, "跳过")
    s_aid = _action_score(a_aid, state, state.players[0])
    s_pass = _action_score(a_pass, state, state.players[0])
    assert s_aid > s_pass, f"高威胁援助应高于 pass: aid={s_aid} pass={s_pass}"


def test_milestone_includes_event_tags():
    """Builder 里程碑应包含事件卡上的建筑标签"""
    from game.state import GameState, Player
    from game.cards import Card
    from game.resources import CardType, Tag
    from game.milestones import build_milestones
    state = GameState(players=[Player(idx=0, name="t")])
    p = state.players[0]
    # 8 张事件卡，全是建筑标签
    for i in range(8):
        p.played.append(Card(id=900 + i, name=f"Evt{i}", cost=0,
                             card_type=CardType.EVENT, tags=(Tag.BUILDING, Tag.EVENT)))
    builder = next(m for m in build_milestones() if m.name.startswith("Builder"))
    assert builder.requirement(state, p) is True
