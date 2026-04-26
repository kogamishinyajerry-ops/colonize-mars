"""核心规则回归测试"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import random
from game.state import GameState, Player, TEMP_MIN, TEMP_MAX, OXY_MAX
from game.resources import ResourcePool, Tag, CardType
from game.board import Board, TileType, HexKind
from game.cards import Card, gain, gain_prod, raise_temperature
from game.engine import Engine
from game.ai import make_ai_decision_fns
from game.card_library import build_card_library, build_corporations
from game.milestones import build_milestones, build_awards, settle_award
from game.actions import can_play_card, list_legal_actions, execute
from game.projects import build_standard_projects


# ─────────────────── 资源 / 产能 ───────────────────

def test_production_phase_adds_tr_to_mc():
    p = Player(idx=0, name="t")
    p.tr = 25
    p.res.mc_prod = 3
    p.res.energy = 4
    p.res.energy_prod = 2
    p.res.production_phase(p.tr)
    assert p.res.mc == 28        # tr(25) + mc_prod(3)
    assert p.res.energy == 2     # 旧 4 转热, 加 prod 2
    assert p.res.heat == 4


def test_negative_mc_production_floor():
    p = Player(idx=0, name="t")
    p.res.mc_prod = -5
    p.res.mc = 10
    p.tr = 20
    p.res.production_phase(p.tr)
    assert p.res.mc == 25        # 10 + (-5) + 20


# ─────────────────── 全球参数 ───────────────────

def test_temperature_max_capped():
    state = GameState(players=[Player(idx=0, name="t")])
    state.temperature = TEMP_MAX
    assert state.raise_temperature(state.players[0]) is False


def test_oxygen_8_triggers_temperature_step():
    state = GameState(players=[Player(idx=0, name="t")])
    state.oxygen = 7
    state.temperature = TEMP_MIN
    state.raise_oxygen(state.players[0])
    assert state.oxygen == 8
    assert state.temperature == TEMP_MIN + 2  # 8% 触发温度+1档


def test_temperature_neg24_grants_heat_prod():
    state = GameState(players=[Player(idx=0, name="t")])
    state.temperature = -26
    p = state.players[0]
    state.raise_temperature(p)
    assert state.temperature == -24
    assert p.res.heat_prod == 1


def test_temperature_zero_queues_ocean():
    state = GameState(players=[Player(idx=0, name="t")])
    state.temperature = -2
    p = state.players[0]
    state.raise_temperature(p)
    assert state.temperature == 0
    assert any(kind == "ocean" for _, kind in state.pending_placements)


# ─────────────────── 棋盘 ───────────────────

def test_board_61_hexes():
    b = Board()
    assert sum(1 for _ in b.all_hexes()) == 61


def test_board_neighbors_inside_grid():
    b = Board()
    # 中央格 (4,4) 应有 6 个邻居
    h = b.hex_at(4, 4)
    assert len(b.neighbors(h)) == 6


def test_ocean_adjacency_bonus():
    b = Board()
    # 在两个相邻格各放一个海洋，第二个的邻接计数应≥1
    h1 = b.hex_at(4, 4)
    h2 = b.neighbors(h1)[0]
    b.place(h1, TileType.OCEAN)
    assert b.adjacent_oceans(h2) >= 1


# ─────────────────── 卡牌 ───────────────────

def test_card_library_loads():
    cards = build_card_library()
    assert len(cards) >= 30
    # ID 唯一
    assert len({c.id for c in cards}) == len(cards)


def test_can_play_card_requires_resources():
    state = GameState(players=[Player(idx=0, name="t")])
    p = state.players[0]
    cards = build_card_library()
    farming = next(c for c in cards if c.name.startswith("Farming"))
    p.hand.append(farming)
    p.res.mc = 5
    state.temperature = 4
    assert can_play_card(state, p, farming) is False  # MC 不够 (16)
    p.res.mc = 30
    state.temperature = 0
    assert can_play_card(state, p, farming) is False  # 温度不达标
    state.temperature = 4
    assert can_play_card(state, p, farming) is True


def test_steel_discount_for_building():
    state = GameState(players=[Player(idx=0, name="t")])
    p = state.players[0]
    cards = build_card_library()
    # Geothermal Power: 11MC, BUILDING 标签
    geo = next(c for c in cards if c.name.startswith("Geothermal"))
    p.hand.append(geo)
    p.res.mc = 5
    p.res.steel = 3   # 抵 6MC → 还需 5MC
    assert can_play_card(state, p, geo) is True


# ─────────────────── 动作执行 ───────────────────

def test_play_card_consumes_resources_and_triggers_effect():
    state = GameState(players=[Player(idx=0, name="t")])
    p = state.players[0]
    p.res.mc = 20
    state.deck = build_card_library()
    inventrix = next(c for c in state.deck if c.name.startswith("Inventrix"))
    p.hand.append(inventrix)
    legal = list_legal_actions(state, p, build_standard_projects(),
                               build_milestones(), build_awards())
    play = next(a for a in legal if a.kind == "play_card" and a.payload is inventrix)
    execute(state, p, play, [], build_milestones(), build_awards())
    assert p.res.mc == 11           # 20 - 9
    assert len(p.hand) >= 3          # 抽 3 张
    assert inventrix in p.played


# ─────────────────── 里程碑 ───────────────────

def test_terraformer_milestone_requires_tr_35():
    state = GameState(players=[Player(idx=0, name="t")])
    p = state.players[0]
    p.tr = 34
    ms = build_milestones()
    tf = next(m for m in ms if m.name.startswith("Terraformer"))
    assert tf.requirement(state, p) is False
    p.tr = 35
    assert tf.requirement(state, p) is True


def test_award_settlement_first_second():
    state = GameState(players=[Player(idx=i, name=f"P{i}") for i in range(3)])
    state.players[0].res.heat = 10
    state.players[1].res.heat = 5
    state.players[2].res.heat = 2
    aw = next(a for a in build_awards() if a.name.startswith("Thermalist"))
    out = settle_award(state, aw)
    assert out[0] == 5
    assert out[1] == 2
    assert 2 not in out


def test_award_tied_first_no_second():
    state = GameState(players=[Player(idx=i, name=f"P{i}") for i in range(3)])
    state.players[0].res.heat = 10
    state.players[1].res.heat = 10
    state.players[2].res.heat = 5
    aw = next(a for a in build_awards() if a.name.startswith("Thermalist"))
    out = settle_award(state, aw)
    assert out[0] == 5 and out[1] == 5
    assert 2 not in out


# ─────────────────── 端到端：AI 自对弈 ───────────────────

def test_ai_self_play_completes():
    rng = random.Random(7)
    players = [Player(idx=i, name=f"AI-{i}", is_ai=True) for i in range(3)]
    fns = {i: make_ai_decision_fns(seed=i + 100) for i in range(3)}
    state = GameState(players=players)
    engine = Engine(state, fns, rng=rng)
    result = engine.run(max_generations=15)
    assert state.generation > 1
    assert "ranking" in result
    assert len(result["ranking"]) == 3
    # 至少温度有所提升
    assert state.temperature > TEMP_MIN
    # 所有玩家 TR 应 > 起始 20
    for p in state.players:
        assert p.tr >= 20


def test_ai_self_play_4players_deterministic():
    """同种子两次跑应得相同排名"""
    def run_once():
        rng = random.Random(123)
        players = [Player(idx=i, name=f"AI-{i}", is_ai=True) for i in range(4)]
        fns = {i: make_ai_decision_fns(seed=i + 1) for i in range(4)}
        state = GameState(players=players)
        engine = Engine(state, fns, rng=rng)
        return engine.run(max_generations=12)

    r1 = run_once()
    r2 = run_once()
    assert r1["ranking"] == r2["ranking"]
