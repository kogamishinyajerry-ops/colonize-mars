"""资源类型与生产系统"""
from dataclasses import dataclass, field
from enum import Enum


class Resource(str, Enum):
    MC = "MC"           # MegaCredits 巨币
    STEEL = "Steel"     # 钢
    TITANIUM = "Titanium"  # 钛
    PLANTS = "Plants"   # 植物
    ENERGY = "Energy"   # 能源
    HEAT = "Heat"       # 热

    @property
    def short(self) -> str:
        return {
            "MC": "M$", "Steel": "Stl", "Titanium": "Ti",
            "Plants": "Pl", "Energy": "En", "Heat": "Ht",
        }[self.value]


class Tag(str, Enum):
    BUILDING = "Building"
    SPACE = "Space"
    SCIENCE = "Science"
    POWER = "Power"
    EARTH = "Earth"
    JOVIAN = "Jovian"
    PLANT = "Plant"
    MICROBE = "Microbe"
    ANIMAL = "Animal"
    CITY = "City"
    EVENT = "Event"
    WILD = "Wild"


class CardType(str, Enum):
    AUTOMATED = "Green"   # 绿卡：立即效果
    ACTIVE = "Blue"       # 蓝卡：持续/行动
    EVENT = "Red"         # 红卡：一次性事件
    CORPORATION = "Corp"


@dataclass
class ResourcePool:
    """玩家持有资源 + 产能"""
    mc: int = 0
    steel: int = 0
    titanium: int = 0
    plants: int = 0
    energy: int = 0
    heat: int = 0

    mc_prod: int = 0       # 可为负
    steel_prod: int = 0
    titanium_prod: int = 0
    plants_prod: int = 0
    energy_prod: int = 0
    heat_prod: int = 0

    def production_phase(self, tr: int) -> None:
        """生产阶段：先 energy→heat 转移，再加产能 + TR"""
        # 能源在生产阶段开始时全部转为热
        self.heat += self.energy
        self.energy = 0
        # 加产能 (mc 还要加 TR)
        self.mc += self.mc_prod + tr
        self.steel += self.steel_prod
        self.titanium += self.titanium_prod
        self.plants += self.plants_prod
        self.energy += self.energy_prod
        self.heat += self.heat_prod

    def can_pay_mc(self, cost: int, *, with_steel: int = 0, with_titanium: int = 0) -> bool:
        """可以用钢 (2MC each) 或钛 (3MC each) 抵建筑/太空卡费用"""
        if with_steel > self.steel or with_titanium > self.titanium:
            return False
        coverage = with_steel * 2 + with_titanium * 3
        if coverage > cost:
            # 允许少量超付（玩家选择消耗钢钛）
            pass
        remaining = max(0, cost - coverage)
        return self.mc >= remaining

    def pay_mc(self, cost: int, *, with_steel: int = 0, with_titanium: int = 0) -> int:
        """支付费用，返回实际消耗 MC。预先校验已通过。"""
        coverage = with_steel * 2 + with_titanium * 3
        self.steel -= with_steel
        self.titanium -= with_titanium
        remaining = max(0, cost - coverage)
        self.mc -= remaining
        return remaining
