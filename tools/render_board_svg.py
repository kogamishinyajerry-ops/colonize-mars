"""把游戏状态渲染为 SVG（与前端 game.js 同样的 hex 布局）。

用法：
    from tools.render_board_svg import render_state_svg
    svg = render_state_svg(state, title="世代 5")
    Path("snap.svg").write_text(svg)
"""
from __future__ import annotations
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from game.state import GameState
from game.board import HexKind, TileType, ROW_LENGTHS


HEX_W = 64
HEX_H = HEX_W * 2 / math.sqrt(3)
ROW_OX = 24
ROW_OY = 24
PLAYER_COLORS = ["#ff6b3d", "#5dade2", "#6dd47e", "#c39bd3", "#ffd166"]

KIND_FILL = {
    "Land": "#6b3d2c",
    "OceanReserved": "#1a3a4a",
    "Volcanic": "#6b2c1a",
    "Noctis": "#1e3a5f",
}
KIND_STROKE = {
    "Land": "#8b5d3c",
    "OceanReserved": "#2c5c7a",
    "Volcanic": "#8b3c1a",
    "Noctis": "#5a8cbf",
}

TILE_FILL = {
    "Ocean": "#2e86c1",
    "Greenery": "#58d68d",
    "City": "#af7ac5",
}
TILE_STROKE = {
    "Ocean": "#5dade2",
    "Greenery": "#2ecc71",
    "City": "#d2b4de",
}

BONUS_GLYPH = {"steel": "S", "titanium": "Ti", "plant": "P", "card": "C", "heat": "H"}


def _hex_polygon(cx: float, cy: float) -> str:
    pts = [
        (cx, cy - HEX_H / 2),
        (cx + HEX_W / 2, cy - HEX_H / 4),
        (cx + HEX_W / 2, cy + HEX_H / 4),
        (cx, cy + HEX_H / 2),
        (cx - HEX_W / 2, cy + HEX_H / 4),
        (cx - HEX_W / 2, cy - HEX_H / 4),
    ]
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)


def render_state_svg(state: GameState, title: str = "", subtitle: str = "") -> str:
    max_len = max(ROW_LENGTHS)
    width = ROW_OX * 2 + max_len * HEX_W
    board_height = (len(ROW_LENGTHS) - 1) * (HEX_H * 0.75) + HEX_H + ROW_OY * 2
    legend_h = 60
    info_h = 80
    height = board_height + legend_h + info_h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" '
        'font-family="-apple-system, BlinkMacSystemFont, sans-serif">',
        # 背景
        f'<rect width="{width:.0f}" height="{height:.0f}" fill="#0d0d14"/>',
    ]

    # 标题栏
    if title or subtitle:
        parts.append(f'<text x="{width/2:.0f}" y="22" text-anchor="middle" '
                     'font-size="18" font-weight="700" fill="#ff6b3d">'
                     f'{title}</text>')
        if subtitle:
            parts.append(f'<text x="{width/2:.0f}" y="42" text-anchor="middle" '
                         'font-size="11" fill="#9c9cb0">'
                         f'{subtitle}</text>')

    # 棋盘
    y_offset = 50 if (title or subtitle) else ROW_OY
    for r, row in enumerate(state.board.grid):
        indent = (max_len - len(row)) * HEX_W / 2
        for c, h in enumerate(row):
            cx = ROW_OX + indent + c * HEX_W + HEX_W / 2
            cy = y_offset + r * (HEX_H * 0.75) + HEX_H / 2

            # 选 fill / stroke
            if h.tile:
                tile_name = h.tile.value
                fill = TILE_FILL[tile_name]
                stroke = TILE_STROKE[tile_name]
                stroke_w = "2"
            else:
                fill = KIND_FILL.get(h.kind.value, "#6b3d2c")
                stroke = KIND_STROKE.get(h.kind.value, "#8b5d3c")
                stroke_w = "1"
                if h.kind.value == "OceanReserved":
                    stroke_w = "1.5"

            extra_attr = ' stroke-dasharray="3,2"' if h.kind.value == "OceanReserved" and not h.tile else ''
            parts.append(
                f'<polygon points="{_hex_polygon(cx, cy)}" fill="{fill}" '
                f'stroke="{stroke}" stroke-width="{stroke_w}"{extra_attr}/>'
            )

            # 板块图标（用文字字符代替 emoji 避免 SVG 字体问题）
            if h.tile:
                tile_label = {"Ocean": "~", "Greenery": "Y", "City": "■"}[h.tile.value]
                tile_color = "#1a1a26" if h.tile.value == "City" else "#0d3a4a"
                if h.tile.value == "Greenery":
                    tile_color = "#0d3014"
                parts.append(
                    f'<text x="{cx:.1f}" y="{cy+5:.1f}" text-anchor="middle" '
                    f'font-size="20" font-weight="bold" fill="{tile_color}">{tile_label}</text>'
                )
            elif h.bonus:
                k, n = h.bonus
                glyph = BONUS_GLYPH.get(k, "?")
                label = f"{glyph}{n}" if n > 1 else glyph
                parts.append(
                    f'<text x="{cx:.1f}" y="{cy+4:.1f}" text-anchor="middle" '
                    f'font-size="11" fill="#ffd166">{label}</text>'
                )

            # 拥有者标记
            if h.owner is not None and h.tile and h.tile.value != "Ocean":
                ox = cx + HEX_W / 3
                oy = cy - HEX_H / 3
                color = PLAYER_COLORS[h.owner % len(PLAYER_COLORS)]
                parts.append(
                    f'<circle cx="{ox:.1f}" cy="{oy:.1f}" r="7" fill="{color}" '
                    f'stroke="#1a1a26" stroke-width="1.5"/>'
                    f'<text x="{ox:.1f}" y="{oy+3:.1f}" text-anchor="middle" '
                    f'font-size="9" font-weight="bold" fill="#1a1a26">{h.owner}</text>'
                )

            # 坐标
            parts.append(
                f'<text x="{cx:.1f}" y="{cy + HEX_H/2 - 3:.1f}" text-anchor="middle" '
                f'font-size="7" fill="#6c6c80">{h.row},{h.col}</text>'
            )

    # 底部状态条
    info_y = y_offset + (len(ROW_LENGTHS) - 1) * (HEX_H * 0.75) + HEX_H + 16
    parts.append(
        f'<rect x="0" y="{info_y-12:.0f}" width="{width:.0f}" height="{height-info_y+12:.0f}" '
        'fill="#1a1a26"/>'
    )

    # 全球参数
    bar_y = info_y + 8
    parts.append(
        f'<text x="20" y="{bar_y:.0f}" font-size="13" font-weight="bold" fill="#e6e6f0">'
        f'温度 {state.temperature}°C / +8 &#160;&#160; '
        f'氧气 {state.oxygen}% / 14% &#160;&#160; '
        f'海洋 {state.oceans} / 9</text>'
    )

    # 玩家排名
    rank = sorted(state.players, key=lambda p: -p.total_vp(state))
    rank_y = info_y + 32
    rank_str_parts = []
    for p in rank:
        c = PLAYER_COLORS[p.idx % len(PLAYER_COLORS)]
        rank_str_parts.append(
            f'<tspan fill="{c}" font-weight="bold">P{p.idx}</tspan> '
            f'<tspan fill="#e6e6f0">{p.corp_name or "—"} TR{p.tr} {p.total_vp(state)}VP</tspan>'
        )
    sep = '<tspan fill="#444"> | </tspan>'
    parts.append(
        f'<text x="20" y="{rank_y:.0f}" font-size="11">{sep.join(rank_str_parts)}</text>'
    )

    # 图例
    legend_y = info_y + 56
    legend_items = [
        ("#2e86c1", "海洋"),
        ("#58d68d", "绿地"),
        ("#af7ac5", "城市"),
        ("#6b2c1a", "火山"),
        ("#ffd166", "地块奖励"),
    ]
    lx = 20
    for color, label in legend_items:
        parts.append(
            f'<rect x="{lx}" y="{legend_y-9:.0f}" width="10" height="10" fill="{color}"/>'
            f'<text x="{lx+14}" y="{legend_y:.0f}" font-size="10" fill="#9c9cb0">{label}</text>'
        )
        lx += 80

    parts.append('</svg>')
    return "\n".join(parts)


if __name__ == "__main__":
    # 简单测试：渲染一个空棋盘
    from game.state import GameState, Player
    s = GameState(players=[Player(idx=0, name="测试")])
    svg = render_state_svg(s, "空棋盘测试")
    out = Path(__file__).parent.parent / "docs" / "demos" / "_test.svg"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg)
    print(f"写入 {out}")
