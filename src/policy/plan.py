"""M9 — Plan Orchestrator。

把 World / Policy / Missions / Scoring 串起来，按时间预算调度并产出最终 moves。

调度伪代码（详见 master-plan.md §1.3）::

    def plan_moves(world, policy, deadline):
        missions = []
        missions.extend(build_reinforce_missions(world, policy))
        missions.extend(build_rescue_missions(world, policy))
        missions.extend(build_recapture_missions(world, policy))
        missions.extend(build_capture_missions(world, policy))
        missions.extend(build_snipe_missions(world, policy))
        missions.extend(build_crash_exploit_missions(world, policy))

        # 评分排序
        missions = rank_missions(missions, world, policy)

        # 依次提交，每次更新 commitment
        moves = []
        for mission in missions:
            if time.perf_counter() > deadline:
                break
            if world.source_inventory_left(mission.source_id) < mission.ships:
                continue
            moves.append([mission.source_id, mission.angle, mission.ships])
            world.add_commitment(Commitment(...))
        return moves
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..env.world import World
    from .modes import Policy


def plan_moves(
    world: "World",
    policy: "Policy",
    *,
    deadline: float | None = None,
    enable_tie_break: bool = False,
) -> list[list]:
    """生成本回合的全部 moves。

    参数
    ----
    world : World
        已构造好的 World 对象。
    policy : Policy
        ``build_policy(world)`` 的产物。
    deadline : float | None
        ``time.perf_counter()`` 维度的截止时间。None 表示无限。
    enable_tie_break : bool
        是否在 top-2 接近时启用 M7 GBC tie-break。开启会增加 ~50ms。

    返回
    ----
    list[list]
        ``[[source_id, angle, ships], ...]``，可以是空列表。

    实现要点
    --------
    1. 必须 **commitment-aware**：每次提交后立刻 ``world.add_commitment``
    2. 必须遵守 ``decision_time ≤ 850ms``（留 0.15s 给序列化）
    3. 必须经过 M4 三层安全过滤
    4. 必须按 master-plan.md §1.4 列出的所有不变量
    """
    raise NotImplementedError(
        "M9.plan_moves 由 Code Lead 实现；参考 lb-1200 的 plan_moves。"
    )
