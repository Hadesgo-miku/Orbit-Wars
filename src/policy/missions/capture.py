"""Mission: capture — 占中立或敌方星球（主流进攻 mission）。

实现指引：

- 对每对 (我方源, 中立/敌方目标) 产生一个候选 Mission
- 中立目标和敌方目标走不同的 margin（敌方守军会继续生产，需要更多 buffer）
- 与 M2 的 ``solve_intercept`` 配合
- 必须经过 M4 的 ``swept_by_other`` + ``segment_hits_sun`` 过滤

预期产出：每回合数百个候选，由 M6 评分后由 M9 选择执行。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...env.world import World
    from ..modes import Policy
    from ..scoring import Mission


def build_capture_missions(world: "World", policy: "Policy") -> list["Mission"]:
    raise NotImplementedError(
        "M5.capture 由 Task agent 实现；参考 lb-1200 的主进攻枚举循环。"
    )
