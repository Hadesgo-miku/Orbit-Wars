"""L1 对手：最近星球狙击手。

来源：``orbit-wars-guide/main.py``（官方 starter kit 示例）。
策略：对每个我方星球，找最近的我不拥有的星球；若 garrison + 1 在我方可承担范围内，
就发刚好够占领的船。

行为相当简单但合理；应当作为"打通评测系统"的合格初级对手。
"""

from __future__ import annotations

import math


def agent(obs, config=None):
    moves = []

    if isinstance(obs, dict):
        planets = obs.get("planets", [])
        player = obs.get("player", 0)
    else:
        planets = getattr(obs, "planets", [])
        player = getattr(obs, "player", 0)

    # 解析为 (id, owner, x, y, radius, ships, production)
    my_planets = [p for p in planets if p[1] == player]
    targets = [p for p in planets if p[1] != player]

    if not targets:
        return moves

    for mine in my_planets:
        # 找最近非我方
        nearest = None
        min_dist = float("inf")
        for t in targets:
            d = math.hypot(mine[2] - t[2], mine[3] - t[3])
            if d < min_dist:
                min_dist = d
                nearest = t

        if nearest is None:
            continue

        # 需要 target.ships + 1 才能占领
        ships_needed = int(nearest[5]) + 1
        if mine[5] >= ships_needed:
            angle = math.atan2(nearest[3] - mine[3], nearest[2] - mine[2])
            moves.append([int(mine[0]), float(angle), int(ships_needed)])

    return moves
