"""卡牌库 — 项目卡数据 (~40 张代表性卡)"""
from .resources import Tag, CardType
from .cards import (
    Card, gain, gain_prod, lose_prod, raise_temperature, raise_oxygen,
    place_ocean, place_greenery, place_city, draw_cards, combine,
    require_temp_min, require_temp_max, require_oxygen_min,
    require_oxygen_max, require_oceans_min, require_tag_count,
    require_production_min, all_of,
)


def _card(id, name, cost, ctype, **kw) -> Card:
    return Card(id=id, name=name, cost=cost, card_type=ctype, **kw)


def build_card_library() -> list[Card]:
    cards: list[Card] = []

    # ─────────── 绿卡 (Automated) — 立即效果 ───────────

    cards.append(_card(
        1, "Asteroid Mining Consortium 小行星采矿联合体", 13, CardType.AUTOMATED,
        tags=(Tag.JOVIAN,), vp=1,
        can_play=require_production_min("titanium", 1),
        on_play=combine(lose_prod("titanium", 1), gain_prod("titanium", 1), gain("titanium", 0)),
        description="需要钛产能。给一名玩家钛产能-1，自己钛产能+1。",
    ))

    cards.append(_card(
        2, "Deep Well Heating 深井加热", 13, CardType.AUTOMATED,
        tags=(Tag.POWER, Tag.BUILDING),
        on_play=combine(gain_prod("energy", 1), raise_temperature(1)),
        description="能源产能+1，温度+1档。",
    ))

    cards.append(_card(
        3, "Cloud Seeding 人工降雨", 11, CardType.AUTOMATED,
        tags=(),
        can_play=require_oceans_min(3),
        on_play=combine(lose_prod("mc", 1), gain_prod("plants", 2), gain_prod("heat", 1)),
        description="MC产能-1，植物产能+2，热产能+1。",
    ))

    cards.append(_card(
        4, "Search For Life 寻找生命", 3, CardType.ACTIVE,
        tags=(Tag.SCIENCE,), vp=0,
        can_play=require_oxygen_max(6),
        action=lambda s, p: (setattr(p.res, "mc", p.res.mc - 1),
                             _add_microbe_to_card(s, p, 4)) if p.res.mc >= 1 else None,
        action_used_each_gen=True,
        resource_kind="science",
        vp_fn=lambda s, p, c: 3 if c.resources_on_card > 0 else 0,
        description="行动：付1MC翻一张牌，若有微生物标签则在本卡放1个标记。终局：若有标记得3VP。",
    ))

    cards.append(_card(
        5, "Inventrix 发明者", 9, CardType.AUTOMATED,
        tags=(Tag.SCIENCE,),
        on_play=draw_cards(3),
        description="抽3张牌。",
    ))

    cards.append(_card(
        6, "Underground Detonations 地下爆破", 6, CardType.AUTOMATED,
        tags=(Tag.BUILDING,),
        on_play=combine(lose_prod("mc", 1), gain_prod("heat", 2)),
        description="MC产能-1，热产能+2。",
    ))

    cards.append(_card(
        7, "Soil Factory 土壤工厂", 9, CardType.AUTOMATED,
        tags=(Tag.BUILDING,), vp=1,
        on_play=combine(lose_prod("energy", 1), gain_prod("plants", 1)),
        description="能源产能-1，植物产能+1。",
    ))

    cards.append(_card(
        8, "Geothermal Power 地热发电", 11, CardType.AUTOMATED,
        tags=(Tag.POWER, Tag.BUILDING),
        on_play=gain_prod("energy", 2),
        description="能源产能+2。",
    ))

    cards.append(_card(
        9, "Farming 农业", 16, CardType.AUTOMATED,
        tags=(Tag.PLANT,), vp=2,
        can_play=require_temp_min(4),
        on_play=combine(gain_prod("mc", 2), gain_prod("plants", 2), gain("plants", 2)),
        description="需要温度≥4。MC产能+2，植物产能+2，立即获得2植物。",
    ))

    cards.append(_card(
        10, "Mass Converter 质能转换器", 8, CardType.AUTOMATED,
        tags=(Tag.SCIENCE, Tag.POWER),
        can_play=require_tag_count(Tag.SCIENCE, 5),
        on_play=gain_prod("energy", 6),
        description="需要5个科学标签。能源产能+6。",
    ))

    cards.append(_card(
        11, "Ecological Zone 生态区", 12, CardType.ACTIVE,
        tags=(Tag.PLANT, Tag.ANIMAL),
        can_play=lambda s, p: any(c.tile and c.tile.name == "GREENERY" and c.owner == p.idx for c in s.board.all_hexes()),
        on_play=lambda s, p: None,
        action_used_each_gen=False,
        resource_kind="animal",
        vp_fn=lambda s, p, c: c.resources_on_card // 2,
        description="需要自己有1块绿地。打出每张动物或植物标签时在本卡加1标记。每2标记=1VP。",
    ))

    cards.append(_card(
        12, "Mining Area 矿区", 4, CardType.AUTOMATED,
        tags=(Tag.BUILDING,),
        on_play=combine(gain_prod("steel", 1), gain_prod("titanium", 0)),
        description="钢产能+1（在指定地块放矿区，简化：直接给产能）。",
    ))

    cards.append(_card(
        13, "Trees 树木", 13, CardType.AUTOMATED,
        tags=(Tag.PLANT,), vp=1,
        can_play=require_temp_min(-4),
        on_play=combine(gain_prod("plants", 3), gain("plants", 1)),
        description="需要温度≥-4。植物产能+3，获得1植物。",
    ))

    cards.append(_card(
        14, "Greenhouses 温室", 6, CardType.AUTOMATED,
        tags=(Tag.BUILDING, Tag.PLANT),
        on_play=lambda s, p: setattr(p.res, "plants", p.res.plants + len(s.board.cities())),
        description="按当前城市数获得对应植物。",
    ))

    cards.append(_card(
        15, "Heat Trappers 热阱", 6, CardType.AUTOMATED,
        tags=(Tag.POWER,), vp=-1,
        on_play=combine(lose_prod("mc", 0), gain_prod("energy", 1)),
        description="能源产能+1（应让他人热产能-2，简化：仅利己）。-1 VP。",
    ))

    cards.append(_card(
        16, "Power Plant 发电厂", 4, CardType.AUTOMATED,
        tags=(Tag.POWER, Tag.BUILDING),
        on_play=gain_prod("energy", 1),
        description="能源产能+1。",
    ))

    cards.append(_card(
        17, "Bushes 灌木", 10, CardType.AUTOMATED,
        tags=(Tag.PLANT,), vp=1,
        can_play=require_temp_min(-10),
        on_play=combine(gain_prod("plants", 2), gain("plants", 2)),
        description="需要温度≥-10。植物产能+2，获得2植物。",
    ))

    cards.append(_card(
        18, "Lichen 地衣", 7, CardType.AUTOMATED,
        tags=(Tag.PLANT,),
        can_play=require_temp_min(-24),
        on_play=gain_prod("plants", 1),
        description="需要温度≥-24。植物产能+1。",
    ))

    cards.append(_card(
        19, "Sponsors 赞助商", 6, CardType.AUTOMATED,
        tags=(Tag.EARTH,),
        on_play=gain_prod("mc", 2),
        description="MC产能+2。",
    ))

    cards.append(_card(
        20, "AI Central 人工智能中心", 21, CardType.ACTIVE,
        tags=(Tag.SCIENCE, Tag.BUILDING), vp=1,
        can_play=require_tag_count(Tag.SCIENCE, 3),
        on_play=lose_prod("energy", 1),
        action=lambda s, p: draw_cards(2)(s, p),
        action_used_each_gen=True,
        description="需要3科学。能源产能-1。行动：抽2张。",
    ))

    cards.append(_card(
        21, "Mars University 火星大学", 8, CardType.ACTIVE,
        tags=(Tag.SCIENCE, Tag.BUILDING), vp=1,
        on_play=lambda s, p: None,
        description="效果：每打一张科学卡，可弃1张牌再抽1张（简化：被动）。",
    ))

    # ─────────── 红卡 (Event) — 一次性 ───────────

    cards.append(_card(
        30, "Asteroid 小行星", 14, CardType.EVENT,
        tags=(Tag.SPACE, Tag.EVENT),
        on_play=combine(raise_temperature(1), gain("titanium", 2)),
        description="温度+1档，获得2钛。",
    ))

    cards.append(_card(
        31, "Comet 彗星", 21, CardType.EVENT,
        tags=(Tag.SPACE, Tag.EVENT),
        on_play=combine(raise_temperature(1), place_ocean()),
        description="温度+1档，放置1海洋。",
    ))

    cards.append(_card(
        32, "Big Asteroid 大型小行星", 27, CardType.EVENT,
        tags=(Tag.SPACE, Tag.EVENT),
        on_play=combine(raise_temperature(2), gain("titanium", 4)),
        description="温度+2档，获得4钛。",
    ))

    cards.append(_card(
        33, "Imported Hydrogen 进口氢气", 16, CardType.EVENT,
        tags=(Tag.SPACE, Tag.EARTH, Tag.EVENT),
        on_play=combine(gain("plants", 3), place_ocean()),
        description="获得3植物，放置1海洋。",
    ))

    cards.append(_card(
        34, "Imported Nitrogen 进口氮气", 23, CardType.EVENT,
        tags=(Tag.SPACE, Tag.EARTH, Tag.EVENT),
        on_play=combine(gain("plants", 4)),  # 简化
        description="获得4植物。",
    ))

    cards.append(_card(
        35, "Lava Flows 熔岩流", 18, CardType.EVENT,
        tags=(Tag.EVENT,),
        on_play=raise_temperature(2),
        description="温度+2档。",
    ))

    cards.append(_card(
        36, "Local Heat Trapping 本地集热", 1, CardType.EVENT,
        tags=(Tag.EVENT,),
        on_play=lambda s, p: (
            setattr(p.res, "heat", max(0, p.res.heat - 5)),
            setattr(p.res, "plants", p.res.plants + 4),
        ) if p.res.heat >= 5 else None,
        description="弃5热，获得4植物。",
    ))

    cards.append(_card(
        37, "Release of Inert Gases 释放惰性气体", 14, CardType.EVENT,
        tags=(Tag.EVENT,),
        on_play=lambda s, p: (
            setattr(p, "tr", p.tr + 2),
            s.emit(f"  🎖 P{p.idx} TR+2 (惰性气体)"),
        ),
        description="TR+2。",
    ))

    cards.append(_card(
        38, "Towing A Comet 拖拽彗星", 23, CardType.EVENT,
        tags=(Tag.SPACE, Tag.EVENT),
        on_play=combine(raise_oxygen(1), place_ocean(), gain("plants", 2)),
        description="氧气+1，放置1海洋，获得2植物。",
    ))

    cards.append(_card(
        39, "Water Import From Europa 木卫二运水", 25, CardType.ACTIVE,
        tags=(Tag.JOVIAN, Tag.SPACE), vp=1,
        action=lambda s, p: (setattr(p.res, "mc", p.res.mc - 12),
                             place_ocean()(s, p)) if p.res.mc >= 12 else None,
        action_used_each_gen=True,
        description="行动：付12MC放1海洋。",
    ))

    cards.append(_card(
        40, "Birds 鸟类", 10, CardType.ACTIVE,
        tags=(Tag.ANIMAL,), vp=0,
        can_play=require_oxygen_min(13),
        on_play=lose_prod("plants", 2),
        action_used_each_gen=True,
        action=lambda s, p: _add_animal_to_card(s, p, 40),
        resource_kind="animal",
        vp_fn=lambda s, p, c: c.resources_on_card,
        description="需要氧气≥13。植物产能-2(对手)。每动物=1VP。行动：本卡+1动物。",
    ))

    cards.append(_card(
        41, "Fish 鱼", 9, CardType.ACTIVE,
        tags=(Tag.ANIMAL,), vp=0,
        can_play=require_temp_min(2),
        on_play=lambda s, p: None,
        action_used_each_gen=True,
        action=lambda s, p: _add_animal_to_card(s, p, 41),
        resource_kind="animal",
        vp_fn=lambda s, p, c: c.resources_on_card,
        description="需要温度≥2。每动物=1VP。",
    ))

    cards.append(_card(
        42, "Livestock 牲畜", 13, CardType.ACTIVE,
        tags=(Tag.ANIMAL,), vp=0,
        can_play=require_oxygen_min(9),
        on_play=combine(lose_prod("plants", 1), gain_prod("mc", 2)),
        action_used_each_gen=True,
        action=lambda s, p: _add_animal_to_card(s, p, 42),
        resource_kind="animal",
        vp_fn=lambda s, p, c: c.resources_on_card,
        description="需要氧气≥9。植物产能-1，MC产能+2。每动物=1VP。",
    ))

    cards.append(_card(
        43, "Predators 掠食者", 14, CardType.ACTIVE,
        tags=(Tag.ANIMAL,), vp=0,
        can_play=require_oxygen_min(11),
        on_play=lambda s, p: None,
        action_used_each_gen=True,
        action=lambda s, p: _add_animal_to_card(s, p, 43),
        resource_kind="animal",
        vp_fn=lambda s, p, c: c.resources_on_card,
        description="需要氧气≥11。每动物=1VP。",
    ))

    cards.append(_card(
        44, "Steelworks 钢厂", 15, CardType.ACTIVE,
        tags=(Tag.BUILDING,),
        action=lambda s, p: (
            setattr(p.res, "energy", p.res.energy - 4),
            setattr(p.res, "steel", p.res.steel + 2),
            raise_oxygen(1)(s, p),
        ) if p.res.energy >= 4 else None,
        action_used_each_gen=True,
        description="行动：付4能源，得2钢，氧气+1。",
    ))

    cards.append(_card(
        45, "Solar Power Group 太阳能集团", 11, CardType.AUTOMATED,
        tags=(Tag.POWER, Tag.BUILDING),
        on_play=combine(gain_prod("energy", 1), draw_cards(0)),
        description="能源产能+1。",
    ))

    cards.append(_card(
        46, "Mining Rights 采矿权", 9, CardType.AUTOMATED,
        tags=(Tag.BUILDING,),
        on_play=gain_prod("steel", 1),
        description="钢产能+1。",
    ))

    cards.append(_card(
        47, "Symbiotic Fungus 共生真菌", 4, CardType.ACTIVE,
        tags=(Tag.MICROBE,),
        can_play=require_temp_min(-14),
        action_used_each_gen=True,
        resource_kind="microbe",
        action=lambda s, p: _add_microbe_to_card(s, p, 47),
        description="需要温度≥-14。行动：本卡+1微生物。",
    ))

    cards.append(_card(
        48, "Bribed Committee 贿赂委员会", 7, CardType.EVENT,
        tags=(Tag.EARTH, Tag.EVENT), vp=-2,
        on_play=lambda s, p: (setattr(p, "tr", p.tr + 2), s.emit(f"  🎖 P{p.idx} TR+2 (贿赂)")),
        description="TR+2。-2VP。",
    ))

    cards.append(_card(
        49, "Optimal Aerobraking 最优气动减速", 7, CardType.AUTOMATED,
        tags=(Tag.SPACE,),
        description="效果：每打一张事件卡，得3MC+3热（简化：被动）。",
    ))

    cards.append(_card(
        50, "Power Infrastructure 电力基础设施", 4, CardType.ACTIVE,
        tags=(Tag.POWER, Tag.BUILDING),
        action=lambda s, p: (
            setattr(p.res, "mc", p.res.mc + p.res.energy),
            setattr(p.res, "energy", 0),
        ),
        action_used_each_gen=True,
        description="行动：所有能源转为MC。",
    ))

    # ═════════ 扩容包：80+ 张项目卡覆盖更多机制 ═════════

    def _q(id, name, cost, ctype, tags=(), vp=0, can=None, play=None,
           action=None, action_each=False, desc=""):
        return Card(id=id, name=name, cost=cost, card_type=ctype, tags=tags,
                    vp=vp, can_play=can, on_play=play, action=action,
                    action_used_each_gen=action_each, description=desc)

    # ─── 建筑/资源类 (id 150+) ───
    cards += [
        _q(150, "Iron Works 钢铁厂", 11, CardType.AUTOMATED, (Tag.BUILDING,),
            play=combine(gain_prod("steel", 1), gain_prod("mc", 1)),
            desc="钢产能+1, MC 产能+1"),
        _q(151, "Methane Refinery 甲烷精炼", 16, CardType.AUTOMATED, (Tag.BUILDING,),
            vp=2, play=combine(gain_prod("titanium", 1), gain_prod("heat", 2)),
            desc="钛产能+1, 热产能+2  VP+2"),
        _q(152, "Ore Processor 矿石处理器", 13, CardType.ACTIVE, (Tag.BUILDING,),
            action=lambda s, p: (
                setattr(p.res, "energy", p.res.energy - 4),
                setattr(p.res, "titanium", p.res.titanium + 1),
                raise_oxygen(1)(s, p),
            ) if p.res.energy >= 4 else None,
            action_each=True,
            desc="行动：付4能源得1钛+氧气+1"),
        _q(153, "Cartel 联合垄断", 8, CardType.AUTOMATED, (Tag.EARTH,),
            play=lambda s, p: setattr(p.res, "mc_prod",
                p.res.mc_prod + p.count_tag_including_events(Tag.EARTH)),
            desc="MC 产能 += 你的地球标签数"),
        _q(154, "Insulation 绝缘层", 2, CardType.AUTOMATED, (),
            play=lambda s, p: (
                setattr(p.res, "heat_prod", max(0, p.res.heat_prod - 1)),
                setattr(p.res, "mc_prod", p.res.mc_prod + 1),
            ) if p.res.heat_prod >= 1 else None,
            desc="热产能-1换 MC 产能+1（若有热产能）"),
        _q(155, "Industrial Microbes 工业微生物", 12, CardType.AUTOMATED,
            (Tag.MICROBE, Tag.BUILDING),
            play=combine(gain_prod("energy", 1), gain_prod("steel", 1)),
            desc="能源产能+1, 钢产能+1"),
        _q(156, "Solar Wind Power 太阳风电", 11, CardType.AUTOMATED,
            (Tag.SCIENCE, Tag.SPACE, Tag.POWER),
            play=combine(gain_prod("energy", 1), gain("titanium", 2)),
            desc="能源产能+1, +2钛"),
        _q(157, "Mass Driver 质量加速器", 23, CardType.AUTOMATED,
            (Tag.BUILDING, Tag.SPACE), vp=2,
            play=lambda s, p: setattr(p.res, "titanium_prod", p.res.titanium_prod + 2),
            desc="钛产能+2  VP+2"),
        _q(158, "Land Claim 土地圈占", 1, CardType.EVENT, (Tag.EVENT,),
            play=lambda s, p: s.queue_greenery_placement(p),
            desc="放置1块绿地（不计氧气）— 简化为正常绿地"),
        _q(159, "Lake Marineris 玛丽内里斯湖", 18, CardType.AUTOMATED, (), vp=2,
            can=require_temp_min(0),
            play=combine(place_ocean(), place_ocean()),
            desc="温度≥0。放2海洋  VP+2"),
        _q(160, "Magnetic Field Generators 磁场发生器", 20, CardType.AUTOMATED, (Tag.BUILDING,),
            vp=3, play=combine(lose_prod("energy", 4), gain_prod("plants", 2),
                                lambda s, p: (setattr(p, "tr", p.tr + 3),
                                              s.emit(f"  🧲 P{p.idx} TR+3"))),
            desc="能源产能-4, 植物产能+2, TR+3  VP+3"),
        _q(161, "Tundra Plants 苔原植物", 5, CardType.AUTOMATED, (Tag.PLANT,),
            can=require_temp_min(-10),
            play=combine(gain_prod("plants", 1), gain("plants", 2)),
            desc="温度≥-10。植物产能+1, +2植物"),
        _q(162, "Genetic Repository 基因库", 2, CardType.ACTIVE, (Tag.SCIENCE,),
            action=lambda s, p: setattr(p.res, "plants", p.res.plants + 1),
            action_each=True,
            desc="行动：每代+1植物"),
        _q(163, "Methane From Titan 泰坦甲烷", 28, CardType.AUTOMATED,
            (Tag.JOVIAN, Tag.SPACE), vp=2, can=require_oxygen_min(2),
            play=combine(gain_prod("heat", 2), gain_prod("plants", 2)),
            desc="氧气≥2%。热产能+2, 植物产能+2  VP+2"),
        _q(164, "Power Grid 电力网", 18, CardType.AUTOMATED, (Tag.POWER,),
            play=lambda s, p: setattr(p.res, "energy_prod",
                p.res.energy_prod + p.count_tag_including_events(Tag.POWER)),
            desc="能源产能 += 你的能源标签数"),
        _q(165, "Domed Crater 圆顶陨石坑", 24, CardType.AUTOMATED,
            (Tag.BUILDING, Tag.CITY), vp=3,
            can=require_oxygen_max(7),
            play=combine(gain_prod("mc", 3), gain("plants", 3), place_city()),
            desc="氧气≤7%。MC产能+3, +3植物, 放1城市  VP+3"),
        _q(166, "Noctis City Noctis城", 18, CardType.AUTOMATED,
            (Tag.BUILDING, Tag.CITY),
            play=combine(lose_prod("energy", 1), gain_prod("mc", 3), place_city()),
            desc="能源产能-1, MC产能+3, 放Noctis城"),
        _q(167, "Mangrove 红树林", 12, CardType.AUTOMATED, (Tag.PLANT,),
            vp=1, can=require_temp_min(4),
            play=lambda s, p: s.queue_greenery_placement(p),
            desc="温度≥4。直接放1绿地（视为植物建造）  VP+1"),
        _q(168, "Beam From a Thorium Asteroid 钍小行星束", 32, CardType.AUTOMATED,
            (Tag.JOVIAN, Tag.SPACE, Tag.POWER), vp=1,
            play=combine(gain_prod("heat", 3), gain_prod("energy", 3)),
            desc="热产能+3, 能源产能+3  VP+1"),
        _q(169, "Quantum Extractor 量子萃取器", 13, CardType.AUTOMATED,
            (Tag.SCIENCE, Tag.POWER),
            can=require_tag_count(Tag.SCIENCE, 4),
            play=combine(gain_prod("energy", 4), gain("titanium", 1)),
            desc="需要4科学。能源产能+4, +1钛"),
    ]

    # ─── 太空/科学类 (id 70-89) ───
    cards += [
        _q(170, "Space Station 太空站", 10, CardType.ACTIVE, (Tag.SPACE,),
            vp=1, play=lambda s, p: setattr(p, "_space_discount", True),
            desc="所有太空卡-2 MC（持续, VP+1）"),
        _q(171, "Earth Office 地球办事处", 1, CardType.ACTIVE, (Tag.EARTH,),
            play=lambda s, p: setattr(p, "_earth_discount", True),
            desc="所有地球卡-3 MC（持续）"),
        _q(172, "Research Network 研究网络", 11, CardType.ACTIVE, (Tag.SCIENCE,),
            vp=2, play=combine(draw_cards(2), gain_prod("mc", 1)),
            desc="抽2张, MC产能+1  VP+2"),
        _q(173, "Energy Tapping 能量汲取", 3, CardType.AUTOMATED, (Tag.POWER,), vp=-1,
            play=gain_prod("energy", 1),
            desc="能源产能+1  VP-1"),
        _q(174, "Adaptation Technology 适应科技", 12, CardType.ACTIVE, (Tag.SCIENCE,), vp=1,
            play=lambda s, p: setattr(p, "_relax_requirements", 2),
            desc="所有需求放宽±2  VP+1"),
        _q(175, "Tectonic Stress Power 板块构造电力", 18, CardType.AUTOMATED,
            (Tag.POWER, Tag.BUILDING),
            can=require_tag_count(Tag.SCIENCE, 2),
            play=combine(gain_prod("energy", 3),
                         lambda s, p: (setattr(p, "tr", p.tr + 1),
                                       s.emit(f"  ⚡ TR+1"))),
            desc="需要2科学。能源产能+3, TR+1"),
        _q(176, "Shuttles 穿梭机", 10, CardType.AUTOMATED,
            (Tag.SPACE,), vp=1,
            can=require_oxygen_min(5),
            play=combine(lose_prod("energy", 1), gain_prod("mc", 2)),
            desc="氧气≥5%。能源-1, MC产能+2  VP+1"),
        _q(177, "Soletta 太阳镜", 35, CardType.AUTOMATED, (Tag.SPACE,), vp=1,
            play=lambda s, p: setattr(p.res, "heat_prod", p.res.heat_prod + 7),
            desc="热产能+7  VP+1"),
        _q(178, "Worms 虫", 8, CardType.AUTOMATED, (Tag.MICROBE,), can=require_oxygen_min(4),
            play=lambda s, p: setattr(p.res, "plants_prod",
                p.res.plants_prod + max(1, p.count_tag(Tag.MICROBE) // 2)),
            desc="氧气≥4%。植物产能 += 微生物标签//2 (≥1)"),
        _q(179, "Decomposers 分解者", 5, CardType.ACTIVE, (Tag.MICROBE,), vp=0,
            can=require_oxygen_min(3), action_each=True,
            action=lambda s, p: _add_microbe_to_card(s, p, 79),
            desc="氧气≥3%。行动：本卡+1微生物（每2=1VP）"),
    ]

    # ─── 事件 / 红卡 (id 80-99) ───
    cards += [
        _q(180, "Imported GHG 进口温室气体", 7, CardType.EVENT, (Tag.SPACE, Tag.EARTH, Tag.EVENT),
            play=combine(gain_prod("heat", 1), raise_temperature(1)),
            desc="热产能+1, 温度+1档"),
        _q(181, "Strip Mine 露天矿", 25, CardType.EVENT,
            (Tag.BUILDING, Tag.EVENT),
            play=combine(lose_prod("energy", 2), gain_prod("steel", 2),
                         gain_prod("titanium", 1), raise_oxygen(2)),
            desc="能源-2, 钢+2, 钛+1, 氧气+2"),
        _q(182, "Acquired Company 收购公司", 10, CardType.AUTOMATED, (Tag.EARTH,),
            play=gain_prod("mc", 3),
            desc="MC产能+3"),
        _q(183, "Asteroid Belt 小行星带", 24, CardType.AUTOMATED, (Tag.SPACE,),
            vp=2, play=combine(gain_prod("titanium", 2), gain("titanium", 4)),
            desc="钛产能+2, +4钛  VP+2"),
        _q(184, "Permafrost Extraction 冻土萃取", 8, CardType.EVENT, (Tag.EVENT,),
            can=require_temp_min(-8),
            play=place_ocean(),
            desc="温度≥-8。放1海洋"),
        _q(185, "Polar Industries 极地工业", 15, CardType.AUTOMATED, (Tag.BUILDING,),
            vp=2, can=require_temp_max(-2),
            play=combine(gain_prod("heat", 2), place_ocean()),
            desc="温度≤-2。热产能+2, 放1海洋  VP+2"),
        _q(186, "GMO Contract 转基因合同", 3, CardType.ACTIVE, (Tag.EARTH, Tag.SCIENCE),
            play=lambda s, p: setattr(p, "_gmo_active", True),
            desc="每打植物/微生物/动物卡 +2MC（持续）"),
        _q(187, "Symbiotic Algae 共生藻类", 4, CardType.AUTOMATED,
            (Tag.PLANT, Tag.MICROBE),
            play=gain_prod("plants", 1),
            desc="植物产能+1"),
        _q(188, "Sister Planet Support 姐妹星支援", 7, CardType.AUTOMATED, (Tag.EARTH,),
            play=combine(gain_prod("mc", 1), gain("mc", 5)),
            desc="MC产能+1, 立即+5MC"),
        _q(189, "Tropos 大气工程", 8, CardType.AUTOMATED, (Tag.BUILDING,),
            play=raise_temperature(1),
            desc="温度+1档"),
    ]

    # ─── 动物/微生物战略 (id 90-99) ───
    cards += [
        _q(190, "Herbivores 植食动物", 12, CardType.ACTIVE, (Tag.ANIMAL,),
            can=require_oxygen_min(8), action_each=True,
            action=lambda s, p: _add_animal_to_card(s, p, 90),
            play=lose_prod("plants", 1),
            desc="氧气≥8%。每代+1动物=1VP"),
        _q(191, "Tardigrades 缓步动物", 4, CardType.ACTIVE, (Tag.MICROBE,),
            action_each=True,
            action=lambda s, p: _add_microbe_to_card(s, p, 91),
            desc="行动：本卡+1微生物。终局每4=1VP"),
        _q(192, "Ants 蚂蚁", 9, CardType.ACTIVE, (Tag.MICROBE,), vp=0,
            can=require_oxygen_min(4),
            action_each=True,
            action=lambda s, p: _add_microbe_to_card(s, p, 92),
            desc="氧气≥4%。每微生物=1VP"),
        _q(193, "Nitrogen-Rich Asteroid 含氮小行星", 31, CardType.EVENT,
            (Tag.SPACE, Tag.EVENT),
            play=combine(raise_temperature(1),
                         lambda s, p: (setattr(p, "tr", p.tr + 2),
                                       s.emit(f"  ☄ TR+2"))),
            desc="温度+1档, TR+2"),
        _q(194, "Black Polar Dust 黑色极地尘", 15, CardType.AUTOMATED, (),
            play=combine(lose_prod("mc", 2), gain_prod("heat", 3), place_ocean()),
            desc="MC产能-2, 热产能+3, 放1海洋"),
        _q(195, "Standard Technology 标准化技术", 6, CardType.ACTIVE, (Tag.SCIENCE,),
            play=lambda s, p: setattr(p, "_std_discount", True),
            desc="所有标准项目-3MC（持续）"),
        _q(196, "Anti-Gravity Technology 反重力科技", 14, CardType.ACTIVE, (Tag.SCIENCE,),
            vp=3, can=require_tag_count(Tag.SCIENCE, 7),
            play=lambda s, p: setattr(p, "_antigravity", True),
            desc="需要7科学。所有蓝/绿卡-2MC  VP+3"),
        _q(197, "Investment Loan 投资贷款", 3, CardType.EVENT, (Tag.EARTH, Tag.EVENT),
            play=combine(lose_prod("mc", 1), gain("mc", 10)),
            desc="MC产能-1, 立即+10MC"),
        _q(198, "Mineral Deposit 矿藏", 5, CardType.EVENT, (Tag.EVENT,),
            play=gain("steel", 5),
            desc="立即+5钢"),
        _q(199, "Ice Cap Melting 冰盖融化", 5, CardType.EVENT, (Tag.EVENT,),
            can=require_temp_min(2),
            play=place_ocean(),
            desc="温度≥2。放1海洋"),
    ]

    # ─── 高阶/连锁 (id 100-119) — 注意公司从 100 开始, 但项目卡 ID 复用问题需避免 ───
    # 公司用 100-105，扩容用 110-129
    cards += [
        _q(210, "Capital 首都", 26, CardType.AUTOMATED,
            (Tag.BUILDING, Tag.CITY), vp=0,
            can=require_oceans_min(4),
            play=combine(lose_prod("energy", 2), gain_prod("mc", 5),
                         place_city()),
            desc="海洋≥4。能源-2, MC产能+5, 放城市"),
        _q(211, "Underground City 地下城", 18, CardType.AUTOMATED,
            (Tag.BUILDING, Tag.CITY),
            play=combine(lose_prod("energy", 2), gain_prod("steel", 2),
                         place_city()),
            desc="能源-2, 钢产能+2, 放城市"),
        _q(212, "Urbanized Area 城市化区", 10, CardType.AUTOMATED,
            (Tag.BUILDING, Tag.CITY),
            play=combine(lose_prod("energy", 1), gain_prod("mc", 2),
                         place_city()),
            desc="能源-1, MC产能+2, 放城市"),
        _q(213, "Phobos Space Haven Phobos太空港", 25, CardType.AUTOMATED,
            (Tag.SPACE, Tag.CITY), vp=3,
            play=combine(gain_prod("titanium", 1), gain_prod("mc", 3)),
            desc="钛产能+1, MC产能+3  VP+3"),
        _q(214, "Ganymede Colony 木卫三殖民地", 20, CardType.AUTOMATED,
            (Tag.JOVIAN, Tag.SPACE, Tag.CITY),
            play=lambda s, p: setattr(p, "vp_from_milestones",
                p.vp_from_milestones + p.count_tag(Tag.JOVIAN)),
            desc="VP = 你的木星标签数"),
        _q(215, "Teractor 投资集团", 10, CardType.AUTOMATED, (Tag.EARTH,),
            play=combine(gain_prod("mc", 2), gain("mc", 4)),
            desc="MC产能+2, +4MC"),
        _q(216, "Ecological Survey 生态调查", 2, CardType.AUTOMATED,
            (Tag.SCIENCE,), can=require_oxygen_min(9),
            play=lambda s, p: (setattr(p.res, "plants",
                p.res.plants + p.count_tag(Tag.PLANT) + p.count_tag(Tag.ANIMAL))),
            desc="氧气≥9%。植物 += 植物+动物标签"),
        _q(217, "Geological Survey 地质调查", 2, CardType.AUTOMATED, (Tag.SCIENCE,),
            can=require_oxygen_min(4),
            play=lambda s, p: (setattr(p.res, "steel",
                p.res.steel + p.count_tag(Tag.BUILDING))),
            desc="氧气≥4%。钢 += 建筑标签"),
        _q(218, "Building Industries 建筑工业", 6, CardType.AUTOMATED,
            (Tag.BUILDING,),
            play=combine(lose_prod("energy", 1), gain_prod("steel", 2)),
            desc="能源-1, 钢产能+2"),
        _q(219, "Industrial Center 工业中心", 4, CardType.ACTIVE, (Tag.BUILDING,),
            action=lambda s, p: (
                setattr(p.res, "mc", p.res.mc - 7),
                setattr(p.res, "steel_prod", p.res.steel_prod + 1),
            ) if p.res.mc >= 7 else None,
            action_each=True,
            desc="行动：付7MC, 钢产能+1"),
        _q(220, "Power Supply Consortium 电力供应联合体", 5, CardType.AUTOMATED, (Tag.POWER,),
            play=lambda s, p: (
                # 取一名玩家能源产能 -1，自己 +1
                _drain_energy_prod(s, p),
            ),
            desc="他玩家能源产能-1, 自己能源产能+1"),
        _q(221, "Spinoff Department 衍生部门", 10, CardType.ACTIVE,
            (Tag.SCIENCE,), vp=1,
            play=combine(gain_prod("mc", 2)),
            desc="MC产能+2  VP+1"),
        _q(222, "Hired Raiders 雇佣劫匪", 1, CardType.EVENT, (Tag.EVENT,),
            play=lambda s, p: _hired_raiders(s, p),
            desc="从一玩家偷 2 钢或 3 MC"),
        _q(223, "Solar Pioneers 太阳先锋", 4, CardType.AUTOMATED, (Tag.POWER,),
            play=gain_prod("energy", 1),
            desc="能源产能+1"),
        _q(224, "Algae 藻类", 10, CardType.AUTOMATED,
            (Tag.PLANT,), can=require_oceans_min(5),
            play=combine(gain("plants", 1), gain_prod("plants", 2)),
            desc="海洋≥5。+1植物, 植物产能+2"),
        _q(225, "Toll Station 收费站", 12, CardType.AUTOMATED, (Tag.SPACE,),
            play=lambda s, p: setattr(p.res, "mc_prod",
                p.res.mc_prod + sum(1 for q in s.players
                                    if q.idx != p.idx
                                    for c in q.played
                                    if Tag.SPACE in c.tags)),
            desc="MC产能 += 其他玩家的太空标签数"),
        _q(226, "Asteroid Mining 小行星采矿", 30, CardType.AUTOMATED, (Tag.JOVIAN, Tag.SPACE),
            vp=2, play=gain_prod("titanium", 2),
            desc="钛产能+2  VP+2"),
        _q(227, "Restricted Area 限制区", 11, CardType.ACTIVE,
            (Tag.SCIENCE,),
            action=lambda s, p: (setattr(p.res, "mc", p.res.mc - 2),
                                 draw_cards(1)(s, p)) if p.res.mc >= 2 else None,
            action_each=True,
            desc="行动：付2MC抽1张"),
        _q(228, "Energy Saving 节能", 15, CardType.AUTOMATED, (Tag.POWER,),
            play=lambda s, p: setattr(p.res, "mc_prod",
                p.res.mc_prod + len(s.board.cities())),
            desc="MC产能 += 棋盘上城市总数"),
        _q(229, "Convoy from Europa 木卫二商队", 15, CardType.EVENT,
            (Tag.SPACE, Tag.EVENT),
            play=combine(place_ocean(), draw_cards(1)),
            desc="放1海洋, 抽1张"),
    ]

    # ─── 动物 / 微生物 高阶 (id 130-149) ───
    cards += [
        _q(230, "Small Animals 小型动物", 6, CardType.ACTIVE, (Tag.ANIMAL,),
            can=require_oxygen_min(6), action_each=True,
            action=lambda s, p: _add_animal_to_card(s, p, 130),
            play=lose_prod("plants", 1),
            desc="氧气≥6%。每动物=1VP"),
        _q(231, "Pets 宠物", 10, CardType.ACTIVE, (Tag.ANIMAL, Tag.EARTH),
            vp=1, action_each=False,
            action=lambda s, p: _add_animal_to_card(s, p, 131),
            desc="不可被攻击。每动物=1VP, +1 起手  VP+1"),
        _q(232, "Hydro-Electric Energy 水电能", 11, CardType.AUTOMATED, (Tag.POWER,),
            can=require_oceans_min(3),
            play=combine(lose_prod("mc", 1), gain_prod("energy", 3)),
            desc="海洋≥3。MC产能-1, 能源产能+3"),
        _q(233, "Special Design 特殊设计", 4, CardType.EVENT,
            (Tag.SCIENCE, Tag.EVENT),
            play=lambda s, p: setattr(p, "_relax_requirements_once", 2),
            desc="本回合下一张卡需求放宽±2"),
        _q(234, "Adapted Lichen 适应地衣", 9, CardType.AUTOMATED, (Tag.PLANT,),
            play=gain_prod("plants", 1),
            desc="植物产能+1"),
        _q(235, "Vesta Shipyard Vesta船坞", 15, CardType.AUTOMATED,
            (Tag.JOVIAN, Tag.SPACE), vp=1,
            play=gain_prod("titanium", 1),
            desc="钛产能+1  VP+1"),
        _q(236, "Tropical Resort 热带度假村", 13, CardType.AUTOMATED,
            (Tag.BUILDING, Tag.EARTH),
            vp=2, play=combine(lose_prod("heat", 2), gain_prod("mc", 3)),
            desc="热产能-2, MC产能+3  VP+2"),
        _q(237, "Toll Booth 城市收费", 8, CardType.AUTOMATED, (Tag.BUILDING,),
            play=lambda s, p: setattr(p.res, "mc", p.res.mc + len(s.board.cities()) * 2),
            desc="立即获得 MC = 棋盘城市数 × 2"),
        _q(238, "Catalyst 催化剂", 7, CardType.EVENT, (Tag.SCIENCE, Tag.EVENT),
            play=lambda s, p: (setattr(p, "tr", p.tr + 1), draw_cards(1)(s, p)),
            desc="TR+1, 抽1张"),
        _q(239, "Fueled Generators 燃料发电机", 1, CardType.AUTOMATED, (Tag.BUILDING,),
            play=combine(lose_prod("mc", 1), gain_prod("energy", 1)),
            desc="MC产能-1, 能源产能+1"),
        _q(240, "Open City 开放城市", 23, CardType.AUTOMATED,
            (Tag.BUILDING, Tag.CITY), vp=2, can=require_oxygen_min(12),
            play=combine(lose_prod("energy", 1), gain_prod("mc", 4),
                         gain("plants", 2), place_city()),
            desc="氧气≥12%。能源-1, MC产能+4, +2植物, 放城  VP+2"),
        _q(241, "Mars-Wide City 全火星都市", 35, CardType.AUTOMATED,
            (Tag.BUILDING, Tag.CITY), vp=4,
            can=lambda s, p: len(s.board.cities()) >= 3,
            play=combine(gain_prod("mc", 5), place_city(), place_city()),
            desc="需城市≥3。MC产能+5, 放2城市  VP+4"),
        _q(242, "Microbe Survey 微生物调查", 4, CardType.AUTOMATED, (Tag.SCIENCE,),
            can=require_oxygen_min(3),
            play=lambda s, p: setattr(p.res, "plants",
                p.res.plants + p.count_tag(Tag.MICROBE) * 2),
            desc="氧气≥3%。植物 += 微生物标签×2"),
        _q(243, "Towing a Asteroid 拖小行星", 22, CardType.EVENT,
            (Tag.SPACE, Tag.EVENT),
            play=combine(raise_temperature(2), gain("titanium", 2)),
            desc="温度+2档, +2钛"),
        _q(244, "Gold Rush 淘金热", 8, CardType.EVENT, (Tag.EVENT,),
            play=lambda s, p: setattr(p.res, "steel", p.res.steel + 6),
            desc="立即+6钢"),
        _q(245, "Energy Storage 储能装置", 11, CardType.ACTIVE, (Tag.BUILDING, Tag.POWER),
            action=lambda s, p: setattr(p.res, "energy", p.res.energy + 4),
            action_each=True,
            desc="行动：每代+4能源"),
        _q(246, "Polar Greenhouses 极地温室", 6, CardType.AUTOMATED, (Tag.PLANT,),
            can=require_temp_max(0),
            play=gain_prod("plants", 1),
            desc="温度≤0。植物产能+1"),
        _q(247, "Archaebacteria 古细菌", 6, CardType.AUTOMATED, (Tag.MICROBE,),
            can=require_temp_max(-18),
            play=gain_prod("plants", 1),
            desc="温度≤-18。植物产能+1"),
        _q(248, "Volcanic Pools 火山池", 8, CardType.ACTIVE, (Tag.BUILDING,),
            action=lambda s, p: (
                setattr(p.res, "energy", p.res.energy - 2),
                setattr(p.res, "heat", p.res.heat + 2),
                setattr(p.res, "mc", p.res.mc + 2),
            ) if p.res.energy >= 2 else None,
            action_each=True,
            desc="行动：付2能源得 2热+2MC"),
        _q(249, "Solar Reflectors 太阳反射板", 23, CardType.AUTOMATED, (Tag.SPACE,),
            vp=2, play=lambda s, p: setattr(p.res, "heat_prod", p.res.heat_prod + 5),
            desc="热产能+5  VP+2"),
    ]

    return cards


# 辅助：吸取他人能源产能（卡 120）
def _drain_energy_prod(state, player):
    targets = sorted([q for q in state.players if q.idx != player.idx],
                     key=lambda q: -q.res.energy_prod)
    for q in targets:
        if q.res.energy_prod >= 1:
            q.res.energy_prod -= 1
            player.res.energy_prod += 1
            state.emit(f"  🔌 P{player.idx} 抢 P{q.idx} 能源产能")
            return
    # 没人有能源产能，仅自加
    player.res.energy_prod += 1


# 辅助：雇佣劫匪（卡 122）
def _hired_raiders(state, player):
    targets = [q for q in state.players if q.idx != player.idx]
    if not targets:
        return
    target = max(targets, key=lambda q: q.res.steel + q.res.mc / 2)
    if target.res.steel >= 2:
        target.res.steel -= 2
        player.res.steel += 2
        state.emit(f"  🥷 P{player.idx} 从 P{target.idx} 抢2钢")
    elif target.res.mc >= 3:
        target.res.mc -= 3
        player.res.mc += 3
        state.emit(f"  🥷 P{player.idx} 从 P{target.idx} 抢3MC")


# ─────────── 卡上资源标记的辅助函数 ───────────

def _add_microbe_to_card(state, player, card_id: int) -> None:
    for c in player.played:
        if c.id == card_id:
            c.resources_on_card += 1
            state.emit(f"  🦠 P{player.idx} 在「{c.name}」加1微生物 (共{c.resources_on_card})")
            break


def _add_animal_to_card(state, player, card_id: int) -> None:
    for c in player.played:
        if c.id == card_id:
            c.resources_on_card += 1
            state.emit(f"  🐾 P{player.idx} 在「{c.name}」加1动物 (共{c.resources_on_card})")
            break


# ─────────── 公司卡 ───────────

def build_corporations() -> list[Card]:
    corps: list[Card] = []

    corps.append(_card(
        100, "CrediCor 信用公司", 0, CardType.CORPORATION,
        on_play=lambda s, p: (
            setattr(p.res, "mc", 57),
            _set_credicor_hook(p),
        ),
        description="起始57MC。打出≥20MC的卡时立即获得4MC。",
    ))

    corps.append(_card(
        101, "Helion 氦能", 0, CardType.CORPORATION,
        on_play=lambda s, p: (
            setattr(p.res, "mc", 42),
            setattr(p.res, "heat_prod", p.res.heat_prod + 3),
            _set_helion_hook(p),
        ),
        description="起始42MC，热产能+3。可以用热当MC支付。",
    ))

    corps.append(_card(
        102, "Mining Guild 矿业行会", 0, CardType.CORPORATION,
        on_play=lambda s, p: (
            setattr(p.res, "mc", 30),
            setattr(p.res, "steel", 5),
            setattr(p.res, "steel_prod", p.res.steel_prod + 1),
        ),
        description="起始30MC，5钢，钢产能+1。",
    ))

    corps.append(_card(
        103, "Tharsis Republic 塔尔西斯共和国", 0, CardType.CORPORATION,
        on_play=lambda s, p: (
            setattr(p.res, "mc", 40),
        ),
        description="起始40MC。每放置一座城市MC产能+1。",
    ))

    corps.append(_card(
        104, "Inventrix 发明者公司", 0, CardType.CORPORATION,
        on_play=lambda s, p: (
            setattr(p.res, "mc", 45),
            # 起始多 3 张牌
            None,
        ),
        description="起始45MC。游戏开始多抽3张牌。需求范围放宽±2。",
    ))

    corps.append(_card(
        105, "EcoLine 生态线", 0, CardType.CORPORATION,
        on_play=lambda s, p: (
            setattr(p.res, "mc", 36),
            setattr(p.res, "plants", 3),
            setattr(p.res, "plants_prod", p.res.plants_prod + 2),
        ),
        description="起始36MC，3植物，植物产能+2。可用7植物造绿地（标准是8）。",
    ))

    return corps


def _set_credicor_hook(player) -> None:
    """打出≥20MC卡时立即获4MC"""
    def hook(state, p, card):
        if card.cost >= 20 and card.card_type != CardType.CORPORATION:
            p.res.mc += 4
            state.emit(f"  💰 P{p.idx} CrediCor 触发：+4MC")
    player.on_card_played_fn = hook


def _set_helion_hook(player) -> None:
    """允许热当MC用 — 标记，由 actions 层检查"""
    setattr(player, "can_use_heat_as_mc", True)
