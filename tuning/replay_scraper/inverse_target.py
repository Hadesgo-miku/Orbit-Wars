"""
Inverse Targeting Resolver（M14 子模块）

把 expert 输出的"连续 launch angle"反推为"目标 planet id"。
这是 IL prior 训练数据的关键转换：让 action space 从 (continuous angle, ships)
简化为 (source_id, target_id, ships_bucket)。

核心算法来源：
    community-examples/data-generation-expert-imitation-for-rl.ipynb Cell 7
    resolve_target() 的 ray-casting + 时间步模拟 + 碰撞检测。

算法步骤：
    1. 从 source planet 位置出发，沿 launch angle 单位向量
    2. 速度 = min(1.0 + ships // 20, 6.0)  ← 注意：这是 IL notebook 用的简化公式
       （我们 src/env/physics.py 已实现真实公式，应用前者还是后者待 T0.6 决定）
    3. 每个时间步 t（最多 250）推进 fleet 位置
    4. 对每个其他 planet：
        - 如果 orbiting（r_orb + radius < 50）：按 angular_velocity * t 旋转预测位置
        - 否则：固定位置
        - 碰撞判定：距离 < planet.radius + tolerance（默认 2.0）
    5. 返回首次碰撞的 planet_id，或 -1 表示未命中（视为 noise / cosmic ray launch）

性能：
    - 单次调用约 100-500μs（取决于 planet 数）
    - 100 万条 action 解析 ~ 5-10 分钟

注意事项：
    - 容差 2.0 是 IL notebook 的经验值，对噪声大的提交可能要 3.0
    - 解析失败率 > 15% 时停止入库（master-plan §6.4）
"""
from __future__ import annotations

import math
from typing import Any

DEFAULT_COLLISION_TOLERANCE: float = 2.0
MAX_SIMULATION_TICKS: int = 250
BOARD_CENTER_X: float = 50.0
BOARD_CENTER_Y: float = 50.0
SUN_OUTER_RADIUS: float = 50.0


def fleet_speed_simple(ships: int) -> float:
    """
    IL notebook 用的简化舰队速度公式（min(1.0 + ships // 20, 6.0)）。

    注意：与 src/env/physics.fleet_speed (1.0 + 5.0 * (log(n)/log(1000))**1.5) 不同。
    本模块为对齐 IL notebook 的 resolve_target 行为，使用前者。
    """
    return min(1.0 + ships // 20, 6.0)


def predict_planet_position_at_tick(
    planet: tuple[Any, ...],
    tick: int,
    angular_velocity: float,
) -> tuple[float, float]:
    """
    预测 planet 在某 tick 的位置。

    输入：
        planet: namedtuple/tuple，索引约定 (id, owner, x, y, radius, ships, prod, ...)
        tick: 目标 tick
        angular_velocity: 系统角速度（弧度/tick）

    返回：(x, y)

    规则：
        - 外层 planet（r_orb + radius >= 50）：固定不动
        - 内层 planet：绕 (50, 50) 做圆周运动
    """
    raise NotImplementedError(
        "M14/T0.6 待实现：planet 位置预测（参考 IL notebook Cell 7）"
    )


def resolve_target(
    source_id: int,
    launch_angle: float,
    ships: int,
    planets: list[tuple[Any, ...]],
    angular_velocity: float,
    tolerance: float = DEFAULT_COLLISION_TOLERANCE,
    max_ticks: int = MAX_SIMULATION_TICKS,
) -> int:
    """
    把 launch angle 反推为 target planet id。

    参数：
        source_id: 发起 planet id
        launch_angle: 发射角度（弧度）
        ships: 发射舰队 ship 数
        planets: 当前所有 planet 列表（含 source 自身）
        angular_velocity: 系统角速度
        tolerance: 碰撞判定的额外容差
        max_ticks: 最大模拟 tick 数

    返回：
        碰撞到的 planet_id，或 -1（未命中 / 噪声）

    实现要点（对齐 IL notebook Cell 7）：
        1. 找到 source planet 位置 (fx, fy)
        2. 单位向量 (cos, sin)
        3. 速度由 fleet_speed_simple 给出
        4. 每个 tick：
            - 推进 fleet 位置
            - 对每个非 source planet：算 predicted 位置
            - 距离 < radius + tolerance 即返回该 planet_id
        5. max_ticks 内未命中 → 返回 -1
    """
    raise NotImplementedError(
        "M14/T0.6 待实现：ray-casting + tick-wise 碰撞模拟"
    )


def batch_resolve(
    actions: list[tuple[int, float, int]],
    planets: list[tuple[Any, ...]],
    angular_velocity: float,
    tolerance: float = DEFAULT_COLLISION_TOLERANCE,
) -> list[int]:
    """
    批量反推 target。

    参数：
        actions: [(source_id, launch_angle, ships), ...]
        planets: 当前所有 planet 状态（共享）
        angular_velocity: 系统角速度

    返回：
        [target_id, ...]，长度同 actions；未命中为 -1

    备注：
        这是 extract_features.py 的主消费入口，建议 numpy 化以加速。
    """
    raise NotImplementedError(
        "M14/T0.6 待实现：批量解析（注意性能：100 万条 < 10 分钟）"
    )


def resolution_stats(resolved: list[int]) -> dict[str, float]:
    """
    返回解析率统计。

    返回：
        {
            "total": int,
            "resolved": int,
            "unresolved": int,
            "hit_rate": float (0-1),
        }
    """
    if not resolved:
        return {"total": 0, "resolved": 0, "unresolved": 0, "hit_rate": 0.0}
    total = len(resolved)
    hit = sum(1 for t in resolved if t != -1)
    return {
        "total": total,
        "resolved": hit,
        "unresolved": total - hit,
        "hit_rate": hit / total,
    }
