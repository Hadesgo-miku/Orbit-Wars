"""M8 — 模式与阶段检测。

输出一个 ``Policy`` 对象，供 M5/M6/M9 使用。Policy 包含：

- 当前 game mode：2P / 4P
- 当前 phase：opening / pressure / finishing / very-late
- 每个我方星球的 reserve（防守预留）和 attack_budget（可用于进攻的份额）
- 4P 时的对手画像（race_eta、近期攻势特征）

设计要点：本模块**只读 World**，不修改 World；产物是 dataclass。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..env.world import World


# ---------------------------------------------------------------------------
# 数据类型
# ---------------------------------------------------------------------------


@dataclass
class Policy:
    """单回合的"策略快照"。"""

    #: 玩家数（2 或 4）
    num_players: int = 2

    #: 阶段标签
    phase: str = "opening"   # opening / pressure / finishing / very-late

    #: 是否处于 "very late"（≤ 60 步剩余）
    is_very_late: bool = False

    #: 每个我方星球应保留的最低 garrison：planet_id → int
    reserve: dict[int, int] = field(default_factory=dict)

    #: 每个我方星球可用于进攻的预算：planet_id → int
    attack_budget: dict[int, int] = field(default_factory=dict)

    #: 4P 时记录的对手画像：opponent_player → 任意 dict
    opponent_profile: dict[int, dict] = field(default_factory=dict)

    #: 仅在 4P 模式下：每个对手"赛跑"到我方第一星球的预计 tick
    enemy_race_eta: dict[int, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 工厂函数（M5/M6/M9 调用）
# ---------------------------------------------------------------------------


def build_policy(world: "World") -> Policy:
    """从 World 构造 Policy。

    实现指引（参考 lb-1200 的 ``build_policy_state``）：

    1. 数对手 → 2P / 4P
    2. 划 phase：``step < 40`` → opening；``step > 440`` → very-late；
       中间根据 我方/敌方 比例与最近 5 回合的舰队动向划 pressure / finishing
    3. 给每个我方星球算 reserve（基于威胁 inventory）
    4. 给每个我方星球算 attack_budget = max(0, garrison - reserve)
    5. 4P 时给每个对手算 race_eta + 最近攻势特征
    """
    raise NotImplementedError(
        "M8.build_policy 由 Task agent 实现；参考 lb-1200 的 build_policy_state。"
    )
