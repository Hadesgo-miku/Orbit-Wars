"""Mission: snipe — 低守敌方的精确狙击。

snipe 与 capture 的区别在于"用最少的代价"：

- capture 在意 "占下来后能保住吗"
- snipe 在意 "用很少的船把对方的高产工厂搞掉一次"

适用场景：发现敌方某高产星球 garrison 几乎为 0（刚被对手自己抽空送舰队）。

实现指引：

- 在 ``policy.phase == "pressure"`` 或 ``"finishing"`` 时优先生成
- ships 取 ``target.ships + production × travel_time + margin``
- 4P 模式下注意不要给第三方做嫁衣
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...env.world import World
    from ..modes import Policy
    from ..scoring import Mission


def build_snipe_missions(world: "World", policy: "Policy") -> list["Mission"]:
    raise NotImplementedError(
        "M5.snipe 由 Task agent 实现；参考 lb-1200 的 build_snipe_mission。"
    )
