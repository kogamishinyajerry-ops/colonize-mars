"""DLC 子系统 — 钩子式扩展，可独立启用"""
from .base import DLC, DLCManager

__all__ = ["DLC", "DLCManager", "load_dlc"]


def load_dlc(name: str) -> DLC:
    """根据名字实例化 DLC"""
    if name == "orbital":
        from .orbital import OrbitalWarfare
        return OrbitalWarfare()
    if name == "parallel":
        from .parallel import ParallelMars
        return ParallelMars()
    if name == "crimson":
        from .crimson import CrimsonStorm
        return CrimsonStorm()
    raise ValueError(f"未知 DLC: {name}")
