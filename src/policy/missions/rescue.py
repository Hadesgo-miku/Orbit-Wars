"""Mission: rescue — 紧急自救。

与 reinforce 的区别：

- reinforce 是"还有几个 tick 缓冲时做的预防性增援"
- rescue 是"再不动就丢，all-in 救一次或正式放弃"

rescue 必须先经过 M4 的 ``is_planet_doomed`` 过滤，若注定失守则不发救援
（避免把救援船白扔，等敌人打过来后白白损失）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...env.world import World
    from ..modes import Policy
    from ..scoring import Mission


def build_rescue_missions(world: "World", policy: "Policy") -> list["Mission"]:
    raise NotImplementedError(
        "M5.rescue 由 Task agent 实现；参考 lb-1200 的 build_rescue_missions。"
    )
