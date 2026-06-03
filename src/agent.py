"""在线推理入口（Kaggle 提交时调用的 ``agent`` 函数）。

工作流（详见 master-plan.md §1.3）::

    obs ─→ World ─→ Policy ─→ plan_moves ─→ moves

为了让评测系统与单元测试都能复用，本入口同时支持两种调用形式：

- ``agent(obs, config=None)``：Kaggle 标准签名
- ``agent_dict(obs_dict)``：测试用的纯函数版本（接受 dict obs）

骨架阶段（v0）：调用底层模块全部抛 NotImplementedError，
本入口暂时退化到"什么都不做"（返回空列表），用于跑通 import 链。
"""

from __future__ import annotations

import time
from typing import Any

# 提前把所有底层模块 import 进来，方便后续 Code Lead 集成时无需修改这里
from .env.world import World  # noqa: F401
from .policy.modes import build_policy  # noqa: F401
from .policy.plan import plan_moves  # noqa: F401


#: 在线推理时间预算（每回合 1s 硬墙，留 0.15s 给序列化等开销）
DECISION_BUDGET_S: float = 0.85


def agent(obs: Any, config: Any = None) -> list[list]:
    """Kaggle 标准入口。

    参数
    ----
    obs : dict 或 Kaggle obs 对象
        见 ``orbit-wars-overview.md`` §Observation reference
    config : 任意
        Kaggle 会传一个 config，我们不用，但接口必须接受。

    返回
    ----
    list[list]
        每个元素为 ``[from_planet_id, direction_angle, num_ships]``，
        空 list ``[]`` 表示本回合不行动。
    """
    deadline = time.perf_counter() + DECISION_BUDGET_S

    try:
        world = World(obs)
        policy = build_policy(world)
        moves = plan_moves(world, policy, deadline=deadline)
    except NotImplementedError:
        # 骨架阶段（v0）：模块尚未实现，安全 fallback 为"什么都不做"
        return []
    except Exception:
        # 任何其他异常一律 fallback；保护 submission 不会因 bug 整局阵亡
        # （Kaggle 在 agent 抛异常时会判负当前局，需要避免）
        return []

    # 必输验证：每个 move 是合法 list 且 ships > 0
    return [m for m in moves if isinstance(m, list) and len(m) == 3 and m[2] > 0]


def agent_dict(obs_dict: dict) -> list[list]:
    """测试友好的纯函数版本：强制接受 dict obs。"""
    return agent(obs_dict, None)
