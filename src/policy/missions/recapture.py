"""Mission: recapture — 抢回刚丢失的星球。

触发条件：上一回合还属于我方、本回合 owner 变成敌方的星球。

实现要点：

- 必须在敌方守军累积到 ``current_ships + production × turns`` 之前命中
- 优先级介于 capture 与 reinforce 之间
- 4P 模式下需要考虑会不会被另一个对手"截胡"（成为他人的 capture 目标）
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...env.world import World
    from ..modes import Policy
    from ..scoring import Mission


def build_recapture_missions(world: "World", policy: "Policy") -> list["Mission"]:
    raise NotImplementedError(
        "M5.recapture 由 Task agent 实现；参考 lb-1200 的 build_recapture_missions。"
    )
