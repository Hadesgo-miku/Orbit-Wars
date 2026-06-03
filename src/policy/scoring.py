"""M6 — Mission 评分。

公开 baseline 的评分公式可以归纳为：

.. math::
    score = base\\_pv \\times f(danger) \\times safety \\times mtype\\_mult - cost\\_penalty

其中：

- ``base_pv`` = present value（折现到当前 tick）
- ``f(danger)`` = 邻接危险图加权（ally / (ally + enemy) 之类）
- ``safety`` = M4 的 launch_safety_score
- ``mtype_mult`` = mission 类型乘子（reinforce > capture > snipe ...）
- ``cost_penalty`` = 时间惩罚 + 资源占用

本模块的所有数值常量都应在 ``SCORING_PARAMS`` 中暴露，便于 M10 CMA-ES 调参。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..env.world import World
    from .modes import Policy


# ---------------------------------------------------------------------------
# 调参面板（所有数值都在这里，M10 直接对它做 CMA-ES）
# ---------------------------------------------------------------------------


@dataclass
class ScoringParams:
    """打分公式的所有可调常量。

    .. warning::
        新增字段时务必在 ``tuning/configs/v{N}_params.json`` 同步暴露，
        否则 CMA-ES 不会优化它。
    """

    # 现值折现系数
    gamma: float = 0.99
    horizon: int = 110

    # mission 类型乘子（见 lb-1200 的 *_VALUE_MULT 一族）
    capture_neutral_mult: float = 1.2
    capture_hostile_mult: float = 2.0
    reinforce_mult: float = 1.35
    rescue_mult: float = 1.5
    recapture_mult: float = 1.4
    snipe_mult: float = 1.12
    crash_exploit_mult: float = 1.18

    # 阶段乘子
    opening_hostile_mult: float = 1.45
    finishing_hostile_mult: float = 1.15

    # 安全分
    launch_safety_floor: float = 0.4
    launch_safety_scale: float = 30.0

    # 危险图加权
    indirect_friendly_weight: float = 0.35
    indirect_neutral_weight: float = 0.9
    indirect_enemy_weight: float = 1.25
    indirect_value_scale: float = 0.15

    # cost 系数
    attack_cost_turn_weight: float = 0.55
    snipe_cost_turn_weight: float = 0.45


DEFAULT_PARAMS = ScoringParams()


# ---------------------------------------------------------------------------
# Mission 数据类（M5 输出，M6 评分）
# ---------------------------------------------------------------------------


@dataclass
class Mission:
    """统一的 mission 表示，所有 M5.* 都返回 List[Mission]。"""

    type: str                # "capture" / "reinforce" / "rescue" / "recapture" / "snipe" / "crash_exploit" / "salvage"
    source_id: int
    target_id: int
    ships: int
    arrival_turn: int
    angle: float

    #: M6 计算得到的最终分数（生成时为 None）
    score: float | None = None

    #: 给 M9 调度用的附加信息（commitment 锁、需要的 holdup ticks 等）
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 评分接口
# ---------------------------------------------------------------------------


def score_mission(
    mission: Mission,
    world: "World",
    policy: "Policy",
    *,
    params: ScoringParams = DEFAULT_PARAMS,
) -> float:
    """计算单个 mission 的分数。

    实现指引（参考 lb-1200 的 ``target_value`` + ``apply_score_modifiers``）：

    1. 用 ``planet.production * (gamma^arrival - gamma^horizon) / (1 - gamma)`` 算 base_pv
       （[istinetz 的公式](../../community-discussions/some-considerations-on-evaluating-targets.md)）
    2. 用 mission.type 查表得到 mtype_mult
    3. 用 phase 套相应的 phase 乘子
    4. 加 danger map 加权（indirect_features）
    5. 乘 launch_safety_score
    6. 扣 cost：travel_time × cost_turn_weight
    """
    raise NotImplementedError(
        "M6.score_mission 由 Task agent 实现；参考 lb-1200 的 target_value。"
    )


def rank_missions(
    missions: list[Mission],
    world: "World",
    policy: "Policy",
    *,
    params: ScoringParams = DEFAULT_PARAMS,
) -> list[Mission]:
    """对一批 mission 评分并按分数降序排序。

    必要时给每个 mission 写入 ``mission.score`` 字段。
    """
    raise NotImplementedError("M6.rank_missions 由 Task agent 实现。")
