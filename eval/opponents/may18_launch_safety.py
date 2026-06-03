"""L2 对手：may18 launch-safety heuristic（公开 1039）。

待 Task agent 移植：``community-examples/orbit-wars-1039-2-lb-launch-safety-heuristic.ipynb``
中 cell 12 的完整 ``agent`` 函数 + cell 6/8 的依赖（fleet_collision_step、solve_intercept 等）。

注意：

1. 该 agent **当年** 1039 分；ELO 时间衰减后，目前实测约在 800–900 区间
2. 但其代码极简清晰，是教学价值最高的一份，**保留作为 L2 对手**
3. 移植时要把所有依赖打成单文件（不要 import 项目内其他模块），
   以便 ``env.run`` 直接调用
"""

from __future__ import annotations


def agent(obs, config=None):
    raise NotImplementedError(
        "Task agent 实现：把 community-examples/orbit-wars-1039-2-lb-launch-safety-"
        "heuristic.ipynb 中的实现合并到此文件。所有依赖（fleet_speed、"
        "solve_intercept、fleet_collision_step 等）需内联，不要 import src/。"
    )
