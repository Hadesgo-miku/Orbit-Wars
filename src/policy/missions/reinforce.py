"""Mission: reinforce — 增援自家受威胁的星球。

触发条件：``world.hold_status(planet_id)`` 显示该星球未来 ``DEFENSE_HORIZON``
内会被攻陷或 garrison 跌破阈值。

实现指引（参考 lb-1200 的 ``build_reinforce_missions``）：

1. 遍历 ``world.my_planets``
2. 若 ``hold_status.holds_full == False``，计算所需补充船数
3. 从邻近的我方星球（按距离）找最小可用源
4. 用 M2 的 ``solve_intercept`` 求角度与到达时间
5. 必须经过 M4 的 ``swept_by_other`` 过滤
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...env.world import World
    from ..modes import Policy
    from ..scoring import Mission


def build_reinforce_missions(world: "World", policy: "Policy") -> list["Mission"]:
    raise NotImplementedError(
        "M5.reinforce 由 Task agent 实现；参考 lb-1200 的 build_reinforce_missions。"
    )
