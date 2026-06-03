"""L0 对手：纯随机 baseline。

行为：每回合 50% 概率不动；50% 概率从随机我方星球往随机方向发送随机数量的船。

用途：

- 验证评测系统跑通（我们应当 ~100% 胜）
- 作为 sanity check：任何 agent 打不过这个就是有严重 bug
"""

from __future__ import annotations

import math
import random


def agent(obs, config=None):
    """随机 agent。"""
    # 解包 obs
    if isinstance(obs, dict):
        planets = obs.get("planets", [])
        player = obs.get("player", 0)
    else:
        planets = getattr(obs, "planets", [])
        player = getattr(obs, "player", 0)

    # 半数回合不行动
    if random.random() < 0.5:
        return []

    # planets 格式：[id, owner, x, y, radius, ships, production]
    my_planets = [p for p in planets if p[1] == player and p[5] > 1]
    if not my_planets:
        return []

    # 随机挑一个源
    src = random.choice(my_planets)
    # 随机方向
    angle = random.uniform(-math.pi, math.pi)
    # 派 1 ~ 50% 当前船数
    ships = max(1, random.randint(1, max(1, src[5] // 2)))

    return [[src[0], angle, ships]]
