"""火星棋盘 — 9 行六边形格子 + 海洋专用区"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TileType(str, Enum):
    OCEAN = "Ocean"
    GREENERY = "Greenery"
    CITY = "City"
    SPECIAL = "Special"   # 用于卡牌指定的特殊地块


class HexKind(str, Enum):
    LAND = "Land"
    OCEAN_RESERVED = "OceanReserved"  # 海洋专属位
    VOLCANIC = "Volcanic"             # 不能放绿地
    NOCTIS = "Noctis"                 # Noctis City 预留位


# 行长度（标准 TM 板：5,6,7,8,9,8,7,6,5 = 61 hexes）
ROW_LENGTHS = [5, 6, 7, 8, 9, 8, 7, 6, 5]


@dataclass
class Hex:
    row: int
    col: int
    kind: HexKind = HexKind.LAND
    bonus: tuple = field(default_factory=tuple)  # e.g. ("steel", 2) 或 ("card", 1)
    tile: Optional[TileType] = None
    owner: Optional[int] = None   # 玩家 idx

    @property
    def coord(self) -> str:
        return f"{self.row},{self.col}"

    def __repr__(self) -> str:
        if self.tile:
            return f"[{self.tile.value[0]}]"
        if self.kind == HexKind.OCEAN_RESERVED:
            return "(O)"
        if self.kind == HexKind.VOLCANIC:
            return "(V)"
        return " · "


# 海洋预留位（标准 9 个：固定坐标）
OCEAN_HEXES = {
    (0, 4), (1, 5), (3, 0), (4, 0), (4, 8),
    (5, 0), (5, 7), (6, 6), (7, 5),
}

# 火山区（Tharsis Tholus、Ascraeus、Pavonis、Arsia 一带，不能放绿地）
VOLCANIC_HEXES = {(0, 0), (1, 0), (2, 0), (5, 7)}

# Noctis City 位
NOCTIS_HEX = (3, 1)


def _build_board() -> list[list[Hex]]:
    board: list[list[Hex]] = []
    for r, length in enumerate(ROW_LENGTHS):
        row = []
        for c in range(length):
            kind = HexKind.LAND
            if (r, c) in OCEAN_HEXES:
                kind = HexKind.OCEAN_RESERVED
            elif (r, c) in VOLCANIC_HEXES:
                kind = HexKind.VOLCANIC
            elif (r, c) == NOCTIS_HEX:
                kind = HexKind.NOCTIS
            # 简化：均匀撒钢/钛/植物/卡牌奖励
            bonus = ()
            if (r + c) % 5 == 0:
                bonus = ("steel", 1)
            elif (r + c) % 5 == 1:
                bonus = ("plant", 1)
            elif (r + c) % 5 == 2:
                bonus = ("card", 1)
            elif (r * 3 + c) % 7 == 0:
                bonus = ("titanium", 1)
            row.append(Hex(row=r, col=c, kind=kind, bonus=bonus))
        board.append(row)
    return board


def neighbors(board: list[list[Hex]], r: int, c: int) -> list[Hex]:
    """六边形邻居 — 偏移坐标系（even-q vertical）"""
    out = []
    # 标准 TM 板的邻接关系（行 0-4 向下增宽，5-8 向下减窄）
    if r < len(ROW_LENGTHS) - 1:
        # 下方行
        next_len = ROW_LENGTHS[r + 1]
        cur_len = ROW_LENGTHS[r]
        if next_len > cur_len:
            # 下方更宽：邻居 (r+1, c), (r+1, c+1)
            for dc in (0, 1):
                nc = c + dc
                if 0 <= nc < next_len:
                    out.append(board[r + 1][nc])
        else:
            # 下方更窄：邻居 (r+1, c-1), (r+1, c)
            for dc in (-1, 0):
                nc = c + dc
                if 0 <= nc < next_len:
                    out.append(board[r + 1][nc])
    if r > 0:
        prev_len = ROW_LENGTHS[r - 1]
        cur_len = ROW_LENGTHS[r]
        if prev_len > cur_len:
            for dc in (0, 1):
                nc = c + dc
                if 0 <= nc < prev_len:
                    out.append(board[r - 1][nc])
        else:
            for dc in (-1, 0):
                nc = c + dc
                if 0 <= nc < prev_len:
                    out.append(board[r - 1][nc])
    # 同行左右
    cur_len = ROW_LENGTHS[r]
    if c > 0:
        out.append(board[r][c - 1])
    if c < cur_len - 1:
        out.append(board[r][c + 1])
    return out


class Board:
    def __init__(self) -> None:
        self.grid: list[list[Hex]] = _build_board()

    def hex_at(self, r: int, c: int) -> Optional[Hex]:
        if 0 <= r < len(self.grid) and 0 <= c < len(self.grid[r]):
            return self.grid[r][c]
        return None

    def all_hexes(self):
        for row in self.grid:
            for h in row:
                yield h

    def empty_land(self) -> list[Hex]:
        return [h for h in self.all_hexes()
                if h.tile is None and h.kind not in (HexKind.OCEAN_RESERVED,)]

    def empty_ocean(self) -> list[Hex]:
        return [h for h in self.all_hexes()
                if h.tile is None and h.kind == HexKind.OCEAN_RESERVED]

    def neighbors(self, h: Hex) -> list[Hex]:
        return neighbors(self.grid, h.row, h.col)

    def render(self) -> str:
        max_w = max(ROW_LENGTHS)
        lines = []
        for r, row in enumerate(self.grid):
            pad = " " * (max_w - len(row))
            cells = " ".join(repr(h) for h in row)
            lines.append(f"R{r}: {pad}{cells}")
        return "\n".join(lines)

    def place(self, h: Hex, tile: TileType, owner: Optional[int] = None) -> tuple:
        """放板块，返回触发的奖励 [(resource, amount), ...]"""
        h.tile = tile
        h.owner = owner
        bonuses = [h.bonus] if h.bonus else []
        return tuple(bonuses)

    def adjacent_oceans(self, h: Hex) -> int:
        return sum(1 for n in self.neighbors(h) if n.tile == TileType.OCEAN)

    def cities(self) -> list[Hex]:
        return [h for h in self.all_hexes() if h.tile == TileType.CITY]

    def greeneries(self) -> list[Hex]:
        return [h for h in self.all_hexes() if h.tile == TileType.GREENERY]
